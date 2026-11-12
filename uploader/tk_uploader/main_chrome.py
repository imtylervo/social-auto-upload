# -*- coding: utf-8 -*-
import re
from datetime import datetime

from playwright.async_api import Playwright, async_playwright
import os
import asyncio

from conf import LOCAL_CHROME_PATH, LOCAL_CHROME_HEADLESS
from uploader.tk_uploader.tk_config import Tk_Locator
from utils.base_social_media import set_init_script
from utils.files_times import get_absolute_path
from utils.log import tiktok_logger


async def cookie_auth(account_file):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=LOCAL_CHROME_HEADLESS)
        context = await browser.new_context(storage_state=account_file)
        context = await set_init_script(context)
        # Create a new page
        page = await context.new_page()
        # Open the given URL
        await page.goto("https://www.tiktok.com/tiktokstudio/upload?lang=en")
        await page.wait_for_load_state('networkidle')
        try:
            # Select all select elements
            select_elements = await page.query_selector_all('select')
            for element in select_elements:
                class_name = await element.get_attribute('class')
                # Match class names of a specific pattern with a regex
                if re.match(r'tiktok-.*-SelectFormContainer.*', class_name):
                    tiktok_logger.error("[+] cookie expired")
                    return False
            tiktok_logger.success("[+] cookie valid")
            return True
        except:
            tiktok_logger.success("[+] cookie valid")
            return True


async def tiktok_setup(account_file, handle=False):
    account_file = get_absolute_path(account_file, "tk_uploader")
    if not os.path.exists(account_file) or not await cookie_auth(account_file):
        if not handle:
            return False
        tiktok_logger.info('[+] cookie file is not existed or expired. Now open the browser auto. Please login with your way(gmail phone, whatever, the cookie file will generated after login')
        await get_tiktok_cookie(account_file)
    return True


async def get_tiktok_cookie(account_file):
    async with async_playwright() as playwright:
        options = {
            'args': [
                '--lang en-GB',
            ],
            'headless': LOCAL_CHROME_HEADLESS,  # Set headless option here
        }
        # Make sure to run headed.
        browser = await playwright.chromium.launch(**options)
        # Setup context however you like.
        context = await browser.new_context()  # Pass any options
        context = await set_init_script(context)
        # Pause the page, and start recording manually.
        page = await context.new_page()
        await page.goto("https://www.tiktok.com/login?lang=en")
        await page.pause()
        # Click Resume in the debugger to save the cookie
        await context.storage_state(path=account_file)


PRIVACY_LABELS = ("Everyone", "Friends", "Only you")
UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload"
CONTENT_URL = "https://www.tiktok.com/tiktokstudio/content"
# TikTok Studio as of 2026-11: the Post button has a stable data-e2e; the older button-group markup is kept as a fallback.
POST_BUTTON = '[data-e2e="post_video_button"], div.button-group > button:has-text("Post")'


