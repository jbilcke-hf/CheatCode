"""
UI helper functions for formatting and displaying data.
"""

from typing import List, Dict, Any


def format_papers_display(papers: List[Dict[str, Any]]) -> str:
    """
    Format papers data into a readable HTML display.

    Args:
        papers: List of paper dictionaries.

    Returns:
        HTML formatted string displaying paper information.
    """
    if not papers:
        return "<p>No papers found or error fetching data.</p>"

    html = f"<h2>📚 Daily Papers ({len(papers)} papers)</h2>"

    for idx, paper in enumerate(papers, 1):
        title = paper.get('title', 'No title')
        paper_id = paper.get('paper', {}).get('id', 'N/A')
        authors = paper.get('paper', {}).get('authors', [])
        summary = paper.get('paper', {}).get('summary', 'No summary available')
        published_at = paper.get('publishedAt', 'N/A')
        upvotes = paper.get('upvotes', 0)

        # Format authors
        author_names = ", ".join([author.get('name', 'Unknown') for author in authors[:3]])
        if len(authors) > 3:
            author_names += f" et al. ({len(authors)} authors)"

        html += f"""
        <div style="border: 2px solid #475569; padding: 20px; margin: 15px 0; border-radius: 10px; background-color: #1e293b; box-shadow: 0 2px 4px rgba(0,0,0,0.3);">
            <h3 style="margin-top: 0; color: #fb923c; font-size: 1.3em;">{idx}. {title}</h3>
            <p style="color: #e2e8f0; margin: 8px 0;"><strong style="color: #f8fafc;">ArXiv ID:</strong> <a href="https://arxiv.org/abs/{paper_id}" target="_blank" style="color: #60a5fa; text-decoration: none;">{paper_id}</a></p>
            <p style="color: #e2e8f0; margin: 8px 0;"><strong style="color: #f8fafc;">Authors:</strong> {author_names}</p>
            <p style="color: #e2e8f0; margin: 8px 0;"><strong style="color: #f8fafc;">Published:</strong> {published_at}</p>
            <p style="color: #e2e8f0; margin: 8px 0;"><strong style="color: #f8fafc;">Upvotes:</strong> ❤️ {upvotes}</p>
            <details style="margin-top: 12px;">
                <summary style="cursor: pointer; color: #60a5fa; font-weight: bold; padding: 5px 0;"><strong>Summary</strong></summary>
                <p style="margin-top: 10px; text-align: justify; color: #e2e8f0; line-height: 1.6;">{summary}</p>
            </details>
        </div>
        """

    return html


