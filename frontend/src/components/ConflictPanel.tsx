"use client";

import { useState } from "react";
import { FileWarning, GitCompareArrows } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SourcePageViewer } from "@/components/SourcePageViewer";
import { cn } from "@/lib/utils";
import type { Contradiction, DocumentInfo, Severity } from "@/types";

const SEVERITY_VARIANT: Record<Severity, "critical" | "high" | "medium" | "low"> = {
  CRITICAL: "critical",
  HIGH: "high",
  MEDIUM: "medium",
  LOW: "low",
};

interface ConflictPanelProps {
  contradictions: Contradiction[];
  documents: DocumentInfo[];
}

export function ConflictPanel({ contradictions, documents }: ConflictPanelProps) {
  const [openPage, setOpenPage] = useState<string | null>(null);
  const fileName = (id: string) => documents.find((d) => d.document_id === id)?.filename ?? id;

  if (contradictions.length === 0) {
    return (
      <Card className="border-emerald-200 bg-emerald-50">
        <CardContent className="flex items-center gap-3 py-4">
          <div className="h-8 w-8 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600 text-lg">✓</div>
          <div>
            <p className="font-medium text-emerald-800 text-sm">No conflicting statements found</p>
            <p className="text-xs text-emerald-600">
              Different numbers or dates for the same item across the tender documents would appear here.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-500">
        These statements may not both be true. BidBridge does not decide which one applies. Ask the buyer to clarify
        before submitting. A later document may amend an earlier one, so check each source.
      </p>
      {contradictions.map((c) => (
        <Card key={c.contradiction_id} className="border-amber-200">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <GitCompareArrows className="h-4 w-4 text-amber-500" />
              <span className="font-mono text-xs text-slate-400">{c.contradiction_id}</span>
              <Badge variant={SEVERITY_VARIANT[c.severity]}>{c.severity}</Badge>
              <span className="text-sm font-normal text-slate-700">{c.explanation}</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-2">
            {c.statements.map((s, i) => {
              const key = `${c.contradiction_id}-${i}`;
              return (
                <div key={key} className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-1.5">
                  <div className="flex items-center gap-2 text-xs font-medium text-slate-600">
                    <FileWarning className="h-3.5 w-3.5 text-amber-500 shrink-0" />
                    <span className="truncate">{fileName(s.document_id)}</span>
                    <span className="ml-auto font-mono bg-white border border-slate-200 rounded px-1.5 py-0.5 shrink-0">
                      Page {s.page}
                    </span>
                  </div>
                  <blockquote className={cn("text-sm text-slate-700 italic border-l-2 border-amber-300 pl-3")}>
                    &quot;{s.excerpt}&quot;
                  </blockquote>
                  <button
                    type="button"
                    className="text-xs font-medium text-brand-600 hover:underline"
                    onClick={() => setOpenPage(openPage === key ? null : key)}
                  >
                    {openPage === key ? "Hide page" : "View full page"}
                  </button>
                  {openPage === key && (
                    <SourcePageViewer documentId={s.document_id} page={s.page} excerpt={s.excerpt} />
                  )}
                </div>
              );
            })}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
