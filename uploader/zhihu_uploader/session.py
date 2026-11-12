"""Saving the Zhihu login session and checking the identity on the current page."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

from patchright.async_api import Page, async_playwright, expect

from conf import LOCAL_CHROME_PATH
from uploader.zhihu_uploader.constants import ZHIHU_CREATOR_URL


PROFILE_IMAGE = "button.AppHeader-profileEntry img[alt^='点击打开'][alt$='的主页']"  # alt = "click to open <name>'s home page"


async def read_zhihu_identity(page: Page) -> dict:
    """Read the display name and avatar URL from the logged-in avatar in the Zhihu header, as the binding info of the local session."""
    # AppHeader-profileEntry is the current-user entry actually shared by the creator center and the video page.
    profile = page.locator(PROFILE_IMAGE)
    await expect(profile).to_have_count(1, timeout=30000)
    await expect(profile).to_be_visible()
    label = (await profile.get_attribute("alt") or "").strip()
    name = label.removeprefix("点击打开").removesuffix("的主页").strip()
    avatar = profile.get_attribute("src")
    avatar_url = (await avatar or "").strip()
    if not name or not avatar_url:
        raise RuntimeError("The Zhihu header has no readable current account info")
    avatar_path = urlsplit(avatar_url).path
    if not avatar_path:
        raise RuntimeError("The Zhihu header avatar has no stable path; cannot bind the current session")
    return {"name": name, "avatar_path": avatar_path}


def load_zhihu_identity(account_file: str | Path) -> dict:
    """Read the Zhihu header info recorded at login, so another local account file is not used by mistake."""
    identity_file = Path(account_file).with_suffix(".identity.json")
    identity = json.loads(identity_file.read_text(encoding="utf-8"))
    if not identity.get("name") or not identity.get("avatar_path"):
        raise ValueError(f"Zhihu account binding is incomplete, please log in again: {identity_file}")
    return identity


async def login_zhihu_account(account_file: str | Path, timeout: int = 600) -> dict:
    """Log in in a visible Chrome, check the header account and then save the local storage state."""
    if timeout <= 0:
        raise ValueError("The login timeout must be greater than 0 seconds")
    account_file = Path(account_file).resolve()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            executable_path=LOCAL_CHROME_PATH or None, channel="chrome", headless=False,
        )
        try:
            context = await browser.new_context(timezone_id="Asia/Shanghai")
            page = await context.new_page()
            await page.goto(ZHIHU_CREATOR_URL, wait_until="domcontentloaded", timeout=45000)
            print("Complete the Zhihu login in the open Chrome; enter the account, password and captcha directly on the web page.", flush=True)
            await page.locator(PROFILE_IMAGE).wait_for(state="visible", timeout=timeout * 1000)
            identity = await read_zhihu_identity(page)
            identity_file = account_file.with_suffix(".identity.json")
            if identity_file.exists() and load_zhihu_identity(account_file) != identity:
                raise RuntimeError("The current Zhihu header differs from the bound session; use a new --account")
            account_file.parent.mkdir(parents=True, exist_ok=True)
            await context.storage_state(path=str(account_file))
            identity_file.write_text(json.dumps(identity, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"success": True, "account_file": str(account_file), "identity": identity}
        finally:
            await browser.close()


async def check_zhihu_account(account_file: str | Path, headless: bool = True) -> bool:
    """Report expired only when the page clearly goes back to the login path; network errors or an identity mismatch are reported directly."""
    account_file = Path(account_file)
    if not account_file.is_file():
        return False
    expected = load_zhihu_identity(account_file)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            executable_path=LOCAL_CHROME_PATH or None, channel="chrome", headless=headless,
        )
        try:
            context = await browser.new_context(storage_state=str(account_file), timezone_id="Asia/Shanghai")
            page = await context.new_page()
            response = await page.goto(ZHIHU_CREATOR_URL, wait_until="domcontentloaded", timeout=45000)
            if response is not None and response.status >= 400:
                raise RuntimeError(f"Failed to open the Zhihu creator center, HTTP {response.status}")
            target = urlsplit(page.url)
            if target.path.startswith(("/signin", "/account/unlogin")):
                return False
            actual = await read_zhihu_identity(page)
            if actual != expected:
                raise RuntimeError("The current Zhihu header does not match the local account binding")
            return True
        finally:
            await browser.close()
