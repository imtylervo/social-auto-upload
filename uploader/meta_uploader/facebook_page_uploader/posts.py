"""Look up and delete original posts in Business Suite, identifying them by content ID rather than by title."""

import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from patchright.async_api import async_playwright, expect, TimeoutError as BrowserTimeoutError

from uploader.meta_uploader.facebook_page_uploader.main import _open_business_page


async def open_meta_post(page, *, list_url: str, page_name: str, expected_text: str,
                         content_id: str | None = None, schedule=None):
    """Find the single matching caption, check the Page and open the details; shared post verification used after publishing and before deleting."""
    # A new Reel can already be in the list while platform search still finds nothing; read the raw list to avoid search index delay.
    # Only posts already loaded in the list are covered. A timeout raises a clear error; another post with the same text is never used instead.
    # A Reel is accepted by the create response first and only later enters the content list; the first list may be a snapshot from before processing finished.
    # Only refresh to look up the original post, never repost here; each read is bounded, and it stops at once if the caption matches more than one post.
    deadline = asyncio.get_running_loop().time() + 120
    row = page.get_by_role("row").filter(has_text=expected_text)
    while True:
        await page.goto(list_url, wait_until="domcontentloaded", timeout=90000)
        try:
            await row.wait_for(state='visible', timeout=10000)
        except BrowserTimeoutError:
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError('The requested record was not found in the post list; result unverified, do not simply repost')
        else:
            await expect(row).to_have_count(1)
            break
    await expect(row).to_contain_text(page_name)
    if parse_qs(urlparse(page.url).query).get('asset_id') != parse_qs(urlparse(list_url).query).get('asset_id'):
        raise RuntimeError('The Page ID of the list does not match the request; nothing deleted')
    is_reel = 'Reels' in await row.inner_text()
    # In the published list the TITLE grid cell holds the detail link; the metrics also have aria-pressed, so do not mix them up.
    # The scheduled list still uses the old layout, where the title is the only selectable detail button.
    title = row.locator('[role="gridcell"][data-surface$=":TITLE"]') if '/published_posts' in list_url else row.locator('[role="button"][aria-pressed]')
    await expect(title).to_have_count(1)
    await title.click()
    if schedule:
        await expect(row).to_contain_text(f'{schedule.month}月{schedule.day}日 {schedule:%H:%M}')
    if '/published_posts' in list_url:
        # The new published list opens insights details; content_id in the URL is the original post ID that "复制帖子编号" (Copy post ID) gives.
        await page.wait_for_url('**/object_insights/**', timeout=30000)
        # The URL changes first while the old list may still hold several menus; wait for the insights body to mount, then limit to the visible menu.
        await page.locator('[data-surface$="BizWebObjectinsightsHeaderActionDropdown"] [aria-haspopup="menu"]').wait_for(timeout=120000)
        query = parse_qs(urlparse(page.url).query)
        ids = query.get('content_id', [])
        if len(ids) != 1 or not ids[0].isdigit() or query.get('asset_id') != parse_qs(urlparse(list_url).query).get('asset_id'):
            raise RuntimeError('Insights details lack a unique post ID or the Page does not match; nothing deleted')
        actual_id = ids[0]
    else:
        # The old detail panel links a level-3 heading through aria-labelledby; the div right after it is the original post ID field.
        # Read the trailing digits rather than the Chinese "编号：" (ID:); the title, caption and the row's view count must not be taken as the ID.
        detail = page.locator('div[aria-labelledby]').filter(has=page.locator('[role="heading"][aria-level="3"] + div')).filter(visible=True)
        if await detail.count():
            await expect(detail).to_have_count(1, timeout=30000)
            number = detail.locator('[role="heading"][aria-level="3"] + div')
            await expect(number).to_have_count(1)
            number_text = await number.inner_text()
        else:
            # The controlled test page has no full detail container; the number field must still be separate and unique, with no fallback to the title or row text.
            number = page.get_by_text(re.compile(r'^编号：\d+$'))
            await expect(number).to_have_count(1, timeout=30000)
            number_text = await number.inner_text()
        match = re.search(r'(\d+)$', number_text.strip())
        if not match:
            raise RuntimeError('The detail ID field does not contain the original post ID; nothing deleted')
        actual_id = match.group(1)
    if content_id is not None and actual_id != content_id:
        raise RuntimeError(f'Original post ID does not match: expected {content_id}, page shows {actual_id}; nothing deleted')
    return row, actual_id, is_reel


