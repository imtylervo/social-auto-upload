# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import inspect
import json as _json
import os
import re
import time
from pathlib import Path

from patchright.async_api import Page, Playwright, TimeoutError as PWTimeoutError, async_playwright

from conf import BASE_DIR, LOCAL_CHROME_HEADLESS, LOCAL_CHROME_PATH
from uploader.base_video import BaseVideoUploader
from utils.base_social_media import set_init_script
from utils.log import alipay_logger
from utils.login_qrcode import build_login_qrcode_path
from utils.login_qrcode import decode_qrcode_from_path
from utils.login_qrcode import print_terminal_qrcode
from utils.login_qrcode import remove_qrcode_file

ALIPAY_HOME_URL = "https://c.alipay.com/"
ALIPAY_PORTAL_HOME = "https://c.alipay.com/page/portal/home"
# Content creation platform entry: it must carry _appScene=CONTENT&appId=xxx, otherwise it redirects to the life account signup page
ALIPAY_LIFE_ACCOUNT_URL = "https://c.alipay.com/page/life-account/index?_appScene=CONTENT&appId=2030022469359777"
ALIPAY_POSTS_URL = "https://c.alipay.com/page/content-creation/posts"


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
        return str((Path(BASE_DIR) / "cookies" / "alipay_uploader" / path).resolve())

    return str(path.resolve())


def format_title_with_tags(title: str, tags: list[str], max_length: int = 30) -> str:
    """Alipay life account tags use the #tag format; they are appended to the title and typed into the title field together.

    Truncates on tag boundaries: the title is kept whole first, then tags are appended one by one; a tag that does not fit is **dropped entirely**,
    never leaving half a tag or a bare `#`. This avoids triggering Alipay's "broken word" optimization popup, which blocks publishing.
    """
    if not tags:
        return title[:max_length]
    result = title
    for tag in tags:
        candidate = result + " #" + tag.strip("#")
        if len(candidate) > max_length:
            break
        result = candidate
    return result


async def _capture_alipay_qr(page: Page, account_file: str, previous_qrcode_path: Path | None = None) -> dict:
    """Screenshot the QR code strictly from the fixed DOM of the Alipay login page (only the QR tab + barcode canvas count)."""
    login_iframe = page.locator('iframe[title="login"]')
    await login_iframe.first.wait_for(state="attached", timeout=30000)
    frame = page.frame_locator('iframe[title="login"]')

    try:
        await frame.locator("#J-loginMethod-tabs").first.wait_for(state="visible", timeout=15000)
        # Always switch to the QR tab (if it is already the QR tab, clicking again has no side effect)
        await frame.locator("#J-loginMethod-tabs li[data-status='show_qr']").first.click(timeout=5000)
    except PWTimeoutError:
        # Handle the other rendering: the page lands directly on the QR area (no tabs)
        pass

    # Only accept the QR container, not the username/password elements
    await frame.locator("#J-qrcode, #J-barcode-container").first.wait_for(state="visible", timeout=25000)
    await frame.locator("#J-barcode-container canvas.barcode, #J-barcode-container canvas").first.wait_for(state="visible", timeout=25000)

    # The username/password area should be hidden in QR mode
    try:
        login_panel = frame.locator("#J-login")
        if await login_panel.count():
            klass = (await login_panel.first.get_attribute("class") or "")
            if "fn-hide" not in klass:
                raise RuntimeError("Still on the username/password login panel (#J-login is not hidden)")
    except RuntimeError:
        raise
    except Exception:
        pass

    qrcode_path = build_login_qrcode_path(account_file)
    qrcode_path.parent.mkdir(parents=True, exist_ok=True)

    qr_canvas = frame.locator("#J-barcode-container canvas.barcode, #J-barcode-container canvas").first
    await qr_canvas.screenshot(path=str(qrcode_path), timeout=15000)

    qrcode_content = decode_qrcode_from_path(qrcode_path)
    if previous_qrcode_path and previous_qrcode_path != qrcode_path:
        if remove_qrcode_file(previous_qrcode_path):
            alipay_logger.info(_msg("🧹", f"Temporary QR code file removed: {previous_qrcode_path}"))
    alipay_logger.info(_msg("🖼️", f"QR code saved to: {qrcode_path}"))
    if qrcode_content:
        print_terminal_qrcode(qrcode_content, qrcode_path, "支付宝APP")
    else:
        alipay_logger.warning(_msg("😵", f"The terminal cannot show the full QR code, open {qrcode_path} and scan it"))
    return {"image_path": str(qrcode_path), "image_data_url": ""}


