"""Supersession extraction, validity intervals, overrides, evaluation and the DB load."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml
from sqlalchemy import select

from reglens.config import Settings
from reglens.evals.supersession import load_gold, score
from reglens.llm.client import LLMClient, LLMResponse, LLMUnavailableError
from reglens.parse.model import Paragraph, ParsedDocument, save_documents
from reglens.store.db import DocumentVersion, SupersessionEdge, make_engine, session_scope
from reglens.temporal import run as temporal_run
from reglens.temporal.supersession import (
    Edge,
    edges_from_json,
    edges_to_json,
    generic_repeal_clauses,
    llm_edges,
    repair_numbers,
    rule_edges,
)
from reglens.temporal.validity import compute_validity, paragraph_interval, stated_commencement


def doc(
    doc_id: str,
    title: str,
    paragraphs: list[tuple[str, str]],
    *,
    version: str = "current",
    regulator: str = "SEBI",
    effective: date | None = None,
    issue: date | None = None,
    number: str | None = None,
) -> ParsedDocument:
    return ParsedDocument(
        doc_id=doc_id,
        version=version,
        regulator=regulator,
        doc_type="circular",
        title=title,
        url="u",
        topics=["t"],
        applies_to=["commercial_banks"],
        doc_number=number,
        issue_date=issue,
        effective_from=effective,
        paragraphs=[Paragraph(ref, text) for ref, text in paragraphs],
    )


OLD_MASTER = doc(
    "old-master",
    "Master Circular on the redressal of investor grievances through SCORES",
    [("1", "1. Entities shall redress complaints within 21 days.")],
    effective=date(2022, 11, 7),
    number="SEBI/HO/OIAE/IGRD/P/CIR/2022/0150",
)
NEW_CIRCULAR = doc(
    "new-circular",
    "Redressal of investor grievances through the SCORES platform",
    [
        ("5", "5. The Modification in Cyber Security framework (CIR/MRD/DP/13/2015) is a topic."),
        (
            "6",
            "6. This Circular shall rescind the Master Circular SEBI/HO/OIAE/IGRD/P/CIR/2022/0150 "
            "dated November 07, 2022 with effect from December 04, 2023.",
        ),
        (
            "52",
            "52. This Circular rescinds the following circulars: i. Circular no.CIR/OIAE/1/2014 "
            "dated December 18, 2014 ii. Circular no.SEBI/HO/OIAE/IGRD/CIR/P/2018/58 dated March 26, 2018",
        ),
    ],
    effective=date(2023, 9, 20),
)
CLARIFICATION = doc(
    "clarification",
    "Clarifications to Master Circular on the redressal of investor grievances through SCORES",
    [("1", "1. Clarifications on timelines follow.")],
    effective=date(2024, 1, 5),
)
RBI_NEW = doc(
    "rbi-new",
    "Reserve Bank of India (Commercial Banks - Know Your Customer) Directions, 2025",
    [
        (
            "80",
            "80. With the issue of these Directions, the existing Directions, instructions, and "
            "guidelines relating to Know Your Customer as applicable to Commercial Banks stand repealed.",
        )
    ],
    regulator="RBI",
    effective=date(2026, 10, 1),
    issue=date(2025, 11, 28),
)
RBI_OLD = doc(
    "rbi-old",
    "Master Direction - Know Your Customer (KYC) Direction, 2016",
    [
        ("1", "1. These directions shall come into force from April 1, 2016."),
        ("2", "2. CDD rules."),
    ],
    regulator="RBI",
    effective=date(2025, 8, 14),
    issue=date(2016, 2, 25),
)
CORPUS = [OLD_MASTER, NEW_CIRCULAR, CLARIFICATION, RBI_NEW, RBI_OLD]


# ---------------------------------------------------------------- rules
def test_rule_edges_by_number_list_and_title() -> None:
    edges = {e.pair: e for e in rule_edges(CORPUS)}
    main = edges[("new-circular", "old-master", "SUPERSEDES")]
    assert main.effective == date(2023, 12, 4)
    assert main.evidence == "new-circular@current ¶6"
    assert ("new-circular", "ext:CIR/OIAE/1/2014", "SUPERSEDES") in edges  # list item inherits
    assert ("new-circular", "ext:SEBI/HO/OIAE/IGRD/CIR/P/2018/58", "SUPERSEDES") in edges
    assert not any("CIR/MRD/DP/13/2015" in t for _, t, _ in edges)  # "Modification" is a title word
    assert ("clarification", "old-master", "AMENDS") in edges
    assert not any(s == "rbi-new" for s, _, _ in edges)  # generic repeals need the LLM


def test_repair_numbers_rejoins_wrapped_pdf_numbers() -> None:
    assert (
        repair_numbers("(SEBI/HO/MRD1/MRD1_DTCS/P/CIR/2 022/68)")
        == "(SEBI/HO/MRD1/MRD1_DTCS/P/CIR/2022/68)"
    )
    assert (
        repair_numbers("SEBI/HO/MRD/CSC/OW/P/2019 / /28528/1")
        == "SEBI/HO/MRD/CSC/OW/P/2019/28528/1"
    )
    assert repair_numbers("IMD￾I/DOF2") == "IMD-I/DOF2"


def test_edges_json_round_trip() -> None:
    edges = rule_edges(CORPUS)
    assert edges_from_json(edges_to_json(edges)) == edges


# ---------------------------------------------------------------- LLM for generic repeals
class ScriptedLLM:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.prompts: list[str] = []

    def __call__(
        self, alias: str, messages: list[dict[str, str]], *, json_mode: bool, max_tokens: int
    ) -> LLMResponse:
        self.prompts.append(messages[-1]["content"])
        return LLMResponse(self.answer, model="fake")


def test_llm_edges_only_for_generic_clauses_and_only_valid_ids(tmp_path: Path) -> None:
    assert generic_repeal_clauses(RBI_NEW)[0][0] == "80"
    backend = ScriptedLLM('{"repealed": ["rbi-old", "invented-id"], "reason": "same subject"}')
    edges = llm_edges(CORPUS, LLMClient(backend, tmp_path))
    assert [(e.source, e.target, e.method) for e in edges] == [("rbi-new", "rbi-old", "llm")]
    assert len(backend.prompts) == 1
    assert (
        "rbi-old" in backend.prompts[0] and "old-master" not in backend.prompts[0]
    )  # same regulator only


def test_llm_edges_survive_a_broken_model(tmp_path: Path) -> None:
    class Broken:
        def __call__(self, *args: object, **kwargs: object) -> LLMResponse:
            raise LLMUnavailableError("down")

    assert llm_edges(CORPUS, LLMClient(Broken(), tmp_path)) == []


# ---------------------------------------------------------------- validity
def test_validity_versions_repeals_commencement_and_status() -> None:
    v1 = doc(
        "ss",
        "SS",
        [("1.1", "Text.")],
        regulator="PRA",
        version="v2021",
        effective=date(2022, 3, 31),
    )
    v2 = doc(
        "ss",
        "SS",
        [("1.1", "Text.")],
        regulator="PRA",
        version="current",
        effective=date(2026, 3, 1),
    )
    future = doc("rule", "Rule", [("1", "1. Text")], regulator="PRA", effective=date(2027, 1, 1))
    edges = [
        Edge("rbi-new", "rbi-old", "SUPERSEDES", "llm"),
        Edge("new-circular", "old-master", "SUPERSEDES", "rule", date(2023, 12, 4)),
    ]
    validity = compute_validity([*CORPUS, v1, v2, future], edges, today=date(2026, 10, 24))

    assert validity["ss@v2021"].valid_to == date(2026, 3, 1)
    assert validity["ss@v2021"].status == "superseded"
    assert validity["ss@current"].status == "current"
    assert validity["rule@current"].status == "future"
    old = validity["rbi-old@current"]
    assert old.valid_from == date(2016, 4, 1)  # stated commencement beats the "updated as on" date
    assert old.valid_to == date(2025, 11, 28)  # repealed when the new directions were *issued*
    assert old.superseded_by == "rbi-new"
    assert validity["old-master@current"].valid_to == date(2023, 12, 4)
    assert old.applies_on(date(2020, 1, 1)) and not old.applies_on(date(2025, 11, 28))


def test_stated_commencement() -> None:
    assert stated_commencement(RBI_OLD) == date(2016, 4, 1)
    assert stated_commencement(OLD_MASTER) is None


def test_paragraph_interval_for_oldest_and_later_versions() -> None:
    validity = compute_validity([RBI_OLD], [], today=date(2026, 10, 24))["rbi-old@current"]
    amended = Paragraph("3", "3. Amended text.", effective_from=date(2020, 1, 9))
    assert paragraph_interval(RBI_OLD, amended, validity, earliest=True) == (date(2016, 4, 1), None)
    plain = Paragraph("2", "2. CDD rules.")
    assert paragraph_interval(RBI_OLD, plain, validity, earliest=True)[0] == date(2016, 2, 25)
    assert paragraph_interval(RBI_OLD, plain, validity, earliest=False)[0] == date(2016, 4, 1)


# ---------------------------------------------------------------- evaluation
def test_score_against_gold(tmp_path: Path) -> None:
    gold_file = tmp_path / "gold.yaml"
    gold_file.write_text(
        yaml.safe_dump(
            {
                "labelled_sources": ["new-circular", "rbi-new"],
                "edges": [
                    {"source": "new-circular", "target": "old-master", "type": "SUPERSEDES"},
                    {
                        "source": "new-circular",
                        "target": "ext:CIR/OIAE/1/2014",
                        "type": "SUPERSEDES",
                    },
                    {"source": "rbi-new", "target": "rbi-old", "type": "SUPERSEDES"},
                ],
            }
        )
    )
    gold = load_gold(gold_file)
    result = score(rule_edges(CORPUS), gold)
    assert result["true_positives"] == 2
    assert result["recall"] == pytest.approx(2 / 3, abs=0.001)
    assert "rbi-new|rbi-old|SUPERSEDES" in result["missed"]
    internal = score(rule_edges(CORPUS), gold, internal_only=True)
    assert internal["gold"] == 2


# ---------------------------------------------------------------- run: overrides + DB
def test_overrides_and_database_load(tmp_path: Path) -> None:
    overrides = tmp_path / "overrides.yaml"
    overrides.write_text(
        yaml.safe_dump(
            {
                "reject": [
                    {"source": "new-circular", "target": "old-master", "type": "SUPERSEDES"}
                ],
                "add": [{"source": "rbi-new", "target": "rbi-old", "type": "SUPERSEDES"}],
            }
        )
    )
    raw, reviewed, validity = temporal_run.build_temporal(
        CORPUS, None, date(2026, 10, 24), overrides
    )
    assert ("new-circular", "old-master", "SUPERSEDES") in {e.pair for e in raw}
    pairs = {e.pair for e in reviewed}
    assert ("new-circular", "old-master", "SUPERSEDES") not in pairs
    assert ("rbi-new", "rbi-old", "SUPERSEDES") in pairs
    assert validity["rbi-old@current"].status == "superseded"

    settings = Settings(data_dir=tmp_path / "data", artifacts_dir=tmp_path / "artifacts")
    (settings.artifacts_dir).mkdir()
    temporal_run.save_temporal(CORPUS, reviewed, validity, settings)
    temporal_run.save_temporal(CORPUS, reviewed, validity, settings)  # idempotent reload
    with session_scope(make_engine(settings.sqlalchemy_url)) as session:
        versions = session.scalars(select(DocumentVersion)).all()
        assert len(versions) == len(CORPUS)
        assert session.get(DocumentVersion, "rbi-old@current").superseded_by == "rbi-new"
        assert len(session.scalars(select(SupersessionEdge)).all()) == len(reviewed)
    assert (settings.data_dir / "processed" / "validity.json").exists()


def test_main_rules_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(data_dir=tmp_path / "data", artifacts_dir=tmp_path / "artifacts")
    save_documents(CORPUS, settings.data_dir / "processed" / "documents")
    settings.artifacts_dir.mkdir()
    monkeypatch.setattr(temporal_run, "get_settings", lambda: settings)
    temporal_run.main(["--no-llm", "--today", "2026-10-24"])
    assert (settings.data_dir / "processed" / "supersession_edges.json").exists()
    assert (settings.reports_dir / "supersession_eval.json").exists()  # real gold file is used
