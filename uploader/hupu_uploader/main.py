# -*- coding: utf-8 -*-
"""Hupu video upload + manual login that saves the cookie.

Features:
  - hupu_cookie_gen: open a browser so the user can log in by hand (QQ, phone number, etc.) and save storage_state
  - cookie_auth: check whether the cookie is still valid
  - hupu_setup: single entry point (check / trigger login)
  - HuPuVideo: video upload class

Rewritten from a script recorded with playwright codegen.
Publish page: https://bbs.hupu.com/newpost?tabkey=2 (the video publishing tab)
Section: always 步行街 → 步行街主干道 (Pedestrian Street → Pedestrian Street main road)

Note: Hupu detects headless browsers, so anti-detection parameters are needed for it to work.
"""
from __future__ import annotations

import asyncio
import inspect
import os
import re
import time
from pathlib import Path

from patchright.async_api import BrowserContext, Page, Playwright, async_playwright

from conf import BASE_DIR, LOCAL_CHROME_HEADLESS, LOCAL_CHROME_PATH
from uploader.base_video import BaseVideoUploader
from utils.log import hupu_logger


HUPU_HOME_URL = "https://www.hupu.com/"
HUPU_LOGIN_URL = "https://passport.hupu.com/v2/login?pcPhone=1&jumpurl=https://www.hupu.com&from=https://www.hupu.com"
HUPU_PUBLISH_URL = "https://bbs.hupu.com/newpost?tabkey=2"

# URL pattern of the post that Hupu redirects to after a successful publish
HUPU_POST_URL_PATTERN = re.compile(r"bbs\.hupu\.com/\d+\.html")

# Anti-detection UA
_CHROME_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"

