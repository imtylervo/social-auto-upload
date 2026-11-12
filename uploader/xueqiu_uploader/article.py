"""Xueqiu long post: structured source, images at their source positions, cover, preview and a single publish."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from patchright.async_api import Page, async_playwright, expect

from conf import LOCAL_CHROME_PATH
from uploader.xueqiu_uploader.constants import (
    XUEQIU_ARTICLE_URL, XUEQIU_DECLARATIONS, XUEQIU_IMAGE_SUFFIXES, XUEQIU_VISIBILITY,
)
from uploader.xueqiu_uploader.session import load_xueqiu_identity, read_xueqiu_identity
from uploader.xueqiu_uploader.content import load_xueqiu_article
from uploader.xueqiu_uploader.verification import check_xueqiu_article_content, query_xueqiu_article


class XueqiuArticle:
    """Keep the article structure through native paste and image upload; the server's confirmation is the publish result."""

    def __init__(self, title, content_file, account_file, visibility="公开",
                 declaration="不添加创作声明", prepare_only=False, headless=False, debug=False,
                 cover=None):
        self.title = title.strip()
        self.content_file = Path(content_file).expanduser().resolve()
        self.account_file = Path(account_file).resolve()
        self.visibility = visibility
        self.declaration = declaration
        self.prepare_only = prepare_only
        self.headless = headless
        self.debug = debug
        self.cover = Path(cover).expanduser().resolve() if cover else None

    def validate_upload_args(self):
        """All local parameters are checked before a remote draft is created; length limits not yet observed are not guessed."""
        if not self.title or "\n" in self.title or "\r" in self.title:
            raise ValueError("Xueqiu title must be a non-empty single line of text")
        self.document = load_xueqiu_article(self.content_file)
        if self.visibility not in XUEQIU_VISIBILITY:
            raise ValueError(f"Sharing scope must be one of: {', '.join(XUEQIU_VISIBILITY)}")
        if self.declaration not in XUEQIU_DECLARATIONS:
            raise ValueError(f"Creation declaration must be one of: {', '.join(XUEQIU_DECLARATIONS)}")
        for image in self.document.images + ([self.cover] if self.cover else []):
            if image.suffix.lower() not in XUEQIU_IMAGE_SUFFIXES:
                raise ValueError(f"Xueqiu supports these image types: {', '.join(XUEQIU_IMAGE_SUFFIXES)}")
            if not image.is_file():
                raise FileNotFoundError(f"Image not found: {image}")
            if image.stat().st_size == 0:
                raise ValueError(f"Image must not be empty: {image}")
        if not self.account_file.is_file():
            raise FileNotFoundError("Run sau xueqiu login first to save the account")
        self.identity = load_xueqiu_identity(self.account_file)

    async def fill_article_body(self, page, body):
        """Put a unique marker at each source image position; after the native upload check the full interleaved order of text and images."""
        parts = []
        insertions = []
        for part in self.document.parts:
            if isinstance(part, Path):
                marker = f"SAU_IMAGE_{uuid4().hex}"
                parts.append(marker)
                insertions.append((marker, part))
            else:
                parts.append(part)
        await page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin="https://mp.xueqiu.com")
        await page.evaluate("""async html => navigator.clipboard.write([
            new ClipboardItem({'text/html': new Blob([html], {type: 'text/html'})})
        ])""", "".join(parts))
        await body.click()
        await body.press("Meta+V" if sys.platform == "darwin" else "Control+V")
        # The title field is used to blur; wait until the final text of this run is actually in the model before selecting image markers.
        await page.get_by_placeholder("请输入标题", exact=True).click()  # "请输入标题" = enter a title
        for marker, _ in insertions:
            await expect(body).to_contain_text(marker)
        self.uploaded_images = []
        for index, (marker, image) in enumerate(insertions):
            # Select the unique marker in an actual text node of the body; use a native selection instead of rewriting the ProseMirror innerHTML.
            # Tested: after a Shift refresh this selection is replaced by the toolbar upload, and the following paragraphs stay in place.
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
                throw Error('找不到本次原稿图片位置标记');
            }""", marker)
            await body.press("Shift")
            # data-tip is the tested meaning of the upload action ("上传图片" = upload image); scoping to snb_toolbar excludes the separate cover input.
            async with page.expect_file_chooser() as chooser:
                await page.locator('#snb_toolbar [data-tip="上传图片"]').click()
            file_chooser = await chooser.value
            # The input keeps the old file; clear only the native value without dispatching an empty change, so the same file can appear at different source positions.
            await file_chooser.element.evaluate("input => { input.value = ''; }")
            await file_chooser.set_files(str(image))
            await expect(body).not_to_contain_text(marker)
            await expect(body.locator("img")).to_have_count(index + 1, timeout=60000)
            # Images are replaced one by one in source order and the count is asserted; a data/blob preview does not mean the server is done.
            inserted = body.locator("img").nth(index)
            await expect(inserted).to_have_attribute("src", re.compile(r"^(?:https:)?//xqimg\.imedao\.com/"), timeout=60000)
            await expect(inserted).to_have_js_property("complete", True, timeout=60000)
            if await inserted.evaluate("e => e.naturalWidth") <= 0:
                raise RuntimeError(f"Body image cannot be loaded: {image.name}")
            self.uploaded_images.append(await inserted.evaluate("e => e.src"))
        await page.get_by_placeholder("请输入标题", exact=True).click()
        await check_xueqiu_article_content(body, self.document)

    async def fill_article_form(self, page: Page):
        """Fill in the real fields, read back options and body, then check the preview and autosave separately."""
        # The title placeholder expresses the field's role; the body placeholder disappears after input, so use the editable node directly under the editor,
        # excluding the contenteditable=false tool containers inside uploaded images; the same locator is used before and after filling in.
        title = page.get_by_placeholder("请输入标题", exact=True)
        body = page.locator('#editor > [contenteditable="true"]')
        await expect(title).to_have_count(1)
        await expect(body).to_have_count(1)
        # A new task only writes into an empty editor; if the page restores an existing draft, the user's text is not overwritten.
        if (await title.input_value()).strip() or (await body.inner_text()).strip() or await body.locator("img").count():
            raise RuntimeError("The Xueqiu editor already has content; refusing to overwrite it. Deal with the existing draft first")
        await title.fill(self.title)
        await expect(title).to_have_value(self.title)
        await self.fill_article_body(page, body)
        self.cover_url = None
        if self.cover:
            # The cover field row is scoped by its label ("封面图片：" = cover image), and the input type expresses the upload purpose; not mixed up with the toolbar body uploader.
            cover_row = page.locator('div[class*="index_sectionFlex_"]').filter(
                has=page.get_by_text("封面图片：", exact=True),
            )
            await cover_row.locator('input[type="file"]').set_input_files(str(self.cover))
            # Tested: the cover must go through a separate crop dialog ("选择封面图片" = choose cover image); keep the default crop box, do not guess sizes or touch hidden state.
            crop = page.locator('div[class*="modal_modal-content_"]').filter(
                has=page.get_by_text("选择封面图片", exact=True),
            )
            await expect(crop).to_be_visible()
            await expect(crop.locator('img[alt="Crop"]')).to_have_js_property("complete", True)
            if await crop.locator('img[alt="Crop"]').evaluate("e => e.naturalWidth") <= 0:
                raise RuntimeError("The cover crop preview cannot be loaded")
            await crop.get_by_role("button", name="确认裁剪", exact=True).click()  # "确认裁剪" = confirm crop
            await expect(crop).to_have_count(0, timeout=60000)
            # Tested: a successful cover is shown as a background image and the original upload button is hidden; the fixed URL of the placeholder img cannot be checked.
            cover_preview = cover_row.locator('div[class*="index_input-cover-pic-btn_"]')
            await expect(cover_preview).to_have_attribute("style", re.compile(r".*xqimg\.imedao\.com/.*"), timeout=60000)
            self.cover_url = await cover_preview.evaluate(
                "e => new URL(getComputedStyle(e).backgroundImage.slice(5, -2), location.href).href")
        for label, value in (("分享范围：", self.visibility), ("创作声明：", self.declaration)):  # field labels: sharing scope, creation declaration
            # class keeps only the field row and component role prefixes; scoping to this row's label excludes the other dropdown of the same structure.
            row = page.locator('div[class*="index_sectionFlex_"]').filter(
                has=page.get_by_text(label, exact=True),
            )
            selected = row.locator('div[class*="index_selectWrap_"]')
            await selected.click()
            # optionContainer is the expanded option container; visible excludes the other menu that is not expanded now.
            option = row.locator('div[class*="index_optionContainer_"]:visible').get_by_text(value, exact=True)
            await expect(option).to_have_count(1)
            await option.click()
            await expect(selected).to_contain_text(value)
        # publish_state is a separate autosave status area; saving is not judged from same-named text in the body.
        await expect(page.locator('div[class*="publish_state_"]')).to_contain_text("已经保存至草稿", timeout=60000)  # "已经保存至草稿" = saved to drafts
        await page.get_by_role("button", name="预览", exact=True).click()  # "预览" = Preview
        # The business prefix of the preview container is stable in the tested DOM; h1 and content-text hold the preview title and body.
        preview = page.locator('div[class*="index_preview-content_"]')
        await expect(preview).to_be_visible()
        await expect(preview.locator("h1")).to_have_text(self.title)
        # The preview is filled in by an async server result; wait for this run's text first, not just for the empty preview shell to be visible.
        preview_body = preview.locator('div[class*="index_content-text_"] > div')
        await expect(preview_body).to_contain_text(next(text.strip() for text in self.document.text if text.strip()), timeout=30000)
        await check_xueqiu_article_content(preview_body, self.document)
        # The cover img directly under the preview content-text sits next to body images inside a direct div; check inserted images only in the latter.
        preview_images = preview.locator('div[class*="index_content-text_"] > div img')
        await expect(preview_images).to_have_count(len(self.uploaded_images))
        for index, source in enumerate(self.uploaded_images):
            # The platform preview adds https to // URLs; compare the parsed src and exclude wrong or reordered images in body order.
            await expect(preview_images.nth(index)).to_have_js_property("src", source)
            await expect(preview_images.nth(index)).to_have_js_property("complete", True)
            if await preview_images.nth(index).evaluate("e => e.naturalWidth") <= 0:
                raise RuntimeError(f"Body image {index + 1} in the preview cannot be loaded")
        if self.cover_url:
            # Tested: index_first-pic is the cover directly under the preview, separate from the body div; check this crop result.
            cover_image = preview.locator('div[class*="index_content-text_"] > img[class*="index_first-pic_"]')
            await expect(cover_image).to_have_js_property("src", self.cover_url)
            await expect(cover_image).to_have_js_property("complete", True)
            if await cover_image.evaluate("e => e.naturalWidth") <= 0:
                raise RuntimeError("The cover in the preview cannot be loaded")
        if (await read_xueqiu_identity(page))["uid"] != self.identity["uid"]:
            raise RuntimeError("The Xueqiu account changed while filling in the form; aborted")

    async def main(self) -> dict:
        """Prepare mode keeps the draft and preview; submit mode clicks only once, and automatic republishing is forbidden when the result is unknown."""
        self.validate_upload_args()
        results_dir = self.account_file.parent / "xueqiu_results"
        results_dir.mkdir(exist_ok=True)
        result_file = results_dir / f"{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}.json"
        result = {"success": False, "status": "preparing", "title": self.title,
                  "content_file": str(self.content_file),
                  "identity": self.identity, "visibility": self.visibility, "declaration": self.declaration,
                  "result_file": str(result_file), "remote_draft_possible": False}
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                executable_path=LOCAL_CHROME_PATH or None, channel="chrome", headless=self.headless,
            )
            page = None
            try:
                context = await browser.new_context(storage_state=str(self.account_file))
                page = await context.new_page()
                response = await page.goto(XUEQIU_ARTICLE_URL, wait_until="domcontentloaded", timeout=45000)
                if response is not None and response.status >= 400:
                    raise RuntimeError(f"Failed to open the Xueqiu editor, HTTP {response.status}")
                if (await read_xueqiu_identity(page))["uid"] != self.identity["uid"]:
                    raise RuntimeError("The Xueqiu identity does not match the bound account")
                result["remote_draft_possible"] = True
                await self.fill_article_form(page)
                result.update(images=self.uploaded_images, cover=self.cover_url,
                              source_format=self.document.source_format, normalizations=self.document.normalizations,
                              manifest=self.document.manifest)
                await page.screenshot(path=str(result_file.with_suffix(".png")), full_page=True)
                result["screenshot"] = str(result_file.with_suffix(".png"))
                if self.prepare_only:
                    result.update(success=True, status="prepared", url=page.url)
                    return result
                # index_preview_ is the preview overlay and its direct child index_close_ is the tested close control; the overlay is not removed and no click is forced.
                await page.locator('div[class*="index_preview_"] > div[class*="index_close_"]').click()
                # After closing, the component stays in the DOM and is hidden by its parent; the node cannot be required to be removed.
                await expect(page.locator('div[class*="index_preview-content_"]')).to_be_hidden()
                publish = page.get_by_role("button", name="发布", exact=True)  # "发布" = Publish
                # The page expresses the disabled state with a class, so HTML disabled alone cannot be relied on; keep the semantic prefix to ignore hash changes.
                await expect(publish).not_to_have_class(re.compile(r".*publish_disabled_.*"), timeout=30000)
                result.update(status="submission_unknown", editor_url=page.url)
                result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                # Tested: the final publish POST /xq/statuses/update.json returns the post ID, user_id, title, text and is_private.
                # The page then returns to the home page, so the wrong assumption "it jumps to the author's detail page" cannot be used to judge success.
                async with page.expect_response(lambda response: response.request.method == "POST"
                                                and response.url == "https://mp.xueqiu.com/xq/statuses/update.json",
                                                timeout=60000) as submitted:
                    await publish.click()
                response = await submitted.value
                payload = await response.json()
                content_id = payload.get("id")
                if not response.ok or not isinstance(content_id, int) or isinstance(content_id, bool) or content_id <= 0:
                    raise RuntimeError(f"Xueqiu did not confirm acceptance: HTTP {response.status}, {payload.get('error_description', payload.get('error_code', '缺少作品 ID'))}")
                # Persist the returned ID first; even if a later content check fails, only the original post may be looked up, republishing is forbidden.
                result["content_id"] = str(content_id)
                result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                if str(payload.get("user_id")) != self.identity["uid"] or payload.get("title") != self.title:
                    raise RuntimeError("The identity or title of the post Xueqiu accepted does not match; check the original post")
                if payload.get("is_private") is not (self.visibility == "私人"):
                    raise RuntimeError("The sharing scope of the post Xueqiu accepted does not match; check the original post")
                # Check on a separate page built from the published body the platform returned; the editor model is not rewritten and no real publish action is added.
                check_page = await context.new_page()
                await check_page.set_content(payload.get("text") or "")
                await check_xueqiu_article_content(check_page.locator("body"), self.document, self.uploaded_images)
                result.update(success=True, status="published",
                              url=f"https://xueqiu.com/{self.identity['uid']}/{content_id}")
                result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                # The publish response confirmed acceptance; then look up the published original ID, and verification must not trigger a second submission.
                record = await query_xueqiu_article(page, self.identity, content_id, self.title, self.visibility)
                await check_page.set_content(record.get("text") or "")
                await check_xueqiu_article_content(check_page.locator("body"), self.document, self.uploaded_images)
                await check_page.close()
                result["management_verified"] = True
                await page.screenshot(path=str(result_file.with_suffix(".published.png")), full_page=True)
                result["published_screenshot"] = str(result_file.with_suffix(".published.png"))
                await context.storage_state(path=str(self.account_file))
                return result
            except Exception as exc:
                result["error"] = str(exc)
                if result["status"] == "preparing":
                    result["status"] = "failed"
                if self.debug and page is not None:
                    await page.screenshot(path=str(result_file.with_suffix(".error.png")), full_page=True)
                raise
            finally:
                result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"Xueqiu operation result: {result_file}", flush=True)
                await browser.close()
