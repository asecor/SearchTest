"""Static HTML report + CSV."""
import csv
import html
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "out"

# Final weighted scores (out of 4 stars) from the 2020 LibreTechTips article.
ARTICLE_2020 = {"google": 2.98, "startpage": 1.45, "bing": 1.60, "duckduckgo": 1.48, "metager": 0.78,
                "ecosia": 1.15, "swisscows": 1.33, "qwant": 0.93, "yandex": 0.83, "mojeek": 1.18}


def _pct(v):
    return "-" if v is None else f"{v * 100:.0f}%"


def _heat(v):
    if v is None:
        return "<td>-</td>"
    hue = int(120 * max(0, min(1, v)))
    return f"<td style='background:hsl({hue} 55% 35% / .55)'>{v * 100:.0f}%</td>"


def build_report(scores, overlap, queries, engines, manual):
    OUT.mkdir(parents=True, exist_ok=True)
    engines = [e for e in engines if e in scores]
    ranked = sorted(engines, key=lambda e: -scores[e]["stars"])

    lead = "".join(
        f"<tr><td>{i}</td><td>{e}</td><td><b>{scores[e]['stars']:.2f}</b></td>"
        f"<td>{'-' if scores[e]['manual_stars'] is None else scores[e]['manual_stars']}</td>"
        f"<td>{ARTICLE_2020.get(e, '-')}</td>"
        f"{_heat(scores[e]['relevancy'])}{_heat(scores[e]['answers'])}{_heat(scores[e]['operators'])}"
        f"<td>{scores[e]['median_latency_ms'] / 1000:.1f}s</td><td>{scores[e]['avg_ads']:.1f}</td>"
        f"<td>{len(scores[e]['empty_serps']) or ''}</td></tr>"
        for i, e in enumerate(ranked, 1)
    )

    groups = {}
    for q in queries:
        groups.setdefault(q["group"], []).append(q)
    qtables = []
    for g, qs in groups.items():
        head = "".join(f"<th>{e}</th>" for e in ranked)
        rows = ""
        for q in qs:
            cells = ""
            for e in ranked:
                d = scores[e]["queries"].get(q["id"])
                if d is None:
                    cells += "<td>n/a</td>"
                elif d["score"] is None:
                    m = manual.get(e, {}).get(q["id"])
                    cells += f"<td>{'manual' if m is None else f'{m}/4'}</td>"
                else:
                    flag = " ⚑" if d["rewrite"] else ""
                    cells += _heat(d["score"]).replace("</td>", f"{flag}</td>")
            rows += f"<tr><td>{html.escape(q['q'])}</td>{cells}</tr>"
        qtables.append(f"<h3>{g}</h3><table><tr><th>query</th>{head}</tr>{rows}</table>")

    ov_rows = ""
    for a in ranked:
        cells = ""
        for b in ranked:
            v = 1.0 if a == b else overlap.get(f"{a}|{b}", overlap.get(f"{b}|{a}"))
            cells += _heat(v)
        ov_rows += f"<tr><th>{a}</th>{cells}</tr>"
    ov = f"<table><tr><th></th>{''.join(f'<th>{e}</th>' for e in ranked)}</tr>{ov_rows}</table>"

    page = f"""<!doctype html><meta charset=utf-8><title>Search engine test</title>
<style>body{{font:14px system-ui;margin:24px;max-width:1400px}}table{{border-collapse:collapse;margin-bottom:24px}}
td,th{{border:1px solid #8884;padding:4px 8px;text-align:right}}td:first-child,th:first-child{{text-align:left}}small{{opacity:.6}}</style>
<h1>Search engine test</h1>
<p><small>Locale en-NL. Weights: relevancy 60%, instant answers 30%, other 10% (as in the 2020 article). Stars out of 4. ⚑ = engine rewrote the query.</small></p>
<h2>Leaderboard</h2>
<table><tr><th>#</th><th>engine</th><th>auto stars</th><th>manual stars</th><th>2020 article</th><th>relevancy</th><th>answers</th><th>operators</th><th>median latency</th><th>avg ads</th><th>empty SERPs</th></tr>{lead}</table>
<h2>Per query</h2>{''.join(qtables)}
<h2>Result overlap (index independence)</h2><p><small>Mean Jaccard overlap of top-10 results. High overlap means a shared index.</small></p>{ov}"""
    path = OUT / "report.html"
    path.write_text(page, encoding="utf-8")

    with open(OUT / "results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["engine", "query_id", "criterion", "score", "n_results", "answer_box", "rewrite", "ads", "captcha"])
        for e in engines:
            for qid, d in scores[e]["queries"].items():
                w.writerow([e, qid, d["criterion"], "" if d["score"] is None else round(d["score"], 3),
                            d["n_results"], d["answer"], d["rewrite"], d["ads"], d["captcha"]])
    (OUT / "scores.json").write_text(json.dumps(scores, indent=2, default=str), encoding="utf-8")
    return path
