[RegLens guide](../README.md) › Part 6: Making it searchable

# 6.3 Qdrant, the searchable shelf

In the [last chapter](02-meaning-and-exact-words.md) every chunk got two vectors, one for meaning
and one for exact words. Now they need a home: somewhere that can find the closest vectors to a
question in milliseconds and, equally important for us, ignore every chunk that wasn't in force
on the date asked.

## A database built for vectors

An ordinary database is good at exact questions: "give me the row with id 42". A **vector
database** is built for a fuzzier one: "give me the 30 items whose vectors are closest to this
one". It organises vectors so that it doesn't have to compare the question against every single
chunk, the way a well-organised library lets you walk to the right shelf instead of checking
every book.

We use **Qdrant**, an open-source vector database. In Qdrant, each chunk becomes a **point** with
three parts: an id, two *named* vectors (`dense` and `bm25`), and a **payload**, which holds the
chunk's text and all its metadata from chapter 6.1.

We chose Qdrant for three reasons. It can search dense and sparse vectors and merge the results
in a single request. It filters on the payload *during* the search. And it runs in two modes with
the same code: **embedded**, as a plain folder on the laptop (or entirely in memory during tests),
with no server at all, and as a **server** inside Docker and on AWS. Other options exist, such as
vector add-ons for an ordinary database or paid hosted services, but none gave us all three for
free on a laptop.

## The "as of" filter

Here is where Part 5 pays off. Every point's payload stores its validity window as day numbers.
"As of 1 March 2024" becomes a filter: valid-from on or before that day, and valid-to after it.

The important word is **inside**. The filter is applied *during* the search, not afterwards. Why
does that matter? Imagine searching first and then throwing away repealed text. The old 2016 KYC
direction looks very much like the 2025 one, so the top 30 results could be mostly repealed
paragraphs. Drop them, and you're left with too few valid ones to answer well. Filtering inside the
search means every one of the 30 candidates is valid on the date.

For Meera, the filter is "as of 5 January 2025". The 2026 Internal Ombudsman Directions start on
14 January 2026, so they can't come back at all. Paragraph 12 of the 2023 direction, valid from 29
December 2023, competes on equal terms. Repealed rules never compete with current ones, and
current rules never sneak into questions about the past.

Think of a library catalogue where every card has a "valid from, valid to" stamp, and the
librarian can hide, in one move, every card that wasn't valid on the day you ask about.

## Four shelves for one experiment

To measure which chunking and labelling ideas actually help, we build **four collections** (a
collection is Qdrant's word for a table of points), one per variant:

- fixed-size chunks;
- paragraph chunks;
- paragraph chunks with context headers;
- paragraph chunks with context headers and LLM document summaries.

They all hold the same corpus, prepared differently. In Part 9 we search each one with the same
questions and keep the winner.

## A nickname that makes updates painless

The application never reads a collection by its real name. It reads an **alias**, a nickname,
called `reglens`, which points at whichever collection is currently serving. To re-index after a
regulator changes a page, we build a brand-new collection beside the old one, then move the
nickname across in one instant step. Users never see a half-built index, and if something is
wrong, rolling back is moving the nickname back.

It's like a shop that sets up its new premises next door while the old shop stays open, then
moves the sign overnight. Customers walk into a finished shop either way.

```
                     ┌─▶ reglens_para_ctx       (serving today)
alias "reglens" ─────┤
                     └─▷ next build, swapped in when ready
```

*Want the details? See `walkthrough/05-indexing/04-qdrant.md`, `src/reglens/index/store.py` and
`src/reglens/index/build.py`.*

So far: our corpus lives in Qdrant, with meaning, exact words, metadata and dates, behind a
nickname that makes updates safe. The library is ready. Next, we learn to find the right paragraphs
for a real question, starting by reading the question itself.

**Next →** [7.1 Reading the question](../07-retrieval/01-reading-the-question.md)
