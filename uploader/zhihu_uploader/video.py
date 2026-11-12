"""Zhihu single-video upload: transfer, metadata, schedule option and submission state are checked separately."""
from __future__ import annotations

import asyncio
import json
import sys
import math
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import cv2
from patchright.async_api import Page, async_playwright, expect

from conf import LOCAL_CHROME_PATH
from uploader.zhihu_uploader.constants import (
    ZHIHU_ORIGINALITY, ZHIHU_TIMEZONE, ZHIHU_VIDEO_DESCRIPTION_MAX, ZHIHU_VIDEO_EXTENSIONS,
    ZHIHU_VIDEO_MAX_BYTES, ZHIHU_VIDEO_MIN_BYTES, ZHIHU_VIDEO_MAX_SECONDS, ZHIHU_VIDEO_TITLE_MAX,
    ZHIHU_VIDEO_TITLE_MIN, ZHIHU_VIDEO_URL, ZHIHU_VIDEO_TOPICS_MAX,
)
from uploader.zhihu_uploader.schedule import fill_zhihu_video_schedule, validate_zhihu_schedule
from uploader.zhihu_uploader.session import load_zhihu_identity, read_zhihu_identity


class ZhihuVideo:
    """Upload and publish one Zhihu video; an unknown submission result is kept in a local JSON file."""

    def __init__(self, title, file_path, account_file, description, category,
                 topics, video_mark, originality, schedule=None, show_options=False,
                 headless=True, debug=False, prepare_only=False, upload_timeout=1200):
        self.title = title
        self.file_path = Path(file_path).expanduser().resolve()
        self.account_file = Path(account_file).resolve()
        self.description = description
        self.category = category
        self.show_options = show_options
        self.topics = topics
        self.video_mark = video_mark
        self.originality = originality
        self.schedule = schedule
        self.headless = headless
        self.debug = debug
        self.prepare_only = prepare_only
        self.upload_timeout = upload_timeout

    def validate_upload_args(self) -> None:
        """Check the video, title, description and the category parameters the current upload needs, following the page's hints."""
        if not self.file_path.is_file():
            raise FileNotFoundError(f"Zhihu video not found: {self.file_path}")
        if self.file_path.suffix.lower() not in ZHIHU_VIDEO_EXTENSIONS:
            raise ValueError(f"Video format not supported by the Zhihu page: {self.file_path.suffix}")
        if self.file_path.stat().st_size <= ZHIHU_VIDEO_MIN_BYTES:
            raise ValueError("Zhihu videos must be larger than 100KB")
        if self.file_path.stat().st_size > ZHIHU_VIDEO_MAX_BYTES:
            raise ValueError("Zhihu video file must not exceed 20 GB")
        capture = cv2.VideoCapture(str(self.file_path))
        try:
            fps = capture.get(cv2.CAP_PROP_FPS)
            frames = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        finally:
            capture.release()
        if not math.isfinite(fps) or not math.isfinite(frames) or fps <= 0 or frames <= 0:
            raise ValueError("Cannot read the video frame rate or frame count; refusing to upload an unknown asset")
        if frames / fps > ZHIHU_VIDEO_MAX_SECONDS:
            raise ValueError("Zhihu videos must not be longer than 4 hours")
        if not ZHIHU_VIDEO_TITLE_MIN <= len(self.title.strip()) <= ZHIHU_VIDEO_TITLE_MAX:
            raise ValueError(f"Zhihu video title must be {ZHIHU_VIDEO_TITLE_MIN}–{ZHIHU_VIDEO_TITLE_MAX} characters")
        if len(self.description) > ZHIHU_VIDEO_DESCRIPTION_MAX:
            raise ValueError(f"Zhihu video description must not exceed {ZHIHU_VIDEO_DESCRIPTION_MAX} characters")
        if len(self.topics) > ZHIHU_VIDEO_TOPICS_MAX:
            raise ValueError(f"Zhihu videos allow at most {ZHIHU_VIDEO_TOPICS_MAX} topics")
        if any(not topic.strip() for topic in self.topics):
            raise ValueError("Zhihu video topics must not be empty")
        if self.topics:
            raise ValueError("Automatic topic selection is not supported for Zhihu videos yet; describe the content in the description")
        if self.originality not in ZHIHU_ORIGINALITY:
            raise ValueError("The originality flag must be original or reprint")
        self.schedule = validate_zhihu_schedule(self.schedule)
        if not self.account_file.is_file():
            raise FileNotFoundError("Run sau zhihu login first to save the account")
        self.identity = load_zhihu_identity(self.account_file)
        if self.upload_timeout <= 0:
            raise ValueError("The upload timeout must be greater than 0 seconds")

    async def video_options(self, page: Page) -> dict:
        """Read the full candidate list from the menu actually rendered for this asset; old second-level fields do not stand in for the new form."""
        # The "所属领域" (field) label scopes the business row and visible scopes the list opened now, excluding hidden menus.
        field = page.locator(".VideoUploadForm-item").filter(has=page.get_by_text("所属领域", exact=True))
        await expect(field).to_have_count(1)
        control = field.get_by_role("combobox")
        await control.click()
        menu = page.locator(".VideoUploadForm-selectList:visible")
        await expect(menu).to_have_count(1)
        # The page source renders exactly one name per field; read the whole menu row by row, without relying on unobserved child component classes.
        await expect(menu).to_contain_text(re.compile(r"\S"))
        categories = [text.strip() for text in await menu.get_by_role("option").all_inner_texts()
                      if text.strip() and text.strip() != "选择领域"]  # placeholder "choose a field"
        await control.click()
        mark_field = page.locator(".VideoUploadForm-item").filter(has=page.get_by_text("视频标记", exact=True))  # "视频标记" = video mark
        await mark_field.get_by_role("button", name="选择视频标记", exact=True).click()
        modal = page.locator(".VideoUploadForm-videoTypeModal:visible")
        await expect(modal).to_be_visible()
        marks = [text.strip() for text in await modal.locator(".VideoUploadForm-videoTypeModalOption").all_inner_texts()
                 if text.strip() and text.strip() not in {"确认", "取消", "关闭"}]  # Confirm / Cancel / Close
        # Only cancel the popup after reading the options; the first candidate is not taken as the user's choice.
        await modal.get_by_role("button", name="取消", exact=True).click()
        await expect(modal).to_be_hidden()
        if not categories or not marks or len(categories) != len(set(categories)) or len(marks) != len(set(marks)):
            raise RuntimeError("Zhihu candidates are empty or duplicated; cannot build a selection menu safely")
        return {"category": categories, "video_mark": marks}

    async def select_option(self, label: str, value: str | None, choices: list[str]) -> str:
        """Show the actual candidates in the terminal and select by number; script calls may only use values present in this menu."""
        if value is not None:
            if value not in choices:
                raise ValueError(f"{label} must be one of: {'、'.join(choices)}")
            return value
        print(label + "：", file=sys.stderr)
        for index, choice in enumerate(choices, 1):
            print(f"  {index}. {choice}", file=sys.stderr)
        if not sys.stdin.isatty():
            raise ValueError(f"Non-interactive calls must specify {label}; use --show-options first to get the full candidate list")
        answer = await asyncio.to_thread(input, f"选择{label}编号（1–{len(choices)}）：")
        if not answer.isdecimal() or not 1 <= int(answer) <= len(choices):
            raise ValueError(f"Invalid {label} number")
        return choices[int(answer) - 1]

    async def fill_video_options(self, page: Page) -> None:
        """Select only live menu values that were checked, then read the form back."""
        field = page.locator(".VideoUploadForm-item").filter(has=page.get_by_text("所属领域", exact=True))
        control = field.get_by_role("combobox")
        await control.click()
        await page.locator(".VideoUploadForm-selectList:visible").get_by_role("option", name=self.category, exact=True).click()
        await expect(control).to_contain_text(self.category)
        mark_field = page.locator(".VideoUploadForm-item").filter(has=page.get_by_text("视频标记", exact=True))
        await mark_field.get_by_role("button", name="选择视频标记", exact=True).click()
        modal = page.locator(".VideoUploadForm-videoTypeModal:visible")
        await modal.get_by_role("button", name=self.video_mark, exact=True).click()
        await modal.get_by_role("button", name="确认", exact=True).click()
        await expect(modal).to_be_hidden()

    async def fill_video_form(self, page: Page) -> None:
        """Wait for this video's transfer to succeed, then fill in and read back the metadata the page requires."""
        form = page.locator(".VideoUploadForm-item").filter(
            has=page.get_by_text("标题与介绍", exact=True),
        )
        await expect(form).to_be_visible(timeout=self.upload_timeout * 1000)
        failure = page.get_by_text("视频上传失败", exact=True)
        if await failure.count():
            raise RuntimeError("Zhihu clearly shows that the video upload failed")
        # The page code treats "上传成功" (upload succeeded) as the uploaded state; wait only for that state, the form appearing or progress completing does not mean processing is done.
        await expect(page.get_by_text("上传成功", exact=True)).to_be_visible(timeout=self.upload_timeout * 1000)

        title = form.locator("textarea")
        await expect(title).to_have_count(1)
        await title.fill(self.title)
        await expect(title).to_have_value(self.title)
        description = form.locator('[contenteditable="true"][role="textbox"]')
        await expect(description).to_have_count(1)
        await description.fill(self.description)
        if self.description.strip():
            await expect(description).to_contain_text(self.description[:80])

        await self.fill_video_options(page)

        # Original/reprint is a separate checkbox on the page; set it from the parameter, not from the visual order of controls.
        # Scope by the "原创视频" (original video) business row, so it is not confused with other checkboxes such as scheduled publishing.
        originality = page.locator(".VideoUploadForm-item").filter(
            has=page.get_by_text("原创视频", exact=True),
        ).get_by_role("checkbox")
        await expect(originality).to_have_count(1)
        wanted_original = self.originality == "original"
        if await originality.is_checked() != wanted_original:
            await originality.click()
        if wanted_original:
            await expect(originality).to_be_checked()
        else:
            await expect(originality).not_to_be_checked()

        await fill_zhihu_video_schedule(page, self.schedule)

    async def main(self) -> dict:
        """Submit only once; if the page does not confirm this post's URL, record submission_unknown."""
        self.validate_upload_args()
        results_dir = self.account_file.parent / "zhihu_results"
        results_dir.mkdir(exist_ok=True)
        result_file = results_dir / f"{datetime.now(ZHIHU_TIMEZONE):%Y%m%d-%H%M%S}-{uuid4().hex[:8]}.json"
        result = {
            "success": False, "status": "preparing", "type": "video", "title": self.title,
            "video_file": str(self.file_path), "identity": self.identity, "topics": self.topics,
            "category": self.category,
            "video_mark": self.video_mark, "originality": self.originality,
            "result_file": str(result_file),
        }
        if self.schedule:
            result["schedule"] = self.schedule.isoformat()
        result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                executable_path=LOCAL_CHROME_PATH or None, channel="chrome", headless=self.headless,
            )
            page = None
            submitted = False
            try:
                context = await browser.new_context(
                    storage_state=str(self.account_file), timezone_id="Asia/Shanghai",
                )
                page = await context.new_page()
                response = await page.goto(ZHIHU_VIDEO_URL, wait_until="domcontentloaded", timeout=45000)
                if response is not None and response.status >= 400:
                    raise RuntimeError(f"Failed to open the Zhihu video upload page, HTTP {response.status}")
                if await read_zhihu_identity(page) != self.identity:
                    raise RuntimeError("The Zhihu video page header does not match the local account binding")
                # The class and accept of this input come from the actual DOM of the upload home page; not mixed up with cover/body image inputs.
                video_input = page.locator("input.VideoUploadButton-fileInput[type=file]")
                await expect(video_input).to_have_count(1)
                await video_input.set_input_files(str(self.file_path))
                result["status"] = "uploading"
                result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                # The form appears only after the asset is chosen; the candidates come from the actual page for this account and this asset.
                await expect(page.get_by_text("上传成功", exact=True)).to_be_visible(timeout=self.upload_timeout * 1000)
                choices = await self.video_options(page)
                result["options"] = choices
                if self.show_options:
                    result["status"] = "options_listed"
                    return result
                self.category = await self.select_option("所属领域", self.category, choices["category"])
                self.video_mark = await self.select_option("视频标记", self.video_mark, choices["video_mark"])
                result.update(category=self.category, video_mark=self.video_mark)
                await self.fill_video_form(page)
                if await read_zhihu_identity(page) != self.identity:
                    raise RuntimeError("The current account changed while the Zhihu video form was being filled in")
                result["status"] = "prepared"
                result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                if self.prepare_only:
                    return result

                # The current video entry shows a success popup on the same page, and "查看详情" (view details) opens /pin/<id> separately.
                # Do not wait for the page to jump to the old /zvideo/, or a published post would be judged unknown.
                publish = page.get_by_role("button", name="发布视频", exact=True)
                await expect(publish).to_be_enabled()
                submitted = True
                result["status"] = "submission_unknown"
                result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                await publish.click()
                await expect(page.get_by_text("发布成功", exact=True)).to_be_visible(timeout=60000)  # "发布成功" = published
                result.update(success=True, status="published")
                result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                async with page.expect_popup() as detail_info:
                    await page.get_by_text("查看详情", exact=True).click()
                detail = await detail_info.value
                await detail.wait_for_url(re.compile(r"^https://www\.zhihu\.com/(?:pin|zvideo|video)/\d+"), timeout=60000)
                result["url"] = detail.url
                return result
            except Exception as exc:
                result["error"] = str(exc)
                if result["status"] != "published":
                    result["status"] = "submission_unknown" if submitted else "failed_before_submit"
                if submitted and page is not None and re.match(r"^https://www\.zhihu\.com/(?:pin|zvideo|video)/\d+", page.url):
                    result["url"] = page.url
                if self.debug and page is not None:
                    screenshot = result_file.with_suffix(".png")
                    await page.screenshot(path=str(screenshot))
                    result["screenshot"] = str(screenshot)
                if result["status"] == "published":
                    # The platform has confirmed publishing; keep the detail read error for the original-post lookup, do not return a retryable publish failure.
                    return result
                raise RuntimeError(f"Zhihu video stage={result['status']}, result file={result_file}: {exc}") from exc
            finally:
                result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                await browser.close()
