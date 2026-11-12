"""Xueqiu login and account binding; network failures and a clear logout are handled separately."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from patchright.async_api import Page, async_playwright, expect

from conf import LOCAL_CHROME_PATH
from uploader.xueqiu_uploader.constants import XUEQIU_HOME_URL


async def read_xueqiu_identity(page: Page) -> dict:
    """The header data-id is the current user ID; the nickname is for display and is not used to compare identity."""
    # header-user is the fixed account area of the logged-in header; data-id can be read both on the home page and in the long-post editor.
    user = page.locator("nav .header-user[data-id]")
    await expect(user).to_have_count(1, timeout=30000)
    await expect(user).to_be_visible()
    uid = await user.get_attribute("data-id")
    # The span inside the user area holds the nickname, excluding identical names that may appear in the sidebar or the body.
    name = (await user.locator("span").inner_text()).strip()
    if not re.fullmatch(r"[1-9][0-9]*", uid or "") or not name:
        raise RuntimeError("The Xueqiu header has no identity; cannot verify the publishing account")
    return {"uid": uid, "name": name}


def load_xueqiu_identity(account_file: str | Path) -> dict:
    """Restore the real user ID bound at login; unbound accounts are rejected."""
    path = Path(account_file).with_suffix(".identity.json")
    identity = json.loads(path.read_text(encoding="utf-8"))
    if not re.fullmatch(r"[1-9][0-9]*", identity.get("uid", "")) or not identity.get("name"):
        raise ValueError(f"Xueqiu account binding is incomplete, please log in again: {path}")
    return identity


async def login_xueqiu_account(account_file: str | Path, expected_name=None, timeout=600) -> dict:
    """Log in in a separate visible Chrome; the user completes account, password, terms and captcha on the web page."""
    if timeout <= 0:
        raise ValueError("The login timeout must be greater than 0 seconds")
    account_file = Path(account_file).resolve()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            executable_path=LOCAL_CHROME_PATH or None, channel="chrome", headless=False,
        )
        try:
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(XUEQIU_HOME_URL, wait_until="domcontentloaded", timeout=45000)
            print("Complete the Xueqiu login in Chrome, then open the creator center; the login state will be saved to the local account file.", flush=True)
            # Wait only for the observed creator header; the login form disappearing or a cookie appearing does not prove the login finished.
            await page.locator("nav .header-user[data-id]").wait_for(state="visible", timeout=timeout * 1000)
            identity = await read_xueqiu_identity(page)
            if expected_name is not None and identity["name"] != expected_name:
                raise RuntimeError("The Xueqiu nickname does not match --expected-name")
            binding = account_file.with_suffix(".identity.json")
            if binding.exists() and load_xueqiu_identity(account_file)["uid"] != identity["uid"]:
                raise RuntimeError("The current Xueqiu account differs from the bound account; use a new --account")
            account_file.parent.mkdir(parents=True, exist_ok=True)
            await context.storage_state(path=str(account_file))
            binding.write_text(json.dumps(identity, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"success": True, "account_file": str(account_file), "identity": identity}
        finally:
            await browser.close()


async def check_xueqiu_account(account_file: str | Path, headless=False) -> bool:
    """Report expired only when the page clearly goes to the login page; 403, network timeouts and ambiguous identity raise errors directly."""
    account_file = Path(account_file)
    if not account_file.is_file():
        return False
    expected = load_xueqiu_identity(account_file)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            executable_path=LOCAL_CHROME_PATH or None, channel="chrome", headless=headless,
        )
        try:
            context = await browser.new_context(storage_state=str(account_file))
            page = await context.new_page()
            response = await page.goto(XUEQIU_HOME_URL, wait_until="domcontentloaded", timeout=45000)
            if response is not None and response.status >= 400:
                raise RuntimeError(f"Xueqiu request failed, HTTP {response.status}; this does not mean the login expired")
            target = urlsplit(page.url)
            if target.hostname in {"xueqiu.com", "www.xueqiu.com"} and target.path == "/account/login":
                return False
            actual = await read_xueqiu_identity(page)
            if actual["uid"] != expected["uid"]:
                raise RuntimeError("The Xueqiu session identity does not match the local binding")
            return True
        finally:
            await browser.close()