async def alipay_cookie_gen(account_file, qrcode_callback=None, poll_interval: int = 3, max_checks: int = 100, headless: bool = LOCAL_CHROME_HEADLESS):
    """Open a browser, let the user log in to the Alipay life account by scanning the QR code, and save the cookie after a successful login (mirrors douyin_cookie_gen).

    The QR code png is written to the cookies directory (*login_qrcode*.png) for terminal display / to report its location; qrcode_callback is optional (e.g. relogin pushes it to Feishu).
    With headless=False the QR code can also be scanned directly in the browser window that opens.
    Returns the result dict from _build_login_result.
    """
    account_file = _resolve_account_file(account_file)
    Path(account_file).parent.mkdir(parents=True, exist_ok=True)
    qrcode_path = None
    result = _build_login_result(False, "failed", "支付宝登录失败", account_file)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**_build_launch_kwargs(headless=headless))
        context = await browser.new_context()
        try:
            page = await context.new_page()
            # Note: do not use set_init_script(stealth). Tests showed that stealth prevents the Alipay login iframe from being injected
            # Open a protected dashboard page first; when not logged in it triggers the login popup (iframe[title="login"], injected asynchronously in about 2-4s)
            await page.goto(ALIPAY_PORTAL_HOME, timeout=60000, wait_until="domcontentloaded")
            if headless:
                alipay_logger.info(_msg("🧍", "Headless login: the QR code was saved as an image; scan it in the terminal or open the image (or let the publishing process push it to Feishu)"))
            else:
                alipay_logger.info(_msg("🧍", "Scan the QR code in the opened browser to log in to the Alipay life account (do not close the browser yourself after logging in)"))

            # Wait for the login iframe to appear
            login_iframe = page.locator('iframe[title="login"]')
            for _ in range(30):
                try:
                    if await login_iframe.count():
                        break
                except Exception:
                    pass
                await page.wait_for_timeout(1000)
            else:
                await context.close()
                await browser.close()
                return _build_login_result(False, "timeout", "等待登录弹窗超时（30s），放弃保存", account_file, current_url=page.url)

            # Screenshot the QR code (headless: for the terminal / Feishu; headed: also take one as a backup, not fatal)
            qrcode_info = await _capture_alipay_qr(page, account_file)
            qrcode_path = Path(qrcode_info["image_path"]) if qrcode_info.get("image_path") else None
            await _emit_qrcode_callback(qrcode_callback, qrcode_info)
            alipay_logger.info(_msg("🧍", "Scan the QR code; waiting for the login to complete"))

            # Poll until login completes: the login iframe disappears (after a successful login the auth page redirects away)
            for _i in range(max_checks):  # wait at most 3-5 minutes
                if await _is_alipay_login_completed(page, login_iframe):
                    alipay_logger.info(_msg("🥳", f"QR code scanned, redirected to the logged-in page: {page.url}"))
                    result = _build_login_result(True, "success", "支付宝扫码登录成功", account_file, qrcode_info, page.url)
                    break
                await page.wait_for_timeout(poll_interval * 1000)
            else:
                result = _build_login_result(False, "timeout", "等待支付宝扫码登录超时", account_file, qrcode_info, page.url)

            if result["success"]:
                await asyncio.sleep(2)
                await context.storage_state(path=account_file)
                # Login finished; do a light check that the cookie file contains something
                try:
                    _d = _json.load(open(account_file))
                    _has_cookie = any(c.get("value") for c in _d.get("cookies", []))
                    if not _has_cookie:
                        result = _build_login_result(False, "cookie_invalid", "支付宝扫码流程结束，但 cookie 为空", account_file, qrcode_info, page.url)
                except Exception as _e:
                    alipay_logger.warning(_msg("⚠️", f"Cookie file check failed (ignored, treated as success): {_e}"))
        except Exception as exc:
            result = _build_login_result(False, "failed", str(exc), account_file, current_url=page.url if "page" in locals() else "")
        finally:
            if remove_qrcode_file(qrcode_path):
                alipay_logger.info(_msg("🧹", f"Temporary QR code file removed: {qrcode_path}"))
            if not result["success"]:
                alipay_logger.error(_msg("😢", f"Login failed: {result['message']}"))
            await context.close()
            await browser.close()
    return result


