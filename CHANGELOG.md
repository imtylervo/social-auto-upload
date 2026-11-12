# Changelog

The project publishes reusable versions through GitHub Releases. Day-to-day merges are recorded here first, and the matching version's entries are copied into the Release notes at release time.

## [Unreleased]

### TikTok (Chrome version)

- Adapted to the 2026-11 TikTok Studio upload form: the publish button now uses `data-e2e="post_video_button"` (the old selector is kept as a fallback).
- Automatically close pop-ups that cover the form ("Turn on automatic content checks?" is answered with Cancel, so account settings are not turned on for the user).
- `TiktokVideo` gains the optional parameters `privacy` (`Everyone` / `Friends` / `Only you`) and `proxy` (Playwright proxy configuration).
- Added `upload_on_page(page)` / `fill_form(page)`: the flow can run on an already logged-in Playwright page supplied from outside (other browsers, persistent profiles, proxies).
- Added `delete_video(page, video_id)`: deletes the given video from the TikTok Studio content list.
- `detect_upload_status` and `click_publish` now have a timeout and raise `TimeoutError` on failure instead of looping forever.

### Structure and CLI

- Split `sau_cli.py` from a single monolithic entry point into per-platform command modules under `sau_commands/`; the entry point now only registers and dispatches.
- The README, CLI docs and Skills now organize publishing entry points by platform and by the three content types: video, article and image post.
- Removed the Zhihu `--expected-name` parameter, which had no practical use; login now reads the identity on the current page directly and saves the account binding information.
- The Zhihu article final-URL check now excludes `/edit` draft addresses, so an autosaved draft is no longer reported as published.

### Zhihu articles

- Supports HTML, Markdown and TXT sources. Body images are uploaded at their positions in the source instead of being appended to the end.
- Supports checking h2 headings, bold text, numbered lists, quotes and external links in Zhihu's real editor.
- PNG images go through the clipboard paste path; text, image order, formatting and links are checked before publishing.

### Zhihu videos

- The CLI provides the full lists of category and video-declaration options, and supports checking against the live menu, selecting by number, and querying with `--show-options`.
- Videos of 100KB or smaller are rejected before upload.
- Fixed the publish-success check: it now reads the `/pin/<post ID>` detail link opened by the success dialog, and keeps the published status if reading the link fails.
- Post lookup is compatible with the new video links; scheduled publishing is marked as experimental.

## Release process

1. Record user-visible changes and verification results under `Unreleased`.
2. Update `project.version` in `pyproject.toml`, following `MAJOR.MINOR.PATCH`.
3. Run the targeted tests, `git diff --check` and the build checks.
4. Create the version commit and the `v<version>` tag, and push them to GitHub.
5. Create a Release with the same name on GitHub, paste this version's log into the Release notes, and keep the verification scope and known limitations.

Before a release, any capability that has not passed real-platform acceptance must be explicitly marked "pending acceptance" and must not be listed as supported.
