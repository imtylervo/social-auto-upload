import configparser
import json
import pathlib
from time import sleep

import requests
from playwright.sync_api import sync_playwright

from conf import BASE_DIR, XHS_SERVER, LOCAL_CHROME_HEADLESS

config = configparser.RawConfigParser()
config.read('accounts.ini')


def sign_local(uri, data=None, a1="", web_session=""):
    for _ in range(10):
        try:
            with sync_playwright() as playwright:
                stealth_js_path = pathlib.Path(BASE_DIR / "utils/stealth.min.js")
                chromium = playwright.chromium

                # If this keeps failing, try setting it to False so the browser opens; adding a sleep lets you watch the browser state
                browser = chromium.launch(headless=LOCAL_CHROME_HEADLESS)

                browser_context = browser.new_context()
                browser_context.add_init_script(path=stealth_js_path)
                context_page = browser_context.new_page()
                context_page.goto("https://www.xiaohongshu.com")
                browser_context.add_cookies([
                    {'name': 'a1', 'value': a1, 'domain': ".xiaohongshu.com", 'path': "/"}]
                )
                context_page.reload()
                # After the browser cookie is set here, getting the signature fails without a short sleep; if it fails often, try a longer sleep
                sleep(2)
                encrypt_params = context_page.evaluate("([url, data]) => window._webmsxyw(url, data)", [uri, data])
                return {
                    "x-s": encrypt_params["X-s"],
                    "x-t": str(encrypt_params["X-t"])
                }
        except Exception:
            # This sometimes hits "window._webmsxyw is not a function" or an unknown redirect error, so retry on failure
            pass
    raise Exception("Signing still failed after all these retries. Giving up")


def sign(uri, data=None, a1="", web_session=""):
    # Fill in the address and port of your own flask signing service
    res = requests.post(f"{XHS_SERVER}/sign",
                        json={"uri": uri, "data": data, "a1": a1, "web_session": web_session})
    signs = res.json()
    return {
        "x-s": signs["x-s"],
        "x-t": signs["x-t"]
    }


def beauty_print(data: dict):
    print(json.dumps(data, ensure_ascii=False, indent=2))
