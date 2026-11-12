# -*- coding: utf-8 -*-
"""Get the Alipay Life Account cookie: open the browser, log in by scanning the QR code, and the cookie is saved automatically to cookies/alipay_uploader/account.json"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uploader.alipay_uploader.main import alipay_cookie_gen


async def main():
    account_file = Path(__file__).resolve().parents[1] / "cookies" / "alipay_uploader" / "account.json"
    await alipay_cookie_gen(str(account_file))


if __name__ == "__main__":
    asyncio.run(main())
