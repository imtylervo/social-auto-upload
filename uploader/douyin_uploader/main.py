# -*- coding: utf-8 -*-
from datetime import datetime

import asyncio
import inspect
import os
import sys
from pathlib import Path

from patchright.async_api import Page
from patchright.async_api import Playwright
from patchright.async_api import async_playwright

from conf import BASE_DIR, DEBUG_MODE, LOCAL_CHROME_HEADLESS, LOCAL_CHROME_PATH
from uploader.base_video import BaseVideoUploader
from utils.base_social_media import set_init_script
from utils.login_qrcode import build_login_qrcode_path
from utils.login_qrcode import decode_qrcode_from_path
from utils.login_qrcode import print_terminal_qrcode
from utils.login_qrcode import remove_qrcode_file
from utils.login_qrcode import save_data_url_image
from utils.log import douyin_logger

DOUYIN_PUBLISH_STRATEGY_IMMEDIATE = "immediate"
DOUYIN_PUBLISH_STRATEGY_SCHEDULED = "scheduled"


def _msg(emoji: str, text: str) -> str:
    return f"{emoji} {text}"


async def _read_verify_code(code_file: str) -> str:
    if os.path.exists(code_file):
        with open(code_file, encoding="utf-8") as file_obj:
            return file_obj.read().strip()

    if not sys.stdin or not sys.stdin.isatty():
        return ""

    try:
        return (await asyncio.to_thread(input, "请输入抖音短信验证码（直接回车可稍后重试）: ")).strip()
    except (EOFError, OSError):
        return ""


def _msg(emoji: str, text: str) -> str:
    return f"{emoji} {text}"


async def _native_click(page, locator) -> bool:
    """Click an element "like a human": a real mouse click at its center plus a full pointer/mouse event sequence.
    Douyin's identity verification component (uc_verification_component) only reacts to the whole sequence, not a plain click.
    Returns whether the click succeeded."""
    try:
        await locator.scroll_into_view_if_needed(timeout=5000)
    except Exception:
        pass
    try:
        box = await locator.bounding_box()
    except Exception:
        box = None
    if not box:
        try:
            await locator.click(timeout=8000)
            return True
        except Exception:
            return False
    x = box["x"] + box["width"] / 2
    y = box["y"] + box["height"] / 2
    try:
        await page.mouse.move(x, y)
        await asyncio.sleep(0.15)
        await page.mouse.click(x, y)
        await asyncio.sleep(0.2)
        await page.evaluate(
            """({x, y}) => {
                const el = document.elementFromPoint(x, y);
                if (!el) return;
                const opts = {bubbles:true,cancelable:true,composed:true,clientX:x,clientY:y,view:window,pointerId:1,pointerType:'mouse',isPrimary:true,button:0,buttons:1};
                for (const t of ['pointerover','pointerenter','pointerdown','mousedown','pointerup','mouseup','click']) {
                    const C = t.startsWith('pointer') ? PointerEvent : MouseEvent;
                    try { el.dispatchEvent(new C(t, opts)); } catch(e){ try{ el.dispatchEvent(new MouseEvent(t,opts)); }catch(_){} }
                }
            }""",
            {"x": x, "y": y},
        )
        return True
    except Exception:
        return False


async def _emit_qrcode_callback(qrcode_callback, payload: dict):
    if not qrcode_callback:
        return

    callback_result = qrcode_callback(payload)
    if inspect.isawaitable(callback_result):
        await callback_result


def _build_login_result(success: bool, status: str, message: str, account_file: str, qrcode: dict | None = None, current_url: str = "") -> dict:
    return {
        "success": success,
        "status": status,
        "message": message,
        "account_file": str(account_file),
        "qrcode": qrcode,
        "current_url": current_url,
    }


async def cookie_auth(account_file):
    if not os.path.exists(account_file):
        return False

    use_headless = os.environ.get("DOUYIN_COOKIE_AUTH_HEADLESS", "true").lower() in ("1", "true", "yes")
    launch_kwargs = {"headless": use_headless, "channel": "chromium", "args": ["--no-sandbox", "--disable-blink-features=AutomationControlled"]}
    for _attempt in range(3):
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(**launch_kwargs)
            try:
                context = await browser.new_context(storage_state=account_file)
                context = await set_init_script(context)
                page = await context.new_page()
                await page.goto("https://creator.douyin.com/creator-micro/content/upload", wait_until="domcontentloaded", timeout=90000)
                await page.wait_for_timeout(2500)  # wait for the page to settle so a brief redirect is not misread
                has_login = await page.get_by_text("手机号登录").count() or await page.get_by_text("扫码登录").count()
                if "content/upload" in page.url and not has_login:
                    return True
            except Exception:
                pass
            finally:
                await browser.close()
    return False


async def douyin_setup(account_file, handle=False, return_detail=False, qrcode_callback=None, headless: bool = LOCAL_CHROME_HEADLESS, cdp_url: str | None = None):
    if not os.path.exists(account_file) or not await cookie_auth(account_file):
        if not handle:
            result = _build_login_result(False, "cookie_invalid", "cookie文件不存在或已失效", account_file)
            return result if return_detail else False
        douyin_logger.info(_msg("🥹", "Cookie is invalid; opening a browser to log in again"))
        result = await douyin_cookie_gen(account_file, qrcode_callback=qrcode_callback, headless=headless, cdp_url=cdp_url)
        return result if return_detail else result["success"]

    result = _build_login_result(True, "cookie_valid", "cookie有效", account_file)
    return result if return_detail else True


async def _extract_douyin_qrcode_src(page: Page) -> str:
    # Wait for the SPA to finish loading (not only for the "扫码登录" (QR-code login) text, or a slow Douyin load times out after 30s).
    # Give the client JS enough time after domcontentloaded to inject the login card.
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    scan_login_tab = page.get_by_text("扫码登录", exact=True).first
    # attached state: being in the DOM is enough; visible/fully rendered is not required, which avoids a race
    await scan_login_tab.wait_for(state="attached", timeout=60000)

    # The new Douyin creator center (single_tab + animate_qrcode_container) no longer uses aria-label="二维码" (QR code).
    # Try several selectors in order of priority; one match is enough.
    qrcode_selectors = [
        'div#animate_qrcode_container img[src^="data:image"]',
        'div[class*="animate_qrcode_container"] img[src^="data:image"]',
        'div[class*="scan_qrcode_login_content"] img[src^="data:image"]',
        'img[aria-label="二维码"]',
    ]
    last_err: Exception | None = None
    for sel in qrcode_selectors:
        qrcode_img = page.locator(sel).first
        try:
            await qrcode_img.wait_for(state="attached", timeout=10000)
        except Exception as e:
            last_err = e
            continue
        src = await qrcode_img.get_attribute("src")
        if src:
            return src
        last_err = RuntimeError(f"selector {sel} 命中但 src 为空")

    raise RuntimeError(f"Could not get the Douyin login QR code URL (last_err={last_err})")


