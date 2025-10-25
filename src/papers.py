"""
Paper fetching and link extraction operations.
"""

import json
import re
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from bs4 import BeautifulSoup
from huggingface_hub import get_session, InferenceClient
from huggingface_hub.utils import hf_raise_for_status

from .status import ProcessingStatus, StepStatus, init_paper_entry, update_step_status
from .repos import clone_repository
from .database import save_database
from .claude_init import check_claude_available, initialize_repository
from .gradio_generator import generate_gradio_app
from .config import get_claude_auto_install


def fetch_daily_papers(date: str = None) -> List[Dict[str, Any]]:
    """
    Fetch daily papers from Hugging Face API using huggingface_hub.

    Args:
        date: Optional date in YYYY-MM-DD format. If None, fetches today's papers.

    Returns:
        List of paper dictionaries containing paper metadata.
    """
    base_url = "https://huggingface.co/api/daily_papers"

    try:
        session = get_session()

        if date:
            response = session.get(f"{base_url}?date={date}")
        else:
            response = session.get(base_url)

        hf_raise_for_status(response)
        return response.json()
    except Exception as e:
        print(f"Error fetching papers: {e}")
        return []


def fetch_paper_page(paper_id: str) -> Optional[str]:
    """
    Fetch the HuggingFace paper page HTML content.

    Args:
        paper_id: ArXiv ID of the paper.

    Returns:
        HTML content of the paper page or None if error.
    """
    try:
        session = get_session()
        url = f"https://huggingface.co/papers/{paper_id}"
        response = session.get(url)
        hf_raise_for_status(response)
        return response.text
    except Exception as e:
        print(f"Error fetching paper page {paper_id}: {e}")
        return None


