---
name: xueqiu-upload
description: Use the social-auto-upload sau CLI to log in to and verify a Xueqiu account, publish HTML, Markdown or TXT long articles that keep the source's images between paragraphs, native text structure and a separate cover, and look up the original post to confirm the result. For the Xueqiu creator platform; scheduling and video are not supported.
license: MIT-0
slug: social-auto-upload-xueqiu-upload
displayName: Xueqiu long article publishing
version: 1.0.0
summary: Publish Xueqiu HTML, Markdown or TXT long articles and verify the result.
---

# Xueqiu long articles

Use the repository's existing `sau xueqiu`; do not write a separate web upload implementation. Check `sau xueqiu upload-article --help` first. On Windows, if it is not on PATH, use `.\.venv\Scripts\sau.exe` from the repository root.

## Account and input

- For an existing account, run `sau xueqiu check --account <alias>`. On first use, run `sau xueqiu login --account <alias> --expected-name "nickname specified by the user"` and log in in the Chrome window that opens. The program saves the session and binds the real user ID; do not put account passwords in commands or source code. Logging in with Codex's built-in browser does not generate a CLI session file automatically.
- You must provide a non-empty single-line `--title`, a UTF-8 HTML/Markdown/TXT `--content-file`, and a `--declaration` that matches how the article was actually created. Choose the declaration `不添加创作声明` (no creation declaration) or `本文包含AI生成内容` (this article contains AI-generated content); do not guess on the user's behalf.
- `--visibility` is `公开` (public) or `私人` (private), and defaults to public. Body images are written at their positions in the source through HTML `img` or Markdown images, and relative paths are based on the source directory; there is no `--images` argument that appends images to the end. Use `--cover` for a separate cover, which uses the platform's default cropping. Images accept local GIF/JPEG/PNG and do not accept remote URLs or data URLs.
- All heading levels become the platform's subheading on Xueqiu; paragraphs, bold, italic and links are kept, and lists are converted to paragraphs with numbers or bullets. Custom CSS is not guaranteed to be kept. Unverified structures such as tables and code blocks raise an error before the remote draft is created. Markdown needs `sau article setup` the first time; see the usage guide for details.

## Drafts and publishing

```powershell
sau xueqiu upload-article --account <alias> --title "用户标题" --content-file "文章.md" --cover "封面.png" --visibility 私人 --declaration "本文包含AI生成内容"
```

The command actually publishes by default. To only check the draft and preview, add `--prepare-only` explicitly. Xueqiu saves remote drafts automatically, so repeated runs may create several drafts. If the editor already has content, the command refuses to overwrite it. Omit `--cover` when no separate cover is needed.

Prefer a Markdown source. For images between paragraphs, use Markdown image syntax with a path relative to the source, for example `![image caption](images/chart.png)`. Run `sau article setup` first on first use.

The official CLI has been tested with native structure, two different images between paragraphs, a separate cover, private publishing and backend lookup of the original post. Stay within the scope the user gave; authorization to develop or log in does not by itself authorize publishing test content.

There is no scheduling argument: no scheduling feature was observed in this account's full long-article form. Word files, custom cropping, video and stock/topic/@ linked objects are not yet supported; do not pass off plain text as linked objects.

## Judging the result and handling interruptions

Keep the result JSON path and screenshots that the command outputs. `prepared` only means preparation is complete; `published` means the platform finally accepted it and the identity, title, sharing scope and body checks passed. `management_verified: true` means the backend lookup by the original ID also passed. A private post shows 仅自己可见 (Only visible to me).

If the record is `submission_unknown`, run `sau xueqiu verify --account <alias> --result "本次结果文件.json"`. It does a read-only lookup by the saved original post ID and re-checks the backend body and images against the source. Keep the source, images and paths used at publish time; changed content raises an error. A successful result from an older version that lacks the source path only checks the post identity and sharing scope. If there is no ID, go to 内容管理 (Content Management) and check by title, account and time. Until this is settled, do not rerun the upload or click publish again, to avoid duplicate posts.

A visible Chrome is used by default, and `--headless` is an explicit option; headless access from this machine was once blocked by the platform. For network timeouts, 403 or an identity mismatch, keep the specific error and do not conclude from it that the cookie has expired. `--debug` saves a screenshot on failure.

## Example scripts

The files under `scripts/examples/` are examples to copy, not runtime dependencies. Before running them, check the current CLI's `--help` and replace the account, materials and body; these commands may create real posts.

- `xueqiu_commands.ps1`: PowerShell
- `xueqiu_commands.sh`: Bash
- `xueqiu_cli_template.py`: Python subprocess
