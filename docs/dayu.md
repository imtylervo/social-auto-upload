# Dayu Video Publishing Guide

Currently supported: login, account check, immediate or scheduled video publishing, and querying publish results. The Web UI is not connected yet. For publishing articles and rich-text body files, see [Dayu image post publishing](./dayu-article.md). For agent use, see the [Dayu Skill](../skills/dayu-upload/SKILL.md).

## First use

First install the project by following the [CLI installation guide](./CLI.md), and run commands from the project root. On Windows, if `sau` is not found, you can use `.\.venv\Scripts\sau.exe`.

```powershell
sau dayu login --account creator --expected-name "Your Dayu account name"
sau dayu check --account creator
```

Login opens Chrome. Complete the login in the web page. `creator` is the local name you give this account. Use the same name for later publishing. If the check returns `valid`, the account is usable. If it returns `invalid`, log in again.

## Before publishing

| Required item | Command option | Requirement |
| --- | --- | --- |
| Account | `--account` | Name of a logged-in local account |
| Video file | `--file` | Path to a local file. At least 5 seconds; for landscape video, 15 seconds or more is recommended |
| Video title | `--title` | 5–60 characters; English characters count as half a character |
| Video category | `--category` | Choose one of the 43 categories below |
| Video cover | `--thumbnail` | Path to an image related to the video, at most 5 MB; jpg, jpeg, png, gif or bmp |
| Information source | `--source` | Choose one of the sources below according to the real content |

Landscape video can be at most 10 GB. Portrait video can be at most 5 GB and no longer than 30 minutes. Supported file extensions are: 3gp, avi, flv, mp4, m3u8, mpg, asf, wmv, mkv, mov, ts, webm, mts. The file must decode normally on the local machine. The platform's own check has the final say on size limits. Real publishing has been verified for landscape video. Real publishing of portrait video has not been verified yet.

**Video categories** (from the page of the current account on 2026-10-17, 43 items). Pass the Chinese name exactly as shown; the English is only a gloss:

其他 (Other), 社会 (Society), 国内 (Domestic), 国际 (International), 体育 (Sports), 科技 (Technology), 娱乐 (Entertainment), 军事 (Military), 财经 (Finance), 汽车 (Auto), 房产 (Real estate), 时尚 (Fashion), 健康 (Health), 两性情感 (Relationships), 游戏 (Games), 动漫 (Anime), 旅游 (Travel), 美食 (Food), 历史 (History), 奇闻 (Odd news), 科学探索 (Science exploration), 星座 (Horoscope), 育儿 (Parenting), 教育 (Education), 美女 (Beauty), 搞笑 (Funny), 演讲 (Speeches), 萌娃 (Cute kids), 萌宠 (Cute pets), 音乐 (Music), 语言类 (Language), 记录短片 (Short documentaries), 涨姿势 (Learn something new), 劲爆体育 (Hot sports), 幽默 (Humor), 综艺 (Variety shows), 电视剧 (TV series), 电影 (Movies), 纪录片 (Documentaries), 少儿 (Children), 文化 (Culture), 三农 (Agriculture and rural affairs), 生活方式 (Lifestyle).

**Information source** (pass the Chinese option text exactly as shown):

| Page option | Support in the current command |
| --- | --- |
| 无需标注 (No label needed) | Supported. Real publishing verified |
| AI生成 (AI-generated) | Supported |
| 虚构演绎 (Fictional dramatization) | Can be filled in. Real publishing not verified separately yet |
| 营销信息 (Marketing information) | Can be filled in. Real publishing not verified separately yet |
| 转载 (Repost) | Can be filled in. You must also provide `--source-url "https://original-article-url"`. Real publishing not verified separately yet |
| 个人观点 (Personal opinion) | Can be filled in. Real publishing not verified separately yet |
| 不适宜未成年人 (Not suitable for minors) | Can be filled in. Real publishing not verified separately yet |

