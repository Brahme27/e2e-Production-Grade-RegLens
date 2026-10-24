export type Regulator = "RBI" | "SEBI" | "FCA" | "PRA";

export interface Citation {
  number: number;
  label: string;
  chunk_id: string;
  doc_id: string;
  doc_key: string;
  ref: string;
  regulator: string;
  title: string;
  url: string;
  status: string;
  valid_from: string | null;
  valid_to: string | null;
  text: string;
}

export interface SentenceCheck {
  text: string;
  markers: number[];
  cited: boolean;
  supported: boolean;
  support: number;
}

export interface Answer {
  question: string;
  text: string;
  abstained: boolean;
  reason: string;
  route: string;
  as_of: string | null;
  citations: Citation[];
  verification: {
    ok: boolean;
    uncited_sentences: number;
    unsupported_sentences: number;
    invalid_markers: number[];
    sentences: SentenceCheck[];
  } | null;
  disclaimer: string;
  trace_id: string;
  cached: boolean;
}

export interface Source {
  number: number;
  label: string;
  doc_id: string;
  doc_key: string;
  ref: string;
  regulator: string;
  title: string;
  status: string;
  score: number;
}

export interface DocVersion {
  key: string;
  doc_id: string;
  version: string;
  regulator: string;
  doc_type: string;
  title: string;
  doc_number: string | null;
  url: string;
  topics: string[];
  applies_to: string[];
  issue_date: string | null;
  valid_from: string | null;
  valid_to: string | null;
  status: string;
  superseded_by: string | null;
  paragraph_count: number;
}

export interface Edge {
  source: string;
  target: string;
  type: string;
  method: string;
  effective: string | null;
  evidence: string;
}

export interface Paragraph {
  ref: string;
  text: string;
  section_path: string[];
  kind: string;
  effective_from: string | null;
  notes: string[];
}

export interface ParsedDocument {
  doc_id: string;
  version: string;
  regulator: string;
  title: string;
  doc_number: string | null;
  url: string;
  version_date: string | null;
  effective_from: string | null;
  paragraphs: Paragraph[];
}

export interface Change {
  ref: string;
  kind: "added" | "removed" | "changed" | "unchanged";
  old_text: string;
  new_text: string;
  similarity: number;
  word_diff: string;
  section: string;
  substantive: boolean;
}

export interface ObligationRow {
  obligation_id: string;
  run_id: string;
  doc_key: string;
  source_ref: string;
  text: string;
  deadline: string;
  severity: string;
  gap_id: number;
  entity: string;
  status: "covered" | "partially_covered" | "not_covered";
  rationale: string;
  policy_refs: string[];
  confidence: number;
  review_status: "pending" | "approved" | "overridden";
  reviewer_note: string;
}

export interface Entity {
  id: string;
  name: string;
  jurisdiction: string;
  applies_to: string[];
}
