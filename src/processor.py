"""
Main processing logic for extracting links and analyzing papers.
"""

from typing import Dict, Any
import gradio as gr
import re
import hashlib
from huggingface_hub import get_session
from huggingface_hub.utils import hf_raise_for_status

from .papers import fetch_daily_papers, fetch_paper_page, extract_links_from_html, process_repositories, process_claude_initialization, process_gradio_generation, process_space_upload
from .database import load_database, save_database
from .status import ProcessingStatus, StepStatus, init_paper_entry, update_step_status


def extract_and_save_links(
    date_filter: str = None,
    hf_token: str = None,
    clone_repos: bool = True,
    progress=gr.Progress()
) -> str:
    """
    Extract links from papers and optionally clone GitHub repositories.
    Uses incremental saving and status tracking.

    Args:
        date_filter: Optional date filter in YYYY-MM-DD format.
        hf_token: HuggingFace API token.
        clone_repos: Whether to clone GitHub repositories.
        progress: Gradio progress tracker.

    Returns:
        Status message.
    """
    # Fetch papers
    papers = fetch_daily_papers(date_filter if date_filter else None)

    if not papers:
        return "No papers found to process."

    # Load existing database
    database = load_database()
    existing_papers = {p.get("paper_id"): p for p in database.get("papers", [])}

    processed = 0
    skipped = 0
    errors = 0
    repos_cloned = 0
    skipped_papers = []

    print(f"\n📊 Database Status: {len(existing_papers)} papers already in database")
    print(f"📋 Found {len(papers)} papers to process")
    print(f"🔧 Repository cloning: {'enabled' if clone_repos else 'disabled'}")

    for idx, paper in enumerate(papers):
        paper_id = paper.get('paper', {}).get('id', 'N/A')
        title = paper.get('title', 'No title')

        progress((idx + 1) / len(papers), desc=f"Processing {paper_id}...")

        # Check if paper exists and what status it has
        if paper_id in existing_papers:
            existing_paper = existing_papers[paper_id]

            # Check if link extraction is complete
            link_extraction_status = existing_paper.get('processing_steps', {}).get('link_extraction', {}).get('status')

            if link_extraction_status == StepStatus.COMPLETED:
                # Links already extracted, check if we need to analyze repos or initialize claude
                if clone_repos:
                    repo_analysis_status = existing_paper.get('processing_steps', {}).get('repo_analysis', {}).get('status')
                    claude_init_status = existing_paper.get('processing_steps', {}).get('claude_init', {}).get('status')

                    # Check if we need to analyze repos
                    if repo_analysis_status not in [StepStatus.COMPLETED, StepStatus.IN_PROGRESS]:
                        print(f"\n🔍 Analyzing repos for existing paper: {paper_id}")
                        repos_count = process_repositories(existing_paper, database)
                        repos_cloned += repos_count

                        # Initialize claude after cloning
                        if repos_count > 0:
                            process_claude_initialization(existing_paper, database)
                            # Generate Gradio apps after initialization
                            process_gradio_generation(existing_paper, database)
                            # Upload to Spaces after generation
                            process_space_upload(existing_paper, database)
                    # Check if we need to initialize claude (repos already cloned)
                    elif claude_init_status not in [StepStatus.COMPLETED, StepStatus.SKIPPED]:
                        print(f"\n🤖 Initializing claude for existing paper: {paper_id}")
                        process_claude_initialization(existing_paper, database)
                        # Generate Gradio apps after initialization
                        process_gradio_generation(existing_paper, database)
                        # Upload to Spaces after generation
                        process_space_upload(existing_paper, database)
                    # Check if we need to generate Gradio apps (repos already initialized)
                    else:
                        gradio_gen_status = existing_paper.get('processing_steps', {}).get('gradio_generation', {}).get('status')
                        if gradio_gen_status not in [StepStatus.COMPLETED, StepStatus.SKIPPED]:
                            print(f"\n🎨 Generating Gradio apps for existing paper: {paper_id}")
                            process_gradio_generation(existing_paper, database)
                            # Upload to Spaces after generation
                            process_space_upload(existing_paper, database)
                        else:
                            # Check if we need to upload to Spaces (apps already generated)
                            space_upload_status = existing_paper.get('processing_steps', {}).get('space_upload', {}).get('status')
                            if space_upload_status not in [StepStatus.COMPLETED, StepStatus.SKIPPED]:
                                print(f"\n📤 Uploading to Spaces for existing paper: {paper_id}")
                                process_space_upload(existing_paper, database)
                            else:
                                skipped += 1
                                skipped_papers.append(paper_id)
                                print(f"⏭️  Skipping {paper_id} (already fully processed)")
                else:
                    skipped += 1
                    skipped_papers.append(paper_id)
                    print(f"⏭️  Skipping {paper_id} (links already extracted)")
                continue

        # Initialize new paper entry
        print(f"\n🔄 Processing new paper: {paper_id}")
        print(f"   Title: {title}")

        paper_entry = init_paper_entry(paper_id, title)
        paper_entry['processing_status'] = ProcessingStatus.EXTRACTING_LINKS

        # Step 1: Extract links
        update_step_status(paper_entry, 'link_extraction', StepStatus.IN_PROGRESS)

        html_content = fetch_paper_page(paper_id)
        if not html_content:
            errors += 1
            paper_entry['processing_status'] = ProcessingStatus.ERROR
            update_step_status(paper_entry, 'link_extraction', StepStatus.ERROR, "Failed to fetch paper page")
            database.setdefault("papers", []).append(paper_entry)
            save_database(database)
            print(f"❌ Error fetching page for {paper_id}")
            continue

        # Extract links from HTML
        print(f"🔗 Extracting links from HTML...")
        extracted_links = extract_links_from_html(paper_id, title, html_content, hf_token)

        if "error" in extracted_links:
            errors += 1
            paper_entry['processing_status'] = ProcessingStatus.ERROR
            update_step_status(paper_entry, 'link_extraction', StepStatus.ERROR, extracted_links.get("error"))
        else:
            paper_entry['links'] = extracted_links.get('links', {})
            paper_entry['processing_status'] = ProcessingStatus.LINKS_EXTRACTED
            update_step_status(paper_entry, 'link_extraction', StepStatus.COMPLETED)
            print(f"✅ Links extracted successfully")

        # Save after link extraction
        if paper_id in existing_papers:
            # Update existing entry
            for i, p in enumerate(database['papers']):
                if p['paper_id'] == paper_id:
                    database['papers'][i] = paper_entry
                    break
        else:
            database.setdefault("papers", []).append(paper_entry)

        save_database(database)
        processed += 1

        # Step 2: Analyze and clone repositories (if enabled)
        if clone_repos and paper_entry['processing_status'] != ProcessingStatus.ERROR:
            repos_cloned_count = process_repositories(paper_entry, database)
            repos_cloned += repos_cloned_count

            # Step 3: Initialize cloned repositories with claude /init
            if repos_cloned_count > 0:
                process_claude_initialization(paper_entry, database)

                # Step 4: Generate Gradio apps for initialized repositories
                process_gradio_generation(paper_entry, database)

                # Step 5: Upload to HuggingFace Spaces
                process_space_upload(paper_entry, database)

    result = f"✅ Processing complete!\n\n"
    result += f"- Processed: {processed} papers\n"
    result += f"- Skipped: {skipped} papers\n"
    result += f"- Errors: {errors} papers\n"
    if clone_repos:
        result += f"- Repositories cloned: {repos_cloned}\n"
    result += f"- Total in database: {len(database.get('papers', []))} papers\n"

    if skipped > 0:
        result += f"\n📦 Skipped papers:\n"
        for pid in skipped_papers[:5]:
            result += f"  • {pid}\n"
        if len(skipped_papers) > 5:
            result += f"  ... and {len(skipped_papers) - 5} more\n"

    return result


