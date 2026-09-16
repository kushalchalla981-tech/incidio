"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  backfillEmbeddings, createScan, createSecurityScan, createSecurityScanZip, getHealth,
  getIncidentById, getIncidents, getLogs, getScan, getScans, promoteFinding, searchLogs,
  getSecurityProjects, getSecurityProject, getSecurityScans, getSecurityScan,
  getSecurityFindings, updateFindingStatus, rerunSecurityScan, compareScans,
} from "./api";
import type { IncidentFilters, LogFilters, ScanFilters, VectorSearchQuery } from "./types";

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 30000,
  });
}

export function useLogs(filters?: LogFilters) {
  return useQuery({
    queryKey: ["logs", filters],
    queryFn: () => getLogs(filters),
    refetchInterval: 5000,
  });
}

export function useLogSearch(query: VectorSearchQuery) {
  return useQuery({
    queryKey: ["search", query],
    queryFn: () => searchLogs(query),
    enabled: query.query.length > 0,
  });
}

export function useBackfill() {
  return useMutation({
    mutationFn: backfillEmbeddings,
  });
}

export function useIncidents(filters?: IncidentFilters) {
  return useQuery({
    queryKey: ["incidents", filters],
    queryFn: () => getIncidents(filters),
    refetchInterval: 15000,
  });
}

export function useIncident(id: string) {
  return useQuery({
    queryKey: ["incident", id],
    queryFn: () => getIncidentById(id),
    enabled: id.length > 0,
    retry: false,
  });
}

export function useScans(filters?: ScanFilters) {
  return useQuery({
    queryKey: ["scans", filters],
    queryFn: () => getScans(filters),
    refetchInterval: (query) =>
      query.state.data?.some((s) => s.status === "queued" || s.status === "running") ? 3000 : false,
  });
}

export function useScan(id: string) {
  return useQuery({
    queryKey: ["scan", id],
    queryFn: () => getScan(id),
    refetchInterval: (query) => {
      const st = query.state.data?.status;
      return st === "completed" || st === "failed" ? false : 3000;
    },
  });
}

export function useCreateScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createScan,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scans"] }),
  });
}

export function usePromoteFinding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ scanId, findingId }: { scanId: string; findingId: string }) =>
      promoteFinding(scanId, findingId),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["scan", vars.scanId] });
      qc.invalidateQueries({ queryKey: ["scans"] });
      qc.invalidateQueries({ queryKey: ["incidents"] });
    },
  });
}

const isActiveScan = (s: { status: string } | undefined) =>
  s?.status === "queued" || s?.status === "running";

export function useSecurityProjects() {
  return useQuery({
    queryKey: ["security-projects"],
    queryFn: getSecurityProjects,
    refetchInterval: (query) =>
      query.state.data?.some((p) => p.last_scan_status === "queued" || p.last_scan_status === "running")
        ? 3000
        : false,
  });
}

export function useSecurityProject(id: string) {
  return useQuery({
    queryKey: ["security-project", id],
    queryFn: () => getSecurityProject(id),
    enabled: id.length > 0,
    refetchInterval: (query) =>
      query.state.data?.scans.some(isActiveScan) ? 3000 : false,
  });
}

export function useSecurityScans() {
  return useQuery({
    queryKey: ["security-scans"],
    queryFn: getSecurityScans,
    refetchInterval: (query) =>
      query.state.data?.some(isActiveScan) ? 3000 : false,
  });
}

export function useSecurityScan(id: string) {
  return useQuery({
    queryKey: ["security-scan", id],
    queryFn: () => getSecurityScan(id),
    enabled: id.length > 0,
    retry: false,
    refetchInterval: (query) => (isActiveScan(query.state.data) ? 3000 : false),
  });
}

export function useSecurityFindings(filters?: { severity?: string; category?: string; status?: string; project_id?: string }) {
  return useQuery({
    queryKey: ["security-findings", filters],
    queryFn: () => getSecurityFindings(filters),
  });
}

export function useCreateSecurityScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createSecurityScan,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["security-scans"] });
      qc.invalidateQueries({ queryKey: ["security-projects"] });
    },
  });
}

export function useCreateSecurityScanZip() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ file, name }: { file: File; name?: string }) => createSecurityScanZip(file, name),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["security-scans"] });
      qc.invalidateQueries({ queryKey: ["security-projects"] });
    },
  });
}

export function useUpdateFindingStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, update }: { id: string; update: Parameters<typeof updateFindingStatus>[1] }) =>
      updateFindingStatus(id, update),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["security-findings"] });
      qc.invalidateQueries({ queryKey: ["security-scan"] });
    },
  });
}

export function useRerunSecurityScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: rerunSecurityScan,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["security-scans"] });
      qc.invalidateQueries({ queryKey: ["security-projects"] });
      qc.invalidateQueries({ queryKey: ["security-scan"] });
    },
  });
}

export function useCompareScans(projectId: string, base: string, target: string) {
  return useQuery({
    queryKey: ["security-compare", projectId, base, target],
    queryFn: () => compareScans(projectId, base, target),
    enabled: projectId.length > 0 && base.length > 0 && target.length > 0 && base !== target,
  });
}
