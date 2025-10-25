"""
Gradio app generation using Claude CLI.
"""

import os
import subprocess
import asyncio
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime


async def run_claude_command_async(
    claude_path: str,
    prompt: str,
    repo_path: str,
    timeout: int = 600,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run a Claude CLI command asynchronously.

    Args:
        claude_path: Path to claude executable
        prompt: The prompt to send to Claude
        repo_path: Repository directory to run in
        timeout: Timeout in seconds (default: 10 minutes)
        session_id: Optional session ID to continue from

    Returns:
        Dictionary with command results
    """
    result = {
        'success': False,
        'output': None,
        'error': None,
        'session_id': session_id
    }

    try:
        # Build command
        cmd = [claude_path, '--print']

        # Add auto-approve if enabled
        auto_approve = os.environ.get('CLAUDE_AUTO_APPROVE', 'true').lower() in ('true', '1', 'yes')
        if auto_approve:
            cmd.append('--dangerously-skip-permissions')

        # Continue from session if provided
        if session_id:
            cmd.extend(['--resume', session_id])

        # Add the prompt
        cmd.append(prompt)

        # Prepare environment
        env = os.environ.copy()

        print(f"     Running: {' '.join(cmd[:3])} '{prompt[:50]}...'")

        # Run command asynchronously
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=repo_path,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Wait for completion with timeout
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )

            result['output'] = stdout.decode() if stdout else stderr.decode()

            if process.returncode == 0:
                result['success'] = True
            else:
                result['error'] = f"Command failed (exit code {process.returncode})"
                if stderr:
                    result['error'] += f": {stderr.decode()[:200]}"

        except asyncio.TimeoutError:
            process.kill()
            result['error'] = f"Command timed out after {timeout} seconds"

    except Exception as e:
        result['error'] = f"Exception running command: {str(e)}"

    return result


async def generate_gradio_app_async(
    repo_entry: Dict[str, Any],
    claude_path: str
) -> Dict[str, Any]:
    """
    Generate a Gradio app for a repository using Claude CLI (async).

    This function:
    1. Adds HuggingFace YAML header to README.md
    2. Generates a Gradio app (app.py) demonstrating the project

    Args:
        repo_entry: Repository entry from database
        claude_path: Path to claude executable

    Returns:
        Dictionary with generation results
    """
    result = {
        'attempted': False,
        'success': False,
        'app_created': False,
        'readme_updated': False,
        'app_path': None,
        'readme_path': None,
        'error': None,
        'session_id': None
    }

    clone_path = repo_entry.get('clone_path')
    if not clone_path or not os.path.isdir(clone_path):
        result['error'] = "Invalid clone path"
        return result

    repo_url = repo_entry.get('url', 'Unknown')
    languages = repo_entry.get('languages', [])

    print(f"\n  🎨 Generating Gradio app for: {repo_url}")
    print(f"     Languages: {', '.join(languages) if languages else 'Unknown'}")

    result['attempted'] = True

    try:
        # Step 1: Add HuggingFace YAML header to README.md
        print(f"  📝 Step 1: Adding HuggingFace YAML header to README.md...")

        readme_prompt = """Please add a HuggingFace Spaces YAML header to the README.md file.

Refer to the official documentation for the correct format:
https://huggingface.co/docs/hub/en/spaces-config-reference

Requirements:
1. Add the YAML frontmatter at the very beginning of README.md (before any content)
2. Use this structure:
   ---
   title: [descriptive title for this project]
   emoji: [single emoji that fits the project]
   colorFrom: [color from: red, yellow, green, blue, indigo, purple, pink, gray]
   colorTo: [another color for gradient]
   sdk: gradio
   sdk_version: 5.49.1
   app_file: app.py
   pinned: false
   short_description: [write a brief one-sentence description of what this project does]
   hardware: zerogpu
   ---

3. **Important Field Requirements:**
   - **short_description**: REQUIRED - Write a clear, one-sentence description of the project's purpose
   - This should be a complete sentence explaining what the project does (e.g., "A machine learning model for image classification" or "A tool for analyzing text sentiment")
   - Keep it concise but informative (max ~100 characters)
   - **hardware**: Set to "zerogpu" to enable free GPU access (NVIDIA H200, 70GB VRAM) on HuggingFace Spaces
   - This provides GPU acceleration for ML/AI projects using PyTorch, TensorFlow, etc.

5. If README.md exists, insert the YAML at the top and keep existing content
6. If README.md doesn't exist, create it with the YAML header and a brief project description
7. Choose appropriate title, emoji, and colors based on the project content

Please proceed with adding this header now."""

        readme_result = await run_claude_command_async(
            claude_path,
            readme_prompt,
            clone_path,
            timeout=300  # 5 minutes
        )

        if not readme_result['success']:
            result['error'] = f"Failed to update README.md: {readme_result['error']}"
            print(f"     ❌ {result['error']}")
            return result

        # Check if README.md was created/updated
        readme_path = os.path.join(clone_path, 'README.md')
        if os.path.isfile(readme_path):
            result['readme_updated'] = True
            result['readme_path'] = readme_path
            print(f"     ✅ README.md updated with HuggingFace header")
        else:
            print(f"     ⚠️  README.md not found after update")

        # Extract session ID if available (for continuing conversation)
        # Note: This would require parsing Claude's output or using session management
        # For now, we'll make separate calls

        # Step 2: Generate Gradio app
        print(f"  🎨 Step 2: Generating Gradio app (app.py)...")

        app_prompt = """Please create a Gradio app (app.py) that demonstrates this project.

## Requirements

1. Create a file called app.py in the root directory
2. The app should use Gradio (import gradio as gr)
3. **🚨 IMPORT ORDER**: If using GPU/CUDA (torch, tensorflow, etc.), ALWAYS import `spaces` FIRST before any CUDA packages
4. Create a simple, functional demo that showcases the main features of this project
5. If this is a machine learning project, create an interface for inference
6. If this is a utility/tool, create an interface for the main functionality
7. Include clear labels, descriptions, and examples
8. Make it beginner-friendly and easy to use
9. Add error handling for robustness
10. Use Gradio 5.x best practices (version 5.49.1)
11. Keep dependencies minimal (prefer built-in libraries when possible)

## Dependencies (requirements.txt)

IMPORTANT: Create or update the requirements.txt file with:
- **gradio==5.49.1** (REQUIRED - use exactly this version)
- **httpx version compatibility**: Gradio 5.49.1 depends on httpx<1.0 and >=0.24.1
  - If httpx is found in requirements.txt with any version, REPLACE it with: httpx>=0.24.1,<1.0
  - If httpx is specified as httpx>=1.0 or httpx==1.x.x, change it to: httpx>=0.24.1,<1.0
  - This prevents version conflicts that break Gradio
- Add other necessary dependencies for the project
- If using ZeroGPU, add: spaces
- Keep versions compatible with Python 3.10+
- Use specific versions when possible for reproducibility

**FlashAttention Detection:**
- Check if the project mentions "FlashAttention" or "flash-attention" anywhere (README, code, docs)
- If FlashAttention is mentioned, you MUST add the appropriate flash-attn wheel to requirements.txt
- Even if flash-attn is not in the original requirements.txt, add it if mentioned in documentation

**Selecting the Correct FlashAttention Wheel:**

**CRITICAL - PyTorch Version Pinning:**
The FlashAttention wheel is built for a specific PyTorch version and MUST match exactly.
You MUST pin PyTorch to the exact version using the `==` operator in requirements.txt.

**Version Selection Logic:**

1. Check the PyTorch version in the project's requirements.txt:

   a) **If pinned version (e.g., `torch==2.6.0`):**
      - Keep the pinned version
      - Select the matching flash-attn wheel below

   b) **If flexible version (e.g., `torch>=2.5`, `torch>2.4`, `torch~=2.5`):**
      - REPLACE it with the latest pinned version: `torch==2.8.0`
      - Use the PyTorch 2.8 flash-attn wheel
      - This prevents version mismatch between PyTorch and the prebuilt wheel

   c) **If no PyTorch specified or version unclear:**
      - Add `torch==2.8.0` to requirements.txt
      - Use the PyTorch 2.8 flash-attn wheel

