# Skill Distribution and Publishing

## Directory layout

`skills/` is the source directory of the Skills. It contains one cross-platform entry point and one separate entry point per platform. The CLI platforms' Skills use the repository's `sau` command. TikTok has no CLI and uses the Chrome uploader already in this repository.

| Platform | Skill directory | CLI entry |
| --- | --- | --- |
| Cross-platform entry point | `social-auto-upload` | Routes to the entries below, based on the platform the user names |
| Douyin | `douyin-upload` | `sau douyin` |
| Bilibili | `bilibili-upload` | `sau bilibili` |
| Xiaohongshu | `xiaohongshu-upload` | `sau xiaohongshu` |
| Kuaishou | `kuaishou-upload` | `sau kuaishou` |
| WeChat Channels | `tencent-upload` | `sau tencent` |
| Baijiahao | `baijiahao-upload` | `sau baijiahao` |
| Dayu | `dayu-upload` | `sau dayu` |
| Alipay Life Account (支付宝生活号) | `alipay-upload` | `sau alipay` |
| Weibo | `weibo-upload` | `sau weibo` |
| Hupu | `hupu-upload` | `sau hupu` |
| TikTok | `tiktok-upload` | None; the repository's Chrome uploader |
| Xueqiu | `xueqiu-upload` | `sau xueqiu` |
| YouTube | `youtube-upload` | `sau youtube` |
| Zhihu | `zhihu-upload` | `sau zhihu` |
| Facebook personal profile | `facebook-upload` | `sau facebook` |
| Facebook Page | `meta-upload` | `sau facebook-page` |
| Instagram | `instagram-upload` | `sau instagram` |

## Distribution channels

The status below was checked on 2026-10-23. Automatic indexing sites may lag behind GitHub. Entries that are not confirmed are not marked as listed.