# Script that hides webdriver detection
_STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
"""


def _msg(emoji: str, text: str) -> str:
    return f"{emoji} {text}"


def _build_login_result(success: bool, status: str, message: str, account_file: str, current_url: str = "") -> dict:
    return {
        "success": success,
        "status": status,
        "message": message,
        "account_file": str(account_file),
        "current_url": current_url,
    }


async def _emit_qrcode_callback(qrcode_callback, payload: dict):
    if not qrcode_callback:
        return
    callback_result = qrcode_callback(payload)
    if inspect.isawaitable(callback_result):
        await callback_result


def _build_launch_kwargs(headless: bool) -> dict:
    launch_kwargs = {
        "headless": headless,
        "args": ["--disable-blink-features=AutomationControlled"],
    }
    if LOCAL_CHROME_PATH:
        launch_kwargs["executable_path"] = LOCAL_CHROME_PATH
    return launch_kwargs


def _resolve_account_file(account_file: str | Path) -> str:
    path = Path(account_file).expanduser()
    if path.is_absolute():
        return str(path)
    if len(path.parts) == 1:
        return str((Path(BASE_DIR) / "cookies" / path).resolve())
    return str(path.resolve())


async def _create_stealth_context(browser, account_file: str | None = None) -> BrowserContext:
    """Create a context with anti-detection settings."""
    kwargs = {
        "user_agent": _CHROME_UA,
        "viewport": {"width": 1920, "height": 1080},
    }
    if account_file and os.path.exists(account_file):
        kwargs["storage_state"] = account_file
    context = await browser.new_context(**kwargs)
    return context


async def _new_stealth_page(context: BrowserContext) -> Page:
    """Create a page with the anti-detection init script."""
    page = await context.new_page()
    await page.add_init_script(_STEALTH_SCRIPT)
    return page


async def hupu_cookie_gen(account_file, qrcode_callback=None, poll_interval: int = 3, max_checks: int = 120, headless: bool = False):
    """Log in to Hupu by QQ QR code and save the cookie.

    Flow: open the Hupu login page → click QQ login → capture the QQ QR code → wait for the scan to finish → save storage_state.
    Supports headless mode (the QR code is shown in the terminal).
    """
    account_file = _resolve_account_file(account_file)
    Path(account_file).parent.mkdir(parents=True, exist_ok=True)
    result = _build_login_result(False, "failed", "虎扑登录失败", account_file)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**_build_launch_kwargs(headless=headless))
        context = await _create_stealth_context(browser)
        try:
            page = await _new_stealth_page(context)
            await page.goto(HUPU_LOGIN_URL, timeout=60000, wait_until="load")
            await page.wait_for_timeout(3000)

            # Click the QQ login button
            qq_btn = page.get_by_role("button", name="qq QQ登录")
            if not await qq_btn.count():
                hupu_logger.error(_msg("😢", "QQ login button not found"))
                result = _build_login_result(False, "failed", "未找到 QQ 登录按钮", account_file, page.url)
                return result

            await qq_btn.click()
            await page.wait_for_timeout(5000)
            hupu_logger.info(_msg("🏃", "Redirected to the QQ login page"))

            # Get the QR code from the QQ iframe
            qrcode_info = await _grab_qq_qrcode(page, context, account_file)

            if qrcode_info:
                await _emit_qrcode_callback(qrcode_callback, qrcode_info)
                hupu_logger.info(_msg("🧍", "Scan the QR code with the QQ mobile app to log in"))
            else:
                hupu_logger.warning(_msg("⚠️", "Could not get the QQ QR code. Scan it manually in the browser"))

            # Poll until the login is done
            for _ in range(max_checks):
                current_url = page.url
                # After QQ authorization succeeds, the page returns to the Hupu home page
                if "www.hupu.com" in current_url and "passport" not in current_url and "graph.qq.com" not in current_url:
                    hupu_logger.info(_msg("🥳", f"Login succeeded, redirected to: {current_url}"))
                    result = _build_login_result(True, "success", "虎扑 QQ 扫码登录成功", account_file, current_url)
                    break
                # Check whether we actually landed on the Hupu passport callback page (not just a redirect_uri parameter containing it)
                if current_url.startswith("https://passport.hupu.com/pc/qqcallback"):
                    await page.wait_for_timeout(5000)
                    current_url = page.url
                    hupu_logger.info(_msg("🥳", f"QQ callback succeeded, current: {current_url}"))
                    result = _build_login_result(True, "success", "虎扑 QQ 扫码登录成功", account_file, current_url)
                    break
                # Check whether the u cookie (the core login state) has appeared
                cookies = await context.cookies()
                if any(c.get("name") == "u" and c.get("value") for c in cookies):
                    hupu_logger.info(_msg("🥳", f"Login succeeded (u cookie detected), current: {current_url}"))
                    result = _build_login_result(True, "success", "虎扑 QQ 扫码登录成功", account_file, current_url)
                    break
                await page.wait_for_timeout(poll_interval * 1000)
            else:
                result = _build_login_result(False, "timeout", "等待 QQ 扫码登录超时", account_file, page.url)

            if result["success"]:
                await asyncio.sleep(2)
                # Make sure we go to the home page so the cookies are loaded
                if "www.hupu.com" not in page.url:
                    await page.goto(HUPU_HOME_URL, timeout=30000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(3000)
                await context.storage_state(path=account_file)
                hupu_logger.success(_msg("🥳", f"cookie saved: {account_file}"))
        except Exception as exc:
            result = _build_login_result(False, "failed", str(exc), account_file, current_url=page.url if "page" in locals() else "")
        finally:
            # Remove the temporary QR-code file
            qr_path = Path(account_file).parent / f"{Path(account_file).stem}_qq_qrcode.png"
            if qr_path.exists():
                qr_path.unlink()
            if not result["success"]:
                hupu_logger.error(_msg("😢", f"Login failed: {result['message']}"))
            await context.close()
            await browser.close()
    return result


async def _grab_qq_qrcode(page: Page, context: BrowserContext, account_file: str) -> dict | None:
    """Get the QR code from the QQ login iframe."""
    from utils.login_qrcode import decode_qrcode_from_path, print_terminal_qrcode

    # Wait for the QQ iframe to load (up to 15 seconds)
    qq_frame = None
    for _ in range(5):
        for frame in page.frames:
            if "xui.ptlogin2.qq.com" in frame.url or "ptlogin2.qq.com" in frame.url:
                qq_frame = frame
                break
        if qq_frame:
            break
        await asyncio.sleep(3)

    if not qq_frame:
        return None

    await asyncio.sleep(3)

    # Get the QR-code image (id="qrlogin_img")
    qr_selectors = ["#qrlogin_img", 'img[src*="ptqrshow"]', 'img[id*="qr"]']
    for sel in qr_selectors:
        qr_loc = qq_frame.locator(sel).first
        if await qr_loc.count():
            src = await qr_loc.get_attribute("src")
            if src and src.startswith("http"):
                # Download the QR-code image
                try:
                    resp = await context.request.get(src)
                    qr_path = Path(account_file).parent / f"{Path(account_file).stem}_qq_qrcode.png"
                    qr_path.parent.mkdir(parents=True, exist_ok=True)
                    qr_path.write_bytes(await resp.body())

                    # Try to decode it and show it in the terminal
                    qrcode_content = decode_qrcode_from_path(qr_path)
                    if qrcode_content:
                        print_terminal_qrcode(qrcode_content, qr_path, "QQ手机版")
                    else:
                        hupu_logger.warning(_msg("😵", f"The terminal cannot show the QR code. Open {qr_path} and scan it"))

                    return {"image_path": str(qr_path), "image_data_url": ""}
                except Exception as exc:
                    hupu_logger.warning(_msg("⚠️", f"Failed to download the QQ QR code: {exc}"))
                    continue

    return None


async def cookie_auth(account_file):
    """Check whether the Hupu cookie is valid. Opens the publish page and checks that it loads normally."""
    account_file = _resolve_account_file(account_file)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**_build_launch_kwargs(headless=True))
        try:
            context = await _create_stealth_context(browser, account_file)
            page = await _new_stealth_page(context)
            await page.goto(HUPU_PUBLISH_URL, timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)

            # Check whether we were redirected to the login page
            if "passport" in page.url or "login" in page.url:
                hupu_logger.info(_msg("🥹", "cookie has expired (redirected to the login page)"))
                return False

            # Check whether the publish page shows the 上传视频 (Upload video) button (only present when logged in)
            upload_btn = page.get_by_role("button", name="上传视频")
            if await upload_btn.count():
                hupu_logger.success(_msg("🥳", "cookie is valid"))
                return True

            # Fallback: check whether the cookies contain the u field
            cookies = await context.cookies()
            if any(c.get("name") == "u" and c.get("value") for c in cookies):
                hupu_logger.success(_msg("🥳", "cookie is valid (u cookie present)"))
                return True

            hupu_logger.info(_msg("🥹", "cookie has expired (no login state detected)"))
            return False
        except Exception as exc:
            hupu_logger.warning(_msg("😵", f"cookie check failed, treating it as expired: {exc}"))
            return False
        finally:
            await browser.close()


async def hupu_setup(account_file, handle=False, return_detail=False, qrcode_callback=None, headless: bool = False):
    """Single entry point: check the cookie → if it is invalid and handle=True, start a manual login."""
    account_file = _resolve_account_file(account_file)
    if not os.path.exists(account_file) or not await cookie_auth(account_file):
        if not handle:
            result = _build_login_result(False, "cookie_invalid", "cookie 文件不存在或已失效", account_file)
            return result if return_detail else False
        hupu_logger.info(_msg("🥹", "cookie file is missing or expired. Opening a browser, please log in manually"))
        result = await hupu_cookie_gen(account_file, qrcode_callback=qrcode_callback, headless=headless)
        return result if return_detail else result["success"]

    result = _build_login_result(True, "cookie_valid", "cookie 有效", account_file)
    return result if return_detail else True


class HuPuVideo(BaseVideoUploader):
    """Hupu video upload.

    Flow: go straight to the publish page → upload the video file → fill in the title → fill in the description →
         upload the cover → choose the section (步行街主干道) → choose original/derivative → choose the AI declaration →
         click 确定发布 (Confirm publish) → wait for the redirect to the post page.
    """

    def __init__(
        self,
        title,
        file_path,
        tags,
        account_file,
        publish_date=0,
        desc: str | None = None,
        thumbnail_path: str | None = None,
        debug: bool = True,
        headless: bool = LOCAL_CHROME_HEADLESS,
    ):
        self.title = title
        self.file_path = file_path
        self.tags = tags or []
        self.account_file = _resolve_account_file(account_file)
        self.publish_date = publish_date
        self.desc = desc or ""
        self.thumbnail_path = thumbnail_path
        self.debug = debug
        self.headless = headless
        self.local_executable_path = LOCAL_CHROME_PATH
        self.max_title_length = 40
        self.min_title_length = 4

    async def validate_upload_args(self):
        if not os.path.exists(self.account_file):
            raise RuntimeError(f"cookie file does not exist, log in to Hupu first: {self.account_file}")
        if not await cookie_auth(self.account_file):
            raise RuntimeError(f"cookie file has expired, log in to Hupu first: {self.account_file}")
        if not self.title or not str(self.title).strip():
            raise ValueError("Video title must not be empty")
        if len(self.title) < self.min_title_length:
            raise ValueError(f"Video title must have at least {self.min_title_length} characters")
        self.file_path = str(self.validate_video_file(self.file_path))
        if self.thumbnail_path:
            self.thumbnail_path = str(self.validate_image_file(self.thumbnail_path))

    async def upload(self, playwright: Playwright) -> None:
        hupu_logger.info(_msg("🧍", "Checking the cookie and the video file first"))
        await self.validate_upload_args()
        hupu_logger.info(_msg("🥳", "Pre-upload checks passed"))

        browser = await playwright.chromium.launch(**_build_launch_kwargs(headless=self.headless))
        context = await _create_stealth_context(browser, self.account_file)

        try:
            page = await _new_stealth_page(context)
            # Go straight to the video publish page (skips clicking through the home page)
            await page.goto(HUPU_PUBLISH_URL, timeout=60000, wait_until="load")
            await page.wait_for_timeout(5000)
            hupu_logger.info(_msg("🏃", f"Starting video upload: {self.title}"))

            # 1) Upload the video file
            await self._upload_video_file(page)

            # 2) Fill in the title
            await self._fill_title(page)

            # 3) Fill in the description
            await self._fill_description(page)

            # 4) Upload the cover (if any)
            if self.thumbnail_path:
                await self._upload_thumbnail(page)

            # 5) Choose the section (步行街 → 步行街主干道)
            await self._select_zone(page)

            # 6) Choose original/derivative + AI declaration
            await self._check_declarations(page)

            # 7) Click publish
            await self._submit_publish(page)

            # Save the cookie
            await context.storage_state(path=self.account_file)
            hupu_logger.success(_msg("🥳", "cookie updated"))
        finally:
            await context.close()
            await browser.close()

    async def _upload_video_file(self, page: Page) -> None:
        """Click the 上传视频 (Upload video) button and set the file."""
        upload_btn = page.get_by_role("button", name="上传视频")
        await upload_btn.wait_for(state="visible", timeout=15000)

        # Set the file through the file chooser
        async with page.expect_file_chooser(timeout=10000) as fc_info:
            await upload_btn.click()
        file_chooser = await fc_info.value
        await file_chooser.set_files(self.file_path)
        hupu_logger.info(_msg("🏃", f"Video file selected: {self.file_path}"))

        # Wait until the video upload is ready (it can be filled in once the title input appears)
        title_field = page.get_by_placeholder("请输入标题（最少4个字，最多40个字）")
        await title_field.wait_for(state="visible", timeout=300000)
        hupu_logger.info(_msg("🥳", "Video is ready"))

    async def _fill_title(self, page: Page) -> None:
        """Fill in the title (4-40 characters)."""
        title_field = page.get_by_placeholder("请输入标题（最少4个字，最多40个字）")
        await title_field.wait_for(state="visible", timeout=15000)
        title = self.title[:self.max_title_length]
        await title_field.click()
        await title_field.fill(title)
        hupu_logger.info(_msg("🏷️", f"Title filled in: {title}"))

    async def _fill_description(self, page: Page) -> None:
        """Fill in the description."""
        desc_field = page.get_by_placeholder("请输入简介")
        if not await desc_field.count():
            hupu_logger.warning(_msg("⚠️", "Description input not found"))
            return

        # Build the description: body text + tags
        content = self.desc
        if self.tags:
            tag_str = " ".join(f"#{t}#" for t in self.tags)
            content = f"{content}\n{tag_str}" if content else tag_str

        if content:
            await desc_field.click()
            await desc_field.fill(content)
            hupu_logger.info(_msg("📝", f"Description filled in ({len(content)} characters)"))

    async def _upload_thumbnail(self, page: Page) -> None:
        """Upload the cover: click 更换封面 (Change cover) → set the file."""
        try:
            cover_span = page.locator("span").filter(has_text="更换封面")
            await cover_span.wait_for(state="visible", timeout=10000)

            # Set the cover image through the file chooser
            async with page.expect_file_chooser(timeout=10000) as fc_info:
                await cover_span.click()
            file_chooser = await fc_info.value
            await file_chooser.set_files(self.thumbnail_path)
            hupu_logger.info(_msg("🏃", f"Cover image selected: {self.thumbnail_path}"))
            await page.wait_for_timeout(3000)
            hupu_logger.success(_msg("🖼️", "Cover uploaded"))
        except Exception as exc:
            hupu_logger.warning(_msg("⚠️", f"Cover upload failed: {exc}, publishing anyway (with the default cover)"))

    async def _select_zone(self, page: Page) -> None:
        """Choose the section: 步行街 → 步行街主干道."""
        try:
            # Recorded script: page.get_by_label("发视频").get_by_text("添加专区").click()
            add_zone_btn = page.get_by_label("发视频").get_by_text("添加专区")
            await add_zone_btn.wait_for(state="visible", timeout=10000)
            await add_zone_btn.click()
            await page.wait_for_timeout(1500)

            # Choose the 步行街 (Pedestrian Street) category
            zone_dialog = page.get_by_label("添加专区")
            step_street = zone_dialog.locator("div").filter(has_text=re.compile(r"^步行街$"))
            await step_street.click()
            await page.wait_for_timeout(1000)

            # Choose the 步行街主干道 (Pedestrian Street main road) subcategory
            main_road = page.get_by_text("步行街主干道")
            await main_road.click()
            await page.wait_for_timeout(500)

            # Click OK
            confirm_btn = page.get_by_role("button", name="确 定")
            await confirm_btn.click()
            await page.wait_for_timeout(1000)
            hupu_logger.info(_msg("🏷️", "Section selected: 步行街主干道 (Pedestrian Street main road)"))
        except Exception as exc:
            hupu_logger.warning(_msg("⚠️", f"Failed to choose the section: {exc}"))

    async def _check_declarations(self, page: Page) -> None:
        """Choose the original/derivative declaration + AI declaration."""
        try:
            # 1) Click the 原创/二创 (Original/Derivative) button
            declaration_btn = page.get_by_role("button", name="原创/二创")
            if await declaration_btn.count():
                await declaration_btn.click(timeout=5000)
                await page.wait_for_timeout(1000)
                hupu_logger.info(_msg("🏷️", "Clicked 原创/二创 (Original/Derivative)"))
        except Exception as exc:
            hupu_logger.warning(_msg("⚠️", f"Failed to click 原创/二创: {exc}"))

        try:
            # 2) Choose 含AI生成内容 (Contains AI-generated content)
            combobox = page.get_by_role("combobox")
            if await combobox.count():
                await combobox.click(timeout=5000)
                await page.wait_for_timeout(1000)

                ai_option = page.get_by_text("含AI生成内容")
                if await ai_option.count():
                    await ai_option.click(timeout=5000)
                    await page.wait_for_timeout(500)
                    hupu_logger.info(_msg("🏷️", "Selected 含AI生成内容 (Contains AI-generated content)"))
        except Exception as exc:
            hupu_logger.warning(_msg("⚠️", f"Failed to choose the AI declaration: {exc}"))

    async def _submit_publish(self, page: Page) -> None:
        """Click 确定发布 (Confirm publish) and wait for the redirect to the post page."""
        # Recorded script: page.get_by_label("发视频").get_by_text("确定发布").click()
        publish_btn = page.get_by_label("发视频").get_by_text("确定发布")
        await publish_btn.wait_for(state="visible", timeout=15000)
        await publish_btn.click()
        hupu_logger.info(_msg("🏃", "Clicked 确定发布 (Confirm publish)"))

        # Wait for the redirect to the post detail page (URL matches bbs.hupu.com/{number}.html)
        start = time.monotonic()
        while time.monotonic() - start < 60:
            current_url = page.url
            if HUPU_POST_URL_PATTERN.search(current_url):
                hupu_logger.success(_msg("🥳", f"Video published: {current_url}"))
                return

            await page.wait_for_timeout(2000)

        # Timeout: it may have succeeded but could not be detected
        hupu_logger.warning(_msg("⚠️", f"No redirect to the post page detected 60s after publishing, current URL: {page.url}"))

    async def main(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)
