# Installation

This document has two parts:

- `For Humans`: for developers, creators and CLI users who use the repository directly
- `For AI Agents`: for agents such as OpenClaw, Codex and Claude Code

If you are a person who uses an agent client and want to give the agent a starting prompt first, instead of reading the execution details below, read this first:

- [Agent Bootstrap Prompt](./agent-bootstrap.md)

## For Humans

### 1. Clone the project

```bash
git clone https://github.com/dreammis/social-auto-upload.git
cd social-auto-upload
```

### 2. Create a virtual environment

`uv` is recommended:

Windows PowerShell:

```powershell
uv venv
.venv\Scripts\activate
```

Linux / macOS:

```bash
uv venv
source .venv/bin/activate
```

### 3. Install the main dependencies

The current main dependencies are declared in `pyproject.toml`. Run:

```bash
uv pip install -e .
```

After installation, the `sau` command is registered.

### 4. Install patchright Chromium

The current main line uses `patchright` to drive the browser.

Users in China should set a mirror first, then install Chromium.

Windows PowerShell:

```powershell
$env:PLAYWRIGHT_DOWNLOAD_HOST="https://npmmirror.com/mirrors/playwright"; patchright install chromium
```

Linux / macOS:

```bash
PLAYWRIGHT_DOWNLOAD_HOST="https://npmmirror.com/mirrors/playwright" patchright install chromium
```

### 5. Configure conf.py

Copy the example config:

```bash
cp conf.example.py conf.py
```

On Windows you can also copy and rename the file by hand.

These settings are usually also needed:

- `LOCAL_CHROME_PATH`
- `LOCAL_CHROME_HEADLESS`
- `DEBUG_MODE`

`XHS_SERVER` is only used by the old Xiaohongshu flow.

### 6. Check that the CLI works

```bash
sau --help
sau douyin --help
sau kuaishou --help
sau xiaohongshu --help
sau bilibili --help
```

If the command is not found, check these first:

- Whether the virtual environment is activated
- Whether `uv pip install -e .` has been run

### 7. Douyin example

```bash
sau douyin login --account <account_name>
sau douyin check --account <account_name>
sau douyin upload-video --account <account_name> --file videos/demo.mp4 --title "Sample title" --desc "Sample description"
Image post body, option 1:
$noteText = @"Image post body"@    
sau douyin upload-note --account <account_name> --images videos/demo1.png videos/demo2.png --title "Image post title" --note $noteText --tags 'tag1,tag2'
Image post body, option 2:
sau douyin upload-note --account <account_name> --images videos/demo1.png videos/demo2.png --title "Image post title" --notef 'path to the body text file' --tags 'tag1,tag2'
Add BGM (optional):
sau douyin upload-note --account <account_name> --images videos/demo1.png videos/demo2.png --title "Image post title" --note $noteText --tags 'tag1,tag2' --bgm 'music name'
``` 

Notes on the Douyin SMS verification code:

- If SMS two-step verification is triggered while publishing a video, the program first reads `verify_code.txt` in the project root
- If you are running in an interactive terminal yourself and `verify_code.txt` is not provided, the CLI prompts you to type the code in the terminal
- In an agent or automation bridge scenario, you can still provide the code by writing it to `verify_code.txt`
- After verification succeeds, the program deletes `verify_code.txt` automatically

If Douyin login gets stuck, get the cookie manually:

- The target server uses VNC
- Log in to the Douyin creator center in a browser: https://creator.douyin.com/
- Run `bash export_douyin_cookie.sh --account <account_name>`
- Check that the cookie works: `sau douyin check --account <account_name>`

### 8. Kuaishou example

```bash
sau kuaishou login --account <account_name>
sau kuaishou check --account <account_name>
sau kuaishou upload-video --account <account_name> --file videos/demo.mp4 --title "Sample title" --desc "Sample description"
sau kuaishou upload-note --account <account_name> --images videos/demo1.png videos/demo2.png videos/demo.png --title "Image post title" --note "Image post body"
```

### 9. Xiaohongshu example

