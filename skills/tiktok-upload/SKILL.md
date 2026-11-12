---
name: tiktok-upload
description: Use the repository's existing Patchright/Playwright Chrome uploader to log in and publish TikTok videos. Use when the user wants to publish a TikTok video and the current environment can access this repository and its local Chrome configuration.
license: MIT-0
slug: social-auto-upload-tiktok-upload
displayName: TikTok video publishing
version: 1.0.0
summary: Log in and publish TikTok videos with the repository's Chrome uploader.
---

# TikTok video publishing

TikTok currently has no `sau tiktok` command. Use the repository's `uploader/tk_uploader/main_chrome.py`; do not invent CLI arguments. Before running, confirm the repository dependencies, the Chrome configuration in `conf.py` and the video path provided by the user.

The account session is stored in `cookies/tk_uploader/account.json`. For the first login, see `examples/get_tk_cookie.py`; the user logs in personally on the TikTok page. Do not read, copy or commit the cookie file.

For a single video, prefer the repository API flow below, using `publish_date=0` to mean publish immediately:

```python
import asyncio
from pathlib import Path
from conf import BASE_DIR
from uploader.tk_uploader.main_chrome import TiktokVideo, tiktok_setup

account_file = Path(BASE_DIR) / "cookies" / "tk_uploader" / "account.json"
video_file = Path(BASE_DIR) / "videos" / "demo.mp4"
asyncio.run(tiktok_setup(str(account_file), handle=True))
app = TiktokVideo("标题", str(video_file), ["标签"], 0, str(account_file))
asyncio.run(app.main())
```

`TiktokVideo` has no separate description parameter. For scheduled publishing, pass an explicit `datetime`; do not work out the time yourself. The repository's `examples/upload_video_to_tiktok.py` processes all MP4 files in a directory in bulk, extracts the title and tags from the files automatically, and schedules publishing for 16:00 the next day. Do not run that script directly unless the user explicitly asks for these behaviors.

Before each publish, have the user confirm the account, the single video, the title, the tags and whether to publish immediately or on a schedule. If the page layout or login state is not as expected, stop and report. Report success only after the platform page confirms the submission; for an unknown result, check TikTok Studio first and do not resend directly.
