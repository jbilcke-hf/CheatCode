"""
Repository cloning and analysis operations.
"""

import re
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from .config import get_repos_path
from .status import RepoStatus


def extract_github_info(url: str) -> Optional[Dict[str, str]]:
    """
    Extract owner and repo name from GitHub URL.

    Args:
        url: GitHub repository URL

    Returns:
        Dict with 'owner', 'repo', and 'full_name' or None if invalid
    """
    patterns = [
        r'github\.com/([^/]+)/([^/\.]+)',
        r'github\.com/([^/]+)/([^/]+)\.git'
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return {
                'owner': match.group(1),
                'repo': match.group(2),
                'full_name': f"{match.group(1)}/{match.group(2)}"
            }
    return None


def clone_repository(repo_url: str, paper_id: str) -> Dict[str, Any]:
    """
    Clone a GitHub repository to local storage.

    Args:
        repo_url: GitHub repository URL
        paper_id: ArXiv paper ID for organizing repos

    Returns:
        Dict with clone status and information
    """
    result = {
        'url': repo_url,
        'status': RepoStatus.ERROR,
        'clone_path': None,
        'cloned_at': None,
        'error': None,
        'has_code': False,
        'languages': []
    }

    try:
        github_info = extract_github_info(repo_url)
        if not github_info:
            result['error'] = "Not a valid GitHub URL"
            return result

        # Create directory structure: repos_path/paper_id/owner_repo
        base_path = get_repos_path()
        paper_dir = base_path / paper_id.replace(".", "_")
        repo_dir = paper_dir / f"{github_info['owner']}_{github_info['repo']}"

        # Create parent directories
        paper_dir.mkdir(parents=True, exist_ok=True)

        # Remove existing repo if it exists
        if repo_dir.exists():
            shutil.rmtree(repo_dir)

        # Clone the repository (shallow clone for speed)
        print(f"🔄 Cloning {github_info['full_name']} to {repo_dir}...")
        result['status'] = RepoStatus.CLONING

        subprocess.run(
            ['git', 'clone', '--depth', '1', repo_url, str(repo_dir)],
            check=True,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        result['status'] = RepoStatus.CLONED
        result['clone_path'] = str(repo_dir)
        result['cloned_at'] = datetime.now().isoformat()

        # Check if repo has actual code
        result['has_code'] = check_repo_has_code(repo_dir)
        result['languages'] = detect_languages(repo_dir)

        print(f"✅ Successfully cloned {github_info['full_name']}")
        print(f"   Path: {repo_dir}")
        print(f"   Has code: {result['has_code']}")
        print(f"   Languages: {', '.join(result['languages']) if result['languages'] else 'None detected'}")

    except subprocess.TimeoutExpired:
        result['error'] = "Clone timeout (5 minutes exceeded)"
        print(f"❌ Clone timeout for {repo_url}")
    except subprocess.CalledProcessError as e:
        result['error'] = f"Git clone failed: {e.stderr}"
        print(f"❌ Clone failed for {repo_url}: {e.stderr}")
    except Exception as e:
        result['error'] = str(e)
        print(f"❌ Error cloning {repo_url}: {e}")

    return result


def check_repo_has_code(repo_path: Path) -> bool:
    """
    Check if a repository contains actual source code files.

    This function distinguishes between repos with real source code vs those
    with only documentation, assets, or trivial example files.

    Args:
        repo_path: Path to repository

    Returns:
        True if substantial code files found
    """
    code_extensions = {
        '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h',
        '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala',
        '.m', '.mm', '.r', '.jl', '.dart', '.vue', '.svelte', '.sh', '.bash'
    }

    # Directories to skip (typically contain examples/demos, not main source)
    skip_dirs = {
        'node_modules', '.git', '__pycache__', '.pytest_cache', 'dist',
        'build', 'venv', 'env', '.env', 'assets', 'images', 'docs',
        'documentation', 'examples', 'demos', 'tests', 'test', '__tests__',
        'screenshots', 'media', 'resources', 'static', 'public'
    }

    # Files that don't count as "real" code (common boilerplate/config)
    trivial_files = {
        '__init__.py', 'setup.py', 'conftest.py', 'webpack.config.js',
        'babel.config.js', 'jest.config.js', 'vite.config.js', 'rollup.config.js'
    }

    MIN_FILE_SIZE = 100  # Minimum bytes to be considered substantial
    MIN_CODE_FILES = 2   # Minimum number of substantial code files
    MIN_TOTAL_SIZE = 500 # Minimum total bytes of code

    substantial_files = []
    total_code_size = 0

    try:
        for file in repo_path.rglob('*'):
            # Skip if not a file
            if not file.is_file():
                continue

            # Skip if not a code extension
            if file.suffix.lower() not in code_extensions:
                continue

            # Skip if in excluded directories
            if any(skip_dir in file.parts for skip_dir in skip_dirs):
                continue

            # Get file size
            file_size = file.stat().st_size

            # Skip empty or very small files
            if file_size < MIN_FILE_SIZE:
                continue

            # Skip trivial boilerplate files
            if file.name in trivial_files:
                continue

            # Read file content to verify it's not just comments/whitespace
            try:
                content = file.read_text(encoding='utf-8', errors='ignore')

                # Remove comments and whitespace to check for actual code
                lines = content.split('\n')
                code_lines = []

                for line in lines:
                    stripped = line.strip()
                    # Skip empty lines and common comment patterns
                    if (stripped and
                        not stripped.startswith('#') and
                        not stripped.startswith('//') and
                        not stripped.startswith('/*') and
                        not stripped.startswith('*') and
                        not stripped == '*/'):
                        code_lines.append(stripped)

                # If we have at least some non-comment lines, count this file
                if len(code_lines) >= 5:  # At least 5 lines of actual code
                    substantial_files.append(file)
                    total_code_size += file_size

            except Exception:
                # If we can't read the file, skip it
                continue

        # Check if we have enough substantial code
        has_code = (len(substantial_files) >= MIN_CODE_FILES and
                   total_code_size >= MIN_TOTAL_SIZE)

        if not has_code and len(substantial_files) > 0:
            print(f"   ⚠️  Found {len(substantial_files)} code file(s) but below threshold for substantial code")
            print(f"      Files: {[f.name for f in substantial_files[:3]]}")

        return has_code

    except Exception as e:
        print(f"Warning: Error checking repo code: {e}")
        return False


def detect_languages(repo_path: Path) -> List[str]:
    """
    Detect programming languages used in the repository.

    Only counts substantial source code files, excluding examples, tests,
    and documentation.

    Args:
        repo_path: Path to repository

    Returns:
        List of detected language names
    """
    language_extensions = {
        '.py': 'Python',
        '.js': 'JavaScript',
        '.ts': 'TypeScript',
        '.jsx': 'JavaScript',
        '.tsx': 'TypeScript',
        '.java': 'Java',
        '.cpp': 'C++',
        '.c': 'C',
        '.h': 'C/C++',
        '.cs': 'C#',
        '.go': 'Go',
        '.rs': 'Rust',
        '.rb': 'Ruby',
        '.php': 'PHP',
        '.swift': 'Swift',
        '.kt': 'Kotlin',
        '.scala': 'Scala',
        '.m': 'Objective-C',
        '.r': 'R',
        '.jl': 'Julia',
        '.dart': 'Dart',
        '.vue': 'Vue',
        '.svelte': 'Svelte',
        '.sh': 'Shell',
        '.bash': 'Shell'
    }

    # Use same skip directories as check_repo_has_code()
    skip_dirs = {
        'node_modules', '.git', '__pycache__', '.pytest_cache', 'dist',
        'build', 'venv', 'env', '.env', 'assets', 'images', 'docs',
        'documentation', 'examples', 'demos', 'tests', 'test', '__tests__',
        'screenshots', 'media', 'resources', 'static', 'public'
    }

    MIN_FILE_SIZE = 100  # Minimum bytes to be considered

    detected = set()
    try:
        for file in repo_path.rglob('*'):
            if not file.is_file():
                continue

            if file.suffix.lower() not in language_extensions:
                continue

            # Skip excluded directories
            if any(skip_dir in file.parts for skip_dir in skip_dirs):
                continue

            # Skip very small files
            if file.stat().st_size < MIN_FILE_SIZE:
                continue

            detected.add(language_extensions[file.suffix.lower()])

    except Exception as e:
        print(f"Warning: Error detecting languages: {e}")

    return sorted(list(detected))
