# 02: The polite fetcher

**File:** `src/reglens/corpus/fetch.py`

## What
One small class, `PoliteFetcher`, through which **every** download goes. It:
1. **reads `robots.txt`** on each website and refuses URLs the site asks bots not to visit;
2. **waits** at least 1.5 seconds between requests to the same website;
3. **retries** temporary failures (server busy, timeouts) with growing pauses: 1.5 s, 3 s, 6 s;
4. **gives up immediately** on permanent failures (404 Not Found): no point retrying;
5. **caches** every successful download on disk, keyed by URL.

## Why
- **Regulators' websites are public infrastructure.** A careless crawler firing hundreds
  of requests a second can slow a site down for real users, and gets blocked. Being
  polite is both ethical and practical.
- **The cache makes everything repeatable.** The first crawl takes ~10 minutes. Every
  later run (re-parsing, re-indexing, a colleague cloning the repo with the cache)
  takes seconds and sends **zero** requests.
- **One choke point.** Because all downloads go through one class, politeness rules
  can't be forgotten by a new crawler written later.

## How it works (plain words)
```
get(url):
    in the cache?          -> return it (no network)
    robots.txt says no?    -> stop with an error
    loop up to 4 attempts:
        wait until 1.5 s have passed since the last request to this host
        download
        200 OK             -> save to cache, return
        404 / 403 ...      -> stop (permanent)
        429 / 5xx / timeout-> pause 1.5 s, 3 s, 6 s... and try again
```
**Analogy:** a well-mannered library visitor: checks the opening rules on the door,
doesn't sprint between shelves, waits and asks again if the librarian is busy, and
photocopies what they borrow so they never need to ask twice.

## Tech used and why
| Tool | Why |
|---|---|
| `httpx` | Modern HTTP client with timeouts, redirects and a **mock transport** for tests |
| `urllib.robotparser` | Python's built-in robots.txt reader: no extra dependency |
| SHA-256 file names | URLs contain `?`, `/` and `&`, which are illegal in file names; a hash of the URL is a safe, fixed-length name |

## How we test it without the internet
`httpx.MockTransport` lets a test pretend to be a website. The tests check that a
cached URL is never fetched twice, robots.txt is obeyed, a server that fails twice
then succeeds is retried with 1 s → 2 s pauses, a 404 fails fast, and requests to the
same host are spaced out. The pause function is swapped for one that just *records*
the requested pauses, so the tests run instantly.

## How to run / what you should see
```bash
uv run pytest tests/unit/test_corpus.py -q --no-cov
```
`17 passed`
