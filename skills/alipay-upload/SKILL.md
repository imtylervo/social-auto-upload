---
name: alipay-upload
description: Use social-auto-upload's `sau alipay` to log in to an Alipay Life Account and publish videos. Use when the user wants to publish a video to an Alipay Life Account or check the creator account state.
license: MIT-0
slug: social-auto-upload-alipay-upload
displayName: Alipay Life Account video publishing
version: 1.0.0
summary: Log in to an Alipay Life Account and publish videos, with cover and collection support.
---

# Alipay Life Account video publishing

Call the existing `sau alipay` CLI. Before first use, the user needs to log in to the Alipay content creation backend and confirm that the account has been granted Life Account content creation permission.

```powershell
sau alipay login --account creator
sau alipay check --account creator
sau alipay upload-video --account creator --file videos/demo.mp4 --title "标题" --desc "简介" --tags 生活号,测试
```

Only videos are supported for now; image posts and scheduled publishing are not. Optional `--thumbnail` sets the cover and `--collection` sets an existing collection. The account name is a local session alias; when login needs a QR scan, show the QR code image to the user.

Before publishing, check the account, materials, title, description and tags. Do not over-read a CLI result of "submitted" as approved or publicly visible. If the result is uncertain, check the Alipay backend first and do not retry blindly.
