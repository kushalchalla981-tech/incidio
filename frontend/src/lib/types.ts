export interface LogCreate {
  timestamp: string;
  service: string;
  level: string;
  message: string;
  raw_log: string;
  metadata?: Record<string, unknown>;
}

export interface LogResponse {
  id: string;
  timestamp: string;
  service: string | null;
  level: string;
  message: string;
  raw_log: string;
  template_id: number | null;
  parameters: unknown[] | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface LogUploadResponse {
  logs_processed: number;
  logs_failed: number;
  errors: string[];
}

export interface IncidentCreate {
  title: string;
  description?: string;
  severity: string;
  start_time: string;
  affected_services?: string[];
  metadata?: Record<string, unknown>;
}
export interface IncidentUpdate {
  title?: string;
  description?: string;
  severity?: string;
  status?: string;
  end_time?: string;
  root_cause?: string;
  resolution?: string;
}

export interface IncidentResponse {
  id: string;
  title: string;
  description: string | null;
  severity: string;
  status: string;
  start_time: string;
  end_time: string | null;
  affected_services: string[];
  root_cause: string | null;
  resolution: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface HealthResponse {
  status: string;
  database: string;
  timestamp: string;
}

export interface LogFilters {
  service?: string;
  level?: string;
  start_time?: string;
  end_time?: string;
  limit?: number;
  offset?: number;
}

export interface VectorSearchQuery {
  query: string;
  limit?: number;
  service?: string;
  level?: string;
}

export interface VectorSearchResultItem {
  id: string;
  timestamp: string;
  service: string | null;
  level: string;
  message: string;
  raw_log: string;
  similarity: number;
}

export interface VectorSearchResponse {
  results: VectorSearchResultItem[];
  query: string;
  total: number;
}

export interface BackfillResponse {
  processed: number;
  failed: number;
  errors: string[];
}

export interface IncidentFilters {
  status?: string;
  severity?: string;
  limit?: number;
  offset?: number;
}

export type ScanStatus = "queued" | "running" | "completed" | "failed";
export type ScanSeverity = "critical" | "high" | "medium" | "low" | "informational";
export type ScanGrade = "A" | "B" | "C" | "D" | "F";
export type SourceType = "repo" | "url" | "zip";
export type FindingStatus = "open" | "resolved" | "accepted" | "false_positive";
export type Confidence = "confirmed" | "strong" | "potential" | "informational";

export interface ScanFinding {
  id: string;
  scan_id: string;
  severity: ScanSeverity;
  category: string;
  rule_id: string | null;
  file: string;
  line: number | null;
  evidence: string;
  description: string;
  remediation: string | null;
  promoted_to_incident: boolean;
  status: FindingStatus;
  status_note: string | null;
  confidence: Confidence;
  cwe: string | null;
  owasp: string | null;
  title: string | null;
  impact: string | null;
  attack_scenario: string | null;
  verification: string | null;
  suggested_fix: string | null;
  source: string | null;
}

export interface ScanRun {
  id: string;
  repo_url: string;
  name: string | null;
  status: ScanStatus;
  score: number | null;
  grade: ScanGrade | null;
  summary: string | null;
  error: string | null;
  total_files: number;
  scanned_files?: string[];
  metadata: Record<string, unknown>;   // sub-scores: {secrets_score, code_score, config_score, ...}
  finding_count: number;
  source_type: SourceType;
  project_id: string | null;
  source_ref: string | null;
  scan_options: Record<string, unknown>;
  scan_version: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScanRunDetail extends ScanRun {
  findings: ScanFinding[];
}

export interface ScanFilters {
  limit?: number;
  offset?: number;
}

export interface SecurityProject {
  id: string;
  name: string | null;
  source_type: SourceType;
  source_ref: string;
  tech_stack: Record<string, unknown>;
  last_scan_id: string | null;
  created_at: string;
  updated_at: string;
  last_scan_status: ScanStatus | null;
  last_scan_score: number | null;
  last_scan_grade: ScanGrade | null;
  last_scan_summary: string | null;
  last_scan_created_at: string | null;
}

export interface SecurityProjectDetail extends SecurityProject {
  scans: ScanRun[];
}

export interface SecurityScanCreate {
  source_type: SourceType;
  source_ref: string;
  name?: string;
  options?: Record<string, unknown>;
}

export interface FindingStatusUpdate {
  status: FindingStatus;
  note?: string;
}

export interface CompareItem {
  key: string;
  severity: string;
  category: string;
  file: string;
  line: number | null;
  title: string | null;
  base_status: string | null;
  target_status: string | null;
}

export interface ScanComparison {
  base_scan_id: string;
  target_scan_id: string;
  added: CompareItem[];
  removed: CompareItem[];
  status_changed: CompareItem[];
  unchanged: number;
}
