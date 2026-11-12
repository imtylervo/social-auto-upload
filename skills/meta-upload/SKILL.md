---
name: meta-upload
description: Use the sau CLI to log in to a Facebook Page, publish videos or image posts, set a schedule in Beijing time, look up the original post and delete it.
license: MIT-0
slug: social-auto-upload-meta-upload
displayName: Facebook Page publishing
version: 1.0.0
summary: Publish Facebook Page videos or image posts and manage schedules.
---

# Facebook Page publishing and deletion

This Skill calls the existing `sau facebook-page` and does not reimplement the browser logic. Instagram is currently on hold and will later use its own web-based approach; Business Suite is not used to link Instagram.

No proxy is configured by default, and the browser connects directly through the system network. If your network needs a proxy, pass `--proxy` explicitly or set `SAU_FACEBOOK_PAGE_PROXY`.

Log in first and save the account alias:

```powershell
sau facebook-page login --account creator
sau facebook-page check --account creator
sau facebook-page upload-note --account creator --page "我的 Page" --images images/1.jpg --title "标题" --note "正文" --result .local/page-result.json
sau facebook-page upload-video --account creator --page "我的 Page" --file videos/demo.mp4 --title "标题" --desc "正文" --schedule "2026-10-21 10:30" --result .local/reel-result.json
```

Both videos and image posts accept `--schedule "YYYY-MM-DD HH:MM"`. It uses Beijing time and must be at least 2 hours ahead, and the browser time zone must be Asia/Shanghai; leave it empty to submit immediately. Give the exact Page name in `--page`. `--tags` is a list of tags separated by English commas. Pass `--proxy ""` to ignore the environment variable and connect directly.

Results are saved to `.local/meta-results/` by default. Pass `--result` explicitly to avoid copying IDs by hand. `scheduled` means the platform confirmed the schedule and the original record was checked; `published` means the image post is published. For an immediate video submission, `processing` is returned once the creation response has no error and the completion dialog has appeared. It means the platform has accepted the video and is processing it, which does not yet prove it is publicly playable, and `content_id` may not be available yet. `submission_unknown` only means the evidence of submission is insufficient; look up the original record first and do not resend.

Look up or delete using the Page ID, Page name, content ID and body from the result:

```powershell
sau facebook-page verify --account creator --page "我的 Page" --page-id "Page-numeric-ID" --content-id "content-ID" --expected-text "original-post-text" --scheduled
sau facebook-page delete --account creator --page "我的 Page" --page-id "Page-numeric-ID" --content-id "content-ID" --expected-text "original-post-text" --scheduled --result .local/delete-result.json
```

`--scheduled` selects the scheduled list; deleting cancels the schedule and removes the post permanently, and returns `deleted`. Do not add it when managing a published post: the platform currently moves it to the trash and returns `trashed`, and deletes it automatically after 30 days. Early permanent deletion from the Page trash is not integrated. The ID of a scheduled post may change once it is actually published, so use the ID from the published list.

It only covers the recent list that has been loaded and does not guarantee finding every historical post. It does not delete when the same caption cannot identify the post uniquely, or when the Page or ID does not match. If a timeout or browser disconnect happens after deleting, check the original record first and do not delete again automatically; local materials are kept. For the full arguments, `sau facebook-page upload-video --help`, `upload-note --help`, `verify --help` and `delete --help` are authoritative.

## Example scripts

The files under `scripts/examples/` are examples to copy, not runtime dependencies. Before running them, check the current CLI's `--help` and replace the account, materials and body; these commands may create real posts.

- `meta_commands.ps1`: PowerShell
- `meta_commands.sh`: Bash
- `meta_cli_template.py`: Python subprocess