When you choose 转载 (Repost), the **original link is conditionally required**. Other sources do not need an original link.

## Publish immediately

The command below actually publishes the video. It returns success as soon as the platform confirms the publish, without waiting for review:

```powershell
# --category "科技" = Technology; --source "无需标注" = No label needed
sau dayu upload-video --account creator --file "D:\assets\video.mp4" --title "This is a Dayu video title" --category "科技" --source "无需标注" --thumbnail "D:\assets\cover.jpg"
```

If you need a description or tags, add these options:

```powershell
--desc "Video description, at most 200 characters" --tags "tag one,tag two"
```

Separate tags with an English comma. Each tag can have at most 10 characters.

## Scheduled publishing

Add `--schedule "YYYY-MM-DD HH:MM"` to the publish command. The time is always interpreted as **Beijing time (Asia/Shanghai, UTC+8)**, regardless of the time zone of the computer running it. It must be between 2 hours and 7 days after the current time, and the minutes must be a multiple of 5, for example `10:30` or `10:35`. The program does not round the time or switch to immediate publishing. Leave enough time for upload and processing: the time must still be in the allowed range when the form is filled in.

```powershell
# --category "科技" = Technology; --source "无需标注" = No label needed
sau dayu upload-video --account creator --file "D:\assets\video.mp4" --title "This is a Dayu video title" --category "科技" --source "无需标注" --thumbnail "D:\assets\cover.jpg" --schedule "2027-01-01 10:30"
```

Replace the example date with a time in the real allowed range. Without `--schedule`, the video is published immediately. The command returns success after the platform confirms the original work and the scheduled time. This means the **schedule has been submitted**. It does not wait for the time to arrive or for review. If review takes longer, the actual public time may be later than the scheduled time.

## Other features on the page

The table below follows the short-video publishing page of the account logged in this time. The platform may show different features depending on the account or the material.

| Page feature | Required | Support in the current command |
| --- | --- | --- |
| Video description | Optional | Supported, with `--desc` |
| Video tags | Optional | Supported, with `--tags` |
| Portrait cover | Optional | Not supported yet |
| Scheduled publishing | Optional | Supported, with `--schedule`; 2 hours to 7 days ahead in Beijing time, in 5-minute steps |
| Choose a video from the asset library | Optional material source | Not supported yet. The current command uses local files |
| Web preview | Optional action | The publishing process goes into the preview and confirms it. There is no separate preview command yet |
| Save draft, clear edited content | Optional actions | No corresponding command yet |

## Viewing the result

When the command prints "发表成功" (published successfully), the platform has confirmed this publish, and the result returns the work ID. It does not wait for review to pass or for public playback. The review result does not affect whether this publish counts as successful.

By default it waits up to 10 minutes for upload and processing. You can add `--upload-timeout 1200`, in seconds.

If the command could not confirm the publish result, for example because the connection dropped, use the result file named in the log to query the original work, to avoid publishing twice:

```powershell
sau dayu verify --account creator --result "cookies/dayu_results/this_result_file.json"
```

This command is read-only. It succeeds when it finds the submitted original work, and it also succeeds if the work is still under review. For a scheduled work, it also checks the scheduled time in the result file, and succeeds once the pending schedule is confirmed. If the log says there is no work information to query, check this work in the Dayu backend.

To additionally check public video playback, add `--public` and use `--timeout` to set the wait in seconds:

```powershell
sau dayu verify --account creator --result "cookies/dayu_results/this_result_file.json" --public --timeout 900
```

The public check may have to wait for review. It is a separate check and not a success condition of the publish command.

## Other command options

| Option | Purpose |
| --- | --- |
| `--headed` | Show the Chrome window used during publishing |
| `--prepare-only` | Upload the material, fill in the form and save a local screenshot, then stop. Used to check the content before publishing. Nothing is published and no web draft is saved |
| `--debug` | Save a page screenshot on error, to help troubleshooting |

Full option help: `sau dayu upload-video --help`.
