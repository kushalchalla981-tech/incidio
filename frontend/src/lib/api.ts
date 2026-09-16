import type {
  BackfillResponse, HealthResponse, IncidentFilters, IncidentResponse, LogFilters, LogResponse,
  LogUploadResponse, ScanFilters, ScanFinding, ScanRun, ScanRunDetail, VectorSearchQuery, VectorSearchResponse,
  SecurityProject, SecurityProjectDetail, SecurityScanCreate, FindingStatusUpdate, ScanComparison,
} from "./types";

const BASE = "";

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    const err = new Error(`API ${res.status}: ${body}`) as Error & { status: number };
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function getHealth(): Promise<HealthResponse> {
  return fetchJSON<HealthResponse>("/health");
}

export async function getLogs(filters?: LogFilters): Promise<LogResponse[]> {
  const params = new URLSearchParams();
  if (filters?.service) params.set("service", filters.service);
  if (filters?.level) params.set("level", filters.level);
  if (filters?.start_time) params.set("start_time", filters.start_time);
  if (filters?.end_time) params.set("end_time", filters.end_time);
  if (filters?.limit) params.set("limit", String(filters.limit));
  if (filters?.offset) params.set("offset", String(filters.offset));
  const qs = params.toString();
  return fetchJSON<LogResponse[]>(`/api/v1/logs${qs ? `?${qs}` : ""}`);
}

export async function getLogById(id: string): Promise<LogResponse> {
  return fetchJSON<LogResponse>(`/api/v1/logs/${id}`);
}

export async function uploadLogFile(file: File): Promise<LogUploadResponse> {
  const form = new FormData();
  form.set("file", file);
  const res = await fetch(`${BASE}/api/v1/logs/upload`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json();
}

export async function getIncidents(filters?: IncidentFilters): Promise<IncidentResponse[]> {
  const params = new URLSearchParams();
  if (filters?.status) params.set("status", filters.status);
  if (filters?.severity) params.set("severity", filters.severity);
  if (filters?.limit) params.set("limit", String(filters.limit));
  if (filters?.offset) params.set("offset", String(filters.offset));
  const qs = params.toString();
  return fetchJSON<IncidentResponse[]>(`/api/v1/incidents${qs ? `?${qs}` : ""}`);
}

export async function getIncidentById(id: string): Promise<IncidentResponse> {
  return fetchJSON<IncidentResponse>(`/api/v1/incidents/${id}`);
}

export async function createIncident(data: {
  title: string;
  severity: string;
  start_time: string;
  description?: string;
  affected_services?: string[];
  metadata?: Record<string, unknown>;
}): Promise<IncidentResponse> {
  return fetchJSON<IncidentResponse>("/api/v1/incidents", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function searchLogs(query: VectorSearchQuery): Promise<VectorSearchResponse> {
  return fetchJSON<VectorSearchResponse>("/api/v1/search", {
    method: "POST",
    body: JSON.stringify(query),
  });
}

export async function backfillEmbeddings(): Promise<BackfillResponse> {
  return fetchJSON<BackfillResponse>("/api/v1/search/backfill", { method: "POST" });
}

export async function updateIncident(id: string, data: Partial<{
  title: string;
  description: string;
  severity: string;
  status: string;
  end_time: string;
  root_cause: string;
  resolution: string;
}>): Promise<IncidentResponse> {
  return fetchJSON<IncidentResponse>(`/api/v1/incidents/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function createScan(data: { repo_url: string; name?: string }): Promise<ScanRun> {
  return fetchJSON<ScanRun>("/api/v1/scans", { method: "POST", body: JSON.stringify(data) });
}
export async function getScans(filters?: ScanFilters): Promise<ScanRun[]> {
  const params = new URLSearchParams();
  if (filters?.limit) params.set("limit", String(filters.limit));
  if (filters?.offset) params.set("offset", String(filters.offset));
  const qs = params.toString();
  return fetchJSON<ScanRun[]>(`/api/v1/scans${qs ? `?${qs}` : ""}`);
}
export async function getScan(id: string): Promise<ScanRunDetail> {
  return fetchJSON<ScanRunDetail>(`/api/v1/scans/${id}`);
}
export async function promoteFinding(scanId: string, findingId: string): Promise<IncidentResponse> {
  return fetchJSON<IncidentResponse>(`/api/v1/scans/${scanId}/findings/${findingId}/incident`, { method: "POST" });
}

export async function getIncidentServices(): Promise<string[]> {
  return fetchJSON<string[]>("/api/v1/incidents/services");
}

export async function createSecurityScan(data: SecurityScanCreate): Promise<ScanRun> {
  return fetchJSON<ScanRun>("/api/v1/security/scans", { method: "POST", body: JSON.stringify(data) });
}
export async function createSecurityScanZip(file: File, name?: string): Promise<ScanRun> {
  const form = new FormData();
  form.set("file", file);
  if (name) form.set("name", name);
  const res = await fetch(`${BASE}/api/v1/security/scans/zip`, { method: "POST", body: form });
  if (!res.ok) {
    const body = await res.text();
    const err = new Error(`API ${res.status}: ${body}`) as Error & { status: number };
    err.status = res.status;
    throw err;
  }
  return res.json();
}
export async function getSecurityProjects(): Promise<SecurityProject[]> {
  return fetchJSON<SecurityProject[]>("/api/v1/security/projects");
}
export async function getSecurityProject(id: string): Promise<SecurityProjectDetail> {
  return fetchJSON<SecurityProjectDetail>(`/api/v1/security/projects/${id}`);
}
export async function getSecurityScans(): Promise<ScanRun[]> {
  return fetchJSON<ScanRun[]>("/api/v1/security/scans");
}
export async function getSecurityScan(id: string): Promise<ScanRunDetail> {
  return fetchJSON<ScanRunDetail>(`/api/v1/security/scans/${id}`);
}
export async function getSecurityFindings(filters?: {
  severity?: string; category?: string; status?: string; project_id?: string; limit?: number;
}): Promise<ScanFinding[]> {
  const params = new URLSearchParams();
  if (filters?.severity) params.set("severity", filters.severity);
  if (filters?.category) params.set("category", filters.category);
  if (filters?.status) params.set("status", filters.status);
  if (filters?.project_id) params.set("project_id", filters.project_id);
  if (filters?.limit) params.set("limit", String(filters.limit));
  const qs = params.toString();
  return fetchJSON<ScanFinding[]>(`/api/v1/security/findings${qs ? `?${qs}` : ""}`);
}
export async function updateFindingStatus(id: string, update: FindingStatusUpdate): Promise<ScanFinding> {
  return fetchJSON<ScanFinding>(`/api/v1/security/findings/${id}`, {
    method: "PATCH",
    body: JSON.stringify(update),
  });
}
export async function rerunSecurityScan(scanId: string): Promise<ScanRun> {
  return fetchJSON<ScanRun>(`/api/v1/security/scans/${scanId}/rerun`, { method: "POST" });
}
export async function compareScans(projectId: string, base: string, target: string): Promise<ScanComparison> {
  return fetchJSON<ScanComparison>(`/api/v1/security/projects/${projectId}/compare?base=${encodeURIComponent(base)}&target=${encodeURIComponent(target)}`);
}
