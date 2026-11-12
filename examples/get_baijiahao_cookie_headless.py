# -*- coding: utf-8 -*-
"""Baijiahao (headless) QR-code login → save cookie.

Notes:
  - A headless browser opens the Baijiahao login page, extracts the login QR code, enlarges the screenshot and saves it as a png,
    and shows an ASCII QR code in the terminal; scan it with your phone / the Baidu app to log in.
  - After a successful scan, the login state is written to cookies/baijiahao_uploader/account.json automatically.

Usage:
    python examples/get_baijiahao_cookie_headless.py
"""
from pathlib import Path

from playwright.async_api import async_playwright
from conf import BASE_DIR
from utils.login_qrcode import (
    build_login_qrcode_path,
    print_terminal_qrcode,
)
from uploader.baijiahao_uploader.main import cookie_auth, baijiahao_logger


QR_SELECTOR = 'img[src^="https://passport.baidu.com/v2/api/qrcode"]'
LOGIN_BTN_TEXT = "登录"
LOGIN_URL = "https://baijiahao.baidu.com/builder/theme/bjh/login"


async def _grab_qr(page, qrcode_path: Path) -> str:
    qr = page.locator(QR_SELECTOR).first
    await qr.wait_for(state="attached", timeout=60000)
    src = await qr.get_attribute("src")
    if src and src.startswith("https://"):
        resp = await page.context.request.get(src)
        qrcode_path.parent.mkdir(parents=True, exist_ok=True)
        qrcode_path.write_bytes(await resp.body())
    else:
        await qr.screenshot(path=str(qrcode_path))

    qrcode_content = ""
    try:
        import cv2
        img = cv2.imread(str(qrcode_path))
        if img is not None:
            h, w = img.shape[:2]
            up = cv2.resize(img, (w * 3, h * 3), interpolation=cv2.INTER_CUBIC)
            qrcode_content = cv2.QRCodeDetector().detectAndDecode(up)[0] or ""
    except Exception:
        pass
    return qrcode_content or ""


async def _wait_login(page, max_checks: int = 120, interval: int = 3) -> bool:
    import asyncio
    async def _logged_in():
        if "login" in page.url:
            return False
        ctx = page.context
        cookies = await ctx.cookies()
        if any(c.get("name") in ("BDUSS", "STOKEN") for c in cookies):
            return True
        return False

    for _ in range(max_checks):
        if await _logged_in():
            return True
        await asyncio.sleep(interval)
    return False


async def main():
    account_file = Path(BASE_DIR / "cookies" / "baijiahao_uploader" / "account.json")
    account_file.parent.mkdir(parents=True, exist_ok=True)

    import os
    if os.path.exists(account_file) and await cookie_auth(str(account_file)):
        baijiahao_logger.success("[+] cookie is already valid, no need to log in again")
        return

    qrcode_path = build_login_qrcode_path(str(account_file))
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(LOGIN_URL, timeout=60000, wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)
        # Open the login dialog
        await page.get_by_text(LOGIN_BTN_TEXT, exact=True).first.click(timeout=10000)
        await page.wait_for_timeout(4000)

        qrcode_content = await _grab_qr(page, qrcode_path)
        baijiahao_logger.info(f"🖼️ QR code saved: {qrcode_path}")
        if qrcode_content:
            print_terminal_qrcode(qrcode_content, qrcode_path, "百度APP/手机百度")
        else:
            print(f"Could not decode the QR code, please open the file and scan it:\n  {qrcode_path}")

        if await _wait_login(page):
            baijiahao_logger.success("[+] QR-code login succeeded, saving cookie...")
            await context.storage_state(path=str(account_file))
            baijiahao_logger.success(f"[+] cookie saved: {account_file}")
        else:
            baijiahao_logger.error("[-] Timed out waiting for the QR scan (about 6 minutes), login not completed.")
        await browser.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())