"""Instagram standalone website session, and publishing of photos, carousels and Reels."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from patchright.async_api import Locator, Page, Playwright, TimeoutError as BrowserTimeoutError, async_playwright, expect

INSTAGRAM_HOME_URL = "https://www.instagram.com/"
# Without the environment variable or --proxy, connect directly through the system.
INSTAGRAM_PROXY = os.environ.get("SAU_INSTAGRAM_PROXY")
# The create dialog's real accept covers both photos and MP4; this attribute pins the media input and excludes the cover input of the edit step.
INSTAGRAM_MEDIA_INPUT = 'input[type="file"][accept*="video/mp4"]'
# _ac76 is the wizard title bar shared by the crop, edit and caption steps (observed in Chinese and English); the main action has no SVG, the back button does.
INSTAGRAM_PRIMARY_ACTION = '._ac76 [role="button"]:not(:has(svg))'


async def _dismiss_optional_prompt(guide: Locator, dismiss_button: Locator) -> bool:
    """Close only recognised optional prompts. If one is absent, carry on; if it appears and closing it fails, raise."""
    try:
        await guide.wait_for(state='visible', timeout=1500)
    except BrowserTimeoutError:
        return False
    await expect(dismiss_button).to_have_count(1)
    await dismiss_button.click()
    await guide.wait_for(state='hidden')
    return True


def _proxy_options(proxy: str | None) -> dict[str, str] | None:
    """Without an argument, use the explicit environment setting, else connect directly; an empty string overrides the environment and connects directly."""
    address = (INSTAGRAM_PROXY if proxy is None else proxy) or ""
    address = address.strip()
    return {"server": address} if address else None


async def _open_instagram_page(playwright: Playwright, account_file: Path, *, proxy: str | None, headless: bool):
    """Use the project's Chrome and the given storage state; if navigation fails, keep the original exception."""
    browser = await playwright.chromium.launch(channel="chrome", headless=headless, proxy=_proxy_options(proxy))
    try:
        context = await browser.new_context(storage_state=str(account_file))
        page = await context.new_page()
        page.set_default_timeout(30_000)
        await page.goto(INSTAGRAM_HOME_URL, wait_until="domcontentloaded", timeout=120_000)
        return browser, context, page
    except Exception:
        await browser.close()
        raise


async def _is_instagram_logged_out(page: Page) -> bool:
    """Wait for an area that clearly shows logged in or logged out; a timeout from the network or an unknown page does not mean the cookie is invalid."""
    # The messages link is logged-in navigation, and the href prefix lets the site append an hl parameter; the login form fields do not depend on translation.
    outcomes = page.locator('a[href^="/direct/inbox/"], input[name="username"], a[href^="/accounts/login/"]')
    await expect(outcomes).not_to_have_count(0, timeout=60_000)
    return not await page.locator('a[href^="/direct/inbox/"]').count()


async def instagram_identity(page: Page, account_file: Path) -> dict:
    """Compare the session's user ID with the ID bound to the account file, and read your own profile link from the navigation."""
    if await _is_instagram_logged_out(page):
        raise RuntimeError("Not logged in to Instagram; run sau instagram login")
    state = json.loads(account_file.read_text(encoding="utf-8"))
    expected = {c['value'] for c in state['cookies'] if c['name'] == 'ds_user_id' and c['domain'].lstrip('.') == 'instagram.com'}
    current = {c['value'] for c in await page.context.cookies(INSTAGRAM_HOME_URL) if c['name'] == 'ds_user_id'}
    if len(expected) != 1 or current != expected:
        raise RuntimeError("The logged-in Instagram user does not match the user ID bound to the account file")
    # The current user's navigation avatar sits in an aria-selected icon container; avatars in the feed and recommendations have no navigation selected state.
    own_profile = page.locator('a[href]').filter(has=page.locator('[aria-selected] img'))
    await expect(own_profile).to_have_count(1)
    href = await own_profile.get_attribute('href')
    username = urlparse(href).path.strip('/')
    if not username or '/' in username:
        raise RuntimeError("Instagram: the current user's profile link has an unexpected structure")
    return {"user_id": next(iter(expected)), "username": username}


async def instagram_cookie_auth(account_file: str | Path, *, proxy: str | None = None) -> bool:
    """Check login and the account binding on their own; unknown pages and network errors are raised as is."""
    account_file = Path(account_file)
    if not account_file.is_file():
        return False
    async with async_playwright() as playwright:
        browser, context, page = await _open_instagram_page(playwright, account_file, proxy=proxy, headless=True)
        try:
            if await _is_instagram_logged_out(page):
                return False
            await instagram_identity(page, account_file)
            return True
        finally:
            await browser.close()


