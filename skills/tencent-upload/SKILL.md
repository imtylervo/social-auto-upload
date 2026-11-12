---
name: tencent-upload
description: Use social-auto-upload's `sau tencent` to log in to WeChat Channels, publish or schedule videos, and save drafts. Use when the user wants to publish a video to WeChat Channels or check the Channels account state.
license: MIT-0
slug: social-auto-upload-tencent-upload
displayName: WeChat Channels publishing
version: 1.0.0
summary: Log in to WeChat Channels and publish, schedule or save video drafts.
---

# WeChat Channels publishing

Call the existing `sau tencent` CLI; do not write a separate web upload flow. Check `sau tencent --help` first. The account name is a local session alias.

```powershell
sau tencent login --account creator
sau tencent check --account creator
sau tencent upload-video --account creator --file videos/demo.mp4 --title "标题" --desc "简介" --tags 视频号,测试
```

WeChat Channels supports video publishing only. Optional arguments include `--schedule "YYYY-MM-DD HH:MM"`, `--draft`, `--collection`, `--short-title`, `--category`, `--thumbnail-landscape` and `--thumbnail-portrait`. `--thumbnail` is a compatibility argument for the portrait cover. The collection must already exist.

Login and upload depend on the browser session. If login produces a QR code, show the QR code image directly so the user can scan it; use `--headed` when the page needs manual operation. Use scheduling only when the user gives an explicit time. `--draft` only saves a draft and does not mean the video was published.

Before publishing, confirm the target account, video, title, description, tags, and whether the intent is immediate publishing, scheduling or a draft. Confirm the result only from the CLI output and the platform page; do not treat a command that started successfully as a successful publish. For the full arguments, `sau tencent upload-video --help` is authoritative.
