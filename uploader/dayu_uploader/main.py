"""Dayu video publishing: check the identity, wait for processing, fill in the form, confirm publishing and record the submission result."""
from __future__ import annotations

import asyncio
import json
import math
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import cv2
from patchright.async_api import Page, async_playwright, expect

from conf import LOCAL_CHROME_PATH
from uploader.base_video import BaseVideoUploader
from uploader.dayu_uploader.publication import submit_dayu_publication
from uploader.dayu_uploader.schedule import fill_dayu_schedule, validate_dayu_schedule
from uploader.dayu_uploader.session import DAYU_VIDEO_URL, load_dayu_identity, read_dayu_identity
from uploader.dayu_uploader.constants import DAYU_SOURCE_REPRINT, DAYU_SOURCE_TYPES, DAYU_VIDEO_CATEGORIES
from utils.log import dayu_logger


async def wait_dayu_processing(page: Page, filename: str, timeout: int = 600) -> None:
    """A processing failure takes priority over the completion text; neither 100% nor "上传成功，处理中" (uploaded, processing) counts as ready to publish."""
    deadline = time.monotonic() + timeout
    # The video container is a business area that persists before and after upload; changing progress or result text is not used as an anchor.
    region = page.locator(".article-write_video-container")
    await expect(region).to_have_count(1)
    previous = None
    while time.monotonic() < deadline:
        text = await region.inner_text(timeout=max(1, min(5000, int((deadline - time.monotonic()) * 1000))))
        if re.search(r"失败|不支持|小于|超出|(?<!不)超过|请重新上传|无法", text):
            raise RuntimeError(f"Dayu rejected the video during processing: {text.strip()}")
        if "视频上传成功，处理完成" in text:  # "upload succeeded, processing complete"
            await expect(region.locator(".article-write_video-container-result-desc p span")).to_have_text(filename)
            return
        if text != previous:
            dayu_logger.info(f"Dayu upload status: {text.strip()}")
            previous = text
        await asyncio.sleep(min(.5, max(0, deadline - time.monotonic())))
    raise TimeoutError("Timed out waiting for Dayu upload/processing; nothing was submitted for publishing, check the current state of the asset")


