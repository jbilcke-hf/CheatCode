"""
Status constants and helpers for tracking paper processing stages.
"""

from datetime import datetime
from typing import Dict, Any


class ProcessingStatus:
    """Global processing status for papers."""
    PENDING = "pending"
    EXTRACTING_LINKS = "extracting_links"
    LINKS_EXTRACTED = "links_extracted"
    ANALYZING_REPOS = "analyzing_repos"
    REPOS_ANALYZED = "repos_analyzed"
    INITIALIZING_CLAUDE = "initializing_claude"
    CLAUDE_INITIALIZED = "claude_initialized"
    GENERATING_GRADIO = "generating_gradio"
    GRADIO_GENERATED = "gradio_generated"
    UPLOADING_SPACES = "uploading_spaces"
    COMPLETED = "completed"
    ERROR = "error"


class StepStatus:
    """Status for individual processing steps."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ERROR = "error"
    SKIPPED = "skipped"


class RepoStatus:
    """Status for repository cloning."""
    PENDING = "pending"
    CLONING = "cloning"
    CLONED = "cloned"
    ERROR = "error"


class SpaceStatus:
    """Status for HuggingFace Space upload."""
    PENDING = "pending"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    ERROR = "error"
    SKIPPED = "skipped"


def init_paper_entry(paper_id: str, title: str) -> Dict[str, Any]:
    """
    Initialize a new paper entry with processing status structure.

    Args:
        paper_id: ArXiv paper ID
        title: Paper title

    Returns:
        Initialized paper dictionary
    """
    return {
        'paper_id': paper_id,
        'title': title,
        'processing_status': ProcessingStatus.PENDING,
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat(),
        'processing_steps': {
            'link_extraction': {
                'status': StepStatus.PENDING,
                'started_at': None,
                'completed_at': None,
                'error': None
            },
            'repo_analysis': {
                'status': StepStatus.PENDING,
                'started_at': None,
                'completed_at': None,
                'error': None,
                'repos_found': 0,
                'repos_cloned': 0
            },
            'claude_init': {
                'status': StepStatus.PENDING,
                'started_at': None,
                'completed_at': None,
                'error': None,
                'repos_initialized': 0,
                'claude_available': False
            },
            'gradio_generation': {
                'status': StepStatus.PENDING,
                'started_at': None,
                'completed_at': None,
                'error': None,
                'repos_generated': 0,
                'apps_created': 0
            },
            'space_upload': {
                'status': StepStatus.PENDING,
                'started_at': None,
                'completed_at': None,
                'error': None,
                'spaces_created': 0,
                'spaces_failed': 0,
                'space_urls': []
            }
        },
        'links': {
            'code_repositories': [],
            'model_weights': [],
            'datasets': [],
            'demo_links': [],
            'paper_links': []
        },
        'repositories': []
    }


def update_step_status(
    paper: Dict[str, Any],
    step_name: str,
    status: str,
    error: str = None
) -> Dict[str, Any]:
    """
    Update the status of a processing step.

    Args:
        paper: Paper dictionary
        step_name: Name of the processing step
        status: New status value
        error: Optional error message

    Returns:
        Updated paper dictionary
    """
    paper['updated_at'] = datetime.now().isoformat()

    if step_name not in paper['processing_steps']:
        paper['processing_steps'][step_name] = {}

    step = paper['processing_steps'][step_name]
    step['status'] = status

    if status == StepStatus.IN_PROGRESS and not step.get('started_at'):
        step['started_at'] = datetime.now().isoformat()
    elif status in [StepStatus.COMPLETED, StepStatus.ERROR]:
        step['completed_at'] = datetime.now().isoformat()

    if error:
        step['error'] = error

    return paper
