"""Publish Facebook Page content through Meta Business Suite."""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from patchright.async_api import Page, Playwright, async_playwright, expect, TimeoutError as BrowserTimeoutError

from uploader.base_video import BaseVideoUploader


META_BUSINESS_URL = "https://business.facebook.com/latest/composer/"
META_PLATFORMS = {"facebook-page"}
# Without the environment variable or --proxy, connect directly through the system.
FACEBOOK_PAGE_PROXY = os.environ.get("SAU_FACEBOOK_PAGE_PROXY")


def meta_account_file(platform: str, account_name: str) -> Path:
    if platform not in META_PLATFORMS:
        raise ValueError(f"Unsupported Meta Business platform: {platform}")
    return Path("cookies") / f"{platform}_{account_name}.json"


def _proxy_options(proxy: str | None) -> dict[str, str] | None:
    address = (FACEBOOK_PAGE_PROXY if proxy is None else proxy) or ""
    address = address.strip()
    return {"server": address} if address else None


async def _open_business_page(
    playwright: Playwright,
    account_file: Path,
    *,
    proxy: str | None,
    headless: bool,
):
    browser = await playwright.chromium.launch(
        channel="chrome", headless=headless, proxy=_proxy_options(proxy)
    )
    try:
        context = await browser.new_context(storage_state=str(account_file))
        page = await context.new_page()
        page.set_default_timeout(30_000)
        await page.goto(META_BUSINESS_URL, wait_until="domcontentloaded", timeout=120_000)
        await page.locator("body").wait_for(state="visible", timeout=30_000)
        return browser, context, page
    except Exception:
        await browser.close()
        raise


async def dismiss_guidance_cards(page: Page) -> None:
    """Close info cards that carry an explicit GeoGuidanceCard marker; leave unknown dialogs alone."""
    # In the Chinese, English and Japanese cards the close button has no aria-label while Learn more has one; do not rely on the text Close/关闭/閉じる.
    close_buttons = page.locator('[data-surface$="lib:GeoGuidanceCard"] [role="button"]:not([aria-label]):visible')
    # data-surface can appear on both the wrapper node and the logging node; select the descendant button directly and let CSS deduplicate.
    for close in await close_buttons.all():
        await close.click()
        await expect(close).to_be_hidden()


async def _is_business_logged_out(page: Page) -> bool:
    url = page.url.lower()
    if "/login" in url or "checkpoint" in url or "two_step_verification" in url:
        return True
    if await page.locator('input[name="email"]').count() and await page.locator('input[name="email"]').first.is_visible():
        return True
    # Navigation hrefs and page surfaces do not depend on the display language; a blank page is no evidence of being logged in.
    navigation = page.locator('a[href*="/latest/home"]')
    return not await navigation.filter(visible=True).count()



async def meta_cookie_auth(account_file: str | Path, *, proxy: str | None = None) -> bool:
    account_file = Path(account_file)
    if not account_file.is_file():
        return False
    async with async_playwright() as playwright:
        browser, context, page = await _open_business_page(
            playwright, account_file, proxy=proxy, headless=True
        )
        try:
            return not await _is_business_logged_out(page)
        finally:
            await browser.close()


