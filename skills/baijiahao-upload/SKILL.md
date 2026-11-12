---
name: baijiahao-upload
description: Use social-auto-upload's `sau baijiahao` to log in to Baijiahao, check the account and publish videos. Use when the user wants to publish a video to Baijiahao or verify the Baijiahao login state.
license: MIT-0
slug: social-auto-upload-baijiahao-upload
displayName: Baijiahao video publishing
version: 1.0.0
summary: Log in to Baijiahao and publish videos, with cover and collection support.
---

# Baijiahao video publishing

Call the existing CLI; do not write a separate upload flow. The account name is a local session alias. Before publishing, check `sau baijiahao upload-video --help`.

```powershell
sau baijiahao login --account creator
sau baijiahao check --account creator
sau baijiahao upload-video --account creator --file videos/demo.mp4 --title "标题" --desc "简介" --tags 百家号,测试
```

Only videos are supported for now; image posts and scheduled publishing are not. Optional `--thumbnail` sets the cover and `--collection` sets an existing collection. Complete the Baidu account login and save the session first; when a QR code appears during login, show the QR code image to the user.

Before publishing, check the account, materials, title, copy and tags. Only evidence for this submission from the command and the platform counts as success. On a timeout or unclear state, check the backend first and do not resend directly.
