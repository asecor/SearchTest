"""Aggregate per-query scores into per-engine results with the article's 60/30/10 weights."""
import json
import statistics
from itertools import combinations
from urllib.parse import urlparse

from engines.parse import parse_serp
from queries_loader import load_spam_domains
from runner import raw_paths

from .metrics import score_ads, score_latency, score_query


def load_run(engine, qid):
    html_p, png_p, meta_p = raw_paths(engine, qid)
    if not meta_p.exists():
        return None
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    parsed = parse_serp(engine, html_p.read_text(encoding="utf-8"))
    parsed["meta"] = meta
    parsed["screenshot"] = str(png_p)
    return parsed


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _domain(url):
    return urlparse(url).netloc.lower().removeprefix("www.")


def score_all(engines, queries, weights, manual=None):
    """Return {engine: {...}} plus overlap matrix. `manual` is {engine: {qid: 0..4}} (unblinded)."""
    spam = load_spam_domains()
    out, serps = {}, {}
    for eng in engines:
        per_q, buckets = {}, {"relevancy": [], "answers": [], "operators": []}
        lat, ads, empty = [], [], []
        for q in queries:
            parsed = load_run(eng, q["id"])
            if parsed is None:
                continue
            serps[(eng, q["id"])] = parsed
            lat.append(parsed["meta"]["latency_ms"])
            ads.append(parsed["ads"])
            if not parsed["results"] and q["kind"] != "answer":
                empty.append(q["id"])
            score, crit = score_query(q, parsed, spam)
            per_q[q["id"]] = {"score": score, "criterion": crit, "n_results": len(parsed["results"]),
                              "answer": bool(parsed["answer"]), "rewrite": parsed["rewrite"],
                              "ads": parsed["ads"], "captcha": parsed["meta"]["captcha"]}
            if score is not None:
                buckets[crit].append(score)
        if not per_q:
            continue
        rel, ans, ops = (_mean(buckets[k]) for k in ("relevancy", "answers", "operators"))
        other_parts = [(ops, 0.5), (score_latency(statistics.median(lat)), 0.25),
                       (score_ads(sum(ads) / len(ads)), 0.25)]
        other_parts = [(v, w) for v, w in other_parts if v is not None]
        other = sum(v * w for v, w in other_parts) / sum(w for _, w in other_parts)
        parts = [(rel, weights["relevancy"]), (ans, weights["answers"]), (other, weights["other"])]
        parts = [(v, w) for v, w in parts if v is not None]
        total = sum(v * w for v, w in parts) / sum(w for _, w in parts)
        m = (manual or {}).get(eng, {})
        out[eng] = {
            "stars": round(4 * total, 2),
            "relevancy": rel, "answers": ans, "operators": ops, "other": other,
            "median_latency_ms": statistics.median(lat), "avg_ads": sum(ads) / len(ads),
            "manual_stars": round(sum(m.values()) / len(m), 2) if m else None,
            "queries": per_q, "empty_serps": empty,
        }
    return out, overlap_matrix(serps, engines, queries)


def overlap_matrix(serps, engines, queries):
    """Mean Jaccard overlap of top-10 domains+paths between engine pairs (index independence)."""
    sets = {}
    for (eng, qid), p in serps.items():
        sets.setdefault(qid, {})[eng] = {_domain(r["url"]) + urlparse(r["url"]).path.rstrip("/")
                                         for r in p["results"]}
    matrix = {}
    for a, b in combinations(engines, 2):
        vals = []
        for per_eng in sets.values():
            if a in per_eng and b in per_eng and (per_eng[a] | per_eng[b]):
                vals.append(len(per_eng[a] & per_eng[b]) / len(per_eng[a] | per_eng[b]))
        if vals:
            matrix[f"{a}|{b}"] = sum(vals) / len(vals)
    return matrix
