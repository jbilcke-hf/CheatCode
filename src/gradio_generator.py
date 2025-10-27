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

## Step 1: Understand the Project (CRITICAL - DO THIS FIRST!)

Before creating any code, you MUST:

1. **Read the README.md thoroughly** (if it exists) to understand:
   - What this project does (purpose and functionality)
   - How to use it (quickstart, usage examples, API)
   - Installation requirements (dependencies, setup steps)
   - Any example code or demo instructions
   - Entry points or main functions to call

2. **Explore the codebase structure** to find:
   - Main application files (may be in root, src/, lib/, or other directories)
   - Example code (check examples/, demos/, scripts/, samples/, notebooks/ subdirectories)
   - Jupyter notebooks (.ipynb files) that demonstrate usage
   - Test files that show how to call the code
   - Library modules that expose APIs
   - Configuration files that indicate the project's purpose

3. **Identify the programming language(s)** and main frameworks used

4. **Locate actual runnable code**:
   - Code may NOT be in the root directory
   - Check subdirectories: examples/, scripts/, samples/, src/, lib/, notebooks/
   - Look for .py, .js, .ipynb, or other executable files
   - Even if the root looks empty, there may be rich examples in subdirectories

5. **Understand the intended use case**:
   - Is this a library (import and call functions)?
   - Is this a model (load weights and run inference)?
   - Is this a CLI tool (wrap commands in UI)?
   - Is this a collection of examples/tutorials (pick one to demonstrate)?

**🚨 IMPORTANT: If you don't find obvious application code in the root, explore deeper!**
- Many research repos put actual code in examples/ or scripts/
- README often contains the exact commands/code to run
- Don't conclude "there's nothing to demo" until you've checked all subdirectories

## Step 1b: Handle Model Downloads (CRITICAL FOR ML PROJECTS!)

**🚨 READ README SECTIONS ABOUT MODELS/CHECKPOINTS/WEIGHTS FIRST! 🚨**

Many ML/AI projects require downloading pretrained models, checkpoints, or data files before they can run. **You MUST check the README for:**

1. **Sections titled:**
   - "Checkpoint" / "Checkpoints"
   - "Model Weights" / "Pretrained Models"
   - "Download" / "Downloads"
   - "Installation" / "Setup"
   - "Getting Started" / "Quickstart"

2. **Look for instructions like:**
   - "Download the model from [HuggingFace URL]"
   - "Place the checkpoint in the `ckpt/` directory"
   - "Download pretrained LLM (e.g., Mistral-7B)"
   - "Required model weights: [list of files]"
   - Links to HuggingFace model repos
   - Links to specific model files (.pth, .safetensors, .bin, .ckpt, etc.)

**CRITICAL RULE: ALWAYS use `huggingface_hub` for model downloads**

**✅ CORRECT - Use huggingface_hub:**
```python
from huggingface_hub import snapshot_download, hf_hub_download
import os

# Example 1: Download entire model repository
MODEL_PATH = "./ckpt/model-name"
if not os.path.exists(MODEL_PATH):
    print(f"Downloading model to {MODEL_PATH}...")
    snapshot_download(
        repo_id="username/model-name",
        local_dir=MODEL_PATH,
        local_dir_use_symlinks=False
    )
    print("✓ Model downloaded")

# Example 2: Download specific file
CHECKPOINT_PATH = "./ckpt/checkpoint.pth"
if not os.path.exists(CHECKPOINT_PATH):
    print("Downloading checkpoint...")
    hf_hub_download(
        repo_id="username/repo-name",
        filename="checkpoint.pth",
        local_dir="./ckpt",
        local_dir_use_symlinks=False
    )
```

**❌ WRONG - Never download at runtime inside functions:**
```python
# DON'T DO THIS - downloads on EVERY function call!
def inference(text):
    model_path = snapshot_download(...)  # VERY SLOW!
    model = load_model(model_path)
    return model(text)
```

**Key Patterns:**

### Pattern 1: README says "Download from HuggingFace repo"
```python
# At module level (runs once at startup)
from huggingface_hub import snapshot_download
import os

MODEL_DIR = "./ckpt/model-name"  # Match README's directory structure!
if not os.path.exists(MODEL_DIR):
    print("Downloading model...")
    snapshot_download(
        repo_id="username/model-name",
        local_dir=MODEL_DIR,
        local_dir_use_symlinks=False
    )
```

### Pattern 2: README says "Download these specific files"
```python
from huggingface_hub import hf_hub_download
import os

os.makedirs("./ckpt", exist_ok=True)

# Download each required file
files = ["model.safetensors", "config.json", "tokenizer.json"]
for filename in files:
    if not os.path.exists(f"./ckpt/{filename}"):
        print(f"Downloading {filename}...")
        hf_hub_download(
            repo_id="username/model-name",
            filename=filename,
            local_dir="./ckpt",
            local_dir_use_symlinks=False
        )
```

