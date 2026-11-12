---
name: dayu-upload
description: Use the social-auto-upload sau CLI to log in to Dayu, verify the account, publish videos and articles immediately or on a schedule, and look up the result of the original post. Articles accept HTML, Markdown or TXT files, and Markdown can use a theme. For environments where sau is installed; no need to read the uploader source first.
license: MIT-0
slug: social-auto-upload-dayu-upload
displayName: Dayu video and article publishing
version: 1.0.0
summary: Publish Dayu videos and articles, with scheduling and result verification.
---

# Dayu publishing

Use `sau dayu`; do not write a separate web publishing flow. Run `sau dayu --help` first; the exact arguments are defined by `upload-video --help`, `upload-article --help` and `verify --help`. In a repository environment, run from the project root; on Windows, if the command is not on PATH, use `.\.venv\Scripts\sau.exe`. Do not depend on a fixed test account or local machine paths.

## Account and input

1. For an existing account, run `sau dayu check --account <local-account-name>`. On first use or when the login has expired, run `sau dayu login --account <local-account-name> --expected-name "the Dayu account name specified by the user"` and have the user log in in the Chrome window that opens. The CLI binds the publishing identity and rejects the wrong account.
2. A video requires `--file`, `--title`, `--thumbnail`, `--category` and `--source`. The video must be at least 5 seconds long; the title is 5–60 characters (English letters count as half a character); the cover is at most 5 MB. Choose the category from the CLI's choices; do not guess categories that are not on the page.
3. An article requires `--title`, `--content-file` and `--source`. The title is 5–50 characters (English letters count as half, rounded up), and the body is a UTF-8 HTML/Markdown/TXT file of at most 20,000 characters. Keep long text in the file; do not put it on the command line. Images use local paths; relative paths start from the directory of the body file, and each image is at most 5 MB.
4. Choose the information source according to the actual content: `无需标注` (no label needed), `AI生成` (AI-generated), `虚构演绎` (fictional dramatization), `营销信息` (marketing information), `转载` (reprint), `个人观点` (personal opinion), `不适宜未成年人` (not suitable for minors). A reprint must also give `--source-url "https://original-url"`; other sources do not pass an original link.

## Commands

```powershell
sau dayu upload-video --account <local-account-name> --file "视频.mp4" --title "用户的视频标题" --category "科技" --source "无需标注" --thumbnail "封面.jpg"
sau dayu upload-article --account <local-account-name> --title "用户的文章标题" --content-file "文章.html" --source "无需标注" --cover-indices 1
```

The commands above actually publish. The materials, the identity and the intent to publish follow the authorization the user has already given. When the user only asks to check the preparation, add `--prepare-only`: it uploads the materials, fills in the form and saves a local screenshot, but does not publish and does not save a recoverable draft.

Markdown needs Node.js 22+ the first time, and `sau article setup` must be run. In the article command, pass `--content-file "文章.md" --theme modern`. The themes are `default/grace/simple/modern/plain`, and the default is `default`. Do not pass `--theme` for HTML/TXT. You can first render locally with `sau article render --content-file "文章.md" --theme modern --output "预览.html"`. Dayu uses a compatible layout that keeps text colors, backgrounds and approximate font sizes; rounded corners, exact fonts and spacing are not guaranteed to look the same. The server-side theme preview is checked before the final publish.

For videos, `--desc` and comma-separated `--tags` are optional. For articles, `--author`, and `--cover-indices 1` or `--cover-indices 1 3 2` are optional; the cover indices start at 1 in the order of the images in the body, and three covers must all be different. Articles have no category or tag fields. Portrait covers, the material library, document import, in-body video and saving drafts separately are not yet integrated; do not claim the command supports them.

## Scheduling

Add `--schedule "YYYY-MM-DD HH:MM"` only when the user asks for scheduled publishing; without it, the post is published immediately. The time is always interpreted as **Beijing time, Asia/Shanghai (UTC+8)**, and must be **between 2 hours and 7 days from now**, with the minutes a **multiple of 5**. Videos and articles use the same argument. Tell the user the time zone; if the exact time is missing or ambiguous, clarify it first, and do not round it or switch to immediate publishing on your own. Leave time for upload and processing; the range is checked again when the form is filled in.

Scheduling counts as successful once the platform confirms this post and the saved scheduled time. Do not wait for the time to arrive, for review or for public access, and do not describe "scheduled successfully" as "made public". Platform review may delay the actual public time.

## Results and interruptions

Keep the result file and the post ID that the command outputs. For immediate publishing, completion means the final business confirmation succeeded; being under review also counts as submitted successfully. For scheduled publishing, confirm the original post and the scheduled time.

When a submission times out or the result is unknown, **only look up the original post; do not run the upload or confirm publishing again**:

```powershell
sau dayu verify --account <local-account-name> --result "本次结果文件.json" --timeout 60
```

The result file helps check the title, identity, post and scheduled time. You can also look up by ID: `sau dayu verify --account <local-account-name> --type article --content-id "post-ID"` (use `--type video` for videos). If there is no ID to look up, tell the user the specific error and ask them to check the backend; do not guess that it failed and resend.

Add `--public` to the lookup command only when the user explicitly asks to check the public content or playback. To check the theme or the full body, use the original result file. A public check may wait for review or for the scheduled time to arrive, and is not part of the default completion condition for publishing.

## Example scripts

The files under `scripts/examples/` are examples to copy, not runtime dependencies. Before running them, check the current CLI's `--help` and replace the account, materials and body; these commands may create real posts.

- `dayu_commands.ps1`: PowerShell
- `dayu_commands.sh`: Bash
- `dayu_cli_template.py`: Python subprocess
