[RegLens guide](../README.md) › Part 3: Collecting the rulebooks

# 3.1 Collecting the rulebooks, politely

In [Part 2](../02-setting-up-the-workshop/04-safety-nets.md) we built the workshop and its safety
nets. Now we need something to read. A copilot is only as good as its documents, so we decide
*which* ones RegLens will know, and download them without being a nuisance.

## A reading list, not the whole library

The collection of documents a system reads from is called its **corpus** (Latin for "body", as in
a body of text). Ours is a hand-picked list of **37 documents**: 14 from the RBI, 8 from SEBI,
6 FCA Handbook chapters and 9 PRA documents (6 parts of its Rulebook and 3 supervisory
statements). They all sit on six themes that every regulator covers: know-your-customer checks,
outsourcing, cyber and operational resilience, complaints, governance, and model risk and AI.

Think of the reading list a new compliance analyst gets on day one: not the whole library, only
the shelves that matter, plus a few old editions. A curated list has three advantages over "crawl
everything":

- **It fits a laptop.** Thousands of documents would take hours to prepare for search on an
  ordinary processor. About forty index in minutes.
- **Shared themes make hard questions possible.** "How do the RBI and the FCA differ on
  outsourcing?" can only be answered if both sides are in the corpus.
- **Old versions make time travel testable.** We deliberately included rules that were later
  *replaced*: the 2016 KYC Master Direction, three editions of the PRA's outsourcing statement
  SS2/21, and Meera's document, the RBI's 2023 Internal Ombudsman direction, together with the
  2026 Directions that replaced it. Counting every edition, the 37 documents give **48 versions**.

The list lives in a configuration file, `configs/sources.yaml`, one entry per document: its
regulator, title, web address, topics, who it applies to, and any older editions. The program
checks every entry on loading and **refuses to start** if one is broken. This choice is written
down as an **ADR** (architecture decision record): a one-page note of a decision, its reasons and
its trade-offs, so a future teammate knows *why* without having to ask.

## Crawling politely

A **crawler** is a program that downloads web pages automatically. A careless crawler can fire
hundreds of requests a second, slow a website down for real people, and get itself blocked.
Regulators' websites are public infrastructure, so being polite is both ethical and practical.

Every download in RegLens goes through one small "polite fetcher" that follows four habits:

1. **It reads `robots.txt` first.** This is a small file a website publishes saying which pages
   bots may visit. Like the opening hours on a library door, we obey it.
2. **It keeps a rate limit.** It waits at least 1.5 seconds between requests to the same site.
3. **It retries sensibly.** If the server is busy, it waits 1.5 seconds, then 3, then 6, and tries
   again. If the page doesn't exist at all, it gives up at once, because retrying won't help.
4. **It keeps a copy.** Every successful download is saved on disk, so it's never fetched twice.

Because all downloads pass through this one door, a crawler written later can't forget the rules.
We built it on **httpx**, a modern Python library for web requests. The older favourite, requests,
would also work, but httpx can pretend to be a website inside a test, so the tests check the
politeness rules without touching the internet.

## Four websites, four shapes

Each regulator publishes differently, so the crawler has one small strategy per website. RBI
directions are long web pages; SEBI circulars are PDFs tucked inside a web page; the FCA Handbook
comes section by section. The PRA Rulebook has a separate web address **for every date**, showing
the rules as they stood that day, even a version that takes effect on 1 January 2027.

Everything lands in `data/raw/`, and one line per version goes into a **manifest**: where it came
from and a **fingerprint** of the exact bytes (a short code computed from the file; change one
character and the fingerprint changes). That's the chain of custody for every document, and later
it tells the system when a regulator has quietly edited a page.

> **A bump on the road:** the RBI's PDF server answered our automated downloads with an "are you
> a robot?" page instead of the PDF, while still reporting success. We don't try to defeat bot
> protection, so for the two RBI PDFs we needed, we used copies saved by the Internet Archive's
> Wayback Machine, a public library of web snapshots. We also check that every "PDF" really starts
> like one. The lesson: stay polite when it's inconvenient, and never trust that a download is
> what it claims to be.

> **Try it:** run `uv run poe crawl`. The first time takes about ten minutes, with a log line for
> each download. Run it again and it finishes in seconds, because every page comes from the
> saved copies.

*Want the details? See `walkthrough/02-corpus/`, `docs/adr/0001-curated-corpus.md` and
`src/reglens/corpus/`.*

So far: we have a reading list of 37 documents and 48 versions, downloaded politely and
fingerprinted. Next, we turn those messy pages into clean paragraphs a lawyer could cite.

**Next →** [4.1 From pages to citable paragraphs](../04-parsing/01-from-pages-to-citable-paragraphs.md)
