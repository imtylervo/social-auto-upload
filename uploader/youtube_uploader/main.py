# -*- coding: utf-8 -*-
"""YouTube uploader (browser automation via YouTube Studio).

Unlike the other platforms here, YouTube also offers an official Data API. We deliberately
use browser automation instead, because videos uploaded through an *unaudited* API project
are force-locked to private and cannot be made public without passing Google's compliance
audit (which is impractical for personal/single-channel use). Browser automation has no such
restriction and can publish public videos right away, and it matches the cookie-based pattern
used by every other uploader in this project.

Login is interactive (Google account, no QR code): the browser opens, the user signs in, and
the storage_state is saved. Reuse it afterwards for fully unattended uploads.
"""
import asyncio
from pathlib import Path

from patchright.async_api import Page, Playwright, async_playwright

from conf import DEBUG_MODE
from uploader.base_video import BaseVideoUploader
from utils.base_social_media import set_init_script
from utils.log import youtube_logger

try:
    # A direct connection to youtube.com from mainland China times out, and the Chromium started by patchright ignores the system proxy.
    # Set YT_PROXY = "http://127.0.0.1:7890" (local proxy port) in conf.py; without it no proxy is used.
    from conf import YT_PROXY
except Exception:
    YT_PROXY = None

STUDIO_URL = "https://studio.youtube.com"
UPLOAD_URL = "https://www.youtube.com/upload"
VISIBILITY = {"public": "PUBLIC", "unlisted": "UNLISTED", "private": "PRIVATE"}


def _msg(emoji: str, text: str) -> str:
    return f"{emoji} {text}"


def _build_login_result(success, status, message, account_file, current_url=""):
    return {
        "success": success,
        "status": status,
        "message": message,
        "account_file": str(account_file),
        "current_url": current_url,
    }


