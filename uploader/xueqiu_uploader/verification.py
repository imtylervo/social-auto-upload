"""Check the text, image positions and native structure of the Xueqiu editor, preview and server-side article."""
import json
import re
from hashlib import sha256
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from patchright.async_api import async_playwright, expect
from conf import LOCAL_CHROME_PATH
from uploader.xueqiu_uploader.constants import XUEQIU_HOME_URL
from uploader.xueqiu_uploader.content import load_xueqiu_article
from uploader.xueqiu_uploader.session import load_xueqiu_identity, read_xueqiu_identity


async def check_xueqiu_article_content(body, document, image_sources=None):
    """Check by the interleaved order of text and images; a matching image count is not taken as proof that positions between paragraphs are right."""
    await expect(body.locator("img")).to_have_count(len(document.images))
    if image_sources is not None:
        # The server may keep the count but swap images; check each source position against the absolute URL obtained at the first upload.
        actual_sources = await body.locator("img").evaluate_all(
            "images => images.map(image => new URL(image.getAttribute('src'), 'https://mp.xueqiu.com/').href)")
        if actual_sources != image_sources:
            raise RuntimeError("Xueqiu article images differ in content or order from this upload")
    actual = await body.evaluate("""(body, html) => {
        let sequence = '';
        function visit(node) {
            if (node.nodeType === Node.TEXT_NODE) { sequence += node.nodeValue; return; }
            if (node.nodeName === 'IMG') { sequence += '\\x00IMG\\x00'; return; }
            node.childNodes.forEach(visit);
        }
        visit(body);
        const source = document.createElement('template'); source.innerHTML = html;
        return {sequence, headings: body.querySelectorAll('h4').length,
            bold: body.querySelectorAll('b,strong').length, italic: body.querySelectorAll('i,em').length,
            links: [...body.querySelectorAll('a')].map(a => ({text: a.textContent, href: a.href})),
            expectedLinks: [...source.content.querySelectorAll('a')].map(a => ({text: a.textContent,
                href: new URL(a.getAttribute('href'), document.baseURI).href}))};
    }""", document.content_html)
    sequence = re.sub(r"[\s\u200b\ufeff]+", "", actual["sequence"])
    if sha256(sequence.encode()).hexdigest() != document.manifest["structure_sha256"]:
        raise RuntimeError("Xueqiu article text or image positions between paragraphs do not match the source")
    expected = {"headings": document.tags["h4"], "bold": document.tags["strong"], "italic": document.tags["em"]}
    for key, count in expected.items():
        if actual[key] != count:
            raise RuntimeError(f"Xueqiu article structure does not match: {key} expected {count}, got {actual[key]}")
    if actual["links"] != actual["expectedLinks"]:
        raise RuntimeError("Xueqiu article link text or target does not match the source")


