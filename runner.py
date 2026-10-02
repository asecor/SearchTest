"""Playwright runner: fetch each (engine, query) once, cache HTML + screenshot + meta."""
import json
import random
import time
from pathlib import Path
from urllib.parse import quote_plus

from engines.specs import CAPTCHA_MARKERS, SPECS

ROOT = Path(__file__).parent
RAW = ROOT / "data" / "raw"
PROFILES = ROOT / "data" / "profiles"


def raw_paths(engine, qid):
    d = RAW / engine
    return d / f"{qid}.html", d / f"{qid}.png", d / f"{qid}.json"


def is_cached(engine, qid):
    return raw_paths(engine, qid)[2].exists()


def _try_click(page, selectors):
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=800):
                loc.click(timeout=2000)
                return True
        except Exception:
            continue
    return False


def _blocked(page, spec):
    try:
        body = page.inner_text("body", timeout=3000).lower()
    except Exception:
        body = ""
    has_results = any(page.locator(s).count() for s in spec["result"])
    return (not has_results) and any(m in body for m in CAPTCHA_MARKERS)


def fetch_engine(engine, queries, cfg, force=False, log=print):
    from playwright.sync_api import sync_playwright

    spec = SPECS[engine]
    loc, br, pace = cfg["locale"], cfg["browser"], cfg["pacing"]
    todo = [q for q in queries if force or not is_cached(engine, q["id"])]
    todo = todo[: pace["max_queries_per_session"]]
    if not todo:
        log(f"[{engine}] nothing to fetch")
        return

    profile = PROFILES / engine
    profile.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        kwargs = dict(
            user_data_dir=str(profile),
            headless=br["headless"],
            locale=loc["browser_locale"],
            timezone_id=loc["timezone"],
            viewport=br["viewport"],
            extra_http_headers={"Accept-Language": loc["accept_language"]},
        )
        if br.get("channel") and br["channel"] != "chromium":
            kwargs["channel"] = br["channel"]
        ctx = p.chromium.launch_persistent_context(**kwargs)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        for i, q in enumerate(todo, 1):
            html_p, png_p, meta_p = raw_paths(engine, q["id"])
            html_p.parent.mkdir(parents=True, exist_ok=True)
            url = spec["url"].format(q=quote_plus(q["q"]))
            log(f"[{engine}] {i}/{len(todo)} {q['id']}")
            t0 = time.perf_counter()
            captcha = False
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                _try_click(page, spec["consent"])
                try:
                    page.wait_for_selector(", ".join(spec["ready"]), timeout=15000)
                except Exception:
                    pass
                latency_ms = int((time.perf_counter() - t0) * 1000)
                try:
                    page.wait_for_load_state("networkidle", timeout=6000)
                except Exception:
                    pass
                if _blocked(page, spec):
                    captcha = True
                    log(f"[{engine}] bot check. Solve it in the browser window "
                        f"(waiting up to {pace['captcha_wait']}s)...")
                    deadline = time.time() + pace["captcha_wait"]
                    while time.time() < deadline and _blocked(page, spec):
                        time.sleep(3)
                    page.wait_for_timeout(1500)
                html_p.write_text(page.content(), encoding="utf-8")
                page.screenshot(path=str(png_p), full_page=True)
                meta_p.write_text(json.dumps({
                    "engine": engine, "qid": q["id"], "q": q["q"], "url": page.url,
                    "latency_ms": latency_ms, "captcha": captcha,
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }, indent=2), encoding="utf-8")
            except Exception as e:
                log(f"[{engine}] FAILED {q['id']}: {e}")
            if i < len(todo):
                time.sleep(random.uniform(pace["min_delay"], pace["max_delay"]))
        ctx.close()
