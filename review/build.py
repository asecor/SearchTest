"""Blind manual review: anonymised, shuffled SERPs rated 0-4 in a local HTML page."""
import html
import json
import random
from pathlib import Path

from scoring.aggregate import load_run

OUT = Path(__file__).resolve().parent.parent / "data" / "out"
LABELS = "ABCDEFGHIJKLMNOP"


def build_review(engines, queries, seed=None):
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    key, cards = {}, []
    for q in queries:
        runs = [(e, load_run(e, q["id"])) for e in engines]
        runs = [(e, p) for e, p in runs if p is not None]
        if not runs:
            continue
        rng.shuffle(runs)
        key[q["id"]] = {LABELS[i]: e for i, (e, _) in enumerate(runs)}
        panels = []
        for i, (_, p) in enumerate(runs):
            lis = "".join(
                f"<li><b>{html.escape(r['title'])}</b><br><span class=u>{html.escape(r['url'])}</span>"
                f"<br>{html.escape(r['snippet'])}</li>" for r in p["results"][:8]
            ) or "<li><i>no results parsed</i></li>"
            ans = f"<div class=ans><b>Answer box:</b> {html.escape(p['answer'][:400])}</div>" if p["answer"] else ""
            qid, lab = q["id"], LABELS[i]
            radios = "".join(
                f"<label><input type=radio name={qid}-{lab} value={v}>{v}</label>" for v in range(5)
            )
            panels.append(
                f"<div class=panel data-q='{qid}' data-l='{lab}'><h3>{lab}</h3>{ans}<ol>{lis}</ol>"
                f"<div class=rate>{radios}</div></div>"
            )
        cards.append(f"<section><h2>{html.escape(q['q'])} <small>{q['id']}</small></h2><div class=grid>{''.join(panels)}</div></section>")
    (OUT / "review_key.json").write_text(json.dumps(key, indent=2), encoding="utf-8")
    page = f"""<!doctype html><meta charset=utf-8><title>Blind review</title>
<style>body{{font:14px system-ui;margin:20px;max-width:1500px}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px}}
.panel{{border:1px solid #8884;border-radius:6px;padding:8px}}.u{{color:#2a7;font-size:12px;word-break:break-all}}li{{margin-bottom:6px}}
.rate label{{margin-right:10px}}.ans{{background:#ff02;padding:4px;margin-bottom:4px}}h2 small{{opacity:.5}}</style>
<h1>Blind review</h1><p>Rate each result page 0 (useless) to 4 (excellent). Ratings save in this browser. Click Export when done, then run <code>python cli.py import-ratings ratings.json</code>.</p>
<button onclick=exp()>Export ratings</button> <span id=n></span>{''.join(cards)}
<script>
const K='searchtest-ratings';let r=JSON.parse(localStorage.getItem(K)||'{{}}');
document.querySelectorAll('.panel').forEach(p=>{{const q=p.dataset.q,l=p.dataset.l;
 if(r[q]&&r[q][l]!==undefined){{const i=p.querySelector('input[value="'+r[q][l]+'"]');if(i)i.checked=true}}
 p.querySelectorAll('input').forEach(i=>i.onchange=()=>{{r[q]=r[q]||{{}};r[q][l]=+i.value;localStorage.setItem(K,JSON.stringify(r));cnt()}})}});
function cnt(){{document.getElementById('n').textContent=Object.values(r).reduce((a,x)=>a+Object.keys(x).length,0)+' rated'}}cnt();
function exp(){{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(r,null,2)]));a.download='ratings.json';a.click()}}
</script>"""
    path = OUT / "review.html"
    path.write_text(page, encoding="utf-8")
    return path


def import_ratings(ratings_path):
    """Map blind ratings back to engines. Returns {engine: {qid: rating}} and saves it."""
    key = json.loads((OUT / "review_key.json").read_text(encoding="utf-8"))
    ratings = json.loads(Path(ratings_path).read_text(encoding="utf-8"))
    manual = {}
    for qid, labels in ratings.items():
        for label, val in labels.items():
            eng = key.get(qid, {}).get(label)
            if eng:
                manual.setdefault(eng, {})[qid] = val
    (OUT / "manual.json").write_text(json.dumps(manual, indent=2), encoding="utf-8")
    return manual


def load_manual():
    p = OUT / "manual.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