async def _save_douyin_qrcode(page: Page, account_file: str, previous_qrcode_path: Path | None = None, qrcode_callback=None) -> dict:
    # The QR code src is extracted only to save it and show it in the terminal; failing to find it is not fatal, because the QR code is visible in the headed browser and can be scanned there
    try:
        qrcode_src = await _extract_douyin_qrcode_src(page)
    except Exception as exc:
        douyin_logger.warning(_msg("😵", f"Could not find the QR code element ({str(exc)[:50]}). Scan the code in the browser window that opened; still waiting for the post-login redirect"))
        return {"image_path": "", "image_data_url": ""}
    qrcode_path = save_data_url_image(qrcode_src, build_login_qrcode_path(account_file))
    if previous_qrcode_path and previous_qrcode_path != qrcode_path:
        if remove_qrcode_file(previous_qrcode_path):
            douyin_logger.info(_msg("🧹", f"Temporary QR code file removed: {previous_qrcode_path}"))
    douyin_logger.info(_msg("🖼️", f"QR code is ready, saved to: {qrcode_path}"))
    qrcode_content = decode_qrcode_from_path(qrcode_path)
    if qrcode_content:
        print_terminal_qrcode(qrcode_content, qrcode_path, "抖音APP")
    else:
        douyin_logger.warning(_msg("😵", f"The terminal cannot show the whole QR code; open {qrcode_path} and scan it"))
    qrcode_info = {
        "image_path": str(qrcode_path),
        "image_data_url": qrcode_src,
    }
    await _emit_qrcode_callback(qrcode_callback, qrcode_info)
    return qrcode_info


async def _is_douyin_login_completed(page: Page) -> bool:
    # After login the page goes to some page under creator-micro (home/content etc.); the login page is the creator.douyin.com/ root
    if "creator.douyin.com/creator-micro" not in page.url:
        return False

    login_markers = [
        page.get_by_text("扫码登录", exact=True).first,
        page.get_by_text("手机号登录", exact=True).first,
        page.get_by_text("二维码失效", exact=True).first,
        page.get_by_role("img", name="二维码").first,
    ]

    for marker in login_markers:
        if not await marker.count():
            continue
        try:
            if await marker.is_visible():
                return False
        except Exception:
            continue

    return True


async def _wait_for_douyin_login(page: Page, account_file: str, qrcode_info: dict, qrcode_callback=None, poll_interval: int = 3, max_checks: int = 100) -> dict:
    qrcode_path = Path(qrcode_info["image_path"]) if qrcode_info.get("image_path") else None
    original_url = page.url
    saw_2fa = False
    for _ in range(max_checks):
        if await _is_douyin_login_completed(page):
            douyin_logger.info(_msg("🥳", f"QR code scanned; redirected to the logged-in page: {page.url}"))
            return _build_login_result(True, "success", "抖音扫码登录成功", account_file, qrcode_info, page.url)

        # URL changed but no sessionid yet → second verification step, keep waiting
        if page.url != original_url and not await _is_douyin_login_completed(page):
            sms_input = page.locator('input[placeholder*="验证码"], input[type="tel"], input[placeholder*="短信"], input[placeholder*="手机号"]')
            if await sms_input.count() > 0:
                if not saw_2fa:
                    douyin_logger.warning(_msg("⚠️", f"Douyin SMS/security second verification detected; enter it by hand in the browser window that opened. Waiting for sessionid ({_}/{max_checks})"))
                    saw_2fa = True
            await asyncio.sleep(poll_interval)
            continue

        expired_box = page.get_by_text("二维码失效", exact=True).locator("..").first
        if await expired_box.count() and await expired_box.is_visible():
            douyin_logger.warning(_msg("😵", "QR code expired; refreshing it"))
            await expired_box.click()
            await asyncio.sleep(1)
            qrcode_info = await _save_douyin_qrcode(page, account_file, qrcode_path, qrcode_callback=qrcode_callback)
            qrcode_path = Path(qrcode_info["image_path"]) if qrcode_info.get("image_path") else None

        await asyncio.sleep(poll_interval)

    return _build_login_result(False, "timeout", "等待抖音扫码登录超时", account_file, qrcode_info, page.url)

async def douyin_cookie_gen(
    account_file,
    qrcode_callback=None,
    poll_interval: int = 2,
    max_checks: int = 60,
    headless: bool = LOCAL_CHROME_HEADLESS,
    cdp_url: str | None = None,
):
    async with async_playwright() as playwright:
        if cdp_url:
            browser = await playwright.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            should_close_context = False
        else:
            browser = await playwright.chromium.launch(headless=headless, channel="chromium")
            context = await browser.new_context()
            should_close_context = True
        context = await set_init_script(context)
        qrcode_path = None
        result = _build_login_result(False, "failed", "抖音登录失败", account_file)
        try:
            page = await context.new_page()
            await page.goto("https://creator.douyin.com/")
            qrcode_info = await _save_douyin_qrcode(page, account_file, qrcode_callback=qrcode_callback)
            qrcode_path = Path(qrcode_info["image_path"]) if qrcode_info.get("image_path") else None
            douyin_logger.info(_msg("🧍", "Scan the QR code; waiting for login to finish"))
            result = await _wait_for_douyin_login(
                page,
                account_file,
                qrcode_info,
                qrcode_callback=qrcode_callback,
                poll_interval=poll_interval,
                max_checks=max_checks,
            )
            if result["success"]:
                await asyncio.sleep(2)
                await context.storage_state(path=account_file)
                # Login was confirmed through "发布视频" (Publish video), and storage_state was just taken from the logged-in browser,
                # so skip the flaky browser re-check (that was the old bug that turned a success into a failure).
                # Only do a light check that the file has a sessionid.
                try:
                    import json as _json
                    _d = _json.load(open(account_file))
                    _has_sess = any(c.get("name") == "sessionid" and c.get("value") for c in _d.get("cookies", []))
                    if not _has_sess:
                        result = _build_login_result(
                            False,
                            "cookie_invalid",
                            "抖音扫码流程结束，但 cookie 中无 sessionid",
                            account_file,
                            qrcode_info,
                            page.url,
                        )
                except Exception as _e:
                    douyin_logger.warning(_msg("⚠️", f"Error while checking the cookie file (ignored, treated as success): {_e}"))
        except Exception as exc:
            result = _build_login_result(False, "failed", str(exc), account_file, current_url=page.url if "page" in locals() else "")
        finally:
            if remove_qrcode_file(qrcode_path):
                douyin_logger.info(_msg("🧹", f"Temporary QR code file removed: {qrcode_path}"))
            if not result["success"]:
                douyin_logger.error(_msg("😢", f"Login failed: {result['message']}"))
            if should_close_context:
                await context.close()
            await browser.close()
        return result


