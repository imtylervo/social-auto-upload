---
name: weibo-upload
description: Use social-auto-upload's `sau weibo` to log in to Weibo and publish videos, with an optional cover. Use when the user wants to publish a video to Weibo or check the Weibo account state.
license: MIT-0
slug: social-auto-upload-weibo-upload
displayName: Weibo video publishing
version: 1.0.0
summary: Log in to Weibo with sau and publish videos, with an optional cover.
---

# Weibo video publishing

Call the existing CLI; do not write a separate web upload flow. The account name is a local session alias.

```powershell
sau weibo login --account creator
sau weibo check --account creator
sau weibo upload-video --account creator --file videos/demo.mp4 --title "标题" --desc "简介" --tags 微博,测试 --thumbnail covers/demo.png
```

Only videos are supported for now; image posts and scheduled publishing are not. The title is at most 30 characters; the cover should preferably be under 5 MB. If a QR code appears during login, show the QR code image so the user can scan it. For the full arguments, `sau weibo upload-video --help` is authoritative.

Before publishing, check the account, video, title length, description, tags and cover. After submitting, report the result only from the actual platform feedback. On a timeout or unclear state, confirm the original post in the Weibo backend first and do not upload again.
