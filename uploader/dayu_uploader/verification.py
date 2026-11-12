"""Read-only confirmation that the original post was submitted; waits for it to go public and checks the content only when asked explicitly."""
from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime
from hashlib import sha256
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import uuid4

from patchright.async_api import Browser, BrowserContext, Locator, expect
from uploader.dayu_uploader.constants import DAYU_CONTENT_PUBLIC, DAYU_CONTENT_REVIEWING, DAYU_CONTENT_SCHEDULED, DAYU_TIMEZONE
from utils.log import dayu_logger


async def check_dayu_article_content(body: Locator, manifest: dict) -> None:
    """Content check shared by the editor and the public body; any change in the order of text and images or in supported formats is an error."""
    await expect(body.locator("img")).to_have_count(manifest["image_count"])
    text = re.sub(r"[\s\u200b\ufeff]+", "", await body.inner_text())
    if sha256(text.encode()).hexdigest() != manifest["text_sha256"]:
        raise RuntimeError("The article body text does not match the input file")
    sequence = await body.evaluate("""body => {
        let value = '';
        function visit(node) {
            if (node.nodeType === Node.TEXT_NODE) { value += node.nodeValue; return; }
            if (node.nodeName === 'IMG') { value += '\\x00IMG\\x00'; return; }
            if (node.nodeName === 'HR') { value += '\\x00HR\\x00'; return; }
            node.childNodes.forEach(visit);
        }
        visit(body); return value;
    }""")
    sequence = re.sub(r"[\s\u200b\ufeff]+", "", sequence)
    if sha256(sequence.encode()).hexdigest() != manifest["structure_sha256"]:
        raise RuntimeError("The order of text, images or dividers in the article does not match the input file")
    for tag, count in manifest["formats"].items():
        await expect(body.locator(tag)).to_have_count(count)
    if manifest.get("dayu_style"):
        # The compatible layout uses the font/table attributes the server was tested to keep; check the actual computed colors so an attribute that is present but overridden is caught.
        actual = await body.evaluate("""body => ({
            text_colors: [...body.querySelectorAll('font[color]')].map(font => ({
                text: font.textContent.replace(/[\\s\\u200b\\ufeff]+/g, ''), color: getComputedStyle(font).color,
            })),
            background_colors: [...body.querySelectorAll('table[bgcolor]')].map(table => getComputedStyle(table).backgroundColor),
        })""")
        if actual != manifest["dayu_style"]:
            raise RuntimeError("The Dayu preview or public body did not keep the expected theme text and background colors")


