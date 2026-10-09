import axios from "axios";
import type {
  AnalysisSummary,
  Contradiction,
  RequirementWithResult,
  PageContent,
  RiskItem,
  ScoreSnapshot,
} from "@/types";
import {
  MOCK_ANALYSIS_ID,
  MOCK_REQUIREMENTS,
  MOCK_RISKS,
  MOCK_SCORE,
  MOCK_SUMMARY,
  delay,
} from "./mockData";

const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === "true";
const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const client = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 120_000, // uploads parse PDFs synchronously
});

// Surface the backend's own message ({"detail": "..."}) instead of "Request failed with status code 415".
client.interceptors.response.use(
  (r) => r,
  (err) => {
    const detail = err?.response?.data?.detail;
    if (detail) err.message = typeof detail === "string" ? detail : JSON.stringify(detail);
    else if (err?.code === "ERR_NETWORK")
      err.message = `Cannot reach the API at ${BASE_URL}. Is the backend running, and is this site's URL in its CORS_ORIGINS?`;
    return Promise.reject(err);
  }
);

/** Original PDF for a tender document (opens in a new tab; append #page=N to jump to a page). */
export const documentFileUrl = (documentId: string) =>
  USE_MOCK ? "#" : `${BASE_URL}/documents/${documentId}/file`;

// ─── Mock Implementations ─────────────────────────────────────────────────────
const mock = {
  createAnalysis: async () => {
    await delay(300);
    return { analysis_id: MOCK_ANALYSIS_ID, status: "PENDING" };
  },
  uploadDocuments: async (_id: string, files: File[]) => {
    await delay(500 * files.length);
    return {
      documents: files.map((f, i) => ({
        document_id: `doc-00${i + 1}`,
        filename: f.name,
        size: f.size,
        checksum: `md5-${i}`,
      })),
    };
  },
  attachSupplier: async (_id: string, profile: Record<string, unknown>) => {
    await delay(200);
    return { ok: true, company_name: profile.company_name as string };
  },
  runAnalysis: async (_id: string) => {
    await delay(200);
    return { analysis_id: MOCK_ANALYSIS_ID, status: "PENDING" };
  },
  getAnalysis: async (_id: string): Promise<AnalysisSummary> => {
    await delay(100);
    return MOCK_SUMMARY;
  },
  getRequirements: async (
    _id: string,
    filters?: { status?: string; category?: string; mandatory_level?: string }
  ): Promise<RequirementWithResult[]> => {
    await delay(200);
    let reqs = [...MOCK_REQUIREMENTS];
    if (filters?.status) reqs = reqs.filter((r) => r.result.status === filters.status);
    if (filters?.category) reqs = reqs.filter((r) => r.category === filters.category);
    if (filters?.mandatory_level) reqs = reqs.filter((r) => r.mandatory_level === filters.mandatory_level);
    return reqs;
  },
  getRisks: async (_id: string): Promise<RiskItem[]> => {
    await delay(150);
    return MOCK_RISKS;
  },
  getScore: async (_id: string): Promise<ScoreSnapshot> => {
    await delay(100);
    return MOCK_SCORE;
  },
  getContradictions: async (_id: string): Promise<Contradiction[]> => {
    await delay(100);
    return [];
  },
  getPage: async (documentId: string, page: number): Promise<PageContent> => {
    await delay(150);
    return {
      document_id: documentId,
      page,
      extraction_method: "native",
      text: "(mock mode) Page text is only available when connected to the backend.",
    };
  },
};

// ─── Real API Implementations ─────────────────────────────────────────────────
const real = {
  createAnalysis: async () => {
    const { data } = await client.post("/analyses");
    return data as { analysis_id: string; status: string };
  },
  uploadDocuments: async (analysisId: string, files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    const { data } = await client.post(`/analyses/${analysisId}/documents`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  },
  attachSupplier: async (analysisId: string, profile: Record<string, unknown>) => {
    const { data } = await client.post(`/analyses/${analysisId}/supplier`, profile);
    return data as { ok: boolean; company_name?: string };
  },
  runAnalysis: async (analysisId: string) => {
    const { data } = await client.post(`/analyses/${analysisId}/run`);
    return data as { analysis_id: string; status: string };
  },
  getAnalysis: async (analysisId: string): Promise<AnalysisSummary> => {
    const { data } = await client.get(`/analyses/${analysisId}`);
    return data;
  },
  getRequirements: async (
    analysisId: string,
    filters?: { status?: string; category?: string; mandatory_level?: string }
  ): Promise<RequirementWithResult[]> => {
    const { data } = await client.get(`/analyses/${analysisId}/requirements`, {
      params: filters,
    });
    return data;
  },
  getRisks: async (analysisId: string): Promise<RiskItem[]> => {
    const { data } = await client.get(`/analyses/${analysisId}/risks`);
    return data;
  },
  getScore: async (analysisId: string): Promise<ScoreSnapshot> => {
    const { data } = await client.get(`/analyses/${analysisId}/score`);
    return data;
  },
  getContradictions: async (analysisId: string): Promise<Contradiction[]> => {
    const { data } = await client.get(`/analyses/${analysisId}/contradictions`);
    return data;
  },
  getPage: async (documentId: string, page: number): Promise<PageContent> => {
    const { data } = await client.get(`/documents/${documentId}/pages/${page}`);
    return data;
  },
};

export const api = USE_MOCK ? mock : real;
