---
name: kuaishou-upload
description: Use this skill when an agent needs to log in to Kuaishou, validate cookies, upload videos or publish image posts through the installed `sau` CLI. It applies to environments where `social-auto-upload` is installed and the `sau` command can be called. Prefer this skill for a stable, command-driven Kuaishou workflow instead of reading the uploader source code first.
license: MIT-0
slug: social-auto-upload-kuaishou-upload
displayName: Kuaishou video and image post publishing
version: 1.0.0
summary: Log in to Kuaishou with sau and publish videos or image posts.
---

# Kuaishou upload Skill

Use `sau` as the primary interface.

Do not assume the current environment can read the repository source.
Do not start by reading `uploader/`.
Fall back to the troubleshooting notes only when the command is unavailable or the CLI run fails.

## Overview

| Function | Command entry | Notes |
| --- | --- | --- |
| Kuaishou login | `sau kuaishou login --account <name>` | Create or refresh the cookie for the given account |
| Cookie check | `sau kuaishou check --account <name>` | Check whether the cookie for the given account is valid |
| Video upload | `sau kuaishou upload-video ...` | Upload and publish a Kuaishou video |
| Image post upload | `sau kuaishou upload-note ...` | Upload and publish a Kuaishou image post |

Metadata conventions:

- Videos use `title + desc + tags`
- Image posts use `title + note + tags`

## Default workflow

1. First confirm the runtime prerequisites in `references/runtime-requirements.md`.
2. Then confirm the command contract in `references/cli-contract.md`.
3. Run the matching `sau kuaishou ...` command.
4. If the command fails, read `references/troubleshooting.md`.

## Supported actions

- Log in to Kuaishou with `sau kuaishou login --account <name>`
- Check whether the cookie is valid with `sau kuaishou check --account <name>`
- Upload a Kuaishou video with `sau kuaishou upload-video ...`
- Upload a Kuaishou image post with `sau kuaishou upload-note ...`

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
