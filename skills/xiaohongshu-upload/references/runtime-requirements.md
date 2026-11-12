# Runtime requirements

This skill assumes the current environment already has:

- `social-auto-upload` installed
- The `sau` command callable, or at least an equivalent way to call it
- Chromium installed for `patchright`

## Recommended installation

Run from the project root:

```bash
uv pip install -e .
```

## Install the patchright browser

Windows PowerShell:

```powershell
$env:PLAYWRIGHT_DOWNLOAD_HOST="https://npmmirror.com/mirrors/playwright"; patchright install chromium
```

Linux / macOS (bash / zsh):

```bash
PLAYWRIGHT_DOWNLOAD_HOST="https://npmmirror.com/mirrors/playwright" patchright install chromium
```

## Common ways to call it

### If `sau` is already on PATH

```bash
sau xiaohongshu --help
```

### If the virtual environment exists but is not activated

PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
sau xiaohongshu --help
```

### If you want to call the executable directly

PowerShell:

```powershell
.\.venv\Scripts\sau.exe xiaohongshu --help
```

### If you prefer uv

```bash
uv run sau xiaohongshu --help
```

## Headless and headed modes

- Use `--headless` for headless mode
- Use `--headed` for headed mode
- If the user explicitly asks for headless login, expect the CLI to give QR-code hints through console output or a temporary image path
- If a local QR code image was generated during login, the agent should show or send the image to the user to scan, and not just tell the user the image path
