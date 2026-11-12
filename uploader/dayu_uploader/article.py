"""Dayu image post: body file, rich-text paste, local image upload and publish confirmation."""
from __future__ import annotations

import json
import math
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from patchright.async_api import Locator, Page, async_playwright, expect

from conf import LOCAL_CHROME_PATH
from uploader.dayu_uploader.article_content import load_dayu_article
from uploader.dayu_uploader.article_style import render_dayu_compatible_html
from uploader.dayu_uploader.constants import DAYU_SOURCE_REPRINT, DAYU_SOURCE_TYPES
from uploader.dayu_uploader.publication import submit_dayu_publication
from uploader.dayu_uploader.schedule import fill_dayu_schedule, validate_dayu_schedule
from uploader.dayu_uploader.session import load_dayu_identity, read_dayu_identity
from uploader.dayu_uploader.verification import check_dayu_article_content
from utils.log import dayu_logger

DAYU_ARTICLE_URL = "https://mp.dayu.com/dashboard/article/write"
DAYU_ARTICLE_COVER_MODES = {1: "单封面", 3: "三封面"}  # single cover / three covers
# Tested: the page also has a helper UEditor iframe; only scoping to the body editor and iframeholder points uniquely at the article body.
ARTICLE_BODY = ".article-write_box-editor .edui-editor-iframeholder iframe"


async def wait_dayu_article_body_stable(body: Locator) -> None:
    """Async cleanup after paste replaces container nodes; cache the image selection or check the final body only once it is stable."""
    deadline = time.monotonic() + 15
    previous = None
    stable = 0
    while time.monotonic() < deadline:
        current = await body.inner_html()
        stable = stable + 1 if current == previous else 0
        previous = current
        if stable >= 3:
            return
        await body.page.wait_for_timeout(1000)
    raise RuntimeError("The Dayu body keeps changing; the final edit result was not confirmed")


