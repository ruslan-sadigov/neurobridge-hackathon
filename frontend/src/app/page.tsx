"use client";

import { useState, useCallback, useEffect } from "react";
import { SetupForm } from "@/components/SetupForm";
import { ProgressLoader } from "@/components/ProgressLoader";
import { HeroSection } from "@/components/HeroSection";
import { RiskPanel } from "@/components/RiskPanel";
import { ComplianceMatrix } from "@/components/ComplianceMatrix";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAnalysisSummary, useRequirements, useRisks, useScore } from "@/hooks/useAnalysis";
import { AlertTriangle, LayoutGrid, ShieldAlert } from "lucide-react";
import type { AppView } from "@/types";

function Dashboard({ analysisId, onReset }: { analysisId: string; onReset: () => void }) {
  const { data: summary } = useAnalysisSummary(analysisId);
  const { data: requirements = [], isLoading: reqLoading } = useRequirements(analysisId);
  const { data: risks = [], isLoading: riskLoading } = useRisks(analysisId);
  const { data: score } = useScore(analysisId);

  if (!summary || !score) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin h-8 w-8 border-4 border-brand-200 border-t-brand-600 rounded-full" />
      </div>
    );
  }

  const warnings = [
    ...(summary.summary?.warnings ?? []),
    ...((summary.summary?.parsing_coverage ?? 1) < 1
      ? [`Only ${Math.round((summary.summary?.parsing_coverage ?? 0) * 100)}% of tender pages had readable text.`]
      : []),
  ];

  const criticalHighCount = risks.filter(
    (r) => r.severity === "CRITICAL" || r.severity === "HIGH"
  ).length;

  return (
    <div className="min-h-screen bg-slate-50 animate-fade-in">
      <HeroSection summary={summary} score={score} onReset={onReset} />

      <main className="max-w-7xl mx-auto px-6 py-8">
        {warnings.length > 0 && (
          <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <p className="font-semibold flex items-center gap-1.5">
              <AlertTriangle className="h-4 w-4" /> Analysis completed with warnings. Results may be incomplete.
            </p>
            <ul className="mt-1.5 list-disc pl-5 text-xs space-y-0.5">
              {warnings.slice(0, 5).map((w, i) => (
                <li key={i}>{w}</li>
              ))}
              {warnings.length > 5 && <li>…and {warnings.length - 5} more</li>}
            </ul>
          </div>
        )}
        <Tabs defaultValue="risks">
          <TabsList className="mb-6">
            <TabsTrigger value="risks" className="gap-1.5">
              <ShieldAlert className="h-3.5 w-3.5" />
              Risk Panel
              {criticalHighCount > 0 && (
                <span className="inline-flex items-center justify-center h-4 w-4 rounded-full bg-red-100 text-red-700 text-[10px] font-bold">
                  {criticalHighCount}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="matrix" className="gap-1.5">
              <LayoutGrid className="h-3.5 w-3.5" />
              Compliance Matrix
              <span className="text-slate-400 text-xs">({requirements.length})</span>
            </TabsTrigger>
          </TabsList>

          <TabsContent value="risks">
            {riskLoading ? (
              <div className="flex items-center justify-center py-20">
                <div className="animate-spin h-6 w-6 border-4 border-brand-200 border-t-brand-600 rounded-full" />
              </div>
            ) : (
              <RiskPanel risks={risks} requirements={requirements} />
            )}
          </TabsContent>

          <TabsContent value="matrix">
            {reqLoading ? (
              <div className="flex items-center justify-center py-20">
                <div className="animate-spin h-6 w-6 border-4 border-brand-200 border-t-brand-600 rounded-full" />
              </div>
            ) : (
              <ComplianceMatrix requirements={requirements} />
            )}
          </TabsContent>
        </Tabs>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white mt-12">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between text-xs text-slate-400">
          <span>BidBridge · AI Tender Qualification · Hackathon Demo</span>
          <span className="flex items-center gap-1.5">
            <AlertTriangle className="h-3 w-3 text-amber-400" />
            AI-generated analysis — verify critical decisions with qualified professionals
          </span>
        </div>
      </footer>
    </div>
  );
}

export default function HomePage() {
  const [view, setView] = useState<AppView>("setup");
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string>("");

  // Deep link: /?analysis=<id> reopens an existing analysis (shareable result link).
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("analysis");
    if (id) {
      setAnalysisId(id);
      setView("loading");
    }
  }, []);

  const handleAnalysisStarted = useCallback((id: string) => {
    setAnalysisId(id);
    setView("loading");
    window.history.replaceState(null, "", `?analysis=${id}`);
  }, []);

  const handleComplete = useCallback(() => {
    setView("dashboard");
  }, []);

  const handleError = useCallback((msg: string) => {
    setLoadError(msg);
    setView("setup");
  }, []);

  const handleReset = useCallback(() => {
    window.history.replaceState(null, "", window.location.pathname);
    setView("setup");
    setAnalysisId(null);
    setLoadError("");
  }, []);

  if (view === "setup") {
    return (
      <>
        {loadError && (
          <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm shadow-lg">
            {loadError}
          </div>
        )}
        <SetupForm onAnalysisStarted={handleAnalysisStarted} />
      </>
    );
  }

  if (view === "loading" && analysisId) {
    return (
      <ProgressLoader
        analysisId={analysisId}
        onComplete={handleComplete}
        onError={handleError}
      />
    );
  }

  if (view === "dashboard" && analysisId) {
    return <Dashboard analysisId={analysisId} onReset={handleReset} />;
  }

  return null;
}
