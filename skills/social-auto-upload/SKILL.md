---
name: social-auto-upload
description: Entry point for social-auto-upload; picks the right publishing flow by platform and content type. Use when the user wants to publish videos, articles or image posts to a platform this repository supports, or to distribute content to several specified platforms.
license: MIT-0
slug: social-auto-upload
displayName: social-auto-upload multi-platform publishing entry point
version: 1.0.0
summary: Choose the publishing flow by the platform and content type the user specifies.
---

# social-auto-upload entry point

First confirm the platform, content type, account alias and publishing method the user specified. If the user has not specified a platform, ask; do not pick a target platform yourself.

## Choose the platform entry

| Platform | Dedicated Skill | CLI platform name |
| --- | --- | --- |
| Douyin | `douyin-upload` | `douyin` |
| Bilibili | `bilibili-upload` | `bilibili` |
| Xiaohongshu | `xiaohongshu-upload` | `xiaohongshu` |
| Kuaishou | `kuaishou-upload` | `kuaishou` |
| WeChat Channels | `tencent-upload` | `tencent` |
| Baijiahao | `baijiahao-upload` | `baijiahao` |
| Dayu | `dayu-upload` | `dayu` |
| Alipay Life Account | `alipay-upload` | `alipay` |
| Weibo | `weibo-upload` | `weibo` |
| Hupu | `hupu-upload` | `hupu` |
| TikTok | `tiktok-upload` | No `sau` command |
| Xueqiu | `xueqiu-upload` | `xueqiu` |
| YouTube | `youtube-upload` | `youtube` |
| Zhihu | `zhihu-upload` | `zhihu` |
| Facebook personal profile | `facebook-upload` | `facebook` |
| Facebook Page | `meta-upload` | `facebook-page` |
| Instagram | `instagram-upload` | `instagram` |

## Workflow

1. If the matching platform Skill is installed, read it first and follow it. When running from the repository, read `skills/<skill-name>/SKILL.md`.
2. If the repository is available, read the platform notes from `skills/<skill-name>/SKILL.md`; otherwise provide the matching install command first. Before running the CLI, use `sau <platform> --help` to confirm the current arguments. Do not guess arguments or claim that TikTok has a CLI.
3. Check the state of the target account first. If login has to be completed by the user on the platform page, hand it over to the user; do not ask for or store passwords.
4. Before publishing, check the files, title, copy, tags, visibility, publish time and target account. Publish only to the platforms the user explicitly named; even for the same content, check each platform's requirements one by one.
5. Report a post as published only when the command or the platform gives success evidence for this submission. On a timeout or an unknown result, check the original post first and do not blindly resend.

## Installation entry

Install the entry point from the public GitHub repository:

```bash
npx skills add dreammis/social-auto-upload --skill social-auto-upload
```

For a specific platform, replace `social-auto-upload` with the dedicated Skill name from the table. For the full platform capabilities and distribution status, see the README and the distribution documents in the GitHub source repository.
