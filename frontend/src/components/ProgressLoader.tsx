"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import { CheckCircle2, Circle, Loader2 } from "lucide-react";
import { useAnalysisSummary } from "@/hooks/useAnalysis";

const STAGES = [
  { key: "parsing",    label: "Parsing documents",          desc: "Extracting text from PDF pages",              durationMs: 2000 },
  { key: "extracting", label: "Extracting requirements",    desc: "Identifying tender criteria with AI",          durationMs: 6000 },
  { key: "matching",   label: "Matching evidence",          desc: "Mapping supplier profile to requirements",    durationMs: 3000 },
  { key: "scoring",    label: "Computing compliance score", desc: "Calculating weighted bid recommendation",     durationMs: 1000 },
] as const;

interface ProgressLoaderProps {
  analysisId: string;
  onComplete: () => void;
  onError: (msg: string) => void;
}

export function ProgressLoader({ analysisId, onComplete, onError }: ProgressLoaderProps) {
  const { data: analysis } = useAnalysisSummary(analysisId);
  const [stageIndex, setStageIndex] = useState(0);
  const [elapsed, setElapsed] = useState(0);

  // Advance visual stages on timer
  useEffect(() => {
    if (stageIndex >= STAGES.length - 1) return;
    const target = STAGES[stageIndex].durationMs;
    const timer = setTimeout(() => setStageIndex((s) => s + 1), target);
    return () => clearTimeout(timer);
  }, [stageIndex]);

  // Track elapsed
  useEffect(() => {
    const t = setInterval(() => setElapsed((e) => e + 100), 100);
    return () => clearInterval(t);
  }, []);

  // React to real backend status
  useEffect(() => {
    if (!analysis) return;
    if (analysis.status === "COMPLETE") {
      setStageIndex(STAGES.length);
      setTimeout(onComplete, 600);
    } else if (analysis.status === "FAILED") {
      onError(analysis.error || "Analysis failed. Please try again.");
    }
  }, [analysis, onComplete, onError]);

  const totalDuration = STAGES.reduce((s, st) => s + st.durationMs, 0);
  const visualProgress = Math.min(
    (STAGES.slice(0, stageIndex).reduce((s, st) => s + st.durationMs, 0) / totalDuration) * 100,
    95
  );
  const realProgress = analysis?.status === "COMPLETE" ? 100 : visualProgress;

  return (
    <div className="min-h-screen bg-slate-100/60 flex items-center justify-center p-6">
      <div className="w-full max-w-lg animate-fade-in">
        {/* Card */}
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-md p-8 space-y-8">
          <div className="text-center">
            <div className="flex justify-center mb-4">
              <div className="relative h-10 w-36">
                <Image
                  src="/logo.png"
                  alt="BidBridge Logo"
                  fill
                  priority
                  className="object-contain"
                />
              </div>
            </div>
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-brand-50 mb-3">
              <Loader2 className="h-6 w-6 text-brand-500 animate-spin" />
            </div>
            <h2 className="text-xl font-bold text-navy-900">Analyzing Tender</h2>
            <p className="text-slate-500 text-sm mt-1">AI pipeline is parsing, matching, and scoring</p>
          </div>

          {/* Progress bar */}
          <div className="space-y-2">
            <div className="flex justify-between text-xs text-slate-500">
              <span>Overall Progress</span>
              <span className="font-semibold text-navy-900">{Math.round(realProgress)}%</span>
            </div>
            <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-brand-500 to-navy-900 rounded-full transition-all duration-700"
                style={{ width: `${realProgress}%` }}
              />
            </div>
          </div>

          {/* Stages */}
          <div className="space-y-4">
            {STAGES.map((stage, i) => {
              const isDone = stageIndex > i;
              const isActive = stageIndex === i;
              return (
                <div key={stage.key} className="flex items-start gap-3">
                  <div className="mt-0.5 shrink-0">
                    {isDone ? (
                      <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                    ) : isActive ? (
                      <Loader2 className="h-5 w-5 text-brand-500 animate-spin" />
                    ) : (
                      <Circle className="h-5 w-5 text-slate-200" />
                    )}
                  </div>
                  <div>
                    <p className={`text-sm font-medium ${isDone ? "text-slate-400 line-through" : isActive ? "text-navy-900" : "text-slate-300"}`}>
                      {stage.label}
                    </p>
                    {isActive && (
                      <p className="text-xs text-brand-600 mt-0.5 animate-fade-in font-normal">{stage.desc}</p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-100">
            <span>Analysis ID: <code className="font-mono text-slate-600">{analysisId.slice(0, 8)}…</code></span>
            <span>{(elapsed / 1000).toFixed(1)}s elapsed</span>
          </div>
        </div>
      </div>
    </div>
  );
}