class DayuArticle:
    """The body is passed as a UTF-8 file; image order is the position of the img tags in the HTML."""

    def __init__(self, title, content_file, account_file, source, source_url="", author=None,
                 cover_indices=None, headless=True, debug=False, prepare_only=False,
                 upload_timeout=600, theme=None, schedule=None):
        self.title = title
        self.content_file = Path(content_file).expanduser().resolve()
        self.account_file = Path(account_file).resolve()
        self.source = source
        self.source_url = source_url
        self.author = author
        self.cover_indices = cover_indices or []
        self.headless = headless
        self.debug = debug
        self.prepare_only = prepare_only
        self.upload_timeout = upload_timeout
        self.theme = theme
        self.schedule = schedule

    def validate_upload_args(self):
        """Before touching remote assets, check the body format, cover indices and the conditionally required source fields."""
        self.schedule = validate_dayu_schedule(self.schedule)
        self.document = load_dayu_article(self.content_file, self.theme)
        title_length = math.ceil(sum(.5 if ord(char) <= 255 else 1 for char in self.title.strip()))
        if not 5 <= title_length <= 50:
            raise ValueError("Dayu image post title must be 5–50 characters (English characters count as half, rounded up)")
        if not self.account_file.is_file():
            raise FileNotFoundError("Run sau dayu login first to save the account")
        load_dayu_identity(self.account_file)
        if self.source not in DAYU_SOURCE_TYPES:
            raise ValueError(f"Information source must be one of: {', '.join(DAYU_SOURCE_TYPES)}")
        if self.source == DAYU_SOURCE_REPRINT:
            original = urlsplit(self.source_url)
            if original.scheme not in ("http", "https") or not original.hostname:
                raise ValueError("For a reprint (转载), --source-url must give the http/https link of the original")
        elif self.source_url:
            raise ValueError("--source-url may only be given when the information source is 转载 (reprint)")
        if self.author is not None:
            author_length = math.ceil(sum(.5 if ord(char) <= 255 else 1 for char in self.author.strip()))
            if not 1 <= author_length <= 10:
                raise ValueError("Author name must be 1–10 characters (English characters count as half, rounded up)")
        if self.cover_indices:
            if len(self.cover_indices) not in DAYU_ARTICLE_COVER_MODES:
                raise ValueError("--cover-indices needs 1 or 3 body image numbers, for a single cover or three covers")
            if any(index < 1 or index > len(self.document.images) for index in self.cover_indices):
                raise ValueError("Cover index is outside the range of body images; images are counted from 1")
            if len(set(self.cover_indices)) != len(self.cover_indices):
                raise ValueError("For three covers give different body image numbers")
        if self.upload_timeout <= 0:
            raise ValueError("The upload timeout must be greater than 0 seconds")

    async def fill_article_body(self, page: Page):
        """Import formatting through a native paste, then insert images at each image position with the platform uploader, keeping the editor metadata."""
        document = self.document
        insertions = []
        parts = []
        for part in document.parts:
            if isinstance(part, Path) or part == "<hr>":
                marker = f"SAU_ITEM_{uuid4().hex}"
                parts.append(marker)
                insertions.append((marker, part if isinstance(part, Path) else None))
            else:
                parts.append(part)
        # The platform turns section into span and puts figure inside p, so the image callback cannot find the image caption.
        # Both elements are layout containers in the theme; only change them to div, keeping the theme's inline styles and the body order.
        html = re.sub(r"<(\/?)(?:section|figure)(?=[\s>])", r"<\1div", "".join(parts), flags=re.I)
        await page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin="https://mp.dayu.com")
        await page.evaluate("""async html => navigator.clipboard.write([
            new ClipboardItem({'text/html': new Blob([html], {type: 'text/html'})})
        ])""", html)
        # The body is in a separate iframe whose editable body is the paste target; do not look for contenteditable in the main document.
        body = page.frame_locator(ARTICLE_BODY).locator("body[contenteditable=true]")
        await expect(body).to_have_count(1, timeout=30000)
        await body.click()
        shortcut = "Meta" if sys.platform == "darwin" else "Control"
        await body.press(f"{shortcut}+A")
        await body.press(f"{shortcut}+V")
        await expect(body).to_contain_text(next(text.strip()[:30] for text in document.text if text.strip()))
        # The theme has nested containers and the platform rebuilds nodes asynchronously after paste; selecting a marker too early breaks the image position.
        await page.locator("#title").click()
        await wait_dayu_article_body_stable(body)
        image_number = 0
        for marker, image_path in insertions:
            await expect(body).to_contain_text(marker)
            # Select the single image marker; keystrokes and mouseup refresh UEditor's selection cache so the toolbar replaces the right position.
            await body.evaluate("""(body, marker) => {
                body.focus(); const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
                let node;
                while (node = walker.nextNode()) {
                    const offset = node.textContent.indexOf(marker);
                    if (offset < 0) continue;
                    const range = document.createRange(); range.setStart(node, offset);
                    range.setEnd(node, offset + marker.length);
                    const selection = getSelection(); selection.removeAllRanges(); selection.addRange(range);
                    return;
                }
                throw Error('正文中未找到本次图片位置标记');
            }""", marker)
            await body.press("Shift")
            await body.dispatch_event("mouseup")
            if image_path is None:
                # Native paste filters out hr; use the page's own divider command to keep its publishing meaning.
                # The toolbar datatitle names the concrete action ("分隔线" = divider); no reliance on icon styles or button order.
                await page.locator('.edui-toolbar [datatitle="分隔线"]').click()
                await expect(body).not_to_contain_text(marker)
                continue
            # Find the insert-image tool by its action datatitle ("插入图片" = insert image); body and cover share one dialog, select only the visible instance.
            await page.locator('.edui-toolbar [datatitle="插入图片"]').click()
            dialog = page.locator(".article-material-image-dialog:visible")
            # The local upload input is created only after the dialog opens; scope to the current dialog to skip hidden uploaders such as the cover's.
            upload = dialog.locator('input[type="file"]')
            await expect(upload).to_have_count(1)
            await upload.set_input_files(str(image_path))
            # chosen is the selected-asset state of this upload; together with the file name and remote src it confirms the uploaded item.
            chosen = dialog.locator(".article-material-localImage_list_item_chosen")
            await expect(chosen).to_have_count(1, timeout=self.upload_timeout * 1000)
            await expect(chosen.locator("p")).to_have_text(image_path.name)
            await expect(chosen.locator("img")).to_have_attribute("src", re.compile(r"^https://mp\.dayu\.com/dayu/image\?"))
            await dialog.get_by_role("button", name="确认", exact=True).click()  # "确认" = Confirm
            await expect(dialog).to_have_count(0)
            await expect(body).not_to_contain_text(marker)
            image_number += 1
            await expect(body.locator("img")).to_have_count(image_number)
            # Images are inserted one by one in body order and the existing image count is asserted; the index is the body position of this insertion.
            await expect(body.locator("img").nth(image_number - 1)).to_have_attribute("data-infoed", "1")
            # After data-infoed the caption is still filled in asynchronously and the body cleaned; that cleanup removes an hr inserted too early.
            # Blur first and confirm this image is stable before handling the next divider/image; waiting only for image metadata is not enough.
            await page.locator("#title").click()
            await wait_dayu_article_body_stable(body)
            dayu_logger.info(f"Dayu body image {image_number}/{len(document.images)} inserted: {image_path.name}")
        # The page normalizes the body asynchronously; check only after blur and three identical read-backs in a row, so a transient DOM cannot report false success.
        # The title ID is a real form field outside the body; moving focus there does not submit or change the article body.
        await page.locator("#title").click()
        await wait_dayu_article_body_stable(body)
        # Check text and semantic formatting separately; a successful paste is no proof that the body is complete and styles were kept.
        await check_dayu_article_content(body, document.manifest)
        self.publication_html = None
        self.style_result = {"mode": "native"}
        if re.search(r'\sstyle="[^\"]+"', document.content_html):
            # Both the editor and the save API filter CSS; convert presentation attributes from the source, images reuse the metadata of this native upload.
            images = await body.locator("img").evaluate_all("images => images.map(image => image.outerHTML)")
            compatible = await render_dayu_compatible_html(page, document.content_html, images)
            self.publication_html = compatible["html"]
            document.manifest["dayu_style"] = compatible["expectations"]
            self.style_result = {"mode": compatible["mode"], "limitations": compatible["limitations"],
                                 "preview_checked": False}
        for index in range(len(document.images)):
            await expect(body.locator("img").nth(index)).to_have_js_property("complete", True)
            if await body.locator("img").nth(index).evaluate("e => e.naturalWidth") <= 0:
                raise RuntimeError(f"Body image {index + 1} cannot be loaded")

    async def fill_article_form(self, page: Page):
        """Fill in body, title, author and source and read each back; without an author the page value is kept."""
        await self.fill_article_body(page)
        # title and author are semantic IDs of form fields, so title and author text in the body is not mistaken for input controls.
        await page.locator("#title").fill(self.title)
        await expect(page.locator("#title")).to_have_value(self.title)
        if self.author is not None:
            await page.locator("#author input").fill(self.author)
            await expect(page.locator("#author input")).to_have_value(self.author)
        # Scope to the source component and choose by the radio's business value, so other radio groups or a changed option order do not interfere.
        source = page.locator(f'.article-write-source-remark input[value="{self.source}"]')
        # The page CSS stretches the transparent radio input to 240px, so the pointer center lands on the neighboring option; native keyboard selection is not affected.
        await source.focus()
        await source.press("Space")
        await expect(source).to_be_checked()
        # The conditional original-link field ("原文链接") has no semantic ID of its own; locate it via the field label and the input in the same container.
        original = page.locator(".article-write_box-form-filed").filter(
            has=page.locator("label").filter(has_text="原文链接"),
        ).locator('input[type="text"]')
        if self.source == DAYU_SOURCE_REPRINT:
            await original.fill(self.source_url)
            await expect(original).to_have_value(self.source_url)
        else:
            await expect(original).to_have_count(0)
        if self.cover_indices:
            mode = DAYU_ARTICLE_COVER_MODES[len(self.cover_indices)]
            # The cover mode is scoped to the landscape cover component and matched by option text, so it is not confused with the portrait cover or the source radio group.
            option = page.locator(".article-write-article-cover_normal-option").filter(has_text=mode)
            await option.locator(".w-radio").click()
            await expect(option.locator(".w-radio")).to_have_class(re.compile(r"w-radio_checked"))
            slots = page.locator(".article-write-article-cover_normal-item")
            await expect(slots).to_have_count(len(self.cover_indices))
            for slot_number, image_index in enumerate(self.cover_indices):
                # Slot order is the cover order the user gave; image order in the dialog is the body image order.
                await slots.nth(slot_number).locator(".article-write-article-cover-cover-item").click()
                dialog = page.locator(".article-material-image-dialog:visible")
                choices = dialog.locator(".article-material-image_image-choose img")
                await expect(choices).to_have_count(len(self.document.images))
                await choices.nth(image_index - 1).click()
                await expect(dialog.locator(".article-material-image_image-choose .chosen")).to_have_count(1)
                await dialog.get_by_role("button", name="下一步", exact=True).click()  # "下一步" = Next
                await expect(dialog.get_by_role("button", name="保存", exact=True)).to_be_visible()
                await dialog.get_by_role("button", name="保存", exact=True).click()  # "保存" = Save
                await expect(dialog).to_have_count(0, timeout=30000)
                preview = slots.nth(slot_number).locator("img")
                await expect(preview).to_have_count(1)
                await expect(preview).to_have_attribute("src", re.compile(r"^https?://image\.uc\.cn/"))
        await fill_dayu_schedule(page, self.schedule)

    async def main(self) -> dict:
        """Check the editor content and submit for publishing; success once the platform confirms this post's ID."""
        self.validate_upload_args()
        expected = load_dayu_identity(self.account_file)
        results_dir = self.account_file.parent / "dayu_results"
        results_dir.mkdir(exist_ok=True)
        result_file = results_dir / f"{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}.json"
        result = {"success": False, "status": "preparing", "type": "article", "title": self.title,
                  "content_file": str(self.content_file), "identity": expected,
                  "manifest": self.document.manifest, "result_file": str(result_file)}
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
                await page.goto(DAYU_ARTICLE_URL, wait_until="domcontentloaded", timeout=45000)
                identity = await read_dayu_identity(page)
                if identity["wmid"] != expected["wmid"]:
                    raise RuntimeError("Dayu identity does not match, image post upload aborted")
                result["identity"] = identity
                await self.fill_article_form(page)
                result.update(source_format=self.document.source_format, theme=self.document.theme,
                              style_check=self.style_result)
                if (await read_dayu_identity(page))["wmid"] != identity["wmid"]:
                    raise RuntimeError("The Dayu identity changed while the form was being filled in; refusing to publish")
                if self.prepare_only:
                    await page.screenshot(path=str(result_file.with_suffix(".png")), full_page=True)
                    result.update(success=True, status="prepared")
                    return result
                await submit_dayu_publication(page, result, result_file, article_html=self.publication_html)
                await context.storage_state(path=str(self.account_file))
                action = "定时发布已安排" if self.schedule else "发表成功"  # "scheduled publishing arranged" / "published"
                dayu_logger.success(f"Dayu image post {action}: {result['content_id']}")
                return result
            except Exception as exc:
                result["error"] = str(exc)
                dayu_logger.error(f"Dayu image post stage={result['status']}, result file={result_file}: {exc}")
                if self.debug and page is not None:
                    await page.screenshot(path=str(result_file.with_suffix(".png")))
                raise
            finally:
                result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                await browser.close()
