"""Load query definitions from queries/*.yaml."""
from pathlib import Path

import yaml

QUERY_DIR = Path(__file__).parent / "queries"
KINDS = {"relevance", "phrase", "answer", "operator", "spam", "manual"}


def load_queries(only_groups=None, only_ids=None):
    queries, seen = [], set()
    for path in sorted(QUERY_DIR.glob("*.yaml")):
        for q in yaml.safe_load(path.read_text(encoding="utf-8")) or []:
            if q["kind"] not in KINDS:
                raise ValueError(f"{q['id']}: unknown kind {q['kind']}")
            if q["id"] in seen:
                raise ValueError(f"duplicate query id {q['id']}")
            seen.add(q["id"])
            q["file"] = path.name
            q.setdefault("group", path.stem)
            if only_groups and q["group"] not in only_groups:
                continue
            if only_ids and q["id"] not in only_ids:
                continue
            queries.append(q)
    return queries


def load_spam_domains():
    path = QUERY_DIR / "spam_domains.txt"
    return [
        l.strip().lower()
        for l in path.read_text(encoding="utf-8").splitlines()
        if l.strip() and not l.startswith("#")
    ]
