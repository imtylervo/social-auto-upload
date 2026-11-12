# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import inspect
import os
from datetime import datetime
from pathlib import Path

from patchright.async_api import Page
from patchright.async_api import Playwright
from patchright.async_api import async_playwright

from conf import DEBUG_MODE, LOCAL_CHROME_HEADLESS, LOCAL_CHROME_PATH
from uploader.base_video import BaseVideoUploader
from utils.base_social_media import set_init_script
from utils.login_qrcode import build_login_qrcode_path
from utils.login_qrcode import decode_qrcode_from_path
from utils.login_qrcode import print_terminal_qrcode
from utils.login_qrcode import remove_qrcode_file
from utils.login_qrcode import save_data_url_image
from utils.log import xiaohongshu_logger

XHS_DEFAULT_CREATOR_BASE_URL = "https://creator.xiaohongshu.com"
XHS_CREATOR_BASE_URL_ENV = "SAU_XHS_CREATOR_BASE_URL"
XHS_PUBLISH_SUCCESS_URL_PATTERN = "**/publish/success?**"
XHS_LOGIN_BOX_SELECTOR = "div[class*='login-box']"
XHS_LOGIN_SWITCH_SELECTOR = "img.css-wemwzq"
XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE = "immediate"
XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED = "scheduled"


def _build_xhs_creator_url(path: str) -> str:
    base_url = os.getenv(
        XHS_CREATOR_BASE_URL_ENV,
        XHS_DEFAULT_CREATOR_BASE_URL,
    ).strip().rstrip("/")
    if not base_url:
        base_url = XHS_DEFAULT_CREATOR_BASE_URL
    return f"{base_url}/{path.lstrip('/')}"


def _msg(emoji: str, text: str) -> str:
    return f"{emoji} {text}"


async def _js_click_by_text(page: Page, text: str) -> bool:
    """Use JS to find the innermost element whose text matches exactly and click it and its ancestors (works around span pointer-events:none and blocking overlays).

    On Xiaohongshu many clickable items keep their text in <span class="d-text">, where pointer-events is often disabled,
    so a normal Playwright click times out. A native click that bubbles up to trigger the Vue events is more reliable.
    """
    return await page.evaluate(
        """(t) => {
            const nodes = [...document.querySelectorAll('*')].filter(
                e => e.children.length === 0 && (e.textContent || '').trim() === t
            );
            if (!nodes.length) return false;
            let el = nodes[nodes.length - 1];
            for (let i = 0; i < 4 && el; i++) { try { el.click(); } catch (e) {} el = el.parentElement; }
            return true;
        }""",
        text,
    )


async def _emit_qrcode_callback(qrcode_callback, payload: dict):
    if not qrcode_callback:
        return

    callback_result = qrcode_callback(payload)
    if inspect.isawaitable(callback_result):
        await callback_result


def _build_login_result(
    success: bool,
    status: str,
    message: str,
    account_file: str,
    qrcode: dict | None = None,
    current_url: str = "",
) -> dict:
    return {
        "success": success,
        "status": status,
        "message": message,
        "account_file": str(account_file),
        "qrcode": qrcode,
        "current_url": current_url,
    }


async def _open_xhs_qrcode_panel(page: Page) -> None:
    login_box = page.locator(XHS_LOGIN_BOX_SELECTOR).first
    await login_box.wait_for(state="visible", timeout=30000)

    scan_text = login_box.locator("div:has-text('扫一扫')").first
    if await scan_text.count():
        return

    switch_img = login_box.locator(XHS_LOGIN_SWITCH_SELECTOR).first
    await switch_img.wait_for(state="visible", timeout=10000)
    await switch_img.click()
    await login_box.locator("div:has-text('扫一扫')").first.wait_for(state="visible", timeout=10000)


async def _find_xhs_qrcode_locator(page: Page):
    await _open_xhs_qrcode_panel(page)

    qrcode_img = page.locator('.login-box-container').get_by_text("APP扫一扫登录").filter(visible=True).locator("xpath=..//following-sibling::div//img").nth(0)

    if await qrcode_img.count():
        return qrcode_img

    raise RuntimeError("Xiaohongshu QR code image not found in the scan-to-log-in area")