async def meta_setup(
    account_file: str | Path,
    *,
    handle: bool = False,
    proxy: str | None = None,
    headless: bool = False,
    return_detail: bool = False,
):
    account_file = Path(account_file)
    account_file.parent.mkdir(parents=True, exist_ok=True)
    if await meta_cookie_auth(account_file, proxy=proxy):
        result = {"success": True, "status": "cookie_valid", "account_file": str(account_file)}
        return result if return_detail else True
    if not handle:
        result = {"success": False, "status": "cookie_invalid", "account_file": str(account_file)}
        return result if return_detail else False

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            channel="chrome", headless=headless, proxy=_proxy_options(proxy)
        )
        try:
            # An existing Facebook login state can seed the Business Suite cookies, so you do not have to log in again.
            source = account_file
            context = await browser.new_context(storage_state=str(source) if source.is_file() else None)
            page = await context.new_page()
            page.set_default_timeout(30_000)
            await page.goto(META_BUSINESS_URL, wait_until="domcontentloaded", timeout=120_000)
            deadline = asyncio.get_running_loop().time() + 600
            while asyncio.get_running_loop().time() < deadline:
                if not await _is_business_logged_out(page):
                    await context.storage_state(path=str(account_file))
                    result = {
                        "success": True,
                        "status": "logged_in",
                        "account_file": str(account_file),
                        "current_url": page.url,
                    }
                    return result if return_detail else True
                await page.wait_for_timeout(1000)
            result = {"success": False, "status": "timeout", "account_file": str(account_file)}
            return result if return_detail else False
        finally:
            await browser.close()


