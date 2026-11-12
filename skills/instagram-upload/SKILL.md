---
name: instagram-upload
description: Use the sau CLI to log in on the standalone Instagram website, publish Reels, single images or carousels immediately, verify the original post and move it to Recently deleted.
license: MIT-0
slug: social-auto-upload-instagram-upload
displayName: Instagram video and image post publishing
version: 1.0.0
summary: Publish Instagram Reels, single images or carousels and verify the post.
---

# Instagram standalone web publishing

Call the existing CLI; do not implement browser upload yourself. It uses the project's Patchright Chrome and a standalone Instagram session, not the Business Suite linking entry. The browser is visible by default, and with no proxy configured it connects directly through the system network. If a proxy is needed, pass `--proxy` explicitly or set `SAU_INSTAGRAM_PROXY`. Pass `--proxy ""` to ignore the environment variable and connect directly.

```powershell
sau instagram login --account creator
sau instagram check --account creator
sau instagram upload-video --account creator --file videos/demo.mp4 --thumbnail covers/demo.png --title "标题" --desc "正文" --tags 生活,分享 --result .local/instagram-video.json
sau instagram upload-note --account creator --images images/1.jpg images/2.jpg --title "轮播标题" --note "正文" --result .local/instagram-images.json
```

For a video/Reel, `--thumbnail` can set a JPG/JPEG/PNG cover; if omitted, Instagram's default cover is used. After an image is specified, the main preview is checked to confirm that it really uses that image, and the submission stops if it does not. The cover is center-cropped to the current video frame, so leave a safe margin for important text near the image edges. Image post publishing does not accept this argument.

The account file is saved as `cookies/instagram_creator.json`. The password and verification are entered by the user in the project's browser. The upload flow automatically skips the first-time notification prompt and confirms the Reels introduction, and continues if there is no prompt. Login verification is still completed by the user; an unknown pop-up, or a failure to close a prompt, must be reported, and the upload must not be claimed as successful.

Videos support MP4/MOV and photos support JPG/JPEG/PNG/AVIF/HEIC/HEIF; actual handling depends on the platform. Multiple images are published as a carousel in the input order, and a single image and a two-image carousel have been tested. The title, body and tags together are at most 2200 characters. In the standalone web version for this account, the photo/Reels form and its advanced settings have no scheduling entry, so the CLI only supports immediate publishing for now; a scheduled task must not be converted into immediate publishing. Location, collaborators, AI labels, alt text, filters, cropping, sound and comment/like settings are not integrated and keep the page defaults.

A final result of `published` means the platform confirmed that the post was created, and it returns the post ID, the original post link and the media count. `processing` means the post was accepted and is still being processed, and `submission_unknown` means the result was not confirmed after submission; neither may be treated as published, and neither may be resent directly. Results are in `.local/instagram-results/` by default; use `--result` to fix the record path.

```powershell
sau instagram verify --account creator --post-url "original-post-link" --expected-text "exact-text-from-the-original-post" --result .local/instagram-verify.json
sau instagram delete --account creator --post-url "original-post-link" --expected-text "exact-text-from-the-original-post" --result .local/instagram-delete.json
```

If the result is unknown and there is no link, first find the original post on the same account's profile by materials, caption and publish time, copy the link and then run `verify`; not finding it does not prove failure, so do not upload again. The link supports `/p/<ID>/`, `/reel/<ID>/` and the form that includes the author name. Deletion is allowed only after checking the logged-in user, the author, the post ID and the body. Deletion returns `deleted` and the post goes to 最近删除 (Recently deleted); bulk deletion and early permanent clearing are out of scope. Local materials are not deleted. For `deletion_unknown`, first look up the original post and 最近删除 (Recently deleted), and do not submit the deletion again.

For the full arguments and capability limits, `sau instagram upload-video --help`, `upload-note --help`, `verify --help` and `delete --help` are authoritative. When something fails, analyze it from the error in the result file and the local evidence; do not commit account state, screenshots or page records to Git.

## Example scripts

The files under `scripts/examples/` are examples to copy, not runtime dependencies. Before running them, check the current CLI's `--help` and replace the account, materials and body; these commands may create real posts.

- `instagram_commands.ps1`: PowerShell
- `instagram_commands.sh`: Bash
- `instagram_cli_template.py`: Python subprocess
