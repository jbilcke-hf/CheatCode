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

    This function checks for programming language files anywhere in the repository,
    including examples/, demos/, and other subdirectories. It uses a lenient approach
    and also checks README and .gitattributes for language indicators.

    Args:
        repo_path: Path to repository

    Returns:
        True if code files are found
    """
    code_extensions = {
        '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h',
        '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala',
        '.m', '.mm', '.r', '.jl', '.dart', '.vue', '.svelte', '.sh', '.bash',
        '.ipynb'  # Include Jupyter notebooks
    }

    # Only skip build artifacts and dependencies - keep examples/demos/tests
    skip_dirs = {
        'node_modules', '.git', '__pycache__', '.pytest_cache', 'dist',
        'build', 'venv', 'env', '.env', '.venv', 'site-packages'
    }

    # More lenient thresholds
    MIN_FILE_SIZE = 50   # Minimum bytes (lowered from 100)
    MIN_CODE_FILES = 1   # Just need 1 code file (lowered from 2)
    MIN_TOTAL_SIZE = 100 # Minimum total bytes (lowered from 500)

    code_files = []
    total_code_size = 0

    try:
        # First, do a quick check for any code files
        for file in repo_path.rglob('*'):
            # Skip if not a file
            if not file.is_file():
                continue

            # Skip if not a code extension
            if file.suffix.lower() not in code_extensions:
                continue

            # Skip if in excluded directories (build artifacts only)
            if any(skip_dir in file.parts for skip_dir in skip_dirs):
                continue

            # Get file size
            file_size = file.stat().st_size

            # Skip empty files but allow small files
            if file_size < MIN_FILE_SIZE:
                continue

            # Count this as a code file
            code_files.append(file)
            total_code_size += file_size

        # Check if we found code files
        has_code = (len(code_files) >= MIN_CODE_FILES and
                   total_code_size >= MIN_TOTAL_SIZE)

        if has_code:
            print(f"   ✓ Found {len(code_files)} code file(s) ({total_code_size} bytes)")
            if code_files:
                # Show some example files
                examples = [str(f.relative_to(repo_path)) for f in code_files[:5]]
                print(f"      Examples: {', '.join(examples)}")
            return True

        # Fallback: Check README for code/project indicators
        readme_files = ['README.md', 'README.rst', 'README.txt', 'README']
        for readme_name in readme_files:
            readme_path = repo_path / readme_name
            if readme_path.is_file():
                try:
                    content = readme_path.read_text(encoding='utf-8', errors='ignore').lower()
                    # Look for programming/usage indicators
                    code_indicators = [
                        'python', 'javascript', 'typescript', 'java', 'c++', 'rust', 'go',
                        'install', 'pip install', 'npm install', 'cargo build',
                        'usage', 'quickstart', 'getting started', 'import ', 'from ',
                        'require(', 'def ', 'class ', 'function ', 'const ',
                        'example', 'tutorial', 'api', 'library', 'framework'
                    ]
                    if any(indicator in content for indicator in code_indicators):
                        print(f"   ✓ README indicates this is a code project")
                        return True
                except Exception:
                    pass

        # Final fallback: Check .gitattributes for linguist data
        gitattributes = repo_path / '.gitattributes'
        if gitattributes.is_file():
            try:
                content = gitattributes.read_text(encoding='utf-8', errors='ignore')
                if 'linguist-language' in content:
                    print(f"   ✓ .gitattributes indicates programming language")
                    return True
            except Exception:
                pass

        print(f"   ⚠️  No substantial code detected (found {len(code_files)} file(s), {total_code_size} bytes)")
        return False

    except Exception as e:
        print(f"   ⚠️  Error checking repo code: {e}")
        # When in doubt, assume it might have code (be lenient)
        return True


def detect_languages(repo_path: Path) -> List[str]:
    """
    Detect programming languages used in the repository.

    Scans all code files including examples/, scripts/, samples/, tests/, etc.
    Only skips build artifacts and dependencies.

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
        '.bash': 'Shell',
        '.ipynb': 'Python'  # Jupyter notebooks
    }

    # Only skip build artifacts and dependencies - keep examples/demos/tests/scripts/samples
    skip_dirs = {
        'node_modules', '.git', '__pycache__', '.pytest_cache', 'dist',
        'build', 'venv', 'env', '.env', '.venv', 'site-packages'
    }

    MIN_FILE_SIZE = 50  # Minimum bytes to be considered (lowered for inclusivity)

    detected = set()
    try:
        for file in repo_path.rglob('*'):
            if not file.is_file():
                continue

            if file.suffix.lower() not in language_extensions:
                continue

            # Skip excluded directories (build artifacts only)
            if any(skip_dir in file.parts for skip_dir in skip_dirs):
                continue

            # Skip very small files
            if file.stat().st_size < MIN_FILE_SIZE:
                continue

            detected.add(language_extensions[file.suffix.lower()])

    except Exception as e:
        print(f"   ⚠️  Error detecting languages: {e}")

    return sorted(list(detected))