async def instagram_setup(account_file: str | Path, *, handle: bool = False, proxy: str | None = None,
                          headless: bool = False, return_detail: bool = False, timeout_seconds: int = 900):
    """Log in by hand in the project browser, export a candidate state, and replace the account file only after it passes in a new context."""
    account_file = Path(account_file)
    account_file.parent.mkdir(parents=True, exist_ok=True)
    if await instagram_cookie_auth(account_file, proxy=proxy):
        result = {"success": True, "status": "cookie_valid", "account_file": str(account_file)}
        return result if return_detail else True
    if not handle:
        result = {"success": False, "status": "cookie_invalid", "account_file": str(account_file)}
        return result if return_detail else False
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=headless, proxy=_proxy_options(proxy), args=["--start-maximized"])
        candidate = account_file.with_name(f'{account_file.stem}.{uuid4().hex}.pending.json')
        try:
            context = await browser.new_context(no_viewport=not headless)
            page = await context.new_page()
            await page.goto(INSTAGRAM_HOME_URL + 'accounts/login/', wait_until='domcontentloaded', timeout=120_000)
            # The messages link appears only after the manual login and any challenge are done; success is not declared from the URL or from the login form disappearing.
            await page.locator('a[href^="/direct/inbox/"]').wait_for(state='visible', timeout=timeout_seconds * 1000)
            await context.storage_state(path=str(candidate))
            if not await instagram_cookie_auth(candidate, proxy=proxy):
                raise RuntimeError('The exported Instagram candidate state failed verification in a new session')
            candidate.replace(account_file)
            result = {"success": True, "status": "logged_in", "account_file": str(account_file)}
            return result if return_detail else True
        finally:
            candidate.unlink(missing_ok=True)
            await browser.close()


def instagram_response_payload(body: str) -> dict:
    """Parse the plain JSON seen so far and Meta's anti-JSON-hijacking prefix; any other format raises."""
    if body.startswith('for (;;);'):
        body = body[len('for (;;);'):]
    return json.loads(body)


def instagram_created_media(payload: dict, *, owner_id: str, caption: str) -> dict:
    """Accept only a post in the final create response that matches the user and caption; "processing" and HTTP 200 alone are not success."""
    envelope = payload
    payload = envelope.get('payload', envelope)
    if envelope.get('error') or payload.get('status') not in (None, 'ok') or ('statusCode' in payload and payload['statusCode'] != 200):
        raise RuntimeError(f"Instagram create did not succeed: {payload.get('message', payload.get('statusCode', payload.get('status')))}")
    media = payload.get('media') or {}
    if not media.get('code') or not media.get('id'):
        raise RuntimeError('Instagram create response is missing the post ID')
    if str((media.get('user') or {}).get('pk')) != owner_id:
        raise RuntimeError('Instagram create response has a non-matching author ID')
    if (media.get('caption') or {}).get('text') != caption:
        raise RuntimeError('Instagram create response has a non-matching caption')
    return media


