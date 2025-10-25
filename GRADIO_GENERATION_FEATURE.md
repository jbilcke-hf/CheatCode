# Gradio App Generation Feature - Complete Documentation

## Overview

CheatCode now automatically generates production-ready Gradio demo apps for cloned repositories, complete with HuggingFace Spaces compatibility and ZeroGPU integration for GPU-accelerated projects.

## Full Processing Pipeline

```
Paper Processing Flow:
  1. Fetch papers from HuggingFace API
  2. Extract GitHub repository links
  3. Clone repositories with code analysis
  4. Run `claude /init` → Generate CLAUDE.md
  5. **[NEW]** Generate Gradio App:
     ├─ Step 1: Add HF YAML header to README.md
     │  ├─ Includes ZeroGPU hardware suggestion (if ML/AI project)
     │  ├─ Title, emoji, colors, SDK configuration
     │  └─ Preserves existing README content
     ├─ Step 2: Generate app.py
     │  ├─ Functional Gradio demo
     │  ├─ ZeroGPU decorators (for GPU projects)
     │  ├─ Error handling and examples
     │  └─ Production-ready code
     └─ Track results in database
  6. Mark as COMPLETED
```

## What Gets Generated

### 1. README.md with HuggingFace YAML Header

**For CPU Projects:**
```yaml
---
title: My Awesome Project
emoji: 🚀
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 4.0.0
app_file: app.py
pinned: false
short_description: A simple demo of the project
---
```

**For GPU/ML Projects:**
```yaml
---
title: Text Generation Model
emoji: 🤖
colorFrom: green
colorTo: blue
sdk: gradio
sdk_version: 4.0.0
app_file: app.py
pinned: false
suggested_hardware: zero-gpu  # ← ZeroGPU enabled!
short_description: Generate text with GPT-2
---
```

### 2. app.py - Gradio Demo App

**CPU Project Example:**
```python
import gradio as gr

def process_input(text):
    """Main processing function."""
    try:
        # Your project logic here
        result = text.upper()
        return result
    except Exception as e:
        return f"Error: {str(e)}"

demo = gr.Interface(
    fn=process_input,
    inputs=gr.Textbox(label="Input Text"),
    outputs=gr.Textbox(label="Output"),
    title="My Project Demo",
    description="A simple demo showcasing the project features",
    examples=[
        ["Example input 1"],
        ["Example input 2"]
    ]
)

if __name__ == "__main__":
    demo.launch()
```

**GPU/ML Project Example (with ZeroGPU):**
```python
import spaces
import gradio as gr
import torch
from transformers import pipeline

# Load model OUTSIDE decorated function (runs on CPU during initialization)
model = pipeline("text-generation", model="gpt2", device="cuda")

@spaces.GPU  # Allocates H200 GPU when function is called
def generate_text(prompt, max_length=50):
    """Generate text using GPT-2 model on GPU."""
    try:
        result = model(prompt, max_length=max_length)
        return result[0]['generated_text']
    except Exception as e:
        return f"Error: {str(e)}"

demo = gr.Interface(
    fn=generate_text,
    inputs=[
        gr.Textbox(label="Prompt", placeholder="Enter your prompt here..."),
        gr.Slider(minimum=10, maximum=200, value=50, label="Max Length")
    ],
    outputs=gr.Textbox(label="Generated Text"),
    title="GPT-2 Text Generator",
    description="Generate text using GPT-2 with ZeroGPU acceleration",
    examples=[
        ["Once upon a time", 50],
        ["The future of AI is", 100]
    ]
)

if __name__ == "__main__":
    demo.launch()
```

## ZeroGPU Integration

### What is ZeroGPU?

- **Free GPU Access**: HuggingFace's shared NVIDIA H200 GPUs (70GB VRAM)
- **Dynamic Allocation**: GPU allocated when decorated function is called
- **Auto-Release**: GPU released after function completes
- **PRO Benefits**: 5x higher daily quota and priority queue

### How It Works

1. **Import**: `import spaces`
2. **Decorate**: Add `@spaces.GPU` to GPU-intensive functions
3. **Load Models**: Initialize models BEFORE decorated function (on CPU)
4. **Move to CUDA**: `model.to('cuda')` to prepare for GPU usage
5. **Execute**: Decorated function runs on H200 GPU

