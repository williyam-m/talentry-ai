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