2. **Available wheels** (ALWAYS use Python 3.10, CUDA 12, abiFALSE):

   - **PyTorch 2.8**: flash-attn @ https://github.com/Dao-AILab/flash-attention/releases/download/v2.8.3/flash_attn-2.8.3+cu12torch2.8cxx11abiFALSE-cp310-cp310-linux_x86_64.whl
   - **PyTorch 2.7**: flash-attn @ https://github.com/Dao-AILab/flash-attention/releases/download/v2.8.3/flash_attn-2.8.3+cu12torch2.7cxx11abiFALSE-cp310-cp310-linux_x86_64.whl
   - **PyTorch 2.6**: flash-attn @ https://github.com/Dao-AILab/flash-attention/releases/download/v2.8.3/flash_attn-2.8.3+cu12torch2.6cxx11abiFALSE-cp310-cp310-linux_x86_64.whl
   - **PyTorch 2.5**: flash-attn @ https://github.com/Dao-AILab/flash-attention/releases/download/v2.8.3/flash_attn-2.8.3+cu12torch2.5cxx11abiFALSE-cp310-cp310-linux_x86_64.whl
   - **PyTorch 2.4**: flash-attn @ https://github.com/Dao-AILab/flash-attention/releases/download/v2.8.3/flash_attn-2.8.3+cu12torch2.4cxx11abiFALSE-cp310-cp310-linux_x86_64.whl