class MetaBusinessUploader(BaseVideoUploader):
    """Publisher for Facebook Page videos and image posts in Business Suite."""

    def __init__(
        self,
        platform: str,
        account_file: str | Path,
        *,
        title: str,
        description: str = "",
        tags: list[str] | None = None,
        video_file: str | Path | None = None,
        image_files: list[str | Path] | None = None,
        schedule: datetime | int = 0,
        page_name: str | None = None,
        proxy: str | None = None,
        headless: bool = False,
        result_file: str | Path | None = None,
    ):
        if platform not in META_PLATFORMS:
            raise ValueError(f"Unsupported Meta Business platform: {platform}")
        if not title.strip():
            raise ValueError("Title must not be empty")
        if bool(video_file) == bool(image_files):
            raise ValueError("Pass either a video or image files, not both and not neither")
        self.platform = platform
        self.account_file = Path(account_file)
        self.title = title.strip()
        self.description = description.strip()
        self.tags = [tag.strip().lstrip("#") for tag in (tags or []) if tag.strip().lstrip("#")]
        self.video_file = Path(video_file) if video_file else None
        self.image_files = [Path(item) for item in (image_files or [])]
        self.schedule = self.validate_publish_date(schedule)
        self.page_name = page_name.strip() if page_name else None
        self.proxy = proxy
        self.headless = headless
        self.result_file = Path(result_file) if result_file else Path('.local/meta-results') / f'{uuid4().hex}.json'
        self.result = {"platform": platform, "title": self.title, "status": "not_submitted"}

    def _caption(self) -> str:
        parts = [self.title, self.description] if self.description else [self.title]
        if self.tags:
            parts.append(" ".join(f"#{tag}" for tag in self.tags))
        return "\n\n".join(parts)

    async def _select_publish_location(self, page: Page) -> None:
        # The accessible name of the post-to selector sets it apart from the text and CTA comboboxes, without relying on page-wide order.
        # The post-to selector carries the Facebook brand logo; the CTA dropdown and the text do not.
        # The real Chinese and English pages both keep this brand alt, which avoids relying on translations of "发布位置/Post to".
        combo = page.locator('[data-surface$="bizweb_create_post:left_panel"] [role="combobox"][aria-haspopup="listbox"]').filter(has=page.locator('img[alt="Facebook"]'))
        await combo.wait_for(state="visible")
        if self.page_name and self.page_name not in await combo.inner_text():
            await combo.click()
            option = page.get_by_role("option", name=self.page_name, exact=True)
            if not await option.count():
                raise RuntimeError(f"Business Suite did not find the requested post-to Page: {self.page_name}")
            await option.click()
        if self.page_name:
            await expect(combo).to_contain_text(self.page_name)
        else:
            self.page_name = (await combo.inner_text()).replace('\u200b', '').strip()
        assets = parse_qs(urlparse(page.url).query).get('asset_id', [])
        if len(assets) != 1 or not assets[0].isdigit():
            raise RuntimeError("Could not verify the current Page asset_id; not submitted")
        self.result.update(page_id=assets[0], page_name=self.page_name, expected_text=self.title)

    async def _upload_files(self, page: Page) -> None:
        # The page may keep hidden responsive layouts; button semantics plus visible pin down the real upload entry.
        # In the empty media area the order is local photo/video upload, then optional AI generation; testing found 1 and 2 entries in Chinese and English respectively.
        # Accept only these two structures of the empty area; the edit/remove actions that appear after upload must not get mixed in. Do not match by translation or icon path.
        media = page.locator('[data-surface$="lib:bizweb_create_post:media"]')
        await expect(media.locator('img')).to_have_count(0)
        entries = media.get_by_role('button')
        if await entries.count() not in (1, 2):
            raise RuntimeError('Unrecognised structure of the empty media area; nothing uploaded')
        trigger = entries.nth(0)
        files = [str(self.video_file)] if self.video_file else [str(path) for path in self.image_files]
        async with page.expect_file_chooser() as chooser_info:
            await trigger.click()
        await (await chooser_info.value).set_files(files)
        # In the new Business Suite a video goes into the "创建 Reels" (Create reel) wizard, which renders no video tag;
        # images stay in the original composer. Both cases must wait until the file name or the wizard title appears.
        if self.video_file:
            await page.get_by_text(self.video_file.name, exact=True).wait_for(state="visible", timeout=180_000)
            # The new Reel wizard has its own surface; do not rely on the Create reel/创建 Reels title.
            await page.locator('[data-surface$="lib:bizweb_create_reel"]').wait_for()
            await dismiss_guidance_cards(page)
            await page.get_by_text('100%', exact=True).wait_for(state='visible', timeout=180000)
        else:
            # After upload the media area shows a server-side preview with pixel dimensions; the Chinese "移除照片" (Remove photo) or the text box does not mean the upload finished.
            await expect(media.locator('img')).to_have_count(len(files), timeout=180000)
            await expect(media.get_by_text(re.compile(r"^\d+ x \d+$")).filter(visible=True)).to_have_count(len(files), timeout=180000)

    async def _fill_caption(self, page: Page) -> None:
        # The Reel title is the only plain text input in left_panel; the keyword input has a separate combobox role.
        reels_title = page.locator('[data-surface$="bizweb_create_reel:left_panel"] input[type="text"]:not([role]):visible')
        separate_title = self.video_file and await reels_title.count() and await reels_title.is_visible()
        if separate_title:
            await reels_title.fill(self.title)
        # Testing found a hidden textbox and a visible combobox with the same name; match only the wizard's visible text field so the old layout is not filled by mistake.
        # The visible contenteditable is the text field; the hidden textbox belongs to the old layout, and the role changes between image post and Reel.
        editor = page.locator('[contenteditable="true"]:visible')
        await expect(editor).to_have_count(1)
        await editor.wait_for(state="visible", timeout=30_000)
        caption = self.description if separate_title else self._caption()
        if self.tags and separate_title:
            caption = f"{caption}\n\n{' '.join(f'#{tag}' for tag in self.tags)}" if caption else " ".join(f"#{tag}" for tag in self.tags)
        if not caption and not self.video_file:
            caption = self._caption()
        await editor.fill(caption)
        if (await editor.inner_text()).strip() != caption:
            raise RuntimeError("Business Suite text field did not read back the expected content")

    async def _advance_reels(self, page: Page) -> None:
        if not self.video_file:
            return
        root = page.locator('[data-surface$="lib:bizweb_create_reel"]')
        # The wizard's three steps have aria-labelledby and the current step has aria-current; the thumbnail switcher has neither.
        steps = root.locator('[role="button"][aria-labelledby]:not([aria-haspopup])')
        await expect(steps).to_have_count(3)
        # Both Next clicks come from the footer, not to be confused with the thumbnails' previous/next; the one with an aria-label is the feedback entry.
        # Tested: in the create, edit and share steps the footer always has two buttons, Back/Cancel plus the main action.
        for index in (0, 1):
            await expect(steps.nth(index)).to_have_attribute('aria-current', 'step')
            actions = page.locator('[data-surface$="bizweb_create_reel:footer"] [role="button"]:not([aria-label])')
            await expect(actions).to_have_count(2)
            await expect(actions.nth(1)).to_be_enabled(timeout=180000)
            await actions.nth(1).click()
            await expect(steps.nth(index + 1)).to_have_attribute('aria-current', 'step')
        # The Story switch and the current Page's Facebook logo belong to the same single-switch group; the other switches have no brand image.
        story = page.locator('[data-surface$="bizweb_create_reel:left_panel"] input[role="switch"]').locator(
            'xpath=self::input[ancestor::div[.//img[@alt="Facebook"] and count(.//input[@role="switch"])=1]]')
        await expect(story).to_have_count(1)
        if await story.is_checked():
            await story.click()
            # Once is the platform's real option value and turns off Story sharing for this post only; Always would change the default for later posts.
            dialog = page.get_by_role('dialog').filter(has=page.locator('input[type="radio"][value="Once"]'))
            await expect(dialog).to_have_count(1)
            await dialog.locator('input[value="Once"]').check()
            actions = dialog.get_by_role('button')
            # Tested: the confirmation box has three items, Close, Cancel and Confirm; use that order only after strictly checking the count.
            await expect(actions).to_have_count(3)
            await actions.nth(2).click()
            await expect(dialog).to_have_count(0)
            await expect(story).not_to_be_checked()

    async def _fill_schedule(self, page: Page) -> None:
        if not self.schedule:
            return
        # This form reads times in the browser's local time zone; it has been verified for real only with Asia/Shanghai.
        zone = await page.evaluate("Intl.DateTimeFormat().resolvedOptions().timeZone")
        if zone != "Asia/Shanghai" or self.schedule.tzinfo is not None:
            raise ValueError("Meta scheduling currently requires an Asia/Shanghai browser and a Beijing-time input without a time zone")
        if self.video_file:
            region = page.locator('[data-surface$="bizweb_create_reel:left_panel"]')
            # The share step has three publish modes, Now, Schedule and Draft; their aria-pressed marks the mode and is not a submit.
            modes = region.locator('[role="button"][aria-pressed]').locator('xpath=self::*[not(ancestor::*[@role="grid"])]')
            await expect(modes).to_have_count(3)
            await modes.nth(1).click()
            await expect(modes.nth(1)).to_have_attribute('aria-pressed', 'true')
        else:
            region = page.locator('[data-surface$="lib:bizweb_create_post:publishing_options"]')
            await region.locator('input[role="switch"]').check()
        # The date is the only plain input with a placeholder in the schedule area; hour and minute are told apart by their value ranges.
        date_input = region.locator('input[placeholder]:not([role])')
        await expect(date_input).to_have_count(1)
        await date_input.click()
        grid = region.locator('[role="grid"][aria-labelledby]')
        await expect(grid).to_have_count(1)
        # Tested: the calendar's aria-labelledby holds month and year; the js_* prefix changes per session, so parse only the date suffix.
        month_id = await grid.get_attribute('aria-labelledby')
        match = re.search(r'-(\d{1,2})-(\d{4})$', month_id or '')
        if not match:
            raise RuntimeError('Could not read the month/year of the calendar; not submitted')
        month, year = map(int, match.groups())
        month_delta = (self.schedule.year - year) * 12 + self.schedule.month - month
        if abs(month_delta) > 12:
            raise ValueError('The scheduled date is outside the verified calendar range')
        # The two calendar buttons outside the grid are previous month and next month; day buttons are gridcells, which excludes them.
        calendar = grid.locator('xpath=ancestor::div[.//*[@role="button"][@aria-busy]][1]')
        navigation = calendar.locator('[role="button"][aria-busy]')
        await expect(navigation).to_have_count(2)
        for _ in range(abs(month_delta)):
            await navigation.nth(1 if month_delta > 0 else 0).click()
        await expect(grid).to_have_attribute('aria-labelledby', re.compile(fr'-{self.schedule.month}-{self.schedule.year}$'))
        # With the calendar's year and month checked, pick the day by its number, avoiding translated weekday/month names in aria-label.
        day = grid.get_by_role('button').filter(has_text=re.compile(fr'^{self.schedule.day}$'))
        await expect(day).to_have_count(1)
        if await day.get_attribute('aria-disabled') == 'true':
            raise ValueError('The platform calendar does not allow the chosen date; not submitted')
        await day.click()
        hour = region.locator('[role="spinbutton"][aria-valuemax="23"], [role="spinbutton"][aria-valuemax="12"]')
        await expect(hour).to_have_count(1)
        twelve_hour = await hour.get_attribute('aria-valuemax') == '12'
        value_hour = (self.schedule.hour % 12 or 12) if twelve_hour else self.schedule.hour
        for control, value in ((hour, value_hour), (region.locator('[role="spinbutton"][aria-valuemax="59"]'), self.schedule.minute)):
            await control.click()
            for digit in f'{value:02d}':
                await control.press(digit)
            await control.press('Tab')
            await expect(control).to_have_attribute('aria-valuenow', str(value))
        if twelve_hour:
            # The real values of AM/PM are 0/1; read it back after toggling with keys, so filling only the hour cannot cause a 12-hour error.
            period = region.locator('[role="spinbutton"][aria-valuemax="1"]')
            target = str(int(self.schedule.hour >= 12))
            if await period.get_attribute('aria-valuenow') != target:
                await period.press('ArrowUp')
            await expect(period).to_have_attribute('aria-valuenow', target)
        # Tested on Chinese, English and Japanese pages: the date control reads back with year, month and day digits; separators may be localised, month names are not guessed.
        parts = [int(part) for part in re.findall(r'\d+', await date_input.input_value())]
        if parts != [self.schedule.year, self.schedule.month, self.schedule.day]:
            raise RuntimeError(f'Date did not read back the requested value: {await date_input.input_value()}')

    async def _publish(self, page: Page) -> None:
        # The image post footer always has Cancel, Save draft and the final submit; limit to the footer and strictly check for three items.
        # Use this order only in the observed layout and stop if the layout changes; never use a same-named button elsewhere on the page or guess translations.
        if not self.video_file:
            actions = page.locator('[data-surface$="lib:bizweb_create_post:footer"] [role="button"]')
            await expect(actions).to_have_count(3)
            button = actions.nth(2)
        else:
            # The share step is still Back plus the final main action; do not pick the Share step in the top navigation.
            actions = page.locator('[data-surface$="bizweb_create_reel:footer"] [role="button"]:not([aria-label])')
            await expect(actions).to_have_count(2)
            button = actions.nth(1)
        await expect(button).to_be_enabled()
        self.result['status'] = 'submission_unknown'
        self.result_file.parent.mkdir(parents=True, exist_ok=True)
        self.result_file.write_text(json.dumps(self.result, ensure_ascii=False, indent=2), encoding='utf-8')
        # Capture only the create response triggered by this click; neither the uploaded media ID nor the story ID in ad suggestions can stand in for the content ID.
        async with page.expect_response(lambda response: '/api/graphql' in response.url and
                parse_qs(response.request.post_data or '').get('fb_api_req_friendly_name') == ['BusinessComposerStoryCreationMutation'], timeout=90000) as response_info:
            await button.click()
        payload = await (await response_info.value).json()
        if payload.get('errors'):
            raise RuntimeError('The platform create response contains an error; look up the original record and do not submit again')
        creation = payload.get('data', {}).get('xfamily_content_create', {})
        if any(creation.get('errors', {}).values()):
            raise RuntimeError('The platform returned a create error; look up the original record and do not submit again')
        items = creation.get('items')
        if isinstance(items, dict):
            items = [items]
        if not isinstance(items, list) or len(items) != 1:
            raise RuntimeError('Submitted, but no unique content ID was obtained; result needs to be looked up')
        # Tested: pending_publish_content_id in the Reels response is empty, so look up the post details after success is confirmed.
        pending_id = items[0].get('pending_publish_content_id')
        if pending_id:
            self.result['content_id'] = str(pending_id)
        self.result_file.write_text(json.dumps(self.result, ensure_ascii=False, indent=2), encoding='utf-8')
        if self.video_file:
            # After the create response the page still runs further publish steps, so do not navigate away at once. Tested: the completion box shows this post's title,
            # a post preview and two actions, Close/Done. The title is this request's own input, not success text in some language.
            completion = page.locator('[role="dialog"][aria-labelledby][tabindex="-1"]').filter(has_text=self.title)
            await expect(completion).to_have_count(1, timeout=120000)
            await expect(completion.get_by_role('heading')).to_have_count(1)
            await expect(completion.get_by_role('button')).to_have_count(2)
            # Both actions of the completion box are Close/Done; clicking the last one means the platform accepted this Reel.
            await completion.get_by_role('button').last.click()
            await expect(completion).to_have_count(0)
            if not self.schedule:
                # Tested: the Reel create response may lack pending_publish_content_id, and the post list may not show it while the video is processing.
                # The completion dialog plus an error-free create response are already evidence of "submitted, processing"; the ID is only for later verification/deletion and must not block the publish result.
                self.result['status'] = 'processing'
                self.result['schedule'] = None
                self.result['timezone'] = 'Asia/Shanghai'
                self.result_file.write_text(json.dumps(self.result, ensure_ascii=False, indent=2), encoding='utf-8')
                return
        # Once the create response clearly accepts the post, look it up by Page and post ID; do not rely on success text in any language.
        # A scheduled post must read back its schedule; an image post published now must read back the post; neither result can be judged from a dialog alone.
        from uploader.meta_uploader.facebook_page_uploader.posts import open_meta_post
        state = 'scheduled_posts' if self.schedule else 'published_posts'
        list_url = f'https://business.facebook.com/latest/posts/{state}?asset_id={self.result["page_id"]}'
        _, content_id, _ = await open_meta_post(page, list_url=list_url, page_name=self.page_name,
            expected_text=self.title, content_id=self.result.get('content_id'), schedule=self.schedule)
        self.result['content_id'] = content_id
        self.result['status'] = 'scheduled' if self.schedule else ('processing' if self.video_file else 'published')
        self.result['schedule'] = self.schedule.isoformat() if self.schedule else None
        self.result['timezone'] = 'Asia/Shanghai'

    async def upload(self) -> dict:
        if self.video_file:
            self.validate_video_file(self.video_file)
        for path in self.image_files:
            self.validate_image_file(path)
        async with async_playwright() as playwright:
            browser, context, page = await _open_business_page(
                playwright, self.account_file, proxy=self.proxy, headless=self.headless
            )
            try:
                if await _is_business_logged_out(page):
                    raise RuntimeError("Business Suite login state is invalid; run login for the matching platform first")
                await dismiss_guidance_cards(page)
                await self._select_publish_location(page)
                await self._upload_files(page)
                await self._fill_caption(page)
                await self._advance_reels(page)
                await self._fill_schedule(page)
                await self._publish(page)
                await context.storage_state(path=str(self.account_file))
                return self.result
            finally:
                self.result_file.parent.mkdir(parents=True, exist_ok=True)
                self.result_file.write_text(json.dumps(self.result, ensure_ascii=False, indent=2), encoding='utf-8')
                await browser.close()
