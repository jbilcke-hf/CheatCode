#!/usr/bin/env python3
"""
Test script to verify Claude initialization works correctly.
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from claude_init import check_claude_available, initialize_repository

def test_claude_init():
    """Test Claude initialization on a test repository."""
    print("🧪 Testing Claude initialization...")
    print()

    # Check if Claude is available
    claude_path = check_claude_available()
    if not claude_path:
        print("❌ Claude CLI not available, cannot test initialization")
        return False

    print(f"✅ Claude CLI found at: {claude_path}")
    print()

    # Create a test repository entry
    test_repo = {
        'url': 'https://github.com/test/test',
        'status': 'cloned',
        'clone_path': '/tmp/test_claude_init',
        'has_code': True,
        'languages': ['Python']
    }

    print(f"📂 Testing initialization on: {test_repo['clone_path']}")
    print()

    # Run initialization
    result = initialize_repository(test_repo)

    print()
    print("📊 Initialization results:")
    print(f"   Attempted: {result['attempted']}")
    print(f"   Success: {result['success']}")
    print(f"   Claude available: {result['claude_available']}")
    print(f"   CLAUDE.md exists: {result['claude_md_exists']}")
    print(f"   CLAUDE.md path: {result['claude_md_path']}")
    if result['error']:
        print(f"   Error: {result['error']}")

    print()

    # Check if CLAUDE.md was created
    if result['success']:
        claude_md_path = result['claude_md_path']
        if claude_md_path and os.path.isfile(claude_md_path):
            file_size = os.path.getsize(claude_md_path)
            print(f"✅ CLAUDE.md successfully created ({file_size} bytes)")

            # Show first few lines
            with open(claude_md_path, 'r') as f:
                lines = f.readlines()[:10]
            print()
            print("   First 10 lines of CLAUDE.md:")
            for i, line in enumerate(lines, 1):
                print(f"   {i:2d}: {line.rstrip()}")

            return True
        else:
            print("❌ CLAUDE.md was reported as created but file doesn't exist")
            return False
    else:
        print("❌ Claude initialization failed")
        return False

if __name__ == "__main__":
    success = test_claude_init()
    sys.exit(0 if success else 1)
