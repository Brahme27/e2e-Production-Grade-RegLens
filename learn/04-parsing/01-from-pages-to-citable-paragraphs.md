[RegLens guide](../README.md) › Part 4: Reading the rulebooks

# 4.1 From pages to citable paragraphs

In the [last chapter](../03-the-corpus/01-collecting-the-rulebooks.md) we downloaded 48 versions
of 37 documents. But a raw web page is full of menus, footers and layout tables, and a PDF doesn't
even know what a paragraph is. Now we pull out each file's structure. That job is called **parsing**: turning a raw file into labelled parts (this is a
heading, this is paragraph 12, this is a page footer to throw away).

## The paragraph is the unit

Before writing any parser, we decided what every parser must produce. The answer: **numbered
paragraphs**, the way a lawyer cites them ("para 93", "PRIN 2A.1.3G", "rule 2.1"). Three reasons:

- **That's how regulation is cited.** An auditor asks "which paragraph says that?" If our unit
  is the paragraph, every answer can point to one.
- **A paragraph is a complete thought.** A piece cut by length often starts halfway through one
  rule and ends halfway through the next, mixing two obligations.
- **The headings travel with the text.** "The bank shall review it annually" means nothing on its
  own. With its headings attached (*Chapter IV › Outsourcing Process › Exit Strategy*) it's clear
  what "it" is.

A recipe book works the same way: cut it into recipes, not pages, because a page can split a
recipe in half. So every parser produces the same shape: a document version (title, official
number, dates) holding a list of paragraphs, each with its reference, text, heading path and,
where the regulator says so, the date its wording took effect.

For Meera's question, the RBI's 2023 Internal Ombudsman direction becomes one such document, and
its paragraph 12 becomes a paragraph with the ref "12", its chapter headings and its text.

## Reading web pages

The RBI, FCA and PRA publish mostly web pages. To read their structure we use **selectolax**, a
fast library for walking through a page's HTML (the tagged text that browsers draw). The classic
choice, BeautifulSoup, is friendlier but slower; selectolax does the same job quickly.

**RBI pages** are long, and the parser walks them in reading order. A line starting with a number
("93.") opens a new paragraph; sub-items like "(i)" and tables join the paragraph they belong to;
a stack of headings is kept for each one.

Older RBI pages also hide a treasure. Every change is marked with a tiny superscript number whose
tooltip says what happened, such as *"Inserted vide circular … dated January 9, 2020."* We strip
the marker (it would confuse search) but **keep the note**, and its date becomes that paragraph's
effective date: paragraph-level history from a single page.

The **UK rulebooks** are the most structured of all. Each FCA provision carries a reference and a
type letter: **R** for a rule that must be followed, **G** for guidance that explains how. We cite
them the way the FCA does, letter included: *SYSC 8.1.1R* is a rule. Each provision also shows the
date its current wording took effect, so we know exactly when each piece changed.

## Rebuilding paragraphs from PDFs

SEBI circulars and PRA supervisory statements are PDFs. A PDF knows where to *draw* each line of
text, but has no idea what a paragraph is, so we rebuild one. We pull out the lines with
**pypdfium2**, a free, fast wrapper around the PDF engine used in Google Chrome. Then simple rules
do the rest: a line that repeats on many pages is a running header or footer and goes; a line that
doesn't start a numbered paragraph continues the previous one; short numbered titles become
headings; a bare number in the wrong place is a footnote, not paragraph 4.

The plan had named **Docling**, a tool that uses neural networks to understand page layouts. It's
excellent, but it needs about a gigabyte of models and takes seconds per page on an ordinary
processor. Our PDFs are clean, born-digital text, where line rules get most of the way in under a
second per document. The trade-off is recorded in an ADR, and a Docling-based reader could be
added later without touching anything downstream.

> **A bump on the road:** the footer rule said "a line that repeats on at least 30% of pages is a
> footer". On a tiny three-page PDF in our tests, 30% meant *one* page, so every line counted as a
> footer and the document came out empty. A footer must now repeat on at least two pages. The
> lesson: write tests with small, awkward examples. They find the edges that big real files hide.

## The corpus after parsing

After parsing, the corpus is **48 document versions and about 4,800 paragraphs**. Most are short,
but a few are giants, like one KYC definitions paragraph of 22,000 characters, which we'll split
sensibly in Part 6.

> **Try it:** run `uv run poe parse`. When it finishes you'll see one line per document version,
> each with its paragraph count, and a final line with the totals. The results are saved as one
> file per version in `data/processed/documents/`.

*Want the details? See `walkthrough/03-parsing/`, `docs/adr/0002-lightweight-parsing.md` and
`src/reglens/parse/`.*

So far: every document is now a clean list of numbered, headed, often dated paragraphs. Next,
we teach RegLens which documents replaced which, and when.

**Next →** [5.1 Who replaced whom](../05-time/01-who-replaced-whom.md)