def process_manual_url(
    url: str,
    title: str = None,
    hf_token: str = None,
    clone_repos: bool = True,
    progress=gr.Progress()
) -> str:
    """
    Process a manually entered URL to extract links and optionally clone repositories.

    Args:
        url: The URL to process (HuggingFace paper, space, model, or any web page)
        title: Optional title for the entry (auto-generated if not provided)
        hf_token: HuggingFace API token
        clone_repos: Whether to clone GitHub repositories
        progress: Gradio progress tracker

    Returns:
        Status message
    """
    if not url or not url.strip():
        return "❌ Error: Please provide a valid URL"

    url = url.strip()

    # Validate URL format
    if not url.startswith(('http://', 'https://')):
        return "❌ Error: URL must start with http:// or https://"

    # Generate paper_id from URL
    paper_id = generate_id_from_url(url)

    # Generate title if not provided
    if not title or not title.strip():
        title = f"Manual Entry: {url}"
    else:
        title = title.strip()

    print(f"\n🔄 Processing manual URL")
    print(f"   URL: {url}")
    print(f"   Generated ID: {paper_id}")
    print(f"   Title: {title}")

    # Load database
    database = load_database()
    existing_papers = {p.get("paper_id"): p for p in database.get("papers", [])}

    # Check if already exists
    if paper_id in existing_papers:
        existing_paper = existing_papers[paper_id]
        link_extraction_status = existing_paper.get('processing_steps', {}).get('link_extraction', {}).get('status')

        if link_extraction_status == StepStatus.COMPLETED:
            return f"⚠️ This URL has already been processed (ID: {paper_id})\nUse the Database Viewer to see the results."

    progress(0.1, desc="Initializing...")

    # Initialize paper entry
    paper_entry = init_paper_entry(paper_id, title)
    paper_entry['source_url'] = url  # Store the original URL
    paper_entry['entry_type'] = 'manual'  # Mark as manual entry
    paper_entry['processing_status'] = ProcessingStatus.EXTRACTING_LINKS

    # Step 1: Fetch HTML content
    progress(0.2, desc="Fetching URL content...")
    update_step_status(paper_entry, 'link_extraction', StepStatus.IN_PROGRESS)

    try:
        session = get_session()
        response = session.get(url, timeout=30)
        hf_raise_for_status(response)
        html_content = response.text
        print(f"✅ Successfully fetched URL content ({len(html_content)} chars)")
    except Exception as e:
        error_msg = f"Failed to fetch URL: {str(e)}"
        print(f"❌ {error_msg}")
        paper_entry['processing_status'] = ProcessingStatus.ERROR
        update_step_status(paper_entry, 'link_extraction', StepStatus.ERROR, error_msg)
        database.setdefault("papers", []).append(paper_entry)
        save_database(database)
        return f"❌ Error: {error_msg}"

    # Step 2: Extract links from HTML
    progress(0.4, desc="Extracting links from page...")
    print(f"🔗 Extracting links from HTML...")

    extracted_links = extract_links_from_html(paper_id, title, html_content, hf_token)

    if "error" in extracted_links:
        error_msg = extracted_links.get("error")
        print(f"❌ Error extracting links: {error_msg}")
        paper_entry['processing_status'] = ProcessingStatus.ERROR
        update_step_status(paper_entry, 'link_extraction', StepStatus.ERROR, error_msg)
    else:
        paper_entry['links'] = extracted_links.get('links', {})
        paper_entry['processing_status'] = ProcessingStatus.LINKS_EXTRACTED
        update_step_status(paper_entry, 'link_extraction', StepStatus.COMPLETED)
        print(f"✅ Links extracted successfully")

        # Count extracted links
        total_links = sum(len(v) for v in paper_entry['links'].values())
        print(f"   Found {total_links} links across all categories")

    # Save after link extraction
    if paper_id in existing_papers:
        for i, p in enumerate(database['papers']):
            if p['paper_id'] == paper_id:
                database['papers'][i] = paper_entry
                break
    else:
        database.setdefault("papers", []).append(paper_entry)

    save_database(database)
    progress(0.6, desc="Links extracted, saving...")

    # Step 3: Analyze and clone repositories (if enabled)
    repos_cloned = 0
    if clone_repos and paper_entry['processing_status'] != ProcessingStatus.ERROR:
        progress(0.7, desc="Cloning repositories...")
        repos_cloned = process_repositories(paper_entry, database)

        # Step 4: Initialize cloned repositories with claude /init
        if repos_cloned > 0:
            progress(0.8, desc="Initializing with claude...")
            process_claude_initialization(paper_entry, database)

            # Step 5: Generate Gradio apps
            progress(0.85, desc="Generating Gradio app...")
            process_gradio_generation(paper_entry, database)

            # Step 6: Upload to HuggingFace Spaces
            progress(0.95, desc="Uploading to Spaces...")
            process_space_upload(paper_entry, database)

    progress(1.0, desc="Complete!")

    # Build result message
    result = f"✅ Successfully processed manual URL!\n\n"
    result += f"📋 Entry Details:\n"
    result += f"- ID: {paper_id}\n"
    result += f"- Title: {title}\n"
    result += f"- URL: {url}\n\n"
    result += f"🔗 Extracted Links:\n"

    for category, links in paper_entry['links'].items():
        if links:
            category_name = category.replace('_', ' ').title()
            result += f"- {category_name}: {len(links)}\n"

    if clone_repos:
        result += f"\n📦 Repositories: {repos_cloned} cloned\n"

    result += f"\n💾 Saved to database. View details using ID: {paper_id}"

    return result


