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
