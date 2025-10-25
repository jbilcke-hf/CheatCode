"""
CheatCode - AI-powered paper analysis and repository extraction tool.

This is the main Gradio UI application.
"""

import gradio as gr
import os

from src.config import get_hf_token, get_auto_fetch_on_startup, get_auto_retry_failed
from src.papers import fetch_daily_papers
from src.processor import extract_and_save_links, process_manual_url, retry_failed_jobs
from src.database import load_database
from src.ui import format_papers_display, get_database_stats, view_paper_details


def refresh_papers(date_filter: str = None) -> str:
    """
    Refresh and display papers.

    Args:
        date_filter: Optional date filter in YYYY-MM-DD format.

    Returns:
        HTML formatted string of papers.
    """
    papers = fetch_daily_papers(date_filter if date_filter else None)
    return format_papers_display(papers)


def get_stats_display() -> str:
    """Get database statistics display."""
    database = load_database()
    return get_database_stats(database)


def view_paper(paper_id: str) -> str:
    """
    View details of a specific paper.

    Args:
        paper_id: ArXiv ID of the paper.

    Returns:
        HTML formatted paper details.
    """
    if not paper_id or not paper_id.strip():
        return "<p>Please enter a paper ID (e.g., 2307.09288)</p>"

    database = load_database()
    papers = database.get("papers", [])

    # Find the paper
    paper = None
    for p in papers:
        if p.get("paper_id") == paper_id.strip():
            paper = p
            break

    if not paper:
        return f"<p>❌ Paper {paper_id} not found in database.</p>"

    return view_paper_details(paper)


# Create Gradio interface with a clean, readable theme
with gr.Blocks(
    title="CheatCode - HuggingFace Papers",
    theme=gr.themes.Soft(
        primary_hue="orange",
        secondary_hue="blue",
        neutral_hue="slate",
    )
) as demo:
    gr.Markdown(
        """
        # 🎯 CheatCode
        ### Discover Daily Papers from Hugging Face

        Browse curated research papers from the Hugging Face community.
        """
    )

    with gr.Row():
        date_input = gr.Textbox(
            label="Date Filter (optional)",
            placeholder="YYYY-MM-DD (e.g., 2025-03-31)",
            value="",
            scale=3
        )
        refresh_btn = gr.Button("🔄 Refresh", variant="primary", scale=1)

    papers_output = gr.HTML(label="Papers")

    gr.Markdown("---")
    gr.Markdown(
        """
        ### 🔍 Extract Links with AI
        Extract code repositories, models, datasets, and demo links from paper pages using LLM analysis.
        Optionally clone GitHub repositories for code analysis.
        Results will be saved to `database.yaml`.
        """
    )

    with gr.Row():
        hf_token_input = gr.Textbox(
            label="HuggingFace Token (optional)",
            placeholder="hf_...",
            value=get_hf_token(),
            type="password",
            scale=2,
            info="Optional: Provide your HF token for higher rate limits. Get one at https://huggingface.co/settings/tokens or set HF_TOKEN in .env"
        )
        clone_repos_checkbox = gr.Checkbox(
            label="Clone GitHub Repositories",
            value=True,
            scale=1,
            info="Clone and analyze code repositories"
        )
        extract_btn = gr.Button("🤖 Extract & Analyze", variant="secondary", scale=1)

    extraction_status = gr.Textbox(label="Extraction Status", interactive=False, lines=5)

    gr.Markdown("---")
    gr.Markdown(
        """
        ### 🔗 Manual URL Entry
        Add a custom URL to be analyzed. Works with HuggingFace papers, spaces, models, or any web page.
        The AI will extract code repositories, models, datasets, and demo links from the page.
        """
    )

    with gr.Row():
        manual_url_input = gr.Textbox(
            label="Project URL",
            placeholder="https://huggingface.co/spaces/username/project or any URL",
            scale=3,
            info="Enter any HuggingFace or web URL to analyze"
        )
        manual_title_input = gr.Textbox(
            label="Title (optional)",
            placeholder="Auto-generated if empty",
            scale=2,
            info="Custom title for this entry"
        )

    with gr.Row():
        manual_hf_token_input = gr.Textbox(
            label="HuggingFace Token (optional)",
            placeholder="hf_...",
            value=get_hf_token(),
            type="password",
            scale=2,
            info="Optional: Provide your HF token for higher rate limits"
        )
        manual_clone_repos_checkbox = gr.Checkbox(
            label="Clone GitHub Repositories",
            value=True,
            scale=1,
            info="Clone and analyze code repositories"
        )
        manual_process_btn = gr.Button("🚀 Process URL", variant="primary", scale=1)

    manual_status = gr.Textbox(label="Processing Status", interactive=False, lines=5)

    gr.Markdown("---")
    gr.Markdown(
        """
        ### 📚 Database Viewer
        View cached papers and their extracted links from the database.
        """
    )

    with gr.Tabs():
        with gr.Tab("Statistics"):
            stats_btn = gr.Button("🔄 Refresh Stats", variant="primary")
            stats_output = gr.HTML(label="Database Statistics")

        with gr.Tab("Paper Details"):
            with gr.Row():
                paper_id_input = gr.Textbox(
                    label="Paper ID",
                    placeholder="e.g., 2307.09288",
                    scale=3
                )
                view_btn = gr.Button("🔍 View Paper", variant="primary", scale=1)
            paper_details_output = gr.HTML(label="Paper Details")

    # Conditionally load papers on startup based on environment variable
    # Database stats are always loaded as they're fast and don't hit external APIs
    if get_auto_fetch_on_startup():
        demo.load(fn=refresh_papers, outputs=papers_output)
    demo.load(fn=get_stats_display, outputs=stats_output)

    # Automatically retry failed jobs on startup if enabled
    if get_auto_retry_failed():
        print("\n" + "="*60)
        print("🚀 AUTO_RETRY_FAILED is enabled")
        print("   Running automatic retry on startup...")
        print("="*60)
        retry_failed_jobs()
        print("="*60 + "\n")

    # Refresh button action
    refresh_btn.click(
        fn=refresh_papers,
        inputs=date_input,
        outputs=papers_output
    )

    # Extract links button action
    extract_btn.click(
        fn=extract_and_save_links,
        inputs=[date_input, hf_token_input, clone_repos_checkbox],
        outputs=extraction_status
    )

    # Manual URL processing button action
    manual_process_btn.click(
        fn=process_manual_url,
        inputs=[manual_url_input, manual_title_input, manual_hf_token_input, manual_clone_repos_checkbox],
        outputs=manual_status
    )

    # Database stats refresh
    stats_btn.click(
        fn=get_stats_display,
        outputs=stats_output
    )

    # View paper details
    view_btn.click(
        fn=view_paper,
        inputs=paper_id_input,
        outputs=paper_details_output
    )


if __name__ == "__main__":
    demo.launch()