def generate_id_from_url(url: str) -> str:
    """
    Generate a unique ID from a URL.

    For HuggingFace paper URLs, extracts the paper ID.
    For other URLs, creates a hash-based ID.

    Args:
        url: The URL to process

    Returns:
        A unique identifier string
    """
    # Try to extract HuggingFace paper ID
    paper_match = re.search(r'huggingface\.co/papers/(\d+\.\d+)', url)
    if paper_match:
        return paper_match.group(1)

    # Try to extract HuggingFace space ID
    space_match = re.search(r'huggingface\.co/spaces/([^/]+/[^/?#]+)', url)
    if space_match:
        space_id = space_match.group(1).replace('/', '_')
        return f"space_{space_id}"

    # Try to extract HuggingFace model ID
    model_match = re.search(r'huggingface\.co/([^/]+/[^/?#]+)(?:/|$)', url)
    if model_match and '/spaces/' not in url and '/papers/' not in url:
        model_id = model_match.group(1).replace('/', '_')
        return f"model_{model_id}"

    # For other URLs, create a hash-based ID
    # Use first 12 chars of SHA256 hash
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:12]

    # Try to extract domain for readability
    domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
    if domain_match:
        domain = domain_match.group(1).replace('.', '_')[:20]
        return f"manual_{domain}_{url_hash}"

    return f"manual_{url_hash}"


