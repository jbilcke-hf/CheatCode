"""
HuggingFace Spaces upload functionality.

This module handles uploading repositories to HuggingFace Spaces,
including creating the Space, uploading files, and handling file size limits.
"""

import os
import re
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from huggingface_hub import HfApi, create_repo, upload_folder, upload_file, SpaceHardware
from huggingface_hub.utils import HfHubHTTPError, RepositoryNotFoundError


# File size limits for HuggingFace Spaces
MAX_FILE_SIZE_MB = 50  # HuggingFace has strict limits on individual file sizes
MAX_TOTAL_SIZE_MB = 500  # Reasonable limit for total space size

# Files to always exclude from upload
EXCLUDE_PATTERNS = [
    '**/.git/**',
    '**/__pycache__/**',
    '**/*.pyc',
    '**/*.pyo',
    '**/*.pyd',
    '**/.pytest_cache/**',
    '**/.mypy_cache/**',
    '**/.tox/**',
    '**/.coverage',
    '**/.env',
    '**/.env.*',
    '**/node_modules/**',
    '**/.DS_Store',
    '**/Thumbs.db',
    '**/*.egg-info/**',
    '**/dist/**',
    '**/build/**',
    '**/.vscode/**',
    '**/.idea/**',
    '**/venv/**',
    '**/env/**',
    '**/.venv/**',
]

# Large binary file extensions to warn about
BINARY_EXTENSIONS = {
    '.bin', '.safetensors', '.ckpt', '.pt', '.pth', '.h5', '.pb',
    '.onnx', '.tflite', '.pkl', '.pickle', '.npz', '.npy',
    '.mp4', '.avi', '.mov', '.mkv', '.webm',
    '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff',
    '.mp3', '.wav', '.flac', '.ogg',
    '.pdf', '.doc', '.docx', '.ppt', '.pptx',
}


def sanitize_space_name(repo_name: str, owner: str, paper_id: str) -> str:
    """
    Create a sanitized Space name.

    Args:
        repo_name: Original repository name
        owner: Repository owner
        paper_id: Paper ID for uniqueness

    Returns:
        Sanitized space name
    """
    # Clean the repo name: lowercase, replace special chars with hyphens
    clean_name = re.sub(r'[^a-z0-9-]', '-', repo_name.lower())
    clean_name = re.sub(r'-+', '-', clean_name).strip('-')

    # Add paper ID suffix for uniqueness (use first 8 chars to keep it short)
    paper_suffix = paper_id.replace('.', '-')[:8]

    # Construct space name with SNIPED_ prefix
    # Format: SNIPED_{repo_name}-{paper_id}
    # space_name = f"SNIPED_{clean_name}-{paper_suffix}"
    
    # EDIT: for low, let's use the short version
    space_name = f"SNIPED_{clean_name}"

    # Ensure it's not too long (HF has 96 char limit for repo names)
    if len(space_name) > 96:
        space_name = space_name[:96].rstrip('-')

    return space_name


def check_file_sizes(repo_path: str) -> Tuple[List[Dict[str, Any]], int, List[str]]:
    """
    Check file sizes in repository and identify problematic files.

    Args:
        repo_path: Path to repository

    Returns:
        Tuple of (file_list, total_size_mb, warnings)
    """
    repo_path = Path(repo_path)
    files = []
    total_size = 0
    warnings = []

    for file_path in repo_path.rglob('*'):
        if file_path.is_file():
            # Skip excluded patterns
            relative_path = file_path.relative_to(repo_path)
            skip = False
            for pattern in EXCLUDE_PATTERNS:
                pattern_clean = pattern.replace('**/', '').replace('/**', '')
                if pattern_clean in str(relative_path):
                    skip = True
                    break

            if skip:
                continue

            size = file_path.stat().st_size
            size_mb = size / (1024 * 1024)

            files.append({
                'path': str(relative_path),
                'size': size,
                'size_mb': size_mb
            })

            total_size += size

            # Warn about large files
            if size_mb > MAX_FILE_SIZE_MB:
                warnings.append(
                    f"File {relative_path} is {size_mb:.1f}MB (exceeds {MAX_FILE_SIZE_MB}MB limit)"
                )

            # Warn about binary files
            if file_path.suffix.lower() in BINARY_EXTENSIONS and size_mb > 10:
                warnings.append(
                    f"Large binary file {relative_path} ({size_mb:.1f}MB) - may cause upload issues"
                )

    total_size_mb = int(total_size / (1024 * 1024))

    return files, total_size_mb, warnings


