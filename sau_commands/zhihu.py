"""Command arguments and execution logic for zhihu."""
from __future__ import annotations
import json
from uploader.zhihu_uploader.article import ZhihuArticle
from uploader.zhihu_uploader.constants import (
    ZHIHU_SCHEDULE_MAX_HOURS,
    ZHIHU_SCHEDULE_MINUTES,
    ZHIHU_ORIGINALITY,
    ZHIHU_VIDEO_CATEGORIES,
    ZHIHU_VIDEO_MARKS,
)
from uploader.zhihu_uploader.session import check_zhihu_account, login_zhihu_account
from uploader.zhihu_uploader.verification import verify_zhihu_result
from uploader.zhihu_uploader.video import ZhihuVideo
from sau_commands.arguments import (
    SCHEDULE_FORMAT,
    add_runtime_flags,
    existing_file_path,
    resolve_account_file,
    schedule_value,
)


def register(platform_parsers):
    """Declare this platform's commands, arguments and allowed options."""
    schedule_help = SCHEDULE_FORMAT.replace("%", "%%")
    zhihu_parser = platform_parsers.add_parser("zhihu", help="Zhihu creator center article and video publishing")
    zhihu_actions = zhihu_parser.add_subparsers(dest="action", required=True)
    zhihu_login = zhihu_actions.add_parser("login", help="Log in in a visible Chrome and save the local session")
    zhihu_login.add_argument("--account", required=True, help="Local session alias; may differ from the Zhihu display name")
    zhihu_login.add_argument("--timeout", type=int, default=600, help="Seconds to wait for login")
    zhihu_check = zhihu_actions.add_parser("check", help="Check the Zhihu login state and the account binding shown in the page header")
    zhihu_check.add_argument("--account", required=True, help="Local session alias")
    add_runtime_flags(zhihu_check)
    zhihu_check.set_defaults(headless=False)
    zhihu_verify = zhihu_actions.add_parser("verify", help="Read-only check of the submission result using the saved post URL")
    zhihu_verify.add_argument("--account", required=True, help="Local session alias")
    zhihu_verify.add_argument("--result", required=True, type=existing_file_path)
    add_runtime_flags(zhihu_verify)
    zhihu_verify.set_defaults(headless=False)
    zhihu_article = zhihu_actions.add_parser("upload-article", help="Publish a Zhihu article; content images go where they are placed in the draft")
    zhihu_article.add_argument("--account", required=True, help="Local session alias")
    zhihu_article.add_argument("--title", required=True, help="Article title, at most 100 characters")
    zhihu_article.add_argument("--content-file", required=True, type=existing_file_path, help="UTF-8 HTML/Markdown/TXT; write image paths in the matching paragraphs of the draft")
    zhihu_article.add_argument("--schedule", type=schedule_value,
                               help=f"Experimental scheduled publishing, format {schedule_help}, Beijing time, {ZHIHU_SCHEDULE_MINUTES} minutes to {ZHIHU_SCHEDULE_MAX_HOURS} hours from now")
    zhihu_article.add_argument("--prepare-only", action="store_true", help="Stop after filling in and checking the editor, without clicking publish")
    zhihu_article.add_argument("--upload-timeout", type=int, default=600, help="Seconds to wait for each content image upload")
    add_runtime_flags(zhihu_article)
    zhihu_article.set_defaults(headless=False)
    zhihu_video = zhihu_actions.add_parser("upload-video", help="Upload and publish one Zhihu video")
    zhihu_video.add_argument("--account", required=True, help="Local session alias")
    zhihu_video.add_argument("--file", required=True, type=existing_file_path, help="Video file, larger than 100KB, at most 20GB and 4 hours long")
    zhihu_video.add_argument("--title", required=True, help="Video title, 5–50 characters")
    zhihu_video.add_argument("--desc", default="", help="Optional video description, at most 300 characters")
    zhihu_video.add_argument("--category", choices=ZHIHU_VIDEO_CATEGORIES,
                             help="Field (topic area); when omitted, choose it by number in the terminal; checked against the live menu before submitting")
    zhihu_video.add_argument("--video-mark", choices=ZHIHU_VIDEO_MARKS,
                             help="Video declaration; when omitted, choose it by number in the terminal")
    zhihu_video.add_argument("--show-options", action="store_true", help="After uploading the media, list all fields and video marks, save them to the result JSON and exit without publishing")
    zhihu_video.add_argument("--originality", choices=ZHIHU_ORIGINALITY, required=True,
                             help="Whether the content is original or a repost")
    zhihu_video.add_argument("--schedule", type=schedule_value,
                             help=f"Experimental scheduled publishing, format {schedule_help}, Beijing time, {ZHIHU_SCHEDULE_MINUTES} minutes to {ZHIHU_SCHEDULE_MAX_HOURS} hours from now")
    zhihu_video.add_argument("--prepare-only", action="store_true", help="Stop after uploading and filling in, without clicking publish")
    zhihu_video.add_argument("--upload-timeout", type=int, default=1200, help="Seconds to wait for the video upload")
    add_runtime_flags(zhihu_video)
    zhihu_video.set_defaults(headless=False)


async def run(args):
    """Run this platform's command; the platform implementation verifies the publish result."""
    account_file = resolve_account_file("zhihu", args.account)
    if args.action == "login":
        result = await login_zhihu_account(account_file, args.timeout)
    elif args.action == "check":
        valid = await check_zhihu_account(account_file, args.headless)
        print("valid" if valid else "invalid")
        return 0 if valid else 1
    elif args.action == "verify":
        result = await verify_zhihu_result(account_file, args.result, args.headless)
    elif args.action == "upload-article":
        app = ZhihuArticle(
            title=args.title, content_file=args.content_file, account_file=account_file,
            schedule=args.schedule, prepare_only=args.prepare_only,
            upload_timeout=args.upload_timeout, headless=args.headless, debug=args.debug,
        )
        result = await app.main()
    else:
        app = ZhihuVideo(
            title=args.title, file_path=args.file, account_file=account_file,
            description=args.desc, category=args.category,
            topics=[], video_mark=args.video_mark, show_options=args.show_options,
            originality=args.originality, schedule=args.schedule,
            prepare_only=args.prepare_only, upload_timeout=args.upload_timeout,
            headless=args.headless, debug=args.debug,
        )
        result = await app.main()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