| Channel | How to list | Status and limits |
| --- | --- | --- |
| GitHub source repository | The public repository's `skills/` is the source; install by directory | Published to `main`. The current Skill update commit is [`7023053`](https://github.com/dreammis/social-auto-upload/commit/7023053) |
| GitHub Skills CLI | `gh skill publish skills --tag <version>` | Preview CLI. Release [`v1.0.0-skills.2`](https://github.com/dreammis/social-auto-upload/releases/tag/v1.0.0-skills.2) is published, and the repository has the `agent-skills` topic. Install command: `gh skill install dreammis/social-auto-upload` |
| skills.sh | Install directly from GitHub: `npx skills add dreammis/social-auto-upload --skill <skill-name>` | Indexed automatically from the GitHub source; there is no separate upload form. The [Douyin Skill page](https://www.skills.sh/dreammis/social-auto-upload/douyin-upload) is confirmed. For the other entries, check the site for their index status. Install counts come from the Skills CLI. Maintainers should not inflate install counts by installing it themselves |
| SkillsMP | Indexes `SKILL.md` from public GitHub repositories | No separate upload. On 2026-10-12 the creator page for this repository showed 4 Skills indexed, with source activity dated 2026-03-25. The index clearly lags behind the current repository, and listing of the other entries is not confirmed. See the [creator page](https://skillsmp.com/zh/creators/dreammis/social-auto-upload) |
| SkillHub.club | Push `SKILL.md` in a public GitHub repository to GitHub, and the site indexes it automatically | The official docs say GitHub automatic indexing is supported. The listing status of this repository is still to be verified. No need to upload files again. See the [site docs](https://www.skillhub.club/docs) |
| SkillHub.space | Upload on the web, or publish with `shsc publish` | Not submitted yet. It needs an account on that site, and the review status should be checked after publishing. See the [official quick start](https://docs.skillhub.space/docs/quick-start) |
| SkillHub.cn | Publish from the web, the CLI or an agent | The frontmatter needs `slug`, `displayName`, `version`, `summary` and `license`; this repository has them all. Not submitted yet. For individual publishing, the repository owner must register the account in person, complete Tencent Cloud face-recognition real-name verification and create an API token. The Windows CLI must go through WSL. See the [official publishing guide](https://skillhub.cn/install/skillhub.md) |
| iFlytek Astron SkillHub (`skill.xfyun.cn`) | Official CLI: `@astron-team/skillhub publish <path> --namespace <namespace>` | Public registry. It needs an API token and namespace for an account on that site, which are not configured yet. It is a different platform from `skillhub.cn` and `skillhub.space`; their CLIs and accounts cannot be mixed. See the [official CLI docs](https://github.com/iflytek/skillhub/blob/main/docs/skillhub/en/guide/cli.md) |
| SkillHub (`useskillhub.com`) | Apply for Publisher permission; pre-check against `skillhub.json`, save a draft, then submit a specific version for review | This is a registry platform with an API, call permissions and a runtime contract. The current Markdown Skills cannot be published as a complete service directly |
| ClawHub | Run `clawhub skill publish <path>` for each Skill directory | Local dry-runs for the 18 unique slugs passed. The CLI is not logged in at the moment. A device code was issued, but polling `clawhub.ai:443` from this machine timed out. After authorizing on the web, you still need to confirm the CLI login succeeded, then publish and check the entries. All listed content is distributed under MIT-0. The root MIT License still applies to the rest of the repository. See the [official CLI docs](https://docs.openclaw.ai/clawhub/cli) |
| SkillHub Registry (skillhub.fyi) | Publish to a registry you own | This is a registry/package service, not a public discovery directory for all users. It is not treated as a public marketplace channel this time |

These platform names are similar, but their account systems and publishing flows differ. This page records `skillhub.space`, `skillhub.cn`, `skill.xfyun.cn`, `useskillhub.com` and `skillhub.fyi` separately. Do not use the login or CLI of one site on another.

There are currently 18 publishing targets: the cross-platform entry point and 17 platform Skills. The license of each Skill is written in its frontmatter. Publishing to ClawHub is licensed under MIT-0.

On ClawHub, 4 entries with the same names are held by other publishers: `bilibili-upload`, `douyin-upload`, `tiktok-upload` and `youtube-upload`. This repository's cross-platform entry point uses `social-auto-upload`. The other Skills use `social-auto-upload-<skill-directory>`, so no one else's entries are overwritten.

## Install examples

Install the entry point or a single platform Skill from the `skills.sh` CLI:

```bash
npx skills add dreammis/social-auto-upload --skill social-auto-upload
npx skills add dreammis/social-auto-upload --skill douyin-upload
```

Replace `douyin-upload` with a directory name from the table above. This command installs the GitHub source. It does not install the Python project itself and does not create the `sau` command. Set up the CLI runtime environment by following the [installation guide](./install.md). `sau skill install` does not exist. Do not refer to it in docs or Skills.

## Checklist for adding a platform

When adding a platform, do all of the following in the same PR:

- Add or update `skills/<platform>-upload/SKILL.md`. If there is no CLI, state the real entry point and dependencies clearly, and do not invent commands
- In the Skill frontmatter, set `license`, a unique `slug`, `displayName`, `version` and `summary`. Before listing on ClawHub, confirm you have the right to publish under MIT-0
- Update the README feature table and all platform Skill links. When the number of platforms or Skills changes, also update the README badge
- Update the platform mapping and channel status on this page
- Update `docs/CLI.md`, stating the available commands and the unsupported capabilities
- Check that the instructions and files needed for standalone installation are inside the Skill's own directory. Do not depend on relative paths outside that directory
- Check that the release package contains no account files, cookies, screenshots, secrets or local paths
- Complete the submission to every applicable public Skills marketplace, or record the specific account, format or license reason that blocks it. Check the license, review and version requirements. Do not mark something as listed when it is unsubmitted or pending review

The GitHub PR template has the same reminder checklist. When you change CLI options, the login flow or platform limits, update the matching Skill at the same time, so the Skill and the implementation do not drift apart.
