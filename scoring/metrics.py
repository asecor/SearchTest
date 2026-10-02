"""Per-query scoring. Every scorer returns a float in [0, 1] (or None if not applicable)."""
import math
import re
from urllib.parse import urlparse

REWRITE_PENALTY = 0.15


def _blob(r):
    return f"{r['title']} {r['url']} {r['snippet']}".lower()


def _norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s.lower())).strip()


def ndcg_single(rank):
    """nDCG@10 with a single relevant item at `rank` (1-based); 0 if absent."""
    return 1 / math.log2(rank + 1) if rank else 0.0


def first_rank(results, pred):
    for r in results:
        if pred(r):
            return r["rank"]
    return None


def score_gold(results, gold):
    gold = [g.lower() for g in gold]
    return ndcg_single(first_rank(results, lambda r: any(g in r["url"].lower() for g in gold)))


def score_phrase(results, phrase):
    p = _norm(phrase)
    return ndcg_single(first_rank(results, lambda r: p in _norm(f"{r['title']} {r['snippet']}")))


def score_intents(results, intents):
    """Mean over intents of 1/log2(first_rank+1); rewards balanced early coverage."""
    if not intents:
        return None
    total = 0.0
    for patterns in intents.values():
        rx = [re.compile(p, re.I) for p in patterns]
        total += ndcg_single(first_rank(results, lambda r: any(x.search(_blob(r)) for x in rx)))
    return total / len(intents)


def score_spam(results, spam_domains):
    if not results:
        return 0.0
    bad = sum(1 for r in results if any(d in r["url"].lower() for d in spam_domains))
    return 1 - bad / len(results)


def score_operator(results, check):
    if not results:
        return 0.0
    n = len(results)
    if "all_domain" in check:
        d = check["all_domain"].lower()
        return sum(d in urlparse(r["url"]).netloc.lower() for r in results) / n
    if "url_endswith" in check:
        e = check["url_endswith"].lower()
        return sum(urlparse(r["url"]).path.lower().endswith(e) for r in results) / n
    if "exclude" in check:
        words = [w.lower() for w in check["exclude"]]
        return sum(not any(w in f"{r['title']} {r['snippet']}".lower() for w in words)
                   for r in results) / n
    if "phrase" in check:
        p = _norm(check["phrase"])
        hits = sum(p in _norm(f"{r['title']} {r['snippet']}") for r in results)
        return min(1.0, hits / 5)
    if "intitle" in check:
        p = _norm(check["intitle"])
        hits = sum(p in _norm(r["title"]) for r in results)
        return min(1.0, hits / 7)
    raise ValueError(f"unknown operator check {check}")


def score_answer(parsed, answer_regex, results=None):
    """0 = nothing, 0.5 = correct text only in organic results, 1 = in a dedicated answer block."""
    rx = re.compile(answer_regex, re.I)
    if parsed["answer"] and rx.search(parsed["answer"]):
        return 1.0
    results = results if results is not None else parsed["results"]
    if any(rx.search(f"{r['title']} {r['snippet']}") for r in results[:5]):
        return 0.5
    return 0.0


def score_query(q, parsed, spam_domains):
    """Return (score or None, criterion) for one parsed SERP."""
    kind, res = q["kind"], parsed["results"]
    if kind == "manual":
        return None, "manual"
    if kind == "answer":
        return score_answer(parsed, q["answer_regex"]), "answers"
    if kind == "operator":
        return score_operator(res, q["check"]), "operators"
    if kind == "spam":
        return score_spam(res, spam_domains), "relevancy"
    # relevance / phrase
    parts = []
    if q.get("gold"):
        parts.append(score_gold(res, q["gold"]))
    if q.get("phrase"):
        parts.append(score_phrase(res, q["phrase"]))
    if q.get("intents"):
        parts.append(score_intents(res, q["intents"]))
    if not parts:
        return None, "manual"
    score = sum(parts) / len(parts)
    if parsed["rewrite"]:
        score = max(0.0, score - REWRITE_PENALTY)
    return score, "relevancy"


def score_latency(median_ms):
    """<=1s -> 1.0, >=5s -> 0.0, linear between."""
    return max(0.0, min(1.0, (5000 - median_ms) / 4000))


def score_ads(avg_ads):
    """0 ads -> 1.0, >=4 -> 0.0."""
    return max(0.0, min(1.0, 1 - avg_ads / 4))
