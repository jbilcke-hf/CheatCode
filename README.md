# CheatCode

A code sniping bot for Hugging Face.
It detects AI research paper with code and create a Gradio demo Space for them. Based on Claude Code (feel free to port it to other coding assistant).

## Alternative names

Paper2Gradio, AutoVibe, PerpetualCode, CodeSniper, CodeSnipingBot

## Examples

Those examples where generated in one go:

- GraspAnyRegion: https://huggingface.co/papers/2510.18876
- RAPO: https://huggingface.co/papers/2510.20206
- AutoPage: https://huggingface.co/papers/2510.19600

## Counter examples

Those examples need an improvement to CheatCode (a feedback loop to fix the bugs):

- Need feedback loop: https://huggingface.co/papers/2411.01156

## Installation

> **Important: Python Version Requirement**
> This project requires **Python 3.8 - 3.13**. Python 3.14+ is **not yet supported** due to PyO3/pydantic-core compatibility issues.
>
> If you encounter build errors with `pydantic-core`, you're likely using Python 3.14+. Please use Python 3.13 or earlier.

1. Clone the repository or navigate to the project directory

2. Create a virtual environment with Python 3.13 or earlier:
```bash
# Verify your Python version first
python3 --version  # Should be 3.8-3.13, NOT 3.14+

# Create virtual environment with Python 3.13 (recommended)
python3.13 -m venv venv

# Or use your default python3 if it's 3.8-3.13
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install the required dependencies:
```bash
pip install -r requirements.txt
```

4. Configure your HuggingFace API token:
```bash
cp .env.example .env
# Edit .env and add your HuggingFace token
```

You can get a token at https://huggingface.co/settings/tokens

## Usage

Run the application:
```bash
python app.py
```

The Gradio interface will launch in your default web browser.


## Requirements

- Python 3.8 - 3.13 (Python 3.14+ not yet supported due to pydantic-core compatibility)
- gradio >= 4.0.0
- huggingface_hub >= 0.20.0
- pyyaml >= 6.0
- python-dotenv >= 1.0.0

## Environment Variables

The app supports configuration via environment variables:

- **HF_TOKEN**: Your HuggingFace API token (optional, but recommended for higher rate limits)

### Local Development
Create a `.env` file in the project root:
```bash
cp .env.example .env
```

Then edit `.env` and add your token:
```
HF_TOKEN=hf_your_token_here
```

### Production
Set environment variables directly in your system or deployment platform:
```bash
export HF_TOKEN=hf_your_token_here
```

The app will automatically use the token from either the .env file or system environment variables.

## Database Caching

The app uses `database.yaml` as an intelligent caching system:

- **Automatic Skip**: Papers already in the database are automatically skipped
- **Incremental Saving**: Each paper is saved immediately after extraction (prevents data loss on crashes)
- **Cache Statistics**: View total papers and links in the database via the Statistics tab
- **Paper Lookup**: Search for specific papers by ArXiv ID to view their extracted links
- **Console Logging**: Detailed logs show which papers are being cached vs. processed

## Troubleshooting

### Claude CLI Initialization Issues

If you encounter errors with `claude /init` when analyzing repositories:

#### "Credit balance is too low"

This error occurs when your Anthropic account doesn't have sufficient API credits.

**Solutions:**
1. **Add credits**: Visit https://console.anthropic.com/ to add credits to your account
2. **Disable initialization**: Set `CLAUDE_INIT_ENABLED=false` in your `.env` file to skip automatic initialization
   ```bash
   # In your .env file
   CLAUDE_INIT_ENABLED=false
   ```

#### "Authentication failed"

If you see authentication errors:

1. Check that `ANTHROPIC_API_KEY` is set correctly in your `.env` file
2. Verify your API key is valid at https://console.anthropic.com/
3. Make sure the key starts with `sk-ant-`

#### Claude CLI Not Found

If Claude CLI is not detected:

1. Install Claude CLI following the instructions at https://docs.claude.com/
2. Set `CLAUDE_CLI_PATH` in your `.env` file if installed in a custom location
3. Or set `CLAUDE_AUTO_INSTALL=true` to attempt automatic installation

### Python Version Issues

**Error**: `pydantic-core` build fails or compatibility errors

**Solution**: Use Python 3.8-3.13 (not 3.14+)
```bash
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Rate Limiting

If you encounter rate limits with HuggingFace API:

1. Add a HuggingFace token to your `.env` file (get one at https://huggingface.co/settings/tokens)
2. Wait a few minutes before retrying
3. The app automatically skips already-processed papers, so you can safely retry

