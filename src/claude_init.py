"""
Claude CLI integration for automatic repository initialization.
"""

import os
import subprocess
import shutil
import sys
from typing import Dict, Any, Optional
from pathlib import Path


def check_claude_available() -> Optional[str]:
    """
    Check if claude CLI is available on the system.

    Returns:
        Path to claude executable if available, None otherwise.
    """
    # First, check environment variable
    claude_path = os.environ.get('CLAUDE_CLI_PATH')
    if claude_path and os.path.isfile(claude_path):
        return claude_path

    # Try common installation paths
    common_paths = [
        os.path.expanduser('~/.claude/local/claude'),
        '/usr/local/bin/claude',
        '/usr/bin/claude',
    ]

    for path in common_paths:
        if os.path.isfile(path):
            return path

    # Try to find in PATH using which/where
    try:
        result = subprocess.run(
            ['which', 'claude'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            path = result.stdout.strip()
            # Handle alias output (e.g., "claude: aliased to /path/to/claude")
            if 'aliased to' in path:
                path = path.split('aliased to')[-1].strip()
            if os.path.isfile(path):
                return path
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Try shutil.which as fallback
    claude_path = shutil.which('claude')
    if claude_path:
        return claude_path

    return None


def install_claude_cli(install_method: str = 'auto') -> Dict[str, Any]:
    """
    Attempt to install Claude CLI programmatically.

    This is designed for Docker/Linux environments where npm/homebrew aren't available.
    Uses the official curl-based installation method.

    Args:
        install_method: Installation method ('auto', 'curl', or 'skip')

    Returns:
        Dictionary with installation results:
        {
            'success': bool,
            'claude_path': str or None,
            'message': str,
            'method': str
        }
    """
    result = {
        'success': False,
        'claude_path': None,
        'message': '',
        'method': install_method
    }

    # Check if already installed to avoid duplicate installations
    existing_path = check_claude_available()
    if existing_path:
        result['success'] = True
        result['claude_path'] = existing_path
        result['message'] = f"Claude CLI already installed at {existing_path}"
        result['method'] = 'existing'
        print(f"ℹ️  {result['message']}")
        return result

    # Skip installation if method is 'skip'
    if install_method == 'skip':
        result['message'] = "Installation skipped by configuration"
        print(f"⏭️  {result['message']}")
        return result

    # Determine installation method
    if install_method == 'auto':
        # Auto-detect best method based on platform and available tools
        if sys.platform in ['linux', 'linux2', 'darwin']:
            install_method = 'curl'
        else:
            result['message'] = f"Unsupported platform: {sys.platform}"
            print(f"❌ {result['message']}")
            return result

    print(f"🔧 Attempting to install Claude CLI using {install_method}...")

    try:
        if install_method == 'curl':
            # Use official curl-based installation
            # According to docs: curl -fsSL https://claude.ai/install.sh | bash
            install_url = "https://claude.ai/install.sh"

            print(f"   Downloading installation script from {install_url}")
            print(f"   This may take a few minutes...")

            # Download and execute the install script
            # We pipe it through bash for execution
            process = subprocess.run(
                f'curl -fsSL {install_url} | bash',
                shell=True,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if process.returncode == 0:
                # Installation succeeded, try to find claude again
                claude_path = check_claude_available()

                if claude_path:
                    result['success'] = True
                    result['claude_path'] = claude_path
                    result['message'] = f"Successfully installed Claude CLI at {claude_path}"
                    print(f"   ✅ {result['message']}")
                else:
                    result['message'] = "Installation completed but Claude CLI not found in PATH"
                    print(f"   ⚠️  {result['message']}")
                    print(f"   stdout: {process.stdout[:200]}")
                    print(f"   stderr: {process.stderr[:200]}")
            else:
                result['message'] = f"Installation script failed (exit code {process.returncode})"
                print(f"   ❌ {result['message']}")
                if process.stderr:
                    print(f"   Error: {process.stderr[:500]}")

        else:
            result['message'] = f"Unknown installation method: {install_method}"
            print(f"❌ {result['message']}")

    except subprocess.TimeoutExpired:
        result['message'] = "Installation timed out after 5 minutes"
        print(f"⏱️  {result['message']}")

    except Exception as e:
        result['message'] = f"Installation failed: {str(e)}"
        print(f"❌ {result['message']}")

    return result


def run_claude_init(repo_path: str, claude_path: str, timeout: int = None) -> Dict[str, Any]:
    """
    Run claude /init command on a repository to create CLAUDE.md.

    Args:
        repo_path: Path to the repository directory
        claude_path: Path to the claude executable
        timeout: Timeout in seconds (default: 1800 seconds / 30 minutes, or from CLAUDE_INIT_TIMEOUT env var, or None for no timeout)

    Returns:
        Dictionary with status and details:
        {
            'success': bool,
            'claude_md_path': str or None,
            'claude_md_exists': bool,
            'error': str or None,
            'output': str or None
        }
    """
    result = {
        'success': False,
        'claude_md_path': None,
        'claude_md_exists': False,
        'error': None,
        'output': None
    }

    # Get timeout from environment variable if not specified
    if timeout is None:
        timeout_str = os.environ.get('CLAUDE_INIT_TIMEOUT', '1800')  # Default: 30 minutes
        if timeout_str.lower() in ('none', 'null', 'inf', 'infinite'):
            timeout = None  # No timeout
        else:
            try:
                timeout = int(timeout_str)
            except ValueError:
                print(f"     ⚠️  Invalid CLAUDE_INIT_TIMEOUT value '{timeout_str}', using default 1800 seconds")
                timeout = 1800

    try:
        # Validate repo path exists
        if not os.path.isdir(repo_path):
            result['error'] = f"Repository path does not exist: {repo_path}"
            return result

        # Check if CLAUDE.md already exists
        claude_md_path = os.path.join(repo_path, 'CLAUDE.md')
        claude_md_existed_before = os.path.isfile(claude_md_path)

        print(f"  🤖 Running claude /init in {repo_path}")
        print(f"     Claude path: {claude_path}")
        if claude_md_existed_before:
            print(f"     CLAUDE.md already exists, will reinitialize")

        # Build command for claude /init
        # We use --print mode for non-interactive execution
        cmd = [
            claude_path,
            '--print',
            '/init'
        ]

        # Add auto-approve flag if enabled (default: true for automation)
        auto_approve = os.environ.get('CLAUDE_AUTO_APPROVE', 'true').lower() in ('true', '1', 'yes')
        if auto_approve:
            cmd.insert(2, '--dangerously-skip-permissions')
            print(f"     Auto-approve: enabled (using --dangerously-skip-permissions)")
        else:
            print(f"     Auto-approve: disabled (may require user interaction)")

        # Prepare environment with API key if provided
        env = os.environ.copy()

        # Disable output buffering to get real-time logs
        # This helps prevent all output from appearing at once at the end
        env['PYTHONUNBUFFERED'] = '1'
        env['PYTHONDONTWRITEBYTECODE'] = '1'  # Also avoid .pyc files

        api_key_present = 'ANTHROPIC_API_KEY' in env
        if api_key_present:
            api_key_value = env.get('ANTHROPIC_API_KEY', '')
            key_preview = f"{api_key_value[:15]}..." if len(api_key_value) > 15 else api_key_value
            print(f"     Using ANTHROPIC_API_KEY for authentication")
            print(f"     API key preview: {key_preview}")
        else:
            print(f"     ⚠️  WARNING: ANTHROPIC_API_KEY not found in environment")
            print(f"     Available env vars: {', '.join([k for k in env.keys() if 'ANTHROPIC' in k or 'CLAUDE' in k])}")

        print(f"     Running command: {' '.join(cmd)}")
        print(f"     Working directory: {repo_path}")
        timeout_display = f"{timeout} seconds" if timeout is not None else "No timeout (will wait indefinitely)"
        print(f"     Timeout: {timeout_display}")
        print(f"")
        print(f"     --- Claude /init output (live) ---")

        # Run claude /init command with real-time output
        # Use subprocess.Popen to stream output as it happens
        process = subprocess.Popen(
            cmd,
            cwd=repo_path,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Merge stderr into stdout
            text=True,
            bufsize=1  # Line buffered
        )

        output_lines = []
        try:
            # Read output line by line and print in real-time
            # Flush after each line to ensure it appears immediately
            for line in process.stdout:
                print(f"     {line.rstrip()}", flush=True)  # flush=True forces immediate output
                output_lines.append(line)

            # Wait for process to complete
            return_code = process.wait(timeout=timeout)

        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            result['error'] = f"Claude /init timed out after {timeout} seconds"
            print(f"")
            print(f"     ⏱️  {result['error']}")
            return result

        print(f"     --- End of claude /init output ---")
        print(f"")
        print(f"     Process exit code: {return_code}")

        # Store output
        result['output'] = ''.join(output_lines)

        # Check if CLAUDE.md was created/updated
        claude_md_exists_after = os.path.isfile(claude_md_path)

        if claude_md_exists_after:
            result['success'] = True
            result['claude_md_path'] = claude_md_path
            result['claude_md_exists'] = True

            # Get file size for confirmation
            file_size = os.path.getsize(claude_md_path)
            action = "reinitialized" if claude_md_existed_before else "created"
            print(f"     ✅ CLAUDE.md {action} ({file_size} bytes)")

        elif return_code == 0:
            # Command succeeded but no file created (might have been approved but not written)
            result['error'] = "Claude /init completed but CLAUDE.md was not created"
            print(f"     ⚠️  {result['error']}")
            if output_lines:
                print(f"     Output was: {' '.join(output_lines[:5])[:200]}")

        else:
            # Command failed - analyze the error
            error_output = ''.join(output_lines).strip() if output_lines else ""

            # Check for common error scenarios
            if "credit balance is too low" in error_output.lower():
                result['error'] = "Insufficient API credits"
                result['error_type'] = 'insufficient_credits'
                print(f"     💳 Claude API credit balance is too low")
                print(f"     💡 To continue using claude /init:")
                print(f"        1. Add credits to your Anthropic account at https://console.anthropic.com/")
                print(f"        2. Or set CLAUDE_INIT_ENABLED=false to skip initialization")

            elif "authentication" in error_output.lower() or "api key" in error_output.lower():
                result['error'] = "Authentication failed"
                result['error_type'] = 'authentication'
                print(f"     🔑 Claude API authentication failed")
                print(f"     💡 Check your ANTHROPIC_API_KEY is valid")

            elif "not found" in error_output.lower() or "no such file" in error_output.lower():
                result['error'] = "Command execution failed"
                result['error_type'] = 'execution'
                print(f"     ⚠️  Claude CLI execution failed")

            else:
                result['error'] = f"Claude /init failed (exit code {return_code})"
                result['error_type'] = 'unknown'
                if error_output:
                    result['error'] += f": {error_output[:300]}"
                print(f"     ❌ {result['error']}")

            # Store the full error output for debugging
            result['error_details'] = error_output

    except subprocess.TimeoutExpired:
        result['error'] = f"Claude /init timed out after {timeout} seconds"
        print(f"     ⏱️  {result['error']}")

    except Exception as e:
        result['error'] = f"Exception running claude /init: {str(e)}"
        print(f"     ❌ {result['error']}")

    return result


def initialize_repository(repo_entry: Dict[str, Any], auto_install: bool = False) -> Dict[str, Any]:
    """
    Initialize a cloned repository with claude /init.

    Args:
        repo_entry: Repository entry from database with 'clone_path' field
        auto_install: If True, attempt to install Claude CLI if not found

    Returns:
        Dictionary with initialization results
    """
    result = {
        'attempted': False,
        'success': False,
        'claude_available': False,
        'claude_md_exists': False,
        'claude_md_path': None,
        'error': None,
        'installation_attempted': False,
        'installation_result': None
    }

    # Check if claude init is enabled via environment variable
    claude_init_enabled = os.environ.get('CLAUDE_INIT_ENABLED', 'true').lower() in ('true', '1', 'yes')
    if not claude_init_enabled:
        result['error'] = "Claude initialization disabled by CLAUDE_INIT_ENABLED setting"
        print("  ⏭️  Claude /init disabled (CLAUDE_INIT_ENABLED=false)")
        return result

    # Check if claude is available
    claude_path = check_claude_available()
    result['claude_available'] = claude_path is not None

    # Attempt installation if not available and auto_install is enabled
    if not claude_path and auto_install:
        print("  🔧 Claude CLI not found, attempting automatic installation...")
        result['installation_attempted'] = True

        # Get installation method from environment variable
        install_method = os.environ.get('CLAUDE_INSTALL_METHOD', 'auto')

        install_result = install_claude_cli(install_method)
        result['installation_result'] = install_result

        if install_result['success']:
            claude_path = install_result['claude_path']
            result['claude_available'] = True
            print(f"  ✅ Claude CLI installed successfully")
        else:
            result['error'] = f"Installation failed: {install_result['message']}"
            print(f"  ❌ {result['error']}")
            return result

    if not claude_path:
        result['error'] = "Claude CLI not found on system"
        print("  ℹ️  Claude CLI not available, skipping initialization")
        return result

    # Check if repository has a valid clone path
    clone_path = repo_entry.get('clone_path')
    if not clone_path or not os.path.isdir(clone_path):
        result['error'] = "Invalid or missing clone path"
        return result

    # Only initialize if repo has code
    if not repo_entry.get('has_code', False):
        result['error'] = "Repository has no code files, skipping initialization"
        print(f"  ⏭️  Skipping claude init (no code detected)")
        return result

    # Run claude /init
    result['attempted'] = True
    init_result = run_claude_init(clone_path, claude_path)

    # Merge results
    result['success'] = init_result['success']
    result['claude_md_exists'] = init_result['claude_md_exists']
    result['claude_md_path'] = init_result['claude_md_path']
    if init_result['error']:
        result['error'] = init_result['error']

    return result
