# -*- coding: utf-8 -*-
"""Weibo video upload + QR-code login.

Features:
  - weibo_cookie_gen: headless QR-code login (Weibo passport QR code)
  - cookie_auth: check whether the cookie is valid
  - weibo_setup: single entry point (check / start login)
  - WeiBoVideo: video upload class

Rewritten from a script recorded with playwright codegen.
Entry page: https://weibo.com/
Publish page: clicking the 「视频」 (Video) entry on the home page opens a new window (the video publish page)
"""
from __future__ import annotations

import asyncio
import inspect
import os
import re
import time
from pathlib import Path

from patchright.async_api import Page, Playwright, TimeoutError as PWTimeoutError, async_playwright

from conf import BASE_DIR, LOCAL_CHROME_HEADLESS, LOCAL_CHROME_PATH
from uploader.base_video import BaseVideoUploader
from utils.log import weibo_logger
from utils.login_qrcode import build_login_qrcode_path, remove_qrcode_file


WEIBO_HOME_URL = "https://weibo.com/"
WEIBO_LOGIN_URL = "https://weibo.com/newlogin?tabtype=weibo&gid=102803&openLoginLayer=0&url=https://weibo.com/"
# Weibo passport QR-code login page (go there directly, skipping the home page popup)
WEIBO_PASSPORT_QR_URL = "https://passport.weibo.com/sso/signin?entry=miniblog&source=miniblog&url=https%3A%2F%2Fweibo.com%2F"

# Weibo passport QR code selectors (the QR code image on the QR-code login page)
QR_SELECTOR = 'img[src*="qrcode"], img[src*="qr"]'


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
        return str((Path(BASE_DIR) / "cookies" / "weibo_uploader" / path).resolve())
    return str(path.resolve())


async def _grab_qr(page: Page, account_file: str) -> dict:
    """Capture the Weibo passport QR code for QR-code login.

    The QR code on the Weibo passport login page may be an img or a canvas, so several selectors are tried.
    """
    # Several possible QR code selectors (the passport page structure may change)
    selectors = [
        'img[src*="qrcode"]',
        'img[src*="qr"]',
        'img[node-type="qrcode_img"]',
        '.qrcode img',
        'canvas',  # some versions draw the QR code on a canvas
    ]

    qr = None
    for sel in selectors:
        loc = page.locator(sel).first
        if await loc.count():
            qr = loc
            weibo_logger.info(_msg("🔍", f"Found QR code element: {sel}"))
            break

    if not qr:
        # Last resort: capture the central area of the whole page
        weibo_logger.warning(_msg("⚠️", "QR code element not found, taking a page screenshot"))
        qrcode_path = build_login_qrcode_path(account_file)
        qrcode_path.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(qrcode_path))
        weibo_logger.info(_msg("🖼️", f"Page screenshot saved to: {qrcode_path}"))
        return {"image_path": str(qrcode_path), "image_data_url": ""}

    await qr.wait_for(state="visible", timeout=30000)

    qrcode_path = build_login_qrcode_path(account_file)
    qrcode_path.parent.mkdir(parents=True, exist_ok=True)

    # Prefer downloading the full-resolution image URL directly (img element)
    tag = await qr.evaluate("el => el.tagName.toLowerCase()")
    if tag == "img":
        src = await qr.get_attribute("src")
        if src and src.startswith("http"):
            try:
                resp = await page.context.request.get(src)
                qrcode_path.write_bytes(await resp.body())
            except Exception:
                await qr.screenshot(path=str(qrcode_path))
        else:
            await qr.screenshot(path=str(qrcode_path))
    else:
        # canvas or another element: take a screenshot directly
        await qr.screenshot(path=str(qrcode_path))

    weibo_logger.info(_msg("🖼️", f"QR code saved to: {qrcode_path}"))
    # The terminal does not render the QR code; only give the file location, and scan the image with the Weibo app
    print(f"Open {qrcode_path} and scan the QR code with the Weibo app to log in")
    return {"image_path": str(qrcode_path), "image_data_url": ""}