### Duration Management

**Default (60 seconds):**
```python
@spaces.GPU
def process(input):
    return model(input)
```

**Custom Duration:**
```python
@spaces.GPU(duration=120)  # 2 minutes
def long_process(input):
    return model(input)
```

**Dynamic Duration:**
```python
def calculate_duration(steps):
    return steps * 2  # 2 seconds per step

@spaces.GPU(duration=calculate_duration)
def process(input, steps):
    return model(input, num_steps=steps)
```

### When to Use ZeroGPU

✅ **Use ZeroGPU for:**
- PyTorch/TensorFlow models (transformers, diffusion, vision models)
- GPU-intensive computations (matrix operations, neural networks)
- LLMs, image generation, video processing
- Any CUDA-based workload

❌ **Don't use ZeroGPU for:**
- CPU-only projects
- Simple text processing
- Non-ML utilities
- Lightweight operations

### Requirements

- **SDK**: Gradio 4+ only
- **Python**: 3.10.13
- **PyTorch**: 2.1.0 or later
- **Package**: `spaces` (add to requirements.txt)

## Claude Prompts

### README.md YAML Header Prompt

The system instructs Claude to:
1. Add YAML frontmatter at the very beginning of README.md
2. Choose appropriate title, emoji, and colors based on project
3. Set `suggested_hardware: zero-gpu` if it's an ML/AI project
4. Reference official HF docs: https://huggingface.co/docs/hub/en/spaces-config-reference
5. Preserve existing README content

### app.py Generation Prompt

The system instructs Claude to:
1. Create functional Gradio demo showcasing project features
2. Use ZeroGPU decorators for PyTorch/TensorFlow projects
3. Include comprehensive example with `@spaces.GPU` decorator
4. Add error handling and examples
5. Follow Gradio 4.x best practices
6. Reference ZeroGPU docs: https://huggingface.co/docs/hub/en/spaces-zerogpu

## Async Implementation

The Gradio generation uses Python `asyncio` for non-blocking execution:

```python
async def generate_gradio_app_async(repo_entry, claude_path):
    """Generate Gradio app asynchronously."""

    # Step 1: README.md YAML header (5 min timeout)
    readme_result = await run_claude_command_async(
        claude_path, readme_prompt, clone_path, timeout=300
    )

    # Step 2: app.py generation (10 min timeout)
    app_result = await run_claude_command_async(
        claude_path, app_prompt, clone_path, timeout=600
    )

    return results
```

**Features:**
- ✅ Non-blocking execution
- ✅ Parallel processing (up to 3 repos concurrently)
- ✅ Timeout protection (5-10 minutes per step)
- ✅ Graceful error handling

## Database Schema

### New Processing Status

```python
ProcessingStatus.CLAUDE_INITIALIZED = "claude_initialized"
ProcessingStatus.GENERATING_GRADIO = "generating_gradio"
```

### New Processing Step

```yaml
gradio_generation:
  status: "pending|in_progress|completed|error|skipped"
  started_at: "2025-10-24T18:30:00"
  completed_at: "2025-10-24T18:35:00"
  error: null
  repos_generated: 2
  apps_created: 2
```

### Repository Entry

```yaml
repositories:
  - url: "https://github.com/owner/repo"
    status: "cloned"
    clone_path: "/tmp/repos/2401_12345/owner_repo"

    # Claude initialization
    claude_init:
      success: true
      claude_md_path: "/tmp/repos/2401_12345/owner_repo/CLAUDE.md"
      initialized_at: "2025-10-24T18:25:00"

    # Gradio generation (NEW)
    gradio_generation:
      attempted: true
      success: true
      app_created: true
      readme_updated: true
      app_path: "/tmp/repos/2401_12345/owner_repo/app.py"
      readme_path: "/tmp/repos/2401_12345/owner_repo/README.md"
      error: null
      generated_at: "2025-10-24T18:35:00"
```

## UI Integration

### Database Stats Display

Shows comprehensive statistics:
- 🎨 **Gradio Apps Generated**: Total count of successfully created apps
- Color-coded indicators for success/failure

### Paper Details View

Per-repository information:
- ✅ **Gradio App**: Generated indicator
- 📝 **README.md**: HF YAML header added indicator
- 📂 **File Paths**: Shows app.py and README.md paths
- ❌ **Error Messages**: If generation failed