class TiktokVideo(object):
    def __init__(self, title, file_path, tags, publish_date, account_file, thumbnail_path=None, privacy=None,
                 proxy=None):
        """
        privacy: None keeps TikTok's default, or one of PRIVACY_LABELS ("Everyone", "Friends", "Only you").
        proxy: optional Playwright proxy dict for upload(), e.g. {"server": "http://127.0.0.1:7890"}.
        """
        if privacy is not None and privacy not in PRIVACY_LABELS:
            raise ValueError(f"privacy must be one of {PRIVACY_LABELS}")
        if privacy == "Only you" and publish_date != 0:
            raise ValueError("TikTok cannot schedule a private video: use publish_date=0 with privacy='Only you'")
        self.title = title
        self.file_path = file_path
        self.tags = tags
        self.publish_date = publish_date
        self.thumbnail_path = thumbnail_path
        self.account_file = account_file
        self.privacy = privacy
        self.proxy = proxy
        self.local_executable_path = LOCAL_CHROME_PATH
        self.headless = LOCAL_CHROME_HEADLESS
        self.locator_base = None

    async def set_schedule_time(self, page, publish_date):
        schedule_input_element = self.locator_base.get_by_label('Schedule')
        await schedule_input_element.wait_for(state='visible')  # Make sure the button is visible

        await schedule_input_element.click(force=True)
        if await self.locator_base.locator('div.TUXButton-content >> text=Allow').count():
            await self.locator_base.locator('div.TUXButton-content >> text=Allow').click()

        scheduled_picker = self.locator_base.locator('div.scheduled-picker')
        await scheduled_picker.locator('div.TUXInputBox').nth(1).click()

        calendar_month = await self.locator_base.locator(
            'div.calendar-wrapper span.month-title').inner_text()

        n_calendar_month = datetime.strptime(calendar_month, '%B').month

        schedule_month = publish_date.month

        if n_calendar_month != schedule_month:
            if n_calendar_month < schedule_month:
                arrow = self.locator_base.locator('div.calendar-wrapper span.arrow').nth(-1)
            else:
                arrow = self.locator_base.locator('div.calendar-wrapper span.arrow').nth(0)
            await arrow.click()

        # day set
        valid_days_locator = self.locator_base.locator(
            'div.calendar-wrapper span.day.valid')
        valid_days = await valid_days_locator.count()
        for i in range(valid_days):
            day_element = valid_days_locator.nth(i)
            text = await day_element.inner_text()
            if text.strip() == str(publish_date.day):
                await day_element.click()
                break
        # time set
        await scheduled_picker.locator('div.TUXInputBox').nth(0).click()

        hour_str = publish_date.strftime("%H")
        correct_minute = int(publish_date.minute / 5)
        minute_str = f"{correct_minute:02d}"

        hour_selector = f"span.tiktok-timepicker-left:has-text('{hour_str}')"
        minute_selector = f"span.tiktok-timepicker-right:has-text('{minute_str}')"

        # pick hour first
        await page.wait_for_timeout(1000)  # Wait 500 ms
        await self.locator_base.locator(hour_selector).click()
        # click time button again
        await page.wait_for_timeout(1000)  # Wait 500 ms
        # pick minutes after
        await self.locator_base.locator(minute_selector).click()

        # click title to remove the focus.
        # await self.locator_base.locator("h1:has-text('Upload video')").click()

    async def handle_upload_error(self, page):
        tiktok_logger.info("video upload error retrying.")
        select_file_button = self.locator_base.locator('button[aria-label="Select file"]')
        async with page.expect_file_chooser() as fc_info:
            await select_file_button.click()
        file_chooser = await fc_info.value
        await file_chooser.set_files(self.file_path)

    async def upload(self, playwright: Playwright) -> None:
        launch_options = {"headless": self.headless}
        if self.local_executable_path:
            launch_options["executable_path"] = self.local_executable_path
        if self.proxy:
            launch_options["proxy"] = self.proxy
        browser = await playwright.chromium.launch(**launch_options)
        context = await browser.new_context(storage_state=f"{self.account_file}")
        # context = await set_init_script(context)
        page = await context.new_page()

        # change language to eng first
        await self.change_language(page)
        video_id = await self.upload_on_page(page)
        tiktok_logger.success(f"video_id: {video_id}")

        await context.storage_state(path=f"{self.account_file}")  # save cookie
        tiktok_logger.info('  [-] update cookie！')
        await asyncio.sleep(2)  # close delay for look the video status
        # close all
        await context.close()
        await browser.close()

    async def upload_on_page(self, page):
        """
        The whole flow on a page that is already signed in and shows TikTok in English. Use this directly when the
        browser is not launched by upload() (another Playwright-compatible browser, a persistent profile, a proxy).
        Returns the id of the newest video in the content list.
        """
        await self.fill_form(page)
        await self.click_publish(page)
        return await self.get_last_video_id(page)

    async def fill_form(self, page):
        """Everything up to, but not including, the click on Post."""
        await page.goto(UPLOAD_URL)
        tiktok_logger.info(f'[+]Uploading-------{self.title}.mp4')

        await page.wait_for_url(UPLOAD_URL, timeout=10000)

        try:
            await page.wait_for_selector(
                'iframe[data-tt="Upload_index_iframe"], div.upload-container, button:has-text("Select video")',
                timeout=15000)
            tiktok_logger.info("Upload page is ready.")
        except Exception as e:
            tiktok_logger.error("The upload page did not show its upload area within the timeout.")

        await self.choose_base_locator(page)

        upload_button = self.locator_base.locator(
            'button:has-text("Select video"):visible')
        await upload_button.wait_for(state='visible')  # Make sure the button is visible

        async with page.expect_file_chooser() as fc_info:
            await upload_button.click()
        file_chooser = await fc_info.value
        await file_chooser.set_files(self.file_path)

        # the form (and with it the Post button) appears once TikTok accepted the file
        await self.locator_base.locator(POST_BUTTON).first.wait_for(state='visible', timeout=120000)
        # pop-ups TikTok shows over the form a few seconds later; they swallow every click until closed
        await self.dismiss_popups(page, wait_ms=15000)

        await self.add_title_tags(page)
        # detect upload status
        await self.detect_upload_status(page)
        if self.thumbnail_path:
            tiktok_logger.info(f'[+] Uploading thumbnail file {self.title}.png')
            await self.upload_thumbnails(page)

        await self.dismiss_popups(page)
        if self.privacy:
            shown = await self.set_privacy(page, self.privacy)
            tiktok_logger.info(f"  [-] who can see this post: {shown}")

        if self.publish_date != 0:
            await self.set_schedule_time(page, self.publish_date)

    async def dismiss_popups(self, page, wait_ms=0):
        """
        Close what TikTok Studio lays over the upload form. The "Turn on automatic content checks?" offer is declined
        (Cancel): an account setting is not changed here. Polls for wait_ms because the offer shows up late.
        """
        deadline = asyncio.get_event_loop().time() + wait_ms / 1000
        while True:
            offer = self.locator_base.locator('[role="dialog"]:has-text("automatic content checks")')
            if await offer.count():
                tiktok_logger.info("  [-] declining the automatic content checks offer")
                await offer.get_by_role("button", name="Cancel").click()
            got_it = self.locator_base.locator('button:has-text("Got it"):visible')
            if await got_it.count():
                await got_it.first.click()
            if asyncio.get_event_loop().time() >= deadline:
                return
            await page.wait_for_timeout(1000)

    async def set_privacy(self, page, label):
        """Set "Who can see this post" to label and return what the control shows afterwards."""
        trigger = self.locator_base.locator('button[role="combobox"]').filter(
            has_text=re.compile(r"^(%s)$" % "|".join(PRIVACY_LABELS))).last
        await trigger.scroll_into_view_if_needed()
        if (await trigger.inner_text()).strip() != label:
            await trigger.click()
            option = self.locator_base.locator('[role="option"]').filter(has_text=re.compile(rf"^{re.escape(label)}"))
            await option.first.click(timeout=10000)
            await page.wait_for_timeout(800)
        shown = (await trigger.inner_text()).strip()
        if shown != label:
            raise RuntimeError(f"privacy is {shown!r} after choosing {label!r}")
        return shown

    async def delete_video(self, page, video_id):
        """Delete one post by its video id from the TikTok Studio content list. Returns True when it is gone."""
        await page.goto(CONTENT_URL)
        await page.wait_for_selector('div[data-tt="components_PostTable_Container"]', timeout=45000)
        await page.wait_for_timeout(4000)
        link = page.locator(f'div[data-tt="components_PostInfoCell_Container"] a[href*="/video/{video_id}"]').first
        if not await link.count():
            raise RuntimeError(f"video {video_id} is not in the content list")
        row = link.locator('xpath=ancestor::*[.//button][.//*[contains(text(),"Private") or '
                           'contains(text(),"Everyone") or contains(text(),"Friends")]][1]')
        await row.locator("button").last.click()  # the "..." actions button of that row
        await page.wait_for_timeout(1200)
        await page.get_by_text("Delete", exact=True).locator("visible=true").last.click(timeout=8000)
        await page.wait_for_timeout(1500)
        await page.locator("button:visible").filter(has_text=re.compile(r"^Delete$")).last.click(timeout=10000)
        await page.wait_for_timeout(6000)
        await page.reload()
        await page.wait_for_timeout(8000)
        return await page.locator(f'a[href*="/video/{video_id}"]').count() == 0

    async def add_title_tags(self, page):

        editor_locator = self.locator_base.locator('div.public-DraftEditor-content')
        await editor_locator.click()

        await page.keyboard.press("End")

        await page.keyboard.press("Control+A")

        await page.keyboard.press("Delete")

        await page.keyboard.press("End")

        await page.wait_for_timeout(1000)  # Wait 1 second

        await page.keyboard.insert_text(self.title)
        await page.wait_for_timeout(1000)  # Wait 1 second
        await page.keyboard.press("End")

        await page.keyboard.press("Enter")

        # tag part
        for index, tag in enumerate(self.tags, start=1):
            tiktok_logger.info("Setting the %s tag" % index)
            await page.keyboard.press("End")
            await page.wait_for_timeout(1000)  # Wait 1 second
            await page.keyboard.insert_text("#" + tag + " ")
            await page.keyboard.press("Space")
            await page.wait_for_timeout(1000)  # Wait 1 second

            await page.keyboard.press("Backspace")
            await page.keyboard.press("End")

    async def upload_thumbnails(self, page):
        await self.locator_base.locator(".cover-container").click()
        await self.locator_base.locator(".cover-edit-container >> text=Upload cover").click()
        async with page.expect_file_chooser() as fc_info:
            await self.locator_base.locator(".upload-image-upload-area").click()
            file_chooser = await fc_info.value
            await file_chooser.set_files(self.thumbnail_path)
        await self.locator_base.locator('div.cover-edit-panel:not(.hide-panel)').get_by_role(
            "button", name="Confirm").click()
        await page.wait_for_timeout(3000)  # wait 3s, fix it later

    async def change_language(self, page):
        # set the language to english
        await page.goto("https://www.tiktok.com")
        await page.wait_for_load_state('domcontentloaded')
        await page.wait_for_selector('[data-e2e="nav-more-menu"]')
        # Already set to English, skip this step
        if await page.locator('[data-e2e="nav-more-menu"]').text_content() == "More":
            return

        await page.locator('[data-e2e="nav-more-menu"]').click()
        await page.locator('[data-e2e="language-select"]').click()
        await page.locator('#creator-tools-selection-menu-header >> text=English (US)').click()

    async def click_publish(self, page, timeout=180):
        """Click Post and wait for the content list. Raises TimeoutError instead of looping forever."""
        deadline = asyncio.get_event_loop().time() + timeout
        publish_button = self.locator_base.locator(POST_BUTTON).first
        clicked = False
        while asyncio.get_event_loop().time() < deadline:
            if page.url.startswith(CONTENT_URL):
                tiktok_logger.success("  [-] video published success")
                return
            try:
                # TikTok asks again when its checks have not finished yet
                confirm = self.locator_base.locator('[role="dialog"] button:has-text("Post now"):visible')
                if await confirm.count():
                    await confirm.first.click()
                elif not clicked and await publish_button.count() and await publish_button.is_enabled():
                    await publish_button.click()
                    clicked = True
                await page.wait_for_url(CONTENT_URL + "**", timeout=3000)
            except Exception:
                tiktok_logger.info("  [-] video publishing")
                await asyncio.sleep(0.5)
        raise TimeoutError(f"TikTok did not open the content list within {timeout}s after Post")

    async def get_last_video_id(self, page):
        await page.wait_for_selector('div[data-tt="components_PostTable_Container"]')
        video_list_locator = self.locator_base.locator('div[data-tt="components_PostTable_Container"] div[data-tt="components_PostInfoCell_Container"] a')
        if await video_list_locator.count():
            first_video_obj = await video_list_locator.nth(0).get_attribute('href')
            video_id = re.search(r'video/(\d+)', first_video_obj).group(1) if first_video_obj else None
            return video_id


    async def detect_upload_status(self, page, timeout=900):
        """Wait until TikTok has the whole file (Post becomes clickable). Raises TimeoutError after timeout seconds."""
        deadline = asyncio.get_event_loop().time() + timeout
        post_button = self.locator_base.locator(POST_BUTTON).first
        while asyncio.get_event_loop().time() < deadline:
            try:
                if await post_button.count() and await post_button.is_enabled():
                    tiktok_logger.info("  [-]video uploaded.")
                    return
                tiktok_logger.info("  [-] video uploading...")
                await asyncio.sleep(2)
                if await self.locator_base.locator(
                        'button[aria-label="Select file"]').count():
                    tiktok_logger.info("  [-] found some error while uploading now retry...")
                    await self.handle_upload_error(page)
            except Exception:
                tiktok_logger.info("  [-] video uploading...")
                await asyncio.sleep(2)
        raise TimeoutError(f"the video was not ready to post within {timeout}s")

    async def choose_base_locator(self, page):
        # await page.wait_for_selector('div.upload-container')
        if await page.locator('iframe[data-tt="Upload_index_iframe"]').count():
            self.locator_base = page.frame_locator(Tk_Locator.tk_iframe)
        else:
            self.locator_base = page.locator(Tk_Locator.default) 

    async def main(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)