async def _extract_xhs_qrcode_src(page: Page) -> str:
    qrcode_img = await _find_xhs_qrcode_locator(page)
    await qrcode_img.wait_for(state="visible", timeout=30000)
    qrcode_src = await qrcode_img.get_attribute("src")
    if not qrcode_src:
        raise RuntimeError("Could not get the Xiaohongshu login QR code URL")
    return qrcode_src


async def _save_xhs_qrcode(
    page: Page,
    account_file: str,
    previous_qrcode_path: Path | None = None,
    qrcode_callback=None,
) -> dict:
    qrcode_src = await _extract_xhs_qrcode_src(page)
    qrcode_path = build_login_qrcode_path(account_file, suffix="xhs_login_qrcode")
    qrcode_img = await _find_xhs_qrcode_locator(page)

    if qrcode_src.startswith("data:image/"):
        save_data_url_image(qrcode_src, qrcode_path)
    else:
        qrcode_path.parent.mkdir(parents=True, exist_ok=True)
        await qrcode_img.screenshot(path=str(qrcode_path))

    if previous_qrcode_path and previous_qrcode_path != qrcode_path:
        if remove_qrcode_file(previous_qrcode_path):
            xiaohongshu_logger.info(_msg("🧹", f"Temporary QR code file removed: {previous_qrcode_path}"))

    xiaohongshu_logger.info(_msg("🖼️", f"QR code is ready, saved to: {qrcode_path}"))
    qrcode_content = decode_qrcode_from_path(qrcode_path)
    if qrcode_content:
        print_terminal_qrcode(qrcode_content, qrcode_path, "小红书APP")
    else:
        xiaohongshu_logger.warning(_msg("😵", f"The terminal cannot show the whole QR code; open {qrcode_path} and scan it"))

    qrcode_info = {
        "image_path": str(qrcode_path),
        "image_data_url": qrcode_src,
    }
    await _emit_qrcode_callback(qrcode_callback, qrcode_info)
    return qrcode_info


async def _is_xhs_login_completed(page: Page) -> bool:
    if page.url.startswith(_build_xhs_creator_url("/login")):
        return False

    login_box = page.locator(XHS_LOGIN_BOX_SELECTOR).first
    if not await login_box.count():
        return True

    try:
        return not await login_box.is_visible()
    except Exception:
        return True


async def cookie_auth(account_file):
    if not os.path.exists(account_file):
        return False

    async with async_playwright() as playwright:
        if LOCAL_CHROME_PATH:
            browser = await playwright.chromium.launch(headless=True, executable_path=LOCAL_CHROME_PATH)
        else:
            browser = await playwright.chromium.launch(headless=True, channel="chromium")
        try:
            context = await browser.new_context(storage_state=account_file)
            context = await set_init_script(context)
            page = await context.new_page()
            await page.goto(
                _build_xhs_creator_url(
                    "/publish/publish?from=homepage&target=video"
                )
            )
            await page.wait_for_timeout(3000)

            if page.url.startswith(_build_xhs_creator_url("/login")):
                xiaohongshu_logger.info(_msg("🥹", "Cookie is invalid; you need to log in again"))
                return False

            login_box = page.locator(XHS_LOGIN_BOX_SELECTOR).first
            if await login_box.count():
                try:
                    if await login_box.is_visible():
                        xiaohongshu_logger.info(_msg("🥹", "The page is still on the login QR code page; treating the cookie as invalid"))
                        return False
                except Exception:
                    return False

            xiaohongshu_logger.success(_msg("🥳", "Cookie is valid"))
            return True
        except Exception as exc:
            xiaohongshu_logger.warning(_msg("😵", f"Error while checking the cookie, treating it as invalid: {exc}"))
            return False
        finally:
            await browser.close()