class DouYinBaseUploader(BaseVideoUploader):
    def __init__(
        self,
        publish_date: datetime | int,
        account_file,
        publish_strategy: str = DOUYIN_PUBLISH_STRATEGY_IMMEDIATE,
        debug: bool = DEBUG_MODE,
        headless: bool = LOCAL_CHROME_HEADLESS,
    ):
        self.publish_date = publish_date
        self.account_file = account_file
        self.publish_strategy = publish_strategy
        self.debug = debug
        self.date_format = "%Y年%m月%d日 %H:%M"
        self.local_executable_path = LOCAL_CHROME_PATH
        self.headless = headless

    async def validate_base_args(self):
        if not os.path.exists(self.account_file):
            raise RuntimeError(f"Cookie file does not exist; log in to Douyin first: {self.account_file}")
        if not await cookie_auth(self.account_file):
            raise RuntimeError(f"Cookie file is no longer valid; log in to Douyin first: {self.account_file}")
        if self.publish_strategy not in {DOUYIN_PUBLISH_STRATEGY_IMMEDIATE, DOUYIN_PUBLISH_STRATEGY_SCHEDULED}:
            raise ValueError(f"Unsupported publish strategy: {self.publish_strategy}")

        if self.publish_strategy == DOUYIN_PUBLISH_STRATEGY_SCHEDULED:
            self.publish_date = self.validate_publish_date(self.publish_date)
        else:
            self.publish_date = 0

    async def set_schedule_time_douyin(self, page, publish_date):
        label_element = page.locator("[class^='radio']:has-text('定时发布')")
        await label_element.click()
        await asyncio.sleep(1)
        publish_date_hour = publish_date.strftime("%Y-%m-%d %H:%M")

        await asyncio.sleep(1)
        await page.locator('.semi-input[placeholder="日期和时间"]').click()
        await page.keyboard.press("Control+KeyA")
        await page.keyboard.type(str(publish_date_hour))
        await page.keyboard.press("Enter")
        await asyncio.sleep(1)

    async def fill_title_and_description(self, page: Page, title: str, description: str, tags: list[str] | None = None):
        # Douyin publish page DOM as of 2026-06: title=input[placeholder*=填写作品标题], description=div.zone-container[contenteditable]
        # The version_2 (post/video) publish page renders the form only after the video upload finishes (about 40s in testing), so the wait timeout is 120s
        title_input = page.locator('input[placeholder*="填写作品标题"]').first
        await title_input.wait_for(state="visible", timeout=120000)
        await title_input.fill(title[:30])

        description_editor = page.locator('div.zone-container[contenteditable="true"]').first
        await description_editor.wait_for(state="visible", timeout=120000)
        await description_editor.click()
        await page.keyboard.press("Control+KeyA")
        await page.keyboard.press("Delete")

        # Fill the description first, then the #hashtags (the description argument used to be dropped, so Douyin got only tags and no text)
        if description and description.strip():
            await page.keyboard.type(description.strip())

        for tag in tags or []:
            await page.keyboard.type(" #" + tag)
            await page.keyboard.press("Space")
        await page.keyboard.press("Escape")  # close the hashtag dropdown so its overlay does not block later clicks

    async def set_location(self, page: Page, location: str = ""):
        if not location:
            return
        await page.locator('div.semi-select span:has-text("输入地理位置")').click()
        await page.keyboard.press("Backspace")
        await page.wait_for_timeout(2000)
        await page.keyboard.type(location)
        await page.wait_for_selector('div[role="listbox"] [role="option"]', timeout=5000)
        await page.locator('div[role="listbox"] [role="option"]').first.click()

    async def handle_product_dialog(self, page: Page, product_title: str):
        await page.wait_for_timeout(2000)
        await page.wait_for_selector('input[placeholder="请输入商品短标题"]', timeout=10000)
        short_title_input = page.locator('input[placeholder="请输入商品短标题"]')
        if not await short_title_input.count():
            douyin_logger.error(_msg("😵", "Product short title input not found"))
            return False

        product_title = product_title[:10]
        await short_title_input.fill(product_title)
        await page.wait_for_timeout(1000)

        finish_button = page.locator('button:has-text("完成编辑")')
        if "disabled" not in await finish_button.get_attribute("class"):
            await finish_button.click()
            douyin_logger.debug(_msg("🥳", "Clicked the “完成编辑” (Finish editing) button"))
            await page.wait_for_selector(".semi-modal-content", state="hidden", timeout=5000)
            return True

        douyin_logger.error(_msg("😵", "The “完成编辑” (Finish editing) button is disabled; closing the dialog first"))
        cancel_button = page.locator('button:has-text("取消")')
        if await cancel_button.count():
            await cancel_button.click()
        else:
            close_button = page.locator(".semi-modal-close")
            await close_button.click()
        await page.wait_for_selector(".semi-modal-content", state="hidden", timeout=5000)
        return False

    async def set_product_link(self, page: Page, product_link: str, product_title: str):
        await page.wait_for_timeout(2000)
        try:
            await page.wait_for_selector("text=添加标签", timeout=10000)
            dropdown = page.get_by_text("添加标签").locator("..").locator("..").locator("..").locator(".semi-select").first
            if not await dropdown.count():
                douyin_logger.error(_msg("😵", "Tag dropdown not found"))
                return False
            douyin_logger.debug(_msg("🧍", "Found the tag dropdown; about to choose “购物车” (Shopping cart)"))
            await dropdown.click()
            await page.wait_for_selector('[role="listbox"]', timeout=5000)
            await page.locator('[role="option"]:has-text("购物车")').click()
            douyin_logger.debug(_msg("🥳", "Selected “购物车” (Shopping cart)"))

            await page.wait_for_selector('input[placeholder="粘贴商品链接"]', timeout=5000)
            input_field = page.locator('input[placeholder="粘贴商品链接"]')
            await input_field.fill(product_link)
            douyin_logger.debug(_msg("🔗", f"Product link filled in: {product_link}"))

            add_button = page.locator('span:has-text("添加链接")')
            button_class = await add_button.get_attribute("class")
            if "disable" in button_class:
                douyin_logger.error(_msg("😵", "The “添加链接” (Add link) button cannot be clicked right now"))
                return False
            await add_button.click()
            douyin_logger.debug(_msg("🥳", "Clicked the “添加链接” (Add link) button"))

            await page.wait_for_timeout(2000)
            error_modal = page.locator("text=未搜索到对应商品")
            if await error_modal.count():
                confirm_button = page.locator('button:has-text("确定")')
                await confirm_button.click()
                douyin_logger.error(_msg("😢", "This product link is invalid"))
                return False

            if not await self.handle_product_dialog(page, product_title):
                return False

            douyin_logger.debug(_msg("🥳", "Product link is set"))
            return True
        except Exception as e:
            douyin_logger.error(_msg("😢", f"Error while setting the product link: {str(e)}"))
            return False

    async def set_self_declaration(self, page: Page, declaration: str) -> bool:
        """Douyin 「自主声明」 (self-declaration): open the declaration dialog → pick one declaration type → 确定 (OK).

        The real dialog (checked by the user in F12): the header is 「请选择声明类型（单选）」 (choose a declaration type, single choice), and the options are
        the span.semi-radio-addon text inside label.semi-radio. 「内容由AI生成」 (AI-generated content) sits alongside
        「内容为转载信息」 (reposted content), 「内容为个人观点或见解」 (personal opinion) and others; the footer's
        semi-button-primary is 「确定」 (OK).

        The entry and the dialog render asynchronously, and the mention-wrapper/semi-portal overlay left over after filling hashtags covers the entry,
        so clear the overlays before clicking. Returns False on failure.

        Args:
            declaration: declaration type text (passed in explicitly by the caller)
        """
        try:
            # Clear overlays that would cover the entry (hashtag dropdown / onboarding layer) and blur the input
            await self._clear_blocking_overlays(page)

            # Entry: open the declaration dialog (several candidate labels; native click only as a fallback)
            entry = None
            for etext in ["请选择自主声明", "请选择声明类型", "添加自主声明", "自主声明", "作品声明"]:
                cand = page.get_by_text(etext).first
                if await cand.count():
                    entry = cand
                    break
            if entry is not None:
                try:
                    await entry.scroll_into_view_if_needed(timeout=3000)
                except Exception:
                    pass
                try:
                    await entry.click(timeout=6000)
                except Exception:
                    await _native_click(page, entry)
                await page.wait_for_timeout(1200)

            # Dialog: header 「请选择声明类型（单选）」 (choose a declaration type, single choice)
            dialog = page.locator(".semi-modal-content").filter(has_text="请选择声明类型").first
            if await dialog.count() == 0:
                dialog = page.locator(".semi-modal-body").filter(has_text="请选择声明类型").first
            if await dialog.count() == 0:
                douyin_logger.warning(_msg("🧾", "Self-declaration dialog did not open; skipping the declaration and continuing to publish"))
                return False
            await dialog.first.wait_for(state="visible", timeout=6000)

            # Option: exact match on span.semi-radio-addon inside label.semi-radio
            option = dialog.locator("label.semi-radio").filter(
                has=page.locator(f'.semi-radio-addon:text-is("{declaration}")')
            ).first
            if await option.count() == 0:
                option = dialog.locator("label.semi-radio").filter(has_text=declaration).first
            if await option.count():
                try:
                    await option.click(timeout=6000)
                except Exception:
                    await _native_click(page, option)
            else:
                await dialog.get_by_text(declaration, exact=True).first.click(timeout=6000, force=True)
            await page.wait_for_timeout(400)

            # OK: the primary button in the footer
            confirm_btn = dialog.locator("button.semi-button-primary").filter(has_text="确定").first
            if await confirm_btn.count() == 0:
                confirm_btn = dialog.get_by_role("button", name="确定").first
            if await confirm_btn.count() == 0:
                confirm_btn = page.get_by_role("button", name="确定").first
            try:
                await confirm_btn.click(timeout=6000)
            except Exception:
                await _native_click(page, confirm_btn)
            try:
                await dialog.first.wait_for(state="hidden", timeout=6000)
            except Exception:
                pass
            douyin_logger.success(_msg("🧾", f"Self-declaration set to 「{declaration}」"))
            return True
        except Exception as exc:
            douyin_logger.warning(_msg("🧾", f"Failed to set the self-declaration; skipping this step and continuing to publish: {exc}"))
            return False

    async def select_bgm(self, page: Page, bgm_name: str) -> bool:
        """Pick background music for an image post. This is optional: no search results or an error just skip it without stopping the publish."""
        try:
            # Click the 「选择音乐」 (Choose music) button
            music_entry = page.locator('text="选择音乐"').nth(1)
            if not await music_entry.count():
                music_entry = page.locator('text="选择音乐"').first
            await music_entry.wait_for(state="visible", timeout=10000)
            await music_entry.click()

            # Wait for the side sheet to appear, then search
            sidesheet = page.locator(".semi-sidesheet-content").first
            await sidesheet.wait_for(state="visible", timeout=8000)
            search_input = sidesheet.locator('input.semi-input[placeholder="搜索音乐"]').first
            await search_input.wait_for(state="visible", timeout=5000)
            await search_input.fill(bgm_name)
            await search_input.press("Enter")

            # Wait for search results
            await asyncio.sleep(2)
            first_card = sidesheet.locator(".card-container-tmocjc").first
            try:
                await first_card.wait_for(state="visible", timeout=8000)
            except Exception:
                douyin_logger.warning(_msg("🎵", f"No search results for music 「{bgm_name}」; skipping"))
                await self._close_music_sidesheet(page)
                return False

            # Print the name of the music found
            try:
                song_name_el = first_card.locator(".song-name-oRge4d").first
                if await song_name_el.count():
                    song_name = await song_name_el.inner_text()
                    douyin_logger.info(_msg("🎵", f"Found: {song_name}"))
            except Exception:
                pass

            # Click 「使用」 (Use) through JS (the button is visibility:hidden, so a normal click does nothing)
            apply_btn = first_card.locator(".apply-btn-LUPP0D").first
            await apply_btn.evaluate("el => el.click()")
            douyin_logger.info(_msg("🥳", f"Background music 「{bgm_name}」 applied"))

            # Wait for the side sheet to close; close it by hand on timeout
            try:
                await sidesheet.wait_for(state="hidden", timeout=5000)
            except Exception:
                await self._close_music_sidesheet(page)

            return True
        except Exception as exc:
            douyin_logger.warning(_msg("🎵", f"Error while adding background music; skipping this step and continuing to publish: {exc}"))
            try:
                await self._close_music_sidesheet(page)
            except Exception:
                pass
            return False

    async def _close_music_sidesheet(self, page: Page) -> None:
        try:
            close_btn = page.locator(".semi-sidesheet-close").first
            if await close_btn.count() and await close_btn.is_visible():
                await close_btn.click()
                await asyncio.sleep(1)
        except Exception:
            pass


