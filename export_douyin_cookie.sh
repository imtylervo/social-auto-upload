#!/bin/bash
# export_douyin_cookie.sh
# Export the Douyin cookies of a logged-in Chrome to douyin_{8 random characters}.json
# Uses curl to call the Chrome DevTools HTTP API directly

set -e

# Parse arguments
USERNAME=""
while [ $# -gt 0 ]; do
    case "$1" in
        --account)
            USERNAME="$2"
            shift 2
            ;;
        *)
            echo "Usage: $0 --account <username>"
            exit 1
            ;;
    esac
done

if [ -z "$USERNAME" ]; then
    echo "No username given; a random file name will be used"
fi

DEBUG_PORT=9222

echo "=========================================="
echo "   Douyin Cookie Export Tool"
echo "=========================================="
echo ""

# Dependencies: curl, python3, websocket-client

echo "Checking Chrome remote debugging..."
RESPONSE=$(curl -s "http://localhost:${DEBUG_PORT}/json" 2>/dev/null) || true

if ! echo "$RESPONSE" | grep -q "webSocketDebuggerUrl"; then
    echo "Chrome remote debugging is not running"
    echo "Start Chrome first: chromium --remote-debugging-port=9222 ..."
    exit 1
fi

echo "Chrome remote debugging is running"
echo ""
echo "Getting Douyin cookies..."

USERNAME="$USERNAME" python3 << 'PYEOF'
import json
import os
import uuid
import sys

# The shell passes USERNAME as an environment variable; Python has to read it explicitly
USERNAME = os.environ.get('USERNAME', '')

DEBUG_PORT = 9222
if USERNAME:
    COOKIE_FILE = f"cookies/douyin_{USERNAME}.json"
else:
    COOKIE_FILE = f"cookies/douyin_{uuid.uuid4().hex[:8]}.json"

def get_douyin_cookies():
    import urllib.request
    import websocket

    # Get the list of pages
    url = f"http://localhost:{DEBUG_PORT}/json"
    with urllib.request.urlopen(url, timeout=10) as response:
        pages = json.loads(response.read().decode())

    # Find the Douyin creator page
    douyin_page = None
    for page in pages:
        page_url = page.get("url", "")
        if "creator.douyin.com" in page_url:
            douyin_page = page
            break

    if not douyin_page:
        print("Douyin creator platform page not found")
        print("Open https://creator.douyin.com in Chrome and log in first")
        return False

    page_url = douyin_page["url"]
    ws_url = douyin_page.get("webSocketDebuggerUrl", "")

    print(f"Found page: {page_url}")

    # Connect to the target page's WebSocket
    print(f"Connecting to the page WebSocket...")
    ws = websocket.create_connection(ws_url, timeout=30)

    # Get all cookies
    ws.send(json.dumps({"id": 1, "method": "Network.getAllCookies"}))
    response = json.loads(ws.recv())

    cookies = response.get("result", {}).get("cookies", [])

    # Keep only Douyin cookies
    douyin_cookies = [
        c for c in cookies
        if "douyin.com" in c.get("domain", "") or ".douyin.com" in c.get("domain", "")
    ]

    print(f"Got {len(douyin_cookies)} Douyin cookies")

    if len(douyin_cookies) == 0:
        print("No Douyin cookies found; probably not logged in")
        return False

    # Get localStorage (origins)
    print(f"Getting localStorage...")
    local_storage_by_origin = {}

    # Get the page's frame tree
    ws.send(json.dumps({"id": 2, "method": "Page.getResourceTree"}))
    resp = json.loads(ws.recv())
    frames = resp.get("result", {}).get("frameTree", {}).get("childFrames", [])
    all_frames = [resp.get("result", {}).get("frameTree", {})] + frames

    for frame in all_frames:
        frame_url = frame.get("url", "")
        frame_id = frame.get("id", "")
        if "douyin.com" in frame_url or "bytedance.com" in frame_url:
            # Run JavaScript to get this frame's localStorage
            script = """
            (function() {
                var result = [];
                for (var i = 0; i < localStorage.length; i++) {
                    var key = localStorage.key(i);
                    result.push([key, localStorage.getItem(key)]);
                }
                return result;
            })()
            """
            ws.send(json.dumps({
                "id": 3,
                "method": "Runtime.evaluate",
                "params": {"expression": script, "contextId": frame.get("id")}
            }))
            resp = json.loads(ws.recv())
            result_eval = resp.get("result", {})
            if result_eval.get("result", {}).get("type") == "array":
                items = result_eval.get("result", {}).get("value", [])
                if items:
                    origin = frame_url.rsplit("/", 2)[0] + "//" + frame_url.split("/")[2]
                    local_storage_by_origin[origin] = items

    # Get the main document's localStorage
    script_main = """
    (function() {
        var result = [];
        try {
            for (var i = 0; i < localStorage.length; i++) {
                var key = localStorage.key(i);
                result.push([key, localStorage.getItem(key)]);
            }
        } catch(e) {}
        return result;
    })()
    """
    ws.send(json.dumps({
        "id": 4,
        "method": "Runtime.evaluate",
        "params": {"expression": script_main}
    }))
    resp = json.loads(ws.recv())
    result_eval = resp.get("result", {})
    if result_eval.get("result", {}).get("type") == "array":
        items = result_eval.get("result", {}).get("value", [])
        if items:
            origin = page_url.rsplit("/", 2)[0] + "//" + page_url.split("/")[2]
            local_storage_by_origin[origin] = items

    ws.close()

    # Build the JSON
    result = {
        "cookies": [],
        "origins": []
    }

    for c in douyin_cookies:
        result["cookies"].append({
            "name": c.get("name", ""),
            "value": c.get("value", ""),
            "domain": c.get("domain", ""),
            "path": c.get("path", "/"),
            "expires": c.get("expires", -1),
            "httpOnly": c.get("httpOnly", False),
            "secure": c.get("secure", True),
            "sameSite": c.get("sameSite", "Lax")
        })

    # Add origins
    for origin, items in local_storage_by_origin.items():
        origin_entry = {
            "origin": origin,
            "localStorage": [{"name": name, "value": value} for name, value in items]
        }
        result["origins"].append(origin_entry)

    # Save
    os.makedirs("cookies", exist_ok=True)
    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Cookies saved to: {COOKIE_FILE}")
    print("")

    # Print the key cookies
    key_cookies = ["sessionid", "uid_tt", "ssid", "ttwid"]
    print("Key cookies:")
    for c in douyin_cookies:
        if c.get("name") in key_cookies:
            val = c.get("value", "")
            if len(val) > 30:
                val = val[:30] + "..."
            print(f"   {c.get('name')}: {val}")

    return True

if __name__ == "__main__":
    if not get_douyin_cookies():
        sys.exit(1)
PYEOF

echo ""
echo "=========================================="
echo "   Done! File exported as $COOKIE_FILE"
echo "=========================================="