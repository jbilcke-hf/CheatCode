#!/usr/bin/env python3
"""
Test script to verify Claude CLI detection works correctly.
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from claude_init import check_claude_available

def test_claude_detection():
    """Test if Claude CLI can be detected."""
    print("🔍 Testing Claude CLI detection...")
    print()

    # Check environment variable
    env_path = os.environ.get('CLAUDE_CLI_PATH')
    if env_path:
        print(f"   CLAUDE_CLI_PATH environment variable: {env_path}")
    else:
        print(f"   CLAUDE_CLI_PATH environment variable: Not set")

    print()

    # Try to find Claude
    claude_path = check_claude_available()

    print()
    if claude_path:
        print(f"✅ Claude CLI found at: {claude_path}")
        print()
        print("   Claude initialization will be enabled for cloned repositories.")
        return True
    else:
        print("❌ Claude CLI not found")
        print()
        print("   Claude initialization will be skipped.")
        print("   To enable it, install Claude CLI:")
        print("   • npm install -g @anthropic-ai/claude-code")
        print("   • brew install --cask claude-code")
        print("   • curl -fsSL https://claude.ai/install.sh | bash")
        print()
        print("   Or set CLAUDE_CLI_PATH to point to your Claude executable.")
        return False

if __name__ == "__main__":
    success = test_claude_detection()
    sys.exit(0 if success else 1)
