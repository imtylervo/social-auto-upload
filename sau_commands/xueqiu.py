"""Command arguments and execution logic for xueqiu."""
from __future__ import annotations
import json
from uploader.xueqiu_uploader.article import XueqiuArticle
from uploader.xueqiu_uploader.constants import XUEQIU_DECLARATIONS, XUEQIU_VISIBILITY
from uploader.xueqiu_uploader.session import check_xueqiu_account, login_xueqiu_account
from uploader.xueqiu_uploader.verification import verify_xueqiu_result
from sau_commands.arguments import (
    SCHEDULE_FORMAT,
    add_runtime_flags,
    existing_file_path,
    resolve_account_file,
)


def register(platform_parsers):
    """Declare this platform's commands, arguments and allowed options."""
    schedule_help = SCHEDULE_FORMAT.replace("%", "%%")
    xueqiu_parser = platform_parsers.add_parser("xueqiu", help="Xueqiu creator center long-form posts with images")
    xueqiu_actions = xueqiu_parser.add_subparsers(dest="action", required=True)
    xueqiu_login = xueqiu_actions.add_parser("login", help="Log in in a visible Chrome and save the local session")
    xueqiu_login.add_argument("--account", required=True, help="Local account alias")
    xueqiu_login.add_argument("--expected-name", help="Expected Xueqiu nickname")
    xueqiu_login.add_argument("--timeout", type=int, default=600, help="Seconds to wait for login")
    xueqiu_check = xueqiu_actions.add_parser("check", help="Check the login state and the bound user ID")
    xueqiu_check.add_argument("--account", required=True)
    add_runtime_flags(xueqiu_check)
    xueqiu_check.set_defaults(headless=False)
    xueqiu_verify = xueqiu_actions.add_parser("verify", help="Look up the original post from the result file, without publishing again")
    xueqiu_verify.add_argument("--account", required=True)
    xueqiu_verify.add_argument("--result", required=True, type=existing_file_path)
    add_runtime_flags(xueqiu_verify)
    xueqiu_verify.set_defaults(headless=False)
    xueqiu_article = xueqiu_actions.add_parser("upload-article", help="HTML/Markdown/TXT long-form post, with images kept in their original positions")
    xueqiu_article.add_argument("--account", required=True)
    xueqiu_article.add_argument("--title", required=True, help="Non-empty single-line title")
    xueqiu_article.add_argument("--content-file", required=True, type=existing_file_path, help="UTF-8 HTML/Markdown/TXT; images go where they are placed in the draft")
    xueqiu_article.add_argument("--cover", type=existing_file_path, help="Separate cover image; the platform's default crop area is used")
    xueqiu_article.add_argument("--visibility", choices=XUEQIU_VISIBILITY, default="公开", help="Sharing scope")
    xueqiu_article.add_argument("--declaration", choices=XUEQIU_DECLARATIONS, required=True, help="Choose according to how the content was actually created")
    xueqiu_article.add_argument("--prepare-only", action="store_true", help="Stop after checking the preview; Xueqiu saves a remote draft automatically")
    add_runtime_flags(xueqiu_article)
    # Real acceptance runs on this machine use a visible Chrome; headless access has triggered download/access blocking before. Users can choose explicitly.
    xueqiu_article.set_defaults(headless=False)


async def run(args):
    """Run this platform's command; the platform implementation verifies the publish result."""
    account_file = resolve_account_file("xueqiu", args.account)
    if args.action == "login":
        result = await login_xueqiu_account(account_file, args.expected_name, args.timeout)
    elif args.action == "check":
        valid = await check_xueqiu_account(account_file, args.headless)
        print("valid" if valid else "invalid")
        return 0 if valid else 1
    elif args.action == "verify":
        result = await verify_xueqiu_result(account_file, args.result, args.headless)
    else:
        app = XueqiuArticle(
            title=args.title, content_file=args.content_file, account_file=account_file,
            visibility=args.visibility, declaration=args.declaration,
            prepare_only=args.prepare_only, headless=args.headless, debug=args.debug,
            cover=args.cover,
        )
        result = await app.main()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