class DayuVideo(BaseVideoUploader):
    """Publish one video through the actual page flow, and persist the submission ID so it can be verified read-only after a disconnect."""

    SUPPORTED_VIDEO_EXTENSIONS = {
        ".3gp", ".avi", ".flv", ".mp4", ".m3u8", ".mpg", ".asf", ".wmv",
        ".mkv", ".mov", ".ts", ".webm", ".mts",
    }
    SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".gif", ".png", ".bmp", ".jpeg"}

    def __init__(self, title, file_path, tags, account_file, thumbnail_path, category,
                 source, desc="", headless=True, debug=False, prepare_only=False,
                 upload_timeout=600, source_url="", schedule=None):
        self.title = title
        self.file_path = file_path
        self.tags = tags or []
        self.account_file = Path(account_file).resolve()
        self.thumbnail_path = thumbnail_path
        self.category = category
        self.source = source
        self.source_url = source_url
        self.desc = desc
        self.headless = headless
        self.debug = debug
        self.prepare_only = prepare_only
        self.upload_timeout = upload_timeout
        self.schedule = schedule

    def validate_upload_args(self) -> None:
        """Before upload, reject assets that cannot be decoded, are too short or exceed limits, and missing required fields."""
        self.schedule = validate_dayu_schedule(self.schedule)
        self.file_path = self.validate_video_file(self.file_path)
        self.thumbnail_path = self.validate_image_file(self.thumbnail_path)
        if not self.account_file.is_file():
            raise FileNotFoundError("Run sau dayu login first to save the account")
        load_dayu_identity(self.account_file)
        # The editor counts a Chinese character as 1 and ASCII as 0.5 (the page shows "demo" as 2/60).
        title_length = sum(.5 if ord(char) <= 255 else 1 for char in self.title.strip())
        if not 5 <= title_length <= 60:
            raise ValueError("Dayu title length must be 5–60 characters (ASCII counts as half a character)")
        if len(self.desc) > 200:
            raise ValueError("Dayu video description must not exceed 200 characters")
        if self.category not in DAYU_VIDEO_CATEGORIES:
            raise ValueError(f"Video category must be one of: {', '.join(DAYU_VIDEO_CATEGORIES)}")
        if self.source not in DAYU_SOURCE_TYPES:
            raise ValueError(f"An information source must be given explicitly: {', '.join(DAYU_SOURCE_TYPES)}")
        if self.source == DAYU_SOURCE_REPRINT:
            original = urlsplit(self.source_url)
            if original.scheme not in ("http", "https") or not original.hostname:
                raise ValueError("When the information source is 转载 (reprint), --source-url must give the http/https link of the original")
        elif self.source_url:
            raise ValueError("--source-url may only be given when the information source is 转载 (reprint)")
        if any(not tag.strip() or len(tag) > 10 for tag in self.tags):
            raise ValueError("Video tags must not be empty and each must be at most 10 characters")
        if self.upload_timeout <= 0:
            raise ValueError("The upload and publish verification timeout must be greater than 0 seconds")
        if self.thumbnail_path.stat().st_size > 5 * 1024 ** 2:
            raise ValueError("Dayu video cover must not exceed 5 MiB")
        capture = cv2.VideoCapture(str(self.file_path))
        try:
            fps = capture.get(cv2.CAP_PROP_FPS)
            frames = capture.get(cv2.CAP_PROP_FRAME_COUNT)
            width = capture.get(cv2.CAP_PROP_FRAME_WIDTH)
            height = capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
        finally:
            capture.release()
        if not all(math.isfinite(value) and value > 0 for value in (fps, frames, width, height)):
            raise ValueError("Cannot read the video size, frame count or frame rate; refusing to upload an unknown asset")
        duration = frames / fps
        if duration < 5:
            raise ValueError(f"Dayu videos must be at least 5 seconds, this one is about {duration:.3f} seconds")
        portrait = height > width
        if self.file_path.stat().st_size > (5 if portrait else 10) * 1024 ** 3:
            raise ValueError("Video exceeds the Dayu file size limit (landscape 10 GiB, portrait 5 GiB)")
        if portrait and duration > 1800:
            raise ValueError("Dayu portrait videos must not be longer than 30 minutes")

    async def fill_video_form(self, page: Page) -> None:
        """Fill in and read back the title, description, category, tags, cover and source; the source is never chosen on the user's behalf."""
        # The title is actually a contenteditable; the fixed placeholder ("视频标题最少5个字" = title needs at least 5 characters) tells it apart from the description box and other editable areas.
        title = page.locator('[contenteditable="true"][placeholder="视频标题最少5个字"]')
        await title.fill(self.title)
        await expect(title).to_have_text(self.title)
        # The description uses a textarea in the form; the category is scoped by its field label ("视频分类" = video category) so other dropdowns of the same structure are not clicked.
        description = page.locator(".w-form-field").filter(has=page.locator("textarea")).locator("textarea")
        await description.fill(self.desc)
        await expect(description).to_have_value(self.desc)
        category = page.locator(".w-form-field").filter(
            has=page.locator("label").filter(has_text="视频分类"),
        )
        await category.locator(".widgets-selects_container").click()
        await category.get_by_role("link", name=self.category, exact=True).click()
        await expect(category.locator(".widgets-selects_container")).to_have_text(self.category)
        if self.tags:
            # The tag component adds input slots dynamically; scope to the component first, then pick slots in the order the user gave.
            tags = page.locator(".article-write_video-tags")
            await tags.click()
            for index, tag in enumerate(self.tags):
                # Tag slots follow the order the user gave; Enter adds an empty slot at the end, it does not pick an arbitrary Nth control.
                inputs = tags.locator("input")
                await expect(inputs).to_have_count(index + 1)
                await inputs.nth(index).fill(tag)
                await inputs.nth(index).press("Enter")
            await title.click()
            # Tested: after Enter/blur the value briefly loses a character and keeps an empty slot; Vue restores the final tag value afterwards.
            await expect(tags.locator("input")).to_have_count(len(self.tags))
            for index, tag in enumerate(self.tags):
                await expect(tags.locator("input").nth(index)).to_have_value(tag)
        # coverImg is the semantic ID of the cover field; scoping to its input keeps the cover from going to the main video uploader.
        await page.locator("#coverImg input[type=file]").set_input_files(str(self.thumbnail_path))
        # Cropping and asset selection share one dialog component; locate only the instance visible now and skip hidden templates.
        dialog = page.locator(".article-material-image-dialog:visible")
        await expect(dialog).to_have_count(1, timeout=30000)
        await dialog.get_by_role("button", name="保存", exact=True).click()  # "保存" = Save
        await expect(page.locator(".article-material-image-dialog:visible")).to_have_count(0, timeout=30000)
        cover = page.locator("#coverImg #form_main_cover_img")
        await expect(cover).to_be_visible()
        await expect(cover).to_have_attribute("src", re.compile(r"^https?://image\.uc\.cn/"))
        # The value of each source radio matches the page option; options are told apart by business value, not by their left-to-right order.
        source = page.locator(f'input[type=radio][value="{self.source}"]')
        await source.check()
        await expect(source).to_be_checked()
        # The original-link field ("原文链接") is located by its label inside the source area, excluding other text boxes; when the source is not a reprint this conditional field should disappear.
        original_link = page.locator(".source-remark-detail .article-write_box-form-filed").filter(
            has=page.locator("label").filter(has_text="原文链接"),
        ).locator('input[type="text"]')
        if self.source == DAYU_SOURCE_REPRINT:
            await original_link.fill(self.source_url)
            await expect(original_link).to_have_value(self.source_url)
        else:
            await expect(original_link).to_have_count(0)
        await fill_dayu_schedule(page, self.schedule)

    async def main(self) -> dict:
        """Submit only once; success as soon as the platform's final publish response confirms this post's ID."""
        self.validate_upload_args()
        expected = load_dayu_identity(self.account_file)
        results_dir = self.account_file.parent / "dayu_results"
        results_dir.mkdir(exist_ok=True)
        result_file = results_dir / f"{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}.json"
        result = {"success": False, "status": "preparing", "type": "video", "title": self.title,
                  "video_file": str(self.file_path), "identity": expected,
                  "result_file": str(result_file)}
        if self.schedule:
            result["schedule"] = self.schedule.isoformat()
        result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                executable_path=LOCAL_CHROME_PATH or None, channel="chrome", headless=self.headless,
            )
            page = None
            try:
                context = await browser.new_context(storage_state=str(self.account_file), timezone_id="Asia/Shanghai")
                page = await context.new_page()
                await page.goto(DAYU_VIDEO_URL, wait_until="domcontentloaded", timeout=45000)
                identity = await read_dayu_identity(page)
                if identity["wmid"] != expected["wmid"]:
                    raise RuntimeError("Dayu identity does not match, upload aborted")
                result["identity"] = identity
                # The main video uploader has name=file and the cover input does not; this tells the two upload inputs apart.
                file_input = page.locator('input[type="file"][name="file"]')
                await expect(file_input).to_have_count(1, timeout=30000)
                await file_input.set_input_files(str(self.file_path))
                await wait_dayu_processing(page, self.file_path.name, self.upload_timeout)
                await self.fill_video_form(page)
                # After filling in the form and the async cover processing, check the same identity and the video processing result again.
                if (await read_dayu_identity(page))["wmid"] != identity["wmid"]:
                    raise RuntimeError("The Dayu identity changed while the form was being filled in; refusing to submit")
                await wait_dayu_processing(page, self.file_path.name, self.upload_timeout)
                if self.prepare_only:
                    await page.screenshot(path=str(result_file.with_suffix(".png")), full_page=True)
                    result.update(success=True, status="prepared")
                    return result

                await submit_dayu_publication(page, result, result_file)
                await context.storage_state(path=str(self.account_file))
                action = "定时发布已安排" if self.schedule else "发表成功"  # "scheduled publishing arranged" / "published"
                dayu_logger.success(f"Dayu {action}: {result['content_id']}")
                return result
            except Exception as exc:
                result["error"] = str(exc)
                dayu_logger.error(f"Dayu stage={result['status']}, result file={result_file}: {exc}")
                if self.debug and page is not None:
                    await page.screenshot(path=str(result_file.with_suffix(".png")))
                raise
            finally:
                result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                await browser.close()
