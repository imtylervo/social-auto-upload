---
name: youtube-upload
description: Use social-auto-upload's `sau youtube` to log in to YouTube and upload videos, schedule them or set their visibility. Use when the user wants to publish or schedule a video on YouTube, or check the Google/YouTube login state.
license: MIT-0
slug: social-auto-upload-youtube-upload
displayName: YouTube video publishing
version: 1.0.0
summary: Log in to YouTube with sau and upload or schedule videos.
---

# YouTube video publishing

Call the existing `sau youtube` CLI. Login is done by signing in to a Google account in the browser, without a QR code. The account name is a local session alias.

```powershell
sau youtube login --account creator
sau youtube check --account creator
sau youtube upload-video --account creator --file videos/demo.mp4 --title "标题" --desc "简介" --tags tag1,tag2 --visibility public
```

The title is at most 100 characters. `--visibility` accepts `public`, `unlisted` or `private`, and defaults to `public`; `--thumbnail` sets the cover and `--playlist` sets an existing playlist. Pass `--schedule "YYYY-MM-DD HH:MM"` only when the user explicitly gives a scheduled time; this option uses the Schedule state in YouTube Studio, so check the date and time shown on the page.

Before publishing, check again the account, video, title, description, tags, visibility, and whether the intent is immediate or scheduled. If an upload or publish times out, check the original video in YouTube Studio first and do not re-upload blindly. A successful upload does not mean review is finished or that the public video is already playable.
