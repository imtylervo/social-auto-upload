# Update Guide

This document has two parts:

- `For Humans`: for people who use the repository normally
- `For AI Agents`: for agents that can run commands and troubleshoot automatically

## For Humans

### 1. Pull the latest code

```bash
git pull
```

If you usually develop on branches, check which branch you are on first.

### 2. Update the local editable install

If the repository recently changed the CLI, entry scripts or dependency config, run this again:

```bash
uv pip install -e .
```

### 3. Update browser dependencies if needed

The current main line uses `patchright`.

Windows PowerShell:

```powershell
$env:PLAYWRIGHT_DOWNLOAD_HOST="https://npmmirror.com/mirrors/playwright"; patchright install chromium
```

Linux / macOS:

```bash
PLAYWRIGHT_DOWNLOAD_HOST="https://npmmirror.com/mirrors/playwright" patchright install chromium
```

### 4. Self-check after updating

At least check:

```bash
sau --help
sau douyin --help
sau kuaishou --help
sau xiaohongshu --help
sau bilibili --help
sau douyin check --account your_account
sau kuaishou check --account your_account
sau xiaohongshu check --account your_account
sau bilibili check --account your_account
```

If you use the skills, also look at:

- `skills/douyin-upload/SKILL.md`
- `skills/kuaishou-upload/SKILL.md`
- `skills/xiaohongshu-upload/SKILL.md`
- `skills/bilibili-upload/SKILL.md`
- `docs/CLI.md`

## For AI Agents

If you are an agent, after updating the repository do this minimal verification in order:

1. Pull the latest code:

```bash
git pull
```

2. Re-sync the local install:

```bash
uv pip install -e .
```

3. If a browser driver is needed, update the `patchright` Chromium

4. Verify the CLI again:

```bash
sau --help
sau douyin --help
sau kuaishou --help
sau xiaohongshu --help
sau bilibili --help
```

5. If the task involves the browser platforms, continue with:

```bash
sau douyin check --account test
sau kuaishou check --account test
sau xiaohongshu check --account test
sau bilibili check --account test
```

6. If the user depends on the skills, check that these paths still exist and their contracts have not changed:

- `skills/douyin-upload/SKILL.md`
- `skills/douyin-upload/references/cli-contract.md`
- `skills/douyin-upload/references/runtime-requirements.md`
- `skills/kuaishou-upload/SKILL.md`
- `skills/kuaishou-upload/references/cli-contract.md`
- `skills/kuaishou-upload/references/runtime-requirements.md`
- `skills/xiaohongshu-upload/SKILL.md`
- `skills/xiaohongshu-upload/references/cli-contract.md`
- `skills/xiaohongshu-upload/references/runtime-requirements.md`
- `skills/bilibili-upload/SKILL.md`
- `skills/bilibili-upload/references/cli-contract.md`
- `skills/bilibili-upload/references/runtime-requirements.md`

### Extra notes for agents

- Trust `pyproject.toml`. Do not treat `requirements.txt` as the source of truth for the main line
- The README is only an overview. For installation and updates, follow `docs/install.md` and `docs/update.md`
- Web-related content is a legacy path. See `docs/legacy-web.md`
- If the login flow outputs a local QR code image after the update, the agent should show or send the image to the user to scan, not just return the image path
- Bilibili commands check for and update `biliup` automatically when they run
- For Bilibili login, it is still best to have the user run it in a real local terminal. If the QR code is not fully displayed, the user can open `qrcode.png` and scan it
