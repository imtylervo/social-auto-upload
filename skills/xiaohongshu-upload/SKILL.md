---
name: xiaohongshu-upload
description: Use this skill when an agent needs to log in to Xiaohongshu, validate cookies, upload videos or publish image posts through the installed `sau` CLI. It applies to environments where `social-auto-upload` is installed and the `sau` command can be called. Prefer this skill for a stable, command-driven Xiaohongshu workflow instead of reading the uploader source code first.
license: MIT-0
slug: social-auto-upload-xiaohongshu-upload
displayName: Xiaohongshu video and image post publishing
version: 1.0.0
summary: Log in to Xiaohongshu with sau and publish videos or image posts.
---

# Xiaohongshu upload Skill

Use `sau` as the primary interface.

Do not assume the current environment can read the repository source.
Do not start by reading `uploader/`.
Fall back to the troubleshooting notes only when the command is unavailable or the CLI run fails.

## Overview

| Function | Command entry | Notes |
| --- | --- | --- |
| Xiaohongshu login | `sau xiaohongshu login --account <name>` | Create or refresh the cookie for the given account |
| Cookie check | `sau xiaohongshu check --account <name>` | Check whether the cookie for the given account is valid |
| Video upload | `sau xiaohongshu upload-video ...` | Upload and publish a Xiaohongshu video |
| Image post upload | `sau xiaohongshu upload-note ...` | Upload and publish a Xiaohongshu image post |

Metadata conventions:

- Videos use `title + desc + tags`
- Image posts use `title + note + tags`

## Default workflow

1. First confirm the runtime prerequisites in `references/runtime-requirements.md`.
2. Then confirm the command contract in `references/cli-contract.md`.
3. Run the matching `sau xiaohongshu ...` command.
4. If the command fails, read `references/troubleshooting.md`.

## Supported actions

- Log in to Xiaohongshu with `sau xiaohongshu login --account <name>`
- Check whether the cookie is valid with `sau xiaohongshu check --account <name>`
- Upload a Xiaohongshu video with `sau xiaohongshu upload-video ...`
- Upload a Xiaohongshu image post with `sau xiaohongshu upload-note ...`

## Choosing a command

- Use `login` when the user needs a new cookie or the existing cookie has expired
- Use `check` when the user only needs to confirm the cookie state
- Use `upload-video` when the user wants to publish a video
- Use `upload-note` when the user wants to publish an image post

## Checks before running

- First confirm that `sau` can be called in the current shell
- If `sau` is not available, follow the fallback in `references/runtime-requirements.md`
- When the user explicitly asks for headless or headed mode, pass `--headless` or `--headed` explicitly
- Use `--schedule` only when the user explicitly asks for scheduled publishing
- If the login flow produces a local QR code image, do not just tell the user the image path
- The QR code image itself is meant for the user to scan, so show or send the local image to the user directly

## References

- Runtime prerequisites: `references/runtime-requirements.md`
- CLI contract: `references/cli-contract.md`
- Troubleshooting: `references/troubleshooting.md`
