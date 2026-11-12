"""Command arguments and execution logic for dayu."""
from __future__ import annotations
import json
from patchright.async_api import async_playwright
from conf import LOCAL_CHROME_PATH
from utils.article_render import ARTICLE_THEMES
from uploader.dayu_uploader.article import DayuArticle
from uploader.dayu_uploader.constants import (
    DAYU_SOURCE_TYPES,
    DAYU_VIDEO_CATEGORIES,
    DAYU_SCHEDULE_MIN_HOURS,
    DAYU_SCHEDULE_MAX_DAYS,
    DAYU_SCHEDULE_STEP_MINUTES,
)
from uploader.dayu_uploader.main import DayuVideo
from uploader.dayu_uploader.session import (
    DAYU_HOME_URL,
    check_dayu_account,
    load_dayu_identity,
    login_dayu_account,
    read_dayu_identity,
)
from uploader.dayu_uploader.verification import verify_dayu_article, verify_dayu_video
from sau_commands.arguments import (
    SCHEDULE_FORMAT,
    add_runtime_flags,
    existing_file_path,
    parse_tags,
    resolve_account_file,
    schedule_value,
)


def register(platform_parsers):
    """Declare this platform's commands, arguments and allowed options."""
    schedule_help = SCHEDULE_FORMAT.replace("%", "%%")
    dayu_parser = platform_parsers.add_parser("dayu", help="Dayu (大鱼号) video publishing and verification")
    dayu_actions = dayu_parser.add_subparsers(dest="action", required=True)
    dayu_login = dayu_actions.add_parser("login", help="Log in manually with visible Chrome")
    dayu_login.add_argument("--account", required=True, help="Local account alias")
    dayu_login.add_argument("--expected-name", help="Expected name displayed by Dayu")
    dayu_login.add_argument("--timeout", type=int, default=600, help="Login timeout in seconds")
    dayu_check = dayu_actions.add_parser("check", help="Check login and bound Dayu identity")
    dayu_check.add_argument("--account", required=True)
    dayu_upload = dayu_actions.add_parser("upload-video", help="Publish a video; succeed when Dayu confirms submission")
    dayu_upload.add_argument("--account", required=True)
    dayu_upload.add_argument("--file", required=True, type=existing_file_path)
    dayu_upload.add_argument("--title", required=True, help="Title, 5-60 Chinese character units")
    dayu_upload.add_argument("--desc", default="")
    dayu_upload.add_argument("--tags", default="", help="Comma-separated tags")
    dayu_upload.add_argument("--category", required=True, choices=DAYU_VIDEO_CATEGORIES, help="Video category, chosen from the page's options")
    dayu_upload.add_argument("--source", required=True, choices=DAYU_SOURCE_TYPES, help="Information source; choose it according to the actual content")
    dayu_upload.add_argument("--source-url", default="", help="http/https link to the original, required for reposts")
    dayu_upload.add_argument("--thumbnail", required=True, type=existing_file_path)
    dayu_upload.add_argument("--schedule", type=schedule_value,
                            help=f"{schedule_help}, Beijing time, {DAYU_SCHEDULE_MIN_HOURS} hours to {DAYU_SCHEDULE_MAX_DAYS} days from now, minutes a multiple of {DAYU_SCHEDULE_STEP_MINUTES}")
    dayu_upload.add_argument("--prepare-only", action="store_true", help="Upload and fill only; do not click publish")
    dayu_upload.add_argument("--upload-timeout", type=int, default=600, help="Upload/processing timeout in seconds")
    add_runtime_flags(dayu_upload)
    dayu_article = dayu_actions.add_parser("upload-article", help="Publish an image post from a content file; reports success once the platform confirms publication")
    dayu_article.add_argument("--account", required=True, help="Name of a logged-in local account")
    dayu_article.add_argument("--title", required=True, help="Image post title, 5–50 characters")
    dayu_article.add_argument("--content-file", required=True, type=existing_file_path, help="UTF-8 HTML, Markdown or TXT content file")
    dayu_article.add_argument("--theme", choices=ARTICLE_THEMES, help="Markdown rendering theme, default is default; published with a Dayu-compatible layout")
    dayu_article.add_argument("--source", required=True, choices=DAYU_SOURCE_TYPES, help="Information source; choose it according to the actual content")
    dayu_article.add_argument("--source-url", default="", help="http/https link to the original, required for reposts")
    dayu_article.add_argument("--author", help="Optional author name; when omitted, the value already on the page is kept")
    dayu_article.add_argument("--cover-indices", nargs="+", type=int, help="Optional 1 or 3 content image numbers (starting at 1), for a single cover or three covers")
    dayu_article.add_argument("--schedule", type=schedule_value,
                             help=f"{schedule_help}, Beijing time, {DAYU_SCHEDULE_MIN_HOURS} hours to {DAYU_SCHEDULE_MAX_DAYS} days from now, minutes a multiple of {DAYU_SCHEDULE_STEP_MINUTES}")
    dayu_article.add_argument("--prepare-only", action="store_true", help="Stop after uploading and filling in, without publishing")
    dayu_article.add_argument("--upload-timeout", type=int, default=600, help="Seconds to wait for each image upload")
    add_runtime_flags(dayu_article)
    dayu_verify = dayu_actions.add_parser("verify", help="Check an existing publication without uploading again")
    dayu_verify.add_argument("--account", required=True)
    dayu_verify.add_argument("--type", choices=("video", "article"), help="Work type; detected automatically when a result file is used, otherwise defaults to video")
    dayu_target = dayu_verify.add_mutually_exclusive_group(required=True)
    dayu_target.add_argument("--content-id", help="Published content_id returned by Dayu")
    dayu_target.add_argument("--origin-id", help="Draft ID captured before confirming publication")
    dayu_target.add_argument("--result", type=existing_file_path, help="Saved Dayu result JSON to recover")
    dayu_verify.add_argument("--public", action="store_true", help="Also wait for review, then check the public content or playback; does not affect whether the publish command counts as successful")
    dayu_verify.add_argument("--timeout", type=int, default=60)
    add_runtime_flags(dayu_verify)


