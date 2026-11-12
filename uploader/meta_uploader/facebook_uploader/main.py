"""Publish videos to a Facebook personal profile with Patchright.

This uses the post composer on the Facebook home page for a personal profile. Page publishing and scheduled
publishing in Meta Business Suite need a different logged-in identity and permissions; do not mix them with the profile flow.
"""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

from patchright.async_api import Page, Playwright, async_playwright, expect

from utils.log import facebook_logger


FACEBOOK_HOME_URL = "https://www.facebook.com/"
# The proxy is read only from an explicit CLI argument or an environment variable set by the user; without one, connect directly.
FACEBOOK_PROXY = os.environ.get("SAU_FACEBOOK_PROXY")
FACEBOOK_LOGIN_INPUT = 'input[name="email"]'
# The home page post attachment accepts both images and video; the avatar/cover controls do not have this set of MIME types.
FACEBOOK_MEDIA_INPUT = 'input[type="file"][accept*="image/"][accept*="video/"]'


def _proxy_options(proxy: str | None) -> dict[str, str] | None:
    """Without an argument, use the explicit environment setting, else connect directly; an empty string overrides the environment and connects directly."""
    address = (FACEBOOK_PROXY if proxy is None else proxy) or ""
    address = address.strip()
    return {"server": address} if address else None


async def _is_logged_out(page: Page) -> bool:
    """Decide whether the session is valid from login-flow markers and the home page post composer anchor."""
    current_url = page.url.lower()
    # two_step_verification is the second-factor page of the login flow; do not mistake it for the logged-in home page.
    if any(
        marker in current_url
        for marker in ("/login", "checkpoint", "two_step_verification", "/authentication/")
    ):
        return True
    email_input = page.locator(FACEBOOK_LOGIN_INPUT)
    if await email_input.count() and await email_input.first.is_visible():
        return True
    # The post attachment control is positive evidence that the home page composer is mounted; a blank page or a page mid-login does not count as logged in.
    return await page.locator(FACEBOOK_MEDIA_INPUT).count() != 1


async def _open_facebook_page(playwright: Playwright, account_file: Path, *, proxy: str | None, headless: bool):
    """Open Facebook with the storage state and pass the proxy setting to the browser process."""
    launch_options = {
        "channel": "chrome",
        "headless": headless,
        "proxy": _proxy_options(proxy),
    }
    browser = await playwright.chromium.launch(**launch_options)
    try:
        context = await browser.new_context(storage_state=str(account_file))
        page = await context.new_page()
        page.set_default_timeout(30_000)
        await page.goto(FACEBOOK_HOME_URL, wait_until="domcontentloaded", timeout=90_000)
        await page.locator("body").wait_for(state="visible", timeout=30_000)
        return browser, context, page
    except Exception:
        # If navigation or the storage state fails, this function owns the browser and must close it before raising.
        await browser.close()
        raise


async def facebook_cookie_auth(account_file: str | Path, *, proxy: str | None = None) -> bool:
    """Check whether the saved Facebook storage state still reaches the logged-in home page."""
    account_file = Path(account_file)
    if not account_file.is_file():
        return False
    async with async_playwright() as playwright:
        browser, context, page = await _open_facebook_page(
            playwright, account_file, proxy=proxy, headless=True
        )
        try:
            return not await _is_logged_out(page)
        finally:
            await browser.close()


async def facebook_setup(
    account_file: str | Path,
    *,
    handle: bool = False,
    return_detail: bool = False,
    headless: bool = False,
    proxy: str | None = None,
    timeout_seconds: int = 600,
):
    """Check the login state. The login command opens a visible browser, waits for the user to log in, then saves the state."""
    account_file = Path(account_file)
    account_file.parent.mkdir(parents=True, exist_ok=True)
    valid = await facebook_cookie_auth(account_file, proxy=proxy)
    if valid:
        result = {
            "success": True,
            "status": "cookie_valid",
            "message": "Facebook 登录态有效",
            "account_file": str(account_file),
        }
        return result if return_detail else True
    if not handle:
        result = {
            "success": False,
            "status": "cookie_invalid",
            "message": "Facebook 登录态不存在或已失效",
            "account_file": str(account_file),
        }
        return result if return_detail else False

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            channel="chrome", headless=headless, proxy=_proxy_options(proxy)
        )
        try:
            context = await browser.new_context(
                storage_state=str(account_file) if account_file.is_file() else None
            )
            page = await context.new_page()
            page.set_default_timeout(30_000)
            await page.goto(FACEBOOK_HOME_URL, wait_until="domcontentloaded", timeout=90_000)
            facebook_logger.info("Log in to Facebook in the browser that opened; the login state will be saved automatically")
            deadline = asyncio.get_running_loop().time() + timeout_seconds
            while asyncio.get_running_loop().time() < deadline:
                if not await _is_logged_out(page):
                    await context.storage_state(path=str(account_file))
                    result = {
                        "success": True,
                        "status": "logged_in",
                        "message": "Facebook 登录成功，登录态已保存",
                        "account_file": str(account_file),
                        "current_url": page.url,
                    }
                    return result if return_detail else True
                await page.wait_for_timeout(1000)
            result = {
                "success": False,
                "status": "timeout",
                "message": "等待 Facebook 登录超时，未保存登录态",
                "account_file": str(account_file),
                "current_url": page.url,
            }
            return result if return_detail else False
        finally:
            await browser.close()