async def wait_dayu_publication(context: BrowserContext, content_id: str | None = None,
                                origin_id: str | None = None, title: str | None = None,
                                timeout: int = 60, public: bool = False,
                                schedule: str | None = None) -> dict:
    """By default confirm that the original post was submitted; only an explicit public check waits for it to go public. Never republishes."""
    if not content_id and not origin_id:
        raise ValueError("Verification needs a content_id or an origin_id (the draft ID saved at preview)")
    deadline = time.monotonic() + timeout
    record = None
    last_status = None
    while time.monotonic() < deadline:
        page_number = 1
        total_pages = 1
        record = None
        while page_number <= total_pages and time.monotonic() < deadline:
            # Request parameters taken from the real "全部" (All) page. The shortvideo filter the page jumps to after publishing cannot be relied on.
            response = await context.request.get(
                "https://mp.dayu.com/dashboard/getNewContentList",
                params={"_rid": uuid4().hex, "currentView": "all", "source": "all",
                        "page": page_number, "currentTab": "all", "_": int(time.time() * 1000)},
                timeout=max(1, min(30000, int((deadline - time.monotonic()) * 1000))),
            )
            if not response.ok:
                raise RuntimeError(f"Failed to query Dayu posts: HTTP {response.status}")
            payload = await response.json()
            data_list = payload.get("dataList")
            if not isinstance(data_list, dict) or not isinstance(data_list.get("data"), list):
                raise RuntimeError("The post query returned no dataList.data; the login may have expired or the platform API changed")
            total_pages = int(data_list["totalPage"])
            matches = [item for item in data_list["data"]
                       if (not content_id or str(item.get("content_id")) == content_id)
                       and (not origin_id or item.get("origin_id") == origin_id)]
            if len(matches) > 1:
                raise RuntimeError("The same post ID matches several records; refusing to report success")
            if matches:
                record = matches[0]
                break
            page_number += 1
        if record:
            if title is not None and record.get("title") != title:
                raise RuntimeError("The title for this post ID does not match this submission")
            current_status = {"status": record.get("status"), "audit_status": record.get("audit_status")}
            if current_status != last_status:
                dayu_logger.info(f"Dayu post query: content_id={record.get('content_id')}, {current_status}")
            last_status = current_status
            # An original post under review was submitted successfully; the public check is an extra scope the caller chooses.
            if schedule or record.get("status") == DAYU_CONTENT_SCHEDULED:
                epoch = record.get("_app_extra", {}).get("time_for_release")
                if isinstance(epoch, bool) or not isinstance(epoch, (int, float)) or epoch <= 0:
                    raise RuntimeError("The original post has no saved schedule; refusing to confirm success")
                actual = datetime.fromtimestamp(epoch / 1000, DAYU_TIMEZONE)
                if schedule and actual != datetime.fromisoformat(schedule):
                    raise RuntimeError(f"Scheduled time of the original post does not match: expected={schedule}, actual={actual.isoformat()}")
            accepted = (DAYU_CONTENT_PUBLIC,) if public else (DAYU_CONTENT_PUBLIC, DAYU_CONTENT_REVIEWING, DAYU_CONTENT_SCHEDULED)
            if record.get("status") in accepted:
                break
        await asyncio.sleep(min(5, max(0, deadline - time.monotonic())))
    else:
        target = "公开访问" if public else "提交发表确认"  # "public access" / "publish submission confirmed"
        raise TimeoutError(f"Timed out waiting for Dayu {target}; last status={last_status}, check the original post, do not upload again")

    return record


async def verify_dayu_video(context: BrowserContext, browser: Browser, identity: dict,
                            content_id: str | None = None, origin_id: str | None = None,
                            title: str | None = None, timeout: int = 60, public: bool = False,
                            schedule: str | None = None) -> dict:
    """Confirm the original video was submitted; with public=True also verify the anonymous title, author and playback."""
    record = await wait_dayu_publication(context, content_id, origin_id, title, timeout, public, schedule)
    result = {"success": True, "status": "published" if record["status"] == DAYU_CONTENT_PUBLIC else "submitted", "type": "video",
              "content_id": str(record["content_id"]), "origin_id": record["origin_id"],
              "title": record["title"], "identity": identity, "platform_status": record["status"]}
    if schedule or record["status"] == DAYU_CONTENT_SCHEDULED:
        result.update(schedule=datetime.fromtimestamp(record["_app_extra"]["time_for_release"] / 1000, DAYU_TIMEZONE).isoformat(),
                      schedule_verified=True)
        if record["status"] != DAYU_CONTENT_PUBLIC:
            result["status"] = "scheduled"
    if not public:
        return result
    public_url = record.get("ucUrl", "")
    parsed = urlsplit(public_url)
    query = parse_qs(parsed.query)
    if (parsed.scheme != "https" or parsed.hostname != "mparticle.uc.cn"
            or parsed.path != "/video.html"
            or query.get("wm_id") != [identity["wmid"]]
            or query.get("wm_aid") != [record["origin_id"]]):
        raise RuntimeError("The domain, identity or origin_id of the post's public URL does not match")

    # Create a new context without storage_state, so logged-in preview permissions cannot hide a public playback failure.
    public_context = await browser.new_context()
    try:
        public_page = await public_context.new_page()
        await public_page.goto(public_url, wait_until="domcontentloaded", timeout=45000)
        # Use only the component's meaningful prefix, excluding the build-generated class hash suffix and same-named authors in recommendation cards.
        await expect(public_page.locator('[class^="pc-videoContent-"]')).to_have_text(record["title"], timeout=30000)
        await expect(public_page.locator('[class^="pc-userInfoContainer-"] > span')).to_have_text(identity["name"])
        video = public_page.locator("video")
        await expect(video).to_have_count(1)
        await video.evaluate("async v => { v.muted = true; await v.play(); }")
        await public_page.wait_for_function(
            """() => { const v = document.querySelector('video');
                return v && !v.error && v.readyState >= 2 && v.duration > 0 && v.currentTime > 0.1; }""",
            timeout=30000,
        )
        playback = await video.evaluate("v => ({duration: v.duration, current_time: v.currentTime, ready_state: v.readyState})")
    finally:
        await public_context.close()
    result.update(status="published", audit_status=record.get("audit_status"),
                  audit_remark=record.get("_app_extra", {}).get("audit_remark", ""),
                  public_url=public_url, public_playback=playback)
    return result