async def xiaohongshu_setup(
    account_file,
    handle=False,
    return_detail=False,
    qrcode_callback=None,
    headless: bool = LOCAL_CHROME_HEADLESS,
):
    if not os.path.exists(account_file) or not await cookie_auth(account_file):
        if not handle:
            result = _build_login_result(False, "cookie_invalid", "cookie文件不存在或已失效", account_file)
            return result if return_detail else False
        xiaohongshu_logger.info(_msg("🥹", "Cookie is invalid; opening a browser to log in again"))
        result = await xiaohongshu_cookie_gen(
            account_file,
            qrcode_callback=qrcode_callback,
            headless=headless,
        )
        return result if return_detail else result["success"]

    result = _build_login_result(True, "cookie_valid", "cookie有效", account_file)
    return result if return_detail else True


async def xiaohongshu_cookie_gen(
    account_file,
    qrcode_callback=None,
    poll_interval: int = 3,
    max_checks: int = 100,
    headless: bool = LOCAL_CHROME_HEADLESS,
):
    if headless:
        xiaohongshu_logger.info(_msg("🖼️", "Xiaohongshu login runs headless; the QR code will be printed in the terminal and saved as a local image"))

    account_path = Path(account_file)
    account_path.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless, channel="chromium")
        context = await browser.new_context()
        context = await set_init_script(context)
        qrcode_path = None
        qrcode_info = None
        result = _build_login_result(False, "failed", "小红书登录失败", account_file)
        try:
            page = await context.new_page()
            await page.goto(_build_xhs_creator_url("/login"))
            qrcode_info = await _save_xhs_qrcode(page, account_file, qrcode_callback=qrcode_callback)
            qrcode_path = Path(qrcode_info["image_path"])
            xiaohongshu_logger.info(_msg("🧍", "Scan the QR code; waiting for login to finish"))

            for _ in range(max_checks):
                if await _is_xhs_login_completed(page):
                    await asyncio.sleep(2)
                    await context.storage_state(path=account_file)
                    if await cookie_auth(account_file):
                        xiaohongshu_logger.success(_msg("🥳", "Xiaohongshu QR-code login succeeded, all done"))
                        result = _build_login_result(True, "success", "小红书扫码登录成功", account_file, qrcode_info, page.url)
                    else:
                        result = _build_login_result(
                            False,
                            "cookie_invalid",
                            "小红书扫码流程结束，但 cookie 校验失败",
                            account_file,
                            qrcode_info,
                            page.url,
                        )
                    return result

                await asyncio.sleep(poll_interval)

            result = _build_login_result(
                False,
                "timeout",
                "等待小红书扫码登录超时",
                account_file,
                qrcode_info,
                page.url,
            )
        except Exception as exc:
            result = _build_login_result(False, "failed", str(exc), account_file, current_url=page.url if "page" in locals() else "")
        finally:
            if remove_qrcode_file(qrcode_path):
                xiaohongshu_logger.info(_msg("🧹", f"Temporary QR code file removed: {qrcode_path}"))
            if not result["success"]:
                xiaohongshu_logger.error(_msg("😢", f"Login failed: {result['message']}"))
            await context.close()
            await browser.close()
        return result