def retry_failed_jobs() -> str:
    """
    Check database for failed jobs and automatically retry them.

    This function is called on startup if AUTO_RETRY_FAILED is enabled.
    It looks for papers with ERROR status and retries incomplete steps.

    Returns:
        Status message describing what was retried
    """
    print("\n🔄 Checking for failed jobs to retry...")

    database = load_database()
    papers = database.get("papers", [])

    if not papers:
        print("   No papers in database")
        return "No papers in database"

    # Find papers with errors or incomplete steps
    failed_papers = []
    for paper in papers:
        paper_id = paper.get("paper_id", "Unknown")
        processing_status = paper.get("processing_status", "")
        steps = paper.get("processing_steps", {})

        # Check if paper has error status
        if processing_status == ProcessingStatus.ERROR:
            failed_papers.append(paper)
            print(f"   📋 Found failed paper: {paper_id} (status: {processing_status})")
        # Or check for any step with error status
        else:
            for step_name, step_info in steps.items():
                if isinstance(step_info, dict) and step_info.get('status') == StepStatus.ERROR:
                    failed_papers.append(paper)
                    print(f"   📋 Found paper with failed step: {paper_id} (step: {step_name})")
                    break

    if not failed_papers:
        print("   ✅ No failed jobs found")
        return "No failed jobs found"

    print(f"\n🔧 Retrying {len(failed_papers)} failed job(s)...\n")

    retried = 0
    for paper_entry in failed_papers:
        paper_id = paper_entry.get("paper_id", "Unknown")
        title = paper_entry.get("title", "No title")

        print(f"\n{'='*60}")
        print(f"🔄 Retrying paper: {paper_id}")
        print(f"   Title: {title}")
        print(f"{'='*60}\n")

        steps = paper_entry.get("processing_steps", {})

        # Check each step and retry if needed
        # Step 1: Link extraction (usually not the issue, but check)
        link_status = steps.get('link_extraction', {}).get('status')
        if link_status == StepStatus.ERROR:
            print(f"   ⚠️  Link extraction failed - skipping (manual review needed)")
            continue

        # Step 2: Repository analysis
        repo_status = steps.get('repo_analysis', {}).get('status')
        if repo_status == StepStatus.ERROR or repo_status == StepStatus.PENDING:
            print(f"   🔍 Retrying repository analysis...")
            process_repositories(paper_entry, database)

        # Step 3: Claude initialization
        claude_status = steps.get('claude_init', {}).get('status')
        if claude_status == StepStatus.ERROR or (claude_status == StepStatus.PENDING and repo_status == StepStatus.COMPLETED):
            print(f"   🤖 Retrying Claude initialization...")
            process_claude_initialization(paper_entry, database)

        # Step 4: Gradio generation
        gradio_status = steps.get('gradio_generation', {}).get('status')
        if gradio_status == StepStatus.ERROR or (gradio_status == StepStatus.PENDING and claude_status == StepStatus.COMPLETED):
            print(f"   🎨 Retrying Gradio app generation...")
            process_gradio_generation(paper_entry, database)

        # Step 5: Space upload
        space_status = steps.get('space_upload', {}).get('status')
        if space_status == StepStatus.ERROR or (space_status == StepStatus.PENDING and gradio_status == StepStatus.COMPLETED):
            print(f"   📤 Retrying Space upload...")
            process_space_upload(paper_entry, database)

        retried += 1

    result = f"\n✅ Retry complete!\n"
    result += f"- Papers retried: {retried}\n"
    result += f"- Total failed found: {len(failed_papers)}\n"

    print(f"\n{result}")

    return result