def extract_links_from_html(
    paper_id: str,
    paper_title: str,
    html_content: str,
    hf_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract relevant links from the paper page HTML using direct parsing.

    This function parses the HTML content and categorizes links using URL patterns,
    which is faster and more reliable than LLM-based extraction.

    Args:
        paper_id: ArXiv ID of the paper.
        paper_title: Title of the paper.
        html_content: HTML content of the paper page.
        hf_token: Not used, kept for API compatibility.

    Returns:
        Dictionary containing extracted and categorized links.
    """
    print(f"🔍 Parsing HTML content ({len(html_content)} characters)")

    try:
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')

        # Extract all URLs from the page
        all_links: Set[str] = set()

        # 1. Extract from <a> tags
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if href.startswith('http'):
                all_links.add(href)
            elif href.startswith('/'):
                all_links.add(f"https://huggingface.co{href}")

        # 2. Extract from text content (for links in abstracts/summaries)
        # Common pattern: URLs in plain text
        url_pattern = r'https?://[^\s<>"{}\\|^`\[\]]+[^\s<>"{}\\|^`\[\].,;!?)]'
        text_content = soup.get_text()
        for match in re.finditer(url_pattern, text_content):
            url = match.group(0)
            # Clean up any trailing characters that got caught
            url = re.sub(r'[.,;:!?)}\]]+$', '', url)
            all_links.add(url)

        # 3. Extract from JSON data embedded in the page (like data-props)
        for script_tag in soup.find_all('script'):
            if script_tag.string:
                for match in re.finditer(url_pattern, script_tag.string):
                    url = match.group(0)
                    url = re.sub(r'[.,;:!?)}\]]+$', '', url)
                    all_links.add(url)

        # Also check data attributes
        for tag in soup.find_all(attrs={'data-props': True}):
            data_props = tag.get('data-props', '')
            for match in re.finditer(url_pattern, data_props):
                url = match.group(0)
                url = re.sub(r'[.,;:!?)}\]]+$', '', url)
                all_links.add(url)

        print(f"   Found {len(all_links)} total unique URLs")

        # Categorize links
        categorized = {
            "code_repositories": [],
            "model_weights": [],
            "datasets": [],
            "demo_links": [],
            "paper_links": []
        }

        for url in all_links:
            url_lower = url.lower()

            # Code repositories
            if any(domain in url_lower for domain in ['github.com', 'gitlab.com', 'bitbucket.org', 'git.io']):
                categorized["code_repositories"].append(url)
                print(f"   ✓ Code repo: {url}")

            # Model weights
            elif 'huggingface.co' in url_lower and any(path in url_lower for path in ['/models/', '/model/']):
                categorized["model_weights"].append(url)
                print(f"   ✓ Model: {url}")

            # Datasets
            elif 'huggingface.co' in url_lower and '/datasets/' in url_lower:
                categorized["datasets"].append(url)
                print(f"   ✓ Dataset: {url}")

            # Demo links
            elif 'huggingface.co' in url_lower and '/spaces/' in url_lower:
                categorized["demo_links"].append(url)
                print(f"   ✓ Demo: {url}")
            elif any(domain in url_lower for domain in ['colab.research.google.com', 'kaggle.com/code', 'replicate.com']):
                categorized["demo_links"].append(url)
                print(f"   ✓ Demo: {url}")

            # Paper links
            elif any(domain in url_lower for domain in ['arxiv.org', 'aclweb.org', 'openreview.net', 'proceedings.mlr.press']):
                categorized["paper_links"].append(url)
                print(f"   ✓ Paper: {url}")
            elif url_lower.endswith('.pdf'):
                categorized["paper_links"].append(url)
                print(f"   ✓ Paper PDF: {url}")

        # Print summary
        total_categorized = sum(len(v) for v in categorized.values())
        print(f"📊 Categorization summary:")
        print(f"   Code repositories: {len(categorized['code_repositories'])}")
        print(f"   Model weights: {len(categorized['model_weights'])}")
        print(f"   Datasets: {len(categorized['datasets'])}")
        print(f"   Demo links: {len(categorized['demo_links'])}")
        print(f"   Paper links: {len(categorized['paper_links'])}")
        print(f"   Total categorized: {total_categorized}/{len(all_links)}")

        return {
            "paper_id": paper_id,
            "title": paper_title,
            "extracted_at": datetime.now().isoformat(),
            "links": categorized,
            "total_links_found": len(all_links),
            "total_links_categorized": total_categorized
        }

    except Exception as e:
        print(f"❌ Error extracting links from HTML for {paper_id}: {e}")
        import traceback
        traceback.print_exc()
        return {
            "paper_id": paper_id,
            "title": paper_title,
            "extracted_at": datetime.now().isoformat(),
            "error": str(e),
            "links": {
                "code_repositories": [],
                "model_weights": [],
                "datasets": [],
                "demo_links": [],
                "paper_links": []
            },
            "total_links_found": 0,
            "total_links_categorized": 0
        }


def extract_links_with_llm(
    paper_id: str,
    paper_title: str,
    html_content: str,
    hf_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Use an LLM to extract relevant links from the paper page HTML.

    Args:
        paper_id: ArXiv ID of the paper.
        paper_title: Title of the paper.
        html_content: HTML content of the paper page.
        hf_token: HuggingFace API token for authentication.

    Returns:
        Dictionary containing extracted links.
    """
    try:
        client = InferenceClient(token=hf_token)

        prompt = f"""You are analyzing a HuggingFace paper page for the paper titled "{paper_title}" (ArXiv ID: {paper_id}).

From the following HTML content, extract ALL relevant links and categorize them as:
1. code_repositories: GitHub, GitLab, or other code repository links
2. model_weights: HuggingFace model links (huggingface.co/...) or direct download links for model weights
3. datasets: HuggingFace dataset links or other dataset sources
4. demo_links: HuggingFace Spaces, Colab notebooks, or live demos
5. paper_links: ArXiv, PDF, or other paper links

Please respond ONLY with a JSON object in this exact format (no markdown, no extra text):
{{
  "code_repositories": ["url1", "url2"],
  "model_weights": ["url1", "url2"],
  "datasets": ["url1", "url2"],
  "demo_links": ["url1", "url2"],
  "paper_links": ["url1", "url2"]
}}

If a category has no links, use an empty array [].

HTML Content (truncated to first 8000 characters):
{html_content[:8000]}
"""

        messages = [{"role": "user", "content": prompt}]
        response = client.chat_completion(
            messages=messages,
            model="Qwen/Qwen3-235B-A22B-Instruct-2507",
            max_tokens=1000,
            temperature=0.3
        )

        response_text = response.choices[0].message.content.strip()

        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        extracted_data = json.loads(response_text)

        return {
            "paper_id": paper_id,
            "title": paper_title,
            "extracted_at": datetime.now().isoformat(),
            "links": extracted_data
        }

    except Exception as e:
        print(f"Error extracting links with LLM for {paper_id}: {e}")
        return {
            "paper_id": paper_id,
            "title": paper_title,
            "extracted_at": datetime.now().isoformat(),
            "error": str(e),
            "links": {
                "code_repositories": [],
                "model_weights": [],
                "datasets": [],
                "demo_links": [],
                "paper_links": []
            }
        }


def process_repositories(paper_entry: Dict[str, Any], database: Dict[str, Any]) -> int:
    """
    Process GitHub repositories for a paper entry.

    Args:
        paper_entry: Paper dictionary
        database: Full database dictionary

    Returns:
        Number of repositories successfully cloned
    """
    paper_id = paper_entry['paper_id']
    code_repos = paper_entry.get('links', {}).get('code_repositories', [])

    if not code_repos:
        print(f"   No code repositories found for {paper_id}")
        update_step_status(paper_entry, 'repo_analysis', StepStatus.SKIPPED)
        paper_entry['processing_steps']['repo_analysis']['repos_found'] = 0
        paper_entry['processing_steps']['repo_analysis']['repos_cloned'] = 0
        save_database(database)
        return 0

    print(f"\n📦 Found {len(code_repos)} code repositories")
    paper_entry['processing_status'] = ProcessingStatus.ANALYZING_REPOS
    update_step_status(paper_entry, 'repo_analysis', StepStatus.IN_PROGRESS)
    paper_entry['processing_steps']['repo_analysis']['repos_found'] = len(code_repos)

    repos_cloned = 0
    paper_entry['repositories'] = paper_entry.get('repositories', [])

    for repo_url in code_repos:
        # Check if repo already cloned
        existing_repo = None
        for r in paper_entry['repositories']:
            if r.get('url') == repo_url:
                existing_repo = r
                break

        if existing_repo and existing_repo.get('status') == 'cloned':
            print(f"   ⏭️  Repo already cloned: {repo_url}")
            repos_cloned += 1
            continue

        # Clone the repository
        clone_result = clone_repository(repo_url, paper_id)

        if existing_repo:
            # Update existing entry
            for i, r in enumerate(paper_entry['repositories']):
                if r.get('url') == repo_url:
                    paper_entry['repositories'][i] = clone_result
                    break
        else:
            paper_entry['repositories'].append(clone_result)

        if clone_result['status'] == 'cloned':
            repos_cloned += 1

        # Save after each repo clone
        save_database(database)

    paper_entry['processing_steps']['repo_analysis']['repos_cloned'] = repos_cloned
    update_step_status(paper_entry, 'repo_analysis', StepStatus.COMPLETED)
    paper_entry['processing_status'] = ProcessingStatus.REPOS_ANALYZED

    save_database(database)
    print(f"✅ Repository analysis complete: {repos_cloned}/{len(code_repos)} cloned")

    return repos_cloned


def process_claude_initialization(paper_entry: Dict[str, Any], database: Dict[str, Any]) -> int:
    """
    Run claude /init on cloned repositories to generate CLAUDE.md files.

    Args:
        paper_entry: Paper dictionary
        database: Full database dictionary

    Returns:
        Number of repositories successfully initialized
    """
    paper_id = paper_entry['paper_id']
    repositories = paper_entry.get('repositories', [])

    # Filter for successfully cloned repos
    cloned_repos = [r for r in repositories if r.get('status') == 'cloned']

    if not cloned_repos:
        print(f"   No cloned repositories found for {paper_id}")
        update_step_status(paper_entry, 'claude_init', StepStatus.SKIPPED)
        paper_entry['processing_steps']['claude_init']['repos_initialized'] = 0
        save_database(database)
        return 0

    # Check if claude is available (or will be auto-installed)
    claude_path = check_claude_available()
    claude_available = claude_path is not None
    auto_install = get_claude_auto_install()

    paper_entry['processing_steps']['claude_init']['claude_available'] = claude_available

    # Only skip if Claude is not available AND auto-install is disabled
    if not claude_available and not auto_install:
        print(f"   Claude CLI not available, skipping initialization for {paper_id}")
        print(f"   (Set CLAUDE_AUTO_INSTALL=true to enable automatic installation)")
        update_step_status(paper_entry, 'claude_init', StepStatus.SKIPPED, "Claude CLI not found")
        paper_entry['processing_steps']['claude_init']['repos_initialized'] = 0
        save_database(database)
        return 0

    print(f"\n🤖 Initializing {len(cloned_repos)} repositories with claude /init")
    paper_entry['processing_status'] = ProcessingStatus.INITIALIZING_CLAUDE
    update_step_status(paper_entry, 'claude_init', StepStatus.IN_PROGRESS)

    repos_initialized = 0

    for repo_entry in repositories:
        # Skip if not cloned successfully
        if repo_entry.get('status') != 'cloned':
            continue

        # Initialize claude_init tracking in repo entry if not present
        if 'claude_init' not in repo_entry:
            repo_entry['claude_init'] = {}

        # Check if already initialized
        if repo_entry['claude_init'].get('success'):
            print(f"   ⏭️  Already initialized: {repo_entry.get('url')}")
            repos_initialized += 1
            continue

        # Run claude initialization
        print(f"\n  📂 Repository: {repo_entry.get('url')}")
        init_result = initialize_repository(repo_entry, auto_install=auto_install)

        # Update repo entry with initialization results
        repo_entry['claude_init'] = {
            'attempted': init_result['attempted'],
            'success': init_result['success'],
            'claude_available': init_result['claude_available'],
            'claude_md_exists': init_result['claude_md_exists'],
            'claude_md_path': init_result['claude_md_path'],
            'error': init_result['error'],
            'initialized_at': datetime.now().isoformat() if init_result['success'] else None
        }

        if init_result['success']:
            repos_initialized += 1

        # Save after each initialization
        save_database(database)

    paper_entry['processing_steps']['claude_init']['repos_initialized'] = repos_initialized
    update_step_status(paper_entry, 'claude_init', StepStatus.COMPLETED)
    paper_entry['processing_status'] = ProcessingStatus.CLAUDE_INITIALIZED

    save_database(database)
    print(f"✅ Claude initialization complete: {repos_initialized}/{len(cloned_repos)} initialized")

    return repos_initialized


def process_gradio_generation(paper_entry: Dict[str, Any], database: Dict[str, Any]) -> int:
    """
    Generate Gradio apps for initialized repositories.

    Args:
        paper_entry: Paper dictionary
        database: Full database dictionary

    Returns:
        Number of apps successfully generated
    """
    paper_id = paper_entry['paper_id']
    repositories = paper_entry.get('repositories', [])

    # Filter for repositories with CLAUDE.md (successfully initialized)
    initialized_repos = [
        r for r in repositories
        if r.get('claude_init', {}).get('success', False)
    ]

    if not initialized_repos:
        print(f"   No initialized repositories found for {paper_id}")
        update_step_status(paper_entry, 'gradio_generation', StepStatus.SKIPPED)
        paper_entry['processing_steps']['gradio_generation']['repos_generated'] = 0
        paper_entry['processing_steps']['gradio_generation']['apps_created'] = 0
        save_database(database)
        return 0

    # Check if claude is available
    claude_path = check_claude_available()
    if not claude_path:
        print(f"   Claude CLI not available, skipping Gradio generation for {paper_id}")
        update_step_status(paper_entry, 'gradio_generation', StepStatus.SKIPPED, "Claude CLI not found")
        paper_entry['processing_steps']['gradio_generation']['repos_generated'] = 0
        paper_entry['processing_steps']['gradio_generation']['apps_created'] = 0
        save_database(database)
        return 0

    print(f"\n🎨 Generating Gradio apps for {len(initialized_repos)} repositories")
    paper_entry['processing_status'] = ProcessingStatus.GENERATING_GRADIO
    update_step_status(paper_entry, 'gradio_generation', StepStatus.IN_PROGRESS)

    apps_generated = 0

    for repo_entry in repositories:
        # Skip if repo has no code
        if not repo_entry.get('has_code', False):
            print(f"   ⏭️  Skipping {repo_entry.get('url')} (no code)")
            continue

        # Skip if not initialized with Claude
        if not repo_entry.get('claude_init', {}).get('success', False):
            continue

        # Initialize gradio_generation tracking in repo entry if not present
        if 'gradio_generation' not in repo_entry:
            repo_entry['gradio_generation'] = {}

        # Check if already generated
        if repo_entry['gradio_generation'].get('success'):
            print(f"   ⏭️  Already generated: {repo_entry.get('url')}")
            apps_generated += 1
            continue

        # Generate Gradio app
        print(f"\n  📂 Repository: {repo_entry.get('url')}")
        gen_result = generate_gradio_app(repo_entry, claude_path)

        # Update repo entry with generation results
        repo_entry['gradio_generation'] = {
            'attempted': gen_result['attempted'],
            'success': gen_result['success'],
            'app_created': gen_result['app_created'],
            'readme_updated': gen_result['readme_updated'],
            'app_path': gen_result['app_path'],
            'readme_path': gen_result['readme_path'],
            'error': gen_result['error'],
            'generated_at': datetime.now().isoformat() if gen_result['success'] else None
        }

        if gen_result['success']:
            apps_generated += 1

        # Save after each generation
        save_database(database)

    paper_entry['processing_steps']['gradio_generation']['repos_generated'] = len(initialized_repos)
    paper_entry['processing_steps']['gradio_generation']['apps_created'] = apps_generated
    update_step_status(paper_entry, 'gradio_generation', StepStatus.COMPLETED)
    paper_entry['processing_status'] = ProcessingStatus.GRADIO_GENERATED

    save_database(database)
    print(f"✅ Gradio generation complete: {apps_generated}/{len(initialized_repos)} apps created")

    return apps_generated


def process_space_upload(paper_entry: Dict[str, Any], database: Dict[str, Any]) -> int:
    """
    Upload repositories to HuggingFace Spaces.

    Args:
        paper_entry: Paper dictionary
        database: Full database dictionary

    Returns:
        Number of spaces successfully created
    """
    from .space_uploader import process_space_uploads
    from .config import validate_space_upload_config, get_hf_token, get_hf_username, get_space_upload_private, get_space_upload_force

    paper_id = paper_entry['paper_id']
    repositories = paper_entry.get('repositories', [])

    # Validate configuration
    is_valid, error_msg = validate_space_upload_config()
    if not is_valid:
        print(f"   ⏭️  Space upload disabled: {error_msg}")
        update_step_status(paper_entry, 'space_upload', StepStatus.SKIPPED, error_msg)
        paper_entry['processing_steps']['space_upload']['spaces_created'] = 0
        paper_entry['processing_steps']['space_upload']['spaces_failed'] = 0
        paper_entry['processing_steps']['space_upload']['space_urls'] = []
        save_database(database)
        return 0

    # Filter for repositories with Gradio apps (successfully generated)
    repos_with_apps = [
        r for r in repositories
        if r.get('gradio_generation', {}).get('success', False)
    ]

    if not repos_with_apps:
        print(f"   No repositories with Gradio apps found for {paper_id}")
        update_step_status(paper_entry, 'space_upload', StepStatus.SKIPPED, "No apps to upload")
        paper_entry['processing_steps']['space_upload']['spaces_created'] = 0
        paper_entry['processing_steps']['space_upload']['spaces_failed'] = 0
        paper_entry['processing_steps']['space_upload']['space_urls'] = []
        save_database(database)
        return 0

    print(f"\n📤 Uploading {len(repos_with_apps)} repositories to HuggingFace Spaces")
    paper_entry['processing_status'] = ProcessingStatus.UPLOADING_SPACES
    update_step_status(paper_entry, 'space_upload', StepStatus.IN_PROGRESS)

    # Get credentials and settings
    hf_token = get_hf_token()
    hf_username = get_hf_username()
    private = get_space_upload_private()
    force = get_space_upload_force()

    # Process uploads
    summary = process_space_uploads(
        paper_entry,
        hf_token,
        hf_username,
        private=private,
        force=force
    )

    # Update paper entry with results
    paper_entry['processing_steps']['space_upload']['spaces_created'] = summary['spaces_created']
    paper_entry['processing_steps']['space_upload']['spaces_failed'] = summary['spaces_failed']
    paper_entry['processing_steps']['space_upload']['space_urls'] = summary['space_urls']

    # Mark as ERROR if all uploads failed, otherwise COMPLETED
    if summary['spaces_failed'] > 0 and summary['spaces_created'] == 0:
        error_summary = f"All {summary['spaces_failed']} uploads failed"
        update_step_status(paper_entry, 'space_upload', StepStatus.ERROR, error_summary)
        paper_entry['processing_status'] = ProcessingStatus.ERROR
    elif summary['spaces_failed'] > 0:
        error_summary = f"{summary['spaces_failed']} of {summary['total_repos']} uploads failed"
        update_step_status(paper_entry, 'space_upload', StepStatus.COMPLETED, error_summary)
        paper_entry['processing_status'] = ProcessingStatus.COMPLETED
    else:
        update_step_status(paper_entry, 'space_upload', StepStatus.COMPLETED)
        paper_entry['processing_status'] = ProcessingStatus.COMPLETED

    save_database(database)
    print(f"✅ Space upload complete: {summary['spaces_created']}/{summary['total_repos']} spaces created")

    if summary['errors']:
        print(f"   ⚠️  Errors occurred:")
        for error_info in summary['errors'][:3]:
            print(f"      - {error_info['repo_url']}: {error_info['error']}")

    return summary['spaces_created']
