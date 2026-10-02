# SearchTest

Search engine comparison harness, modelled on the 2020 LibreTechTips article
("Detailed tests of search engines") with automated scoring and a blind manual layer.
Runs on your own machine so your IP is not blocked. Locale: English / Netherlands.

Engines: Google, Bing, DuckDuckGo, Startpage, MetaGer, Ecosia, Swisscows, Qwant, Yandex, Mojeek, Brave, Marginalia.

## Setup

```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chrome      # or set browser.channel: chromium in config.yaml
```

## Workflow

```
python cli.py run --engines mojeek,brave --groups core2020   # start small
python cli.py doctor                                         # do the selectors still parse?
python cli.py run                                            # everything (resumable)
python cli.py score
python cli.py review                                         # open data/out/review.html, rate blind, Export
python cli.py import-ratings ~/Downloads/ratings.json
python cli.py report                                         # data/out/report.html + results.csv
```

`run` opens a visible Chrome window, waits 8-20 s between queries, and caches raw HTML plus a
screenshot per (engine, query) in `data/raw/`. If an engine shows a CAPTCHA, solve it in the
window and the run continues. Rerunning skips cached queries (`--force` to refetch).
A full run is roughly 3-4 hours; use `--engines` and `--groups` to split it.

## Scoring

Weights follow the article: relevancy 60%, instant answers 30%, other 10%. Stars are out of 4.

- Relevancy: nDCG@10 of gold URLs, verbatim-phrase rank, intent coverage (disambiguation), affiliate-spam share. A query rewrite costs 0.15.
- Answers: 1.0 correct text in a dedicated answer box, 0.5 only in the top-5 organic results, 0 otherwise.
- Other: operator pass rate (50%), median latency (25%), ads per page (25%).
- Manual: blind 0-4 ratings, shown next to the automated stars, not mixed in.
- Overlap: top-10 Jaccard between engines, to show which share an index.

## Queries

`queries/core_2020.yaml` holds the article's 8 queries verbatim, plus an EUR variant of the currency query.
Other files add technical, navigational, operator, instant-answer, spam and manual (news, local, non-English, typo, ambiguity) queries.
Add your own by dropping a YAML file in `queries/`.

## Known limits

- Selectors in `engines/specs.py` were written without access to the live sites and are unverified. Expect to fix several after the first fetch: run `doctor`, open the cached HTML in `data/raw/<engine>/`, adjust the spec, rerun `score`. No refetch needed.
- Answer correctness is regex-based; live values (currency, weather) are matched by format, not by number.
- Snippets are truncated by engines, so exact-phrase checks can miss a true hit.
- Results vary with IP location and cookies; the persistent profile per engine is in `data/profiles/`.