class InstagramUploader:
    """Publish immediately on the standalone website; return the post link once the final create response confirms success."""

    def __init__(self, account_file: str | Path, *, title: str, description: str = '', tags: list[str] | None = None,
                 video_file: str | Path | None = None, image_files: list[str | Path] | None = None,
                 thumbnail: str | Path | None = None,
                 proxy: str | None = None, headless: bool = False, result_file: str | Path | None = None):
        self.account_file = Path(account_file)
        self.title, self.description = title.strip(), description.strip()
        self.tags = [t.strip().lstrip('#') for t in (tags or []) if t.strip().lstrip('#')]
        self.video_file = Path(video_file) if video_file else None
        self.image_files = [Path(p) for p in (image_files or [])]
        self.thumbnail = Path(thumbnail) if thumbnail else None
        if self.thumbnail and not self.video_file:
            raise ValueError('An Instagram custom cover only applies to a video/Reel')
        if bool(self.video_file) == bool(self.image_files):
            raise ValueError('Pass either a video or image files, not both and not neither')
        if not self.title:
            raise ValueError('Title must not be empty')
        self.proxy, self.headless = proxy, headless
        self.result_file = Path(result_file) if result_file else Path('.local/instagram-results') / f'{uuid4().hex}.json'
        self.result = {'platform': 'instagram', 'title': self.title, 'status': 'not_submitted'}
        self.stage = 'validation'
        if len(self._caption()) > 2200:
            raise ValueError('The Instagram caption (title, text and tags together) must not exceed 2200 characters')

    def _caption(self) -> str:
        """Instagram only has a caption, so merge the CLI title, text and tags into it."""
        parts = [p for p in (self.title, self.description) if p]
        if self.tags:
            parts.append(' '.join(f'#{t}' for t in self.tags))
        return '\n\n'.join(parts)

    async def _upload_files(self, page: Page) -> None:
        """Open the create entry and wait for the crop step to be ready; never assume completion from a fixed delay after upload."""
        # The real notifications prompt uses this fixed icon and the _a9-z action area. Its two items are, in order, Turn on and Not now;
        # take the second direct child button. Limiting to the icon and local action area avoids clicking by translated text or a page-wide button.
        notifications = page.get_by_role('dialog').filter(
            has=page.locator('img[src^="/images/instagram/xig/ico/xxhdpi_launcher.png"]'))
        notification_buttons = notifications.locator('._a9-z > button')
        # These four navigation popup entries were seen on both the Chinese and English home pages, in order Notifications, Create, Settings, Meta.
        # First assert the full group and that each entry has an aria-selected icon, then take the second item in that order, instead of an arbitrary page-wide nth.
        navigation_popups = page.locator('a._a6hd[href="#"]').filter(has=page.locator('[aria-selected]'))
        # In testing, the notifications prompt can appear after the navigation. Handle this known overlay during the action check, to avoid the race of checking it is absent
        # and having it pop up at click time; when there is no prompt the callback does not run, and no fixed wait is added.
        await page.add_locator_handler(notifications, lambda: _dismiss_optional_prompt(notifications, notification_buttons.nth(1)))
        try:
            await expect(navigation_popups).to_have_count(4)
            await navigation_popups.nth(1).click()
        finally:
            await page.remove_locator_handler(notifications)
        dialog = page.get_by_role('dialog')
        await expect(dialog).to_have_count(1)
        file_input = dialog.locator(INSTAGRAM_MEDIA_INPUT)
        await expect(file_input).to_have_count(1)
        paths = [self.video_file] if self.video_file else self.image_files
        await file_input.set_input_files([str(p.resolve()) for p in paths])
        if self.video_file:
            # The real Reels intro uses reels_nux_icon; in its action area "Learn more" sits in a span,
            # while the confirm button sits directly in a div. Tell them apart by local parent/child structure, not by language or style hashes.
            reels_intro = page.get_by_role('dialog').filter(
                has=page.locator('img[src^="/images/instagram/clips/reels_nux_icon.png"]'))
            await _dismiss_optional_prompt(reels_intro, reels_intro.locator('._a9-z div > button'))
        # Advance only once the crop title bar's main action actually appears; an upload failure or an unknown blocking dialog keeps the page as is and raises.
        await expect(dialog.locator(INSTAGRAM_PRIMARY_ACTION)).to_have_count(1, timeout=60_000)

    async def _advance_media_editor(self, page: Page) -> None:
        """For the crop and edit steps, wait for the title to change each time; finally confirm with the Lexical caption box."""
        # The same create dialog title bar exists in all three steps; the local main action has no icon, which excludes the back and media tool buttons.
        dialog = page.get_by_role('dialog')
        heading = dialog.locator('._ac76 [role="heading"]')
        for step in range(2):
            if step == 1 and self.thumbnail:
                # In the real video edit dialog, the exact JPEG/PNG accept is the separate cover input, which excludes the initial video input.
                cover = dialog.locator('input[type="file"][accept="image/jpeg,image/png"]')
                # The main preview video sits right next to the cover background layer; the frame strip on the right also has background images, so do not use it to verify the cover.
                poster = dialog.locator('video + div[style*="background-image"]')
                await expect(cover).to_have_count(1)
                await expect(poster).to_have_count(1)
                previous_style = await poster.get_attribute('style')
                await cover.set_input_files(str(self.thumbnail.resolve()))
                await expect(poster).not_to_have_attribute('style', previous_style, timeout=30_000)
                # The page was seen to replace the cover with a blob of the original image. Check and decode the actual preview bytes; selecting the file alone does not mean it took effect.
                preview = await asyncio.wait_for(poster.evaluate('''async element => {
                    const background = getComputedStyle(element).backgroundImage;
                    const url = background.slice(5, -2);
                    const blob = await (await fetch(url)).blob();
                    const bitmap = await createImageBitmap(blob);
                    const digest = await crypto.subtle.digest('SHA-256', await blob.arrayBuffer());
                    const result = {width: bitmap.width, height: bitmap.height,
                        sha256: Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, '0')).join('')};
                    bitmap.close();
                    return result;
                }'''), timeout=30)
                if not preview['width'] or not preview['height'] or preview['sha256'] != hashlib.sha256(self.thumbnail.read_bytes()).hexdigest():
                    raise RuntimeError('Instagram cover main preview does not match the given image')
            await expect(heading).to_have_count(1)
            previous = await heading.inner_text()
            action = dialog.locator(INSTAGRAM_PRIMARY_ACTION)
            await expect(action).to_have_count(1)
            await expect(action).to_be_enabled()
            await action.click()
            await expect(heading).not_to_have_text(previous, timeout=60_000)
        # data-lexical-editor marks the real caption editor; limiting it to the current create dialog excludes comment boxes.
        await expect(dialog.locator('[contenteditable="true"][role="textbox"][data-lexical-editor="true"]')).to_have_count(1)

    async def _publish(self, page: Page, identity: dict) -> None:
        """Register the listener for the final response before sharing; if the response is unclear, record unknown and do not repost."""
        # Only the caption step has the Lexical editor; the title bar's single main action is then Share, so no translated button name is used.
        dialog = page.get_by_role('dialog')
        editor = dialog.locator('[contenteditable="true"][role="textbox"][data-lexical-editor="true"]')
        caption = self._caption()
        await editor.fill(caption)
        await expect(editor).to_have_text(caption)
        action = dialog.locator(INSTAGRAM_PRIMARY_ACTION)
        await expect(action).to_have_count(1)
        await expect(action).to_be_enabled()
        self.result.update(identity, status='submission_unknown')
        self.result_file.parent.mkdir(parents=True, exist_ok=True)
        self.result_file.write_text(json.dumps(self.result, ensure_ascii=False, indent=2), encoding='utf-8')
        # For a Reel the first response is 202; the browser keeps calling the same create endpoint, and the real media comes back later.
        # Install a queue listener before submitting and keep consuming this create's responses; click only once, and never treat the upload response or a 202 as published.
        responses = asyncio.Queue()
        def on_response(response):
            if response.request.method == 'POST' and urlparse(response.url).path.startswith('/api/v1/media/configure'):
                responses.put_nowait(response)
        page.on('response', on_response)
        try:
            await action.click()
            deadline = asyncio.get_running_loop().time() + 180
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise TimeoutError('Instagram post submitted, but waiting for the final create response timed out')
                response = await asyncio.wait_for(responses.get(), timeout=remaining)
                remaining = deadline - asyncio.get_running_loop().time()
                payload = instagram_response_payload(await asyncio.wait_for(response.text(), timeout=max(remaining, 0)))
                body = payload.get('payload', payload)
                if body.get('statusCode') == 202:
                    self.result['status'] = 'processing'
                    self.result_file.write_text(json.dumps(self.result, ensure_ascii=False, indent=2), encoding='utf-8')
                    continue
                media = instagram_created_media(payload, owner_id=identity['user_id'], caption=caption)
                break
        finally:
            page.remove_listener('response', on_response)
        kind = 'reel' if self.video_file else 'p'
        self.result.update(status='published', content_id=media['id'], post_id=media['code'],
                           post_url=f"{INSTAGRAM_HOME_URL}{kind}/{media['code']}/", schedule=None,
                           media_count=len(media.get('carousel_media') or [media]))
        self.result_file.write_text(json.dumps(self.result, ensure_ascii=False, indent=2), encoding='utf-8')

    async def upload(self) -> dict:
        """Verify identity, upload and publish in one session; on failure, save the stage and local evidence."""
        if self.thumbnail:
            if not self.thumbnail.is_file():
                raise FileNotFoundError(f'Instagram cover does not exist: {self.thumbnail}')
            if self.thumbnail.suffix.lower() not in {'.jpg', '.jpeg', '.png'}:
                raise ValueError('Instagram cover only supports JPG/JPEG/PNG')
        paths = [self.video_file] if self.video_file else self.image_files
        for path in paths:
            if not path.is_file():
                raise FileNotFoundError(f'Instagram media file does not exist: {path}')
            allowed = {'.mp4', '.mov'} if self.video_file else {'.jpg', '.jpeg', '.png', '.avif', '.heic', '.heif'}
            if path.suffix.lower() not in allowed:
                raise ValueError(f'Unsupported Instagram media type: {path.suffix}')
        async with async_playwright() as p:
            browser, context, page = await _open_instagram_page(p, self.account_file, proxy=self.proxy, headless=self.headless)
            try:
                self.stage = 'identity'
                identity = await instagram_identity(page, self.account_file)
                self.stage = 'upload'
                await self._upload_files(page)
                self.stage = 'edit'
                await self._advance_media_editor(page)
                self.stage = 'publish'
                await self._publish(page, identity)
                self.stage = 'save_session'
                await context.storage_state(path=str(self.account_file))
                return self.result
            except Exception as error:
                folder = Path('.local/instagram-errors') / uuid4().hex
                folder.mkdir(parents=True)
                self.result.update(stage=self.stage, error=str(error), evidence_dir=str(folder))
                self.result_file.parent.mkdir(parents=True, exist_ok=True)
                self.result_file.write_text(json.dumps(self.result, ensure_ascii=False, indent=2), encoding='utf-8')
                await page.screenshot(path=str(folder/'page.png'))
                (folder/'page.html').write_text(await page.content(), encoding='utf-8')
                raise RuntimeError(f'Instagram {self.stage} did not finish; result record: {self.result_file}; reason: {error}') from error
            finally:
                await browser.close()