3. **IMPORTANT**: Always use wheels with:
   - `cp310` (Python 3.10) - REQUIRED
   - `abiFALSE` - REQUIRED (never use abiTRUE)
   - `cu12` (CUDA 12) - REQUIRED
   - `linux_x86_64` platform

**Examples:**

Example 1 - Flexible version → Pin to latest:
```
# Original: torch>=2.5
# Updated requirements.txt:
torch==2.8.0
flash-attn @ https://github.com/Dao-AILab/flash-attention/releases/download/v2.8.3/flash_attn-2.8.3+cu12torch2.8cxx11abiFALSE-cp310-cp310-linux_x86_64.whl
```

Example 2 - Pinned version → Match exactly:
```
# Original: torch==2.6.0
# Updated requirements.txt (keep pinned version):
torch==2.6.0
flash-attn @ https://github.com/Dao-AILab/flash-attention/releases/download/v2.8.3/flash_attn-2.8.3+cu12torch2.6cxx11abiFALSE-cp310-cp310-linux_x86_64.whl
```

Example 3 - Complete requirements.txt with FlashAttention:
```
gradio==5.49.1
torch==2.8.0
transformers>=4.30.0
spaces
flash-attn @ https://github.com/Dao-AILab/flash-attention/releases/download/v2.8.3/flash_attn-2.8.3+cu12torch2.8cxx11abiFALSE-cp310-cp310-linux_x86_64.whl
```

**Why Version Pinning Matters:**
- FlashAttention wheels are compiled for specific PyTorch versions
- Using `torch>=2.5` with a torch2.6 wheel could install PyTorch 2.9, causing compatibility errors
- Pinning ensures: torch==2.6.0 + torch2.6 wheel = perfect match ✓

## ZeroGPU Integration

This Space is configured with ZeroGPU hardware (NVIDIA H200, 70GB VRAM) in the YAML header.
If this project uses PyTorch, TensorFlow, or other GPU libraries, use the @spaces.GPU decorator for GPU acceleration.

**Documentation**: https://huggingface.co/docs/hub/en/spaces-zerogpu

**🚨 CRITICAL IMPORT ORDER REQUIREMENT 🚨**

**The `spaces` package MUST be imported BEFORE any CUDA-related packages (torch, tensorflow, etc.).**

If CUDA is initialized before importing `spaces`, you will get this error:
```
RuntimeError: CUDA has been initialized before importing the `spaces` package.
Try importing `spaces` before any other CUDA-related package.
```

**Correct Import Order:**
```python
# ALWAYS import spaces FIRST, before torch/tensorflow/etc.
import spaces  # ← MUST BE FIRST

# Then import CUDA-related packages
import torch
from transformers import pipeline
import tensorflow as tf  # if using TensorFlow
# ... other imports
```