async def _is_login_completed(page: Page) -> bool:
    """Check whether the Weibo login is complete: the URL is back on the home page and the user avatar / feed appears."""
    url = page.url
    # Still on the login/passport page
    if "newlogin" in url or "passport" in url:
        return False
    # Check whether we are back on the home page with a logged-in user
    if "weibo.com" in url and "login" not in url:
        # A feed or avatar means the login succeeded
        has_user = await page.locator('[class*="Nav_avatar"], [class*="woo-avatar"]').count()
        if has_user:
            return True
        # A SUB cookie means the login succeeded
        cookies = await page.context.cookies()
        if any(c.get("name") == "SUB" for c in cookies):
            return True
    return False


async def weibo_cookie_gen(account_file, qrcode_callback=None, poll_interval: int = 3, max_checks: int = 120, headless: bool = LOCAL_CHROME_HEADLESS):
    """Headless/headed QR-code login to Weibo, saving the cookie.

    Flow: open the Weibo passport QR-code page directly → capture the QR code → wait for the scan to complete (redirect back to the home page) → save storage_state.
    Returns the standard login result dict.
    """
    account_file = _resolve_account_file(account_file)
    Path(account_file).parent.mkdir(parents=True, exist_ok=True)
    qrcode_path = None
    result = _build_login_result(False, "failed", "微博登录失败", account_file)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**_build_launch_kwargs(headless=headless))
        context = await browser.new_context()
        try:
            page = await context.new_page()
            # Go straight to the passport QR-code login page, skipping the home page's "登录" (Login) button (not visible in headless mode)
            await page.goto(WEIBO_PASSPORT_QR_URL, timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)

            if headless:
                weibo_logger.info(_msg("🧍", "Headless login: the QR code was saved as an image, scan it with the Weibo app"))
            else:
                weibo_logger.info(_msg("🧍", "Scan the QR code in the opened browser to log in to Weibo"))

            # Capture the QR code
            qrcode_info = await _grab_qr(page, account_file)
            qrcode_path = Path(qrcode_info["image_path"]) if qrcode_info.get("image_path") else None
            await _emit_qrcode_callback(qrcode_callback, qrcode_info)

            weibo_logger.info(_msg("🧍", "Scan the QR code; waiting for the login to complete"))

            # Poll until the login completes (the page leaves passport or a logged-in cookie appears)
            for _ in range(max_checks):
                current_url = page.url
                # Leaving the passport page means the login succeeded
                if "passport" not in current_url and "weibo.com" in current_url:
                    weibo_logger.info(_msg("🥳", f"QR code scanned, redirected to: {current_url}"))
                    result = _build_login_result(True, "success", "微博扫码登录成功", account_file, qrcode_info, current_url)
                    break
                # Check whether SUB appears in the cookies (sometimes the page does not redirect but the cookie is already written)
                cookies = await context.cookies()
                if any(c.get("name") == "SUB" and c.get("value") for c in cookies):
                    weibo_logger.info(_msg("🥳", f"QR code scanned (SUB cookie detected), current: {current_url}"))
                    result = _build_login_result(True, "success", "微博扫码登录成功", account_file, qrcode_info, current_url)
                    break
                await page.wait_for_timeout(poll_interval * 1000)
            else:
                result = _build_login_result(False, "timeout", "等待微博扫码登录超时", account_file, qrcode_info, page.url)

            if result["success"]:
                await asyncio.sleep(2)
                await context.storage_state(path=account_file)
                weibo_logger.success(_msg("🥳", f"cookie saved: {account_file}"))
        except Exception as exc:
            result = _build_login_result(False, "failed", str(exc), account_file, current_url=page.url if "page" in locals() else "")
        finally:
            if remove_qrcode_file(qrcode_path):
                weibo_logger.info(_msg("🧹", f"Temporary QR code file removed: {qrcode_path}"))
            if not result["success"]:
                weibo_logger.error(_msg("😢", f"Login failed: {result['message']}"))
            await context.close()
            await browser.close()
    return result


