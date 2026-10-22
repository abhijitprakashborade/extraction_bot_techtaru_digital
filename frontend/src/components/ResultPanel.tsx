import { Fragment, useState } from "react";
import { motion } from "framer-motion";
import { JsonView, allExpanded, darkStyles } from "react-json-view-lite";
import "react-json-view-lite/dist/index.css";
import { AlertTriangle, Braces, ChevronDown, ChevronUp, Clock, Copy, Download, FileText, Layers, ShieldCheck } from "lucide-react";
import { cn, confColor, isDemoRun, prettyField } from "@/utils/common";
import { ConfidenceBars } from "@/components/Pipeline";
import { getExportUrl } from "@/utils/api";
import type { ExtractionResponse } from "@/types";

const CARD = "rounded-2xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-sm";

/* ─────────────────────────────────────────────────────────────────────── */
/* Pretty "Structured Data" renderer                                       */
/* ─────────────────────────────────────────────────────────────────────── */

function renderPrimitive(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (Array.isArray(v)) return "";
  if (typeof v === "object") return "";
  if (typeof v === "boolean") return v ? "Yes" : "No";
  return String(v);
}

function ValueChip({ v }: { v: unknown }) {
  return <span className="text-[13px] text-slate-200">{renderPrimitive(v)}</span>;
}

function DataTree({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="space-y-3">
      {Object.entries(data)
        .filter(([, v]) => !(v === null || v === undefined || (Array.isArray(v) && v.length === 0)))
        .map(([key, value]) => (
          <FieldBlock key={key} label={prettyField(key)} value={value} depth={0} />
        ))}
    </div>
  );
}

