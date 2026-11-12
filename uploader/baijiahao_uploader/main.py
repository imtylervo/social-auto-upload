# -*- coding: utf-8 -*-
"""Baijiahao (Baidu Baijiahao) video upload + QR-code login.

Features:
  - baijiahao_cookie_gen: headless QR-code login (Baidu passport QR code)
  - cookie_auth: check whether the cookie is still valid
  - baijiahao_setup: single entry point (check / trigger login)
  - BaiJiaHaoVideo: video upload class
"""
from __future__ import annotations

import asyncio
import inspect
import json as _json
import os
import time
from pathlib import Path

from patchright.async_api import Page, Playwright, TimeoutError as PWTimeoutError, async_playwright

from conf import BASE_DIR, LOCAL_CHROME_HEADLESS, LOCAL_CHROME_PATH
from uploader.base_video import BaseVideoUploader
from utils.log import baijiahao_logger
from utils.login_qrcode import build_login_qrcode_path, decode_qrcode_from_path, print_terminal_qrcode, remove_qrcode_file


BAIJIAHAO_LOGIN_URL = "https://baijiahao.baidu.com/builder/theme/bjh/login"
BAIJIAHAO_HOME_URL = "https://baijiahao.baidu.com/builder/rc/home"
BAIJIAHAO_PUBLISH_URL = "https://baijiahao.baidu.com/builder/rc/edit?type=videoV2"
# URL prefix the page redirects to after a successful publish
BAIJIAHAO_SUCCESS_URL_PREFIX = "https://baijiahao.baidu.com/builder/rc/clue"

# Selector for the Baidu passport QR-code image
QR_SELECTOR = 'img[src^="https://passport.baidu.com/v2/api/qrcode"]'


def _msg(emoji: str, text: str) -> str:
    return f"{emoji} {text}"


def _build_login_result(success: bool, status: str, message: str, account_file: str, qrcode: dict | None = None, current_url: str = "") -> dict:
    return {
        "success": success,
        "status": status,
        "message": message,
        "account_file": str(account_file),
        "qrcode": qrcode,
        "current_url": current_url,
    }


async def _emit_qrcode_callback(qrcode_callback, payload: dict):
    if not qrcode_callback:
        return
    callback_result = qrcode_callback(payload)
    if inspect.isawaitable(callback_result):
        await callback_result


def _build_launch_kwargs(headless: bool) -> dict:
    launch_kwargs = {"headless": headless}
    if LOCAL_CHROME_PATH:
        launch_kwargs["executable_path"] = LOCAL_CHROME_PATH
    return launch_kwargs


def _resolve_account_file(account_file: str | Path) -> str:
    path = Path(account_file).expanduser()
    if path.is_absolute():
        return str(path)
    if len(path.parts) == 1:
        return str((Path(BASE_DIR) / "cookies" / "baijiahao_uploader" / path).resolve())
    return str(path.resolve())


async def _grab_qr(page: Page, account_file: str) -> dict:
    """Capture the QR code of the Baidu passport QR-code login.

    After clicking 登录 (Log in) on the Baijiahao login page, the unified Baidu login box opens. Its QR code is an img[src] pointing
    to an image URL on passport.baidu.com, which can be downloaded directly or screenshotted.
    """
    qr = page.locator(QR_SELECTOR).first
    await qr.wait_for(state="attached", timeout=60000)

    qrcode_path = build_login_qrcode_path(account_file)
    qrcode_path.parent.mkdir(parents=True, exist_ok=True)

    # Prefer downloading the high-resolution image URL directly
    src = await qr.get_attribute("src")
    if src and src.startswith("https://"):
        try:
            resp = await page.context.request.get(src)
            qrcode_path.write_bytes(await resp.body())
        except Exception:
            await qr.screenshot(path=str(qrcode_path))
    else:
        await qr.screenshot(path=str(qrcode_path))

    qrcode_content = decode_qrcode_from_path(qrcode_path)
    baijiahao_logger.info(_msg("🖼️", f"QR code saved to: {qrcode_path}"))
    if qrcode_content:
        print_terminal_qrcode(qrcode_content, qrcode_path, "百度APP/手机百度")
    else:
        baijiahao_logger.warning(_msg("😵", f"The terminal cannot show the full QR code. Open {qrcode_path} and scan it"))
    return {"image_path": str(qrcode_path), "image_data_url": ""}


