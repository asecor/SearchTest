#!/usr/bin/env python3
"""Search engine test harness.

  python cli.py run [--engines a,b] [--groups g1,g2] [--force]   fetch SERPs (opens a browser)
  python cli.py doctor                                           check parsers against cached HTML
  python cli.py score                                            print scores
  python cli.py review                                           build blind rating page
  python cli.py import-ratings ratings.json                      map blind ratings back to engines
  python cli.py report                                           build data/out/report.html + CSV
"""
import argparse
import sys
from pathlib import Path

import yaml

from engines.parse import parse_serp
from queries_loader import load_queries
from review.build import build_review, import_ratings, load_manual
from runner import fetch_engine, raw_paths
from scoring.aggregate import score_all
from report.build import build_report

ROOT = Path(__file__).parent


def _csv(s):
    return [x for x in s.split(",") if x] if s else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("cmd", choices=["run", "doctor", "score", "review", "import-ratings", "report"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--engines")
    ap.add_argument("--groups")
    ap.add_argument("--ids")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--all", action="store_true", help="review: include non-manual queries too")
    a = ap.parse_args(argv)

    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    engines = _csv(a.engines) or cfg["engines"]
    queries = load_queries(_csv(a.groups), _csv(a.ids))

    if a.cmd == "run":
        for e in engines:
            fetch_engine(e, queries, cfg, force=a.force)
    elif a.cmd == "doctor":
        for e in engines:
            n_ok = n_tot = 0
            for q in queries:
                html_p = raw_paths(e, q["id"])[0]
                if html_p.exists():
                    n_tot += 1
                    n_ok += bool(parse_serp(e, html_p.read_text(encoding="utf-8"))["results"])
            status = "no data" if not n_tot else ("OK" if n_ok == n_tot else "CHECK SELECTORS")
            print(f"{e:12} parsed {n_ok}/{n_tot} SERPs with results   {status}")
    elif a.cmd == "score":
        scores, _ = score_all(engines, queries, cfg["weights"], load_manual())
        for e, s in sorted(scores.items(), key=lambda kv: -kv[1]["stars"]):
            print(f"{e:12} {s['stars']:.2f} stars  relevancy={s['relevancy'] or 0:.2f} "
                  f"answers={s['answers'] or 0:.2f} other={s['other']:.2f}")
    elif a.cmd == "review":
        qs = queries if a.all else [q for q in queries if q["kind"] == "manual"]
        print("wrote", build_review(engines, qs))
    elif a.cmd == "import-ratings":
        m = import_ratings(a.arg)
        print({e: len(v) for e, v in m.items()})
    elif a.cmd == "report":
        manual = load_manual()
        scores, overlap = score_all(engines, queries, cfg["weights"], manual)
        print("wrote", build_report(scores, overlap, queries, engines, manual))


if __name__ == "__main__":
    sys.exit(main())