### Pattern 3: README mentions pretrained LLM (e.g., Mistral, Llama)
```python
# Download the specific LLM mentioned
LLM_PATH = "./ckpt/Mistral-7B-Instruct-v0.3"
if not os.path.exists(LLM_PATH):
    print("Downloading Mistral LLM...")
    snapshot_download(
        repo_id="mistralai/Mistral-7B-Instruct-v0.3",
        local_dir=LLM_PATH,
        local_dir_use_symlinks=False
    )
```

### Pattern 4: README provides HuggingFace download links
```
Example link: https://huggingface.co/username/repo/resolve/main/checkpoint.pth
Extract: repo_id="username/repo", filename="checkpoint.pth"
```

**CRITICAL RULES:**
1. **Run downloads at MODULE LEVEL** (not inside functions) - they run once at Space startup
2. **Always check if files exist first** (for caching with `if not os.path.exists(...)`)
3. **Match README's directory structure exactly** (if README says "ckpt/", use "./ckpt/")
4. **Use `local_dir_use_symlinks=False`** to create actual files
5. **Handle optional models gracefully** (use try/except, continue without them if not found)
6. **Add `huggingface_hub` to requirements.txt**

**Example - Complete model setup:**
```python
print("=" * 60)
print("Setting up models (first run may take a few minutes)...")
print("=" * 60)

# Create directories from README
os.makedirs("./ckpt", exist_ok=True)
os.makedirs("./relation_graph", exist_ok=True)  # if README mentions it

# Download main checkpoint
try:
    if not os.path.exists("./ckpt/checkpoint.pth"):
        print("Downloading main checkpoint...")
        hf_hub_download(
            repo_id="username/project",
            filename="checkpoint.pth",
            local_dir="./ckpt",
            local_dir_use_symlinks=False
        )
        print("✓ Checkpoint downloaded")
except Exception as e:
    print(f"⚠ Could not download checkpoint: {e}")

# Download optional Mistral (if README mentions it)
MISTRAL_PATH = "./ckpt/Mistral-7B-Instruct-v0.3"
try:
    if not os.path.exists(MISTRAL_PATH):
        print("Downloading Mistral LLM...")
        snapshot_download(
            repo_id="mistralai/Mistral-7B-Instruct-v0.3",
            local_dir=MISTRAL_PATH,
            local_dir_use_symlinks=False
        )
        print("✓ Mistral downloaded")
    else:
        print("✓ Mistral already cached")
except Exception as e:
    print(f"⚠ Mistral not found - will skip advanced features")
    MISTRAL_PATH = None

print("✓ Setup complete!")
print("=" * 60)
```

**Why this matters:**
- ✅ Models download once at Space startup (cached for future runs)
- ✅ No runtime delays during inference
- ✅ Handles missing/optional models gracefully
- ✅ Follows README instructions exactly
- ✅ Works efficiently on HuggingFace Spaces infrastructure

**Reference documentation:** See `./docs/using-huggingface_hub-for-downloads.md` for more examples.

## Step 2: Requirements for app.py

1. Create a file called app.py in the root directory
2. The app should use Gradio (import gradio as gr)
3. **🚨 IMPORT ORDER**: If using GPU/CUDA (torch, tensorflow, etc.), ALWAYS import `spaces` FIRST before any CUDA packages
4. Create a simple, functional demo that showcases the main features of this project
5. **Base the demo on README instructions** - if README shows how to use the project, follow those exact steps in your Gradio app
6. If this is a machine learning project, create an interface for inference
7. If this is a library/utility, demonstrate the main API functions
8. If code is in subdirectories (examples/, scripts/), import from those paths
9. Include clear labels, descriptions, and examples
10. Make it beginner-friendly and easy to use
11. Add error handling for robustness
12. Use Gradio 5.x best practices (version 5.49.1)
13. Keep dependencies minimal (prefer built-in libraries when possible)

## Handling Different Project Types

### Research/ML Projects with Example Code
- If main code is in examples/ or scripts/, import from there:
  ```python
  import sys
  sys.path.append('./examples')
  from example_script import main_function
  ```
- Use the example code as a starting point for your Gradio interface

### Library Projects
- Read the library's main API from src/ or lib/
- Create a simple demo that calls the main functions
- Show inputs → processing → outputs

### Model/Weights Projects
- If project is for loading pretrained models:
  - Find the model loading code (often in examples/ or README)
  - Create inference function
  - Wrap in Gradio interface with appropriate inputs (text, image, etc.)

### Notebooks/Tutorials
- If project consists mainly of Jupyter notebooks:
  - Extract the key functionality from a notebook
  - Convert it to a Python function
  - Wrap in Gradio interface

### Projects with No Obvious Entry Point
- Check README for "Usage", "Quickstart", "Getting Started" sections
- Look for example commands or code snippets
- Implement those exact steps in your Gradio app
- If truly nothing is runnable, create a simple showcase/documentation viewer

## Dependencies (requirements.txt)

**🚨 CRITICAL: File must be named "requirements.txt" (plural) - NOT "requirement.txt" (singular)**

IMPORTANT: Create or update the requirements.txt file with:

**CRITICAL - Gradio Version Pinning:**
- **gradio==5.49.1** (REQUIRED - use exactly this version)
- **gradio-client==1.13.3** (REQUIRED - exact version needed for gradio 5.49.1 compatibility)
  - **NEVER** use gradio_client (underscore) - always use gradio-client (hyphen)
  - If you see gradio_client or gradio-client with any other version, REMOVE it
  - Gradio 5.49.1 specifically requires gradio-client==1.13.3 - other versions will fail

**Other Gradio Dependencies:**
- **httpx version compatibility**: Gradio 5.49.1 depends on httpx<1.0 and >=0.24.1
  - If httpx is found in requirements.txt with any version, REPLACE it with: httpx>=0.24.1,<1.0
  - If httpx is specified as httpx>=1.0 or httpx==1.x.x, change it to: httpx>=0.24.1,<1.0
  - This prevents version conflicts that break Gradio

- **ruff version compatibility**: Gradio 5.49.1 depends on ruff>=0.9.3
  - If ruff is found in requirements.txt with any version LOWER than 0.9.3, REPLACE it with: ruff>=0.9.3
  - If ruff is specified as ruff==0.7.4 or any version <0.9.3, change it to: ruff>=0.9.3
  - Examples of WRONG versions: ruff==0.7.4, ruff>=0.7.0, ruff~=0.8.0
  - Correct version: ruff>=0.9.3
  - This prevents version conflicts that break Gradio

- **huggingface-hub version compatibility**: Gradio 5.49.1 depends on huggingface-hub>=0.33.5 and <2.0
  - If huggingface-hub is found with version <0.33.5, REPLACE with: huggingface-hub==0.36.0
  - Examples of WRONG versions: huggingface-hub==0.27.1, huggingface-hub>=0.20.0, huggingface-hub==0.30.0
  - Correct version: huggingface-hub==0.36.0 (or any version >=0.33.5 and <2.0)
  - Note: Package name uses hyphen, but import uses underscore: `from huggingface_hub import ...`
  - This prevents conflicts with gradio, datasets, diffusers, and evaluate

**Project Dependencies:**
- **huggingface-hub==0.36.0** (REQUIRED if project needs to download models/weights from HuggingFace)
  - Note: Use hyphen (huggingface-hub), not underscore (huggingface_hub)
  - Gradio 5.49.1 requires huggingface-hub>=0.33.5, we recommend pinning to 0.36.0
  - If you see older version like huggingface-hub==0.27.1 or <0.33.5, REPLACE with: huggingface-hub==0.36.0
  - This prevents version conflicts with gradio, datasets, diffusers, and evaluate

- **sentencepiece==0.2.1** (REQUIRED if using sentence-transformers - always add this together)
  - If you see `sentence-transformers` in requirements, ALWAYS add `sentencepiece==0.2.1`
  - sentence-transformers needs sentencepiece for tokenization
  - This prevents "No module named 'sentencepiece'" errors
- Add other necessary dependencies for the project
- If using ZeroGPU, add: spaces
- Keep versions compatible with Python 3.10+
- Use specific versions when possible for reproducibility

**Example requirements.txt structure:**
```
gradio==5.49.1
gradio-client==1.13.3
httpx>=0.24.1,<1.0
ruff>=0.9.3
huggingface-hub==0.36.0
spaces
[other project dependencies...]
```

**Example with sentence-transformers:**
```
gradio==5.49.1
gradio-client==1.13.3
httpx>=0.24.1,<1.0
ruff>=0.9.3
huggingface-hub==0.36.0
sentence-transformers>=2.0.0
sentencepiece==0.2.1
spaces
[other dependencies...]
```

**When to include specific dependencies:**
- ✅ **huggingface-hub**: If README mentions downloading models/checkpoints from HuggingFace
- ✅ **sentencepiece**: If using sentence-transformers (ALWAYS include together)
- ✅ **spaces**: If using ZeroGPU or GPU decorators
- ❌ Can skip huggingface-hub if project has no model downloads

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

## FINAL CHECKLIST BEFORE CREATING FILES:

✅ **requirements.txt filename:**
   - MUST be named "requirements.txt" (plural) - NOT "requirement.txt" (singular)
   - This is CRITICAL - HuggingFace Spaces will not recognize "requirement.txt"

✅ **Required dependencies:**
   - gradio==5.49.1 (first dependency)
   - gradio-client==1.13.3 (exact version)
   - httpx>=0.24.1,<1.0 (version range)
   - ruff>=0.9.3 (if ruff is present, upgrade to this minimum version)

✅ **Conditional dependencies:**
   - If using sentence-transformers → ALWAYS add sentencepiece==0.2.1
   - If downloading models from HF → add huggingface-hub==0.36.0
   - If project has older huggingface-hub (<0.33.5) → upgrade to huggingface-hub==0.36.0
   - If using GPU/ZeroGPU → add spaces

✅ **Model downloads:**
   - Check README for checkpoint/model download instructions
   - Use huggingface_hub library (import uses underscore: `from huggingface_hub import ...`)
   - Package name uses hyphen: `huggingface-hub==0.36.0` in requirements.txt
   - Download at module level (not inside functions)
   - Match README directory structure (ckpt/, models/, etc.)

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