async def cookie_auth(account_file) -> bool:
    """Is the login state still valid: open Studio with the cookies; valid if not sent to the Google login page and the channel page loads."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, channel="chrome")
        try:
            context = await browser.new_context(storage_state=account_file)
            context = await set_init_script(context)
            page = await context.new_page()
            await page.goto(STUDIO_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            url = page.url
            if "accounts.google.com" in url or "/signin" in url.lower():
                return False
            return "/channel/" in url
        except Exception:
            return False
        finally:
            await browser.close()


async def youtube_cookie_gen(account_file, headless: bool = False):
    """Interactive login: open a browser for the user to sign in to Google/YouTube, then save storage_state once the channel page loads."""
    async with async_playwright() as playwright:
        # Login must be visible so the user can enter the password / two-step verification
        browser = await playwright.chromium.launch(headless=False, channel="chrome")
        context = await browser.new_context()
        context = await set_init_script(context)
        page = await context.new_page()
        await page.goto(STUDIO_URL, wait_until="domcontentloaded")
        youtube_logger.info(_msg("🔐", "Sign in to your Google / YouTube account in the browser that opened; the login is saved automatically"))
        ok = False
        for _ in range(600):  # wait at most 10 minutes
            if "/channel/" in page.url:
                await page.wait_for_timeout(2000)  # let the cookies settle
                ok = True
                break
            await asyncio.sleep(1)
        if ok:
            await context.storage_state(path=account_file)
            youtube_logger.success(_msg("✅", f"YouTube login state saved: {account_file}"))
        else:
            youtube_logger.error(_msg("😵", "Timed out waiting for login; login state not saved"))
        await browser.close()
        return _build_login_result(ok, "logged_in" if ok else "timeout",
                                   "登录成功" if ok else "登录超时", account_file, page.url)


async def youtube_setup(account_file, handle: bool = False, return_detail: bool = False, headless: bool = False):
    """Check the login state; if it is invalid and handle=True, start the interactive login."""
    if not Path(account_file).exists() or not await cookie_auth(account_file):
        if not handle:
            result = _build_login_result(False, "cookie_invalid", "登录态不存在或已失效", account_file)
            return result if return_detail else False
        youtube_logger.info(_msg("🥹", "YouTube login state missing or expired, opening a browser to log in"))
        result = await youtube_cookie_gen(account_file, headless=headless)
        return result if return_detail else result["success"]
    result = _build_login_result(True, "cookie_valid", "登录态有效", account_file)
    return result if return_detail else True


async def _dismiss_autocomplete(page: Page):
    """Close the # hashtag / @ mention autocomplete dropdown (it covers the later Next / Publish buttons).

    First blur the field; if the dropdown is still visible, press Escape once. Escape is only pressed when a dropdown
    is detected, so it cannot close the whole upload dialog when there is none."""
    try:
        await page.evaluate("() => { const a = document.activeElement; if (a && a.blur) a.blur(); }")
    except Exception:
        pass
    try:
        dropdown = page.locator("tp-yt-iron-dropdown:visible")
        if await dropdown.count() > 0:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(200)
    except Exception:
        pass


async def _fill_editable(page: Page, selector: str, text: str):
    """Fill a contenteditable rich-text box in YouTube Studio (title/description): clear it first, then enter the text.

    Use fill() to insert everything at once instead of type() character by character: a # in the title/description
    (e.g. #Shorts) triggers YouTube's hashtag autocomplete dropdown. Typing character by character keeps the dropdown
    following the cursor, covering the input and the later Next / Publish buttons, and the upload gets stuck. fill() writes it in one go and does not trigger autocomplete per character."""
    box = page.locator(selector).first
    await box.wait_for(state="visible", timeout=30000)
    await box.click()
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Delete")
    try:
        await box.fill(text)            # insert at once, so # hashtag autocomplete is not triggered per character
    except Exception:
        await box.type(text, delay=6)   # fall back to per-character typing when a contenteditable does not support fill
    await page.wait_for_timeout(400)
    await _dismiss_autocomplete(page)   # finally close any autocomplete dropdown that popped up


async def _click_if_present(page: Page, selector: str, timeout: int = 4000) -> bool:
    try:
        el = page.locator(selector).first
        await el.wait_for(state="visible", timeout=timeout)
        await el.click()
        return True
    except Exception:
        return False


async def _wait_upload_complete(page: Page, max_polls: int = 360) -> bool:
    """Wait for the web upload to go from X% to 100% before publishing. A browser upload only finishes while the window stays open;
    clicking Publish halfway and closing the browser cuts the upload off mid-way (e.g. at 76%).
    The upload counts as done when “处理/检查/上传完成” (processing / checks / upload complete) shows, or “正在上传” (uploading) is gone. Limit: max_polls*5s = 30 min."""
    last = ""
    for _ in range(max_polls):
        txt = ""
        for sel in (".progress-label", "span.progress-label", "ytcp-video-upload-progress"):
            loc = page.locator(sel).first
            try:
                if await loc.count():
                    txt = (await loc.inner_text()).strip()
                    if txt:
                        break
            except Exception:
                pass
        if txt:
            if any(k in txt for k in ("处理", "检查", "上传完成", "已上传", "Processing", "complete", "Checks", "Finished")):
                youtube_logger.info(_msg("✅", f"Upload complete: {txt[:40]}"))
                return True
            if txt != last:
                youtube_logger.info(_msg("⏳", f"Uploading: {txt[:40]}"))
                last = txt
        await page.wait_for_timeout(5000)
    youtube_logger.warning(_msg("⚠️", "Timed out waiting for upload (30 min), trying to publish anyway"))
    return False


class YouTubeVideo(BaseVideoUploader):
    def __init__(self, title, file_path, tags, account_file, *,
                 description="", thumbnail_path=None, playlist=None,
                 visibility="public", debug=DEBUG_MODE, headless=False):
        self.title = title
        self.file_path = str(file_path)
        self.tags = tags or []
        self.account_file = str(account_file)
        self.description = description or ""
        self.thumbnail_path = str(thumbnail_path) if thumbnail_path else None
        self.playlist = playlist
        self.visibility = visibility if visibility in VISIBILITY else "public"
        self.debug = debug
        self.headless = headless

    async def upload(self, playwright: Playwright) -> None:
        browser = await playwright.chromium.launch(
            headless=self.headless, channel="chrome",
            proxy={"server": YT_PROXY} if YT_PROXY else None,
        )
        context = await browser.new_context(storage_state=self.account_file)
        context = await set_init_script(context)
        page = await context.new_page()
        page.set_default_timeout(60000)

        youtube_logger.info(_msg("🎬", f"Start uploading: {Path(self.file_path).name}"))
        await page.goto(UPLOAD_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        if "accounts.google.com" in page.url or "signin" in page.url.lower():
            await browser.close()
            raise RuntimeError("YouTube login state expired, run login again")

        # 1) Select the video file
        file_input = page.locator('input[type="file"]').first
        await file_input.wait_for(state="attached", timeout=60000)
        await file_input.set_input_files(self.file_path)

        # 2) Wait for the details dialog
        await page.locator("#title-textarea").wait_for(state="visible", timeout=120000)

        # 3) Title
        youtube_logger.info(_msg("✍️", "Filling in title"))
        await _fill_editable(page, "#title-textarea #textbox", self.title[:100])

        # 4) Description
        if self.description.strip():
            youtube_logger.info(_msg("✍️", "Filling in description"))
            await _fill_editable(page, "#description-textarea #textbox", self.description)

        # 5) Thumbnail (only allowed after processing reaches a certain point; failure is not fatal)
        if self.thumbnail_path and Path(self.thumbnail_path).exists():
            try:
                thumb_input = page.locator(
                    "#file-loader input[type='file'], ytcp-thumbnail-uploader input[type='file']"
                ).first
                await thumb_input.wait_for(state="attached", timeout=20000)
                await thumb_input.set_input_files(self.thumbnail_path)
                await page.wait_for_timeout(2000)
                youtube_logger.info(_msg("🖼️", "Thumbnail uploaded"))
            except Exception as exc:
                youtube_logger.warning(_msg("⚠️", f"Thumbnail upload skipped (publishing not affected): {exc}"))

        # 6) Add to a playlist (for a series). The dialog must be closed, or it blocks the next steps.
        if self.playlist:
            try:
                await _click_if_present(
                    page, "#basics ytcp-text-dropdown-trigger, ytcp-video-metadata-playlists ytcp-dropdown-trigger", 8000)
                await page.wait_for_timeout(1200)
                existing = page.locator(
                    f"tp-yt-paper-checkbox:has-text('{self.playlist}'), "
                    f"ytcp-checkbox-group:has-text('{self.playlist}')").first
                if await existing.count():
                    await existing.click()
                else:
                    if await _click_if_present(page, "ytcp-button:has-text('New playlist'), ytcp-button:has-text('创建播放列表')", 4000):
                        await page.wait_for_timeout(800)
                        await _click_if_present(page, "tp-yt-paper-item:has-text('New playlist'), tp-yt-paper-item:has-text('新建播放列表')", 3000)
                        title_box = page.locator("ytcp-playlist-metadata-editor #textbox, #create-playlist-form #textbox").first
                        if await title_box.count():
                            await title_box.click()
                            await title_box.type(self.playlist, delay=6)
                            await _click_if_present(page, "ytcp-button#create-button, tp-yt-paper-dialog ytcp-button:has-text('Create'), tp-yt-paper-dialog ytcp-button:has-text('创建')", 4000)
            except Exception as exc:
                youtube_logger.warning(_msg("⚠️", f"Playlist step skipped (publishing not affected): {exc}"))
            finally:
                await _click_if_present(page, "ytcp-playlist-dialog #save-button, ytcp-button:has-text('Done'), ytcp-button:has-text('完成')", 3000)
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(600)

        # 7) Audience: not made for kids (required)
        if not await _click_if_present(page, "tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']", 10000):
            await _click_if_present(page, "tp-yt-paper-radio-button:has-text('not made for kids'), tp-yt-paper-radio-button:has-text('不是面向儿童')", 6000)

        # 8) Tags (under "Show more")
        if self.tags:
            try:
                await _click_if_present(page, "#toggle-button", 6000)
                await page.wait_for_timeout(800)
                tag_input = page.locator("#tags-container #text-input, ytcp-form-input-container#tags-container input").first
                await tag_input.click()
                await tag_input.type(",".join(self.tags)[:500] + ",", delay=4)
            except Exception as exc:
                youtube_logger.warning(_msg("⚠️", f"Tags skipped (publishing not affected): {exc}"))

        # 9) Click Next repeatedly until the Visibility step
        for _ in range(5):
            vis = page.locator("tp-yt-paper-radio-button[name='PUBLIC']")
            if await vis.count() and await vis.first.is_visible():
                break
            if not await _click_if_present(page, "#next-button", 6000):
                await page.wait_for_timeout(1200)
            await page.wait_for_timeout(1000)

        # 10) Visibility
        youtube_logger.info(_msg("🌐", f"Set visibility = {self.visibility}"))
        await _click_if_present(page, f"tp-yt-paper-radio-button[name='{VISIBILITY[self.visibility]}']", 10000)

        # 10.5) Important: wait until the upload has really finished before publishing. A browser upload needs the window open;
        #       clicking Publish halfway and closing the browser cuts the upload off mid-way (e.g. at 76%).
        youtube_logger.info(_msg("📤", "Waiting for the upload to finish (publish only after it completes)…"))
        await _wait_upload_complete(page)

        # 11) Publish
        await page.wait_for_timeout(1200)
        if not await _click_if_present(page, "#done-button", 15000):
            youtube_logger.warning(_msg("🤔", "Publish button not found; the upload may not be far enough to publish yet. Publish manually in the window"))
        else:
            await page.wait_for_timeout(4000)
            video_url = ""
            try:
                link = page.locator("a[href*='youtu.be'], a[href*='watch?v=']").first
                if await link.count():
                    video_url = await link.get_attribute("href") or ""
            except Exception:
                pass
            await _click_if_present(page, "ytcp-button:has-text('Close'), ytcp-button:has-text('关闭'), #close-button", 8000)
            youtube_logger.success(_msg("🥳", f"Published ({self.visibility}){(' ' + video_url) if video_url else ''}"))

        # Refresh cookies
        try:
            await context.storage_state(path=self.account_file)
        except Exception:
            pass
        await page.wait_for_timeout(2000)
        await browser.close()

    async def main(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)