def filter_uploadable_files(files: List[Dict[str, Any]]) -> List[str]:
    """
    Filter files that can be safely uploaded to HuggingFace Spaces.

    Args:
        files: List of file info dicts

    Returns:
        List of file paths to upload
    """
    uploadable = []

    for file_info in files:
        # Skip files that are too large
        if file_info['size_mb'] > MAX_FILE_SIZE_MB:
            continue

        uploadable.append(file_info['path'])

    return uploadable


def create_space_readme(
    repo_name: str,
    repo_url: str,
    paper_id: str,
    paper_title: str,
    languages: List[str],
    has_app: bool = False
) -> str:
    """
    Create a README.md for the HuggingFace Space.

    Args:
        repo_name: Repository name
        repo_url: Original GitHub URL
        paper_id: Paper ID
        paper_title: Paper title
        languages: List of programming languages
        has_app: Whether an app.py was generated

    Returns:
        README content
    """
    app_status = "✅ Generated by CheatCode" if has_app else "⚠️ No app.py found"

    # Generate a short description from the paper title (truncate to ~100 chars)
    short_desc = paper_title[:97] + "..." if len(paper_title) > 100 else paper_title

    # Escape double quotes in strings for YAML safety
    def yaml_escape(text: str) -> str:
        """Escape double quotes for YAML string values."""
        return text.replace('"', '\\"') if text else text

    # Prepare YAML-safe values
    safe_title = yaml_escape(repo_name)
    safe_short_desc = yaml_escape(short_desc)

    readme = f"""---
title: "{safe_title}"
emoji: 🤖
colorFrom: yellow
colorTo: blue
sdk: gradio
sdk_version: 5.49.1
app_file: app.py
pinned: false
short_description: "{safe_short_desc}"
hardware: zerogpu
tags:
  - research
  - paper
  - code
  - cheatcode
license: mit
---

# {repo_name}

**Automated upload by CheatCode** 🚀

## 📄 Paper Information

- **Paper ID**: {paper_id}
- **Title**: {paper_title}
- **Original Repository**: [{repo_url}]({repo_url})

## 🛠️ Repository Information

- **Languages**: {', '.join(languages) if languages else 'Not detected'}
- **Gradio App**: {app_status}

## 🤖 About CheatCode

This Space was automatically created by [CheatCode](https://github.com/jbilcke-hf/CheatCode),
an AI-powered tool that:

1. Discovers research papers from HuggingFace
2. Extracts and analyzes linked repositories
3. Generates Gradio demo applications
4. Uploads everything to HuggingFace Spaces

## 📝 Usage

{'This Space includes a Gradio app that was automatically generated from the repository code.' if has_app else 'This Space contains the repository code. You may need to add an app.py file to create a demo.'}

## ⚠️ Disclaimer

This is an automated upload. The code comes from the original repository and may require
additional configuration or dependencies to run properly.

## 📜 License

Please refer to the original repository for licensing information: {repo_url}
"""

    return readme