class XiaoHongShuBaseUploader(BaseVideoUploader):
    def __init__(
        self,
        publish_date: datetime | int,
        account_file,
        publish_strategy: str = XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE,
        debug: bool = DEBUG_MODE,
        headless: bool = LOCAL_CHROME_HEADLESS,
    ):
        self.publish_date = publish_date
        self.account_file = str(account_file)
        self.publish_strategy = publish_strategy
        self.debug = debug
        self.date_format = "%Y年%m月%d日 %H:%M"
        self.local_executable_path = LOCAL_CHROME_PATH
        self.headless = headless

    async def validate_base_args(self):
        if not os.path.exists(self.account_file):
            raise RuntimeError(f"Cookie file does not exist; log in to Xiaohongshu first: {self.account_file}")
        if not await cookie_auth(self.account_file):
            raise RuntimeError(f"Cookie file is no longer valid; log in to Xiaohongshu first: {self.account_file}")

        if self.publish_strategy not in {
            XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE,
            XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED,
        }:
            raise ValueError(f"Unsupported publish strategy: {self.publish_strategy}")

        if self.publish_strategy == XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED:
            self.publish_date = self.validate_publish_date(self.publish_date)
        else:
            self.publish_date = 0

    async def set_schedule_time_xiaohongshu(self, page: Page, publish_date: datetime):
        xiaohongshu_logger.info(_msg("🕒", f"Setting the scheduled publishing time: {publish_date.strftime(self.date_format)}"))
        await page.locator('.custom-switch-card').filter(has_text="定时发布").locator('.d-switch').click()
        await asyncio.sleep(1)
        publish_date_hour = publish_date.strftime("%Y-%m-%d %H:%M")
        time_input = page.locator('.d-datepicker-input-filter input.d-text')
        await time_input.fill(str(publish_date_hour))
        await asyncio.sleep(1)

    async def set_location(self, page: Page, location: str = "青岛市"):
        if not location:
            return True

        xiaohongshu_logger.info(_msg("📍", f"Setting the location: {location}"))
        loc_ele = await page.wait_for_selector('div.d-text.d-select-placeholder.d-text-ellipsis.d-text-nowrap')
        await loc_ele.click()
        await page.wait_for_timeout(1000)
        await page.keyboard.type(location)
        dropdown_selector = 'div.d-popover.d-popover-default.d-dropdown.--size-min-width-large'
        await page.wait_for_timeout(2000)
        try:
            await page.wait_for_selector(dropdown_selector, timeout=3000)
        except Exception:
            xiaohongshu_logger.warning(_msg("😵", "The location dropdown did not appear as expected; falling back to the old lookup"))
        await page.wait_for_timeout(1000)
        flexible_xpath = (
            f'//div[contains(@class, "d-popover") and contains(@class, "d-dropdown")]'
            f'//div[contains(@class, "d-options-wrapper")]'
            f'//div[contains(@class, "d-grid") and contains(@class, "d-options")]'
            f'//div[contains(@class, "name") and text()="{location}"]'
        )
        await page.wait_for_timeout(3000)
        try:
            location_option = await page.wait_for_selector(
                flexible_xpath,
                timeout=3000
            )

            if not location_option:
                location_option = await page.wait_for_selector(
                    f'//div[contains(@class, "d-popover") and contains(@class, "d-dropdown")]'
                    f'//div[contains(@class, "d-options-wrapper")]'
                    f'//div[contains(@class, "d-grid") and contains(@class, "d-options")]'
                    f'/div[1]//div[contains(@class, "name") and text()="{location}"]',
                    timeout=2000
                )

            await location_option.scroll_into_view_if_needed()
            await location_option.click()
            xiaohongshu_logger.success(_msg("🥳", f"Location set to {location}"))
            return True
        except Exception as e:
            xiaohongshu_logger.error(_msg("😢", f"Failed to set the location: {e}"))
            try:
                all_options = await page.query_selector_all(
                    '//div[contains(@class, "d-popover") and contains(@class, "d-dropdown")]'
                    '//div[contains(@class, "d-options-wrapper")]'
                    '//div[contains(@class, "d-grid") and contains(@class, "d-options")]'
                    '/div'
                )
                xiaohongshu_logger.debug(_msg("🧍", f"Found {len(all_options)} options in the location dropdown"))
                for i, option in enumerate(all_options[:3]):
                    option_text = await option.inner_text()
                    xiaohongshu_logger.debug(_msg("🧾", f"Location option {i + 1}: {option_text.strip()[:50]}"))
            except Exception as inner_e:
                xiaohongshu_logger.debug(_msg("😵", f"Failed to read the location options: {inner_e}"))
            return False

    async def fill_title(self, page: Page) -> None:
        title_container = page.locator('input[placeholder*="填写标题"]')
        await title_container.fill(self.title[:20])

    async def fill_desc(self, page: Page) -> None:
        if not getattr(self, "desc", ""):
            return

        desc = page.locator('p[data-placeholder*="输入正文描述"]')
        await desc.click()
        await page.keyboard.press("Backspace")
        await page.keyboard.press("Control+KeyA")
        await page.keyboard.press("Delete")
        await page.keyboard.type(self.desc)
        await page.keyboard.press("Enter")

    async def fill_tags(self, page: Page) -> None:
        if not getattr(self, "tags", None):
            return

        # Xiaohongshu allows at most 10 tags; more than that loops forever and stalls the publish
        max_tags = 10
        if len(self.tags) > max_tags:
            xiaohongshu_logger.warning(
                _msg("🏷️", f"{len(self.tags)} tags exceeds the Xiaohongshu limit of {max_tags}; using only the first {max_tags}: {self.tags[:max_tags]}")
            )
            self.tags = self.tags[:max_tags]

        if not getattr(self, "desc", ""):
            desc = page.locator('p[data-placeholder*="输入正文描述"]')
            await desc.click()

        for tag in self.tags:  # go through all tags
            # The hashtag suggestion dropdown depends on Xiaohongshu's live suggestion API, so with network jitter or no match it may never appear.
            # Tags are optional: if no suggestions appear, skip that tag and go on, so the whole publish does not fail because of it.
            try:
                await page.keyboard.type("#" + tag, delay=30)
                await page.locator('#creator-editor-topic-container').wait_for(
                    state="visible",
                    timeout=6000
                )
                first_item = page.locator('#creator-editor-topic-container .item').first
                await first_item.wait_for(state="visible", timeout=4000)
                await first_item.click()
            except Exception as exc:
                xiaohongshu_logger.warning(
                    _msg("🏷️", f"No suggestions appeared for hashtag 『{tag}』; skipping this tag and continuing to publish: {exc}")
                )
                # Delete the typed "#tag" text that did not become a hashtag, so it does not stay in the text
                for _ in range(len("#" + tag)):
                    await page.keyboard.press("Backspace")
                continue

    async def fill_meta(self, page: Page) -> None:
        await self.fill_title(page)
        await self.fill_desc(page)
        await self.fill_tags(page)

    async def check_original_declaration(self, page: Page) -> None:
        """Set the 「来源转载」 (reposted from a source) declaration and fill in the source.

        Flow (matches the codegen recording):
          click 「添加内容类型声明」 (Add content type declaration) → click the div containing 「来源转载」 (reposted from a source)
          → fill the placeholder 「请输入媒体名称」 (enter media name) → click the 「确认」 (Confirm) button.
        Error handling: if any step fails, log a warning, skip it and keep publishing without stopping.
        """
        source = getattr(self, "repost_source", "") or ""
        try:
            # 1. Click 「添加内容类型声明」 (Add content type declaration)
            trigger = page.get_by_text("添加内容类型声明", exact=False).first
            try:
                await trigger.scroll_into_view_if_needed(timeout=5000)
            except Exception:
                pass
            await trigger.click(force=True)
            await page.wait_for_timeout(1500)

            # 2. Choose the 「来源转载」 (reposted from a source) option
            import re as _re
            repost_option = page.locator("#publish-container div").filter(
                has_text=_re.compile(r"^来源转载$")
            ).last
            if await repost_option.count():
                await repost_option.click(force=True)
            else:
                await _js_click_by_text(page, "来源转载")
            await page.wait_for_timeout(1500)

            # 3. Fill in the media name
            source_input = page.get_by_placeholder("请输入媒体名称").first
            await source_input.wait_for(state="visible", timeout=8000)
            await source_input.click()
            await source_input.fill(source)
            await page.wait_for_timeout(500)

            # 4. Click the 「确认」 (Confirm) button
            confirm = page.get_by_role("button", name="确认").first
            try:
                await confirm.wait_for(state="visible", timeout=5000)
                await confirm.click()
            except Exception:
                await _js_click_by_text(page, "确认")

            await page.wait_for_timeout(1000)
            xiaohongshu_logger.success(_msg("🧾", f"Repost declared (source: {source})"))
        except Exception as exc:
            xiaohongshu_logger.warning(_msg("⚠️", f"Failed to set the repost declaration; skipping and continuing to publish: {exc}"))
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass


class XiaoHongShuVideo(XiaoHongShuBaseUploader):
    def __init__(
        self,
        title,
        file_path,
        tags,
        publish_date: datetime | int,
        account_file,
        thumbnail_path=None,
        desc: str | None = None,
        publish_strategy: str = XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE,
        debug: bool = DEBUG_MODE,
        headless: bool = LOCAL_CHROME_HEADLESS,
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
        self.tags = tags or []
        self.thumbnail_path = thumbnail_path
        self.desc = desc or ""

    async def validate_upload_args(self):
        await self.validate_base_args()
        if not self.title or not str(self.title).strip():
            raise ValueError("title is required in video mode")

        self.file_path = str(self.validate_video_file(self.file_path))
        if self.thumbnail_path:
            self.thumbnail_path = str(self.validate_image_file(self.thumbnail_path))

    async def handle_upload_error(self, page: Page):
        xiaohongshu_logger.warning(_msg("😵", "Video upload failed; uploading again"))
        await page.locator('div.progress-div [class^="upload-btn-input"]').set_input_files(self.file_path)

    async def set_thumbnail(self, page: Page, thumbnail_path: str):
        if not thumbnail_path:
            return

        xiaohongshu_logger.info(_msg("🖼️", "Setting the cover"))

        # Setting the cover is optional: on failure, log a warning, skip it and keep publishing (the first video frame is the fallback).
        try:
            # The cover area is embedded in the publish page; clicking div.upload-cover opens the cover dialog (d-modal).
            cover_section = page.locator("text=设置封面").first
            try:
                await cover_section.scroll_into_view_if_needed(timeout=5000)
            except Exception:
                pass
            await page.wait_for_timeout(2000)

            # 1. Click div.upload-cover to open the cover dialog
            upload_cover = page.locator("div.upload-cover").first
            if not await upload_cover.count():
                upload_cover = page.locator("div.cover-plugin-preview div.default.pointer").first
            await upload_cover.click(force=True)
            await page.wait_for_timeout(3000)

            # 2. Switch to the 「上传封面」 (Upload cover) tab (the default is 「截取封面」 (Capture cover))
            upload_tab = page.get_by_text("上传封面", exact=True).first
            await upload_tab.wait_for(state="visible", timeout=10000)
            await upload_tab.click()
            await page.wait_for_timeout(2000)

            # 3. Find the image file input (parent class: upload-wrapper) and upload
            file_input = page.locator('div.upload-wrapper input[type="file"][accept*="image"]').first
            if not await file_input.count():
                file_input = page.locator('input[type="file"][accept*="image"]').last
            await file_input.set_input_files(thumbnail_path)
            await page.wait_for_timeout(4000)  # wait for the image to load and the crop view to render

            # 4. Click the 「确定」 (OK) button
            modal_footer = page.locator("div.d-modal-footer")
            confirm = modal_footer.get_by_text("确定", exact=True).first
            if not await confirm.count():
                confirm = page.get_by_role("button", name="确定").first
            await confirm.wait_for(state="visible", timeout=10000)
            await confirm.click()

            # 5. Wait for the dialog to close
            modal = page.locator("div.d-modal")
            try:
                await modal.first.wait_for(state="hidden", timeout=15000)
            except Exception:
                pass
            xiaohongshu_logger.success(_msg("🥳", "Cover set"))
        except Exception as exc:
            xiaohongshu_logger.warning(_msg("🖼️", f"Failed to set the cover; skipping this step and continuing to publish (using the first video frame): {exc}"))
            try:
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(500)
            except Exception:
                pass

    async def upload_video_content(self, page: Page) -> None:
        xiaohongshu_logger.info(_msg("🏃", f"Starting video upload: {self.title}.mp4"))
        xiaohongshu_logger.info(_msg("🧭", "Opening the video publish page"))
        publish_url = _build_xhs_creator_url(
            "/publish/publish?from=homepage&target=video"
        )
        await page.goto(publish_url)
        await page.wait_for_url(publish_url)
        await page.locator("div[class^='upload-content'] input[class='upload-input']").set_input_files(self.file_path)

        while True:
            try:
                upload_input = await page.wait_for_selector('input.upload-input', timeout=3000)
                preview_new = await upload_input.query_selector(
                    'xpath=following-sibling::div[contains(@class, "preview-new")]')
                if preview_new:
                    # Read the text of the whole preview area for a more robust check of the upload state
                    all_text = await preview_new.inner_text()
                    upload_success = any(keyword in all_text for keyword in ['上传成功', '分辨率', '重新上传', '编辑封面', '已上传', '已选择', '100%'])
                    
                    if not upload_success:
                        # Check for a specific status code or percentage
                        stage_elements = await preview_new.query_selector_all('div.stage')
                        for stage in stage_elements:
                            text_content = await page.evaluate('(element) => element.textContent', stage)
                            if '上传成功' in text_content or '分辨率' in text_content:
                                upload_success = True
                                break
                    
                    if upload_success:
                        xiaohongshu_logger.success(_msg("🥳", "Video upload finished"))
                        break
                    
                    if self.debug:
                        normalized_text = all_text.strip().replace("\n", " ")
                        xiaohongshu_logger.debug(_msg("🧍", f"Preview area content: {normalized_text}"))
                    xiaohongshu_logger.debug(_msg("🧍", "No upload success marker yet; waiting a bit longer"))
                else:
                    # Check whether the title input has appeared; if so, the page is already in edit mode
                    title_container = page.locator('input[placeholder*="填写标题"]')
                    if await title_container.count() > 0 and await title_container.is_visible():
                        xiaohongshu_logger.success(_msg("🥳", "No preview area, but the title box is there; continuing"))
                        break
                    xiaohongshu_logger.debug(_msg("🧍", "Preview area not available yet; waiting a bit longer"))
            except Exception as e:
                xiaohongshu_logger.debug(_msg("😵", f"Upload status has not settled yet; still watching: {e}"))
            await asyncio.sleep(2)

        xiaohongshu_logger.info(_msg("✍️", "Filling in the title, description and hashtags"))
        await self.fill_meta(page)

        await self.set_thumbnail(page, self.thumbnail_path)

        # await self.set_location(page, "青岛市")

        await self.check_original_declaration(page)

        if self.publish_strategy == XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED and self.publish_date != 0:
            await self.set_schedule_time_xiaohongshu(page, self.publish_date)

        while True:
            try:
                if self.publish_strategy == XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED:
                    await page.locator('button:has-text("定时发布")').click()
                else:
                    await page.locator('button:has-text("发布")').click()
                await page.wait_for_url(
                    XHS_PUBLISH_SUCCESS_URL_PATTERN,
                    timeout=3000
                )
                xiaohongshu_logger.success(_msg("🥳", "Video published successfully, all done"))
                break
            except Exception:
                xiaohongshu_logger.info(_msg("🏃", "Publishing video..."))
                if self.debug:
                    await page.screenshot(full_page=True)
                await asyncio.sleep(0.5)

    async def upload(self, playwright: Playwright) -> None:
        xiaohongshu_logger.info(_msg("🧍", "Checking the cookie, video file, cover and publish time first"))
        await self.validate_upload_args()
        xiaohongshu_logger.info(_msg("🥳", "Pre-upload checks passed"))
        browser = await playwright.chromium.launch(headless=self.headless, channel="chromium")
        context = await browser.new_context(
            permissions=["geolocation"],
            storage_state=self.account_file,
        )
        context = await set_init_script(context)

        try:
            page = await context.new_page()
            await self.upload_video_content(page)
            await context.storage_state(path=self.account_file)
            xiaohongshu_logger.success(_msg("🥳", "Cookie updated"))
        finally:
            await context.close()
            await browser.close()

    async def xiaohongshu_upload_video(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)

    async def main(self):
        await self.xiaohongshu_upload_video()


class XiaoHongShuNote(XiaoHongShuBaseUploader):
    def __init__(
        self,
        image_paths,
        note,
        tags,
        publish_date: datetime | int,
        account_file,
        title: str | None = None,
        desc: str | None = None,
        publish_strategy: str = XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE,
        debug: bool = DEBUG_MODE,
        headless: bool = LOCAL_CHROME_HEADLESS,
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
        self.tags = tags or []
        self.desc = desc if desc is not None else self.note
        self.title = title or ((self.desc or self.note)[:20] if (self.desc or self.note) else "")

    async def validate_upload_args(self):
        await self.validate_base_args()
        if not self.image_paths:
            raise ValueError("Images are required in image post mode")
        if not self.title or not str(self.title).strip():
            raise ValueError("title is required in image post mode")

        if isinstance(self.image_paths, (str, Path)):
            self.image_paths = [self.image_paths]

        normalized_image_paths = []
        for image_path in self.image_paths:
            normalized_image_paths.append(str(self.validate_image_file(image_path)))
        self.image_paths = normalized_image_paths

    async def upload_note_content(self, page: Page) -> None:
        xiaohongshu_logger.info(_msg("🏃", f"Starting image post upload, {len(self.image_paths)} images"))
        xiaohongshu_logger.info(_msg("🧭", "Opening the image post publish page"))
        publish_url = _build_xhs_creator_url(
            "/publish/publish?from=homepage&target=image"
        )
        await page.goto(publish_url)
        await page.wait_for_url(publish_url)

        upload_input = page.locator('input[type="file"][accept*="image"]').first
        if not await upload_input.count():
            upload_input = page.locator("div[class^='upload-content'] input[class='upload-input']").first

        await upload_input.wait_for(state="attached", timeout=30000)
        xiaohongshu_logger.info(_msg("📤", "Uploading images..."))
        await upload_input.set_input_files(self.image_paths)

        while True:
            try:
                title_container = page.locator('input[placeholder*="填写标题"]').first
                await title_container.wait_for(state="visible", timeout=3000)
                xiaohongshu_logger.success(_msg("🥳", "Image post media uploaded; ready to fill in the content"))
                break
            except Exception:
                xiaohongshu_logger.debug(_msg("🧍", "Image post media still uploading; waiting a bit longer"))
                await asyncio.sleep(1)

        xiaohongshu_logger.info(_msg("✍️", "Filling in the title, description and hashtags"))
        await self.fill_meta(page)

        await self.check_original_declaration(page)

        if self.publish_strategy == XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED and self.publish_date != 0:
            await self.set_schedule_time_xiaohongshu(page, self.publish_date)

        while True:
            try:
                if self.publish_strategy == XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED:
                    await page.locator('button:has-text("定时发布")').click()
                else:
                    await page.locator('button:has-text("发布")').click()
                await page.wait_for_url(
                    XHS_PUBLISH_SUCCESS_URL_PATTERN,
                    timeout=3000
                )
                xiaohongshu_logger.success(_msg("🥳", "Image post published successfully, all done"))
                break
            except Exception:
                xiaohongshu_logger.info(_msg("🏃", "Publishing image post..."))
                if self.debug:
                    await page.screenshot(full_page=True)
                await asyncio.sleep(0.5)

    async def upload(self, playwright: Playwright) -> None:
        xiaohongshu_logger.info(_msg("🧍", "Checking the cookie, images and publish time first"))
        await self.validate_upload_args()
        xiaohongshu_logger.info(_msg("🥳", "Image post pre-upload checks passed"))
        browser = await playwright.chromium.launch(headless=self.headless, channel="chromium")
        context = await browser.new_context(
            permissions=["geolocation"],
            storage_state=self.account_file,
        )
        context = await set_init_script(context)

        try:
            page = await context.new_page()
            await self.upload_note_content(page)
            await context.storage_state(path=self.account_file)
            xiaohongshu_logger.success(_msg("🥳", "Cookie updated"))
        finally:
            await context.close()
            await browser.close()

    async def xiaohongshu_upload_note(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)

    async def main(self):
        await self.xiaohongshu_upload_note()
