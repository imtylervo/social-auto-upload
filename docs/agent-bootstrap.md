# Agent Bootstrap Prompt

This document is for users of agent clients such as `OpenClaw`, `Codex` and `Claude Code / cc`.

The goal is not to make the agent read the whole repository first. It is to get `social-auto-upload` installed in a state where it runs, can be verified, and can go on to execute tasks.

Platforms currently supported on the main line:

- `bilibili`
- `douyin`
- `kuaishou`
- `xiaohongshu`
- `dayu`

## What this document solves

The repository already has:

- Installation guide
- CLI documentation
- Platform skills

But those mostly cover how an agent should act once it is inside the repository.

This document covers what the user should say the first time they hand the repository to an agent client.

## Recommended usage

1. Give the whole repository to your agent client.
2. Send it the starting prompt below in full.
3. After the agent finishes the installation and CLI verification, give it tasks such as login, upload and scheduled publishing.

## Generic starting prompt

Copy the whole block below and send it to your agent:

```text
You are now working in a repository named `social-auto-upload`.

This is a multi-platform social media auto-publishing project. The main line currently supports:

- bilibili
- douyin
- kuaishou
- xiaohongshu
- dayu

Your first goal is not to read all the source code, and not to run the legacy examples first. It is to get the project installed in a state where it runs, can be verified, and can go on to execute tasks.

Follow these rules:

1. Treat the repository root as the current working directory by default.
2. Prefer `uv` for managing the Python environment. Do not fall back to the old `requirements.txt` by default.
3. Prefer the current main-line CLI: `sau`.
4. Prefer these documents:
   - `docs/install.md`
   - `docs/CLI.md`
   - `docs/update.md`
5. For platform-level operations, prefer these skills:
   - `skills/douyin-upload/`
   - `skills/kuaishou-upload/`
   - `skills/xiaohongshu-upload/`
   - `skills/bilibili-upload/`
   - `skills/dayu-upload/`
6. Do not use the legacy `examples/` and the old Web path by default, unless the main-line CLI is unusable.
7. If the login flow generates a QR code image, do not just return the image path. Show the image directly, or tell me clearly which local image file to open and scan.
8. For Bilibili login, do not force it through in a non-interactive environment. Instead, guide me to run it in a real local terminal.
9. After installation, verify these commands first:
   - `sau --help`
   - `sau douyin --help`
   - `sau kuaishou --help`
   - `sau xiaohongshu --help`
   - `sau bilibili --help`
10. When done, output clearly:
   - Which commands you actually ran
   - Which checks passed
   - Whether the project is now ready to continue with login/upload
   - What you recommend I do next

If you hit an error, do not skip it. State the error first, then say what you plan to do next.
```

## What to say after installation

Here are example tasks you can send to the agent next.

### Log in to a platform

```text
Please log in to my Xiaohongshu account in headed mode, with the account name `creator`.
```

```text
Please log in to my Douyin account in headless mode, with the account name `creator`.
```

### Check that the CLI is usable

```text
Please check whether the CLI entries for bilibili, douyin, kuaishou and xiaohongshu all work, and tell me which dependencies are missing.
```

### Do a real upload

```text
Please use the xiaohongshu CLI to upload an image post draft, using scheduled publishing, not immediate publishing.
```

```text
Please use the douyin CLI to upload a video. Use the current main line, not the legacy example.
```

## Tips for OpenClaw / Codex / Claude Code

### OpenClaw

- Paste the full starting prompt above directly
- If it can mount the repository as the working directory, mount the repository first, then send the prompt
- If it supports showing local files, have the agent show the login QR code image directly

### Codex

- Have it finish the bootstrap first, then send platform tasks
- Have it use `docs/install.md`, `docs/CLI.md` and `skills/` first
- Do not let it explore the whole repository freely at the start, or it may wander into legacy paths

### Claude Code / cc

- Make the repository the current workspace first
- Then send the full starting prompt
- After that, give tasks in the order "install -> verify -> log in -> upload"

## Why there are not four per-platform prompts

Because the project now has one unified CLI main line.

When a user first hands the repository to an agent, what matters more is that:

- The agent knows what the main entry is
- The agent knows which path to prefer
- The agent knows which paths are legacy
- The agent gives a clear acceptance result once installation is done

Once the work phase starts, let the agent choose, based on your actual goal, among:

- `bilibili`
- `douyin`
- `kuaishou`
- `xiaohongshu`

This is more stable than preparing four per-platform prompts, and easier to maintain.
