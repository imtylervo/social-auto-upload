"""Preview, publish confirmation and submission result recording shared by Dayu video and article."""
import json
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit

from patchright.async_api import Page, expect
from uploader.dayu_uploader.verification import check_dayu_article_content, wait_dayu_publication
from uploader.dayu_uploader.schedule import read_dayu_schedule


async def submit_dayu_publication(page: Page, result: dict, result_file: Path,
                                  article_html: str | None = None) -> None:
    """Each submit action runs once; before and after every remote write the stage and post identifiers are saved for read-only lookup."""
    result["status"] = "preview_unknown"
    result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    # The main form's "发表" (Publish) only creates a preview; the exact button name tells it apart from the later "确认发表" (Confirm publish).
    save_url = "https://mp.dayu.com/dashboard/save-draft"
    async def preserve_article_html(route):
        # Replace only this article's body, keeping the title, source, cover and session fields filled in on the form; the platform's filtering rules are not changed.
        fields = parse_qsl(route.request.post_data or "", keep_blank_values=True)
        if route.request.method != "POST" or sum(key == "content" for key, _ in fields) != 1:
            await route.abort()
            raise RuntimeError("The body structure of the article preview request changed; refusing to submit")
        if result.get("origin_id") and dict(fields).get("draft_id") != result["origin_id"]:
            await route.abort()
            raise RuntimeError("The preview request does not match the draft ID to be restored")
        await route.fallback(post_data=urlencode([
            (key, article_html if key == "content" else value) for key, value in fields
        ]))
    if article_html is not None:
        await page.route(save_url, preserve_article_html)
    try:
        async with page.expect_response(
            lambda r: urlsplit(r.url).path == "/dashboard/save-draft" and r.request.method == "POST",
            timeout=45000,
        ) as draft_event:
            await page.get_by_role("button", name="发表", exact=True).click()
    finally:
        if article_html is not None:
            await page.unroute(save_url, preserve_article_html)
    draft_response = await draft_event.value
    if not draft_response.ok:
        raise RuntimeError(f"Saving the publish preview failed: HTTP {draft_response.status}")
    draft = (await draft_response.json()).get("data", {})
    if not draft.get("_id"):
        raise RuntimeError("The publish preview returned no draft ID; refusing to confirm publishing")
    if result.get("origin_id") and draft["_id"] != result["origin_id"]:
        raise RuntimeError("The preview response returned a different draft ID; refusing to confirm publishing")
    result.update(origin_id=draft["_id"], status="preview_ready")
    result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    # Read the server-side settings before the irreversible publish confirmation, so a correct UI cannot hide a time that was not saved on the draft.
    await read_dayu_schedule(page.context, result["origin_id"], result.get("schedule"))
    if article_html is not None:
        preview_url = draft.get("previewUrl", "")
        parsed = urlsplit(preview_url)
        if (parsed.scheme != "https" or parsed.hostname != "mparticle.uc.cn"
                or parsed.path != "/preview.html" or parse_qs(parsed.query).get("wm_aid") != [draft["_id"]]):
            raise RuntimeError("The article preview URL does not match this draft; refusing to confirm publishing")
        preview = await page.context.new_page()
        try:
            await preview.goto(preview_url, wait_until="domcontentloaded", timeout=45000)
            # article-content in the server preview is the body area, excluding the header title, the author and other images on the page.
            body = preview.locator(".article-content")
            await expect(body).to_have_count(1, timeout=30000)
            await check_dayu_article_content(body, result["manifest"])
            # Preview images are lazy-loaded; scroll to each one and check that it decodes, a screenshot of images not yet loaded is no evidence of the result.
            images = body.locator("img")
            for index in range(await images.count()):
                image = images.nth(index)
                await image.scroll_into_view_if_needed()
                await expect(image).to_have_js_property("complete", True, timeout=30000)
                if await image.evaluate("image => image.naturalWidth") <= 0:
                    raise RuntimeError(f"Image {index + 1} in the article preview cannot be loaded")
            result["style_check"]["preview_checked"] = True
            result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        finally:
            await preview.close()
    # The final submit button on the preview page has its own name; the main form's "发表" locator cannot be reused.
    confirm = page.get_by_role("button", name="确认发表", exact=True)
    await expect(confirm).to_be_visible(timeout=30000)
    # Never click confirm again after a response timeout. With origin_id saved this submission can be looked up without uploading again.
    result["status"] = "submission_unknown"
    result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    async with page.expect_response(
        lambda r: urlsplit(r.url).path == "/dashboard/submit-article" and r.request.method == "POST",
        timeout=45000,
    ) as submit_event:
        await confirm.click()
    response = await submit_event.value
    if not response.ok:
        raise RuntimeError(f"Publish result not confirmed: HTTP {response.status}, check the original post")
    submitted = (await response.json()).get("data", {})
    if not submitted.get("content_id"):
        raise RuntimeError("The publish response returned no content_id, result unknown, check the original post")
    # Success once the final publish response returns this post's ID; review and public access are not completion conditions of the publish command.
    result.update(content_id=str(submitted["content_id"]), article_id=submitted.get("_id"))
    result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if result.get("schedule"):
        # content_id confirms the submission; then recheck the original post and its schedule in the content list. A draft does not count as a successful scheduled submission.
        record = await wait_dayu_publication(page.context, content_id=result["content_id"],
                                             origin_id=result["origin_id"], title=result.get("title"),
                                             schedule=result["schedule"])
        result.update(schedule_verified=True, platform_status=record["status"])
        result.update(success=True, status="scheduled")
    else:
        result.update(success=True, status="submitted")
    result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
