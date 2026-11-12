# CLI Guide

The project now provides one unified CLI entry, `sau`. The main line currently supports:

- `douyin`
- `kuaishou`
- `xiaohongshu`
- `bilibili`
- `tencent`
- `baijiahao`
- `alipay`
- `weibo`
- `hupu`
- `youtube`
- `facebook`: immediate publishing, lookup and deletion of videos/image posts on a Facebook personal profile
- `facebook-page`: immediate or scheduled publishing of videos/image posts to a Facebook Page through Meta Business Suite
- `dayu`
- `xueqiu`: HTML/Markdown/TXT long articles, images at their original positions, and covers. It publishes for real by default and supports querying the result by original work ID. See the [Xueqiu guide](./xueqiu.md). Publishing through the official CLI and backend verification have been tested
- `zhihu`: articles, videos and scheduled publishing. See the [Zhihu Skill](../skills/zhihu-upload/SKILL.md) in the repository

The local article processing command is `sau article`. It supports listing themes, preparing the environment, and rendering Markdown/HTML files. See [Article Files and Theme Rendering](./article.md).

The Skills for agents include one cross-platform entry point and a separate entry point for each supported platform. For the full list, see the [AI Agent section of the README](../README.md#ai-agent). TikTok uses the Chrome uploader already in the repository and has no `sau tiktok` command. See the [TikTok Skill](../skills/tiktok-upload/SKILL.md).

Implementation notes:

- `sau_cli.py` assembles the commands and starts execution. `sau_commands/<platform>.py` each maintain their own options, request data and execution logic. `sau_commands/arguments.py` maintains the shared option rules
- `sau.exe` is the command entry generated automatically in the Windows virtual environment after installation. It still just calls `sau_cli.py`
- To use it with agents such as OpenClaw and Codex, install the entry point or any platform entry under the repository's `skills/`. For publishing channels and install methods, see [Skill Distribution and Publishing](./skill-distribution.md).

## Install the CLI entry

If you want to use the `sau` command directly instead of running `python sau_cli.py` by hand, install once in the project root:

```bash
uv pip install -e .
```

After that you can use it directly:

```bash
sau douyin --help
sau kuaishou --help
sau xiaohongshu --help
sau bilibili --help
sau tencent --help
sau baijiahao --help
sau alipay --help
sau weibo --help
sau hupu --help
sau youtube --help
sau facebook --help
sau facebook-page --help
sau dayu --help
sau xueqiu --help
sau zhihu --help
```

## Install the patchright browser

On Windows, set a mirror first, then install Chromium:

```powershell
$env:PLAYWRIGHT_DOWNLOAD_HOST="https://npmmirror.com/mirrors/playwright"; patchright install chromium
```

## Dayu CLI subcommands

For login, categories and source options, see [Video publishing](./dayu.md). For body files, formats and image paths, see [Image post publishing](./dayu-article.md). For Markdown themes and the standalone local render command, see [Article Files and Theme Rendering](./article.md).

```powershell
# --title "如何阅读作品数据面板" = "How to read the work data dashboard"; --source "无需标注" = "No label needed"
sau dayu upload-article --account creator --title "如何阅读作品数据面板" --content-file examples/dayu_article.html --source "无需标注" --cover-indices 1

# Markdown needs Node.js 22+ the first time; install the rendering dependencies first
sau article setup
sau dayu upload-article --account creator --title "如何阅读作品数据面板" --content-file examples/article.md --theme modern --source "无需标注" --cover-indices 1
```

The default Markdown theme is `default`. The options are `default/grace/simple/modern/plain`. HTML/TXT do not use `--theme`. A theme is automatically converted to Dayu-compatible layout, which keeps text color, background and approximate font size. Rounded corners, fonts and spacing may differ from the local preview. The server-side preview is checked before the publish is confirmed. The command returns success once the platform confirms the final publish, without waiting for review.

Both videos and articles support `--schedule "YYYY-MM-DD HH:MM"`: Beijing time, 2 hours to 7 days ahead, with minutes a multiple of 5. It succeeds once the platform confirms the original work and the schedule, without waiting for the time to arrive. Run `sau dayu verify --account creator --result "this_result_file.json"` with the result file to check the original work and its time read-only. Do not upload again. Agents can use the repository's [Dayu Skill](../skills/dayu-upload/SKILL.md).

## Zhihu CLI subcommands

Zhihu supports publishing articles and videos. Articles use HTML/Markdown/TXT source files, and body images are imported at their positions in the source. A video file must be larger than 100KB (102400 bytes), at most 20GB, and at most 4 hours long.

```powershell
sau zhihu login --account creator
sau zhihu check --account creator
sau zhihu upload-article --account creator --title "Zhihu article title" --content-file examples/article.md
# --category "教育" = Education; --video-mark "含 AI 生成内容" = Contains AI-generated content
sau zhihu upload-video --account creator --file videos/demo.mp4 --title "Zhihu video title" --desc "Video description" --originality original --category "教育" --video-mark "含 AI 生成内容"
# After uploading the material, export all topics and video marks of that form. Nothing is published, but a draft may be left behind.
sau zhihu upload-video --account creator --file videos/demo.mp4 --title "Zhihu video title" --originality original --show-options
```

`--account` is a local session alias and does not need to match the Zhihu display name. The login command reads the identity currently shown on the page and saves a local session.

`--category` and `--video-mark` use the CLI's selectable values. For the full list of topics, see `sau zhihu upload-video --help`. When omitted, you pick by number in an interactive terminal. Non-interactive calls must specify them. Before submitting, the program still checks the live menu. `--show-options` writes the candidates to `options` in the result JSON.

`--originality` accepts `original` or `reprint` (repost). `--video-mark` accepts `内容无需标注` (no label needed), `含 AI 生成内容` (contains AI-generated content), `含虚构演绎内容` (contains fictional dramatization), `内容含营销信息` (contains marketing information), `内容为转载` (content is a repost), `个人观点仅供参考` (personal opinion, for reference only). Choose according to the real content. A video title is 5–50 characters and the description is at most 300 characters. Automatic topic selection, custom covers, columns and content sources are not supported yet.

An article title is at most 100 characters. Images are written in the source, for example `![image](images/1.png)`, and relative paths are resolved from the source directory. Before submitting, the text, image positions, basic formatting and links are checked. When a non-empty draft is restored, the program stops to protect the original text. For Markdown, run `sau article setup` the first time. Custom theme CSS, manual covers, adding to a column and document import are not supported yet.

Add `--prepare-only` to an article or video to only fill in and check. The platform may still save a draft automatically. `published` means the platform confirmed the publish. When the result is `submission_unknown`, first check the original work in the creator center and do not upload again. If you already have a link, check it with `sau zhihu verify --account creator --result "this_result.json"`. The video detail URL can be `/pin/<work ID>`.

`--schedule "YYYY-MM-DD HH:MM"` is experimental. In Beijing time it is limited to between 30 minutes and 48 hours ahead, and the full scheduling flow is not guaranteed to work yet. For more usage, see the [Zhihu Skill](../skills/zhihu-upload/SKILL.md).

## Douyin CLI subcommands

```bash
sau douyin login --account <account_name>
sau douyin login --account <account_name> --headless
sau douyin check --account <account_name>
sau douyin upload-video --account <account_name> --file videos/demo.mp4 --title "Sample title" --desc "Sample description" --tags sports,training
sau douyin upload-note --account <account_name> --images videos/1.png videos/2.png --title "Image post title" --note "Image post example" --tags image-post,test
```

Notes on the Douyin SMS verification code:

- If SMS two-step verification is triggered while publishing a video, the CLI first reads `verify_code.txt` in the project root
- If `verify_code.txt` is not found and the command is being run by hand in an interactive terminal, the CLI prompts for the code directly in the terminal
- For agents, automated tasks and remote bridges, you can still feed the code by writing `verify_code.txt`
- After verification succeeds, the program cleans up `verify_code.txt` automatically

## Kuaishou CLI subcommands

```bash
sau kuaishou login --account <account_name>
sau kuaishou check --account <account_name>
sau kuaishou upload-video --account <account_name> --file videos/demo.mp4 --title "Sample title" --desc "Sample description" --tags sports,training
sau kuaishou upload-note --account <account_name> --images videos/1.png videos/2.png videos/3.png --title "Image post title" --note "Image post example" --tags image-post,test
```

## Xiaohongshu CLI subcommands

```bash
sau xiaohongshu login --account <account_name>
sau xiaohongshu check --account <account_name>
sau xiaohongshu upload-video --account <account_name> --file videos/demo.mp4 --title "Sample title" --desc "Sample description" --tags xiaohongshu,video
sau xiaohongshu upload-note --account <account_name> --images videos/1.png videos/2.png videos/3.png --title "Image post title" --note "Image post example" --tags image-post,test
```

If you are overseas and cannot log in to the default creator backend, you can switch to the RedNote domain with an environment variable. The setting applies to login, cookie checks, video publishing and image post publishing:

```bash
SAU_XHS_CREATOR_BASE_URL=https://creator.rednote.com sau xiaohongshu login --account <account_name>
```

## Bilibili CLI subcommands

```bash
sau bilibili login --account <account_name>
sau bilibili check --account <account_name>
sau bilibili upload-video --account <account_name> --file videos/demo.mp4 --title "Sample title" --desc "Sample description" --tid 249 --tags football,test --thumbnail covers/demo.png
```

Additional notes:

- Names such as `creator` are only example values. What you actually pass is your own `account_name`
- One `account_name` maps to one account file. You can prepare several accounts and use them concurrently
- Shared metadata convention for the browser platforms:
- Videos use `title + desc + tags`
- Image notes on Douyin, Kuaishou and Xiaohongshu use `title + note + tags`
- Dayu articles use `title + content-file + source`, and the body is read from a UTF-8 file
- `sau bilibili ...` prepares `biliup` automatically
- If `biliup` is not present locally, it is downloaded automatically the first time
- If the upstream GitHub Release has an update, it is updated automatically before running
- It is best for the user to run `sau bilibili login --account <name>` in a real local terminal. If the QR code is not fully displayed in the terminal, open `qrcode.png` in the current directory and scan it

## WeChat Channels CLI subcommands

```bash
sau tencent login --account <account_name>
sau tencent check --account <account_name>
sau tencent upload-video --account <account_name> --file videos/demo.mp4 --title "Sample title" --desc "Sample description" --tags channels,test
```

WeChat Channels supports scheduled publishing, drafts, collections and covers in two aspect ratios:

```bash
sau tencent upload-video --account <account_name> --file videos/demo.mp4 --title "Sample title" --desc "Sample description" --schedule "2026-03-24 21:30" --thumbnail-landscape covers/landscape.png --thumbnail-portrait covers/portrait.png --collection "My collection"
sau tencent upload-video --account <account_name> --file videos/demo.mp4 --title "Sample title" --desc "Sample description" --draft
```

WeChat Channels login and upload depend on the login state in the browser. In headless mode, if a QR-code scan is needed, the CLI generates a temporary QR code. When you need to look at the page by hand, add `--headed`.

## Baijiahao CLI subcommands

```bash
sau baijiahao login --account <account_name>
sau baijiahao check --account <account_name>
sau baijiahao upload-video --account <account_name> --file videos/demo.mp4 --title "Sample title" --desc "Sample description" --tags baijiahao,test
```

Baijiahao currently supports login, account check and video upload. It supports `--thumbnail` and `--collection`, and does not support `--schedule` yet. Before uploading, you must log in to the Baidu account and save the account file.

## Alipay Life Account CLI subcommands

```bash
sau alipay login --account <account_name>
sau alipay check --account <account_name>
sau alipay upload-video --account <account_name> --file videos/demo.mp4 --title "Sample title" --desc "Sample description" --tags life-account,test
```

Alipay Life Account (支付宝生活号) currently supports login, account check and video upload. It supports `--thumbnail` and `--collection`, and does not support image post upload or `--schedule` yet. Before first use, log in to the Alipay content creation backend and confirm that the account has Life Account content creation permission.

## YouTube CLI subcommands

```bash
sau youtube login --account <account_name>
sau youtube check --account <account_name>
sau youtube upload-video --account <account_name> --file videos/demo.mp4 --title "Sample title" --desc "Sample description" --tags tag1,tag2 --playlist "My series" --visibility public
sau youtube upload-video --account <account_name> --file videos/demo.mp4 --title "Scheduled video" --schedule "2026-10-21 10:30"
```

YouTube login needs a Google account login in the browser and does not use a QR code. `--visibility` accepts `public`, `unlisted` or `private`, and `--playlist` is optional. With `--schedule`, the YouTube Studio Schedule state is used and the date/time controls are checked. Without it, the video is published immediately according to `--visibility`.

## Facebook CLI subcommands

Use `facebook` for a personal profile and `facebook-page` for a Page. No proxy is configured by default, and the browser connects directly through the system network. When you need a proxy, pass `--proxy "proxy address"` in the command, or set `SAU_FACEBOOK_PROXY` or `SAU_FACEBOOK_PAGE_PROXY`. Pass `--proxy ""` to ignore the environment variables and connect directly. Account files are saved separately. Log in to the matching entry first on first use.

```powershell
sau facebook login --account creator
sau facebook check --account creator
sau facebook upload-video --account creator --file videos/demo.mp4 --title "Video title" --desc "Body text"
sau facebook upload-note --account creator --images images/1.jpg --title "Image post title" --note "Body text"
sau facebook-page login --account creator
sau facebook-page upload-note --account creator --page "My Page" --images images/1.jpg --title "Image post title" --note "Body text" --schedule "2026-10-21 10:30" --result .local/page-result.json
sau facebook-page upload-video --account creator --page "My Page" --file videos/demo.mp4 --title "Video title" --desc "Body text" --schedule "2026-10-21 10:30" --result .local/reel-result.json
```

A personal profile supports immediate publishing of videos, images and body text. Scheduling for personal profiles is not connected yet. Page videos and image posts support `--schedule "YYYY-MM-DD HH:MM"` in Beijing time, and it must be at least 2 hours ahead. Without it, the post is submitted immediately. The current implementation checks the `Asia/Shanghai` browser time zone, the page date/time, and the schedule in the original work list. `--page` should be the exact Page name.

Page publish results are saved in `.local/meta-results/` by default. You can also specify a JSON file with `--result`. The result contains `page_id`, `page_name`, `content_id` (which may not exist yet while a video is processing) and the status. `scheduled` means the platform confirmed the schedule and the original record was checked. `published` means the image post is published and the original record was checked. For an immediately published video, `processing` is returned when the creation response has no error and the completion dialog appears. It means the platform has accepted it and is processing it. Do not treat it as already publicly playable. Look up the work ID later, once the platform has generated it. `submission_unknown` only means the submission response or the completion evidence was not confirmed. You must check the original record first and must not resend directly.

### Lookup and deletion

```powershell
sau facebook verify --account creator --post-url "https://www.facebook.com/reel/<work ID>/" --owner-id "<numeric author ID>" --expected-text "<original work body text>"
sau facebook delete --account creator --post-url "<original work link>" --owner-id "<numeric author ID>" --expected-text "<original work body text>"
sau facebook delete --account creator --post-url "<original work link>" --owner-id "<numeric author ID>" --expected-text "<original work body text>" --from-trash --permanent
sau facebook-page verify --account creator --page "My Page" --page-id "<numeric Page ID>" --content-id "<content ID>" --expected-text "<original work body text>" --scheduled
sau facebook-page delete --account creator --page "My Page" --page-id "<numeric Page ID>" --content-id "<content ID>" --expected-text "<original work body text>" --scheduled --result .local/delete-result.json
```

Deleting from a personal profile moves the work to the trash by default. Add `--permanent` to delete it permanently. For a work that is already in the trash, also add `--from-trash`. To look up the trash, also use `verify --from-trash`. `verify --deleted` only checks whether the original ID is no longer in the trash and returns `absent_from_trash`. It does not use "not found" as proof that it was once permanently deleted.

A Page's `--scheduled` selects the scheduled list. Deleting there cancels the schedule and removes the post permanently. Without this option for a published work, the platform currently moves it to the trash and returns `trashed`. The platform deletes it after 30 days. The CLI does not yet support permanently deleting from the Page trash early. The ID of a scheduled work may change after it is published. To manage a published work, use the ID in the published list.

All deletion actions first check the author or Page, the original work ID and the body text. If the body text is identical and the work cannot be located uniquely, it fails with a clear error. The current lookup covers recent works already loaded in the list. It does not page through all historical works automatically. After a deletion, the server list is queried again. If the result is unknown, query first and do not delete again automatically. Deleting a remote work does not delete the local material.

## Instagram standalone web publishing

Instagram uses the project's Patchright Chrome and does not depend on a Facebook Page or a Business Suite binding. The browser is visible by default. When no proxy is configured, it connects directly through the system network. When you need a proxy, use `--proxy` or `SAU_INSTAGRAM_PROXY`. Pass `--proxy ""` to ignore the environment variables and connect directly. On first use, install the dependencies and Chrome first, following the project environment steps in this document.

```powershell
sau instagram login --account creator
sau instagram check --account creator
sau instagram upload-video --account creator --file videos/demo.mp4 --thumbnail covers/demo.png --title "Video title" --desc "Body text" --tags life,sharing --result .local/instagram-video.json
sau instagram upload-note --account creator --images images/1.jpg --title "Single image title" --note "Body text"
sau instagram upload-note --account creator --images images/1.jpg images/2.jpg --title "Carousel title" --note "Body text" --result .local/instagram-carousel.json
```

For a video/Reel, `--thumbnail` can set a JPG/JPEG/PNG cover. When omitted, Instagram's default cover is used. After an image is specified, the main preview is checked to confirm that it really uses that image, and submission stops if not. The cover is center-cropped to the current video frame, so leave a safe margin for important text near the image edges. Image post publishing does not accept this option.

`login` waits in the project browser for manual login and any required verification, saves the state to `cookies/instagram_creator.json`, and verifies it in a new session. `check` checks the login state and user binding of that account. It cannot replace a check of publishing permission. A network error or an unknown-page timeout is reported as an error and is not treated directly as an expired cookie.

Video input is MP4/MOV. Photos are JPG/JPEG/PNG/AVIF/HEIC/HEIF, and actual decoding and processing are limited by the platform. Several image paths create a carousel in the order passed. A single photo and two different photos have been tested so far. The title, body and tags are merged into the caption, with a total of at most 2200 characters. `--headless` switches to headless running. Manual login uses the default visible mode.

The photo/Reels publishing page and its advanced settings for the current account have no scheduling entry. So this standalone web implementation only supports immediate publishing and has no `--schedule`. This does not mean that all Instagram accounts and clients lack scheduling. The page also offers location, collaborators, AI label, hiding like/view counts and turning off comments. Photos get alt text and filters, and videos get trimming and sound. These optional features are not connected to the CLI yet, and the page defaults are kept. The first notification prompt is dismissed with "later" automatically, and the Reels introduction shown during video upload is confirmed automatically. If there is no prompt, it continues. Login and verification are still completed by the user in the project browser. Unknown popups or failed actions are reported with a clear error.

On success it returns `published`, `content_id`, `post_id`, `post_url` and `media_count`. A Reel may first be in `processing`, and the program waits for the final creation result of this submission. After a timeout, the state already observed is kept. `submission_unknown` means the submission was entered but the platform result was not confirmed. `processing` means the platform has accepted it but the final work is not yet available. In neither case should you upload again directly. The default results are saved in `.local/instagram-results/`. Specifying a path with `--result` is recommended.

If you already have the original work link:

```powershell
sau instagram verify --account creator --post-url "https://www.instagram.com/p/<work ID>/" --expected-text "<exact text from the original work>" --result .local/instagram-verify.json
sau instagram delete --account creator --post-url "https://www.instagram.com/reel/<work ID>/" --expected-text "<exact text from the original work>" --result .local/instagram-delete.json
```

It accepts `/p/<ID>/`, `/reel/<ID>/` and original work links that include the author name. Before acting, it checks the account binding, the author, the work ID and the body text, and refuses to delete another author's work. `delete` moves the work to Instagram's 最近删除 (Recently Deleted) and finally returns `deleted`. Batch deletion and early permanent clearing are not implemented. The retention rules of 最近删除 (Recently Deleted) are decided by the platform. Local material is not deleted.

When the result is unknown and there is no link, first look for the original work on the same account's profile by caption, material and publish time. Copy the original work link and then run `verify`. Not finding it does not prove the submission failed, and do not resend directly. When a deletion shows `deletion_unknown`, likewise check the original work and 最近删除 (Recently Deleted) first, and do not delete again. A failed result includes the stage/error and the local evidence directory. Account state, screenshots and page records are all in directories ignored by Git and should not be committed to the repository.

## Weibo CLI subcommands

```bash
sau weibo login --account <account_name>
sau weibo check --account <account_name>
sau weibo upload-video --account <account_name> --file videos/demo.mp4 --title "Sample title" --desc "Sample description" --tags weibo,test --thumbnail covers/demo.png
```

Weibo currently supports login, account check and video upload. The title is at most 30 characters, and the cover image should be under 5 MB. Image post upload and `--schedule` are not supported yet.

## Hupu CLI subcommands

```bash
sau hupu login --account <account_name>
sau hupu check --account <account_name>
sau hupu upload-video --account <account_name> --file videos/demo.mp4 --title "Sample title" --desc "Sample description" --tags hupu,test --thumbnail covers/demo.png
```

Hupu currently supports login, account check and video upload. The title must be 4–40 characters. Image post upload and `--schedule` are not supported yet. Hupu login may require a QQ or phone-number login in the browser. When you need to look at the page by hand, add `--headed`.

## Login QR codes

- During login on Douyin, Kuaishou, Xiaohongshu, WeChat Channels, Baijiahao, Alipay Life Account, Weibo and Hupu, the CLI / uploader may generate a temporary QR code image
- An ordinary user can open that image directly and scan it
- For an agent that can work with local files, do not just tell the user the image path
- The QR code image is meant to be scanned by the user. The agent should show or send the local image to the user directly
- Bilibili and YouTube currently do not use this local QR-code image hosting flow. Handle their login as described in the platform sections above

## Scheduled publishing

`--schedule` is supported for image post or video upload on Douyin, Kuaishou, Xiaohongshu and WeChat Channels, for video upload on Bilibili, and for video and article upload on Dayu. Whenever `--schedule` is passed, the CLI automatically switches to that platform's scheduled publishing strategy. Without it, the default is to publish immediately. Dayu time is always Beijing time, between 2 hours and 7 days ahead, in 5-minute steps. Baijiahao, Alipay Life Account, Weibo and Hupu do not support `--schedule` for now.

```bash
sau douyin upload-video --account <account_name> --file videos/demo.mp4 --title "Sample title" --desc "Sample description" --schedule "2026-03-24 21:30"
sau douyin upload-note --account <account_name> --images videos/1.png videos/2.png --title "Image post title" --note "Image post example" --schedule "2026-03-24 21:30"
sau kuaishou upload-video --account <account_name> --file videos/demo.mp4 --title "Sample title" --desc "Sample description" --schedule "2026-03-24 21:30"
sau kuaishou upload-note --account <account_name> --images videos/1.png videos/2.png videos/3.png --title "Image post title" --note "Image post example" --schedule "2026-03-24 21:30"
sau xiaohongshu upload-video --account <account_name> --file videos/demo.mp4 --title "Sample title" --desc "Sample description" --schedule "2026-03-24 21:30"
sau xiaohongshu upload-note --account <account_name> --images videos/1.png videos/2.png videos/3.png --title "Image post title" --note "Image post example" --schedule "2026-03-24 21:30"
sau bilibili upload-video --account <account_name> --file videos/demo.mp4 --title "Sample title" --desc "Sample description" --tid 249 --schedule "2026-03-24 21:30"
sau tencent upload-video --account <account_name> --file videos/demo.mp4 --title "Sample title" --desc "Sample description" --schedule "2026-03-24 21:30"
```

## Runtime options

The CLI splits `debug` and `headless` into two independent dimensions:

```bash
--debug
--headless
--headed
```

- `--debug`: turns on debug behavior, for example keeping more debug information on failure
- `--headless`: run in headless mode
- `--headed`: run in headed mode

If none is passed, the CLI currently runs with `headless=True` by default.

Also:

- The Douyin and Kuaishou CLIs are both headless by default
- Only pass `--headed` explicitly if the user clearly asks for a visible browser window, or you really need to look at the page by hand

## Video upload options

```bash
--file videos/demo.mp4
--title "Sample title"
--desc "Sample description"
--tags sports,training
--thumbnail videos/demo.png
--thumbnail-landscape videos/cover-4x3.png
--thumbnail-portrait videos/cover-3x4.png
```

Douyin and WeChat Channels support setting covers in two aspect ratios at the same time:

- `--thumbnail-landscape`: 4:3 landscape cover
- `--thumbnail-portrait`: 3:4 portrait cover
- `--thumbnail`: legacy option kept for compatibility, equivalent to the 3:4 portrait cover

WeChat Channels, Baijiahao and Alipay Life Account support `--collection` to pick an existing collection. Baijiahao and Alipay Life Account also support `--thumbnail` to set the cover image.

Douyin additionally supports:

```bash
--product-link https://example.com/item
--product-title "Sample product"
```

Bilibili has an additional requirement:

```bash
--tid 249
```

- `--tid` is required in the first version
- `--tags` is mapped to `biliup upload --tag`
- `--schedule` is mapped to the timestamp option that Bilibili requires

## Image note upload options

```bash
--images videos/1.png videos/2.png videos/3.png
--title "Image post title"
--note "Image post content"
--tags image-post,test
```

Current limits for image note upload:

- Douyin: at most 35 images, GIF is not supported
- Kuaishou: multiple images are supported. Pass really different files and do not repeat the same path several times
- Xiaohongshu: multiple images are supported. The body `--note` is optional, but it is best to always pass `--title` explicitly

Dayu articles use `--content-file` to provide an HTML, Markdown or TXT body file. Local images and mixed text and images are supported, with a body of at most 20,000 characters. For source, cover and other options, see [Dayu image post publishing](./dayu-article.md).