async def _is_login_completed(page: Page) -> bool:
    """Check whether the Baidu login is done: the URL has left the login page, or a BDUSS cookie is present."""
    if "login" in page.url.lower():
        # Still on the login page: check the cookies
        cookies = await page.context.cookies()
        if any(c.get("name") in ("BDUSS", "STOKEN") for c in cookies):
            return True
        return False
    # Redirected away, so the login succeeded
    return True


async def baijiahao_cookie_gen(account_file, qrcode_callback=None, poll_interval: int = 3, max_checks: int = 120, headless: bool = LOCAL_CHROME_HEADLESS):
    """QR-code login to Baijiahao, headless or headed, and save the cookie.

    Flow: open the login page → click the 登录 (Log in) button to open the Baidu passport login box → capture the QR code → wait for the scan to finish → save storage_state.
    Returns the standard login result dict.
    """
    account_file = _resolve_account_file(account_file)
    Path(account_file).parent.mkdir(parents=True, exist_ok=True)
    qrcode_path = None
    result = _build_login_result(False, "failed", "百家号登录失败", account_file)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**_build_launch_kwargs(headless=headless))
        context = await browser.new_context()
        try:
            page = await context.new_page()
            await page.goto(BAIJIAHAO_LOGIN_URL, timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_timeout(4000)

            # Click the 登录 (Log in) button to trigger the Baidu passport popup
            login_btn = page.get_by_text("登录", exact=True).first
            try:
                await login_btn.click(timeout=10000)
            except Exception:
                # Sometimes the page is already logged in
                pass
            await page.wait_for_timeout(4000)

            if headless:
                baijiahao_logger.info(_msg("🧍", "Headless login: the QR code was saved as an image. Scan it with the Baidu app"))
            else:
                baijiahao_logger.info(_msg("🧍", "Scan the QR code in the opened browser to log in to Baijiahao"))

            # Capture the QR code
            qrcode_info = await _grab_qr(page, account_file)
            qrcode_path = Path(qrcode_info["image_path"]) if qrcode_info.get("image_path") else None
            await _emit_qrcode_callback(qrcode_callback, qrcode_info)

            baijiahao_logger.info(_msg("🧍", "Scan the QR code. Waiting for the login to finish"))

            # Poll until the login is done
            for _ in range(max_checks):
                if await _is_login_completed(page):
                    baijiahao_logger.info(_msg("🥳", f"QR code scanned, current page: {page.url}"))
                    result = _build_login_result(True, "success", "百家号扫码登录成功", account_file, qrcode_info, page.url)
                    break
                await page.wait_for_timeout(poll_interval * 1000)
            else:
                result = _build_login_result(False, "timeout", "等待百家号扫码登录超时", account_file, qrcode_info, page.url)

            if result["success"]:
                await asyncio.sleep(2)
                await context.storage_state(path=account_file)
                baijiahao_logger.success(_msg("🥳", f"cookie saved: {account_file}"))
        except Exception as exc:
            result = _build_login_result(False, "failed", str(exc), account_file, current_url=page.url if "page" in locals() else "")
        finally:
            if remove_qrcode_file(qrcode_path):
                baijiahao_logger.info(_msg("🧹", f"Temporary QR-code file removed: {qrcode_path}"))
            if not result["success"]:
                baijiahao_logger.error(_msg("😢", f"Login failed: {result['message']}"))
            await context.close()
            await browser.close()
    return result


async def cookie_auth(account_file):
    """Check whether the Baijiahao cookie is valid. Opens the dashboard home page and looks for a login prompt."""
    account_file = _resolve_account_file(account_file)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**_build_launch_kwargs(headless=True))
        try:
            context = await browser.new_context(storage_state=account_file)
            page = await context.new_page()
            await page.goto(BAIJIAHAO_HOME_URL, timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)

            if await page.get_by_text("注册/登录百家号").count():
                baijiahao_logger.info(_msg("🥹", "cookie has expired"))
                return False
            else:
                baijiahao_logger.success(_msg("🥳", "cookie is valid"))
                return True
        except Exception as exc:
            baijiahao_logger.warning(_msg("😵", f"cookie check failed, treating it as expired: {exc}"))
            return False
        finally:
            await browser.close()


