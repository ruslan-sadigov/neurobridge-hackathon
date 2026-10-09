// ─── Enums ───────────────────────────────────────────────────────────────────
export type Status = "MET" | "PARTIALLY_MET" | "NOT_MET" | "UNKNOWN";
export type Category =
  | "LEGAL" | "FINANCIAL" | "TECHNICAL" | "EXPERIENCE"
  | "CERTIFICATION" | "PERSONNEL" | "DOCUMENTATION"
  | "DELIVERY" | "COMMERCIAL" | "CONTRACTUAL";
export type MandatoryLevel = "MANDATORY" | "PREFERRED" | "INFORMATIONAL" | "UNKNOWN";
export type Severity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
export type Recommendation = "GO" | "GO_WITH_CONDITIONS" | "NO_GO";
export type JobStatus = "PENDING" | "RUNNING" | "COMPLETE" | "FAILED";
export type Method = "DETERMINISTIC_RULE" | "LLM_SEMANTIC" | "NO_EVIDENCE";
export type ReasonCode =
  | "ALL_CRITICAL_MANDATORY_MET"
  | "MANDATORY_CERTIFICATION_MISSING"
  | "MANDATORY_EVIDENCE_UNKNOWN"
  | "EXPERIENCE_THRESHOLD_NOT_MET"
  | "FINANCIAL_THRESHOLD_NOT_MET"
  | "DOCUMENT_REQUIRED_MISSING"
  | "DELIVERY_CONSTRAINT_RISK"
  | "CONFLICTING_TENDER_TERMS"
  | "MANDATORY_REQUIREMENT_NOT_MET"
  | "MANDATORY_PARTIALLY_MET";

// ─── Core Data Models ─────────────────────────────────────────────────────────
export interface SourceRef {
  document_id: string;
  page: number;
  section?: string;
  excerpt: string;
}

export interface NormalizedRule {
  rule_type: string;
  field?: string;
  operator?: string;
  value?: unknown;
  unit?: string;
  filters: Record<string, unknown>;
}

export interface Requirement {
  requirement_id: string;
  text: string;
  category: Category;
  mandatory_level: MandatoryLevel;
  normalized_rule: NormalizedRule;
  sources: SourceRef[];
  extraction_confidence: number;
}

export interface Evidence {
  evidence_id: string;
  type: string; // CERTIFICATE | FINANCIAL | PROJECT | COMPANY_FACT | DOCUMENT
  label: string;
  value: unknown;
  text: string;
  source: string;
  issued_date?: string;
  expiry_date?: string;
  metadata: Record<string, unknown>;
}

export interface ComplianceResult {
  requirement_id: string;
  status: Status;
  method: Method;
  supporting_evidence_ids: string[];
  rationale: string;
  confidence: number;
  risk_severity?: Severity;
  reason_code?: ReasonCode;
}

export interface RequirementWithResult extends Requirement {
  result: ComplianceResult;
  evidence_candidates: Array<{ evidence: Evidence; score: number }>;
}

export interface RiskItem {
  requirement_id: string;
  severity: Severity;
  explanation: string;
  recommended_action: string;
  reason_code: ReasonCode;
}

export interface DimensionScore {
  name: string;
  weight: number;
  score: number | null;
  coverage: number | null;
  requirement_count: number;
}

export interface ScoreSnapshot {
  dimensions: DimensionScore[];
  final_score: number;
  recommendation: Recommendation;
  reason_codes: ReasonCode[];
  overall_coverage: number;
  config: Record<string, unknown>;
}

export interface DocumentInfo {
  document_id: string;
  filename: string;
  pages: number;
}

export interface RequirementCounts {
  total: number;
  mandatory: number;
  MET: number;
  PARTIALLY_MET: number;
  NOT_MET: number;
  UNKNOWN: number;
}

export interface AnalysisSummary {
  analysis_id: string;
  status: JobStatus;
  error?: string;
  summary?: {
    warnings: string[];
    timings: Record<string, number>;
    parsing_coverage: number;
    requirement_count: number;
  };
  documents: DocumentInfo[];
  counts: RequirementCounts;
  recommendation?: Recommendation;
  final_score?: number;
}

// ─── UI State ─────────────────────────────────────────────────────────────────
export interface FilterState {
  status: Status | "ALL";
  category: Category | "ALL";
  mandatory: MandatoryLevel | "ALL";
  severity: Severity | "ALL";
}

export type AppView = "setup" | "loading" | "dashboard";

export type SortKey = "category" | "mandatory_level" | "status" | "risk_severity";
export type SortDir = "asc" | "desc";
