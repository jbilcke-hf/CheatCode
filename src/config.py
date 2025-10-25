"""
Configuration management for CheatCode.
"""

import os
from pathlib import Path
import tempfile
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def get_hf_token() -> str:
    """Get HuggingFace API token from environment."""
    return os.getenv("HF_TOKEN", "")


def get_hf_username() -> str:
    """
    Get HuggingFace username from environment.

    Required for Space upload functionality.
    """
    return os.getenv("HF_USERNAME", "")


def get_repos_path() -> Path:
    """
    Get the base path for storing repositories.

    Returns path from REPOS_PATH env var, or temp directory if not set.
    """
    repos_path_env = os.getenv("REPOS_PATH", "")
    if repos_path_env:
        return Path(repos_path_env).expanduser().resolve()
    else:
        return Path(tempfile.gettempdir()) / "cheatcode_repos"


def get_database_path() -> Path:
    """Get the path to the database.yaml file."""
    return Path("database.yaml")


def get_auto_fetch_on_startup() -> bool:
    """
    Get whether to automatically fetch papers on startup.

    Returns True if AUTO_FETCH_ON_STARTUP is set to "true" or "1".
    Defaults to False for better performance and user control.
    """
    value = os.getenv("AUTO_FETCH_ON_STARTUP", "false").lower()
    return value in ("true", "1", "yes")


def get_auto_retry_failed() -> bool:
    """
    Get whether to automatically retry failed jobs on startup.

    Returns True if AUTO_RETRY_FAILED is set to "true" or "1".
    Defaults to False to avoid unexpected processing on startup.
    """
    value = os.getenv("AUTO_RETRY_FAILED", "false").lower()
    return value in ("true", "1", "yes")


def get_claude_auto_install() -> bool:
    """
    Get whether to automatically install Claude CLI if not found.

    Returns True if CLAUDE_AUTO_INSTALL is set to "true" or "1".
    Defaults to False to avoid unexpected installations.
    """
    value = os.getenv("CLAUDE_AUTO_INSTALL", "false").lower()
    return value in ("true", "1", "yes")


def get_claude_install_method() -> str:
    """
    Get the method to use for installing Claude CLI.

    Returns the installation method from CLAUDE_INSTALL_METHOD env var.
    Options: "auto", "curl", "skip"
    Defaults to "auto".
    """
    return os.getenv("CLAUDE_INSTALL_METHOD", "auto")


def get_space_upload_enabled() -> bool:
    """
    Get whether Space upload is enabled.

    Returns True if SPACE_UPLOAD_ENABLED is set to "true" or "1".
    Defaults to True if both HF_TOKEN and HF_USERNAME are set.
    """
    # Check explicit enable/disable setting
    explicit_value = os.getenv("SPACE_UPLOAD_ENABLED", "").lower()
    if explicit_value in ("false", "0", "no"):
        return False
    elif explicit_value in ("true", "1", "yes"):
        return True

    # Auto-enable if credentials are present
    return bool(get_hf_token() and get_hf_username())


def get_space_upload_private() -> bool:
    """
    Get whether to create private Spaces by default.

    Returns True if SPACE_UPLOAD_PRIVATE is set to "true" or "1".
    Defaults to False (public Spaces).
    """
    value = os.getenv("SPACE_UPLOAD_PRIVATE", "false").lower()
    return value in ("true", "1", "yes")


def get_space_upload_force() -> bool:
    """
    Get whether to force overwrite existing Spaces during upload.

    Returns True if SPACE_UPLOAD_FORCE is set to "true" or "1".
    Defaults to False (don't overwrite existing Spaces).
    """
    value = os.getenv("SPACE_UPLOAD_FORCE", "false").lower()
    return value in ("true", "1", "yes")


def validate_space_upload_config() -> tuple[bool, str]:
    """
    Validate configuration for Space upload.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not get_space_upload_enabled():
        return False, "Space upload is disabled"

    hf_token = get_hf_token()
    if not hf_token:
        return False, "HF_TOKEN is required for Space upload"

    hf_username = get_hf_username()
    if not hf_username:
        return False, "HF_USERNAME is required for Space upload"

    return True, ""