async def baijiahao_setup(account_file, handle=False, return_detail=False, qrcode_callback=None, headless: bool = LOCAL_CHROME_HEADLESS):
    """Single entry point: check the cookie → if it is invalid and handle=True, start QR-code login."""
    account_file = _resolve_account_file(account_file)
    if not os.path.exists(account_file) or not await cookie_auth(account_file):
        if not handle:
            result = _build_login_result(False, "cookie_invalid", "cookie 文件不存在或已失效", account_file)
            return result if return_detail else False
        baijiahao_logger.info(_msg("🥹", "cookie file is missing or expired. Opening a browser, scan the QR code to log in"))
        result = await baijiahao_cookie_gen(account_file, qrcode_callback=qrcode_callback, headless=headless)
        return result if return_detail else result["success"]

    result = _build_login_result(True, "cookie_valid", "cookie 有效", account_file)
    return result if return_detail else True


class BaiJiaHaoVideo(BaseVideoUploader):
    """Baijiahao video upload.

    Flow: open the publish page → upload the video file → fill in the title → wait for upload/transcoding to finish → wait for the cover to be generated → click publish.
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
        collection_name: str | None = None,
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
        self.collection_name = collection_name
        self.debug = debug
        self.headless = headless
        self.local_executable_path = LOCAL_CHROME_PATH
        self.max_title_length = 30

    async def validate_upload_args(self):
        if not os.path.exists(self.account_file):
            raise RuntimeError(f"cookie file does not exist, log in to Baijiahao first: {self.account_file}")
        if not await cookie_auth(self.account_file):
            raise RuntimeError(f"cookie file has expired, log in to Baijiahao first: {self.account_file}")
        if not self.title or not str(self.title).strip():
            raise ValueError("Video title must not be empty")
        if not self.thumbnail_path:
            raise ValueError("Publishing a Baijiahao video requires a landscape cover image (--thumbnail)")
        self.file_path = str(self.validate_video_file(self.file_path))
        self.thumbnail_path = str(self.validate_image_file(self.thumbnail_path))

    async def upload(self, playwright: Playwright) -> None:
        baijiahao_logger.info(_msg("🧍", "Checking the cookie and the video file first"))
        await self.validate_upload_args()
        baijiahao_logger.info(_msg("🥳", "Pre-upload checks passed"))

        browser = await playwright.chromium.launch(**_build_launch_kwargs(headless=self.headless))
        context = await browser.new_context(storage_state=self.account_file)
        await context.grant_permissions(["geolocation"])

        try:
            page = await context.new_page()
            await page.goto(BAIJIAHAO_PUBLISH_URL, timeout=120000, wait_until="domcontentloaded")
            baijiahao_logger.info(_msg("🏃", f"Starting video upload: {self.title}"))

            # Wait for the publish page to load
            await page.wait_for_timeout(3000)

            # 1) Upload the video file
            file_input = page.locator('input[type="file"][accept*="video"], input[type="file"][accept*="mp4"]').first
            if not await file_input.count():
                file_input = page.locator("div[class^='video-main-container'] input[type='file']").first
            if not await file_input.count():
                file_input = page.locator('input[type="file"]').first
            await file_input.wait_for(state="attached", timeout=30000)
            await file_input.set_input_files(self.file_path)
            baijiahao_logger.info(_msg("🏃", f"Video file selected: {self.file_path}"))

            # 2) Wait for the form page (the form has rendered once the contenteditable title area appears)
            title_editor = page.locator('div[class*="contentEditable"]').first
            await title_editor.wait_for(state="visible", timeout=180000)
            await page.wait_for_timeout(1000)

            # 3) Fill in the title
            await self._fill_title(page)

            # 4) Wait for the video upload to finish
            await self._wait_upload_complete(page)

            # 5) Upload the landscape cover (required)
            await self._upload_thumbnail(page)

            # 6) Tick 含AI生成内容 (Contains AI-generated content)
            await self._check_ai_declaration(page)

            # 7) Choose a collection (if configured)
            await self._apply_collection(page)

            # 8) Click publish
            await self._submit_publish(page)

            # Save the cookie
            await context.storage_state(path=self.account_file)
            baijiahao_logger.success(_msg("🥳", "cookie updated"))
        finally:
            await context.close()
            await browser.close()

    async def _fill_title(self, page: Page) -> None:
        title_field = page.locator('div[class*="contentEditable"]').first
        await title_field.wait_for(state="visible", timeout=15000)
        title = self.title
        # Baijiahao titles need at least 9 characters
        if len(title) <= 8:
            title += " 你不知道的"
        title = title[: self.max_title_length]
        # Clear the existing content (the file name may have been filled in automatically), then type the title
        await title_field.click()
        await page.keyboard.press("Control+a")
        await page.keyboard.press("Backspace")
        await title_field.fill(title)
        baijiahao_logger.info(_msg("🏷️", f"Title filled in: {title}"))

    async def _wait_upload_complete(self, page: Page, timeout: int = 600) -> None:
        """Wait until the video upload has really finished.

        Baidu's real upload progress is a percentage text (9%…99%; it disappears when the upload is done, about 35s for this file in testing).
        The old implementation used 'div .cover-overlay:has-text("上传中")' ("uploading"); testing showed that element never exists,
        so it wrongly decided "upload finished" right after the file was chosen (about 4s). A large file is still uploading in the background then, and clicking
        publish is rejected by Baidu with "确保视频已经上传完毕" ("make sure the video has finished uploading"), producing 0 posts. Now the percentage progress is tracked:
        the upload only counts as finished once progress has appeared and then disappeared or reached 100%.
        """
        import re as _re
        start = time.monotonic()
        seen_progress = False
        gone_count = 0
        while True:
            if time.monotonic() - start > timeout:
                baijiahao_logger.warning(_msg("⚠️", f"Timed out waiting for the upload (>{timeout}s), continuing with the next steps"))
                return

            body = ""
            try:
                body = await page.inner_text("body")
            except Exception:
                pass

            if "上传失败" in body:  # "上传失败" = upload failed
                raise RuntimeError("Video upload failed")

            m = _re.search(r'(\d{1,3})\s*%', body)
            pct = int(m.group(1)) if m else None

            if pct is not None and pct < 100:
                seen_progress = True
                gone_count = 0
                baijiahao_logger.info(_msg("🏃", f"Uploading {pct}%"))
                await asyncio.sleep(2)
                continue

            if seen_progress:
                # The percentage has disappeared or reached 100%; treat the upload as finished after two consecutive confirmations
                gone_count += 1
                if gone_count >= 2:
                    baijiahao_logger.success(_msg("🥳", "Video upload finished"))
                    return
                await asyncio.sleep(2)
                continue

            # Progress never appeared: a small file may have finished instantly; let it pass after a 15s window
            if time.monotonic() - start > 15:
                baijiahao_logger.success(_msg("🥳", "Video upload finished"))
                return
            await asyncio.sleep(2)

    async def _upload_thumbnail(self, page: Page) -> None:
        """Upload the landscape cover (required).

        Flow: click 选择封面 (Choose cover) → click the 上传 (Upload) button in the dialog → set the image file → wait for the upload to finish → confirm.
        If no thumbnail_path is given, just wait for the platform to generate the cover automatically.
        """
        if not self.thumbnail_path:
            # No custom cover: wait for the platform to generate one
            await self._wait_cover_ready(page)
            return

        try:
            # 1) Click the 选择封面 (Choose cover) entry
            cover_entry = page.locator('[data-testid="select-cover"]').first
            if not await cover_entry.count():
                # Fallback: locate it by text
                cover_entry = page.get_by_text("选择封面", exact=True).first
            await cover_entry.scroll_into_view_if_needed()
            await cover_entry.click(timeout=10000)
            baijiahao_logger.info(_msg("🏃", "Clicked 选择封面 (Choose cover)"))
            await page.wait_for_timeout(2000)

            # 2) Find the 上传 (Upload) button in the dialog and click it
            # The Baijiahao cover dialog usually has an 上传 (Upload) tab/button
            upload_btn = page.locator('button:has-text("上传"), div:has-text("上传"):not(:has(*)):visible').first
            if not await upload_btn.count():
                upload_btn = page.get_by_text("上传", exact=True).first
            await upload_btn.click(timeout=8000)
            await page.wait_for_timeout(1500)

            # 3) Set the image file on the file input
            # An input[type=file] appears in the dialog
            img_input = page.locator('input[type="file"][accept*="image"], input[type="file"][accept*="jpg"], input[type="file"][accept*="png"]').first
            if not await img_input.count():
                # Generic fallback: the newest file input in the dialog
                img_input = page.locator('input[type="file"]').last
            await img_input.set_input_files(self.thumbnail_path)
            baijiahao_logger.info(_msg("🏃", f"Cover image selected: {self.thumbnail_path}"))

            # 4) Wait for the confirm/done button and click it (if there is a crop dialog).
            #    The crop dialog renders with a delay (image upload + server processing). The old code did a fixed sleep(3s) and then
            #    checked confirm_btn once. If the dialog had not rendered yet, that was taken as "no confirmation needed" and the click was skipped,
            #    so the cover choice was never submitted while the log still said "封面已上传" (cover uploaded). This was the root cause of the
            #    live Baijiahao video with no cover while the log showed success. Now it polls instead (not raising the timeout itself
            #    is not an error: the crop dialog is optional, and not seeing it may mean this flow simply has no such dialog).
            confirm_btn = page.locator('button:has-text("确定"), button:has-text("完成"), button:has-text("确认")').first
            confirmed = False
            try:
                await confirm_btn.wait_for(state="visible", timeout=15000)
                await confirm_btn.click(timeout=8000)
                await page.wait_for_timeout(1000)
                confirmed = True
            except PWTimeoutError:
                baijiahao_logger.debug("Cover confirm button did not appear; this flow may not need a crop confirmation")

            if confirmed:
                baijiahao_logger.success(_msg("🖼️", "Cover uploaded"))
            else:
                # The confirm button never appeared: we cannot tell whether the cover took effect, so do not pretend it succeeded.
                # Hand over to the same "wait for the automatic cover" fallback in the except branch below to verify / fall back.
                raise RuntimeError("Cover confirm button did not appear; cannot confirm that the cover took effect")
        except Exception as exc:
            baijiahao_logger.warning(_msg("⚠️", f"Cover upload failed: {exc}, trying to wait for the automatic cover"))
            # Fallback: wait for the platform to generate one
            await self._wait_cover_ready(page)

    async def _check_ai_declaration(self, page: Page) -> None:
        """Choose the 含AI生成内容 (Contains AI-generated content) creation declaration.

        Click the 请选择创作声明 (Choose a creation declaration) input → a modal opens → pick 含AI生成内容 → click 确定 (OK).
        """
        try:
            # Click the creation declaration input to open the dialog
            trigger = page.locator('input[placeholder="请选择创作声明"]').first
            await trigger.scroll_into_view_if_needed()
            await trigger.click(force=True, timeout=8000)
            await page.wait_for_timeout(3000)

            # Pick 含AI生成内容 in the dialog
            ai_option = page.locator('.cheetah-modal-wrap :text("含AI生成内容")').first
            if not await ai_option.count():
                ai_option = page.locator('text="含AI生成内容"').first
            await ai_option.wait_for(state="visible", timeout=10000)
            await ai_option.click(timeout=5000)
            await page.wait_for_timeout(1000)

            # Click 确定 (OK) to close the dialog (it may still be open after picking)
            modal = page.locator('.cheetah-modal-wrap:visible').first
            if await modal.count():
                confirm_btn = modal.locator('button:has-text("确定")').first
                if await confirm_btn.count() and await confirm_btn.is_visible():
                    await confirm_btn.click(timeout=5000)
                    await page.wait_for_timeout(500)
                else:
                    # OK button not visible: try a force click or press Escape to close
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(500)

            baijiahao_logger.success(_msg("🏷️", "Selected 含AI生成内容 (Contains AI-generated content)"))
        except Exception as exc:
            # On failure, try to close any dialog that may be left open
            try:
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(500)
            except Exception:
                pass
            baijiahao_logger.warning(_msg("⚠️", f"Failed to choose the AI declaration: {exc}"))

    async def _apply_collection(self, page: Page) -> None:
        """Choose a collection (cheetah-select dropdown with search).

        placeholder: "选择同主题的合集，可获得更多播放机会" ("choose a collection on the same topic to get more plays")
        With collection_name set, open the dropdown → search for / select the target collection; otherwise skip.
        """
        if not self.collection_name:
            return
        try:
            # Locate the collection dropdown (by its placeholder text)
            select_box = page.locator('.cheetah-select:has(.cheetah-select-selection-placeholder:has-text("选择同主题的合集"))').first
            if not await select_box.count():
                select_box = page.locator('.cheetah-select-selection-placeholder:has-text("合集")').locator('xpath=ancestor::div[contains(@class,"cheetah-select")]').first
            if not await select_box.count():
                baijiahao_logger.warning(_msg("⚠️", "Collection selector not found, skipping"))
                return

            await select_box.scroll_into_view_if_needed()
            await select_box.click(timeout=8000)
            await page.wait_for_timeout(1500)

            # Type the collection name into the search box (triggers search filtering)
            search_input = select_box.locator('input.cheetah-select-selection-search-input').first
            if await search_input.count():
                await search_input.fill(self.collection_name)
                await page.wait_for_timeout(1500)

            # Select the target collection from the dropdown options
            option = page.locator(f'[role="option"]:has-text("{self.collection_name}"), .cheetah-select-item:has-text("{self.collection_name}")').first
            if await option.count():
                await option.click(timeout=5000)
                await page.wait_for_timeout(500)
                baijiahao_logger.success(_msg("🥳", f"Collection selected: {self.collection_name}"))
            else:
                baijiahao_logger.warning(_msg("⚠️", f"The account has no collection named '{self.collection_name}', skipping"))
                await page.keyboard.press("Escape")
        except Exception as exc:
            baijiahao_logger.warning(_msg("⚠️", f"Failed to choose the collection, skipping: {exc}"))

    async def _wait_cover_ready(self, page: Page, timeout: int = 120) -> None:
        """Wait for Baijiahao to generate the cover image automatically."""
        start = time.monotonic()
        while True:
            if time.monotonic() - start > timeout:
                baijiahao_logger.warning(_msg("⚠️", "Timed out waiting for the cover, publishing anyway"))
                return
            if await page.locator("div.cheetah-spin-container img").count():
                baijiahao_logger.info(_msg("🖼️", "Cover generated"))
                return
            baijiahao_logger.info(_msg("🏃", "Waiting for the cover to be generated..."))
            await asyncio.sleep(3)

    async def _submit_publish(self, page: Page) -> None:
        """Click the publish button and confirm success."""
        # Make sure no leftover dialog is covering the page
        modal = page.locator('.cheetah-modal-wrap:visible').first
        if await modal.count():
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(1000)

        # The Baijiahao publish button has data-testid="publish-btn"
        publish_btn = page.locator('[data-testid="publish-btn"]').first
        if not await publish_btn.count():
            publish_btn = page.locator('button:text-is("发布")').first
        if not await publish_btn.count():
            publish_btn = page.locator('button:has-text("发布")').last
        await publish_btn.wait_for(state="visible", timeout=15000)
        await publish_btn.click(force=True)
        baijiahao_logger.info(_msg("🏃", "Clicked the publish button"))

        # Wait for a redirect or a success message (up to 30s)
        start = time.monotonic()
        while time.monotonic() - start < 30:
            url = page.url
            # Redirect after a successful publish
            if BAIJIAHAO_SUCCESS_URL_PREFIX in url or "/rc/content" in url or "/rc/home" in url:
                baijiahao_logger.success(_msg("🥳", "Video published"))
                return
            # Check whether Baidu's security verification appeared
            if await page.locator('text="百度安全验证"').count():
                raise RuntimeError("Baidu security verification appeared, manual action required")
            # Check for an error message blocking the publish
            error_toast = page.locator('.cheetah-message-error, .cheetah-message-warning').first
            if await error_toast.count() and await error_toast.is_visible():
                err_text = await error_toast.inner_text()
                baijiahao_logger.warning(_msg("⚠️", f"Publish message: {err_text}"))
            await page.wait_for_timeout(1000)

        # Check once more after the timeout
        if BAIJIAHAO_SUCCESS_URL_PREFIX in page.url or "/rc/content" in page.url:
            baijiahao_logger.success(_msg("🥳", "Video published"))
        else:
            raise RuntimeError(f"No redirect to the success page after publishing (30s), current URL: {page.url}")

    async def main(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)
