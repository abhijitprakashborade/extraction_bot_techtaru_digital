import { motion } from "framer-motion";
import { CheckCircle2, CircleDashed, Loader2, XCircle } from "lucide-react";
import { cn } from "@/utils/common";
import type { PipelineStage } from "@/types";

export function Pipeline({ stages }: { stages: PipelineStage[] }) {
  return (
    <div className="flex flex-wrap items-center gap-x-1 gap-y-2">
      {stages.map((s, i) => {
        const Icon =
          s.status === "done" ? CheckCircle2 :
          s.status === "running" ? Loader2 :
          s.status === "error" ? XCircle : CircleDashed;
        return (
          <div key={s.id} className="flex items-center gap-1">
            <div className={cn(
              "flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-all duration-300",
              s.status === "idle"    && "border-white/5 bg-white/[0.03] text-slate-500",
              s.status === "running" && "border-indigo-500/40 bg-indigo-500/10 text-indigo-300",
              s.status === "done"    && "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
              s.status === "error"   && "border-rose-500/30 bg-rose-500/10 text-rose-400",
            )}>
              <Icon size={11} className={s.status === "running" ? "animate-spin" : ""} />
              {s.label}
            </div>
            {i < stages.length - 1 && (
              <div className={cn("h-px w-3 transition-colors", s.status === "done" ? "bg-emerald-500/40" : "bg-white/10")} />
            )}
          </div>
        );
      })}
    </div>
  );
}

/** Format any extracted value as a short human-readable preview line. */
function previewOf(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (Array.isArray(v) && v.length > 0 && v.every((x) => x === null || typeof x !== "object")) {
    return v.filter(Boolean).slice(0, 4).map(String).join(", ") + (v.length > 4 ? ` +${v.length - 4} more` : "");
  }
  if (Array.isArray(v)) return `${v.length} record${v.length === 1 ? "" : "s"}`;
  if (typeof v === "object") {
    const keys = Object.keys(v as Record<string, unknown>).filter(
      (k) => (v as Record<string, unknown>)[k] !== null
    );
    return `${keys.length} field${keys.length === 1 ? "" : "s"}`;
  }
  const s = String(v);
  return s.length > 56 ? s.slice(0, 56) + "…" : s;
}

/** Confidence bars paired with the live extracted value for each field.
 *  Only fields that actually contain data (score > 0) get a bar —
 *  fields the model found nothing for are summarised separately. */
export function ConfidenceBars({
  scores,
  values,
}: {
  scores: Record<string, number>;
  values?: Record<string, unknown>;
}) {
  const entries = Object.entries(scores)
    .filter(([k, v]) => typeof v === "number" && v > 0.001)
    .sort(([, a], [, b]) => b - a);
  const missing = Object.entries(scores).filter(([, v]) => !v || v <= 0.001);
  if (!entries.length) {
    return (
      <p className="text-[12px] text-slate-500">
        No fields were found in this document — everything came back as null.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
        {entries.map(([label, v], i) => {
          const val = values?.[label];
          return (
            <motion.div
              key={label}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.04, duration: 0.3 }}
            >
              <div className="mb-1 flex items-baseline justify-between gap-2 text-[11px]">
                <span className="truncate font-medium text-slate-300" title={label}>{label}</span>
                <span className={
                  v >= 0.85 ? "font-mono font-semibold text-emerald-400" :
                  v >= 0.6  ? "font-mono font-semibold text-amber-400" :
                              "font-mono font-semibold text-rose-400"
                }>{(v * 100).toFixed(0)}%</span>
              </div>
              {/* live extracted value for this field */}
              {val !== undefined && (
                <div className="mb-1.5 truncate pl-0.5 text-[11px] leading-snug text-slate-500" title={previewOf(val)}>
                  {previewOf(val)}
                </div>
              )}
              <div className="h-1.5 overflow-hidden rounded-full bg-white/5">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${v * 100}%` }}
                  transition={{ duration: 0.6, ease: "easeOut" }}
                  className={cn(
                    "h-full rounded-full",
                    v >= 0.85 ? "bg-gradient-to-r from-emerald-500 to-emerald-400" :
                    v >= 0.6  ? "bg-gradient-to-r from-amber-500 to-amber-400" :
                                "bg-gradient-to-r from-rose-500 to-rose-400",
                  )}
                />
              </div>
            </motion.div>
          );
        })}
      </div>
      {missing.length > 0 && (
        <p className="text-[11px] text-slate-600">
          {missing.length} field{missing.length === 1 ? "" : "s"} returned null — not present in the document (shown nowhere by design, never guessed).
        </p>
      )}
    </div>
  );
}
