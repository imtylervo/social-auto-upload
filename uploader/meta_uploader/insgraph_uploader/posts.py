"""Verify an original Instagram post and move it to Recently Deleted."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from patchright.async_api import Page, async_playwright, expect

from .main import _open_instagram_page, instagram_identity, instagram_response_payload


def instagram_post_id(post_url: str) -> str:
    """Accept the short links and author-qualified links the site actually serves; reject other domains and non-post URLs."""
    parsed = urlparse(post_url)
    if parsed.scheme != 'https' or parsed.hostname not in {'www.instagram.com', 'instagram.com'} or parsed.username or parsed.password or parsed.port:
        raise ValueError('The original Instagram post must be an official HTTPS link')
    match = re.fullmatch(r'/(?:[A-Za-z0-9_.]+/)?(?:p|reel)/([A-Za-z0-9_-]+)/?', parsed.path)
    if not match:
        raise ValueError('The original Instagram post link must contain /p/<id>/ or /reel/<id>/')
    return match.group(1)


async def find_instagram_post(page: Page, *, post_url: str, expected_text: str, owner_id: str) -> dict:
    """Check the canonical link, author ID and caption on the detail page; return the numeric ID of the current post."""
    shortcode = instagram_post_id(post_url)
    if not expected_text.strip():
        raise ValueError('expected_text must not be empty')
    # Open the post's detail page through /p/; the /reel/ route opens a full-screen recommendation player with other posts.
    await page.goto(f'https://www.instagram.com/p/{shortcode}/', wait_until='domcontentloaded', timeout=120_000)
    # og:url and instapp:owner_user_id in the post page head are the canonical link and author metadata the platform outputs.
    # Do not guess the author from recommended posts or matching text; the caption is limited to main to exclude navigation and other windows.
    canonical = page.locator('meta[property="og:url"]')
    owner = page.locator('meta[property="instapp:owner_user_id"]')
    await expect(canonical).to_have_count(1)
    await expect(owner).to_have_count(1)
    if instagram_post_id(await canonical.get_attribute('content')) != shortcode:
        raise RuntimeError('Instagram: the current original post ID does not match')
    if await owner.get_attribute('content') != owner_id:
        raise RuntimeError('Instagram: the author of the original post does not match the logged-in user')
    main = page.locator('main')
    await expect(main).to_have_count(1)
    await expect(main).to_contain_text(expected_text, timeout=60_000)
    # The detail meta description holds the original caption and never the comments; checking both stops a match on a sentence that only appears in a comment.
    caption_metadata = page.locator('meta[name="description"]')
    await expect(caption_metadata).to_have_count(1)
    if expected_text not in (await caption_metadata.get_attribute('content') or ''):
        raise RuntimeError('Instagram: the original caption metadata does not contain the expected text. Verify with a short phrase from the original caption')
    # Photo, carousel and Reel detail pages all output the same app deep-link metadata, which holds the current post's numeric ID.
    # Use the platform's post identity field, which is not affected by recommended posts or structural differences in internal query variables.
    deep_link = page.locator('meta[property="al:ios:url"]')
    await expect(deep_link).to_have_count(1)
    match = re.fullmatch(r'instagram://media\?id=(\d+)', await deep_link.get_attribute('content'))
    if not match:
        raise RuntimeError('Instagram: the detail page did not provide the numeric ID of the current post')
    return {'post_id': shortcode, 'content_id': f'{match.group(1)}_{owner_id}', 'post_url': post_url,
            'owner_id': owner_id, 'expected_text': expected_text, 'status': 'published'}


async def instagram_post_action(account_file: Path, *, post_url: str, expected_text: str, delete: bool = False,
                                proxy: str | None = None, headless: bool = False,
                                result_file: str | Path | None = None) -> dict:
    """Delete once after verifying the original post; accept only a did_delete response for the target ID."""
    instagram_post_id(post_url)
    result_file = Path(result_file) if result_file else Path('.local/instagram-results') / f'{uuid4().hex}.json'
    result = {'platform': 'instagram', 'post_url': post_url, 'status': 'not_submitted'}
    async with async_playwright() as p:
        browser, context, page = await _open_instagram_page(p, account_file, proxy=proxy, headless=headless)
        try:
            identity = await instagram_identity(page, account_file)
            result.update(await find_instagram_post(page, post_url=post_url, expected_text=expected_text, owner_id=identity['user_id']))
            if delete:
                # The only three-dot menu button on the detail page has aria-haspopup=dialog; the comment emoji menu has no circle.
                # This structure was observed on Chinese and English photo, carousel and Reel detail pages; it avoids translated aria-labels.
                menu_button = page.locator('[role="button"][aria-haspopup="dialog"]').filter(has=page.locator('svg circle'))
                await expect(menu_button).to_have_count(1)
                await menu_button.click()
                menu = page.get_by_role('dialog')
                buttons = menu.get_by_role('button')
                # The menu on your own post was observed to have a fixed eight items, the first being Delete; the role covers native and non-native buttons.
                # The count assertion, together with the verified author and post identity, fails on any structure change instead of clicking some other menu.
                await expect(buttons).to_have_count(8, timeout=30_000)
                # In testing, a mouse click sometimes only closed the popup menu; this role=button accepts Enter, and keyboard activation reliably opens the confirmation box.
                await buttons.nth(0).press('Enter')
                # The confirmation box is a modal dialog with a title and only two items, Delete and Cancel, with Delete always first.
                # Keep it strictly separate from the previous menu; a closed menu does not mean the post was deleted.
                confirm = page.locator('[role="dialog"][aria-modal="true"]').filter(has=page.get_by_role('heading'))
                await expect(confirm).to_have_count(1, timeout=60_000)
                confirm_buttons = confirm.get_by_role('button')
                await expect(confirm_buttons).to_have_count(2)
                result['status'] = 'deletion_unknown'
                result_file.parent.mkdir(parents=True, exist_ok=True)
                result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
                target = f"/api/v1/web/create/{result['content_id']}/delete/"
                async with page.expect_response(lambda r: urlparse(r.url).path == target and r.request.method == 'POST', timeout=60_000) as event:
                    await confirm_buttons.nth(0).press('Enter')
                payload = instagram_response_payload(await (await event.value).text())
                if payload.get('payload', {}).get('did_delete') is not True:
                    raise RuntimeError('Instagram did not confirm that the target post was deleted')
                result['status'] = 'deleted'
            result_file.parent.mkdir(parents=True, exist_ok=True)
            result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            await context.storage_state(path=str(account_file))
            return result
        except Exception as error:
            folder = Path('.local/instagram-errors') / uuid4().hex
            folder.mkdir(parents=True)
            result.update(error=str(error), evidence_dir=str(folder))
            result_file.parent.mkdir(parents=True, exist_ok=True)
            result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            await page.screenshot(path=str(folder/'page.png'))
            (folder/'page.html').write_text(await page.content(), encoding='utf-8')
            raise RuntimeError(f'Instagram operation on the original post did not finish; result record: {result_file}; reason: {error}') from error
        finally:
            await browser.close()
