"""Mint and persist a fresh chat.sakana.ai guest session with headless Playwright.

chat.sakana.ai hands anonymous visitors a `sakana-chat` guest id (behind a
Cloudflare `cf_clearance` cookie). That guest allowance runs out, at which
point the API replies 429 「利用量の上限に達しました」. Loading the site again in a
fresh browser context yields a brand new guest id, so we drive a headless
browser to do exactly that and hand the cookies back to the requests client.
"""

import json
import os
import threading
import time

UA = os.environ.get(
    "SAKANA_UA",
    "Mozilla/5.0 (X11; Linux x86_64; rv:152.0) Gecko/20100101 Firefox/152.0",
)
SESSION_URL = "https://chat.sakana.ai/"
SESSION_FILE = os.environ.get(
    "SAKANA_SESSION_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "sakana_session.json"),
)
# Playwright's sync API owns a subprocess and must not be entered concurrently.
_refresh_lock = threading.Lock()


def load_session():
    """Return a persisted {cf_clearance, sakana_chat, ua, ts} dict, or None."""
    try:
        with open(SESSION_FILE) as f:
            data = json.load(f)
        if data.get("cf_clearance") and data.get("sakana_chat"):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return None


def save_session(data):
    _atomic_write(SESSION_FILE, data)


POOL_FILE = os.environ.get(
    "SAKANA_POOL_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "sakana_pool.json"),
)


def load_pool():
    """Return a list of persisted session dicts, or []."""
    try:
        with open(POOL_FILE) as f:
            data = json.load(f)
        return [
            s for s in data
            if isinstance(s, dict) and s.get("cf_clearance") and s.get("sakana_chat")
        ]
    except (OSError, json.JSONDecodeError):
        return []


def save_pool(sessions):
    _atomic_write(POOL_FILE, list(sessions))


def _atomic_write(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


def _grab_session(ctx, page, timeout_ms, settle_ms):
    """Drive one context to a fresh guest session; return dict or None."""
    page.goto(SESSION_URL, wait_until="domcontentloaded", timeout=timeout_ms)
    # Let Cloudflare's JS challenge settle and the guest cookie land.
    deadline = time.time() + settle_ms / 1000
    cookies = {}
    while time.time() < deadline:
        page.wait_for_timeout(1000)
        cookies = {c["name"]: c["value"] for c in ctx.cookies()}
        if cookies.get("cf_clearance") and cookies.get("sakana-chat"):
            break
    cf = cookies.get("cf_clearance")
    chat = cookies.get("sakana-chat")
    if not cf or not chat:
        return None
    return {"cf_clearance": cf, "sakana_chat": chat, "ua": UA, "ts": time.time()}


def mint_sessions(n=1, timeout_ms=60000, settle_ms=6000, gap_ms=1500):
    """Mint up to `n` fresh guest sessions in a single browser launch.

    Each session comes from its own browser context (a fresh cookie jar, so
    Cloudflare issues a new guest id). Returns a list of session dicts, one
    per context that produced valid cookies (deduped by guest id).
    """
    with _refresh_lock:
        from playwright.sync_api import sync_playwright

        results = []
        seen = set()
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            try:
                for i in range(n):
                    ctx = browser.new_context(
                        user_agent=UA,
                        viewport={"width": 1280, "height": 800},
                        locale="en-US",
                    )
                    try:
                        page = ctx.new_page()
                        data = _grab_session(ctx, page, timeout_ms, settle_ms)
                    finally:
                        ctx.close()
                    if data and data["sakana_chat"] not in seen:
                        seen.add(data["sakana_chat"])
                        results.append(data)
                    if i < n - 1:
                        time.sleep(gap_ms / 1000)
            finally:
                browser.close()
    return results


def refresh_session(persist=True, timeout_ms=60000, settle_ms=6000):
    """Mint a single fresh guest session; persist to SESSION_FILE by default."""
    sessions = mint_sessions(1, timeout_ms=timeout_ms, settle_ms=settle_ms)
    if not sessions:
        raise RuntimeError(
            "session refresh failed: no cookies "
            "(Cloudflare challenge may have blocked the headless browser)"
        )
    data = sessions[0]
    if persist:
        save_session(data)
    return data


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    got = mint_sessions(n)
    for d in got:
        print("sakana_chat", d["sakana_chat"], "cf len", len(d["cf_clearance"]))
    if got:
        save_pool(got)
        print(f"minted {len(got)} session(s), saved to {POOL_FILE}")