async def cookie_auth(account_file):
    """Check whether the Weibo cookie is valid. Open the home page and look for a login prompt."""
    account_file = _resolve_account_file(account_file)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**_build_launch_kwargs(headless=True))
        try:
            context = await browser.new_context(storage_state=account_file)
            page = await context.new_page()
            await page.goto(WEIBO_HOME_URL, timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)

            # Check whether we were redirected to the login page
            if "newlogin" in page.url or "passport" in page.url:
                weibo_logger.info(_msg("🥹", "cookie expired (redirected to the login page)"))
                return False

            # Check for a 「登录」 (Login) button (shown when not logged in)
            login_btn = page.get_by_text("登录", exact=True).first
            if await login_btn.count() and await login_btn.is_visible():
                weibo_logger.info(_msg("🥹", "cookie expired (login button shown)"))
                return False

            weibo_logger.success(_msg("🥳", "cookie is valid"))
            return True
        except Exception as exc:
            weibo_logger.warning(_msg("😵", f"cookie check failed, treating it as expired: {exc}"))
            return False
        finally:
            await browser.close()


async def weibo_setup(account_file, handle=False, return_detail=False, qrcode_callback=None, headless: bool = LOCAL_CHROME_HEADLESS):
    """Single entry point: check the cookie → if it is invalid and handle=True, start the QR-code login."""
    account_file = _resolve_account_file(account_file)
    if not os.path.exists(account_file) or not await cookie_auth(account_file):
        if not handle:
            result = _build_login_result(False, "cookie_invalid", "cookie 文件不存在或已失效", account_file)
            return result if return_detail else False
        weibo_logger.info(_msg("🥹", "cookie file missing or expired, opening a browser; scan the QR code to log in"))
        result = await weibo_cookie_gen(account_file, qrcode_callback=qrcode_callback, headless=headless)
        return result if return_detail else result["success"]

    result = _build_login_result(True, "cookie_valid", "cookie 有效", account_file)
    return result if return_detail else True


