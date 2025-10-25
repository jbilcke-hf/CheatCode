#!/usr/bin/env python3
"""
Quick test script to verify link extraction works correctly.
"""

import sys
sys.path.insert(0, '.')

from src.papers import fetch_paper_page, extract_links_from_html

# Test with the problematic paper
paper_id = "2411.01156"
paper_title = "Fish-Speech: Leveraging Large Language Models for Advanced Multilingual Text-to-Speech Synthesis"

print(f"Testing link extraction for paper {paper_id}...")
print(f"Title: {paper_title}\n")

# Fetch the page
print("Fetching paper page...")
html_content = fetch_paper_page(paper_id)

if not html_content:
    print("❌ Failed to fetch paper page")
    sys.exit(1)

print(f"✅ Fetched {len(html_content)} characters of HTML\n")

# Extract links
print("Extracting links...")
result = extract_links_from_html(paper_id, paper_title, html_content)

# Print results
print("\n" + "="*60)
print("EXTRACTION RESULTS")
print("="*60)

if "error" in result:
    print(f"❌ Error: {result['error']}")
    sys.exit(1)

links = result.get('links', {})
total_found = result.get('total_links_found', 0)
total_categorized = result.get('total_links_categorized', 0)

print(f"\nTotal URLs found: {total_found}")
print(f"Total URLs categorized: {total_categorized}")
print(f"\nCategorized links:")

for category, urls in links.items():
    if urls:
        print(f"\n{category.replace('_', ' ').title()} ({len(urls)}):")
        for url in urls:
            print(f"  • {url}")

# Verify we found the expected GitHub link
github_urls = links.get('code_repositories', [])
expected_url = "https://github.com/fishaudio/fish-speech"

if expected_url in github_urls:
    print(f"\n✅ SUCCESS! Found the expected GitHub URL: {expected_url}")
else:
    print(f"\n❌ FAILED! Did not find expected GitHub URL: {expected_url}")
    print(f"   Found {len(github_urls)} GitHub URLs instead:")
    for url in github_urls:
        print(f"   • {url}")
    sys.exit(1)

print("\n" + "="*60)
print("✅ All tests passed!")
print("="*60)