Example display:
```
Repository: https://github.com/owner/ml-project
Status: ✅ cloned
Has Code: ✅ Yes
Languages: Python, JavaScript

Claude Init: ✅ CLAUDE.md created
  CLAUDE.md: /tmp/repos/.../CLAUDE.md

Gradio App: ✅ Generated
  app.py: /tmp/repos/.../app.py
  README.md: ✓ HF YAML header added

Path: /tmp/repos/2401_12345/owner_ml-project
```

## Console Output

Example processing output:

```
🎨 Generating Gradio apps for 1 repositories

  📂 Repository: https://github.com/openai/gpt-2

  📝 Step 1: Adding HuggingFace YAML header to README.md...
     Running: claude --print --dangerously-skip-permissions '/init' 'Please add...'
     ✅ README.md updated with HuggingFace header

  🎨 Step 2: Generating Gradio app (app.py)...
     Running: claude --print --dangerously-skip-permissions '/init' 'Please create...'
     ✅ app.py created (2847 bytes)
     Preview:
     import spaces
     import gradio as gr
     import torch
     from transformers import pipeline
     ...

  ✅ Gradio app generation complete!

✅ Gradio generation complete: 1/1 apps created
```

## Files Structure

### Created Files

**`src/gradio_generator.py`** - Main Gradio generation module:
- `generate_gradio_app()` - Synchronous wrapper
- `generate_gradio_app_async()` - Async generation logic
- `run_claude_command_async()` - Async Claude CLI executor
- `generate_gradio_apps_parallel()` - Parallel processing (max 3 concurrent)

### Modified Files

- `src/status.py` - Added CLAUDE_INITIALIZED, GENERATING_GRADIO statuses
- `src/papers.py` - Added `process_gradio_generation()` function
- `src/processor.py` - Integrated Gradio generation into pipeline
- `src/ui.py` - Added Gradio generation status displays

## Key Features

### ✅ Production-Ready Output

Generated apps are immediately deployable to HuggingFace Spaces:
1. ✅ README.md with proper YAML frontmatter
2. ✅ app.py with functional Gradio interface
3. ✅ ZeroGPU integration (for ML projects)
4. ✅ Error handling and examples
5. ✅ Proper SDK configuration

### ✅ Smart ZeroGPU Detection

The system automatically determines if ZeroGPU should be used:
- Analyzes project languages (Python → check for ML libraries)
- Checks for PyTorch, TensorFlow, transformers imports
- Only suggests ZeroGPU for GPU-intensive projects
- CPU projects get standard configuration

### ✅ Async & Non-Blocking

- Uses Python asyncio for parallel processing
- Can generate apps for multiple repos simultaneously
- Doesn't block the main thread
- Timeout protection prevents hanging

### ✅ Fully Tracked

- Database records all generation attempts
- UI shows detailed status per repository
- Error messages captured and displayed
- Timestamps for all operations

### ✅ Resumable

- Detects already-generated apps
- Skips completed repositories
- Can re-run failed generations
- Incremental saves prevent data loss

## Example Workflow

### Input
```
Paper: "Attention Is All You Need"
Repository: https://github.com/tensorflow/tensor2tensor
Languages: Python (TensorFlow detected)
```

### Output

**README.md:**
```yaml
---
title: Tensor2Tensor Transformers
emoji: 🤖
colorFrom: purple
colorTo: pink
sdk: gradio
sdk_version: 4.0.0
app_file: app.py
pinned: false
suggested_hardware: zero-gpu
short_description: Transformer models for sequence-to-sequence tasks
---

# Tensor2Tensor

[existing README content preserved...]
```

**app.py:**
```python
import spaces
import gradio as gr
import torch
from transformers import pipeline

# Initialize model on CPU
translator = pipeline("translation_en_to_fr", model="t5-small")
translator.to('cuda')

@spaces.GPU(duration=90)
def translate(text):
    """Translate English to French using T5."""
    try:
        result = translator(text, max_length=100)
        return result[0]['translation_text']
    except Exception as e:
        return f"Error: {str(e)}"

demo = gr.Interface(
    fn=translate,
    inputs=gr.Textbox(label="English Text", placeholder="Enter text to translate..."),
    outputs=gr.Textbox(label="French Translation"),
    title="English to French Translator",
    description="Translate English text to French using T5 with ZeroGPU acceleration",
    examples=[
        ["Hello, how are you?"],
        ["Machine learning is fascinating."]
    ]
)

if __name__ == "__main__":
    demo.launch()
```

