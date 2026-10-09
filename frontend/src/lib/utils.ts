import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import type { Category, MandatoryLevel, Recommendation, Severity, Status } from "@/types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// ─── Status ──────────────────────────────────────────────────────────────────
export const STATUS_CONFIG: Record<
  Status,
  { label: string; color: string; bg: string; border: string; dot: string }
> = {
  MET: {
    label: "Met",
    color: "text-emerald-700",
    bg: "bg-emerald-50",
    border: "border-emerald-200",
    dot: "bg-emerald-500",
  },
  PARTIALLY_MET: {
    label: "Partial",
    color: "text-amber-700",
    bg: "bg-amber-50",
    border: "border-amber-200",
    dot: "bg-amber-500",
  },
  NOT_MET: {
    label: "Not Met",
    color: "text-red-700",
    bg: "bg-red-50",
    border: "border-red-200",
    dot: "bg-red-500",
  },
  UNKNOWN: {
    label: "Unknown",
    color: "text-slate-600",
    bg: "bg-slate-100",
    border: "border-slate-200",
    dot: "bg-slate-400",
  },
};

// ─── Severity ─────────────────────────────────────────────────────────────────
export const SEVERITY_CONFIG: Record<
  Severity,
  { label: string; color: string; bg: string; border: string }
> = {
  CRITICAL: { label: "Critical", color: "text-red-700", bg: "bg-red-50", border: "border-red-300" },
  HIGH: { label: "High", color: "text-orange-700", bg: "bg-orange-50", border: "border-orange-300" },
  MEDIUM: { label: "Medium", color: "text-amber-700", bg: "bg-amber-50", border: "border-amber-300" },
  LOW: { label: "Low", color: "text-slate-600", bg: "bg-slate-50", border: "border-slate-200" },
};

// ─── Recommendation ───────────────────────────────────────────────────────────
export const RECOMMENDATION_CONFIG: Record<
  Recommendation,
  { label: string; color: string; bg: string; border: string; desc: string; ring: string }
> = {
  GO: {
    label: "GO",
    color: "text-emerald-700",
    bg: "bg-emerald-50",
    border: "border-emerald-300",
    desc: "Proceed with bid submission",
    ring: "#10b981",
  },
  GO_WITH_CONDITIONS: {
    label: "GO WITH CONDITIONS",
    color: "text-amber-700",
    bg: "bg-amber-50",
    border: "border-amber-400",
    desc: "Bid viable — address flagged conditions first",
    ring: "#f59e0b",
  },
  NO_GO: {
    label: "NO GO",
    color: "text-red-700",
    bg: "bg-red-50",
    border: "border-red-400",
    desc: "Do not submit — critical gaps detected",
    ring: "#ef4444",
  },
};

// ─── Mandatory Level ──────────────────────────────────────────────────────────
export const MANDATORY_CONFIG: Record<MandatoryLevel, { label: string; classes: string }> = {
  MANDATORY: { label: "Mandatory", classes: "text-red-600 font-semibold" },
  PREFERRED: { label: "Preferred", classes: "text-blue-600" },
  INFORMATIONAL: { label: "Info", classes: "text-slate-500" },
  UNKNOWN: { label: "Unknown", classes: "text-slate-400" },
};

// ─── Category ─────────────────────────────────────────────────────────────────
export const CATEGORY_LABELS: Record<Category, string> = {
  LEGAL: "Legal",
  FINANCIAL: "Financial",
  TECHNICAL: "Technical",
  EXPERIENCE: "Experience",
  CERTIFICATION: "Certification",
  PERSONNEL: "Personnel",
  DOCUMENTATION: "Documentation",
  DELIVERY: "Delivery",
  COMMERCIAL: "Commercial",
  CONTRACTUAL: "Contractual",
};

// ─── Severity order for sort ──────────────────────────────────────────────────
export const SEVERITY_ORDER: Record<Severity, number> = {
  CRITICAL: 0,
  HIGH: 1,
  MEDIUM: 2,
  LOW: 3,
};

export const STATUS_ORDER: Record<Status, number> = {
  NOT_MET: 0,
  UNKNOWN: 1,
  PARTIALLY_MET: 2,
  MET: 3,
};
