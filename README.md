# SearchTest

Search engine comparison harness, modelled on the 2020 LibreTechTips article
("Detailed tests of search engines") with automated scoring and a blind manual layer.
Runs on your own machine so your IP is not blocked. Locale: English / Netherlands.

Engines tested: Google, Bing, DuckDuckGo, Startpage, Swisscows, Qwant, Yandex, Mojeek, Brave. Specs for MetaGer, Ecosia and Marginalia exist in `engines/specs.py` but were not part of the run (see [Engines left out](#engines-left-out)).

## Findings

One pass on 2026-10-02 from the Netherlands (English, `en-NL`): 52 queries per engine, 38 scored automatically and 14 rated by hand.

**Short version:** Startpage, Brave and Swisscows came out on top on both the automated score and the blind manual ratings, and this run cannot separate them. Bing was clearly last on both. Brave is a good choice but not a clear winner.

| Engine | Auto stars (0-4) | Manual (0-4) | Relevancy | Answers | Operators | Median latency | Avg ads |
|---|---|---|---|---|---|---|---|
| Startpage | 3.00 | 3.64 | 0.88 | 0.46 | 0.74 | 0.8 s | 0.0 |
| Brave | 2.74 | 3.64 | 0.69 | 0.58 | 0.96 | 1.0 s | 0.1 |
| Swisscows | 2.73 | 3.57 | 0.72 | 0.50 | 0.94 | 0.2 s | 0.0 |
| DuckDuckGo | 2.71 | 3.21 | 0.75 | 0.50 | 0.59 | 1.2 s | 0.0 |
| Yandex | 2.60 | 3.00 | 0.75 | 0.42 | 0.96 | 12.2 s | 0.0 |
| Google | 2.54 | 3.29 | 0.65 | 0.54 | 0.77 | 0.7 s | 1.0 |
| Qwant | 2.32 | 3.21 | 0.73 | 0.19 | 0.85 | 1.0 s | 1.1 |
| Mojeek | 2.04 | 2.43 | 0.49 | 0.38 | 1.00 | 0.8 s | 0.0 |
| Bing | 1.53 | 1.29 | 0.52 | 0.04 | 0.22 | 0.3 s | 0.1 |

Auto stars combine relevancy (60%), answers (30%) and an "other" score (10%: operators, latency, ads), see [Scoring](#scoring). Manual is the mean of 14 blind ratings and is not mixed into the stars. Relevancy, answers and operators are 0-1.

Mean automated score by query group (0-1; `spam` is the share of results that are not affiliate spam):

| Engine | core | ia | nav | op | spam | tech |
|---|---|---|---|---|---|---|
| Startpage | 0.59 | 0.44 | 1.00 | 0.74 | 0.80 | 0.94 |
| Brave | 0.56 | 0.50 | 0.87 | 0.96 | 0.60 | 0.81 |
| Swisscows | 0.45 | 0.50 | 1.00 | 0.94 | 0.82 | 0.70 |
| DuckDuckGo | 0.57 | 0.38 | 1.00 | 0.59 | 0.42 | 0.95 |
| Yandex | 0.50 | 0.44 | 0.91 | 0.96 | 0.65 | 0.78 |
| Google | 0.66 | 0.44 | 0.88 | 0.77 | 0.81 | 0.48 |
| Qwant | 0.35 | 0.12 | 1.00 | 0.85 | 0.55 | 0.84 |
| Mojeek | 0.33 | 0.38 | 0.75 | 1.00 | - | - |
| Bing | 0.15 | 0.06 | 0.83 | 0.22 | 0.85 | 0.29 |

### Reading the results

- **The top three are not separable.** 14 manual queries, one rater and one run from one IP. Startpage and Brave tie at 3.64, Swisscows is at 3.57.
- **Brave:** best on instant answers (0.58, 16 answer boxes detected), nine 4s out of 14 manual ratings and no rating below 2. Relevancy is mid-pack (0.69), behind Startpage on technical queries (0.81 vs 0.94).
- **Startpage:** best relevancy (0.88) and the highest automated stars (3.00).
- **Bing** is last on both measures. Seven of its 14 manual ratings were 1 or lower and it has no 4s. Its answers (0.04) and operators (0.22) scores were not investigated further; they may reflect how Bing responded to an automated browser.
- **DuckDuckGo** is strong on navigational and technical queries but weak on spam (0.42) and operators (0.59). **Qwant** detected no answer boxes (answers 0.19).

### Do Startpage, Brave and Swisscows share an index?

Partly. Mean top-10 Jaccard overlap (1.0 = identical result sets) over the queries both engines have, about 50 per pair:

| Pair | Same URL (host + path) | Same domain |
|---|---|---|
| Brave / Swisscows | 0.53 | 0.58 |
| DuckDuckGo / Qwant | 0.47 | 0.51 |
| Startpage / Brave | 0.31 | 0.39 |
| Startpage / Swisscows | 0.29 | 0.37 |
| Startpage / Google | 0.09 | 0.49 |

Brave and Swisscows overlap more than any other pair, which suggests shared sources but not an identical index. Startpage looks like a separate source; its domain overlap with Google is its highest. Google's exact-URL overlap is understated (see below).

### What to trust less

- **Google URLs are approximate.** Google serves opaque `/goto?url=` links, so URLs are rebuilt from the truncated breadcrumb (flagged `url_approx`). Domain checks work, path-based gold checks can miss, so Google's relevancy is a lower bound.
- **Answer boxes:** Startpage, Swisscows and Qwant show zero detected answer boxes, so their selectors may be stale and their answers scores unreliable.
- **Incomplete pages:** Mojeek was blocked partway and has 36 of 52 queries (22 automated). Startpage's `op-intitle` page is still a block page and scores 0 for that query. Swisscows has one genuine "no results" page (`core-java-verbose`).
- **Yandex latency (12.2 s)** is probably an artefact: its `ready` selectors matched nothing on the cached pages, so the runner likely waited out its timeout. That drags down its "other" score. Yandex pages flagged as bot checks were not individually inspected.
- **The review was not fully blind** for Bing and Google: Bing panels showed `bing.com/ck/a` redirect links and Google panels showed shortened breadcrumb URLs, both of which identify the engine. One Mojeek panel (`man-ja`) was empty.

## Methodology

Modelled on the 2020 LibreTechTips article, with the same 60/30/10 weights.

### Queries

52 queries in `queries/`:

| Group | n | What is checked |
|---|---|---|
| core | 9 | The article's 8 queries plus an EUR variant: gold URL, verbatim phrase, intent coverage or answer text |
| ia | 8 | Instant answers (calculator, time, unit, currency, weather, population, author, definition) |
| man | 14 | News, local, non-English, typo, ambiguity, long-tail, health: rated blind by hand |
| nav | 4 | Navigational: gold URL |
| op | 5 | Operators: `site:`, `filetype:`, `-word`, `"phrase"`, `intitle:` |
| spam | 4 | Share of results from the affiliate-spam domains in `queries/spam_domains.txt` |
| tech | 8 | Developer queries: gold URL on docs / Q&A sites |

### Collection

Playwright drives a headed browser with one persistent profile per engine, locale `en-NL` and timezone `Europe/Amsterdam`. Queries are paced 8-20 s apart. Raw HTML, a screenshot and the latency are cached per (engine, query), and everything is scored offline from that cache. The runner pauses up to 300 s for a CAPTCHA or bot check to be solved by hand, and not every check was cleared (see [What to trust less](#what-to-trust-less)). Engine geolocation comes from the IP address.

Environment: Linux, Python 3.13.5, Playwright 1.63.0, Chromium 153.0.8010.12, beautifulsoup4 4.15.0, lxml 6.1.3.

### Blind manual rating

`review` builds a page with the 14 manual queries x 9 engines = 126 panels (top 8 parsed results each). Panels are shuffled and labelled A-I per query, and the label-to-engine key stays in `data/out/review_key.json` until `import-ratings`. One person rated each panel 0-4.

### Engines left out

- **MetaGer:** requires an access token key.
- **Ecosia:** the Cloudflare check did not clear after ticking the box in the automated browser.
- **Marginalia:** the IP was blocked.
- **Mojeek** was blocked partway through and is included with the 36 queries it returned.

### Fixes made during the run

Selectors drift. Before scoring I fixed the Google result container and URL extraction, the Swisscows and Yandex result containers, and Bing's redirect links (the destination is base64 in the `u=` parameter). 13 pages that were errors or block pages were refetched and 11 recovered.

## Run it yourself

Needs Python 3 and a desktop session (the browser is headed). Tested on Linux only. A home connection is less likely to be blocked than a datacentre or VPN address.

### Setup

```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium    # for installed Google Chrome: set browser.channel: chrome in config.yaml
```

Region is set in two places: `locale` / `timezone` in `config.yaml`, and the region parameters in the URL templates in `engines/specs.py` (for example `gl=nl`, `mkt=en-NL`). Change both to test from somewhere else, and swap the Dutch queries in `queries/`.

### Workflow

```
python cli.py run --engines mojeek,brave --groups core2020   # start small
python cli.py doctor                                         # do the selectors still parse?
python cli.py run                                            # everything (resumable)
python cli.py score
python cli.py review                                         # open data/out/review.html, rate blind, Export
python cli.py import-ratings ~/Downloads/ratings.json
python cli.py report                                         # data/out/report.html + results.csv
```

`run` opens a visible browser window, waits 8-20 s between queries, and caches raw HTML plus a
screenshot per (engine, query) in `data/raw/`. If an engine shows a CAPTCHA, solve it in the
window and the run continues. Rerunning skips cached queries (`--force` to refetch).
Expect a long run; use `--engines` and `--groups` to split it.

**Check for blocked pages after `run`.** A block or error page that never cleared is saved like any other result, so the query counts as cached and a plain rerun skips it. It then parses as zero results and scores 0.

- `python cli.py doctor` shows how many pages per engine parse into results. Anything below N/N needs a look.
- In `data/raw/<engine>/<id>.json`, `"captcha": true` means a check appeared. Open the matching `.png` to see the page.
- Refetch specific pages with `python cli.py run --force --engines <engine> --ids <id>,<id>`.
- Genuinely empty results exist too (for example an exact-phrase query), so check before refetching.

**Do not rerun `review` once you have started rating.** It reshuffles the labels and overwrites the key, so saved ratings would map to the wrong engines. Keep `data/out/review_key.json` unopened until you have imported the ratings.

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

- Selectors in `engines/specs.py` drift. They were fixed for the nine tested engines against pages fetched on 2026-10-02 and will go stale. Run `doctor`, open the cached HTML in `data/raw/<engine>/`, adjust the spec, rerun `score`. No refetch needed. The specs for MetaGer, Ecosia and Marginalia were never verified.
- One run, one IP, one rater, 14 manual queries per engine. There are no confidence intervals, so small gaps are noise.
- Answer correctness is regex-based; live values (currency, weather) are matched by format, not by number.
- Snippets are truncated by engines, so exact-phrase checks can miss a true hit.
- Results vary with IP location and cookies; the persistent profile per engine is in `data/profiles/`.

## What not to commit

Everything under `data/` is gitignored and must stay that way. `data/profiles/` holds full browser profiles (cookies and local storage), `data/raw/` holds cached pages and screenshots that reflect your IP's location, and `data/out/` is generated. Before publishing a fork, check that `git ls-files data` prints nothing.
