---
name: facebook-upload
description: Use the sau CLI to log in to a Facebook personal profile, publish videos or image posts immediately, look up the original post, move it to the trash or delete it permanently.
license: MIT-0
slug: social-auto-upload-facebook-upload
displayName: Facebook personal profile publishing
version: 1.0.0
summary: Manage Facebook personal profile login, video and image post publishing, and post verification.
---

# Facebook personal profile publishing and deletion

This Skill calls the existing CLI. No proxy is configured by default, and the browser connects directly through the system network. If your network needs a proxy, pass `--proxy` explicitly or set `SAU_FACEBOOK_PROXY`. Pass `--proxy ""` to ignore the environment variable and connect directly.

```powershell
sau facebook login --account creator
sau facebook check --account creator
sau facebook upload-video --account creator --file videos/demo.mp4 --title "标题" --desc "正文" --tags 生活,分享
sau facebook upload-note --account creator --images images/1.jpg images/2.jpg --title "图文标题" --note "正文"
```

Complete the login in a visible Chrome window; the account is saved as `cookies/facebook_creator.json`. `check` verifies the personal profile login state and says nothing about Page permissions or post publishing results. The title, body and tags are merged into a single caption. Immediate publishing is supported for now; scheduling for personal profiles is not integrated. Pages use the separate `facebook-page` command.

After getting the original post link, manage the post:

```powershell
sau facebook verify --account creator --post-url "original-post-link" --owner-id "author-numeric-ID" --expected-text "original-post-text"
sau facebook delete --account creator --post-url "original-post-link" --owner-id "author-numeric-ID" --expected-text "original-post-text" --result .local/trash-result.json
sau facebook delete --account creator --post-url "original-post-link" --owner-id "author-numeric-ID" --expected-text "original-post-text" --from-trash --permanent --result .local/delete-result.json
```

Before deleting, check the logged-in user, the author, the original post ID and the body together. By default the post is moved to the trash, the platform deletes it after 30 days, and `trashed` is returned. Add `--permanent` to delete it permanently right away, and also add `--from-trash` if it is already in the trash. Permanent deletion cannot be undone.

`verify --from-trash` looks up the original record in the trash. `verify --deleted` only confirms that the ID is not in the trash and returns `absent_from_trash`; absence alone cannot prove that a permanent deletion happened in the past. For now it only searches recent posts within a limited scroll range; if the post is not found, or the same caption cannot identify it uniquely, it fails explicitly.

Treat publishing as confirmed only when the platform shows a success message for this submission. A timeout or browser disconnect after the click means the result is unknown: check the original post on the same account's personal profile or in the trash first, and do not upload again or delete again. Local materials are not deleted. For the full arguments, `sau facebook upload-video --help`, `upload-note --help`, `verify --help` and `delete --help` are authoritative.

## Example scripts

The files under `scripts/examples/` are examples to copy, not runtime dependencies. Before running them, check the current CLI's `--help` and replace the account, materials and body; these commands may create real posts.

- `facebook_commands.ps1`: PowerShell
- `facebook_commands.sh`: Bash
- `facebook_cli_template.py`: Python subprocess
