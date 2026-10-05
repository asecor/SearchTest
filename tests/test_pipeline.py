import base64
import json

import pytest

import runner
from engines.parse import parse_serp, unwrap_url
from queries_loader import load_queries
from review.build import build_review, import_ratings
from scoring import metrics
from scoring.aggregate import score_all

MOJEEK = """<html><body><ul class="results-standard">
<li><a class="title" href="https://github.com/foxlet/macOS-Simple-KVM">macOS-Simple-KVM</a><p class="s">Tools to set up a QEMU virtual machine running macOS</p></li>
<li><a class="title" href="https://example.com/kvm-switch">KVM switch</a><p class="s">keyboard video mouse switch</p></li>
</ul></body></html>"""


def test_parse_mojeek():
    p = parse_serp("mojeek", MOJEEK)
    assert [r["rank"] for r in p["results"]] == [1, 2]
    assert p["results"][0]["url"].startswith("https://github.com/foxlet")
    assert p["rewrite"] is False


def test_unwrap():
    assert unwrap_url("/url?q=https://a.com/x&sa=U") == "https://a.com/x"
    assert unwrap_url("https://duckduckgo.com/l/?uddg=https%3A%2F%2Fa.com%2Fx") == "https://a.com/x"
    assert unwrap_url("https://a.com/x") == "https://a.com/x"


def test_unwrap_bing_ck():
    dest = "https://www.rijksmuseum.nl/en/visit?a=1&b=2"
    u = "a1" + base64.urlsafe_b64encode(dest.encode()).decode().rstrip("=")
    assert unwrap_url(f"https://www.bing.com/ck/a?!&&p=abc&u={u}&ntb=1") == dest
    # not a base64 destination: left as is
    bad = "https://www.bing.com/ck/a?u=a1!!!"
    assert unwrap_url(bad) == bad


def _google_block(href, title, cite_texts, snippet="snippet"):
    cites = "".join(f"<cite>{c}</cite>" for c in cite_texts)
    return (f'<div class="MjjYud"><a href="{href}"><h3>{title}</h3></a>{cites}'
            f'<div class="VwiC3b">{snippet}</div></div>')


def test_parse_google_breadcrumb_urls():
    html = "<html><body><div id='rso'>" + "".join([
        _google_block("/goto?url=CAES1", "ripgrep", ["https://github.com › burntsushi › ripgrep"]),
        # a non-URL cite comes first, the URL cite must still be found
        _google_block("/goto?url=CAES2", "thread", ["40+ comments · 4 years ago", "https://news.ycombinator.com › item"]),
        _google_block("/goto?url=CAES3", "truncated", ["https://nl.wikipedia.org › wiki › A..."]),
        _google_block("/goto?url=CAES4", "home", ["https://www.patagonia.com › ..."]),
        # Google's own help link is not an organic result
        _google_block("https://support.google.com/websearch?p=ai_overviews", "AI Mode replied:", []),
        # no usable URL anywhere: dropped
        _google_block("/goto?url=CAES5", "no cite", ["5 comments"]),
    ]) + "</div></body></html>"
    res = parse_serp("google", html)["results"]
    assert [r["url"] for r in res] == [
        "https://github.com/burntsushi/ripgrep",
        "https://news.ycombinator.com/item",
        "https://nl.wikipedia.org/wiki/A",
        "https://www.patagonia.com",
    ]
    assert all(r["url_approx"] for r in res)
    assert [r["rank"] for r in res] == [1, 2, 3, 4]


def test_parse_swisscows():
    html = """<html><body><div class="web-results">
<article class="item web-page"><header><a class="mainlink" href="https://www.patagonia.com/home/"><h1 class="title">Patagonia Outdoor</h1></a></header>
<p class="description">Outdoor clothing</p><footer></footer></article>
<article class="video-object"><a href="https://youtu.be/x"><h2>a video</h2></a></article>
</div></body></html>"""
    res = parse_serp("swisscows", html)["results"]
    assert [(r["title"], r["url"], r["snippet"]) for r in res] == [
        ("Patagonia Outdoor", "https://www.patagonia.com/home/", "Outdoor clothing")]
    assert res[0]["url_approx"] is False


def test_parse_yandex():
    html = """<html><body><ul><li><div class="Organic">
<div class="OrganicTitle"><a class="OrganicTitle-Link" href="https://www.rijksmuseum.nl/en"><span class="OrganicTitle-LinkText">Rijksmuseum</span></a></div>
<div class="OrganicText">Tickets</div></div></li></ul></body></html>"""
    res = parse_serp("yandex", html)["results"]
    assert [(r["title"], r["url"], r["snippet"]) for r in res] == [
        ("Rijksmuseum", "https://www.rijksmuseum.nl/en", "Tickets")]


def test_metrics():
    res = [{"rank": 1, "title": "a", "url": "https://x.com", "snippet": ""},
           {"rank": 2, "title": "to be or not to be", "url": "https://github.com/foo", "snippet": ""}]
    assert metrics.score_gold(res, ["github.com/foo"]) == pytest.approx(1 / 1.58496, rel=1e-3)
    assert metrics.score_gold(res, ["nope"]) == 0
    assert metrics.score_phrase(res, "To be or not to be!") > 0
    assert metrics.score_operator(res, {"all_domain": "x.com"}) == 0.5
    assert metrics.score_spam(res, ["x.com"]) == 0.5
    parsed = {"answer": "Salem is the capital", "results": res, "rewrite": False}
    assert metrics.score_answer(parsed, r"\bSalem\b") == 1.0
    assert metrics.score_answer({**parsed, "answer": ""}, r"\bSalem\b") == 0.0


def test_all_queries_have_required_fields():
    for q in load_queries():
        if q["kind"] == "answer":
            assert q.get("answer_regex"), q["id"]
        if q["kind"] == "operator":
            assert q.get("check"), q["id"]


@pytest.fixture
def fake_raw(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RAW", tmp_path)
    d = tmp_path / "mojeek"
    d.mkdir()
    (d / "core-mac-kvm.html").write_text(MOJEEK)
    (d / "core-mac-kvm.json").write_text(json.dumps(
        {"engine": "mojeek", "qid": "core-mac-kvm", "latency_ms": 900, "captcha": False}))
    return tmp_path


def test_score_and_review(fake_raw, tmp_path, monkeypatch):
    import review.build as rb
    monkeypatch.setattr(rb, "OUT", tmp_path / "out")
    qs = load_queries(only_ids=["core-mac-kvm"])
    scores, _ = score_all(["mojeek"], qs, {"relevancy": .6, "answers": .3, "other": .1})
    # gold at rank 1 -> 1.0, both intents present (ranks 1 and 2) -> (1 + 0.63) / 2
    assert scores["mojeek"]["queries"]["core-mac-kvm"]["score"] == pytest.approx(
        (1.0 + (1.0 + 1 / 1.58496) / 2) / 2, rel=1e-3)
    path = build_review(["mojeek"], qs, seed=1)
    assert path.exists()
    rates = tmp_path / "r.json"
    rates.write_text(json.dumps({"core-mac-kvm": {"A": 3}}))
    assert import_ratings(rates) == {"mojeek": {"core-mac-kvm": 3}}
