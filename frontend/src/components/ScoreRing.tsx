"use client";

import { RECOMMENDATION_CONFIG } from "@/lib/utils";
import type { Recommendation } from "@/types";

interface ScoreRingProps {
  score: number;
  recommendation: Recommendation;
  size?: number;
}

export function ScoreRing({ score, recommendation, size = 140 }: ScoreRingProps) {
  const cfg = RECOMMENDATION_CONFIG[recommendation];
  const radius = (size - 20) / 2;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference - (score / 100) * circumference;
  const center = size / 2;

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        {/* Track */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="#f1f5f9"
          strokeWidth={14}
        />
        {/* Progress */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={cfg.ring}
          strokeWidth={14}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          style={{ transition: "stroke-dashoffset 1s ease-in-out" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center" style={{ transform: "none" }}>
        <span className="text-3xl font-bold text-slate-900">{Math.round(score)}</span>
        <span className="text-xs text-slate-400 font-medium">/ 100</span>
      </div>
    </div>
  );
}