def get_database_stats(database: Dict[str, Any]) -> str:
    """
    Get statistics about the database.

    Args:
        database: Database dictionary

    Returns:
        HTML formatted statistics.
    """
    papers = database.get("papers", [])

    if not papers:
        return "<p>Database is empty. Extract some papers first!</p>"

    total_papers = len(papers)

    # Count links by category
    total_code = sum(len(p.get("links", {}).get("code_repositories", [])) for p in papers)
    total_models = sum(len(p.get("links", {}).get("model_weights", [])) for p in papers)
    total_datasets = sum(len(p.get("links", {}).get("datasets", [])) for p in papers)
    total_demos = sum(len(p.get("links", {}).get("demo_links", [])) for p in papers)
    total_paper_links = sum(len(p.get("links", {}).get("paper_links", [])) for p in papers)

    # Count repos
    total_repos_found = sum(p.get('processing_steps', {}).get('repo_analysis', {}).get('repos_found', 0) for p in papers)
    total_repos_cloned = sum(p.get('processing_steps', {}).get('repo_analysis', {}).get('repos_cloned', 0) for p in papers)

    # Count claude initializations
    total_repos_initialized = sum(p.get('processing_steps', {}).get('claude_init', {}).get('repos_initialized', 0) for p in papers)
    claude_available = any(p.get('processing_steps', {}).get('claude_init', {}).get('claude_available', False) for p in papers)

    # Count Gradio apps generated
    total_apps_created = sum(p.get('processing_steps', {}).get('gradio_generation', {}).get('apps_created', 0) for p in papers)

    # Count Spaces uploaded
    total_spaces_created = sum(p.get('processing_steps', {}).get('space_upload', {}).get('spaces_created', 0) for p in papers)
    total_space_urls = []
    for p in papers:
        urls = p.get('processing_steps', {}).get('space_upload', {}).get('space_urls', [])
        total_space_urls.extend(urls)

    # Get most recent papers
    recent_papers = sorted(papers, key=lambda x: x.get("created_at", ""), reverse=True)[:5]

    html = f"""
    <div style="padding: 20px; background-color: #1e293b; border-radius: 10px; border: 2px solid #475569; box-shadow: 0 2px 4px rgba(0,0,0,0.3);">
        <h3 style="color: #fb923c; margin-top: 0;">📊 Database Statistics</h3>
        <p style="color: #e2e8f0; font-size: 1.1em;"><strong style="color: #f8fafc;">Total Papers:</strong> {total_papers}</p>
        <p style="color: #e2e8f0; margin-top: 15px;"><strong style="color: #f8fafc;">Total Links Extracted:</strong></p>
        <ul style="color: #e2e8f0; line-height: 1.8;">
            <li>💻 Code Repositories: <strong>{total_code}</strong></li>
            <li>🤖 Model Weights: <strong>{total_models}</strong></li>
            <li>📊 Datasets: <strong>{total_datasets}</strong></li>
            <li>🎮 Demo Links: <strong>{total_demos}</strong></li>
            <li>📄 Paper Links: <strong>{total_paper_links}</strong></li>
        </ul>

        <p style="color: #e2e8f0; margin-top: 15px;"><strong style="color: #f8fafc;">Repository Analysis:</strong></p>
        <ul style="color: #e2e8f0; line-height: 1.8;">
            <li>🔍 Repositories Found: <strong>{total_repos_found}</strong></li>
            <li>✅ Repositories Cloned: <strong>{total_repos_cloned}</strong></li>
            <li>🤖 Claude Init: <strong>{total_repos_initialized}</strong> {'<em style="color: #4ade80;">(Claude CLI available)</em>' if claude_available else '<em style="color: #f87171;">(Claude CLI not available)</em>'}</li>
            <li>🎨 Gradio Apps Generated: <strong>{total_apps_created}</strong></li>
            <li>🚀 Spaces Uploaded: <strong>{total_spaces_created}</strong></li>
        </ul>

        <h4 style="color: #60a5fa; margin-top: 20px;">Recently Added Papers:</h4>
        <ul style="color: #e2e8f0; line-height: 1.8;">
    """

    for paper in recent_papers:
        paper_id = paper.get("paper_id", "Unknown")
        title = paper.get("title", "No title")
        created_at = paper.get("created_at", "Unknown")
        status = paper.get("processing_status", "unknown")
        html += f"<li><strong style='color: #f8fafc;'>{paper_id}</strong>: {title[:60]}{'...' if len(title) > 60 else ''} <em style='color: #cbd5e1;'>(added {created_at[:10]}, status: {status})</em></li>\n"

    html += """
        </ul>
    </div>
    """

    return html


