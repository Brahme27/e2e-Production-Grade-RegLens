"""What changed between two versions of a document, paragraph by paragraph.

Paragraphs are aligned by their ref ("2.1", "PRIN 2A.4.1R"). Each is reported as added,
removed, changed or unchanged; changed paragraphs carry a word-level diff and a similarity
score so trivial edits (punctuation, renumbered cross-references) can be told apart from
real changes in obligations.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Literal

from reglens.parse.model import ParsedDocument

ChangeKind = Literal["added", "removed", "changed", "unchanged"]
MINOR_CHANGE = 0.97  # word similarity above this = cosmetic edit
RENUMBERED_SIMILARITY = 0.6


@dataclass(frozen=True)
class ParagraphChange:
    ref: str
    kind: ChangeKind
    old_text: str
    new_text: str
    similarity: float
    word_diff: str  # "[-removed words-] {+added words+}" markup
    section: str

    @property
    def substantive(self) -> bool:
        return self.kind in ("added", "removed") or (
            self.kind == "changed" and self.similarity < MINOR_CHANGE
        )


def word_diff(old: str, new: str) -> tuple[str, float]:
    a, b = old.split(), new.split()
    matcher = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    out: list[str] = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            out.append(" ".join(a[i1:i2]))
        if op in ("delete", "replace"):
            out.append("[-" + " ".join(a[i1:i2]) + "-]")
        if op in ("insert", "replace"):
            out.append("{+" + " ".join(b[j1:j2]) + "+}")
    return " ".join(out), round(matcher.ratio(), 4)


def diff_versions(old: ParsedDocument, new: ParsedDocument) -> list[ParagraphChange]:
    old_by_ref = {p.ref: p for p in old.paragraphs}
    new_by_ref = {p.ref: p for p in new.paragraphs}
    changes: list[ParagraphChange] = []
    for para in new.paragraphs:
        section = " > ".join(para.section_path)
        before = old_by_ref.get(para.ref)
        if before is None:
            changes.append(
                ParagraphChange(
                    para.ref, "added", "", para.text, 0.0, "{+" + para.text + "+}", section
                )
            )
            continue
        if before.text == para.text:
            changes.append(
                ParagraphChange(para.ref, "unchanged", before.text, para.text, 1.0, "", section)
            )
            continue
        markup, similarity = word_diff(before.text, para.text)
        changes.append(
            ParagraphChange(
                para.ref, "changed", before.text, para.text, similarity, markup, section
            )
        )
    for para in old.paragraphs:
        if para.ref not in new_by_ref:
            changes.append(
                ParagraphChange(
                    para.ref,
                    "removed",
                    para.text,
                    "",
                    0.0,
                    "[-" + para.text + "-]",
                    " > ".join(para.section_path),
                )
            )
    return _pair_renumbered(changes)


def _pair_renumbered(changes: list[ParagraphChange]) -> list[ParagraphChange]:
    """A paragraph that was only renumbered shows up as removed + added: pair them up."""
    added = [c for c in changes if c.kind == "added"]
    removed = [c for c in changes if c.kind == "removed"]
    paired: dict[int, ParagraphChange] = {}
    used: set[int] = set()
    for new in added:
        best, best_ratio = None, RENUMBERED_SIMILARITY
        for index, old in enumerate(removed):
            if index in used:
                continue
            ratio = difflib.SequenceMatcher(
                a=old.old_text.split(), b=new.new_text.split(), autojunk=False
            ).quick_ratio()
            if ratio >= best_ratio:
                best, best_ratio = index, ratio
        if best is not None:
            used.add(best)
            old = removed[best]
            markup, similarity = word_diff(old.old_text, new.new_text)
            kind: ChangeKind = "unchanged" if old.old_text == new.new_text else "changed"
            paired[id(new)] = ParagraphChange(
                f"{old.ref} → {new.ref}",
                kind,
                old.old_text,
                new.new_text,
                similarity,
                markup,
                new.section,
            )
    result = [
        paired.get(id(c), c)
        for c in changes
        if not (c.kind == "removed" and removed.index(c) in used)
    ]
    return result


def summarise(changes: list[ParagraphChange]) -> dict[str, int]:
    counts = {"added": 0, "removed": 0, "changed": 0, "unchanged": 0, "substantive": 0}
    for change in changes:
        counts[change.kind] += 1
        counts["substantive"] += change.substantive
    return counts