async def run(args):
    """Run this platform's command; the platform implementation verifies the publish result."""
    account_file = resolve_account_file("dayu", args.account)
    if args.action == "login":
        if args.timeout <= 0:
            raise ValueError("Login timeout must be greater than 0 seconds")
        result = await login_dayu_account(account_file, args.expected_name, args.timeout)
    elif args.action == "check":
        valid = await check_dayu_account(account_file)
        print("valid" if valid else "invalid")
        return 0 if valid else 1
    elif args.action == "upload-video":
        app = DayuVideo(
            title=args.title, file_path=args.file, tags=parse_tags(args.tags),
            account_file=account_file, thumbnail_path=args.thumbnail, category=args.category,
            source=args.source, desc=args.desc, headless=args.headless, debug=args.debug,
            prepare_only=args.prepare_only, upload_timeout=args.upload_timeout,
            source_url=args.source_url, schedule=args.schedule,
        )
        result = await app.main()
    elif args.action == "upload-article":
        app = DayuArticle(
            title=args.title, content_file=args.content_file, account_file=account_file,
            source=args.source, source_url=args.source_url, author=args.author,
            theme=args.theme, schedule=args.schedule,
            cover_indices=args.cover_indices, headless=args.headless, debug=args.debug,
            prepare_only=args.prepare_only, upload_timeout=args.upload_timeout,
        )
        result = await app.main()
    elif args.action == "verify":
        if args.timeout <= 0:
            raise ValueError("Verification timeout must be greater than 0 seconds")
        saved = json.loads(args.result.read_text(encoding="utf-8")) if args.result else {}
        expected = load_dayu_identity(account_file)
        if saved and saved.get("identity", {}).get("wmid") != expected["wmid"]:
            raise RuntimeError("The result file does not match the selected Dayu account")
        kind = args.type or saved.get("type", "video")
        if saved.get("type") and saved["type"] != kind:
            raise ValueError("The given work type does not match the result file")
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                executable_path=LOCAL_CHROME_PATH or None, channel="chrome", headless=args.headless,
            )
            try:
                context = await browser.new_context(storage_state=str(account_file))
                page = await context.new_page()
                await page.goto(DAYU_HOME_URL, wait_until="domcontentloaded", timeout=45000)
                identity = await read_dayu_identity(page)
                if identity["wmid"] != expected["wmid"]:
                    raise RuntimeError("During verification the Dayu account did not match the account binding")
                if kind == "article":
                    result = await verify_dayu_article(
                        context, browser, identity,
                        content_id=args.content_id or saved.get("content_id"),
                        origin_id=args.origin_id or saved.get("origin_id"),
                        title=saved.get("title"), timeout=args.timeout, manifest=saved.get("manifest"), public=args.public,
                        schedule=saved.get("schedule"),
                    )
                else:
                    result = await verify_dayu_video(
                        context, browser, identity,
                        content_id=args.content_id or saved.get("content_id"),
                        origin_id=args.origin_id or saved.get("origin_id"),
                        title=saved.get("title"), timeout=args.timeout, public=args.public,
                        schedule=saved.get("schedule"),
                    )
                if args.result:
                    saved.update(result)
                    saved.pop("error", None)
                    args.result.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
            finally:
                await browser.close()
    else:
        raise RuntimeError(f"Unsupported Dayu action: {args.action}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
