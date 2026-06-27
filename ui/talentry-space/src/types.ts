/** Shared TypeScript types mirroring the Talentry API responses. */

export interface ScoreBreakdown {
  title_alignment: number;
  semantic_fit: number;
  skill_evidence: number;
  experience_band: number;
  location: number;
  behavioural: number;
  honeypot_penalty: number;
  final: number;
}

export interface RankedRow {
  candidate_id: string;
  rank: number;
  score: number;
  reasoning: string;
  breakdown: ScoreBreakdown;
}

export interface JDSummary {
  title: string;
  seniority: string;
  min_years: number;
  max_years: number;
  must_have_skills: string[];
  preferred_locations: string[];
}

export interface RankResponse {
  version: string;
  jd: JDSummary;
  n_candidates: number;
  n_returned: number;
  session_id: string | null;
  results: RankedRow[];
}

// ── Schema validation ───────────────────────────────────────────────────────

export interface SchemaErrorItem {
  path: string;
  code:
    | "missing_required"
    | "wrong_type"
    | "enum_violation"
    | "out_of_range"
    | "pattern_mismatch"
    | "bad_date"
    | "unknown_property"
    | "too_few_items"
    | "too_many_items";
  message: string;
  expected: string;
  actual: string;
}

export interface RowReport {
  index: number;
  candidate_id: string | null;
  errors: SchemaErrorItem[];
  truncated: boolean;
}

export interface ValidationReport {
  n_total: number;
  n_valid: number;
  n_invalid: number;
  first_invalid_index: number | null;
  errors_by_row: RowReport[];
}

export type DiffLineKind = "match" | "missing" | "extra" | "wrong";

export interface DiffLine {
  kind: DiffLineKind;
  path: string;
  expected?: unknown;
  actual?: unknown;
}

export interface SchemaDiffPayload {
  expected_skeleton: unknown;
  actual: unknown;
  lines: DiffLine[];
}

export interface ValidateResponse {
  report: ValidationReport;
  diff?: SchemaDiffPayload;
}

// ── Schema-validation error returned by /api/rank (HTTP 422) ───────────────

export interface RankErrorResponse {
  error: "schema_validation_failed" | string;
  message: string;
  report?: ValidationReport;
  diff?: SchemaDiffPayload;
}

// ── Resume parsing ──────────────────────────────────────────────────────────

export interface ParsedResume {
  record: Record<string, unknown>;
  schema_errors: SchemaErrorItem[];
  schema_ok: boolean;
  filename: string | null;
}

export interface ParseResumesResponse {
  n_uploaded: number;
  n_parsed: number;
  n_failed: number;
  results: ParsedResume[];
  errors: { filename: string; error: string }[];
}
