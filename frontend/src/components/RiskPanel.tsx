"use client";

import { AlertTriangle, ChevronDown, ChevronUp, Lightbulb } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SEVERITY_CONFIG, cn } from "@/lib/utils";
import type { RiskItem, RequirementWithResult, Severity } from "@/types";
import { useState } from "react";

const SEVERITY_VARIANT: Record<Severity, "critical" | "high" | "medium" | "low"> = {
  CRITICAL: "critical",
  HIGH: "high",
  MEDIUM: "medium",
  LOW: "low",
};

interface RiskPanelProps {
  risks: RiskItem[];
  requirements: RequirementWithResult[];
}

export function RiskPanel({ risks, requirements }: RiskPanelProps) {
  const [expanded, setExpanded] = useState<string | null>(null);

  const filtered = risks
    .filter((r) => r.severity === "CRITICAL" || r.severity === "HIGH")
    .sort((a, b) => {
      const order = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };
      return order[a.severity] - order[b.severity];
    });

  const reqMap = Object.fromEntries(requirements.map((r) => [r.requirement_id, r]));

  if (filtered.length === 0) {
    return (
      <Card className="border-emerald-200 bg-emerald-50">
        <CardContent className="flex items-center gap-3 py-4">
          <div className="h-8 w-8 rounded-full bg-emerald-100 flex items-center justify-center">
            <span className="text-emerald-600 text-lg">✓</span>
          </div>
          <div>
            <p className="font-medium text-emerald-800 text-sm">No critical or high risks detected</p>
            <p className="text-xs text-emerald-600">All mandatory requirements either met or low-risk</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-red-100">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <AlertTriangle className="h-4 w-4 text-red-500" />
          Disqualification Risks
          <div className="ml-auto flex gap-1.5">
            {["CRITICAL", "HIGH"].map((sev) => {
              const count = filtered.filter((r) => r.severity === sev).length;
              if (count === 0) return null;
              return (
                <Badge key={sev} variant={SEVERITY_VARIANT[sev as Severity]}>
                  {count} {sev.toLowerCase()}
                </Badge>
              );
            })}
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 pt-0">
        {filtered.map((risk) => {
          const sev = SEVERITY_CONFIG[risk.severity];
          const req = reqMap[risk.requirement_id];
          const isExpanded = expanded === risk.requirement_id;

          return (
            <div
              key={risk.requirement_id}
              className={cn(
                "rounded-xl border p-4 space-y-3 transition-all",
                sev.bg,
                sev.border,
                risk.severity === "CRITICAL" && "ring-1 ring-red-300"
              )}
            >
              {/* Header row */}
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-2 flex-1">
                  <Badge variant={SEVERITY_VARIANT[risk.severity]} className="shrink-0 mt-0.5">
                    {risk.severity}
                  </Badge>
                  <div>
                    <code className="text-xs text-slate-500 font-mono">{risk.requirement_id}</code>
                    <p className="text-xs text-slate-500 mt-0.5 font-mono bg-white/50 rounded px-1.5 py-0.5 border border-current/10 inline-block ml-1">
                      {risk.reason_code.replace(/_/g, " ")}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setExpanded(isExpanded ? null : risk.requirement_id)}
                  className="text-slate-400 hover:text-slate-600 shrink-0"
                >
                  {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </button>
              </div>

              {/* Requirement text */}
              {req && (
                <p className={cn("text-sm font-medium", sev.color)}>{req.text}</p>
              )}

              {/* Explanation — always visible */}
              <p className="text-sm text-slate-700">{risk.explanation}</p>

              {/* Recommended action — expanded */}
              {isExpanded && (
                <div className="bg-white/60 rounded-lg p-3 border border-current/10 flex gap-2 animate-fade-in">
                  <Lightbulb className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-1">Recommended Action</p>
                    <p className="text-sm text-slate-700">{risk.recommended_action}</p>
                  </div>
                </div>
              )}

              {!isExpanded && (
                <button
                  onClick={() => setExpanded(risk.requirement_id)}
                  className={cn("text-xs font-medium underline underline-offset-2", sev.color, "opacity-70 hover:opacity-100")}
                >
                  View recommended action →
                </button>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