class DouYinVideo(DouYinBaseUploader):
    def __init__(
        self,
        title,
        file_path,
        tags,
        publish_date: datetime | int,
        account_file,
        thumbnail_landscape_path=None,
        productLink="",
        productTitle="",
        thumbnail_portrait_path=None,
        desc: str | None = None,
        collection_name: str | None = None,
        publish_strategy: str = DOUYIN_PUBLISH_STRATEGY_IMMEDIATE,
        debug: bool = DEBUG_MODE,
        headless: bool = LOCAL_CHROME_HEADLESS,
        declaration: str | None = None,
    ):
        super().__init__(
            publish_date=publish_date,
            account_file=account_file,
            publish_strategy=publish_strategy,
            debug=debug,
            headless=headless,
        )
        self.title = title
        self.file_path = file_path
        self.tags = tags
        self.thumbnail_landscape_path = thumbnail_landscape_path
        self.thumbnail_portrait_path = thumbnail_portrait_path
        self.productLink = productLink
        self.productTitle = productTitle
        self.desc = desc or ""
        self.collection_name = collection_name
        self.declaration = declaration.strip() if declaration and declaration.strip() else None

    async def apply_self_declaration(self, page: Page) -> None:
        if not self.declaration:
            return
        if not await self.set_self_declaration(page, self.declaration):
            raise RuntimeError(f"Failed to set the self-declaration 「{self.declaration}」; refusing to continue publishing")

    async def _clear_blocking_overlays(self, page: Page) -> None:
        """Remove overlays that intercept clicks: the hashtag/@mention dropdown left over after filling hashtags (publish-mention-wrapper)
        and its semi-portal, other non-modal semi-portals (tooltip/popover) and the shepherd onboarding layer,
        and blur the current input. The collection/declaration dropdowns create their own portal only "after they are opened", so this cleanup does not hit them.

        Root cause, see recorder.log 2026-08-10 05:31: when apply_collection clicked the collection dropdown,
        publish-mention-wrapper / semi-portal intercepted pointer events → click timed out → adding to the collection was skipped.
        """
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
        try:
            await page.evaluate(
                """() => {
                    if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
                    document.querySelectorAll('.shepherd-element,.shepherd-modal-overlay-container').forEach(e=>e.remove());
                    document.querySelectorAll('[class*="mention-wrapper"]').forEach(e=>{ const p=e.closest('.semi-portal'); (p||e).remove(); });
                    // 关闭残留的非模态 Semi 浮层 portal（保留模态框，如声明弹窗）
                    document.querySelectorAll('.semi-portal').forEach(e=>{ if(!e.querySelector('.semi-modal, .semi-modal-content')) e.remove(); });
                }"""
            )
        except Exception:
            pass
        await page.wait_for_timeout(400)

    async def apply_collection(self, page: Page) -> None:
        """Pick the target collection in the "添加合集" (Add to collection) area of the publish form (a Semi Design select, ByteDance's component library).

        The structure differs from Kuaishou (Ant Design): collection names are plain-text span.option-title-* with no label attribute,
        so match the text exactly. The trigger is located by its own class .select-collection-* (unique on the page; the first-level
        "合集/系列" (collection/series) type dropdown is unrelated and will not be picked by mistake). If no collection matches, press Escape to close the dropdown
        and publish with nothing selected (the form allows it to be empty, and the main publish flow is not blocked).
        """
        if not self.collection_name:
            return
        try:
            # Key fix: the hashtag/@mention dropdown (publish-mention-wrapper) and semi-portal left over after filling hashtags
            # cover the "添加合集" (Add to collection) dropdown, so a normal click lands on the overlay → timeout → collection skipped. Clear the overlays before clicking.
            await self._clear_blocking_overlays(page)

            trigger = page.locator('[class*="select-collection-"]').first
            if await trigger.count() == 0:
                douyin_logger.warning(_msg("😵", "\"添加合集\" (Add to collection) dropdown not found; skipping the collection"))
                return
            selection = trigger.locator(".semi-select-selection")
            try:
                await selection.click(timeout=5000)
            except Exception:
                await self._clear_blocking_overlays(page)
                await _native_click(page, selection)
            await page.wait_for_timeout(800)

            option = page.locator(".semi-select-option.collection-option").filter(
                has=page.locator(f'[class*="option-title-"]:text-is("{self.collection_name}")')
            )
            if await option.count() == 0:
                douyin_logger.warning(
                    _msg("😵", f"Collection 「{self.collection_name}」 not found in the dropdown; skipping it and leaving nothing selected")
                )
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(300)
                return

            try:
                await option.first.click(timeout=5000)
            except Exception:
                await _native_click(page, option.first)
            await page.wait_for_timeout(500)
            douyin_logger.success(_msg("🥳", f"Selected collection: {self.collection_name}"))
        except Exception as exc:
            douyin_logger.warning(_msg("😵", f"Failed to select the collection; skipping it and continuing to publish: {exc}"))
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass

    async def _submit_sms_verify_code(self, page: Page, sms_input, code: str, code_file: str) -> bool:
        douyin_logger.info(_msg("✍️", f"Got the verification code, filling it in: {code}"))
        await sms_input.click()
        await sms_input.fill(code)
        douyin_logger.info(_msg("✅", "Verification code entered"))
        await page.wait_for_timeout(500)

        verify_btn = page.locator('div.uc-ui-verify_sms-verify_button:has-text("验证")').first
        if await verify_btn.count() and await verify_btn.is_visible():
            try:
                await verify_btn.click(force=True)
                douyin_logger.success(_msg("✅", "Clicked the 「验证」 (Verify) button (force)"))
            except Exception:
                await page.eval_on_selector('div.uc-ui-verify_sms-verify_button', 'el => el.click()')
                douyin_logger.success(_msg("✅", "Clicked the 「验证」 (Verify) button (JS)"))
        else:
            verify_by_text = page.get_by_text("验证", exact=True).first
            if await verify_by_text.count():
                await verify_by_text.click(force=True)
                douyin_logger.success(_msg("✅", "Clicked the 「验证」 (Verify) button (text)"))
            else:
                douyin_logger.warning(_msg("⚠️", "Verify button not found; trying Enter"))
                await page.keyboard.press("Enter")

        if os.path.exists(code_file):
            os.remove(code_file)
            douyin_logger.info(_msg("🧹", "Verification code file removed"))

        await page.wait_for_timeout(3000)
        douyin_logger.info(_msg("🔄", "Verification code handled; continuing the publish flow"))
        return True

    async def validate_upload_args(self):
        await self.validate_base_args()
        if not self.title or not str(self.title).strip():
            raise ValueError("title is required in video mode")

        self.file_path = str(self.validate_video_file(self.file_path))
        if self.thumbnail_landscape_path:
            self.thumbnail_landscape_path = str(self.validate_image_file(self.thumbnail_landscape_path))
        if self.thumbnail_portrait_path:
            self.thumbnail_portrait_path = str(self.validate_image_file(self.thumbnail_portrait_path))

    async def handle_upload_error(self, page):
        douyin_logger.warning(_msg("😵", "Video upload failed; uploading again"))
        await page.locator('div.progress-div [class^="upload-btn-input"]').set_input_files(self.file_path)

    async def handle_auto_video_cover(self, page):
        if await page.get_by_text("请设置封面后再发布").first.is_visible():
            douyin_logger.info(_msg("🧍", "The cover has to be set before publishing"))
            recommend_cover = page.locator('[class^="recommendCover-"]').first
            if await recommend_cover.count():
                douyin_logger.info(_msg("🏃", "Choosing the first recommended cover"))
                try:
                    await recommend_cover.click()
                    await asyncio.sleep(1)
                    confirm_text = "是否确认应用此封面？"
                    if await page.get_by_text(confirm_text).first.is_visible():
                        douyin_logger.info(_msg("🪟", f"Confirmation dialog appeared: {confirm_text}"))
                        await page.get_by_role("button", name="确定").click()
                        douyin_logger.info(_msg("🥳", "Recommended cover applied"))
                        await asyncio.sleep(1)
                    douyin_logger.info(_msg("🥳", "Cover selection finished"))
                    return True
                except Exception as e:
                    douyin_logger.warning(_msg("😵", f"Could not choose the recommended cover: {e}"))
        return False

    async def set_thumbnail(self, page: Page):
        if not self.thumbnail_landscape_path and not self.thumbnail_portrait_path:
            return

        douyin_logger.info(_msg("🏃", "Setting the video cover"))
        # Remove the shepherd onboarding overlay first, or it blocks the cover click and the dialog never opens
        await page.evaluate(
            "() => document.querySelectorAll('.shepherd-element,.shepherd-modal-overlay-container').forEach(e=>e.remove())"
        )

        cover_area = page.locator('[class*="cover-"]').filter(has=page.locator("img")).first
        if not await cover_area.count():
            cover_area = page.locator('[class*="cover"]').first

        # Open the cover dialog. Douyin components often silently ignore a normal or force click (the same problem as the "完成" (Done) button),
        # so always use _native_click to send the full native event sequence; after clicking, check that the dialog appeared, and retry if not.
        cover_locator_str = 'div.dy-creator-content-modal'
        cover_locator = page.locator(cover_locator_str).first
        opened = False
        # Right after upload the page is still in transition; wait for the cover area to settle so a click does not land on nothing
        try:
            await cover_area.wait_for(state="visible", timeout=8000)
        except Exception:
            pass
        await page.wait_for_timeout(1500)
        for attempt in range(5):
            # Hover a few times until the 「编辑封面/选择封面」 (Edit cover / Choose cover) entry really shows, so we do not fall back to clicking an empty spot in the middle of the cover area
            trigger = None
            trigger_txt = "封面区域"
            for _ in range(3):
                try:
                    await cover_area.hover(force=True)
                    await page.wait_for_timeout(600)
                except Exception:
                    pass
                for txt in ["编辑封面", "选择封面", "设置封面"]:
                    t = page.get_by_text(txt, exact=True).first
                    if await t.count() and await t.is_visible():
                        trigger, trigger_txt = t, txt
                        break
                if trigger is not None:
                    break
            if trigger is None:
                trigger = cover_area
            # Use _native_click every round (a force click often silently fails on Douyin custom components and just wastes time)
            await _native_click(page, trigger)
            douyin_logger.info(_msg("🖼️", f"Clicked 「{trigger_txt}」 to open the cover dialog (attempt {attempt + 1})"))
            try:
                await page.wait_for_selector(cover_locator_str, timeout=5000)
                opened = True
                break
            except Exception:
                continue
        if not opened:
            douyin_logger.warning(_msg("⚠️", "Cover dialog will not open; skipping the custom cover and continuing to publish (the recommended cover is the fallback)"))
            return

        await page.wait_for_timeout(1500)

        # The cover dialog has two input.semi-upload-hidden-input elements (each with a -replace sibling):
        #   ① the left-hand 「生成参考图」 (AI cover reference image); its drag area is semi-upload-drag-area-custom with only a + icon;
        #   ② the frame picker's 「上传封面」 (Upload cover); its drag area has .semi-upload-drag-area-main-text 「点击上传文件或拖拽…」 (click to upload or drag…).
        # The old code took ① with .first, so the cover went into the AI reference slot → the real cover was never set and checking/AI generation kept spinning,
        # and 「完成」 (Done) never closed the dialog → publish was blocked → timeout (the real root cause, found by the user in F12).
        # Now locate ②'s upload input exactly through the main-text drag area, with .last as a fallback.
        cover_upload = cover_locator.locator(
            '.semi-upload:has(.semi-upload-drag-area-main-text) input.semi-upload-hidden-input'
        ).first
        if await cover_upload.count() == 0:
            cover_upload = cover_locator.locator("input.semi-upload-hidden-input").last

        if self.thumbnail_portrait_path:
            # The dialog opens on the "设置竖封面" (Set portrait cover) tab by default; click the tab anyway to be safe (ignored if already active)
            try:
                await cover_locator.get_by_text("设置竖封面", exact=True).first.click(timeout=3000)
                await page.wait_for_timeout(800)
            except Exception:
                pass
            await cover_upload.set_input_files(self.thumbnail_portrait_path)
            await page.wait_for_timeout(3000)
            douyin_logger.info(_msg("🖼️", "Portrait cover uploaded to the preview"))
        elif self.thumbnail_landscape_path:
            try:
                await cover_locator.get_by_text("设置横封面", exact=True).first.click(timeout=3000)
                await page.wait_for_timeout(800)
            except Exception:
                pass
            await cover_upload.set_input_files(self.thumbnail_landscape_path)
            await page.wait_for_timeout(3000)
            douyin_logger.info(_msg("🖼️", "Landscape cover uploaded to the preview"))

        # ── Wait for the "完成" (Done) button to enable: until the cover image is processed it is semi-button-disabled and clicking does nothing ──
        def _finish_btn():
            return cover_locator.get_by_role("button", name="完成", exact=True).first

        for _ in range(30):  # wait up to ~15s for the image to process and the button to enable
            try:
                b = _finish_btn()
                if await b.count():
                    cls = await b.get_attribute("class") or ""
                    if "semi-button-disabled" not in cls:
                        break
            except Exception:
                pass
            await page.wait_for_timeout(500)

        # ── Click "完成" (Done) and check that the dialog really detaches ──
        # On Douyin custom components a normal click may neither raise nor work, so after each click check whether the dialog is gone:
        # only then is it a success; otherwise escalate to _native_click, handle a possible second confirmation, and finally fall back to Esc.
        closed = False
        for attempt in range(4):
            btn = _finish_btn()
            if not await btn.count():
                btn = cover_locator.locator("button.semi-button").filter(has_text="完成").first
            if await btn.count() and await btn.is_visible():
                try:
                    await btn.click(timeout=4000)
                except Exception:
                    pass
                await page.wait_for_timeout(1500)
                if await cover_locator.count() == 0:
                    closed = True
                    break
                # A normal click did not close it → send the full native event sequence
                await _native_click(page, btn)
                await page.wait_for_timeout(1500)
                if await cover_locator.count() == 0:
                    closed = True
                    break

            # After "完成" (Done), Douyin may ask for a second confirmation (for example "确定完成？" when no landscape cover is set) → click a confirm-type button
            for cname in ["确定", "确认", "仍然完成", "仍要完成", "继续"]:
                confirm = page.locator(".semi-modal-content").get_by_role("button", name=cname, exact=True).first
                if await confirm.count() and await confirm.is_visible():
                    await _native_click(page, confirm)
                    await page.wait_for_timeout(1500)
                    break
            if await cover_locator.count() == 0:
                closed = True
                break

            # Still open: press Esc as a fallback and check once more
            douyin_logger.debug(_msg("🖼️", f"Cover dialog still open after 「完成」 (Done); retrying (attempt {attempt + 1})"))
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(1000)
            if await cover_locator.count() == 0:
                closed = True
                break

        if closed:
            douyin_logger.info(_msg("🥳", "Video cover set, dialog closed"))
        else:
            douyin_logger.warning(_msg("⚠️", "Cover dialog did not close; it may block the self-declaration/publish"))


    async def upload(self, playwright: Playwright) -> None:
        douyin_logger.info(_msg("🧍", "Checking the cookie, video file, cover and publish time first"))
        await self.validate_upload_args()
        douyin_logger.info(_msg("🥳", "Pre-upload checks passed"))

        browser = await playwright.chromium.launch(headless=self.headless, channel="chromium", args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(
            storage_state=f"{self.account_file}",
            permissions=["geolocation"],
        )
        context = await set_init_script(context)

        page = await context.new_page()
        await page.goto("https://creator.douyin.com/creator-micro/content/upload", wait_until="domcontentloaded", timeout=90000)
        douyin_logger.info(_msg("🏃", f"Starting video upload: {self.title}.mp4"))
        douyin_logger.info(_msg("🧭", "Opening the upload page"))
        await page.wait_for_url("https://creator.douyin.com/creator-micro/content/upload", timeout=90000)

        # ── After the page opens, an identity check (SMS code) may pop up, or we may be sent to the login page ──
        await page.wait_for_timeout(2000)

        # Make sure we are on the upload page (not the login page) before looking for the upload input
        # Use a more precise selector so the login form's input is not matched
        upload_input = page.locator("input.upload-btn-input, div[class^='container'] input[accept]").first
        if not await upload_input.count():
            # Fallback: exclude the login page's input
            upload_input = page.locator("div[class^='container'] input[type='file'], div[class^='container'] input.upload-input").first
        if not await upload_input.count():
            # Last fallback
            upload_input = page.locator("div[class^='container'] input").first
        await upload_input.wait_for(state="attached", timeout=60000)
        await upload_input.set_input_files(self.file_path)

        while True:
            try:
                await page.wait_for_url(
                    "https://creator.douyin.com/creator-micro/content/publish?enter_from=publish_page",
                    timeout=3000,
                )
                douyin_logger.info(_msg("🥳", "On the version_1 publish page"))
                break
            except Exception:
                try:
                    await page.wait_for_url(
                        "https://creator.douyin.com/creator-micro/content/post/video?enter_from=publish_page",
                        timeout=3000,
                    )
                    douyin_logger.info(_msg("🥳", "On the version_2 publish page"))
                    break
                except Exception:
                    douyin_logger.debug(_msg("🧍", "Not on the video publish page yet; waiting a bit longer"))
                    await asyncio.sleep(0.5)

        await asyncio.sleep(1)
        douyin_logger.info(_msg("✍️", "Filling in the title, description and hashtags"))
        await self.fill_title_and_description(page, self.title, self.desc, self.tags)
        douyin_logger.info(_msg("🏷️", f"Added {len(self.tags)} hashtags in total"))

        while True:
            try:
                number = await page.locator('[class^="long-card"] div:has-text("重新上传")').count()
                if number > 0:
                    douyin_logger.success(_msg("🥳", "Video upload finished"))
                    break
                douyin_logger.info(_msg("🏃", "Uploading video..."))
                await asyncio.sleep(2)
                if await page.locator('div.progress-div > div:has-text("上传失败")').count():
                    douyin_logger.error(_msg("😵", "Upload failure detected; about to retry"))
                    await self.handle_upload_error(page)
            except Exception:
                douyin_logger.debug(_msg("🧍", "Still waiting for the video upload to finish"))
                await asyncio.sleep(2)

        if self.productLink and self.productTitle:
            douyin_logger.info(_msg("🛒", "Setting the product link"))
            await self.set_product_link(page, self.productLink, self.productTitle)
            douyin_logger.info(_msg("🥳", "Product link set"))

        # Self-declaration: this project's videos contain AI-generated content (TTS voice-over / AI subtitles / AI intro clip),
        # so, to follow platform rules, honestly choose 「内容由AI生成」 (AI-generated content) (listed alongside repost and others; single choice, no sub-options, no source needed).
        if not self.declaration:
            self.declaration = "内容由AI生成"
        await self.apply_self_declaration(page)

        # Add to the collection first: the cover dialog is not open yet, so the dy-creator-content-portal cover overlay cannot block the collection dropdown
        # (tested: in headless mode the cover dialog often stays on "检测中" (checking) and does not close, covering the "添加合集" (Add to collection) dropdown)
        await self.apply_collection(page)

        # Then set the cover (last, closing the dialog, so no leftover overlay blocks the publish button)
        await self.set_thumbnail(page)

        third_part_element = '[class^="info"] > [class^="first-part"] div div.semi-switch'
        if await page.locator(third_part_element).count():
            if "semi-switch-checked" not in await page.eval_on_selector(third_part_element, "div => div.className"):
                await page.locator(third_part_element).locator("input.semi-switch-native-control").click()

        if self.publish_strategy == DOUYIN_PUBLISH_STRATEGY_SCHEDULED and self.publish_date != 0:
            await self.set_schedule_time_douyin(page, self.publish_date)

        sms_prompt_logged = False
        while True:
            try:
                # Remove onboarding/hashtag dropdown overlays that would block the publish button click
                await page.evaluate(
                    "() => { document.querySelectorAll('.shepherd-element, .shepherd-modal-overlay-container, [class*=\"mention-wrapper\"]').forEach(e => e.remove()); }"
                )
                # Detect and handle the SMS verification code dialog
                sms_input = page.locator('input[placeholder*="验证码"], input[type="tel"], input[placeholder*="短信"], input[placeholder*="手机号"]').first
                if await sms_input.count() and await sms_input.is_visible():
                    douyin_logger.warning(_msg("📱", "SMS verification code dialog detected"))
                    # Click the 「获取验证码」 (Get code) button (first time only)
                    get_code_btn = page.get_by_text("获取验证码").first
                    if await get_code_btn.count() and await get_code_btn.is_visible():
                        await get_code_btn.click()
                        douyin_logger.info(_msg("📤", "Clicked 「获取验证码」 (Get code); check your phone for the SMS"))
                    code_file = os.path.join(BASE_DIR, "verify_code.txt")
                    code = await _read_verify_code(code_file)
                    if code:
                        sms_prompt_logged = False
                        await self._submit_sms_verify_code(page, sms_input, code, code_file)
                    elif not sms_prompt_logged:
                        douyin_logger.warning(_msg("⏳", f"Waiting for the verification code; type it in the interactive terminal or write it to the file: {code_file}"))
                        sms_prompt_logged = True

                # ── Normal publish flow ──
                publish_button = page.get_by_role("button", name="发布", exact=True)
                if await publish_button.count():
                    await publish_button.click(force=True)
                await page.wait_for_url(
                    "https://creator.douyin.com/creator-micro/content/manage**",
                    timeout=3000,
                )
                douyin_logger.success(_msg("🥳", "Video published successfully, all done"))
                break
            except Exception:
                await self.handle_auto_video_cover(page)
                douyin_logger.info(_msg("🏃", "Publishing video..."))
                if self.debug:
                    await page.screenshot(full_page=True)
                await asyncio.sleep(0.5)

        await context.storage_state(path=self.account_file)
        douyin_logger.success(_msg("🥳", "Cookie updated"))
        await asyncio.sleep(2)
        await context.close()
        await browser.close()

    async def douyin_upload_video(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)

    async def main(self):
        await self.douyin_upload_video()


class DouYinNote(DouYinBaseUploader):
    def __init__(
        self,
        image_paths,
        note,
        tags,
        publish_date: datetime | int,
        account_file,
        title: str | None = None,
        publish_strategy: str = DOUYIN_PUBLISH_STRATEGY_IMMEDIATE,
        debug: bool = DEBUG_MODE,
        headless: bool = LOCAL_CHROME_HEADLESS,
        bgm: str = "",
    ):
        super().__init__(
            publish_date=publish_date,
            account_file=account_file,
            publish_strategy=publish_strategy,
            debug=debug,
            headless=headless,
        )
        self.image_paths = image_paths
        self.note = note or ""
        self.title = title or (self.note[:30] if self.note else "")
        self.tags = tags or []
        self.bgm = bgm or ""

    async def validate_upload_args(self):
        await self.validate_base_args()
        if not self.title or not str(self.title).strip():
            raise ValueError("title is required in image post mode")

        if len(self.title) > 20:
            raise ValueError(f"Title must not exceed 20 characters, current: {len(self.title)} characters")

        if not self.image_paths:
            raise ValueError("Images are required in image post mode")

        if isinstance(self.image_paths, (str, Path)):
            self.image_paths = [self.image_paths]

        if len(self.image_paths) > 35:
            raise ValueError("Image post mode supports at most 35 images")

        note_len = len(self.note) if self.note else 0
        if note_len > 1000:
            raise ValueError(f"Text must not exceed 1000 characters, current: {note_len} characters")

        normalized_image_paths = []
        for image_path in self.image_paths:
            normalized_image_paths.append(str(self.validate_image_file(image_path)))
        self.image_paths = normalized_image_paths

    async def upload_note_content(self, page: Page) -> None:
        douyin_logger.info(_msg("🏃", f"Starting image post upload, {len(self.image_paths)} images"))
        douyin_logger.info(_msg("🔀", "Switching to image post publishing"))
        await page.get_by_text("发布图文", exact=True).click()
        await page.wait_for_timeout(1000)

        douyin_logger.info(_msg("📤", "Uploading images..."))
        await page.locator("div[class^='container'] input[accept*='image']").set_input_files(self.image_paths)

        while True:
            try:
                await page.wait_for_url(
                    "**/creator-micro/content/post/image?**",
                    timeout=3000,
                )
                douyin_logger.info(_msg("🥳", "On the image post publish page"))
                break
            except Exception:
                douyin_logger.debug(_msg("🧍", "Still waiting for the images to finish uploading"))
                await asyncio.sleep(0.5)

        await asyncio.sleep(1)
        douyin_logger.info(_msg("✍️", "Filling in the title, description and hashtags"))
        await self.fill_title_and_description(page, self.title, self.note, self.tags)
        title_len = len(self.title) if self.title else 0
        tags_text = " ".join(f"#{t}" for t in self.tags) if self.tags else ""
        desc_and_tags_len = len(self.note or "") + (len(tags_text) + 2 if self.tags else 0)
        douyin_logger.info(_msg("📝", f"Title length: {title_len}, description + hashtags length: {desc_and_tags_len}"))
        douyin_logger.info(_msg("🏷️", f"Added {len(self.tags)} hashtags in total"))

        if self.bgm:
            await self.select_bgm(page, self.bgm)

        if self.publish_strategy == DOUYIN_PUBLISH_STRATEGY_SCHEDULED and self.publish_date != 0:
            await self.set_schedule_time_douyin(page, self.publish_date)

        while True:
            try:
                publish_button = page.get_by_role("button", name="发布", exact=True)
                if await publish_button.count():
                    await publish_button.click()
                await page.wait_for_url(
                    "**/creator-micro/content/manage?enter_from=publish**",
                    timeout=3000,
                )
                douyin_logger.success(_msg("🥳", "Image post published successfully, all done"))
                break
            except Exception:
                douyin_logger.info(_msg("🏃", "Publishing image post..."))
                await asyncio.sleep(0.5)

    async def upload(self, playwright: Playwright) -> None:
        douyin_logger.info(_msg("🧍", "Checking the cookie, images and publish time first"))
        await self.validate_upload_args()
        douyin_logger.info(_msg("🥳", "Image post pre-upload checks passed"))

        browser = await playwright.chromium.launch(headless=self.headless, channel="chromium", args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(
            storage_state=f"{self.account_file}",
            permissions=["geolocation"],
        )
        context = await set_init_script(context)

        upload_success = False
        try:
            page = await context.new_page()
            await page.goto("https://creator.douyin.com/creator-micro/content/upload", wait_until="domcontentloaded", timeout=90000)
            douyin_logger.info(_msg("🧭", "Opening the image post publish page"))
            await page.wait_for_url("https://creator.douyin.com/creator-micro/content/upload", timeout=90000)

            await self.upload_note_content(page)
            upload_success = True
        finally:
            if upload_success:
                await context.storage_state(path=self.account_file)
                douyin_logger.success(_msg("🥳", "Cookie updated"))
                await asyncio.sleep(2)
            await context.close()
            await browser.close()

    async def douyin_upload_note(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)
