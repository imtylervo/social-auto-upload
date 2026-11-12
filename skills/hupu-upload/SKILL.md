---
name: hupu-upload
description: Use social-auto-upload's `sau hupu` to log in to Hupu and publish videos, with an optional cover. Use when the user wants to publish a video to Hupu or check the Hupu account state.
license: MIT-0
slug: social-auto-upload-hupu-upload
displayName: Hupu video publishing
version: 1.0.0
summary: Log in to Hupu and publish videos, with an optional cover.
---

# Hupu video publishing

Call the existing CLI; do not write a separate web upload flow. The account name is a local session alias.

```powershell
sau hupu login --account creator --headed
sau hupu check --account creator
sau hupu upload-video --account creator --file videos/demo.mp4 --title "标题" --desc "简介" --tags 虎扑,测试 --thumbnail covers/demo.png
```

Only videos are supported for now; image posts and scheduled publishing are not. The title is 4–40 characters. Login may require the user to complete QQ or phone-number verification in the browser; keep `--headed` when the page needs to be visible. The cover argument `--thumbnail` can be omitted.

Before publishing, check the account, video, title length, description, tags and cover. If the result is unclear, check the Hupu backend first and do not resend directly.