function FieldBlock({ label, value, depth }: { label: string; value: unknown; depth: number }) {
  const [open, setOpen] = useState(depth < 1);

  // primitive
  if (value === null || typeof value !== "object") {
    return (
      <div className="flex items-baseline justify-between gap-3 py-1.5">
        <span className="shrink-0 text-[11px] font-medium uppercase tracking-wider text-slate-500">{label}</span>
        <ValueChip v={value} />
      </div>
    );
  }

  // array of primitives
  if (Array.isArray(value) && value.every((v) => v === null || typeof v !== "object")) {
    if (!value.length) return null;
    return (
      <div className="py-1.5">
        <span className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-slate-500">{label}</span>
        <div className="flex flex-wrap gap-1.5">
          {value.filter(Boolean).map((v, i) => (
            <span key={i} className="rounded-md border border-indigo-500/20 bg-indigo-500/[0.08] px-2 py-0.5 text-[12px] text-indigo-200">
              {String(v)}
            </span>
          ))}
        </div>
      </div>
    );
  }

  // complex: array of objects / object
  const items = Array.isArray(value) ? value : [value];
  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02]">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-3 py-2.5 text-left"
      >
        <span className="flex items-center gap-2 text-[12px] font-semibold text-slate-200">
          {label}
          {Array.isArray(value) && (
            <span className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-[10px] text-slate-400">{value.length}</span>
          )}
        </span>
        {open ? <ChevronUp size={13} className="text-slate-500" /> : <ChevronDown size={13} className="text-slate-500" />}
      </button>
      {open && (
        <div className="divide-y divide-white/[0.04] border-t border-white/[0.04] px-3">
          {items.map((it, i) =>
            it && typeof it === "object" ? (
              <div key={i} className="py-2">
                {items.length > 1 && (
                  <span className="mb-1 block text-[10px] font-semibold uppercase tracking-widest text-indigo-400/70">
                    {label.replace(/s$/, "")} {i + 1}
                  </span>
                )}
                <div className="space-y-0.5">
                  {Object.entries(it as Record<string, unknown>)
                    .filter(([, v]) => !(v === null || v === undefined || (Array.isArray(v) && v.length === 0)))
                    .map(([k, v]) => (
                      <FieldBlock key={k} label={prettyField(k)} value={v} depth={depth + 1} />
                    ))}
                </div>
              </div>
            ) : null,
          )}
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────── */
/* Result panel                                                            */
/* ─────────────────────────────────────────────────────────────────────── */

export default function ResultPanel({ result }: { result: ExtractionResponse }) {
  const [view, setView] = useState<"structured" | "raw">("structured");
  const [warnOpen, setWarnOpen] = useState(false);
  const [notesOpen, setNotesOpen] = useState(false);
  const demo = isDemoRun(result.processing_notes);

  const copyJSON = () => {
    navigator.clipboard.writeText(JSON.stringify(result.data, null, 2));
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-4"
    >
      {/* Summary header */}
      <div className={cn(CARD, "p-4 md:p-5")}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-3 py-1 text-[12px] font-semibold text-indigo-300">
                <Layers size={12} />
                {result.document_type.replace("_", " ")}
                <span className="text-indigo-400/60">· {(result.document_type_confidence * 100).toFixed(0)}%</span>
              </span>
              {demo && (
                <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-[11px] font-medium text-amber-400">
                  <ShieldCheck size={11} /> Demo engine
                </span>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11.5px] text-slate-500">
              <span className={cn("flex items-center gap-1 font-mono font-semibold", confColor(result.overall_confidence))}>
                {(result.overall_confidence * 100).toFixed(0)}% confidence
              </span>
              <span className="flex items-center gap-1"><Clock size={11} />{result.processing_time_ms.toFixed(0)} ms</span>
              <span className="flex items-center gap-1"><FileText size={11} />{result.raw_text_length.toLocaleString()} chars</span>
              {result.file_name && <span className="max-w-[180px] truncate">{result.file_name}</span>}
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            {["structured", "raw"].map((v) => (
              <button
                key={v}
                onClick={() => setView(v as "structured" | "raw")}
                className={cn(
                  "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-medium transition-all",
                  view === v
                    ? "bg-white/10 text-white"
                    : "text-slate-500 hover:bg-white/5 hover:text-slate-300",
                )}
              >
                {v === "structured" ? <Layers size={12} /> : <Braces size={12} />}
                {v === "structured" ? "Structured" : "Raw"}
              </button>
            ))}
            <button onClick={copyJSON} title="Copy JSON"
              className="rounded-lg p-2 text-slate-500 transition-all hover:bg-white/5 hover:text-white">
              <Copy size={14} />
            </button>
            {result.id && (
              <>
                <a href={getExportUrl(result.id, "json")} download title="Download JSON"
                  className="rounded-lg p-2 text-slate-500 transition-all hover:bg-white/5 hover:text-white">
                  <Download size={14} />
                </a>
                <a href={getExportUrl(result.id, "csv")} download title="Download CSV"
                  className="rounded-lg p-2 text-slate-500 transition-all hover:bg-white/5 hover:text-white">
                  <FileText size={14} />
                </a>
              </>
            )}
          </div>
        </div>

        {/* Warnings */}
        {result.warnings.length > 0 && (
          <div className="mt-4">
            <button onClick={() => setWarnOpen(!warnOpen)}
              className="flex items-center gap-2 text-[12px] font-medium text-amber-400 hover:text-amber-300">
              <AlertTriangle size={13} />
              {result.warnings.length} warning{result.warnings.length > 1 ? "s" : ""}
              {warnOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>
            {warnOpen && (
              <ul className="mt-2 space-y-1.5">
                {result.warnings.map((w, i) => (
                  <li key={i} className="rounded-lg border border-amber-500/20 bg-amber-500/[0.07] px-3 py-2 text-[11.5px] text-amber-300/90">
                    {w}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {/* Confidence */}
      {Object.keys(result.field_confidence).length > 0 && (
        <div className={cn(CARD, "p-4 md:p-5")}>
          <p className="mb-4 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Field Confidence · live values</p>
          <ConfidenceBars scores={result.field_confidence} values={result.data} />
        </div>
      )}

      {/* Data */}
      <div className={cn(CARD, "overflow-hidden")}>
        {view === "structured" ? (
          <div className="p-4 md:p-5">
            <DataTree data={result.data} />
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-2.5">
              <span className="font-mono text-[11px] text-slate-500">extracted_data.json</span>
              <span className="font-mono text-[11px] text-slate-600">
                {JSON.stringify(result.data).length.toLocaleString()} bytes
              </span>
            </div>
            <div className="max-h-[460px] overflow-y-auto p-4 font-mono text-[12px] leading-relaxed">
              <JsonView data={result.data} shouldExpandNode={allExpanded} style={darkStyles} />
            </div>
          </>
        )}
      </div>

      {/* Processing notes */}
      {result.processing_notes.length > 0 && (
        <div className={cn(CARD)}>
          <button onClick={() => setNotesOpen(!notesOpen)}
            className="flex w-full items-center justify-between px-4 py-3 text-[11.5px] text-slate-500 hover:text-slate-400">
            <span>Processing notes ({result.processing_notes.length})</span>
            {notesOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>
          {notesOpen && (
            <ul className="space-y-1 border-t border-white/[0.04] px-4 py-3">
              {result.processing_notes.map((n, i) => (
                <Fragment key={i}>
                  <li className="text-[11.5px] text-slate-500">· {n}</li>
                </Fragment>
              ))}
            </ul>
          )}
        </div>
      )}
    </motion.div>
  );
}