```bash
sau xiaohongshu login --account <account_name>
sau xiaohongshu check --account <account_name>
sau xiaohongshu upload-video --account <account_name> --file videos/demo.mp4 --title "Sample title" --desc "Sample description"
sau xiaohongshu upload-note --account <account_name> --images videos/demo1.png videos/demo2.png videos/demo.png --title "Image post title" --note "Image post body"
```

### 10. Bilibili example

```bash
sau bilibili login --account <account_name>
sau bilibili check --account <account_name>
sau bilibili upload-video --account <account_name> --file videos/demo.mp4 --title "Sample title" --desc "Sample description" --tid 249
```

Additional notes:

- Names such as `creator` are only example values. What you actually pass is your own `account_name`
- One `account_name` maps to one account file. You can prepare several accounts and use them concurrently
- Shared metadata convention for the browser platforms:
- Videos use `title + desc + tags`
- Image posts use `title + note + tags`
- Users do not need to install `biliup` by hand
- The first time a Bilibili command runs, the program downloads `biliup` automatically
- Later runs check the upstream release and update automatically
- It is best for the user to run Bilibili login in a real local terminal. If the QR code is not fully displayed in the terminal, open `qrcode.png` in the current directory and scan it
- If GitHub Releases are slow to reach from China, you can use `https://gh-proxy.com/` or `https://gh-proxy.org/` to help reach the release URL when troubleshooting
- Example:
  - `https://gh-proxy.org/https://github.com/biliup/biliup/releases/download/v1.1.29/biliupR-v1.1.29-aarch64-linux.tar.xz`

## For AI Agents

If you are an agent that can run commands, handle things in this order:

1. Assume the repository root is the current working directory
2. Prefer `uv` for managing the environment. Do not fall back to the old `requirements.txt` by default
3. Prefer this install command:

```bash
uv pip install -e .
```

4. If a browser driver is needed, prefer:

Windows PowerShell:

```powershell
$env:PLAYWRIGHT_DOWNLOAD_HOST="https://npmmirror.com/mirrors/playwright"; patchright install chromium
```

Linux / macOS:

```bash
PLAYWRIGHT_DOWNLOAD_HOST="https://npmmirror.com/mirrors/playwright" patchright install chromium
```

5. After installation, check these first:

```bash
sau --help
sau douyin --help
sau kuaishou --help
sau xiaohongshu --help
sau bilibili --help
```

6. If the user wants to log in to Douyin or Kuaishou, check cookies, upload videos or upload image posts, use the CLI first:

```bash
sau douyin login
sau douyin check
sau douyin upload-video
sau douyin upload-note

sau kuaishou login
sau kuaishou check
sau kuaishou upload-video
sau kuaishou upload-note

sau xiaohongshu login
sau xiaohongshu check
sau xiaohongshu upload-video
sau xiaohongshu upload-note

sau bilibili login
sau bilibili check
sau bilibili upload-video
```

7. If the user is explicitly using the skill system, point them to:

- `skills/douyin-upload/SKILL.md`
- `skills/douyin-upload/references/cli-contract.md`
- `skills/kuaishou-upload/SKILL.md`
- `skills/kuaishou-upload/references/cli-contract.md`
- `skills/xiaohongshu-upload/SKILL.md`
- `skills/xiaohongshu-upload/references/cli-contract.md`
- `skills/bilibili-upload/SKILL.md`
- `skills/bilibili-upload/references/cli-contract.md`

### Extra notes for agents

- When the login flow generates a local QR code image, do not just send the image path to the user
- The QR code image is meant to be scanned by the user. The agent should show or send the local image to the user directly
- If the environment can view local images, use that to display the QR code. Give the path only as extra information
- Do not run Bilibili login for the user in a non-interactive environment
- The right approach is to ask the user to run `sau bilibili login --account <name>` in a local terminal. If the QR code is not fully displayed, tell the user to open `qrcode.png`
- `requirements.txt` is currently a legacy compatibility file, not the main install entry
- `uploader/` is the core implementation directory
- `sau_cli.py` is the current main CLI entry
- `docs/legacy-web.md` describes the legacy Web version and is not guaranteed to work now
- Bilibili may download `biliup` automatically on first run
