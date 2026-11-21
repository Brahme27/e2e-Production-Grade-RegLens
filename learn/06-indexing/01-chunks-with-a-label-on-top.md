[RegLens guide](../README.md) › Part 6: Making it searchable

# 6.1 Chunks with a label on top

In [Part 5](../05-time/02-valid-from-valid-to.md) every paragraph got a validity window. Our
corpus is now clean and dated, but it isn't searchable yet. Search needs an **index**, like the
index at the back of a book, except that ours must work for meaning as well as words. Building it
takes three steps, one per chapter: cut the text into pieces, turn the pieces into numbers, and
load them into a database built for searching. This chapter is the cutting.

## The pieces a search returns

A **chunk** is the piece of text a search engine hands back. **Chunking** is deciding where to
cut. It sounds like a detail, but it decides what the answer writer gets to read, so we built two
kinds and let the numbers choose later:

- **Fixed-size chunks**, the naive approach most "chat with your PDFs" tools use: glue a document's
  text together and cut it every 380 words or so. That gives 1,120 chunks.
- **Paragraph chunks**: one chunk per numbered paragraph, the unit from Part 4. That gives 5,203
  chunks.

A fixed window often starts mid-rule ("…and the Board shall") and mixes two unrelated obligations,
which confuses both the search and the answer. Think of cutting a cookbook into equal strips of
paper instead of into recipes. Strips are easy to make, but nobody can cook from half a recipe.

Giant paragraphs need care. That KYC definitions paragraph of 22,000 characters is split at its
own sub-items, "(i)", "(ii)" and so on, into pieces of at most about 300 words. Each piece is
still cited as paragraph 3, part 2 of 9, so citations never break.

## Every chunk carries its paperwork

A chunk isn't only text. It carries **metadata**, which means data about the data, like the label
on a jar of pickle that says what's inside and when it was made. Each chunk knows its document, its
version, its regulator, its paragraph reference, its headings, its validity window and its status.
That's everything needed to cite it and to filter it by date.

Each chunk also gets a stable id, made from its document, version, position and reference. If we
rebuild the index from the same text, chunks overwrite themselves instead of appearing twice.

## A lonely paragraph

Here is a quieter problem. Take a paragraph from the FCA's complaints chapter about what firms must
report. The paragraph itself may never say "complaints" or "FCA": those words live in the chapter
title above it. A question like "What must firms report to the FCA about complaints?" would
struggle to find it.

The fix is a **context header**: before a chunk is turned into numbers, we write a short label at
the top naming the regulator, the document, its official number, the heading path and the
paragraph reference. It's like photocopying a page from a binder and writing the binder's name and
chapter at the top before filing it. Months later, the copy can still be found and understood.

For Meera's question, the chunk for paragraph 12 starts with a label saying it is from the RBI,
from the 2023 Internal Ombudsman direction, under which heading, and which paragraph it is. Now the
words "RBI" and "Internal Ombudsman" travel with it.

## Two layers, and only one of them free

This idea comes from a technique called **contextual retrieval**, which asks an LLM to write a
custom context for every single chunk. For our 5,203 chunks that would be 5,203 calls: about five
days of our free quota. So we split the idea in two:

| Layer | Cost | What it adds |
|---|---|---|
| Structural header | Free | Regulator, document, number, headings, paragraph ref |
| Document summary | 37 LLM calls, one per document | What the document covers and who it applies to |

Both sound helpful. But in RegLens, sounding helpful isn't enough: each layer has to earn its place
in the measurements of Part 9. One of them will fail that test, and we'll see which, and why.

*Want the details? See `walkthrough/05-indexing/01-chunking.md`, `02-contextual-retrieval.md` and
`src/reglens/index/chunking.py`.*

So far: the corpus is cut into paragraph-shaped chunks, each with its paperwork and a label on top.
Next, we turn every chunk into numbers a computer can compare.

**Next →** [6.2 Meaning and exact words](02-meaning-and-exact-words.md)