async def _is_alipay_login_completed(page: Page, login_iframe) -> bool:
    # Login counts as successful when the login iframe is gone (the auth page redirects away after login) and the URL is back on the c.alipay.com dashboard, not a login page
    try:
        if await login_iframe.count() != 0:
            return False
        url = page.url
        if url.startswith("https://c.alipay.com/") and "login" not in url.lower():
            return True
    except Exception:
        return False
    return False


async def cookie_auth(account_file):
    account_file = _resolve_account_file(account_file)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**_build_launch_kwargs(headless=True))
        try:
            context = await browser.new_context(storage_state=account_file)
            page = await context.new_page()
            await page.goto(ALIPAY_LIFE_ACCOUNT_URL, timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)

            # Login redirects the whole page to auth.alipay.com; the cookie is valid only if we stay on c.alipay.com and not on a login page
            url = page.url
            if url.startswith("https://auth.alipay.com/") or "login" in url.lower():
                alipay_logger.info(_msg("🥹", "Cookie has expired (redirected to the login page)"))
                return False
            if await page.locator('iframe[title="login"]').count():
                alipay_logger.info(_msg("🥹", "Cookie has expired (login popup appeared)"))
                return False

            alipay_logger.success(_msg("🥳", "Cookie is valid"))
            return True
        except Exception as exc:
            alipay_logger.warning(_msg("😵", f"Error while checking the cookie, treated as expired: {exc}"))
            return False
        finally:
            await browser.close()


async def alipay_setup(account_file, handle=False, return_detail=False, qrcode_callback=None, headless: bool = LOCAL_CHROME_HEADLESS):
    account_file = _resolve_account_file(account_file)
    if not os.path.exists(account_file) or not await cookie_auth(account_file):
        if not handle:
            result = _build_login_result(False, "cookie_invalid", "cookie 文件不存在或已失效", account_file)
            return result if return_detail else False
        alipay_logger.info(_msg("🥹", "Cookie file is missing or expired; opening a browser, scan the QR code to log in"))
        result = await alipay_cookie_gen(account_file, qrcode_callback=qrcode_callback, headless=headless)
        return result if return_detail else result["success"]

    result = _build_login_result(True, "cookie_valid", "cookie 有效", account_file)
    return result if return_detail else True


