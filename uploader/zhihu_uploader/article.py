"""Zhihu article publishing: body text, body images, scheduling and submission result recording."""
from __future__ import annotations

import base64
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from patchright.async_api import Page, async_playwright, expect

from conf import LOCAL_CHROME_PATH
from utils.article_render import load_article, ARTICLE_MARKDOWN_EXTENSIONS
from uploader.zhihu_uploader.constants import (
    ZHIHU_ARTICLE_TITLE_MAX, ZHIHU_ARTICLE_URL, ZHIHU_IMAGE_EXTENSIONS, ZHIHU_TIMEZONE,
)
from uploader.zhihu_uploader.schedule import fill_zhihu_article_schedule, validate_zhihu_schedule
from uploader.zhihu_uploader.session import load_zhihu_identity, read_zhihu_identity


class ZhihuArticle:
    """Import the body following the source structure, upload images at their source positions, check, then publish only once."""

    def __init__(self, title, content_file, account_file, schedule=None,
                 headless=True, debug=False, prepare_only=False, upload_timeout=600):
        self.title = title
        self.content_file = Path(content_file).expanduser().resolve()
        self.account_file = Path(account_file).resolve()
        self.schedule = schedule
        self.headless = headless
        self.debug = debug
        self.prepare_only = prepare_only
        self.upload_timeout = upload_timeout

    def validate_upload_args(self) -> None:
        """Check the title, body, images and schedule before starting the browser."""
        if not self.title.strip() or len(self.title) > ZHIHU_ARTICLE_TITLE_MAX:
            raise ValueError(f"Zhihu article title must be 1–{ZHIHU_ARTICLE_TITLE_MAX} characters")
        self.document = load_article(
            self.content_file, "plain" if self.content_file.suffix.lower() in ARTICLE_MARKDOWN_EXTENSIONS else None,
        )
        self.images = self.document.images
        if not "".join(self.document.text).strip():
            raise ValueError("Zhihu article body must not be empty")
        if not self.account_file.is_file():
            raise FileNotFoundError("Run sau zhihu login first to save the account")
        self.identity = load_zhihu_identity(self.account_file)
        self.schedule = validate_zhihu_schedule(self.schedule)
        if self.upload_timeout <= 0:
            raise ValueError("The upload timeout must be greater than 0 seconds")
        for image in self.images:
            if not image.is_file():
                raise FileNotFoundError(f"Zhihu body image not found: {image}")
            if image.suffix.lower() not in ZHIHU_IMAGE_EXTENSIONS:
                raise ValueError(f"Zhihu article image format not supported: {image.suffix}")

    async def fill_article_form(self, page: Page) -> None:
        """Import rich text through a native paste; upload images at their source positions and check the interleaved order."""
        # The title placeholder comes from the article form's actual textarea, so the body and the search box are not filled by mistake.
        title = page.locator('textarea[placeholder="请输入标题（最多 100 个字）"]')
        await expect(title).to_have_count(1)
        body = page.locator('div[contenteditable="true"][role="textbox"]')
        await expect(body).to_have_count(1)
        # The Zhihu editor autosaves; a new task only writes into an empty editor, so an old draft restored in the account is not overwritten.
        if ((await title.input_value()).strip() or (await body.inner_text()).strip()
                or await body.locator("img").count()):
            raise RuntimeError("The Zhihu article editor already holds a draft; refusing to overwrite it. Deal with that draft first")
        await title.fill(self.title)
        await expect(title).to_have_value(self.title)
        # Do not rewrite the DraftJS innerHTML; a native HTML paste lets the editor update its own internal model.
        # Images are first replaced by unique markers, so local paths are not pasted as remote images that cannot load.
        parts, insertions = [], []
        for part in self.document.parts:
            if isinstance(part, Path):
                marker = f"SAU_IMAGE_{uuid4().hex}"
                parts.append(marker)
                insertions.append((marker, part))
            else:
                parts.append(part)
        await page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin="https://zhuanlan.zhihu.com")
        await page.evaluate("""async html => navigator.clipboard.write([
            new ClipboardItem({'text/html': new Blob([html], {type: 'text/html'})})
        ])""", "".join(parts))
        await body.click()
        await body.press("Meta+V" if sys.platform == "darwin" else "Control+V")
        await title.click()
        for marker, _ in insertions:
            await expect(body).to_contain_text(marker)
        self.uploaded_images = []
        for index, (marker, image) in enumerate(insertions, 1):
            # The unique marker in a text node fixes the source image position; the default cursor position after clicking the body cannot stand in for it.
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
                throw Error('找不到原稿图片位置标记');
            }""", marker)
            await body.press("Shift")
            await body.press("Backspace")
            await expect(body).not_to_contain_text(marker)
            # Tested: the current article editor supports pasting images from the clipboard, while the image button first opens the asset panel.
            # Paste at the confirmed source cursor position and let DraftJS create the image block and start the upload itself.
            # The browser ClipboardItem supports PNG; other formats keep using the native file input.
            if image.suffix.lower() == ".png":
                await page.evaluate("""async encoded => {
                    const bytes = Uint8Array.from(atob(encoded), c => c.charCodeAt(0));
                    await navigator.clipboard.write([
                        new ClipboardItem({'image/png': new Blob([bytes], {type: 'image/png'})})
                    ]);
                }""", base64.b64encode(image.read_bytes()).decode("ascii"))
                await body.press("Meta+V" if sys.platform == "darwin" else "Control+V")
            else:
                # accept/multiple exclude the cover and document-import inputs; the non-PNG path still awaits verification with a real upload.
                image_input = page.locator('input[type="file"][accept^="image/webp"][multiple]')
                await expect(image_input).to_have_count(1)
                await image_input.evaluate("input => { input.value = ''; }")
                await image_input.set_input_files(str(image))
            await expect(body.locator("img")).to_have_count(index, timeout=self.upload_timeout * 1000)
            # The image count is already asserted; check the server URLs and actual decode state in the order the images were inserted one by one.
            inserted = body.locator("img").nth(index - 1)
            await expect(inserted).to_have_attribute("src", re.compile(r"^https://"), timeout=self.upload_timeout * 1000)
            await expect(inserted).to_have_js_property("complete", True, timeout=self.upload_timeout * 1000)
            if await inserted.evaluate("image => image.naturalWidth") <= 0:
                raise RuntimeError(f"Image {index} in the Zhihu article cannot be loaded")
            self.uploaded_images.append(await inserted.get_attribute("src"))
        await title.click()
        sources = await body.locator("img").evaluate_all("images => images.map(image => image.getAttribute('src'))")
        if sources != self.uploaded_images:
            raise RuntimeError("Zhihu article images were reordered or replaced; stopping the submission")
        await self.check_article_body(body)

        await fill_zhihu_article_schedule(page, self.schedule)

    async def check_article_body(self, body) -> None:
        """Check all text, image positions between paragraphs and basic formatting; abort the submission if the platform filtered or reordered anything."""
        # Tested: Zhihu DraftJS writes inline bold/italic as styled spans, so counting strong/em tags is not enough.
        actual = await body.evaluate(r"""body => {
            let sequence = '';
            function visit(node) {
                if (node.nodeType === Node.TEXT_NODE) { sequence += node.nodeValue; return; }
                if (node.nodeName === 'IMG') { sequence += '\x00IMG\x00'; return; }
                node.childNodes.forEach(visit);
            }
            visit(body);
            return {sequence, formats: Object.fromEntries(
                ['h1','h2','h3','h4','h5','h6','strong','em','ul','ol','blockquote','pre'].map(
                    tag => [tag, tag === 'strong'
                        ? body.querySelectorAll('strong,b,span[style*="font-weight: bold"],span[style*="font-weight: 700"]').length
                        : tag === 'em' ? body.querySelectorAll('em,i,span[style*="font-style: italic"]').length
                        : body.querySelectorAll(tag).length]
                )), links: [...body.querySelectorAll('a')].map(a => [a.textContent, a.getAttribute('href')])};
        }""")
        normalize = lambda text: re.sub(r"[\s\u200b\ufeff]+", "", text)
        if normalize(actual["sequence"]) != normalize("".join(self.document.sequence)):
            raise RuntimeError("Zhihu article text or image positions between paragraphs do not match the source; stopping the submission")
        for tag, count in actual["formats"].items():
            if count != self.document.tags[tag]:
                raise RuntimeError(f"Zhihu article formatting does not match: {tag} expected {self.document.tags[tag]}, got {count}")
        expected_links = await body.page.evaluate("""html => {
            const template = document.createElement('template'); template.innerHTML = html;
            return [...template.content.querySelectorAll('a')].map(a => [a.textContent, a.getAttribute('href')]);
        }""", self.document.content_html)
        if [[normalize(text), href] for text, href in actual["links"]] != [[normalize(text), href] for text, href in expected_links]:
            raise RuntimeError("Zhihu article link text or target does not match the source")

    async def main(self) -> dict:
        """Only the post detail URL counts as proof of publishing; automatic retries are forbidden when the submit response is unknown."""
        self.validate_upload_args()
        results_dir = self.account_file.parent / "zhihu_results"
        results_dir.mkdir(exist_ok=True)
        result_file = results_dir / f"{datetime.now(ZHIHU_TIMEZONE):%Y%m%d-%H%M%S}-{uuid4().hex[:8]}.json"
        result = {
            "success": False, "status": "preparing", "type": "article", "title": self.title,
            "content_file": str(self.content_file), "images": [str(image) for image in self.images],
            "identity": self.identity, "result_file": str(result_file),
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
                response = await page.goto(ZHIHU_ARTICLE_URL, wait_until="domcontentloaded", timeout=45000)
                if response is not None and response.status >= 400:
                    raise RuntimeError(f"Failed to open the Zhihu article editor, HTTP {response.status}")
                if await read_zhihu_identity(page) != self.identity:
                    raise RuntimeError("The Zhihu article editor header does not match the local account binding")
                await self.fill_article_form(page)
                result.update(images=self.uploaded_images, manifest=self.document.manifest)
                result["status"] = "prepared"
                result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                if self.prepare_only:
                    return result

                # The publish button is enabled only once title and body meet the editor's requirements; submission is triggered only once.
                publish = page.get_by_role("button", name="发布", exact=True)  # "发布" = Publish
                await expect(publish).to_be_enabled()
                submitted = True
                result["status"] = "submission_unknown"
                result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                await publish.click()
                # Drafts also have a /p/<id>/edit URL; it counts as published only on the real detail page with the post title read back.
                await page.wait_for_url(re.compile(r"^https://zhuanlan\.zhihu\.com/p/\d+/?(?:\?.*)?$"), timeout=60000)
                await expect(page.get_by_role("article").get_by_role("heading", name=self.title, exact=True)).to_be_visible()
                result.update(success=True, status="published", url=page.url)
                return result
            except Exception as exc:
                result["error"] = str(exc)
                if submitted:
                    result["status"] = "submission_unknown"
                    if page is not None and re.fullmatch(r"https://zhuanlan\.zhihu\.com/p/\d+/?(?:\?.*)?", page.url):
                        result["url"] = page.url
                else:
                    result["status"] = "failed_before_submit"
                if self.debug and page is not None:
                    screenshot = result_file.with_suffix(".png")
                    await page.screenshot(path=str(screenshot))
                    result["screenshot"] = str(screenshot)
                raise RuntimeError(f"Zhihu article stage={result['status']}, result file={result_file}: {exc}") from exc
            finally:
                result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                await browser.close()