class FacebookPost:
    """Publish one video or a set of images through the profile composer."""

    def __init__(
        self,
        title: str,
        file_path: str | Path | list[Path],
        description: str,
        tags: list[str],
        account_file: str | Path,
        proxy: str | None = None,
        headless: bool = True,
    ):
        self.title = title.strip()
        self.files = [Path(item) for item in file_path] if isinstance(file_path, list) else [Path(file_path)]
        self.file_path = self.files[0] if self.files else Path()
        self.description = description.strip()
        self.tags = [tag.strip().lstrip("#") for tag in tags if tag.strip().lstrip("#")]
        self.account_file = Path(account_file)
        self.proxy = proxy
        self.headless = headless

    def _caption(self) -> str:
        """Facebook's home page has no separate video title field, so the title is merged into the text, following the project convention."""
        parts = [part for part in (self.title, self.description) if part]
        if self.tags:
            parts.append(" ".join(f"#{tag}" for tag in self.tags))
        return "\n\n".join(parts)

    async def _find_caption_editor(self, page: Page):
        # The outer aria-modal dialog belongs to this post form, which excludes home page comment boxes and hidden templates.
        editor = page.locator('[role="dialog"][aria-modal="true"] [contenteditable="true"][role="textbox"]')
        await expect(editor).to_have_count(1)
        return editor

    async def _find_publish_button(self, page: Page):
        # The last action in the post form is submit; the buttons before it are close editor, privacy and edit attachment.
        # The real DOM was checked for both image posts and video; the nested dialog is the editor title bar, not the submit area.
        form = page.locator('[role="dialog"][aria-modal="true"] form')
        await expect(form).to_have_count(1)
        button = form.get_by_role('button').last
        await expect(button).to_be_visible()
        return button

    async def _wait_until_publishable(self, page: Page) -> None:
        deadline = asyncio.get_running_loop().time() + 180
        while asyncio.get_running_loop().time() < deadline:
            error = page.locator('[role="dialog"] [role="alert"]')
            if await error.count() and await error.first.is_visible():
                message = (await error.first.inner_text()).strip()
                if message:
                    raise RuntimeError(f"Facebook video upload failed: {message}")
            try:
                publish_button = await self._find_publish_button(page)
                if await publish_button.is_enabled():
                    return
            except RuntimeError as exc:
                if "未找到 Facebook 发布按钮" not in str(exc):
                    raise
            await page.wait_for_timeout(1000)
        raise TimeoutError("Facebook video upload or processing timed out; the publish button is not ready")

    async def _publish_and_verify(self, page: Page) -> None:
        publish_button = await self._find_publish_button(page)
        # The tested success notice is a full sentence; any "已发布" (published) text in the feed must not count as success for this post.
        success_pattern = re.compile(r"^(?:你的帖子已成功分享给.+|你的帖子已发布|Your post has been published[.!]?)$", re.I)
        success_text = page.get_by_text(success_pattern)
        for index in range(await success_text.count()):
            if await success_text.nth(index).is_visible():
                raise RuntimeError("A publish success notice was already showing before submit, so this result cannot be told apart; not submitted")
        await publish_button.click()
        deadline = asyncio.get_running_loop().time() + 90
        while asyncio.get_running_loop().time() < deadline:
            # Accept only a status notice or success text; the dialog disappearing does not prove the server accepted the post.
            success_text = page.get_by_text(success_pattern)
            if await success_text.count():
                for index in range(await success_text.count()):
                    if await success_text.nth(index).is_visible():
                        return
            await page.wait_for_timeout(1000)
        raise TimeoutError("Clicked publish on Facebook, but no clear publish success state was seen")

    async def upload(self, playwright: Playwright) -> None:
        if not self.files:
            raise ValueError("Facebook media files must not be empty")
        for file in self.files:
            if not file.is_file():
                raise FileNotFoundError(f"Facebook media file does not exist: {file}")
        if not self.title:
            raise ValueError("Facebook video title must not be empty")
        if not self.account_file.is_file():
            raise RuntimeError(f"Facebook login state file does not exist: {self.account_file}")

        browser, context, page = await _open_facebook_page(
            playwright, self.account_file, proxy=self.proxy, headless=self.headless
        )
        try:
            if await _is_logged_out(page):
                raise RuntimeError("Facebook login state is invalid; run sau facebook login first")

            # Tested: the home page has a single mixed image/video input; matching on an accept that allows both excludes the avatar and similar controls.
            file_input = page.locator(FACEBOOK_MEDIA_INPUT)
            if await file_input.count() != 1:
                raise RuntimeError("The home page media upload control is not unique; nothing was uploaded")
            await file_input.set_input_files([str(file) for file in self.files])

            # The composer mounts asynchronously after files are chosen; do not conclude the text box is missing from an immediate count in the same pass.
            await page.locator('[role="dialog"] [contenteditable="true"][role="textbox"]:visible').wait_for(timeout=30000)
            editor = await self._find_caption_editor(page)
            caption = self._caption()
            await editor.click()
            await editor.fill(caption)
            if (await editor.inner_text()).strip() != caption:
                raise RuntimeError("The Facebook text box did not read back the expected content")

            await self._wait_until_publishable(page)
            await self._publish_and_verify(page)
            await context.storage_state(path=str(self.account_file))
        finally:
            await browser.close()

    async def main(self) -> None:
        async with async_playwright() as playwright:
            await self.upload(playwright)


# Keep the class name the original video callers use; video and image posts share the same post form, with no extra wrapper.
FacebookVideo = FacebookPost