def upload_to_space(
    repo_entry: Dict[str, Any],
    paper_entry: Dict[str, Any],
    hf_token: str,
    username: str,
    private: bool = False,
    force: bool = False
) -> Dict[str, Any]:
    """
    Upload a repository to a new HuggingFace Space.

    Args:
        repo_entry: Repository entry from database
        paper_entry: Paper entry from database
        hf_token: HuggingFace API token
        username: HuggingFace username
        private: Whether to make the Space private
        force: Force re-upload even if Space exists

    Returns:
        Dictionary with upload results:
        {
            'success': bool,
            'space_url': str or None,
            'space_id': str or None,
            'error': str or None,
            'warnings': list,
            'files_uploaded': int,
            'total_size_mb': int
        }
    """
    result = {
        'success': False,
        'space_url': None,
        'space_id': None,
        'error': None,
        'warnings': [],
        'files_uploaded': 0,
        'total_size_mb': 0
    }

    try:
        # Validate inputs
        clone_path = repo_entry.get('clone_path')
        if not clone_path or not os.path.isdir(clone_path):
            result['error'] = "Invalid or missing clone path"
            return result

        # Extract repository info
        repo_url = repo_entry.get('url', '')
        repo_match = re.search(r'github\.com/([^/]+)/([^/]+?)(?:\.git)?$', repo_url)
        if not repo_match:
            result['error'] = "Could not parse GitHub URL"
            return result

        owner, repo_name = repo_match.groups()
        paper_id = paper_entry.get('paper_id', 'unknown')
        paper_title = paper_entry.get('title', 'Unknown Paper')

        # Create sanitized space name
        space_name = sanitize_space_name(repo_name, owner, paper_id)
        space_id = f"{username}/{space_name}"

        print(f"  📦 Preparing to upload to Space: {space_id}")
        print(f"     Original repo: {repo_url}")
        print(f"     Local path: {clone_path}")

        # Check file sizes
        print(f"     Analyzing files...")
        files, total_size_mb, warnings = check_file_sizes(clone_path)
        result['warnings'] = warnings
        result['total_size_mb'] = total_size_mb

        if warnings:
            print(f"     ⚠️  Found {len(warnings)} warnings:")
            for warning in warnings[:5]:  # Show first 5 warnings
                print(f"        - {warning}")
            if len(warnings) > 5:
                print(f"        ... and {len(warnings) - 5} more")

        print(f"     Total files: {len(files)}, Total size: {total_size_mb}MB")

        # Check if total size is too large
        if total_size_mb > MAX_TOTAL_SIZE_MB:
            result['error'] = f"Repository too large ({total_size_mb}MB exceeds {MAX_TOTAL_SIZE_MB}MB limit)"
            print(f"     ❌ {result['error']}")
            return result

        # Initialize HuggingFace API
        api = HfApi(token=hf_token)

        # Check if Space already exists
        space_exists = False
        try:
            api.repo_info(repo_id=space_id, repo_type="space")
            space_exists = True
            print(f"     ℹ️  Space already exists: {space_id}")

            if not force:
                result['error'] = "Space already exists (use force=True to overwrite)"
                result['space_url'] = f"https://huggingface.co/spaces/{space_id}"
                result['space_id'] = space_id
                return result

        except RepositoryNotFoundError:
            pass  # Space doesn't exist, we'll create it

        # Create or update Space
        if not space_exists:
            print(f"     🏗️  Creating Space...")
            try:
                create_repo(
                    repo_id=space_id,
                    repo_type="space",
                    space_sdk="gradio",
                    space_hardware="zerogpu",
                    private=private,
                    token=hf_token
                )
                print(f"     ✅ Space created with ZeroGPU hardware")
            except Exception as e:
                result['error'] = f"Failed to create Space: {str(e)}"
                print(f"     ❌ {result['error']}")
                return result
        else:
            print(f"     🔄 Updating existing Space...")

        # Create README for the Space
        languages = repo_entry.get('languages', [])
        has_app = os.path.isfile(os.path.join(clone_path, 'app.py'))
        readme_content = create_space_readme(
            repo_name, repo_url, paper_id, paper_title, languages, has_app
        )

        # Write README to repo
        readme_path = os.path.join(clone_path, 'README.md')
        readme_existed = os.path.isfile(readme_path)

        # Backup existing README if it exists
        if readme_existed:
            backup_path = os.path.join(clone_path, 'README_original.md')
            if not os.path.exists(backup_path):
                os.rename(readme_path, backup_path)
                print(f"     📝 Backed up original README to README_original.md")

        # Write new README
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        print(f"     📝 Created Space README.md")

        # Upload folder to Space with staged upload strategy
        print(f"     ⬆️  Uploading files to Space...")
        print(f"     This may take several minutes depending on repository size...")

        # Use staged upload for large repositories
        use_staged_upload = total_size_mb > 50 or len(files) > 300

        if use_staged_upload:
            print(f"     ℹ️  Using staged upload (core files first, then assets)")

            # Create temporary ignore patterns for each stage
            # Stage 1: Core source files (exclude large assets)
            stage1_ignore = EXCLUDE_PATTERNS + [
                '**/*.onnx', '**/*.pt', '**/*.pth', '**/*.h5', '**/*.pb',  # Model files
                '**/*.bin', '**/*.weights',  # Weight files
                '**/*.mp4', '**/*.avi', '**/*.mov', '**/*.mkv',  # Videos
                '**/*.zip', '**/*.tar', '**/*.tar.gz', '**/*.tgz',  # Archives
                '**/*.jpg', '**/*.jpeg', '**/*.png', '**/*.gif',  # Images (if > 1MB, filtered later)
                '**/assets/**', '**/screenshots/**', '**/demo/**', '**/examples/**'
            ]

            # Stage 2: Large assets only (inverse of stage1)
            stage2_allow_patterns = [
                '**/*.onnx', '**/*.pt', '**/*.pth', '**/*.h5', '**/*.pb',
                '**/*.bin', '**/*.weights',
                '**/*.mp4', '**/*.avi', '**/*.mov', '**/*.mkv',
                '**/*.zip', '**/*.tar', '**/*.tar.gz', '**/*.tgz',
                '**/assets/**', '**/screenshots/**', '**/demo/**', '**/examples/**'
            ]
        else:
            use_staged_upload = False

        # Retry logic for uploads
        max_retries = 3
        retry_delay = 10  # seconds

        # Stage 1: Upload core source files
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    print(f"     🔄 Retry attempt {attempt + 1}/{max_retries}...")
                    time.sleep(retry_delay * attempt)  # Exponential backoff

                if use_staged_upload:
                    print(f"     📦 Stage 1/2: Uploading core source files...")

                upload_folder(
                    folder_path=clone_path,
                    repo_id=space_id,
                    repo_type="space",
                    token=hf_token,
                    ignore_patterns=stage1_ignore if use_staged_upload else EXCLUDE_PATTERNS,
                    commit_message=f"Upload core files for paper {paper_id}" if use_staged_upload else f"Upload repository for paper {paper_id}"
                )

                print(f"     ✅ Stage 1 complete!")
                break  # Success, exit retry loop

            except (HfHubHTTPError, TimeoutError, ConnectionError, Exception) as e:
                error_msg = str(e)
                is_timeout = any(x in error_msg.lower() for x in ['timeout', 'timed out', 'connection'])
                is_last_attempt = (attempt == max_retries - 1)

                if is_timeout and not is_last_attempt:
                    print(f"     ⚠️  Upload timed out, will retry...")
                    continue
                else:
                    result['error'] = f"Upload failed (Stage 1): {error_msg}"
                    print(f"     ❌ {result['error']}")
                    if 'file is too large' in error_msg.lower():
                        result['error'] += " (File too large - check warnings)"

                    # Don't return yet if using staged upload - core files might be uploaded
                    if not use_staged_upload:
                        return result
                    break

        # Stage 2: Upload large assets (if using staged upload and stage 1 succeeded)
        if use_staged_upload and not result.get('error'):
            print(f"     📦 Stage 2/2: Uploading large assets and media files...")
            print(f"     ⚠️  This stage may take longer and could timeout - that's okay!")

            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        print(f"     🔄 Retry attempt {attempt + 1}/{max_retries}...")
                        time.sleep(retry_delay * attempt)

                    # Upload only the large asset files
                    # Find large asset files
                    asset_files = []
                    for file_info in files:
                        file_path = Path(clone_path) / file_info['path']
                        # Check if file matches asset patterns and size > 1MB
                        if file_info['size_mb'] > 1:
                            for pattern in ['.onnx', '.pt', '.pth', '.h5', '.pb', '.bin', '.weights',
                                          '.mp4', '.avi', '.mov', '.mkv', '.zip', '.tar', '.gz']:
                                if str(file_info['path']).endswith(pattern):
                                    asset_files.append(file_info)
                                    break

                    if asset_files:
                        print(f"     📊 Found {len(asset_files)} large asset files to upload")
                        uploaded = 0

                        for asset in asset_files[:10]:  # Limit to first 10 assets to avoid excessive uploads
                            try:
                                if asset['size_mb'] <= MAX_FILE_SIZE_MB:  # Only upload if within limits
                                    print(f"        - Uploading {asset['path']} ({asset['size_mb']:.1f}MB)...")
                                    upload_file(
                                        path_or_fileobj=str(Path(clone_path) / asset['path']),
                                        path_in_repo=asset['path'],
                                        repo_id=space_id,
                                        repo_type="space",
                                        token=hf_token,
                                        commit_message=f"Add asset: {asset['path']}"
                                    )
                                    uploaded += 1
                                else:
                                    print(f"        ⏭️  Skipping {asset['path']} (too large: {asset['size_mb']:.1f}MB)")
                            except Exception as e:
                                print(f"        ⚠️  Failed to upload {asset['path']}: {str(e)[:100]}")

                        if uploaded > 0:
                            print(f"     ✅ Stage 2 complete! Uploaded {uploaded}/{len(asset_files)} assets")
                    else:
                        print(f"     ℹ️  No large assets to upload in stage 2")

                    break  # Stage 2 done

                except Exception as e:
                    error_msg = str(e)
                    is_last_attempt = (attempt == max_retries - 1)

                    if not is_last_attempt:
                        print(f"     ⚠️  Stage 2 failed, will retry...")
                        continue
                    else:
                        print(f"     ⚠️  Stage 2 failed (non-critical): {error_msg[:200]}")
                        # Don't fail the whole upload if stage 2 fails
                        break

        # Mark as successful if stage 1 completed
        if not result.get('error'):
            result['success'] = True
            result['space_url'] = f"https://huggingface.co/spaces/{space_id}"
            result['space_id'] = space_id
            result['files_uploaded'] = len(files)

            print(f"     ✅ Upload complete!")
            print(f"     🌐 Space URL: {result['space_url']}")

    except Exception as e:
        result['error'] = f"Unexpected error: {str(e)}"
        print(f"     ❌ {result['error']}")

    return result