async def query_xueqiu_article(page, identity, content_id, title=None, visibility=None):
    """Look up the original ID through the published management list (as tested), read-only; never republish."""
    await page.goto(XUEQIU_HOME_URL, wait_until="domcontentloaded", timeout=45000)
    if (await read_xueqiu_identity(page))["uid"] != identity["uid"]:
        raise RuntimeError("The Xueqiu identity used for the lookup does not match the bound account")
    # 内容管理 (content management) is the actual sidebar entry on the home page; SPA navigation adds the request headers the platform needs, so requesting the JSON directly is not equivalent.
    async with page.expect_response(lambda response: response.request.method == "GET"
                                    and urlsplit(response.url).path == "/xq/query/v1/search/long",
                                    timeout=30000) as listing:
        await page.get_by_role("link", name="内容管理", exact=True).click()
    response = await listing.value
    payload = await response.json()
    # Tested: the list has page/maxPage/list; later pages reuse the auth headers of that request, and no auth value is ever printed.
    headers = await response.request.all_headers()
    query_url = urlsplit(response.url)
    params = parse_qs(query_url.query)
    seen_pages = set()
    while True:
        if not response.ok or not isinstance(payload.get("list"), list):
            raise RuntimeError(f"Xueqiu original post lookup failed: HTTP {response.status}, no published list returned")
        matches = [item for item in payload["list"] if str(item.get("id")) == str(content_id)]
        if len(matches) > 1:
            raise RuntimeError("The same Xueqiu post ID matches several records")
        if matches:
            item = matches[0]
            if str(item.get("user_id")) != identity["uid"] or (title is not None and item.get("title") != title):
                raise RuntimeError("The identity or title of the original Xueqiu post does not match")
            if visibility is not None and item.get("is_private") is not (visibility == "私人"):
                raise RuntimeError("The sharing scope of the original Xueqiu post does not match")
            # The first-screen API returns before the list is drawn; wait for the original post title to be visible before the screenshot, so a skeleton screen is not taken as dashboard evidence.
            if payload.get("page") == 1:
                await expect(page.get_by_text(item["title"], exact=True)).to_be_visible(timeout=30000)
            return item
        current, last = payload.get("page"), payload.get("maxPage")
        if not isinstance(current, int) or not isinstance(last, int) or current >= last:
            raise RuntimeError(f"Original post {content_id} not found in the published list; check the dashboard, do not republish directly")
        if current in seen_pages:
            raise RuntimeError("The Xueqiu lookup returned the same page again and was stopped; check the dashboard, do not republish")
        seen_pages.add(current)
        params["page"] = [str(current + 1)]
        url = urlunsplit(query_url._replace(query=urlencode(params, doseq=True)))
        response = await page.context.request.get(url, headers=headers, timeout=30000)
        payload = await response.json()


async def verify_xueqiu_result(account_file, result_file, headless=False):
    """Recover the original post ID from the result file and look up the submission result read-only under the bound account."""
    account_file = Path(account_file)
    result_file = Path(result_file)
    result = json.loads(result_file.read_text(encoding="utf-8"))
    identity = load_xueqiu_identity(account_file)
    content_id = result.get("content_id", "")
    if not re.fullmatch(r"[1-9][0-9]*", str(content_id)):
        raise ValueError("The result file has no post ID returned by the platform; check the original post in the dashboard first, do not republish")
    if result.get("identity", {}).get("uid") != identity["uid"]:
        raise ValueError("The result file does not match the selected Xueqiu account")
    # The current result stores the source path; the lookup must recheck the body with the unchanged source, and must not clear an earlier content error and then report success.
    document = None
    if result.get("content_file"):
        document = load_xueqiu_article(Path(result["content_file"]))
        if document.manifest != result.get("manifest"):
            raise ValueError("The source differs from the content at publish time; restore the source before the lookup, do not republish")
    elif result.get("error"):
        raise ValueError("The old result has no source path and keeps a check error; check the original post in the dashboard first, do not republish")
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=LOCAL_CHROME_PATH or None, channel="chrome", headless=headless)
        try:
            context = await browser.new_context(storage_state=str(account_file))
            page = await context.new_page()
            record = await query_xueqiu_article(page, identity, content_id, result.get("title"), result.get("visibility"))
            if document is not None:
                # Check the body actually saved in the dashboard; the editor is not rewritten and no publish action is triggered.
                check_page = await context.new_page()
                await check_page.set_content(record.get("text") or "")
                await check_xueqiu_article_content(check_page.locator("body"), document, result.get("images"))
                await check_page.close()
            screenshot = result_file.with_suffix(".verified.png")
            await page.screenshot(path=str(screenshot), full_page=True)
            result.update(success=True, status="published", management_verified=True,
                          url=f"https://xueqiu.com/{identity['uid']}/{content_id}",
                          verified_screenshot=str(screenshot), is_private=record["is_private"])
            result.pop("error", None)
            result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return result
        finally:
            await browser.close()
