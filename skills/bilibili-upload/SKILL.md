---
name: bilibili-upload
description: Use this skill when an agent needs to log in to Bilibili, validate the account or upload videos through the installed `sau` CLI. Prefer `sau bilibili ...`; the program prepares `biliup` automatically, so the user does not need to install it manually.
license: MIT-0
slug: social-auto-upload-bilibili-upload
displayName: Bilibili video publishing
version: 1.0.0
summary: Log in to Bilibili and publish videos, with category selection.
---

# Bilibili upload Skill

Use `sau` as the primary interface.

Do not start by asking the user to find `biliup` or download a release manually.
The program checks, downloads and updates `biliup` automatically at runtime.

## Overview

| Function | Command entry | Notes |
| --- | --- | --- |
| Login | `sau bilibili login --account <name>` | The user must run it in a real local terminal; it creates or refreshes the login information |
| Check | `sau bilibili check --account <name>` | Check whether the given account is currently valid |
| Video upload | `sau bilibili upload-video ...` | Upload one Bilibili video |

## Default workflow

1. First confirm `references/runtime-requirements.md`
2. Then confirm `references/cli-contract.md`
3. Run the matching `sau bilibili ...` command
4. If the command fails, read `references/troubleshooting.md`

## Choosing a command

- If the user has no login information, first have the user run `login` in a local terminal
- If the user only wants to confirm the account state, use `check`
- If the user wants to publish a video, use `upload-video`

## Checks before running

- First confirm that `sau` can run in the current environment
- If `sau` is not on PATH, you can use `sau_cli.py` in the repository
- Do not ask the user to download `biliup` manually
- The first time a Bilibili command runs, the program may go online to prepare `biliup` automatically
- For an agent, do not force `sau bilibili login` to run in a non-interactive environment
- The right approach is to have the user run `sau bilibili login --account <name>` in a local terminal
- If the QR code in the terminal is displayed incompletely, remind the user to open `qrcode.png` in the current directory and scan it

## References

- Runtime prerequisites: `references/runtime-requirements.md`
- CLI contract: `references/cli-contract.md`
- Troubleshooting: `references/troubleshooting.md`
