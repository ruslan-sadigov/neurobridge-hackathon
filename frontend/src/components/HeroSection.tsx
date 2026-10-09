"use client";

import Image from "next/image";
import { FileText, ArrowLeft, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScoreRing } from "@/components/ScoreRing";
import { RECOMMENDATION_CONFIG, STATUS_CONFIG, cn } from "@/lib/utils";
import type { AnalysisSummary, ScoreSnapshot } from "@/types";

interface HeroSectionProps {
  summary: AnalysisSummary;
  score: ScoreSnapshot;
  onReset: () => void;
}

export function HeroSection({ summary, score, onReset }: HeroSectionProps) {
  const rec = score.recommendation;
  const cfg = RECOMMENDATION_CONFIG[rec];

  return (
    <div className="bg-white border-b border-slate-200">
      {/* Top bar on a crisp light background so navy blue text and logo are prominently visible */}
      <header className="bg-slate-50/90 backdrop-blur border-b border-slate-200 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-6 py-2.5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="relative h-9 w-32 sm:h-10 sm:w-36 flex items-center">
              <Image
                src="/logo.png"
                alt="BidBridge Logo"
                fill
                priority
                className="object-contain object-left"
              />
            </div>
            <div className="hidden sm:block h-4 w-[1px] bg-slate-300" />
            <span className="hidden sm:inline-block text-xs font-medium text-slate-500 uppercase tracking-wider">
              Tender Intelligence
            </span>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="border-slate-300 text-navy-900 hover:bg-slate-100 hover:text-brand-600 font-medium"
            onClick={onReset}
          >
            <ArrowLeft className="h-3.5 w-3.5 mr-1.5" />
            New Analysis
          </Button>
        </div>
      </header>

      {/* Hero content */}
      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex flex-col lg:flex-row lg:items-start gap-8">
          {/* Left: tender info */}
          <div className="flex-1 space-y-5">
            <div>
              <div className="flex items-center gap-2 text-xs text-slate-400 font-medium uppercase tracking-wide mb-1">
                <FileText className="h-3.5 w-3.5 text-brand-500" />
                Tender Analysis
                <span className="text-slate-300">•</span>
                <code className="font-mono text-navy-900 bg-slate-100 px-1.5 py-0.5 rounded">{summary.analysis_id.slice(0, 8)}…</code>
              </div>
              <h1 className="text-2xl font-bold text-navy-900 tracking-tight">
                {summary.documents[0]?.filename.replace(/\.pdf$/i, "").replace(/_/g, " ") || "Tender Package"}
              </h1>
              <div className="flex items-center gap-3 mt-2 text-sm text-slate-500">
                <span>{summary.documents.length} document{summary.documents.length !== 1 ? "s" : ""}</span>
                <span>•</span>
                <span>{summary.documents.reduce((s, d) => s + d.pages, 0)} pages</span>
                <span>•</span>
                <span>{summary.counts.total} requirements</span>
              </div>
            </div>

            {/* Document list */}
            <div className="flex flex-wrap gap-2">
              {summary.documents.map((doc) => (
                <span key={doc.document_id} className="inline-flex items-center gap-1.5 bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1 text-xs text-slate-700 shadow-sm">
                  <FileText className="h-3 w-3 text-brand-500" />
                  {doc.filename}
                  <span className="text-slate-400">({doc.pages}p)</span>
                </span>
              ))}
            </div>

            {/* Requirement count badges */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {(["MET", "PARTIALLY_MET", "NOT_MET", "UNKNOWN"] as const).map((s) => {
                const cfg = STATUS_CONFIG[s];
                const count = summary.counts[s];
                return (
                  <div key={s} className={cn("rounded-xl border p-3 text-center", cfg.bg, cfg.border)}>
                    <div className={cn("text-2xl font-bold", cfg.color)}>{count}</div>
                    <div className={cn("text-xs mt-0.5 font-medium", cfg.color)}>{cfg.label}</div>
                  </div>
                );
              })}
            </div>

            {/* Mandatory breakdown */}
            <div className="flex items-center gap-4 text-sm">
              <span className="text-slate-600">
                <span className="font-semibold text-navy-900">{summary.counts.mandatory}</span> mandatory requirements
              </span>
              <span className="text-slate-300">|</span>
              <span className="text-slate-600">
                <span className="font-semibold text-navy-900">{(score.overall_coverage * 100).toFixed(0)}%</span> evidence coverage
              </span>
            </div>
          </div>

          {/* Right: score + recommendation */}
          <div className="flex flex-col items-center gap-4 lg:items-end">
            <div className={cn("rounded-2xl border-2 p-6 text-center space-y-3 shadow-sm", cfg.bg, cfg.border)}>
              <ScoreRing score={score.final_score} recommendation={rec} size={140} />
              <div>
                <div className={cn("text-xl font-extrabold tracking-tight", cfg.color)}>
                  {cfg.label}
                </div>
                <div className={cn("text-xs mt-0.5 max-w-[180px]", cfg.color, "opacity-80")}>
                  {cfg.desc}
                </div>
              </div>
            </div>

            {/* Dimension breakdown */}
            <div className="w-full lg:w-64 space-y-2">
              <div className="flex items-center gap-1.5 text-xs text-slate-500 font-medium uppercase tracking-wide mb-2">
                <TrendingUp className="h-3 w-3 text-brand-500" />
                Score by Dimension
              </div>
              {score.dimensions.filter((d) => d.score !== null).map((dim) => {
                // API sends dimension scores as 0-1 fractions; coverage = share of requirements that are not UNKNOWN
                const pct = (dim.score ?? 0) * 100;
                return (
                <div key={dim.name} className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-600">{dim.name}</span>
                    <span className="font-medium text-navy-900">
                      {Math.round(pct)}
                      {dim.coverage !== null && (
                        <span className="ml-1 font-normal text-slate-400" title="Share of requirements verified from supplier evidence">
                          ({Math.round(dim.coverage * 100)}% verified)
                        </span>
                      )}
                    </span>
                  </div>
                  <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{
                        width: `${pct}%`,
                        backgroundColor: pct >= 70 ? "#10b981" : pct >= 40 ? "#00B4D8" : "#ef4444",
                      }}
                    />
                  </div>
                </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
