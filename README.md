# social-auto-upload

![Python](https://img.shields.io/badge/Python-3.10--3.12-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/github/license/dreammis/social-auto-upload)
![Release](https://img.shields.io/github/v/release/dreammis/social-auto-upload?display_name=tag)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-18-0D9488?logo=github)](./docs/skill-distribution.md)
[![skills.sh](https://img.shields.io/badge/skills.sh-Agent%20Skills-4B32C3?logo=github)](https://www.skills.sh/dreammis/social-auto-upload/douyin-upload)

`social-auto-upload` is a multi-platform publishing tool for content creators and operators. It provides a unified CLI and Skills for agents such as Codex, OpenClaw and Claude Code.

The platforms for video, article and image post publishing, and their entry points, are listed in the table below.

CLI commands are maintained per platform in `sau_commands/`, and the publishing flows are in `uploader/`. Day-to-day changes are recorded in [CHANGELOG.md](./CHANGELOG.md); stable versions are published through GitHub Releases.

<img src="media/show/tkupload.gif" alt="tiktok show" width="800"/>

## 💎 Sponsors

<table width="100%">
 <tr>
    <td width="25%" align="center" valign="middle">
      <a href="https://chilltion.com/?ref=1y5k5k">
        <img src="static/DolOffer.png" alt="DolOffer Sponsor" width="180">
      </a>
    </td>
    <td width="75%" align="left" valign="middle">
      Thanks to <a href="https://doloffer.com/" target="_blank">DolOffer</a> for supporting this project! For creators who run content matrices, multi-platform distribution and AI-automated operations, digital tools such as ChatGPT, Claude, YouTube Premium, Spotify, Apple Music, Notion and Office are often a long-term cost. DolOffer provides subscription and top-up services for AI, video, music and productivity tools, helping users set up common digital products at a lower cost. See the <a href="https://github.com/Doloffer-g/guide" target="_blank">DolOffer Guide</a> for details. Use the coupon code <code>AI8888</code> for an extra 10% off. Prices and service rules are as stated on the official website.  
    </td>
  </tr>
  <tr>
    <td width="25%" align="center" valign="middle">
      <a href="https://chilltion.com/?ref=1y5k5k">
        <img src="static/chilltion.png" alt="chilltion Sponsor" width="180">
      </a>
    </td>
    <td width="75%" align="left" valign="middle">
      Chilltion AI (轻视AI): turns a single sentence into motion-graphics animation. It suits low-cost production of knowledge, science, explainer, tutorial and introduction videos, video matrices and account warm-up, at about 1% of the cost of tools such as Seedance. <a href="https://chilltion.com/?ref=1y5k5k">Sign up</a> now and get 1500 credits.
    </td>
  </tr>
    <tr>
        <td width="25%" align="center" valign="middle">
          <a href="http://t.clawpower.vip/1005">
            <img src="static/clawpower.png" alt="ClawPower Sponsor" width="180">
          </a>
        </td>
        <td width="75%" align="left" valign="middle">
          ClawPower is a stable and reliable relay service for large AI models, providing access to more than 60 models including Claude, GPT and Gemini. Whether you use OpenClaw or Hermes for agent automation, Claude Code or Codex for programming, or write content for WeChat official accounts and Xiaohongshu, you get a stable, smooth model service you can rely on long term. Prices start at 30% of the official price. Click <a href="http://t.clawpower.vip/1005">to claim a free $5 cash voucher</a>.
        </td>
      </tr>
  <tr>
    <td width="25%" align="center" valign="middle">
      <img src="static/wechat.png" alt="Sponsor Contact" width="150">
    </td>
    <td width="75%" align="left" valign="middle">
      <strong>Become a sponsor</strong><br>
      If you would like to sponsor this project, scan the WeChat QR code on the left (please state your purpose when adding: <strong>sponsorship</strong>).
    </td>
  </tr>
</table>

---


## Table of contents

- [💡 Features](#features)
- [💾 Installation](#installation)
- [🤖 AI Agent](#ai-agent)
- [🏁 Quick start](#quick-start)
- [📝 Changelog](./CHANGELOG.md)
- [📃 Documentation](#documentation)
- [🐾 Community and support](#community-and-support)
- [🤝 Contributing](#contributing)
- [📜 License](#license)
- [⭐ Star History](#star-history)

## 💡Features

| Platform | Login / account setup | Video | Article | Image post | Scheduled publishing | CLI | Skill | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Douyin | ✅ | ✅ | - | ✅ | ✅ | ✅ | ✅ | Video and image post publishing |
| Bilibili | ✅ | ✅ | - | - | ✅ | ✅ | ✅ | Video publishing; `biliup` is set up automatically at runtime |
| Xiaohongshu (browser version) | ✅ | ✅ | - | ✅ | ✅ | ✅ | ✅ | Video and image post publishing |
| Kuaishou | ✅ | ✅ | - | ✅ | ✅ | ✅ | ✅ | Video and image post publishing |
| WeChat Channels | ✅ | ✅ | - | - | ✅ | ✅ | ✅ | Video publishing |
| Baijiahao | ✅ | ✅ | - | - | - | ✅ | ✅ | Video publishing |
| Dayu | ✅ | ✅ | ✅ | - | ✅ | ✅ | ✅ | [Video publishing](./docs/dayu.md); [article publishing](./docs/dayu-article.md) supports HTML/Markdown/TXT, inline images and a cover |
| Alipay Life Account | ✅ | ✅ | - | - | - | ✅ | ✅ | Video publishing |
| Weibo | ✅ | ✅ | - | - | - | ✅ | ✅ | Video title up to 30 characters |
| Hupu | ✅ | ✅ | - | - | - | ✅ | ✅ | Video title 4–40 characters |
| TikTok | ✅ | ✅ | - | - | ✅ | - | ✅ | Chrome-based implementation; no `sau` CLI |
| Xueqiu | ✅ | - | ✅ | - | - | ✅ | ✅ | [Long articles with images](./docs/xueqiu.md): supports HTML/Markdown/TXT, inline images and a cover |
| YouTube | ✅ | ✅ | - | - | In development | ✅ | ✅ | Video publishing |
| Zhihu | ✅ | ✅ | ✅ | - | Experimental | ✅ | ✅ | [Article and video publishing](./skills/zhihu-upload/SKILL.md); articles support images at their positions in the body |
| Facebook | ✅ | ✅ | - | ✅ | - | ✅ | ✅ | Supports listing posts, moving to trash and permanent deletion |
| Facebook Page | ✅ | ✅ | - | ✅ | ✅ | ✅ | ✅ | Supports scheduled publishing of videos and image posts, listing, and cancelling a schedule |
| Instagram | ✅ | ✅ | - | ✅ | - | ✅ | ✅ | Supports Reels, single images and carousels |

`✅` means supported, `-` means not applicable or not provided; "In development" and "Experimental" are not counted as stable capabilities. An article body can contain images; this is listed separately from standalone image post publishing.

### By content type

| Content type | Platforms and entry points |
| --- | --- |
| Video | Douyin, Kuaishou, Xiaohongshu, Bilibili, WeChat Channels, Baijiahao, Dayu, Zhihu, YouTube and others; see the CLI examples below and the [CLI guide](./docs/CLI.md) |
| Article | Dayu [article publishing](./docs/dayu-article.md), Xueqiu [long articles with images](./docs/xueqiu.md), Zhihu [article publishing](./skills/zhihu-upload/SKILL.md#article) |
| Image post | Douyin, Kuaishou, Xiaohongshu, Facebook, Facebook Page, Instagram; see the [CLI guide](./docs/CLI.md) for CLI examples |

For article theme previews and Markdown-to-HTML conversion, see [Article files and theme rendering](./docs/article.md). The built-in themes are `default/grace/simple/modern/plain`. Dayu accepts Markdown directly and converts the theme into a compatible layout that keeps text colors, backgrounds and approximate font sizes; effects such as rounded corners and exact spacing may differ from the local preview.

## 💾Installation

### Using it yourself
Regular users can install and update by following these documents:

- [Installation guide](./docs/install.md)
- [Update guide](./docs/update.md)


### AI Agent

If you use `OpenClaw`, `Codex` or `Claude Code` to install and operate this project, give the agent the repository together with the bootstrap prompt:

- [Agent Bootstrap Prompt](./docs/agent-bootstrap.md)

It guides the agent to:

- Install the project from the current main line first
- Prefer `uv`, the `sau` CLI and `skills/`
- Verify first that the four platform entry points `bilibili`, `douyin`, `kuaishou` and `xiaohongshu` work


Related entry points:

- [CLI guide](./docs/CLI.md)
- [Agent Bootstrap Prompt](./docs/agent-bootstrap.md)
- Cross-platform entry point: [social-auto-upload](./skills/social-auto-upload/SKILL.md)
- Per-platform Skills: [Douyin](./skills/douyin-upload/SKILL.md), [Bilibili](./skills/bilibili-upload/SKILL.md), [Xiaohongshu](./skills/xiaohongshu-upload/SKILL.md), [Kuaishou](./skills/kuaishou-upload/SKILL.md), [WeChat Channels](./skills/tencent-upload/SKILL.md), [Baijiahao](./skills/baijiahao-upload/SKILL.md), [Dayu](./skills/dayu-upload/SKILL.md), [Alipay Life Account](./skills/alipay-upload/SKILL.md), [Weibo](./skills/weibo-upload/SKILL.md), [Hupu](./skills/hupu-upload/SKILL.md), [TikTok](./skills/tiktok-upload/SKILL.md), [Xueqiu](./skills/xueqiu-upload/SKILL.md), [YouTube](./skills/youtube-upload/SKILL.md), [Zhihu](./skills/zhihu-upload/SKILL.md), [Facebook](./skills/facebook-upload/SKILL.md), [Facebook Page](./skills/meta-upload/SKILL.md), [Instagram](./skills/instagram-upload/SKILL.md)
- [Legacy web version](./docs/legacy-web.md)

#### Skill distribution and marketplaces

The repository provides a cross-platform entry point and a separate Skill for each platform. `skills.sh` already lists the [Douyin Skill](https://www.skills.sh/dreammis/social-auto-upload/douyin-upload). For marketplace listings, how to publish to them, and the checklist for adding a platform, see [Skill distribution channels and publishing status](./docs/skill-distribution.md).

Skill directories can be installed from GitHub into compatible agents. To install a single Skill:

```bash
npx skills add dreammis/social-auto-upload --skill douyin-upload
```

Replace `douyin-upload` with the cross-platform entry point or another platform's directory name. For how directories map to platforms, and for marketplace publishing methods and status, see [Skill distribution](./docs/skill-distribution.md). `sau skill install` is not a command provided by this project.


## 🏁Quick start

### Option 1: Use the CLI

First check the platform capability table above for what is supported, then pick a content type below. Videos, articles and image posts each use their own publish command; images inside an article are still part of the article body.

#### Account setup

Log in to each platform once, then check the session. `--account` is a name you give the local session, for example `creator`; it is used to tell multiple accounts apart.

```bash
sau douyin login --account creator
sau douyin check --account creator
# Replace with dayu, xueqiu, zhihu or another platform name; see the matching document for the login requirements.
```

#### Video

Use `upload-video` for the platform you want:

| Platform | Platform argument | Publishing notes |
| --- | --- | --- |
| Douyin, Kuaishou, Xiaohongshu | `douyin`, `kuaishou`, `xiaohongshu` | [CLI arguments](./docs/CLI.md) |
| Bilibili, WeChat Channels | `bilibili`, `tencent` | [CLI arguments](./docs/CLI.md) |
| Baijiahao, Dayu | `baijiahao`, `dayu` | [Dayu video](./docs/dayu.md), [CLI arguments](./docs/CLI.md) |
| Alipay Life Account, Weibo, Hupu | `alipay`, `weibo`, `hupu` | [CLI arguments](./docs/CLI.md) |
| YouTube | `youtube` | [CLI arguments](./docs/CLI.md) |
| Zhihu | `zhihu` | [Article and video publishing](./skills/zhihu-upload/SKILL.md) |
| Facebook, Facebook Page, Instagram | `facebook`, `facebook-page`, `instagram` | [CLI arguments](./docs/CLI.md) |

```bash
sau douyin upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介"
sau kuaishou upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介"
sau xiaohongshu upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介"
sau bilibili upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介" --tid 249
sau tencent upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介" --tags tag1,tag2
sau baijiahao upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介" --tags tag1,tag2
sau alipay upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介" --tags tag1,tag2
sau weibo upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介" --tags tag1,tag2
sau hupu upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介" --tags tag1,tag2
sau youtube upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介" --tags tag1,tag2 --playlist "我的系列" --visibility public
sau zhihu upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介" --originality original --category "教育" --video-mark "内容无需标注"
sau facebook upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介" --tags Facebook,测试
sau facebook-page upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介" --page "我的 Page"
```

#### Article

Articles use `upload-article`. The body comes from a file, and images should be placed at the matching paragraphs in the source. The supported platforms are:

| Platform | Body and notes |
| --- | --- |
| Dayu | HTML / Markdown / TXT, inline images and a cover; see [article publishing](./docs/dayu-article.md) |
| Xueqiu | HTML / Markdown / TXT, images at their original positions in the body and a separate cover; see [long article publishing](./docs/xueqiu.md) |
| Zhihu | HTML / Markdown / TXT, images at their original positions in the body; see [article publishing](./skills/zhihu-upload/SKILL.md#article) |

```bash
sau dayu upload-article --account creator --title "如何阅读作品数据面板" --content-file examples/dayu_article.html --source "无需标注" --cover-indices 1
sau xueqiu upload-article --help
sau zhihu upload-article --account creator --title "文章标题" --content-file examples/article.md
```

#### Image post

An image post is a standalone picture post, carousel or image note. Use `upload-note`; it is supported on Douyin, Kuaishou, Xiaohongshu, Facebook, Facebook Page and Instagram.

```bash
sau douyin upload-note --account <account_name> --images videos/1.png videos/2.png --title "图文标题" --note "图文正文"
sau kuaishou upload-note --account <account_name> --images videos/1.png videos/2.png videos/3.png --title "图文标题" --note "图文正文"
sau xiaohongshu upload-note --account <account_name> --images videos/1.png videos/2.png videos/3.png --title "图文标题" --note "图文正文"
sau facebook-page upload-note --account <account_name> --images images/1.jpg --title "Page 图文" --note "正文" --page "我的 Page" --schedule "2026-10-21 10:30" --result .local/page-result.json
sau facebook upload-note --account creator --images images/1.jpg images/2.jpg --title "图片帖" --note "正文"
sau instagram upload-note --account creator --images images/1.jpg images/2.jpg --title "图片轮播" --note "正文"
```

For Zhihu, `--account` is a local session alias and does not have to match the display name; at login the program reads the identity currently shown on the page and saves the binding information.

Facebook, Facebook Page and Instagram connect directly through the system network by default. If your network needs a proxy, add `--proxy "<proxy address>"` to the command explicitly, or set `SAU_FACEBOOK_PROXY`, `SAU_FACEBOOK_PAGE_PROXY` or `SAU_INSTAGRAM_PROXY`. Pass `--proxy ""` to ignore the environment variables and connect directly.

> YouTube notes: login is interactive (a Google account, completed in the browser, no QR code). This project uses browser automation instead of the official API
> because **videos uploaded through an API project that has not passed Google's compliance audit are forced to private and cannot be made public**, which is impractical for an individual or single channel.
> Browser automation has no such limit, can publish public videos directly, and is consistent with the cookie approach used for the project's other platforms.
> `--playlist` suits serialized content and series; `--visibility` accepts `public`, `unlisted` or `private`.
> The upload **waits until progress reaches 100% before clicking publish** (a browser upload only continues while the window stays open, so publishing halfway would cut it off and leave it stuck).
> In regions where youtube.com is blocked, set `YT_PROXY = "http://127.0.0.1:7890"` in `conf.py` (chromium ignores the system proxy, so it must be specified explicitly).

Markdown themed articles need Node.js 22+ the first time. Prepare the rendering dependencies first, then publish:

```bash
sau article setup
sau article render --content-file examples/article.md --theme modern --output output/article.html
sau dayu upload-article --account <account_name> --title "如何阅读作品数据面板" --content-file examples/article.md --theme modern --source "无需标注" --cover-indices 1
```

`sau article render` only generates local HTML; `sau dayu upload-article` actually publishes, and returns success once the platform confirms publication, without waiting for review. HTML/TXT input does not need Node.js and does not use `--theme`. For Dayu video arguments and article format limits, see the [video guide](./docs/dayu.md) and the [article guide](./docs/dayu-article.md).

Additional notes:

- Names such as `creator` are only example values; what they really mean is `account_name`
- One `account_name` corresponds to one account file. You can prepare several accounts, and run tasks concurrently by account name
- If Douyin video publishing triggers an SMS second verification, the program first reads `verify_code.txt` in the project root. If you run the CLI manually in a local interactive terminal, you can also type the verification code at the terminal prompt
- Conventions shared by the browser platforms:
- Videos use `title + desc + tags`
- Douyin, Kuaishou and Xiaohongshu image notes use `title + note + tags`
- Dayu articles use `title + content-file + source`, with the body saved in an HTML, Markdown or TXT file
- The Bilibili CLI does not require users to install `biliup` manually
- The program downloads `biliup` automatically the first time the related command runs
- Later runs check the upstream release automatically and update
- Bilibili login is best done by the user in a real local terminal. If the terminal QR code is displayed incompletely, open `qrcode.png` in the current directory and scan it

### Option 2: Use the examples

The `examples/` directory contains two kinds of scripts:

- Examples that wrap the current main-line CLI
- Legacy examples that call the uploaders directly

For Douyin, Kuaishou, Xiaohongshu and Bilibili, the current main line prefers the `sau ...` CLI above.
The scripts below are mostly legacy direct-uploader examples or debugging entry points:

- `examples/upload_to_douyin.py`
- `examples/upload_video_to_bilibili.py`
- `examples/upload_to_kuaishou.py`
- `examples/upload_video_to_tencent.py`
- `examples/upload_video_to_baijiahao.py`
- `examples/get_alipay_cookie.py`
- `examples/test_alipay_upload.py`
- `examples/upload_video_to_tiktok.py`
- `examples/upload_video_to_xiaohongshu.py`

## 📃Documentation

For installation, updates and platform arguments, see the matching documents in this repository: the [installation guide](./docs/install.md), the [update guide](./docs/update.md) and the [CLI guide](./docs/CLI.md). For the product introduction and community information, see the [social-auto-upload documentation site](https://sap-doc.nasdaddy.com/).

## 🐾Community and support

[☕ Donate as u like](https://www.buymeacoffee.com/hysn2001m) - If you find this project helpful, please consider sponsoring it.

If you are also an independent developer or tech enthusiast interested in topics such as #technology monetization, #AI startups, #cross-border e-commerce, #automation tools and #video creation, you are welcome to join the community.

### Creator

<table>
    <td align="center">
        <a href="https://sap-doc.nasdaddy.com/">
            <img src="media/mp.jpg" width="200px" alt="NasDaddy official account"/>
            <br />
            <sub><b>WeChat official account</b></sub>
        </a>
        <br />
        <a href="https://github.com/dreammis/social-auto-upload/commits?author=dreammis" title="Code">💻</a>
        <br />
        Follow the official account and send the account the message `上传` ("upload") to get the group invitation
    </td>
    <td align="center">
        <a href="https://sap-doc.nasdaddy.com/">
            <img src="media/QR.png" width="200px" alt="Donation code / group invitation"/>
            <br />
            <sub><b>Community group (via the official account)</b></sub>
        </a>
        <br />
        <a href="https://sap-doc.nasdaddy.com/" title="Documentation">📖</a>
        <br />
        If you find the project useful, please consider a donation
    </td>
</table>




## 🤝Contributing

Contributions of all kinds are welcome, including but not limited to:

-   Submitting bug reports and feature requests.
-   Improving the code and documentation.
-   Sharing usage experience and tutorials.

If you want to contribute code, please follow these steps:

1.  Fork this repository.
2.  Create a new branch (`git checkout -b feature/YourFeature` or `bugfix/YourBugfix`).
3.  Commit your changes (`git commit -m 'Add some feature'`).
4.  Push to your branch (`git push origin feature/YourFeature`).
5.  Open a Pull Request.

Before submitting code or regular documentation, please confirm that you have the right to submit it and agree that your contribution is released under this project's MIT License. Skills under `skills/` are MIT-0 as declared in their own frontmatter. When submitting third-party content, please also state its source and the license that applies to it.

When adding or changing a platform, update the CLI capability table, the platform's Skill and the distribution catalog in the same PR. For a platform without a CLI, also explain the actual entry point. The GitHub PR template contains an item-by-item checklist so that Skill publishing materials are not missed once the implementation is done.

## Main contributors

<a href="https://github.com/dreammis/social-auto-upload/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=dreammis/social-auto-upload" />
</a>


## 🙏Acknowledgements

This project's Bilibili upload support is built by integrating and wrapping the open-source project `biliup`.
Thanks to the `biliup` project and its contributors for the underlying capability:

- https://github.com/biliup/biliup

The third-party components and runtime tools this project depends on remain subject to their own licenses. When redistributing or integrating this project downstream, please also check and keep the copyright, license and NOTICE statements required by the relevant third-party components.

## 📜License

The main body of the repository uses the [MIT License](LICENSE). The Agent Skills under version control are released under the license declared in each `SKILL.md` frontmatter. The current 18 product Skills are MIT-0, so that they can be distributed on platforms that require that license. This does not change the MIT License of the rest of the repository's code.

## ⭐Star-History

> If this project helps you, please give it a ⭐ Star to show your support!




[![Star History Chart](https://star-history.dera.page/svg?repos=dreammis/social-auto-upload&type=Date)](https://star-history.dera.page/#dreammis/social-auto-upload&Date)