class WeiBoVideo(BaseVideoUploader):
    """Weibo video upload.

    Flow: open the home page → click the 「视频」 (Video) entry to open the publish window → upload the video file →
         wait for the upload to finish → fill in the title → upload the thumbnail → tick 二创 (derivative work) + the AI declaration →
         fill in the description → click Publish.
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
            raise RuntimeError(f"cookie file does not exist, log in to Weibo first: {self.account_file}")
        if not await cookie_auth(self.account_file):
            raise RuntimeError(f"cookie file has expired, log in to Weibo first: {self.account_file}")
        if not self.title or not str(self.title).strip():
            raise ValueError("The video title cannot be empty")
        if not self.thumbnail_path:
            raise ValueError("Publishing a Weibo video requires a thumbnail image (--thumbnail)")
        self.file_path = str(self.validate_video_file(self.file_path))
        self.thumbnail_path = str(self.validate_image_file(self.thumbnail_path))
        # Thumbnail file < 5MB
        thumb_size = Path(self.thumbnail_path).stat().st_size
        if thumb_size > 5 * 1024 * 1024:
            raise ValueError(f"Thumbnail file too large ({thumb_size / 1024 / 1024:.1f}MB), Weibo requires < 5MB")

    async def upload(self, playwright: Playwright) -> None:
        weibo_logger.info(_msg("🧍", "Checking the cookie and video file first"))
        await self.validate_upload_args()
        weibo_logger.info(_msg("🥳", "Pre-upload checks passed"))

        browser = await playwright.chromium.launch(**_build_launch_kwargs(headless=self.headless))
        context = await browser.new_context(
            storage_state=self.account_file,
            viewport={"width": 1280, "height": 2000},  # tall viewport so the publish button etc. stay in the visible area
        )

        try:
            page = await context.new_page()
            await page.goto(WEIBO_HOME_URL, timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            weibo_logger.info(_msg("🏃", f"Start uploading video: {self.title}"))

            # 1) Click the 「视频」 (Video) entry on the home page to open the publish window (popup)
            publish_page = await self._open_video_publish_page(page)

            # 2) Upload the video file
            await self._upload_video_file(publish_page)

            # 3) Wait until the video has really finished uploading (the "上传完成" (upload complete) block is visible)
            await self._wait_upload_complete(publish_page)

            # 4) Type = 二创 (derivative work) (required)
            await self._select_type(publish_page)

            # 5) Content declaration = 含AI生成内容 (contains AI-generated content) (required)
            await self._select_declaration(publish_page)

            # 6) Fill in the title (required)
            await self._fill_title(publish_page)

            # 7) Upload the thumbnail (required)
            await self._upload_thumbnail(publish_page)

            # 8) Collection: pick an existing one, or create it if missing (when collection_name is set)
            if self.collection_name:
                await self._apply_collection(publish_page)

            # 9) Fill in the description (including tags)
            await self._fill_description(publish_page)

            # 10) Click Publish and verify it really succeeded
            await self._submit_publish(publish_page)

            # Save cookies
            await context.storage_state(path=self.account_file)
            weibo_logger.success(_msg("🥳", "cookie updated"))
        finally:
            await context.close()
            await browser.close()

    async def _open_video_publish_page(self, page: Page) -> Page:
        """Click the 「视频」 (Video) entry on the home page and wait for the video publish popup."""
        async with page.expect_popup(timeout=30000) as popup_info:
            # Recorded script: page.locator("span").filter(has_text="视频").click()
            video_btn = page.locator("span").filter(has_text="视频").first
            await video_btn.wait_for(state="visible", timeout=15000)
            await video_btn.click()
        publish_page = await popup_info.value
        await publish_page.wait_for_timeout(3000)
        weibo_logger.info(_msg("🏃", "Video publish page opened"))
        return publish_page

    async def _upload_video_file(self, page: Page) -> None:
        """Click the 「上传视频」 (Upload video) button and set the file."""
        # Recorded script: page2.get_by_role("button", name="上传视频").click()
        upload_btn = page.get_by_role("button", name="上传视频")
        await upload_btn.wait_for(state="visible", timeout=15000)

        # Set the file through the file chooser
        async with page.expect_file_chooser(timeout=10000) as fc_info:
            await upload_btn.click()
        file_chooser = await fc_info.value
        await file_chooser.set_files(self.file_path)
        weibo_logger.info(_msg("🏃", f"Video file selected: {self.file_path}"))

    async def _wait_upload_complete(self, page: Page, timeout: int = 900) -> None:
        """Wait until the video has really finished uploading.

        Real DOM: the upload area has three sibling `_info` blocks (上传中 uploading / 暂停中 paused / 上传完成 upload complete). The states not
        reached yet are hidden with `display:none`; only the block for the current state is visible:
          - Uploading: `<span>上传中</span>` + `269.61MB/269.61MB`
          - Upload complete: `<i class="woo-font woo-font--check">` + `<span>上传完成</span>`
        The only completion signal is the "上传完成" block **becoming visible** (the text of all three blocks is always in the DOM, so text presence cannot be used).
        """
        start = time.monotonic()
        done = page.locator('div:has(> i.woo-font--check) span:text-is("上传完成")').first
        uploading = page.locator('span:text-is("上传中")').first
        last_log = 0.0
        while True:
            if time.monotonic() - start > timeout:
                raise TimeoutError(f"Video upload timed out (>{timeout}s)")

            body = ""
            try:
                body = await page.inner_text("body")
            except Exception:
                pass
            if "上传失败" in body:
                raise RuntimeError("Video upload failed")

            try:
                if await done.is_visible():
                    weibo_logger.success(_msg("🥳", "Video upload finished ('上传完成' visible)"))
                    return
            except Exception:
                pass

            if time.monotonic() - last_log > 5:
                try:
                    if await uploading.is_visible():
                        m = re.search(r"上传中[\s\S]{0,60}?([\d.]+)\s*MB\s*/\s*([\d.]+)\s*MB", body)
                        if m:
                            weibo_logger.info(_msg("🏃", f"Uploading {m.group(1)}/{m.group(2)}MB"))
                        else:
                            weibo_logger.info(_msg("🏃", "Uploading…"))
                except Exception:
                    pass
                last_log = time.monotonic()
            await asyncio.sleep(2)

    async def _fill_title(self, page: Page) -> None:
        """Fill in the title (at most 30 characters)."""
        title_field = page.get_by_placeholder("填写标题（0～30个字）")
        await title_field.wait_for(state="visible", timeout=15000)
        title = self.title[:self.max_title_length]
        await title_field.click()
        await title_field.fill(title)
        weibo_logger.info(_msg("🏷️", f"Title filled in: {title}"))

    async def _upload_thumbnail(self, page: Page) -> None:
        """Upload the thumbnail (required).

        Real DOM / pitfalls:
          - The main form's `<a>上传封面</a>` (Upload thumbnail) → opens the 「编辑封面」 (Edit thumbnail) layer `_layer_1mhd8_153` (the layer contains
            `input[type=file]._file_1mhd8_65`, which accepts set_input_files directly).
          - **Main pitfall**: after an image is chosen the thumbnail goes through **server-side cropping**; meanwhile the layer shows "裁切处理中/处理中请稍后…" (cropping, please wait),
            and clicking the "完成" (Done) button has no effect yet. While the 「编辑封面」 layer is open, Weibo sets the **main form layer
            `_layer_19x8d_246` to display:none** → the collection switch / publish button afterwards all have 0 size and cannot be clicked.
          - So we must: wait until cropping finishes (cropper shows a blob image and there is no "处理中" text) → click "完成" →
            **confirm the Edit thumbnail layer has closed** (otherwise retry / raise); only then does the main form become visible again.
        """
        # Open 「上传封面」 (Upload thumbnail)
        upload_link = page.get_by_role("link", name="上传封面").first
        if not await upload_link.count():
            upload_link = page.locator('a:has-text("上传封面")').first
        await upload_link.wait_for(state="visible", timeout=20000)
        await upload_link.click()
        await page.wait_for_timeout(1200)

        # The 「编辑封面」 (Edit thumbnail) layer
        cover_layer = page.locator('div.wbpro-layer:has(div:text-is("编辑封面"))').first
        await cover_layer.wait_for(state="visible", timeout=15000)

        # Set the thumbnail file (.first hits the visible main input; .last hits the 0-size cropper in a hidden panel,
        # which leaves "裁切处理中" (cropping) stuck forever and never sends the picupload request)
        file_input = page.locator('input[type="file"][accept*="jpg"]').first
        await file_input.wait_for(state="attached", timeout=15000)
        await file_input.set_input_files(self.thumbnail_path)
        weibo_logger.info(_msg("🏃", f"Thumbnail image selected: {self.thumbnail_path}"))

        # cropper renders the image locally (within seconds)
        blob_img = page.locator('.cropper-container img[src^="blob:"], .wb_cropper img[src^="blob:"]').first
        try:
            await blob_img.wait_for(state="attached", timeout=20000)
        except PWTimeoutError:
            weibo_logger.warning(_msg("⚠️", "cropper shows no blob image, trying to click Done anyway"))
        await page.wait_for_timeout(500)

        # Fault-tolerant finish: cropping time varies with image and network, so do not rely on a fixed duration or on a specific request.
        # Trust only the **real result**: whether the 「编辑封面」 layer has closed. Meanwhile **click "完成" (Done) repeatedly**
        # (clicking during cropping is harmless; the click after it finishes closes the layer), and detect crop/upload errors.
        finish_btn = cover_layer.locator('div.wbpro-layer-btn button:has(span:text-is("完成"))').first
        if not await finish_btn.count():
            finish_btn = cover_layer.locator('button:has(span:text-is("完成"))').first
        closed = False
        last_click = 0.0
        start = time.monotonic()
        while time.monotonic() - start < 300:  # generous 5 minutes
            # Result check: the Edit thumbnail layer is no longer visible → success
            try:
                if not await cover_layer.is_visible():
                    closed = True
                    break
            except Exception:
                closed = True
                break
            # Error detection (crop / format / upload failure)
            try:
                layer_txt = await cover_layer.inner_text()
            except Exception:
                layer_txt = ""
            for err in ("裁切失败", "上传失败", "图片格式", "封面上传失败", "重新上传", "格式不支持"):
                if err in layer_txt:
                    raise RuntimeError(f"Thumbnail crop/upload failed: {err}")
            # Click "完成" (Done) periodically (every 4s; skip when clearly disabled)
            if time.monotonic() - last_click > 4:
                try:
                    if await finish_btn.count() and await finish_btn.is_visible():
                        if (await finish_btn.get_attribute("aria-disabled")) != "true":
                            await finish_btn.click(timeout=3000)
                except Exception:
                    pass
                last_click = time.monotonic()
            await asyncio.sleep(2)
        if not closed:
            raise RuntimeError("After clicking Done on the thumbnail, the Edit thumbnail layer did not close for a long time (>300s); the cropping service may be failing")

        # Confirm the main form layer is visible again (display changes back from none)
        main_form = page.locator('div.wbpro-layer[class*="_layer_19x8d"]').first
        try:
            await main_form.wait_for(state="visible", timeout=10000)
        except PWTimeoutError:
            weibo_logger.warning(_msg("⚠️", "Main form not confirmed visible after the thumbnail layer closed, continuing"))
        weibo_logger.success(_msg("🖼️", "Thumbnail uploaded and done"))

    async def _select_type(self, page: Page) -> None:
        """Type (required): select 「二创」 (derivative work).

        Real DOM: under `<div class="_type_1vpmt_29">` there are two
        `<label class="woo-radio-main"><input type=radio><span class="woo-radio-shadow"><span class="woo-radio-text">二创</span></label>`,
        when selected, the matching `woo-radio-shadow` gets `woo-radio-checked` added.
        """
        label = page.locator('label.woo-radio-main:has(span.woo-radio-text:text-is("二创"))').first
        await label.wait_for(state="visible", timeout=20000)
        await label.click()
        await page.wait_for_timeout(500)

        checked_sel = 'label.woo-radio-main:has(span.woo-radio-text:text-is("二创")) span.woo-radio-checked'
        if not await page.locator(checked_sel).count():
            # Fallback: tick the radio input directly
            try:
                await label.locator('input.woo-radio-input').check()
                await page.wait_for_timeout(300)
            except Exception:
                pass
        if not await page.locator(checked_sel).count():
            raise RuntimeError("Type 「二创」 (derivative work) is not selected")
        weibo_logger.info(_msg("🏷️", "Type selected: 二创 (derivative work)"))

    async def _select_declaration(self, page: Page) -> None:
        """Content declaration (required): select 「含AI生成内容」 (contains AI-generated content).

        Real DOM:
          - Dropdown trigger: `.woo-pop-ctrl` inside `<div class="_gap1_nsgmr_26">` (a wbpro-select with caretDown)
          - Popup: `<div class="_panel_nsgmr_114">`, option `<button class="_option..."><span class="_optionLabel...">含AI生成内容</span></button>`
          - When selected, `._check_nsgmr_237` inside that button gets `_checkActive_nsgmr_251` added (with _checkMark)
          - The bottom `._footer_nsgmr_270 button` ("确定" OK) closes the popup
        """
        # Open the dropdown
        trigger = page.locator('div[class*="_gap1_nsgmr"] .woo-pop-ctrl').first
        if not await trigger.count():
            trigger = page.locator('div:has(> div[class*="_tit1_nsgmr"]) .woo-pop-ctrl').first
        await trigger.wait_for(state="visible", timeout=15000)
        await trigger.click()
        await page.wait_for_timeout(1000)

        panel = page.locator('div[class*="_panel_nsgmr"]').first
        if await panel.count():
            try:
                await panel.wait_for(state="visible", timeout=8000)
            except PWTimeoutError:
                panel = None
        else:
            panel = None

        scope = panel if panel is not None else page
        ai_opt = scope.locator('button:has(span:text-is("含AI生成内容"))').first
        await ai_opt.wait_for(state="visible", timeout=8000)
        await ai_opt.click()
        await page.wait_for_timeout(500)

        # Check the selected state
        if not await ai_opt.locator('[class*="_checkActive"]').count():
            weibo_logger.warning(_msg("⚠️", "Content declaration 「含AI生成内容」 does not look active, trying to click OK anyway"))

        # Click OK to close the popup
        confirm = scope.locator('div[class*="_footer_nsgmr"] button:has(span:text-is("确定"))').first
        if not await confirm.count():
            confirm = scope.locator('button:has(span:text-is("确定"))').last
        if await confirm.count():
            await confirm.click()
            await page.wait_for_timeout(500)
        weibo_logger.info(_msg("🏷️", "Content declaration selected: 含AI生成内容 (contains AI-generated content)"))

    async def _fill_description(self, page: Page) -> None:
        """Fill in the description area (body + tags).

        Weibo description placeholder: "有什么新鲜事想分享给大家？" (What's new you want to share?)
        Tags are inserted at the end of the description in #topic# format.
        """
        desc_field = page.get_by_placeholder("有什么新鲜事想分享给大家？")
        if not await desc_field.count():
            weibo_logger.warning(_msg("⚠️", "Description input not found"))
            return

        # Build the description: body + tags
        content = self.desc
        if self.tags:
            tag_str = " ".join(f"#{t}#" for t in self.tags)
            content = f"{content}\n{tag_str}" if content else tag_str

        if content:
            await desc_field.click()
            await desc_field.fill(content)
            weibo_logger.info(_msg("📝", f"Description filled in ({len(content)} characters)"))

    async def _apply_collection(self, page: Page) -> None:
        """Collection: pick an existing one, or create it if missing.

        Real DOM: turning on the 「合集」 (Collection) switch shows the collection panel `._scroll_19x8d_143`, with one row per existing collection:
        `woo-checkbox` + a read-only `input value="名字(共N集)"` (name (N episodes)); at the end `._add_19x8d_63` (「新建合集」 New collection).
          - Existing: tick the checkbox of the row whose name matches (after removing the "(共N集)" suffix).
          - Missing: click 「新建合集」 → a new row is added (ticked automatically) with an editable input → fill in the collection name (≤12).
        """
        target = (self.collection_name or "").strip()
        if not target:
            return

        # 1) Turn on the collection switch
        block = page.locator('div[class*="_switch_"]:has(div[class*="_tit1_"]:text-is("合集"))').first
        if not await block.count():
            block = page.locator('div:has(> div:text-is("合集")):has(label.woo-switch-main)').first
        try:
            switch_input = block.locator('label.woo-switch-main input.woo-switch-input').first
            try:
                already = await switch_input.is_checked()
            except Exception:
                already = False
            if not already:
                for sw in (
                    block.locator('label.woo-switch-main span[role="switch"]').first,
                    block.locator('label.woo-switch-main').first,
                ):
                    try:
                        await sw.click(timeout=6000)
                    except Exception:
                        try:
                            await sw.click(timeout=4000, force=True)
                        except Exception:
                            continue
                    await page.wait_for_timeout(1000)
                    try:
                        if await switch_input.is_checked():
                            break
                    except Exception:
                        break
        except Exception as exc:
            weibo_logger.warning(_msg("⚠️", f"Error turning on the collection switch, still looking for the panel: {exc}"))

        # 2) Collection panel
        panel = page.locator('div[class*="_scroll_"]:has(div[class*="_add_"])').first
        if not await panel.count():
            panel = page.locator('div:has(> div[class*="_add_"]:has-text("新建合集"))').first
        try:
            await panel.wait_for(state="visible", timeout=8000)
        except PWTimeoutError:
            weibo_logger.warning(_msg("⚠️", "Collection panel not found, skipping the collection"))
            return

        # 3) Match an existing collection (remove the "(共N集)" suffix)
        rows = panel.locator('div[class*="_top2_"]')
        n = await rows.count()
        matched = False
        for i in range(n):
            row = rows.nth(i)
            inp = row.locator('input[type="text"]').first
            if not await inp.count():
                continue
            val = (await inp.get_attribute("value")) or ""
            name = re.sub(r"\(共\d+集\)\s*$", "", val).strip()
            if name and name == target:
                await row.locator('label.woo-checkbox-main').first.click()
                await page.wait_for_timeout(400)
                matched = True
                weibo_logger.info(_msg("🥳", f"Selected existing collection: {target}"))
                break

        # 4) Otherwise create it (best effort: if creating fails, only the collection is skipped; publishing is never interrupted)
        if not matched:
            try:
                add_btn = panel.locator('div[class*="_add_"]:has-text("新建合集")').first
                if not await add_btn.count():
                    add_btn = page.locator('div:has-text("新建合集")').last
                # The 「新建合集」 row is 598px wide and the clickable "＋新建合集" text is on the left; clicking the row's center lands
                # on the empty right side and does nothing. Click the inner "新建合集" text span instead (on the left, always hits onClick).
                add_target = add_btn.get_by_text("新建合集", exact=True).first
                if not await add_target.count():
                    add_target = add_btn
                # The editable input of the new row (inputs of existing rows all have disabled; the new row's does not)
                new_inp = panel.locator('div[class*="_top2_"] input[type="text"]:not([disabled])').last
                created = False
                for _ in range(3):
                    try:
                        await add_target.scroll_into_view_if_needed(timeout=2000)
                    except Exception:
                        pass
                    try:
                        await add_target.click(timeout=4000)
                    except Exception:
                        try:
                            await add_target.click(timeout=3000, force=True)
                        except Exception:
                            try:
                                await add_target.evaluate("el => el.click()")
                            except Exception:
                                pass
                    await page.wait_for_timeout(800)
                    if await new_inp.count() and await new_inp.is_visible():
                        created = True
                        break
                if not created:
                    weibo_logger.warning(_msg("⚠️", f"「新建合集」 (New collection) did not show an input row, skipping the collection and continuing to publish: {target[:12]}"))
                    return
                await new_inp.click()
                await new_inp.fill(target[:12])
                await page.wait_for_timeout(500)
                weibo_logger.info(_msg("🥳", f"Created collection: {target[:12]}"))
            except Exception as exc:
                weibo_logger.warning(_msg("⚠️", f"Creating the collection failed, skipping it and continuing to publish: {exc}"))
                return

    async def _submit_publish(self, page: Page) -> None:
        """Click Publish and verify it really succeeded.

        Real DOM:
          - Publish button: `._check_2z30i_81 button` (text "发布"). The button center may be covered by an empty div,
            so the button's own click is triggered with JS to get past the overlay.
          - The only reliable success signal: the hidden success layer `_layer1_9a8j7_2` changes from `display:none` to **visible**;
            it contains the "再发一条视频" (Post another video) button → use it / that button being visible to confirm real success.
            (The text "视频已上传成功，将在转码后发布" (video uploaded, will publish after transcoding) is a hidden template that is always present and cannot be used as the signal.)
          - No success within 60s → raise (no longer pretend it succeeded), and let the caller record the failure.
        """
        # Close any leftover dropdown / popup
        try:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(300)
        except Exception:
            pass

        publish_btn = page.locator('div[class*="_check_2z30i"] button:has(span:text-is("发布"))').first
        if not await publish_btn.count():
            publish_btn = page.get_by_role("button", name="发布").first
        await publish_btn.wait_for(state="visible", timeout=15000)
        await publish_btn.evaluate("el => el.click()")
        weibo_logger.info(_msg("🏃", "Publish button clicked (JS)"))

        success_layer = page.locator('div[class*="_layer1_9a8j7"]').first
        again_btn = page.locator('button:has(span:text-is("再发一条视频"))').first
        start = time.monotonic()
        while time.monotonic() - start < 60:
            try:
                if await again_btn.is_visible():
                    weibo_logger.success(_msg("🥳", "Video published (「再发一条视频」 appeared)"))
                    return
            except Exception:
                pass
            try:
                if await success_layer.is_visible():
                    weibo_logger.success(_msg("🥳", "Video published (success layer visible)"))
                    return
            except Exception:
                pass
            # Handle a possible second confirmation dialog
            try:
                dialog = page.locator('.woo-dialog-main, .woo-modal-wrap, [class*="Dialog"]').first
                if await dialog.count() and await dialog.is_visible():
                    for name in ("确定", "确认", "继续", "仍然发布", "发布"):
                        cb = dialog.locator(f'button:has(span:text-is("{name}"))').first
                        if await cb.count() and await cb.is_visible():
                            await cb.evaluate("el => el.click()")
                            weibo_logger.info(_msg("🏃", f"Confirmed dialog: {name}"))
                            break
            except Exception:
                pass
            await page.wait_for_timeout(1500)

        raise RuntimeError("No success layer / 「再发一条视频」 within 60s after publishing; treating the publish as failed (not saved)")

    async def main(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)
