# 03: Crawl strategies: four websites, four shapes

**File:** `src/reglens/corpus/crawl.py`

## What
Each regulator publishes differently, so the crawler has one **strategy** per shape:

| Kind | Who | How it's downloaded |
|---|---|---|
| `html` | RBI | One page per direction; older versions from listed snapshot URLs |
| `pdf` | PRA supervisory statements, one RBI direction | Download the PDF, then check it really *is* a PDF (starts with `%PDF`), because bot-protection pages come back as "200 OK" HTML |
| `sebi_circular` | SEBI | Open the circular's web page, find the PDF embedded in its viewer (`<iframe … file=…pdf>`), download that. Very old circulars have no PDF, so keep the HTML |
| `fca_chapter` | FCA Handbook | A chapter is split into sections (`prin2as1`, `prin2as2`, …). Try section 1, 2, 3… and stop after two empty pages in a row (a missing section in the middle is fine) |
| `pra_part` | PRA Rulebook | The Rulebook has a URL **per date**: `/pra-rules/outsourcing/30-06-2025` shows the rules as they stood that day. We snapshot each date in the source list |

Everything lands in `data/raw/<doc_id>/<version>/<part>.html|pdf` and one line per
version goes into `data/raw/manifest.jsonl`:
```json
{"doc_id": "pra-outsourcing", "version": "asof2025-06-30", "source": "pra_point_in_time",
 "parts": [{"name": "main", "path": "pra-outsourcing/asof2025-06-30/main.html",
            "url": "https://www.prarulebook.co.uk/pra-rules/outsourcing/30-06-2025",
            "sha256": "…"}]}
```

## Why keep a manifest?
It's the **chain of custody** for every document: where it came from, when, and a
fingerprint (SHA-256) of the exact bytes. If the RBI edits a page tomorrow, the
fingerprint changes, and that's how the change-detection job (phase 10) knows a
document needs re-reading.

## How it works
The strategies are small generator functions that yield one `RawVersion` per
snapshot. A failed document is logged and listed at the end, and the crawl carries on;
one broken page must not stop the other 36. `--only <ids>` re-crawls a few documents
and keeps the rest of the manifest.

**Analogy:** four different libraries with four different catalogues. You learn each
librarian's system once, then file every photocopy in the same labelled drawers.

## Discoveries while building this
- **FCA** pages are rendered by a JavaScript app, but the server sends the full text in
  the first response (server-side rendering), so a plain HTTP client works.
- **PRA** shows past *and future* versions: the Risk Control part already has a version
  dated 1 January 2027. Our index can answer "what will apply next year?"
- **RBI** keeps an official "Previous Versions" page for each direction, but the old
  versions are PDFs on the bot-protected server, hence the Wayback snapshot.

## How to run / what you should see
```bash
uv run poe crawl
```
Log lines like `fetched bytes=275684 url=https://www.rbi.org.in/...` and finally
`crawl_done versions=56 failed=[]`. Run it again: it finishes in seconds because every
page comes from the cache.
