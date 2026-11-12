"""Dayu login state and publishing identity checks; a network timeout is not treated as an expired login."""
from __future__ import annotations

import json
import re
from pathlib import Path

from patchright.async_api import Page, async_playwright, expect

from conf import LOCAL_CHROME_PATH

DAYU_HOME_URL = "https://mp.dayu.com/dashboard/index"
DAYU_VIDEO_URL = "https://mp.dayu.com/dashboard/video/write"


async def read_dayu_identity(page: Page) -> dict:
    """Read the current identity from the dashboard header and the server-injected wmid; reject missing or ambiguous values."""
    # The header account area shows the current publishing identity; restricting to header-info excludes same-named text in article authors and the content list.
    name = page.locator(".header-info .name")
    await expect(name).to_have_count(1)
    await expect(name).to_be_visible()
    scripts = "\n".join(await page.locator("script:not([src])").all_text_contents())
    ids = set(re.findall(r'''["']?wmid["']?\s*:\s*["']([a-f0-9]{32})["']''', scripts))
    if len(ids) != 1:
        raise RuntimeError("Cannot uniquely identify the Dayu account wmid; check the login state or the page structure")
    account_name = (await name.inner_text()).strip()
    if not account_name:
        raise RuntimeError("Dayu header account name is empty")
    return {"wmid": ids.pop(), "name": account_name}


def load_dayu_identity(account_file: str | Path) -> dict:
    """Read the identity binding saved at login; a local account alias cannot stand in for the platform identity."""
    identity_file = Path(account_file).with_suffix(".identity.json")
    identity = json.loads(identity_file.read_text(encoding="utf-8"))
    if not re.fullmatch(r"[a-f0-9]{32}", identity.get("wmid", "")) or not identity.get("name"):
        raise ValueError(f"Dayu identity binding is incomplete, please log in again: {identity_file}")
    return identity


async def login_dayu_account(account_file: str | Path, expected_name: str | None = None,
                             timeout: int = 600) -> dict:
    """The user logs in in a visible Chrome; the identity is checked before the state is saved. Captchas are completed by the user."""
    account_file = Path(account_file).resolve()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            executable_path=LOCAL_CHROME_PATH or None, channel="chrome", headless=False,
        )
        try:
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto("https://mp.dayu.com/", wait_until="domcontentloaded", timeout=45000)
            print("Complete the Dayu login in Chrome; enter the account, password and captcha directly on the web page.", flush=True)
            await page.wait_for_url("https://mp.dayu.com/dashboard/**", timeout=timeout * 1000)
            identity = await read_dayu_identity(page)
            if expected_name is not None and identity["name"] != expected_name:
                raise RuntimeError(f"Logged-in identity does not match, expected {expected_name}, got {identity['name']}")
            identity_file = account_file.with_suffix(".identity.json")
            if identity_file.exists() and load_dayu_identity(account_file)["wmid"] != identity["wmid"]:
                raise RuntimeError("The current Dayu account differs from the bound identity; refusing to overwrite the original account. Use a new --account")
            account_file.parent.mkdir(parents=True, exist_ok=True)
            await context.storage_state(path=str(account_file))
            identity_file.write_text(json.dumps(identity, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"success": True, "account_file": str(account_file), "identity": identity}
        finally:
            await browser.close()


async def check_dayu_account(account_file: str | Path) -> bool:
    """Restore the login state and compare the wmid; report expired only when the page clearly goes back to the login iframe."""
    account_file = Path(account_file)
    if not account_file.is_file():
        return False
    expected = load_dayu_identity(account_file)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            executable_path=LOCAL_CHROME_PATH or None, channel="chrome", headless=True,
        )
        try:
            context = await browser.new_context(storage_state=str(account_file))
            page = await context.new_page()
            await page.goto(DAYU_HOME_URL, wait_until="domcontentloaded", timeout=45000)
            # The CAS domain and path of the login iframe identify the auth page; the mere presence of some iframe does not mean the login expired.
            if await page.locator('iframe[src*="uop.dayu.com/cas/"]').count():
                return False
            actual = await read_dayu_identity(page)
            if actual["wmid"] != expected["wmid"]:
                raise RuntimeError("Dayu identity does not match the binding in the account file")
            return True
        finally:
            await browser.close()
