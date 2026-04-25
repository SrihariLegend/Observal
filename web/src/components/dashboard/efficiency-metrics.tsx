"use client";

import { useRef, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import gsap from "gsap";
import type { SessionEfficiencyData } from "@/hooks/use-api";

type EfficiencyData = SessionEfficiencyData;

function interpretStyle(label: string): { color: string; bg: string; border: string } {
  if (label.startsWith("Excellent")) return { color: "#10b981", bg: "rgba(16,185,129,0.08)", border: "rgba(16,185,129,0.2)" };
  if (label.startsWith("Good"))      return { color: "#3b82f6", bg: "rgba(59,130,246,0.08)", border: "rgba(59,130,246,0.2)" };
  if (label.startsWith("Fair"))      return { color: "#f59e0b", bg: "rgba(245,158,11,0.08)", border: "rgba(245,158,11,0.2)" };
  if (label.startsWith("Minor"))     return { color: "#f59e0b", bg: "rgba(245,158,11,0.08)", border: "rgba(245,158,11,0.2)" };
  if (label.startsWith("None") || label === "N/A") return { color: "#64748b", bg: "rgba(100,116,139,0.06)", border: "rgba(100,116,139,0.15)" };
  return { color: "#ef4444", bg: "rgba(239,68,68,0.08)", border: "rgba(239,68,68,0.2)" };
}

const METRIC_LABELS: Record<string, { label: string; description: string }> = {
  path_efficiency_ratio:      { label: "Path Efficiency",      description: "Effective actions / total actions" },
  token_waste_rate:           { label: "Token Waste",           description: "Tokens spent on reverted work" },
  first_pass_success_rate:    { label: "First Pass Success",    description: "Writes that stuck without revert" },
  file_churn_rate:            { label: "File Churn",            description: "Files rewritten multiple times" },
  repetition_cycles:          { label: "Repetition Cycles",     description: "Detected edit-error-fix loops" },
  duplicate_tool_call_count:  { label: "Duplicate Calls",       description: "Identical tool calls repeated" },
};

export function EfficiencyMetrics({ data }: { data: EfficiencyData }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const animatedRef = useRef(false);

  useEffect(() => {
    if (animatedRef.current || !containerRef.current) return;
    animatedRef.current = true;

    const rows = containerRef.current.querySelectorAll("[data-metric-row]");
    const warnings = containerRef.current.querySelectorAll("[data-warning]");

    gsap.set(rows, { opacity: 0, x: -12 });
    gsap.set(warnings, { opacity: 0, y: 8 });

    const tl = gsap.timeline({ defaults: { ease: "expo.out" } });
    tl.to(rows, { opacity: 1, x: 0, duration: 0.5, stagger: 0.04 }, 0.1);
    tl.to(warnings, { opacity: 1, y: 0, duration: 0.4, stagger: 0.06 }, "-=0.2");
  }, []);

  const entries = Object.entries(data.interpretation);

  return (
    <Card className="overflow-hidden border-0 shadow-none bg-transparent">
      <CardHeader className="pb-2 px-0">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-semibold tracking-tight flex items-center gap-2">
            <span
              className="w-5 h-5 rounded flex items-center justify-center text-[10px] font-black"
              style={{ background: "rgba(59,130,246,0.1)", color: "#3b82f6", border: "1px solid rgba(59,130,246,0.2)" }}
            >
              E
            </span>
            Process Efficiency
          </CardTitle>
          <span
            className="text-[10px] font-mono px-2 py-0.5 rounded"
            style={{ color: "rgba(148,163,184,0.5)", background: "rgba(148,163,184,0.06)" }}
          >
            v{data.scorer_version}
          </span>
        </div>
      </CardHeader>

      <CardContent className="px-0 pt-0" ref={containerRef}>
        <div
          className="rounded-xl overflow-hidden"
          style={{
            background: "linear-gradient(145deg, rgba(15,23,42,0.4) 0%, rgba(15,23,42,0.2) 100%)",
            border: "1px solid rgba(100,116,139,0.1)",
          }}
        >
          {/* Metrics grid */}
          <div className="px-4 py-4 space-y-1">
            {entries.map(([key, label]) => {
              const meta = METRIC_LABELS[key] || { label: key, description: "" };
              const rawValue = data.efficiency_metrics[key];
              const displayValue = rawValue === null || rawValue === undefined
                ? "—"
                : typeof rawValue === "number" && !Number.isInteger(rawValue)
                  ? rawValue.toFixed(2)
                  : String(rawValue);
              const style = interpretStyle(label);

              return (
                <div
                  key={key}
                  data-metric-row
                  className="flex items-center justify-between py-2 px-3 rounded-lg group"
                  style={{ background: "rgba(100,116,139,0.03)" }}
                >
                  <div className="flex flex-col min-w-0 mr-3">
                    <span className="text-[12px] font-medium" style={{ color: "rgba(226,232,240,0.8)" }}>
                      {meta.label}
                    </span>
                    <span className="text-[10px]" style={{ color: "rgba(148,163,184,0.4)" }}>
                      {meta.description}
                    </span>
                  </div>
                  <div className="flex items-center gap-2.5 shrink-0">
                    <span
                      className="text-xs font-mono font-bold tabular-nums"
                      style={{ color: "rgba(226,232,240,0.7)" }}
                    >
                      {displayValue}
                    </span>
                    <span
                      className="text-[10px] font-semibold px-2 py-0.5 rounded-md whitespace-nowrap"
                      style={{ color: style.color, background: style.bg, border: `1px solid ${style.border}` }}
                    >
                      {label.split("(")[0].trim()}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Warnings */}
          {data.warnings.length > 0 && (
            <div className="px-4 pb-4 space-y-1.5">
              <div className="h-px" style={{ background: "rgba(245,158,11,0.1)" }} />
              {data.warnings.map((w, i) => (
                <div
                  key={i}
                  data-warning
                  className="flex items-start gap-2.5 px-3 py-2 rounded-lg text-[11px]"
                  style={{ background: "rgba(245,158,11,0.04)", border: "1px solid rgba(245,158,11,0.1)" }}
                >
                  <span
                    className="shrink-0 w-4 h-4 rounded flex items-center justify-center text-[9px] font-black mt-0.5"
                    style={{ background: "rgba(245,158,11,0.12)", color: "#f59e0b" }}
                  >
                    !
                  </span>
                  <span style={{ color: "rgba(251,191,36,0.8)" }}>{w}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