def view_paper_details(paper: Dict[str, Any]) -> str:
    """
    View details of a specific paper from the database.

    Args:
        paper: Paper dictionary

    Returns:
        HTML formatted paper details.
    """
    if not paper:
        return "<p>Paper not found in database.</p>"

    paper_id = paper.get("paper_id", "Unknown")
    title = paper.get("title", "No title")
    processing_status = paper.get("processing_status", "unknown")
    created_at = paper.get("created_at", "Unknown")
    links = paper.get("links", {})
    repositories = paper.get("repositories", [])

    html = f"""
    <div style="padding: 20px; background-color: #1e293b; border-radius: 10px; border: 2px solid #475569; box-shadow: 0 2px 4px rgba(0,0,0,0.3);">
        <h3 style="color: #fb923c; margin-top: 0;">{title}</h3>
        <p style="color: #e2e8f0; margin: 8px 0;"><strong style="color: #f8fafc;">Paper ID:</strong> {paper_id}</p>
        <p style="color: #e2e8f0; margin: 8px 0;"><strong style="color: #f8fafc;">Processing Status:</strong> <span style="background-color: #334155; color: #e2e8f0; padding: 2px 8px; border-radius: 4px;">{processing_status}</span></p>
        <p style="color: #e2e8f0; margin: 8px 0;"><strong style="color: #f8fafc;">Created:</strong> {created_at}</p>

        <h4 style="color: #60a5fa; margin-top: 20px;">🔗 Extracted Links:</h4>
    """

    # Code repositories
    code_repos = links.get("code_repositories", [])
    if code_repos:
        html += "<h5 style='color: #e2e8f0; margin-top: 15px;'>💻 Code Repositories:</h5><ul style='color: #e2e8f0; line-height: 1.8;'>"
        for link in code_repos:
            html += f'<li><a href="{link}" target="_blank" style="color: #60a5fa; text-decoration: none;">{link}</a></li>'
        html += "</ul>"
    else:
        html += "<p style='color: #94a3b8; font-style: italic; margin: 10px 0;'>No code repositories found</p>"

    # Model weights
    models = links.get("model_weights", [])
    if models:
        html += "<h5 style='color: #e2e8f0; margin-top: 15px;'>🤖 Model Weights:</h5><ul style='color: #e2e8f0; line-height: 1.8;'>"
        for link in models:
            html += f'<li><a href="{link}" target="_blank" style="color: #60a5fa; text-decoration: none;">{link}</a></li>'
        html += "</ul>"
    else:
        html += "<p style='color: #94a3b8; font-style: italic; margin: 10px 0;'>No model weights found</p>"

    # Datasets
    datasets = links.get("datasets", [])
    if datasets:
        html += "<h5 style='color: #e2e8f0; margin-top: 15px;'>📊 Datasets:</h5><ul style='color: #e2e8f0; line-height: 1.8;'>"
        for link in datasets:
            html += f'<li><a href="{link}" target="_blank" style="color: #60a5fa; text-decoration: none;">{link}</a></li>'
        html += "</ul>"
    else:
        html += "<p style='color: #94a3b8; font-style: italic; margin: 10px 0;'>No datasets found</p>"

    # Demo links
    demos = links.get("demo_links", [])
    if demos:
        html += "<h5 style='color: #e2e8f0; margin-top: 15px;'>🎮 Demo Links:</h5><ul style='color: #e2e8f0; line-height: 1.8;'>"
        for link in demos:
            html += f'<li><a href="{link}" target="_blank" style="color: #60a5fa; text-decoration: none;">{link}</a></li>'
        html += "</ul>"
    else:
        html += "<p style='color: #94a3b8; font-style: italic; margin: 10px 0;'>No demo links found</p>"

    # Paper links
    paper_links = links.get("paper_links", [])
    if paper_links:
        html += "<h5 style='color: #e2e8f0; margin-top: 15px;'>📄 Paper Links:</h5><ul style='color: #e2e8f0; line-height: 1.8;'>"
        for link in paper_links:
            html += f'<li><a href="{link}" target="_blank" style="color: #60a5fa; text-decoration: none;">{link}</a></li>'
        html += "</ul>"
    else:
        html += "<p style='color: #94a3b8; font-style: italic; margin: 10px 0;'>No paper links found</p>"

    # Repository information
    if repositories:
        html += "<h4 style='color: #60a5fa; margin-top: 20px;'>📦 Cloned Repositories:</h4>"
        for repo in repositories:
            repo_url = repo.get('url', 'Unknown')
            repo_status = repo.get('status', 'unknown')
            clone_path = repo.get('clone_path', 'N/A')
            has_code = repo.get('has_code', False)
            languages = repo.get('languages', [])
            claude_init = repo.get('claude_init', {})
            gradio_gen = repo.get('gradio_generation', {})

            status_color = '#4ade80' if repo_status == 'cloned' else '#f87171'

            # Claude init info
            claude_init_html = ""
            if claude_init:
                if claude_init.get('success'):
                    claude_md_path = claude_init.get('claude_md_path', 'N/A')
                    claude_init_html = f"""
                    <p style="color: #e2e8f0; margin: 4px 0;">
                        <strong>Claude Init:</strong>
                        <span style="color: #4ade80;">✅ CLAUDE.md created</span>
                    </p>
                    <p style="color: #e2e8f0; margin: 4px 0; font-size: 0.9em;">
                        <strong>CLAUDE.md:</strong> <code style="color: #cbd5e1;">{claude_md_path}</code>
                    </p>
                    """
                elif claude_init.get('attempted'):
                    error = claude_init.get('error', 'Unknown error')
                    claude_init_html = f"""
                    <p style="color: #e2e8f0; margin: 4px 0;">
                        <strong>Claude Init:</strong>
                        <span style="color: #f87171;">❌ Failed</span>
                    </p>
                    <p style="color: #94a3b8; margin: 4px 0; font-size: 0.85em; font-style: italic;">
                        Error: {error[:100]}{'...' if len(error) > 100 else ''}
                    </p>
                    """
                elif not claude_init.get('claude_available'):
                    claude_init_html = f"""
                    <p style="color: #e2e8f0; margin: 4px 0;">
                        <strong>Claude Init:</strong>
                        <span style="color: #94a3b8;">⏭️ Skipped (Claude CLI not available)</span>
                    </p>
                    """

            # Gradio generation info
            gradio_gen_html = ""
            if gradio_gen:
                if gradio_gen.get('success'):
                    app_path = gradio_gen.get('app_path', 'N/A')
                    readme_updated = gradio_gen.get('readme_updated', False)
                    gradio_gen_html = f"""
                    <p style="color: #e2e8f0; margin: 4px 0;">
                        <strong>Gradio App:</strong>
                        <span style="color: #4ade80;">✅ Generated</span>
                    </p>
                    <p style="color: #e2e8f0; margin: 4px 0; font-size: 0.9em;">
                        <strong>app.py:</strong> <code style="color: #cbd5e1;">{app_path}</code>
                    </p>
                    {f'<p style="color: #e2e8f0; margin: 4px 0; font-size: 0.9em;"><strong>README.md:</strong> <span style="color: #4ade80;">✓ HF YAML header added</span></p>' if readme_updated else ''}
                    """
                elif gradio_gen.get('attempted'):
                    error = gradio_gen.get('error', 'Unknown error')
                    gradio_gen_html = f"""
                    <p style="color: #e2e8f0; margin: 4px 0;">
                        <strong>Gradio App:</strong>
                        <span style="color: #f87171;">❌ Failed</span>
                    </p>
                    <p style="color: #94a3b8; margin: 4px 0; font-size: 0.85em; font-style: italic;">
                        Error: {error[:100]}{'...' if len(error) > 100 else ''}
                    </p>
                    """

            # Space upload info
            space_upload_html = ""
            space_upload = repo.get('space_upload', {})
            if space_upload:
                if space_upload.get('success'):
                    space_url = space_upload.get('space_url', '')
                    space_id = space_upload.get('space_id', 'N/A')
                    files_uploaded = space_upload.get('files_uploaded', 0)
                    total_size_mb = space_upload.get('total_size_mb', 0)
                    warnings = space_upload.get('warnings', [])

                    space_upload_html = f"""
                    <p style="color: #e2e8f0; margin: 4px 0;">
                        <strong>HuggingFace Space:</strong>
                        <span style="color: #4ade80;">✅ Uploaded</span>
                    </p>
                    <p style="color: #e2e8f0; margin: 4px 0; font-size: 0.9em;">
                        <strong>Space URL:</strong> <a href="{space_url}" target="_blank" style="color: #60a5fa; text-decoration: none; font-weight: bold;">{space_id}</a>
                    </p>
                    <p style="color: #94a3b8; margin: 4px 0; font-size: 0.85em;">
                        {files_uploaded} files • {total_size_mb}MB total
                    </p>
                    {f'<p style="color: #fb923c; margin: 4px 0; font-size: 0.85em;">⚠️ {len(warnings)} warnings during upload</p>' if warnings else ''}
                    """
                elif space_upload.get('error'):
                    error = space_upload.get('error', 'Unknown error')
                    space_upload_html = f"""
                    <p style="color: #e2e8f0; margin: 4px 0;">
                        <strong>HuggingFace Space:</strong>
                        <span style="color: #f87171;">❌ Upload Failed</span>
                    </p>
                    <p style="color: #94a3b8; margin: 4px 0; font-size: 0.85em; font-style: italic;">
                        Error: {error[:100]}{'...' if len(error) > 100 else ''}
                    </p>
                    """

            html += f"""
            <div style="border-left: 4px solid {status_color}; padding: 10px; margin: 10px 0; background-color: #334155;">
                <p style="color: #e2e8f0; margin: 4px 0;"><strong>URL:</strong> <a href="{repo_url}" target="_blank" style="color: #60a5fa;">{repo_url}</a></p>
                <p style="color: #e2e8f0; margin: 4px 0;"><strong>Status:</strong> <span style="color: {status_color};">{repo_status}</span></p>
                <p style="color: #e2e8f0; margin: 4px 0;"><strong>Has Code:</strong> {'✅ Yes' if has_code else '❌ No'}</p>
                {f'<p style="color: #e2e8f0; margin: 4px 0;"><strong>Languages:</strong> {", ".join(languages)}</p>' if languages else ''}
                {claude_init_html}
                {gradio_gen_html}
                {space_upload_html}
                {f'<p style="color: #e2e8f0; margin: 4px 0; font-size: 0.9em;"><strong>Path:</strong> <code style="color: #cbd5e1;">{clone_path}</code></p>' if clone_path != 'N/A' else ''}
            </div>
            """

    html += "</div>"

    return html