**Setup Pattern:**
```python
# Step 1: Import spaces FIRST (CRITICAL!)
import spaces

# Step 2: Then import other packages
import torch
from transformers import pipeline

# Load model outside decorated function (runs once on CPU)
model = pipeline("text-generation", model="gpt2")
model.to('cuda')  # Move to CUDA device

@spaces.GPU  # This decorator allocates GPU when function is called
def generate_text(prompt):
    # This runs on GPU (NVIDIA H200, 70GB VRAM)
    result = model(prompt, max_length=50)
    return result[0]['generated_text']

# Gradio interface
demo = gr.Interface(
    fn=generate_text,
    inputs=gr.Textbox(label="Prompt"),
    outputs=gr.Textbox(label="Generated Text")
)

demo.launch()
```

**Key Points:**
- **🚨 CRITICAL**: Import `spaces` FIRST, before torch/tensorflow/any CUDA packages (to avoid "CUDA has been initialized" error)
- Import `spaces` module: `import spaces`
- Decorate GPU functions with `@spaces.GPU`
- Load models BEFORE the decorated function (initialization happens on CPU)
- Move model to 'cuda' device
- Only GPU-intensive operations run inside decorated function
- Default GPU duration: 60 seconds (specify custom: `@spaces.GPU(duration=120)`)
- Requires Python 3.10.13 and PyTorch 2.1.0+
- Add `spaces` to requirements.txt if using GPU decorators

**When to Use @spaces.GPU Decorator:**
- ✅ For PyTorch/TensorFlow models (LLMs, diffusion, computer vision)
- ✅ For GPU-intensive computations
- ❌ Skip the decorator for CPU-only projects (ZeroGPU will still be available but unused)

## General App Structure

The app should:
- Be self-contained and runnable with: python app.py
- Use gr.Blocks() or gr.Interface() appropriately
- Include a title and description
- Have example inputs if applicable
- Be visually appealing with proper layout

If the project doesn't have obvious demo functionality (e.g., it's a library), create a simple demo that shows how to use the main API/functions with example inputs and outputs.

REMEMBER: Create/update requirements.txt with gradio==5.49.1 as the first dependency!

Please proceed with creating the Gradio app and requirements.txt now."""

        app_result = await run_claude_command_async(
            claude_path,
            app_prompt,
            clone_path,
            timeout=600  # 10 minutes
        )

        if not app_result['success']:
            result['error'] = f"Failed to generate app.py: {app_result['error']}"
            print(f"     ❌ {result['error']}")
            return result

        # Check if app.py was created
        app_path = os.path.join(clone_path, 'app.py')
        if os.path.isfile(app_path):
            result['app_created'] = True
            result['app_path'] = app_path
            file_size = os.path.getsize(app_path)
            print(f"     ✅ app.py created ({file_size} bytes)")

            # Show first few lines
            with open(app_path, 'r') as f:
                first_lines = ''.join(f.readlines()[:5])
            print(f"     Preview:\n{first_lines}")
        else:
            result['error'] = "app.py was not created"
            print(f"     ❌ {result['error']}")
            return result

        # Success if both files were created/updated
        if result['readme_updated'] and result['app_created']:
            result['success'] = True
            print(f"  ✅ Gradio app generation complete!")
        else:
            result['error'] = "Partial success - some files missing"

    except Exception as e:
        result['error'] = f"Exception during generation: {str(e)}"
        print(f"  ❌ {result['error']}")

    return result


def generate_gradio_app(repo_entry: Dict[str, Any], claude_path: str) -> Dict[str, Any]:
    """
    Synchronous wrapper for generate_gradio_app_async.

    Args:
        repo_entry: Repository entry from database
        claude_path: Path to claude executable

    Returns:
        Dictionary with generation results
    """
    # Run the async function in a new event loop
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(
        generate_gradio_app_async(repo_entry, claude_path)
    )


async def generate_gradio_apps_parallel(
    repo_entries: list,
    claude_path: str,
    max_concurrent: int = 3
) -> list:
    """
    Generate Gradio apps for multiple repositories in parallel.

    Args:
        repo_entries: List of repository entries
        claude_path: Path to claude executable
        max_concurrent: Maximum number of parallel generations

    Returns:
        List of results for each repository
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def generate_with_limit(repo_entry):
        async with semaphore:
            return await generate_gradio_app_async(repo_entry, claude_path)

    tasks = [generate_with_limit(repo) for repo in repo_entries]
    return await asyncio.gather(*tasks, return_exceptions=True)