class AlipayVideo(BaseVideoUploader):
    def __init__(
        self,
        title,
        file_path,
        tags,
        account_file,
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
        self.desc = desc or ""
        self.thumbnail_path = thumbnail_path
        self.collection_name = collection_name
        self.debug = debug
        self.headless = headless
        self.local_executable_path = LOCAL_CHROME_PATH
        self.max_title_length = 30

    async def validate_upload_args(self):
        if not os.path.exists(self.account_file):
            raise RuntimeError(f"Cookie file does not exist, log in to the Alipay life account first: {self.account_file}")
        if not await cookie_auth(self.account_file):
            raise RuntimeError(f"Cookie file has expired, log in to the Alipay life account first: {self.account_file}")
        if not self.title or not str(self.title).strip():
            raise ValueError("title is required in video mode")
        self.file_path = str(self.validate_video_file(self.file_path))
        if self.thumbnail_path:
            self.thumbnail_path = str(self.validate_image_file(self.thumbnail_path))

    async def open_upload_page(self, page: Page) -> None:
        # Open the content creation platform home and click the "发布视频" (Publish video) card (JS navigation) to reach the short video publish form
        await page.goto(ALIPAY_LIFE_ACCOUNT_URL, timeout=120000, wait_until="domcontentloaded")
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        publish_entry = page.locator('a:has-text("发布视频推荐分辨率720p及以上，建议1080p")').first
        try:
            await publish_entry.wait_for(state="visible", timeout=30000)
            await publish_entry.click()
        except Exception as exc:
            alipay_logger.warning(_msg("😵", f"Failed to click the 发布视频 (Publish video) entry: {exc}"))
            raise

        await page.wait_for_url("**/content-creation/publish/short-video**", timeout=60000)

    async def upload_video_file(self, page: Page, file_path: str) -> None:
        file_input = page.locator('input[type="file"]').first
        await file_input.wait_for(state="attached", timeout=30000)
        await file_input.set_input_files(file_path)
        alipay_logger.info(_msg("🏃", f"Video file selected: {file_path}"))

    async def fill_title_and_tags(self, page: Page) -> None:
        title_field = page.get_by_placeholder("一个好的标题，能获得更多人的喜欢哦").first
        await title_field.wait_for(state="visible", timeout=30000)
        value = format_title_with_tags(self.title, self.tags, max_length=self.max_title_length)
        await title_field.fill(value)
        alipay_logger.info(_msg("🏷️", f"Title filled in ({len(value)} characters including tags): {value}"))

    async def fill_description(self, page: Page) -> None:
        if not self.desc:
            return
        desc_field = page.get_by_placeholder("填写作品描述，让你的作品更容易被看到").first
        await desc_field.fill(self.desc)
        alipay_logger.info(_msg("🏷️", f"Description filled in: {self.desc[:40]}"))

    async def upload_thumbnail(self, page: Page) -> None:
        if not self.thumbnail_path:
            return
        try:
            # 1) Click the "上传封面" (Upload cover) entry of the publish form, which opens the "截取封面" (Capture cover) dialog
            cover_el = page.get_by_text("上传封面", exact=True).first
            await cover_el.scroll_into_view_if_needed()
            await cover_el.click(timeout=10000)
            await page.wait_for_timeout(2000)

            modal_body = page.locator(".antd5-modal-body").last

            # 2) The dialog first shows two entries, "截取封面/上传封面" (Capture cover / Upload cover); click "上传封面" to open the image upload area
            inner = modal_body.get_by_text("上传封面", exact=True).first
            if await inner.count():
                await inner.click(timeout=8000)
                await page.wait_for_timeout(1500)

            # 3) Click "上传图片" (Upload image) to open the image picker
            upload_img_btn = modal_body.get_by_role("button", name="上传图片").first
            await upload_img_btn.wait_for(state="visible", timeout=10000)
            await upload_img_btn.click()
            await page.wait_for_timeout(1500)

            # 4) Set the image on the newly appeared image file input
            img_input = page.locator('input[type="file"][accept*="jpg"], input[type="file"][accept*="png"]').first
            await img_input.wait_for(state="attached", timeout=10000)
            await img_input.set_input_files(self.thumbnail_path)
            await page.wait_for_timeout(3000)

            # 5) Click "完 成" (Done) in the crop dialog
            done_btn = page.get_by_role("button", name="完 成").first
            if not await done_btn.count():
                done_btn = page.get_by_role("button", name="完成").first
            await done_btn.wait_for(state="visible", timeout=15000)
            await done_btn.click()
            await page.wait_for_timeout(800)
            alipay_logger.success(_msg("🖼️", "Cover uploaded"))
        except Exception as exc:
            alipay_logger.warning(_msg("😵", f"Cover upload failed, skipping and continuing: {exc}"))

    async def apply_collection(self, page: Page) -> None:
        if not self.collection_name:
            return
        try:
            # antd5-select: click the clickable toggle of the collection dropdown (the parent container of the compilation input) to open the options
            compilation = page.locator('input[id*="_compilationInfo"]').first
            await compilation.scroll_into_view_if_needed()
            select = compilation.locator("xpath=../../..").first
            if not await select.count():
                select = page.locator(
                    '.antd5-select:has(.antd5-select-selection-placeholder)'
                ).first
            await select.click(timeout=8000)
            await page.wait_for_timeout(2000)

            # Look for the mapped collection name only among the options; if it is not found, skip the collection (once the user creates it manually it will be selected automatically)
            options = page.locator('[role="option"]')
            target = options.filter(has_text=self.collection_name).first
            if await target.count():
                try:
                    await target.click(timeout=5000, force=True)
                except Exception:
                    await target.scroll_into_view_if_needed()
                    await target.click(timeout=5000)
                await page.wait_for_timeout(800)
                alipay_logger.success(_msg("🥳", f"Collection selected: {self.collection_name}"))
                return

            alipay_logger.warning(_msg("😵", f"The account has no collection '{self.collection_name}', skipping the collection"))
            await page.keyboard.press("Escape")
        except Exception as exc:
            alipay_logger.warning(_msg("😵", f"Failed to select the collection, skipping it and continuing to publish: {exc}"))

    async def check_ai_label(self, page: Page) -> None:
        # The author statement is a radio group (default "内容无需标注" (no label needed), NO_STATEMENT); use radio.check() to select "内容由AI生成" (AI-generated content, A_AG3)
        ai_label = page.locator('label.antd5-radio-wrapper', has_text="内容由AI生成").first
        try:
            if await ai_label.count():
                radio = ai_label.locator('input[type="radio"]').first
                await radio.scroll_into_view_if_needed()
                await radio.check(timeout=5000)
                await page.wait_for_timeout(500)
                alipay_logger.success(_msg("🏷️", "Checked 内容由AI生成 (AI-generated content)"))
        except Exception as exc:
            alipay_logger.warning(_msg("😵", f"Failed to check 内容由AI生成 (AI-generated content): {exc}"))

    async def wait_for_upload_complete(self, page: Page, timeout: int = 1800) -> None:
        # Wait until the "确认发布" (Confirm publish) button becomes clickable (video upload + transcoding done)
        publish_btn = page.get_by_role("button", name="确认发布").first
        start = time.monotonic()
        while True:
            if time.monotonic() - start > timeout:
                raise TimeoutError(f"Timed out waiting for video upload/transcoding (>{timeout}s); the confirm publish button never became available")
            try:
                if not await publish_btn.count():
                    await asyncio.sleep(2)
                    continue
                if await publish_btn.is_disabled():
                    alipay_logger.info(_msg("🏃", "Uploading/transcoding the video..."))
                    await asyncio.sleep(2)
                    continue
                alipay_logger.success(_msg("🥳", "Video upload finished"))
                return
            except Exception:
                alipay_logger.info(_msg("🏃", "Uploading/transcoding the video..."))
                await asyncio.sleep(2)

    async def submit_publish(self, page: Page) -> None:
        publish_btn = page.get_by_role("button", name="确认发布").first
        await publish_btn.wait_for(state="visible", timeout=30000)
        # On some accounts the click does not go to posts right away, so also watch for the success toast text
        if await publish_btn.is_disabled():
            raise RuntimeError("The confirm publish button is still not clickable, cannot submit")

        # Capture only the key requests of the submit stage, used to find the root cause on failure
        net_events: list[tuple[str, str, int | None, str]] = []
        req_events: list[tuple[str, str, str]] = []
        net_tasks: list[asyncio.Task] = []

        async def _collect_click_diag(tag: str):
            try:
                diag = await page.evaluate(
                    """
                    () => {
                      const btns = Array.from(document.querySelectorAll('button')).filter(b => (b.innerText || '').includes('确认发布'));
                      const confirmButtons = btns.map((b, i) => {
                        const r = b.getBoundingClientRect();
                        const cx = r.left + r.width / 2;
                        const cy = r.top + r.height / 2;
                        const topEl = document.elementFromPoint(cx, cy);
                        return {
                          i,
                          text: (b.innerText || '').trim(),
                          disabled: !!b.disabled,
                          ariaDisabled: b.getAttribute('aria-disabled'),
                          className: b.className,
                          rect: { x: r.x, y: r.y, w: r.width, h: r.height },
                          topElement: topEl ? `${topEl.tagName}.${topEl.className || ''}` : null,
                        };
                      });

                      const visibleModals = Array.from(document.querySelectorAll('.antd5-modal-wrap, .antd5-message, .antd5-notification')).filter(el => {
                        const st = window.getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        return st.display !== 'none' && st.visibility !== 'hidden' && r.width > 0 && r.height > 0;
                      }).slice(0, 5).map(el => ({
                        cls: el.className,
                        text: (el.textContent || '').trim().slice(0, 120),
                      }));

                      const errorHints = Array.from(document.querySelectorAll('.antd5-form-item-explain-error, .ant-form-item-explain-error, [class*="error"]')).map(el => (el.textContent || '').trim()).filter(Boolean).slice(0, 8);

                      return {
                        url: location.href,
                        title: document.title,
                        readyState: document.readyState,
                        confirmButtons,
                        visibleModals,
                        errorHints,
                        activeElement: document.activeElement ? `${document.activeElement.tagName}.${document.activeElement.className || ''}` : null,
                      };
                    }
                    """
                )
                alipay_logger.info(_msg("🔍", f"{tag}: {_json.dumps(diag, ensure_ascii=False)[:1000]}"))
            except Exception as exc:
                alipay_logger.warning(_msg("🔍", f"{tag}: diagnostics collection failed: {exc}"))

        def _watch_url(url: str) -> bool:
            u = (url or "").lower()
            return any(k in u for k in (
                "publish",
                "publishshortvideo",
                "content-creation",
                "posts",
                "submit",
                "short-video",
                "captcha.alipay.com/api/v1/captcha/verify",
            ))

        async def _collect_response(resp):
            try:
                if not _watch_url(resp.url):
                    return
                status = resp.status
                text = ""
                req_body = ""
                try:
                    req_body = (resp.request.post_data or "").strip().replace("\n", " ")
                except Exception:
                    req_body = ""
                ct = (resp.headers or {}).get("content-type", "").lower()
                if "json" in ct or "text" in ct:
                    try:
                        text = (await resp.text() or "").strip().replace("\n", " ")
                    except Exception:
                        text = ""
                merged = f"req={req_body[:180]} resp={text[:180]}".strip()
                net_events.append((resp.request.method, resp.url, status, merged[:380]))
            except Exception:
                pass

        def _on_response(resp):
            try:
                net_tasks.append(asyncio.create_task(_collect_response(resp)))
            except Exception:
                pass

        def _on_request(req):
            try:
                if not _watch_url(req.url):
                    return
                body = (req.post_data or "").strip().replace("\n", " ")
                req_events.append((req.method, req.url, body[:220]))
            except Exception:
                pass

        page.on("response", _on_response)
        page.on("request", _on_request)
        async def _dismiss_quality_modal() -> bool:
            """After clicking "确认发布" (Confirm publish), Alipay may show a quality popup "发现N个优化项" (N optimization items found) (cover broken word /
            title broken word, etc.), which blocks the real submit and causes a 90s timeout. In the popup, "继续发布" (Continue publishing) lets it through;
            "返回更换" (Go back and change) looks like the primary button but goes back to editing, so click "继续发布" by its text.
            Returns whether "继续发布" was clicked."""
            try:
                btn = page.locator(
                    '.antd5-modal-wrap button:has-text("继续发布"), '
                    '.antd5-modal button:has-text("继续发布")'
                ).first
                if await btn.count() and await btn.is_visible():
                    await btn.click(timeout=3000)
                    alipay_logger.info(_msg("✅", "Clicked 继续发布 (Continue publishing) in the optimization popup to let the submit through"))
                    await page.wait_for_timeout(500)
                    return True
            except Exception as exc:
                alipay_logger.warning(_msg("😵", f"Failed to click 继续发布 (Continue publishing): {exc}"))
            return False

        await _collect_click_diag("点击前")
        await publish_btn.click()
        await page.wait_for_timeout(600)
        await _collect_click_diag("首次点击后")
        # Right after the first click the optimization popup may appear and block; let it through once
        await _dismiss_quality_modal()

        start = time.monotonic()
        timeout = 90
        success_toast = page.locator('.antd5-message-notice-content:has-text("发布成功"), .antd5-message-notice-content:has-text("提交成功"), .antd5-message-notice-content:has-text("提交审核"), .antd5-message-notice-content:has-text("审核中")').first
        fail_toast = page.locator('.antd5-message-notice-content:has-text("发布失败"), .antd5-message-notice-content:has-text("提交失败"), .antd5-message-notice-content:has-text("请稍后重试")').first

        retried_after_aigc = False
        submit_click_retries = 0
        last_click_ts = start
        try:
            while time.monotonic() - start <= timeout:
                if "/content-creation/posts" in page.url:
                    alipay_logger.success(_msg("🥳", "Video published successfully"))
                    return

                # The optimization popup may appear later and block the submit at any time; click "继续发布" whenever it shows up
                await _dismiss_quality_modal()

                # After the AIGC preprocessing path is hit, the page usually stays on the publish page; confirm publish must be clicked again to really submit
                try:
                    saw_aigc_done = any(
                        ("querylooptask" in u.lower() and '"done":true' in (b or "").lower())
                        for _, u, _, b in net_events
                    )
                    if saw_aigc_done and not retried_after_aigc:
                        if await publish_btn.count() and not await publish_btn.is_disabled():
                            await publish_btn.click()
                            retried_after_aigc = True
                            alipay_logger.info(_msg("🔁", "AIGC preprocessing finished, clicked confirm publish a second time"))
                            await page.wait_for_timeout(500)
                            await _collect_click_diag("AIGC后二次点击后")
                except Exception:
                    pass

                # Main criterion: at least one captcha verify / publishShortVideo request must be seen
                saw_captcha_verify = any("captcha.alipay.com/api/v1/captcha/verify" in u.lower() for _, u, _, _ in net_events)
                saw_publish_submit = any("publishshortvideo.json" in u.lower() for _, u, _, _ in net_events)
                no_submit_signal = not (saw_captcha_verify or saw_publish_submit)
                if no_submit_signal and submit_click_retries < 3 and (time.monotonic() - last_click_ts) >= 8:
                    try:
                        if await publish_btn.count() and not await publish_btn.is_disabled():
                            await publish_btn.click()
                            submit_click_retries += 1
                            last_click_ts = time.monotonic()
                            alipay_logger.info(_msg("🔁", f"No submit request detected, clicking confirm publish again ({submit_click_retries}/3)"))
                            await page.wait_for_timeout(500)
                            await _collect_click_diag(f"重试点击后#{submit_click_retries}")
                    except Exception:
                        pass

                try:
                    if await success_toast.count() and await success_toast.is_visible():
                        alipay_logger.success(_msg("🥳", "Video published successfully (toast matched)"))
                        return
                except Exception:
                    pass
                try:
                    if await fail_toast.count() and await fail_toast.is_visible():
                        raise RuntimeError("Publish failed (the page showed a failure message)")
                except RuntimeError:
                    raise
                except Exception:
                    pass
                await page.wait_for_timeout(1000)

            raise RuntimeError(
                f"No success signal detected after publishing (90s), current URL: {page.url}"
            )
        finally:
            page.remove_listener("response", _on_response)
            page.remove_listener("request", _on_request)
            if net_tasks:
                try:
                    await asyncio.wait(net_tasks, timeout=3)
                except Exception:
                    pass
            if req_events:
                alipay_logger.info(_msg("🧾", f"Submit stage: {len(req_events)} request events (last 10)"))
                for m, u, b in req_events[-10:]:
                    alipay_logger.info(_msg("🧾", f"REQ {m} {u} | {b}"))
            if net_events:
                alipay_logger.info(_msg("🧾", f"Submit stage: {len(net_events)} network events (last 10)"))
                for m, u, s, b in net_events[-10:]:
                    alipay_logger.info(_msg("🧾", f"{m} {s} {u} | {b}"))

    async def upload(self, playwright: Playwright) -> None:
        alipay_logger.info(_msg("🧍", "Checking the cookie and the video file first"))
        await self.validate_upload_args()
        alipay_logger.info(_msg("🥳", "Pre-upload checks passed"))

        browser = await playwright.chromium.launch(**_build_launch_kwargs(headless=self.headless))
        context = await browser.new_context(storage_state=self.account_file)
        await context.grant_permissions(["geolocation"])
        # Note: do not use set_init_script(stealth). It prevents the Alipay content creation platform (a qiankun micro-app) from rendering

        try:
            page = await context.new_page()
            await self.open_upload_page(page)
            alipay_logger.info(_msg("🏃", f"Starting video upload: {self.title}"))

            await self.upload_video_file(page, self.file_path)
            await self.fill_title_and_tags(page)
            await self.fill_description(page)
            await self.upload_thumbnail(page)
            await self.apply_collection(page)
            await self.check_ai_label(page)
            await self.wait_for_upload_complete(page)
            await self.submit_publish(page)

            await context.storage_state(path=self.account_file)
            alipay_logger.success(_msg("🥳", "Cookie updated"))
        finally:
            await context.close()
            await browser.close()

    async def alipay_upload_video(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)

    async def main(self):
        await self.alipay_upload_video()