def process_space_uploads(
    paper_entry: Dict[str, Any],
    hf_token: str,
    username: str,
    private: bool = False,
    force: bool = False
) -> Dict[str, Any]:
    """
    Process Space uploads for all repositories of a paper.

    Args:
        paper_entry: Paper entry from database
        hf_token: HuggingFace API token
        username: HuggingFace username
        private: Whether to make Spaces private
        force: Force re-upload even if Space exists

    Returns:
        Summary dict with upload results
    """
    summary = {
        'total_repos': 0,
        'spaces_created': 0,
        'spaces_failed': 0,
        'space_urls': [],
        'errors': []
    }

    repositories = paper_entry.get('repositories', [])
    summary['total_repos'] = len(repositories)

    if not repositories:
        print("  ℹ️  No repositories to upload")
        return summary

    print(f"  📦 Processing {len(repositories)} repositories for Space upload")

    for idx, repo_entry in enumerate(repositories, 1):
        # Only upload cloned repos with code
        if repo_entry.get('status') != 'cloned':
            print(f"  ⏭️  Skipping repo {idx}/{len(repositories)} (not cloned)")
            continue

        if not repo_entry.get('has_code', False):
            print(f"  ⏭️  Skipping repo {idx}/{len(repositories)} (no code)")
            continue

        print(f"  📤 Uploading repo {idx}/{len(repositories)}...")

        result = upload_to_space(
            repo_entry,
            paper_entry,
            hf_token,
            username,
            private=private,
            force=force
        )

        # Update repo entry with Space info
        repo_entry['space_upload'] = result

        if result['success']:
            summary['spaces_created'] += 1
            summary['space_urls'].append(result['space_url'])
        else:
            summary['spaces_failed'] += 1
            summary['errors'].append({
                'repo_url': repo_entry.get('url'),
                'error': result['error']
            })

    return summary
