"""Parsing: dates, paragraph assembly, RBI / FCA / PRA HTML, PDFs, the parse runner."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from reglens.corpus.crawl import RawPart, RawVersion, write_manifest
from reglens.corpus.sources import SourceDoc
from reglens.parse.blocks import Block, assemble
from reglens.parse.handbooks import parse_fca_section, parse_pra_part
from reglens.parse.html_text import node_text, parse_html
from reglens.parse.model import ParsedDocument, load_documents, save_documents
from reglens.parse.pdf import parse_pdf
from reglens.parse.rbi import parse_rbi_html
from reglens.parse.run import parse_all, parse_version
from reglens.parse.text import clean, find_dates, first_date, parse_day_first
from tests.helpers import make_pdf


# ---------------------------------------------------------------- text helpers
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("dated November 28, 2025", date(2025, 11, 28)),
        ("issued on 28th Nov, 2025", date(2025, 11, 28)),
        ("as at 30/06/2025", date(2025, 6, 30)),
        ("Updated as on Sept 18 2026", date(2026, 9, 18)),
    ],
)
def test_find_dates_styles(text: str, expected: date) -> None:
    assert first_date(text) == expected


def test_find_dates_order_and_invalid() -> None:
    assert find_dates("from 1 April 2026 to March 31, 2027 (not 31/02/2026)") == [
        date(2026, 4, 1),
        date(2027, 3, 31),
    ]
    assert first_date("no dates here") is None
    assert parse_day_first("26/06/2026") == date(2026, 6, 26)
    assert parse_day_first("30-06-2025") == date(2025, 6, 30)
    assert parse_day_first("G") is None


def test_clean_whitespace() -> None:
    assert clean("a  b  \n\n\n  c ") == "a b\nc"


# ---------------------------------------------------------------- assembly
def test_assemble_numbered_paragraphs_headings_and_notes() -> None:
    blocks = [
        Block("text", "In exercise of the powers conferred by the Act, RBI issues these."),
        Block("heading", "Chapter I - Preliminary", 1),
        Block("heading", "A. Short Title", 2),
        Block("text", "1. These Directions shall be called the Test Directions, 2025."),
        Block("text", "(i) a sub-item that belongs to paragraph one", notes=("Inserted vide X",)),
        Block("heading", "B. Scope", 2),
        Block("text", "2. Deleted."),
        Block("text", "3. These Directions apply to every commercial bank in India."),
        Block("heading", "Annex II", 1),
        Block("text", "1. Annex paragraphs restart their numbering at one."),
        Block("text", "4 footnote-like text that is not a paragraph", numbered=False),
        Block("text", "Principle 1.2 Model inventory should be complete and accurate."),
    ]
    paragraphs = assemble(blocks)
    refs = [p.ref for p in paragraphs]
    assert refs == ["Preamble ¶1", "1", "3", "Annex II, 1", "Annex II, Principle 1.2"]
    first = paragraphs[1]
    assert first.section_path == ("Chapter I - Preliminary", "A. Short Title")
    assert "(i) a sub-item" in first.text
    assert first.notes == ("Inserted vide X",)
    assert paragraphs[2].section_path == ("Chapter I - Preliminary", "B. Scope")
    assert "footnote-like" in paragraphs[3].text  # appended, not a new paragraph


def test_unnumbered_text_is_named_after_its_heading() -> None:
    long_heading = "A very long heading that goes on and on about outsourcing arrangements"
    paragraphs = assemble(
        [Block("heading", long_heading, 1), Block("text", "Unnumbered guidance text here.")]
    )
    assert paragraphs[0].ref.endswith("… ¶1")


# ---------------------------------------------------------------- HTML text
def test_node_text_keeps_blocks_tables_and_markers() -> None:
    tree = parse_html(
        b"<div id='x'><p>The <a href='#'>Consumer Duty</a> applies.</p>"
        b"<p>(1)</p><p>the rules apply</p>"
        b"<table><tr><td>Subject</td><td>Rule</td></tr><tr><td>A</td><td>B</td></tr></table></div>"
    )
    text = node_text(tree.css_first("#x"))
    assert text.split("\n") == [
        "The Consumer Duty applies.",
        "(1) the rules apply",
        "Subject | Rule",
        "A | B",
    ]


# ---------------------------------------------------------------- RBI
RBI_PAGE = b"""
<html><body><table class="tablebg"><tr><td class="tableheader"><b>
Reserve Bank of India (Commercial Banks - Test) Directions, 2025 (Updated as on October 1, 2026)
</b></td></tr>
<tr class="tablecontent2"><td><table class="td"><tr><td>
<p>RBI/DOR/2025-26/171<br>DOR.ORG.REC.No.90/21-04-158/2025-26</p>
<p align="right">November 28, 2025</p>
<p><a class="links" href="x">Previous Versions</a></p>
<table><tr><td>Table of Contents</td></tr><tr><td>Chapter I</td></tr></table>
<p class="head">Chapter I - Preliminary</p>
<p class="head">A. Short Title and Commencement</p>
<p>1. These Directions shall be called the Test Directions, 2025.</p>
<p class="head">B. Applicability</p>
<p>2. These Directions apply to all banks.<sup title="Amended vide circular X dated January 9, 2026."><a href="#F1">1</a></sup></p>
<p>(i) scheduled commercial banks; and</p>
<table><tr><td>Bank type</td><td>Applies</td></tr><tr><td>SCB</td><td>Yes</td></tr></table>
<p><b>3. Board Approved Policy</b></p>
<p>A bank shall have a board approved outsourcing policy.</p>
<p>Amended vide circular X dated January 9, 2026.</p>
</td></tr></table></td></tr></table></body></html>
"""


def test_parse_rbi_html() -> None:
    header, paragraphs = parse_rbi_html(RBI_PAGE)
    assert header.title == "Reserve Bank of India (Commercial Banks - Test) Directions, 2025"
    assert header.doc_number == "RBI/DOR/2025-26/171"
    assert header.issue_date == date(2025, 11, 28)
    assert header.version_date == date(2026, 10, 1)
    by_ref = {p.ref: p for p in paragraphs}
    assert set(by_ref) == {"1", "2", "3"}
    assert by_ref["2"].effective_from == date(2026, 1, 9)  # from the amendment footnote
    assert "Bank type | Applies" in by_ref["2"].text
    assert "1" not in by_ref["2"].text.split("banks.")[1][:2]  # footnote marker stripped
    assert by_ref["3"].section_path == ("Chapter I - Preliminary", "B. Applicability")
    assert "Previous Versions" not in " ".join(p.text for p in paragraphs)


def test_parse_rbi_html_without_content_fails() -> None:
    with pytest.raises(ValueError, match="no RBI content"):
        parse_rbi_html(b"<html><body><p>nothing</p></body></html>")


# ---------------------------------------------------------------- FCA / PRA
FCA_SECTION = b"""
<div class="provisions-container">
<h2><span>SYSC 8.1 General outsourcing requirements</span></h2>
<h3><span>General requirements</span></h3>
<p-card><div class="header"><span></span><label><span>SYSC 8.1.1</span></label>
<span>03/01/2018</span><span>R</span></div>
<div class="provision-meta"><p>A common platform firm must:</p><p>(1)</p><p>avoid undue risk.</p></div>
</p-card>
<p-card><div class="header"><label><span>SYSC 8.1.2</span></label><span>01/04/2009</span>
<span>G</span></div><div class="provision-meta"><p>[deleted]</p></div></p-card>
<p-card><div class="header"><label><span>SYSC 8.1.3</span></label><span>23/10/2025</span>
<span>G</span></div><div class="provision-meta"><p>Firms should note SYSC 4.1.1R.</p></div></p-card>
</div>
"""


def test_parse_fca_section() -> None:
    paragraphs = parse_fca_section(FCA_SECTION)
    assert [p.ref for p in paragraphs] == ["SYSC 8.1.1R", "SYSC 8.1.3G"]
    rule = paragraphs[0]
    assert rule.kind == "rule"
    assert rule.effective_from == date(2018, 1, 3)
    assert rule.section_path == (
        "SYSC 8.1 General outsourcing requirements",
        "General requirements",
    )
    assert "(1) avoid undue risk." in rule.text
    assert paragraphs[1].kind == "guidance"
    assert parse_fca_section(b"<html><body>empty</body></html>") == []


PRA_PART = b"""
<html><body><h1>Outsourcing</h1>
<div class="chapter-section"><span class="rule-number chapter-number">2</span>
<h3 class="chapter-heading">Outsourcing</h3>
<div class="row-block"><span class="rule-number">2.1</span>
<div class="div-row__col-2"><p>A firm must ensure that it takes reasonable steps.</p></div>
<div class="row-block__info"><ul><li>23/10/2025</li></ul></div></div>
<div class="row-block"><span class="rule-number">2.2</span>
<div class="div-row__col-2">[Deleted.]</div>
<div class="row-block__info"><ul><li>03/01/2018</li></ul></div></div>
</div></body></html>
"""


def test_parse_pra_part() -> None:
    title, paragraphs = parse_pra_part(PRA_PART)
    assert title == "Outsourcing"
    assert len(paragraphs) == 1
    assert paragraphs[0].ref == "2.1"
    assert paragraphs[0].section_path == ("2 Outsourcing",)
    assert paragraphs[0].effective_from == date(2025, 10, 23)


# ---------------------------------------------------------------- PDF
def sample_pdf() -> bytes:
    footer = "This SS was published as part of PS6/23."
    return make_pdf(
        [
            ["Supervisory Statement SS1/23", "May 2023", "1 Introduction", footer],
            [
                "1.1 This supervisory statement sets out the expectations for",
                "model risk management in banks.",
                "Model inventory",
                "1.2 Firms should keep a complete model inventory, including:",
                "(a) the purpose of each model;",
                "4 A footnote that should be dropped from the text.",
                footer,
            ],
            ["1.3 Self-assessments should be updated at least annually.", footer, "3"],
        ]
    )


def test_parse_pdf_numbered_paragraphs_headers_and_footnotes() -> None:
    first_page, paragraphs = parse_pdf(sample_pdf())
    assert "SS1/23" in first_page
    by_ref = {p.ref: p for p in paragraphs}
    assert list(by_ref) == ["Preamble ¶1", "1.1", "1.2", "1.3"]  # title block, then numbered
    assert by_ref["Preamble ¶1"].text == "Supervisory Statement SS1/23 May 2023"
    assert by_ref["1.1"].text.endswith("model risk management in banks.")  # wrapped line glued
    assert by_ref["1.2"].section_path == ("1 Introduction", "Model inventory")
    assert "(a) the purpose" in by_ref["1.2"].text
    assert "footnote" not in by_ref["1.2"].text
    assert all("PS6/23" not in p.text for p in paragraphs)  # running footer removed


# ---------------------------------------------------------------- model + runner
def test_document_json_round_trip(tmp_path: Path) -> None:
    _, paragraphs = parse_rbi_html(RBI_PAGE)
    doc = ParsedDocument(
        doc_id="x",
        version="current",
        regulator="RBI",
        doc_type="directions",
        title="T",
        url="u",
        topics=["kyc"],
        applies_to=["commercial_banks"],
        issue_date=date(2025, 11, 28),
        paragraphs=paragraphs,
    )
    save_documents([doc], tmp_path)
    (loaded,) = load_documents(tmp_path)
    assert loaded == doc
    assert loaded.key == "x@current"


def _source(**fields: object) -> SourceDoc:
    base: dict[str, object] = {
        "id": "doc",
        "regulator": "RBI",
        "kind": "html",
        "doc_type": "directions",
        "title": "Doc",
        "topics": ["kyc"],
        "applies_to": ["commercial_banks"],
        "url": "https://reg.example/doc",
    }
    return SourceDoc.model_validate(base | fields)


def _raw(tmp_path: Path, doc_id: str, version: str, parts: dict[str, bytes]) -> RawVersion:
    raw = RawVersion(doc_id, version, "live")
    for name, content in parts.items():
        relative = f"{doc_id}/{version}/{name}"
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative).write_bytes(content)
        raw.parts.append(RawPart(name.split(".")[0], relative, f"https://reg.example/{name}", "h"))
    return raw


def test_parse_version_dispatches_by_kind(tmp_path: Path) -> None:
    rbi = parse_version(
        _source(), _raw(tmp_path, "doc", "current", {"main.html": RBI_PAGE}), tmp_path
    )
    assert rbi.doc_number == "RBI/DOR/2025-26/171"
    assert rbi.effective_from == date(2026, 10, 1)  # the "Updated as on" date

    fca_src = _source(id="fca", regulator="FCA", kind="fca_chapter", chapter="sysc8", url=None)
    fca = parse_version(
        fca_src, _raw(tmp_path, "fca", "current", {"s01.html": FCA_SECTION}), tmp_path
    )
    assert fca.doc_number == "SYSC 8"
    assert fca.version_date == date(2025, 10, 23)

    pra_src = _source(
        id="pra",
        regulator="PRA",
        kind="pra_part",
        part="outsourcing",
        url=None,
        as_of=["2026-10-24"],
        title="PRA Rulebook - Outsourcing",
    )
    pra = parse_version(
        pra_src, _raw(tmp_path, "pra", "asof2026-10-24", {"main.html": PRA_PART}), tmp_path
    )
    assert pra.version_date == date(2025, 10, 23)
    assert pra.doc_number == "PRA Rulebook: Outsourcing"

    snap = {
        "label": "2023-05-17",
        "url": "https://reg.example/old.pdf",
        "effective_from": "2024-05-17",
    }
    pdf_src = _source(id="ss", regulator="PRA", kind="pdf", snapshots=[snap])
    pdf = parse_version(
        pdf_src, _raw(tmp_path, "ss", "v2023-05-17", {"main.pdf": sample_pdf()}), tmp_path
    )
    assert pdf.doc_number == "SS1/23"
    assert pdf.version_date == date(2023, 5, 17)
    assert pdf.effective_from == date(2024, 5, 17)


def test_parse_version_rejects_empty_documents(tmp_path: Path) -> None:
    empty = _raw(tmp_path, "fca", "current", {"s01.html": b"<html></html>"})
    src = _source(id="fca", regulator="FCA", kind="fca_chapter", chapter="sysc8", url=None)
    with pytest.raises(ValueError, match="paragraphs parsed"):
        parse_version(src, empty, tmp_path)


def test_parse_all_reads_manifest_and_skips_unknown(tmp_path: Path) -> None:
    raw = _raw(tmp_path, "doc", "current", {"main.html": RBI_PAGE})
    stray = _raw(tmp_path, "removed-doc", "current", {"main.html": RBI_PAGE})
    write_manifest([raw, stray], tmp_path / "manifest.jsonl")
    sources = tmp_path / "sources.yaml"
    import yaml  # noqa: PLC0415

    sources.write_text(yaml.safe_dump({"documents": [_source().model_dump(mode="json")]}))
    documents = parse_all(tmp_path, sources)
    assert [d.key for d in documents] == ["doc@current"]
