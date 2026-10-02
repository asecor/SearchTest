"""Parse a saved SERP (raw HTML) into structured results using engines/specs.py."""
import re
from urllib.parse import parse_qs, unquote, urlparse

from bs4 import BeautifulSoup

from .specs import REWRITE_TEXT, SPECS


def _first(node, selectors):
    for sel in selectors:
        try:
            found = node.select_one(sel)
        except Exception:
            found = None
        if found is not None:
            return found
    return None


def _select(node, selectors):
    for sel in selectors:
        try:
            found = node.select(sel)
        except Exception:
            found = []
        if found:
            return found
    return []


def unwrap_url(href):
    """Strip redirect wrappers (Google /url?q=, DDG uddg=, Bing u=)."""
    if not href:
        return ""
    p = urlparse(href)
    qs = parse_qs(p.query)
    for key in ("uddg", "q", "url", "u"):
        if key in qs and qs[key][0].startswith("http") and (
            p.path.startswith(("/url", "/l/")) or key == "uddg"
        ):
            return unquote(qs[key][0])
    return href


def _text(node):
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)) if node else ""


def parse_serp(engine, html):
    spec = SPECS[engine]
    soup = BeautifulSoup(html, "lxml")

    results = []
    for node in _select(soup, spec["result"]):
        title_el = _first(node, spec["title"])
        link_el = _first(node, spec["link"])
        href = unwrap_url(link_el.get("href", "") if link_el else "")
        if not href.startswith("http"):
            continue
        results.append({
            "rank": len(results) + 1,
            "title": _text(title_el),
            "url": href,
            "snippet": _text(_first(node, spec["snippet"])),
        })
        if len(results) >= 10:
            break

    ads = 0
    for sel in spec["ads"]:
        try:
            ads = len(soup.select(sel))
        except Exception:
            ads = 0
        if ads:
            break

    answer = ""
    for sel in spec["answer"]:
        try:
            nodes = soup.select(sel)
        except Exception:
            nodes = []
        if nodes:
            answer = _text(nodes[0])[:2000]
            break

    page_text = _text(soup.body or soup)[:6000].lower()
    rewrite = any(_first(soup, [s]) for s in spec["rewrite"]) or any(
        re.search(p, page_text) for p in REWRITE_TEXT
    )

    return {"results": results, "ads": ads, "answer": answer, "rewrite": bool(rewrite)}