async def verify_dayu_article(context: BrowserContext, browser: Browser, identity: dict,
                              content_id: str | None = None, origin_id: str | None = None,
                              title: str | None = None, timeout: int = 60,
                              manifest: dict | None = None, public: bool = False,
                              schedule: str | None = None) -> dict:
    """Confirm the original article was submitted; with public=True also check the body, image positions and formatting anonymously."""
    record = await wait_dayu_publication(context, content_id, origin_id, title, timeout, public, schedule)
    result = {"success": True, "status": "published" if record["status"] == DAYU_CONTENT_PUBLIC else "submitted", "type": "article",
              "content_id": str(record["content_id"]), "origin_id": record["origin_id"],
              "title": record["title"], "identity": identity, "platform_status": record["status"]}
    if schedule or record["status"] == DAYU_CONTENT_SCHEDULED:
        result.update(schedule=datetime.fromtimestamp(record["_app_extra"]["time_for_release"] / 1000, DAYU_TIMEZONE).isoformat(),
                      schedule_verified=True)
        if record["status"] != DAYU_CONTENT_PUBLIC:
            result["status"] = "scheduled"
    if not public:
        return result
    if not re.fullmatch(r"[a-f0-9]{32}", record.get("origin_id", "")):
        raise RuntimeError("The article draft ID is incomplete; cannot open the public article")
    # Clicking a published image post title in the real dashboard produces this URL; the image post list does not have the ucUrl field used for videos.
    public_url = "https://mparticle.uc.cn/article.html?" + urlencode({
        "uc_param_str": "frdnsnpfvecpntnwprdssskt", "wm_aid": record["origin_id"],
    })
    public_context = await browser.new_context()
    try:
        page = await public_context.new_page()
        await page.goto(public_url, wait_until="domcontentloaded", timeout=45000)
        # The public body component prefix has no build hash; scope to the article container, excluding titles, authors and images in the recommendation area.
        article = page.locator('[class^="index-articleContainer-"]')
        await expect(article.locator(":scope > h1")).to_have_text(record["title"], timeout=30000)
        await expect(article.locator('[class^="article-userInfoName-"]')).to_have_text(identity["name"])
        body = article.locator('[class^="index-articleSummary-"]')
        await expect(body).to_have_count(1)
        await expect(body).not_to_be_empty()
        images = body.locator("img")
        if manifest:
            await expect(images).to_have_count(manifest["image_count"])
        for index in range(await images.count()):
            image = images.nth(index)
            await image.scroll_into_view_if_needed()
            await expect(image).to_have_attribute("src", re.compile(r"^https?://(?:image\.uc\.cn|mp\.dayu\.com)/"))
            await expect(image).to_have_js_property("complete", True, timeout=30000)
            if await image.evaluate("e => e.naturalWidth") <= 0:
                raise RuntimeError(f"Image {index + 1} in the public article cannot be loaded")
        if manifest:
            await check_dayu_article_content(body, manifest)
        public_article = {"image_count": await images.count(), "content_checked": bool(manifest)}
    finally:
        await public_context.close()
    result.update(status="published", audit_status=record.get("audit_status"),
                  audit_remark=record.get("_app_extra", {}).get("audit_remark", ""),
                  public_url=public_url, public_article=public_article)
    return result