async def meta_post_action(account_file: Path, *, page_id: str, page_name: str,
                           content_id: str, expected_text: str, scheduled: bool = False,
                           delete: bool = False, proxy: str | None = None,
                           headless: bool = False) -> dict:
    """Verify by Page, content ID and caption; scheduled posts are deleted permanently, published posts are moved to the trash."""
    if not page_id.isdigit() or not content_id.isdigit() or not page_name.strip() or not expected_text.strip():
        raise ValueError("Numeric page-id/content-id, a Page name and a caption for verification are required")
    async with async_playwright() as playwright:
        browser, context, page = await _open_business_page(playwright, account_file, proxy=proxy, headless=headless)
        try:
            state = "scheduled_posts" if scheduled else "published_posts"
            list_url = f"https://business.facebook.com/latest/posts/{state}?asset_id={page_id}"
            row, actual_id, is_reel = await open_meta_post(page, list_url=list_url, page_name=page_name,
                                                   expected_text=expected_text, content_id=content_id)
            result = {"platform": "facebook-page", "page_id": page_id, "page_name": page_name,
                      "content_id": content_id, "expected_text": expected_text,
                      "status": "scheduled" if scheduled else "published"}
            if delete:
                # The detail menu of a published post has an explicit delete Action marker; the title ID is already verified.
                # Do not rely on translated labels such as "打开下拉菜单/删除帖子" (Open dropdown / Delete post), and do not search the whole page for a same-named button.
                if scheduled:
                    # The old detail action menu has no separate Action surface; limit it to the detail panel with a level-3 heading,
                    # which excludes the post preview menu that has an aria-label. Tested: five items, in order Edit, Duplicate, Reschedule, Move to drafts, Delete.
                    detail = page.locator('div[aria-labelledby]').filter(has=page.locator('[role="heading"][aria-level="3"] + div')).filter(visible=True)
                    await expect(detail).to_have_count(1)
                    menu_button = detail.locator('[role="button"][aria-haspopup="menu"]:not([aria-label])')
                    await expect(menu_button).to_have_count(1)
                    await menu_button.click()
                    items = page.get_by_role('menu').get_by_role('menuitem')
                    count = await items.count()
                    if count not in (4, 5):
                        raise RuntimeError(f'Unrecognised action menu on the scheduled post details: {count} items, nothing deleted')
                    # Delete is always the last item of this menu; depending on localisation or permissions, "移到草稿" (Move to drafts) may be missing.
                    await items.nth(count - 1).click()
                else:
                    dropdown = page.locator('[data-surface$="BizWebObjectinsightsHeaderActionDropdown"] [aria-haspopup="menu"]')
                    await expect(dropdown).to_have_count(1)
                    await dropdown.click()
                    action = page.locator('[data-surface$="match_container:TofuObjectInsightsDeleteAction"] [role="menuitem"]')
                    await expect(action).to_have_count(1)
                    await action.click()
                # The real confirmation box has dialog/aria-labelledby/tabindex=-1; the old implementation wrongly assumed there was no dialog.
                # The detail panel does not have these attributes. The confirmation box items are, in order, Close, Cancel and the main action.
                # Stop on any change in count or scope; never perform a destructive action based on Chinese text or on whatever button is last on the page.
                dialog = page.locator('[role="dialog"][aria-labelledby][tabindex="-1"]').filter(visible=True)
                await expect(dialog).to_have_count(1)
                actions = dialog.get_by_role('button')
                await expect(actions).to_have_count(2)
                await actions.nth(1).click()
                await expect(dialog).to_have_count(0, timeout=30000)
                await expect(row).to_have_count(0, timeout=45000)
                if not scheduled:
                    # After a delete from insights details the platform navigates back to the list; wait for that navigation to finish so a refresh does not race it and hit ERR_ABORTED.
                    await page.wait_for_url('**/posts/published_posts**', wait_until='domcontentloaded', timeout=90000)
                # After deleting, request the list from the server again rather than trusting the frontend's optimistic removal; only query, never delete again.
                deadline = asyncio.get_running_loop().time() + 60
                while True:
                    await page.goto(list_url, wait_until="domcontentloaded", timeout=90000)
                    # The unfiltered list counts as loaded only when it has post rows or the platform's explicit empty state; search index delay does not prove deletion.
                    loaded = page.get_by_role('row').filter(has=page.locator('[role="button"][aria-pressed]')).or_(page.get_by_text('没有定时帖', exact=True))
                    try:
                        await expect(loaded).not_to_have_count(0, timeout=10000)
                        await expect(page.get_by_role('row').filter(has_text=expected_text)).to_have_count(0, timeout=10000)
                    except BrowserTimeoutError:
                        if asyncio.get_running_loop().time() >= deadline:
                            raise TimeoutError("Delete was submitted, but the refreshed list has not yet confirmed the original post is gone; look it up first and do not delete again")
                    else:
                        break
                result["status"] = "deleted" if scheduled else "trashed"
            result["checked_at"] = datetime.now(timezone.utc).isoformat()
            await context.storage_state(path=str(account_file))
            return result
        except Exception:
            # Keep the actual page at the time of the error to help track down site changes or unknown results; do not retry the remote delete.
            directory = Path('.local/meta-errors') / uuid4().hex
            directory.mkdir(parents=True, exist_ok=True)
            (directory / 'page.txt').write_text(page.url + '\n' + await page.locator('body').inner_text(), encoding='utf-8')
            await page.screenshot(path=str(directory / 'page.png'))
            raise
        finally:
            await browser.close()
