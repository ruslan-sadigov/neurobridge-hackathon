"use client";

import { useState } from "react";
import { FileText, Link, Shield, ChevronRight } from "lucide-react";
import { SourcePageViewer } from "@/components/SourcePageViewer";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import {
  STATUS_CONFIG,
  SEVERITY_CONFIG,
  MANDATORY_CONFIG,
  CATEGORY_LABELS,
  RECOMMENDATION_CONFIG,
  cn,
} from "@/lib/utils";
import type { RequirementWithResult, Severity } from "@/types";

const SEVERITY_VARIANT_MAP: Record<Severity, "critical" | "high" | "medium" | "low"> = {
  CRITICAL: "critical",
  HIGH: "high",
  MEDIUM: "medium",
  LOW: "low",
};

interface DrillDownModalProps {
  requirement: RequirementWithResult | null;
  open: boolean;
  onClose: () => void;
}

export function DrillDownModal({ requirement, open, onClose }: DrillDownModalProps) {
  const [openPage, setOpenPage] = useState<string | null>(null);
  if (!requirement) return null;

  const { result } = requirement;
  const statusCfg = STATUS_CONFIG[result.status];
  const mandatoryCfg = MANDATORY_CONFIG[requirement.mandatory_level];

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center gap-2 flex-wrap">
            <code className="text-xs text-slate-400 font-mono">{requirement.requirement_id}</code>
            <Badge
              className={cn("text-xs", statusCfg.color, statusCfg.bg, "border", statusCfg.border)}
            >
              <span className={cn("w-1.5 h-1.5 rounded-full mr-1", statusCfg.dot)} />
              {statusCfg.label}
            </Badge>
            {result.risk_severity && (
              <Badge variant={SEVERITY_VARIANT_MAP[result.risk_severity]}>
                {result.risk_severity}
              </Badge>
            )}
          </div>
          <DialogTitle className="text-base leading-snug mt-2">{requirement.text}</DialogTitle>
          <DialogDescription className="flex items-center gap-3 flex-wrap">
            <span className="flex items-center gap-1">
              <Shield className="h-3 w-3" />
              <span className={mandatoryCfg.classes + " text-xs"}>{mandatoryCfg.label}</span>
            </span>
            <span className="text-slate-300">•</span>
            <span>{CATEGORY_LABELS[requirement.category]}</span>
            <span className="text-slate-300">•</span>
            <span>{(requirement.extraction_confidence * 100).toFixed(0)}% confidence</span>
          </DialogDescription>
        </DialogHeader>

        <div className="px-6 pb-6 space-y-5">

          {/* Compliance Rationale */}
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-2">
              {result.method === "DETERMINISTIC_RULE" ? "Rationale (verified by rule engine)" : "Rationale (AI-assisted)"}
            </h3>
            <div className={cn("rounded-lg border p-4 text-sm", statusCfg.bg, statusCfg.border)}>
              <p className={cn("text-sm leading-relaxed", statusCfg.color)}>{result.rationale}</p>
              {result.reason_code && (
                <p className="mt-2 text-xs font-mono text-slate-500">
                  Reason: {result.reason_code.replace(/_/g, " ")}
                </p>
              )}
              <p className="mt-2 text-xs text-slate-400">
                Method: {result.method.replace(/_/g, " ")} · Confidence: {(result.confidence * 100).toFixed(0)}%
              </p>
            </div>
          </section>

          {/* Source Documents */}
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-2 flex items-center gap-1.5">
              <FileText className="h-3 w-3" />
              Source Evidence in Tender
            </h3>
            <div className="space-y-2">
              {requirement.sources.map((src, i) => (
                <div key={i} className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-1.5">
                  <div className="flex items-center gap-2 text-xs font-medium text-slate-600">
                    <span className="font-mono bg-white border border-slate-200 rounded px-1.5 py-0.5">
                      Page {src.page}
                    </span>
                    {src.section && (
                      <span className="text-slate-400 truncate">{src.section}</span>
                    )}
                    <code className="ml-auto text-slate-300 truncate text-xs">{src.document_id}</code>
                  </div>
                  <blockquote className="text-sm text-slate-700 italic border-l-2 border-brand-300 pl-3">
                    "{src.excerpt}"
                  </blockquote>
                  <button
                    type="button"
                    className="text-xs font-medium text-brand-600 hover:underline"
                    onClick={() => {
                      const k = `${requirement.requirement_id}-${i}`;
                      setOpenPage(openPage === k ? null : k);
                    }}
                  >
                    {openPage === `${requirement.requirement_id}-${i}` ? "Hide page" : "View full page"}
                  </button>
                  {openPage === `${requirement.requirement_id}-${i}` && (
                    <SourcePageViewer documentId={src.document_id} page={src.page} excerpt={src.excerpt} />
                  )}
                </div>
              ))}
            </div>
          </section>

          {/* Supplier Evidence */}
          {requirement.evidence_candidates.length > 0 && (
            <section>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-2 flex items-center gap-1.5">
                <Link className="h-3 w-3" />
                {result.supporting_evidence_ids.length > 0
                  ? "Supplier Evidence"
                  : "Closest supplier evidence (does not satisfy this requirement)"}
              </h3>
              <div className="space-y-2">
                {requirement.evidence_candidates.map(({ evidence, score }, i) => (
                  <div key={i} className="rounded-lg border border-slate-200 bg-white p-3 space-y-1">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-slate-700">{evidence.label}</span>
                          <Badge variant="secondary" className="text-xs">{evidence.type}</Badge>
                          {result.supporting_evidence_ids.includes(evidence.evidence_id) && (
                            <Badge className="text-xs bg-emerald-50 text-emerald-700 border border-emerald-200">Supports finding</Badge>
                          )}
                        </div>
                        <code className="text-xs text-slate-400 font-mono">{evidence.evidence_id}</code>
                      </div>
                      <div className="text-right shrink-0">
                        <div className="text-xs font-bold text-brand-600">{(score * 100).toFixed(0)}%</div>
                        <div className="text-xs text-slate-400">match</div>
                      </div>
                    </div>
                    <p className="text-sm text-slate-600">{evidence.text || String(evidence.value)}</p>
                    {(evidence.issued_date || evidence.expiry_date) && (
                      <p className="text-xs text-slate-400">
                        {evidence.issued_date && <>Issued: {evidence.issued_date}</>}
                        {evidence.issued_date && evidence.expiry_date && "  ·  "}
                        {evidence.expiry_date && <>Expires: {evidence.expiry_date}</>}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          {result.supporting_evidence_ids.length === 0 && requirement.evidence_candidates.length === 0 && (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-center text-sm text-slate-400">
              No supplier evidence found for this requirement
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
