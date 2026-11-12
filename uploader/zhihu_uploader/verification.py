"""Read-only verification of a Zhihu post after submission."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from patchright.async_api import async_playwright, expect

from conf import LOCAL_CHROME_PATH
from uploader.zhihu_uploader.session import load_zhihu_identity, read_zhihu_identity


async def verify_zhihu_result(account_file, result_file, headless=False) -> dict:
    """Open the post URL saved in the result file, read-only; without a URL, ask for the original post to be looked up in the creator center first."""
    account_file = Path(account_file).resolve()
    result_file = Path(result_file).resolve()
    result = json.loads(result_file.read_text(encoding="utf-8"))
    expected = load_zhihu_identity(account_file)
    if result.get("identity") != expected:
        raise ValueError("The result file does not match the current Zhihu account binding")
    url = result.get("url")
    if not url:
        raise ValueError(
            "The result file has no Zhihu post URL; find the original post by title and submission time under content management in the creator center, do not upload again"
        )
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in {"www.zhihu.com", "zhuanlan.zhihu.com"}:
        raise ValueError("The Zhihu post URL in the result file is not supported")
    if not re.search(r"/(?:p|pin|zvideo|video)/\d+/?$", parsed.path):
        raise ValueError("The result file URL contains no Zhihu article or video post ID")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            executable_path=LOCAL_CHROME_PATH or None, channel="chrome", headless=headless,
        )
        try:
            context = await browser.new_context(storage_state=str(account_file), timezone_id="Asia/Shanghai")
            page = await context.new_page()
            response = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            if response is not None and response.status >= 400:
                raise RuntimeError(f"Failed to open the original Zhihu post URL, HTTP {response.status}")
            if await read_zhihu_identity(page) != expected:
                raise RuntimeError("The Zhihu header during verification does not match the local account binding")
            title = result.get("title")
            if not title:
                raise ValueError("The result file has no title; cannot check the original post")
            # The new video detail page puts title and description in the same body area, with a separator after the title.
            await expect(page.locator("main")).to_contain_text(title, timeout=30000)
            result.update(success=True, status="published", verified=True)
            result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return result
        finally:
            await browser.close()