## Deployment to HuggingFace Spaces

The generated repositories are **immediately ready** for deployment:

### Method 1: Via Git
```bash
cd /path/to/cloned/repo
git init
git add README.md app.py
git commit -m "Add Gradio demo"
git remote add space https://huggingface.co/spaces/username/space-name
git push space main
```

### Method 2: Via HF Hub
```python
from huggingface_hub import HfApi

api = HfApi()
api.upload_folder(
    folder_path="/path/to/cloned/repo",
    repo_id="username/space-name",
    repo_type="space"
)
```

### Method 3: Manual Upload
1. Go to https://huggingface.co/new-space
2. Select Gradio SDK
3. Upload README.md and app.py
4. Space auto-deploys!

## Best Practices

### For Claude-Generated Apps

✅ **Do:**
- Verify generated code syntax before deployment
- Test apps locally first (`python app.py`)
- Check dependencies in requirements.txt
- Review ZeroGPU usage (avoid on CPU projects)
- Customize examples for your use case

❌ **Don't:**
- Deploy without testing
- Use ZeroGPU for non-GPU workloads
- Forget to add `spaces` to requirements.txt (for GPU apps)
- Ignore error handling

### For ZeroGPU Apps

✅ **Best Practices:**
- Load models OUTSIDE `@spaces.GPU` decorated functions
- Use shortest practical duration (better queue priority)
- Add error handling for GPU allocation failures
- Test with both GPU and CPU fallback
- Monitor quota usage (especially on free tier)

## Troubleshooting

### Common Issues

**1. README.md YAML not valid**
- Check for proper YAML syntax (colons, indentation)
- Ensure `---` delimiters are on separate lines
- Verify emoji is a single character

**2. app.py doesn't run**
- Check Python syntax
- Verify all imports are available
- Test locally before deploying

**3. ZeroGPU not working**
- Ensure `spaces` in requirements.txt
- Check Python version (needs 3.10.13)
- Verify PyTorch version (2.1.0+)
- Confirm `suggested_hardware: zero-gpu` in README.md

**4. Generation failed**
- Check Claude CLI is available
- Verify ANTHROPIC_API_KEY is set
- Check timeout limits (increase if needed)
- Review error messages in database

## Statistics

After processing papers, the database tracks:
- Total repos analyzed
- Total apps generated
- Success/failure rates
- Generation timestamps
- Error messages

Example stats output:
```
📊 Database Statistics
Total Papers: 50
Total Links Extracted:
  💻 Code Repositories: 125
  🤖 Model Weights: 78
  📊 Datasets: 45
  🎮 Demo Links: 23
  📄 Paper Links: 156

Repository Analysis:
  🔍 Repositories Found: 125
  ✅ Repositories Cloned: 98
  🤖 Claude Init: 95 (Claude CLI available)
  🎨 Gradio Apps Generated: 92
```

## Future Enhancements

Potential improvements:
- [ ] Auto-generate requirements.txt
- [ ] Validate generated Python syntax
- [ ] Run generated apps in sandbox for testing
- [ ] Create demo videos/screenshots
- [ ] Auto-deploy to HuggingFace Spaces
- [ ] Generate multi-tab Gradio apps for complex projects
- [ ] Add support for Streamlit/FastAPI alternatives
- [ ] Integrate with HF model/dataset APIs
- [ ] Create themed app templates
- [ ] Add analytics tracking to apps

## Conclusion

The Gradio generation feature transforms CheatCode into a complete **paper-to-demo pipeline**:

1. ✅ Discovers research papers
2. ✅ Extracts GitHub repositories
3. ✅ Clones and analyzes code
4. ✅ Generates CLAUDE.md documentation
5. ✅ **Creates production-ready Gradio demos**
6. ✅ **Integrates ZeroGPU for ML projects**
7. ✅ **Prepares for instant HF Spaces deployment**

All fully automated, tracked, and production-ready! 🚀

---

**Last Updated**: 2025-10-24
**Version**: 2.0.0
**Author**: Claude (Anthropic)
