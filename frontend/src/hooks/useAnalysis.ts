"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { FilterState } from "@/types";

const POLL_INTERVAL = 2000;

export function useAnalysisSummary(analysisId: string | null) {
  return useQuery({
    queryKey: ["analysis", analysisId],
    queryFn: () => api.getAnalysis(analysisId!),
    enabled: !!analysisId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "COMPLETE" || status === "FAILED") return false;
      return POLL_INTERVAL;
    },
    staleTime: 0,
  });
}

export function useRequirements(
  analysisId: string | null,
  filters?: Partial<Pick<FilterState, "status" | "category" | "mandatory">>
) {
  const params: Record<string, string> = {};
  if (filters?.status && filters.status !== "ALL") params.status = filters.status;
  if (filters?.category && filters.category !== "ALL") params.category = filters.category;
  if (filters?.mandatory && filters.mandatory !== "ALL") params.mandatory_level = filters.mandatory;

  return useQuery({
    queryKey: ["requirements", analysisId, params],
    queryFn: () => api.getRequirements(analysisId!, params),
    enabled: !!analysisId,
    staleTime: 30_000,
  });
}

export function useRisks(analysisId: string | null) {
  return useQuery({
    queryKey: ["risks", analysisId],
    queryFn: () => api.getRisks(analysisId!),
    enabled: !!analysisId,
    staleTime: 30_000,
  });
}

export function useScore(analysisId: string | null) {
  return useQuery({
    queryKey: ["score", analysisId],
    queryFn: () => api.getScore(analysisId!),
    enabled: !!analysisId,
    staleTime: 30_000,
  });
}

export function usePage(documentId: string | null, page: number | null) {
  return useQuery({
    queryKey: ["page", documentId, page],
    queryFn: () => api.getPage(documentId!, page!),
    enabled: !!documentId && page != null,
    staleTime: Infinity,
  });
}

export function useContradictions(analysisId: string | null) {
  return useQuery({
    queryKey: ["contradictions", analysisId],
    queryFn: () => api.getContradictions(analysisId!),
    enabled: !!analysisId,
    staleTime: 30_000,
  });
}
