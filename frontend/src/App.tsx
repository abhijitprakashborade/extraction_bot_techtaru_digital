import { useCallback, useRef, useState } from "react";
import { useDropzone } from "react-dropzone";
import { motion, AnimatePresence } from "framer-motion";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import toast, { Toaster } from "react-hot-toast";
import Header, { type Tab } from "@/components/Header";
import HistoryTab from "@/components/HistoryTab";
import StatsTab from "@/components/StatsTab";
import ResultPanel from "@/components/ResultPanel";
import { Pipeline } from "@/components/Pipeline";
import Logo from "@/components/Logo";
import { getHealth, extractFromFile, extractFromText } from "@/utils/api";
import { cn, DOC_TYPES } from "@/utils/common";
import { SAMPLE_RESUME, SAMPLE_INVOICE, SAMPLE_BUSINESS_CARD, SAMPLE_CONTRACT } from "@/utils/samples";
import type { DocumentType, ExtractionResponse, PipelineStage } from "@/types";
import { ClipboardList, FileText, FileUp, Layers, Loader2, Settings2, Upload, Wand2 } from "lucide-react";

const IDLE_STAGES: PipelineStage[] = [
  { id: "upload",   label: "Read & preprocess", status: "idle" },
  { id: "classify", label: "Classify type",     status: "idle" },
  { id: "extract",  label: "Structured extract", status: "idle" },
  { id: "validate", label: "Pydantic validate", status: "idle" },
  { id: "score",    label: "Confidence score",  status: "idle" },
];

const SAMPLES: { label: string; type: DocumentType; text: string }[] = [
  { label: "Resume",   type: "RESUME",        text: SAMPLE_RESUME },
  { label: "Invoice",  type: "INVOICE",       text: SAMPLE_INVOICE },
  { label: "Card",     type: "BUSINESS_CARD", text: SAMPLE_BUSINESS_CARD },
  { label: "Contract", type: "CONTRACT",      text: SAMPLE_CONTRACT },
];

const CARD = "rounded-2xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-sm";

export default function App() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("extract");
  const [mode, setMode] = useState<"file" | "text">("file");
  const [docType, setDocType] = useState<DocumentType>("UNKNOWN");
  const [rawText, setRawText] = useState("");
  const [customFields, setCustomFields] = useState("");
  const [result, setResult] = useState<ExtractionResponse | null>(null);
  const [stages, setStages] = useState<PipelineStage[]>(IDLE_STAGES.map((s) => ({ ...s })));
  const [fileMeta, setFileMeta] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const { data: health, isError: healthOffline } = useQuery<import("@/types").HealthInfo>({
    queryKey: ["health"],
    queryFn: getHealth,
    staleTime: 60_000,
    retry: 1,
  });
  const resultRef = useRef<HTMLDivElement | null>(null);

  /* ── Pipeline stage control: mirrors the real backend pipeline.
     Backed by the single HTTP result — stages advance as the
     request proceeds, never with artificial sleeps. ── */
  const setStage = (id: string, status: PipelineStage["status"]) =>
    setStages((prev) => prev.map((s) => (s.id === id ? { ...s, status } : s)));

  const markAllDone = () =>
    setStages((prev) => prev.map((s) => ({ ...s, status: "done" as const })));

  /* ── Dropzone ── */
  const onDrop = useCallback((files: File[]) => {
    const file = files[0];
    if (!file) return;
    runExtraction({ file, name: file.name });
  }, []);
  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
      "text/plain": [".txt"],
      "image/png": [".png"],
      "image/jpeg": [".jpg", ".jpeg"],
    },
    maxFiles: 1,
    maxSize: 10 * 1024 * 1024,
    noClick: true,
    multiple: false,
  });

  /* ── Extraction mutation ── */
  const runExtraction = async (payload: { file?: File; text?: string; name?: string }) => {
    if (busy) return;
    setBusy(true);
    setStages(IDLE_STAGES.map((s) => ({ ...s, status: "idle" })));
    setResult(null);
    setFileMeta(payload.name ?? null);
    setStage("upload", "running");

    const fields = customFields.split(",").map((f) => f.trim()).filter(Boolean);

    try {
      const res = payload.file
        ? await extractFromFile(payload.file, docType)
        : await extractFromText(payload.text!, docType, fields.length ? fields : undefined);

      markAllDone();
      setResult(res);
      qc.invalidateQueries({ queryKey: ["history"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      toast.success(
        `Extracted ${res.document_type.replace("_", " ")} in ${res.processing_time_ms.toFixed(0)} ms`,
        { iconTheme: { primary: "#8b5cf6", secondary: "#12121c" } },
      );
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 100);
    } catch (err: unknown) {
      const axiosErr = err as {
        response?: { data?: { detail?: string }; status?: number };
        request?: unknown;
        code?: string;
      };
      let msg: string;
      if (axiosErr.response?.data?.detail) {
        msg = String(axiosErr.response.data.detail);
        if (axiosErr.response?.status === 429) msg = "⏳ " + msg;
      } else if (axiosErr.request) {
        msg =
          "Can't reach the backend — start it in a separate terminal: " +
          "cd backend && uvicorn app.main:app --port 8000";
      } else {
        msg = "Extraction failed — try again";
      }
      setStages((prev) =>
        prev.map((s) =>
          s.status === "running"
            ? { ...s, status: "error" }
            : s.status === "done"
              ? { ...s, status: "done" }
              : s,
        ),
      );
      toast.error(msg.slice(0, 200), { duration: 6000 });
    } finally {
      setBusy(false);
    }
  };

  const extract = async () => {
    if (mode === "text" && !rawText.trim()) {
      toast.error("Please enter some text");
      return;
    }
    if (docType === "CUSTOM" && mode === "text" && !customFields.trim()) {
      toast.error("Add at least one custom field");
      return;
    }
    await runExtraction({ text: rawText });
  };

  return (
    <div className="relative min-h-screen bg-[#07070c] font-sans text-slate-200 antialiased">
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: "#12121c",
            color: "#e2e8f0",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 12,
            fontSize: 13,
          },
        }}
      />

      {/* Ambient background */}
      <div aria-hidden className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-40 left-1/4 h-[480px] w-[720px] rounded-full bg-indigo-600/[0.07] blur-[120px]" />
        <div className="absolute right-0 top-1/3 h-[380px] w-[520px] rounded-full bg-fuchsia-600/[0.05] blur-[120px]" />
        <div
          className="absolute inset-0 opacity-[0.35]"
          style={{
            backgroundImage:
              "radial-gradient(rgba(255,255,255,0.045) 1px, transparent 1px)",
            backgroundSize: "28px 28px",
          }}
        />
      </div>

      <Header tab={tab} onTab={(t) => setTab(t)} health={health} />

      {healthOffline && (
        <div className="relative border-b border-amber-500/20 bg-amber-500/[0.07] px-4 py-2.5 text-center text-[12.5px] text-amber-300">
          Backend API is offline — extraction needs it running. In a new terminal:{" "}
          <code className="rounded bg-black/40 px-1.5 py-0.5 font-mono text-[11.5px]">cd backend &amp;&amp; .venv\Scripts\activate &amp;&amp; uvicorn app.main:app --port 8000</code>
          {" "}or just run <code className="rounded bg-black/40 px-1.5 py-0.5 font-mono text-[11.5px]">START_ALL.bat</code>
        </div>
      )}

      <main className="relative mx-auto max-w-7xl px-4 pb-20 pt-8 md:px-8">
        {tab === "extract" && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[420px_1fr] xl:grid-cols-[460px_1fr]">
            {/* ══════════ Left — input workspace */}
            <div className="space-y-4">
              <div>
                <h1 className="font-display text-[26px] font-bold leading-tight text-white">
                  Document intelligence,{" "}
                  <span className="bg-gradient-to-r from-indigo-400 via-violet-400 to-fuchsia-400 bg-clip-text text-transparent">
                    structured on demand
                  </span>
                </h1>
                <p className="mt-1.5 text-[13.5px] leading-relaxed text-slate-400">
                  Upload a file or paste text — get validated, confidence-scored JSON
                  for resumes, invoices, contracts and cards.
                </p>
              </div>

              {/* Mode switch */}
              <div className={cn(CARD, "grid grid-cols-2 gap-1 p-1")}>
                {(["file", "text"] as const).map((m) => (
                  <button
                    key={m}
                    onClick={() => setMode(m)}
                    className={cn(
                      "flex items-center justify-center gap-2 rounded-xl py-2 text-[13px] font-medium capitalize transition-all",
                      mode === m
                        ? "bg-gradient-to-r from-indigo-500/80 to-violet-500/80 text-white shadow shadow-violet-500/20"
                        : "text-slate-400 hover:text-white",
                    )}
                  >
                    {m === "file" ? <FileUp size={14} /> : <FileText size={14} />}
                    {m === "file" ? "Upload file" : "Paste text"}
                  </button>
                ))}
              </div>

              {/* Document type */}
              <div className={cn(CARD, "p-4")}>
                <p className="mb-2.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                  <Layers size={11} /> Document type
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {DOC_TYPES.map((dt) => (
                    <button
                      key={dt.value}
                      onClick={() => setDocType(dt.value)}
                      className={cn(
                        "rounded-lg px-2.5 py-1.5 text-[12px] font-medium transition-all",
                        docType === dt.value
                          ? "border border-indigo-500/60 bg-indigo-500/15 text-indigo-300"
                          : "border border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/25 hover:text-slate-200",
                      )}
                    >
                      {dt.label}
                    </button>
                  ))}
                </div>

                <AnimatePresence>
                  {docType === "CUSTOM" && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="mt-3 flex items-center gap-2 rounded-lg border border-white/10 bg-black/30 px-3 py-2">
                        <Settings2 size={13} className="shrink-0 text-indigo-400" />
                        <input
                          value={customFields}
                          onChange={(e) => setCustomFields(e.target.value)}
                          placeholder="company_name, founding_year, ceo, revenue"
                          className="w-full border-0 bg-transparent text-[12.5px] text-slate-200 outline-none placeholder:text-slate-600"
                        />
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Input area */}
              {mode === "file" ? (
                <div
                  {...getRootProps()}
                  className={cn(
                    "group cursor-default rounded-2xl border-2 border-dashed p-7 text-center transition-all",
                    isDragActive
                      ? "border-indigo-500/70 bg-indigo-500/[0.07] shadow-[0_0_60px_-15px_rgba(99,102,241,0.35)]"
                      : "border-white/10 bg-white/[0.02] hover:border-white/25 hover:bg-white/[0.04]",
                  )}
                >
                  <input {...getInputProps()} />
                  <div className="flex flex-col items-center gap-3">
                    <div className={cn(
                      "flex h-12 w-12 items-center justify-center rounded-xl transition-all",
                      isDragActive ? "bg-indigo-500/20 text-indigo-300" : "bg-white/[0.06] text-slate-500 group-hover:text-slate-400",
                    )}>
                      <Upload size={20} />
                    </div>
                    <div>
                      <p className="text-[13.5px] font-medium text-slate-200">
                        {isDragActive ? "Drop to extract" : "Drag & drop your document"}
                      </p>
                      <p className="mt-0.5 text-[11.5px] text-slate-500">PDF · DOCX · TXT · PNG · JPG — up to 10 MB</p>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); open(); }}
                      className="rounded-lg bg-gradient-to-r from-indigo-500 to-violet-500 px-4 py-1.5 text-[12.5px] font-semibold text-white shadow shadow-violet-500/25 transition-all hover:brightness-110"
                    >
                      Browse files
                    </button>
                  </div>
                </div>
              ) : (
                <div className={cn(CARD, "overflow-hidden")}>
                  <div className="relative">
                    <textarea
                      value={rawText}
                      onChange={(e) => setRawText(e.target.value)}
                      placeholder="Paste a resume, invoice, contract or any unstructured text…"
                      rows={12}
                      maxLength={50_000}
                      className="block w-full resize-none bg-transparent px-4 py-3.5 font-mono text-[12.5px] leading-relaxed text-slate-200 outline-none placeholder:text-slate-600"
                    />
                  </div>
                  <div className="flex items-center justify-between gap-3 border-t border-white/[0.06] px-3 py-2">
                    <div className="flex flex-wrap gap-1">
                      {SAMPLES.map((s) => (
                        <button
                          key={s.label}
                          onClick={() => {
                            setRawText(s.text);
                            setDocType(s.type);
                          }}
                          className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-[10.5px] text-slate-400 transition-all hover:border-indigo-500/40 hover:text-indigo-300"
                        >
                          {s.label} sample
                        </button>
                      ))}
                    </div>
                    <span className="shrink-0 font-mono text-[10.5px] text-slate-600">
                      {rawText.length.toLocaleString()} / 50,000
                    </span>
                  </div>
                </div>
              )}

              {/* Extract CTA */}
              {mode === "text" && (
                <button
                  onClick={extract}
                  disabled={busy || !rawText.trim()}
                  className={cn(
                    "group flex w-full items-center justify-center gap-2 rounded-xl py-3 text-[13.5px] font-semibold transition-all",
                    busy || !rawText.trim()
                      ? "cursor-not-allowed bg-white/[0.04] text-slate-600"
                      : "bg-gradient-to-r from-indigo-500 via-violet-500 to-fuchsia-500 text-white shadow-[0_8px_30px_-6px_rgba(139,92,246,0.45)] hover:brightness-110 active:scale-[0.99]",
                  )}
                >
                  {busy ? <Loader2 size={15} className="animate-spin" /> : <Wand2 size={15} />}
                  {busy ? "Extracting…" : "Extract structured data"}
                </button>
              )}

              {/* Pipeline */}
              <AnimatePresence>
                {(busy || stages.some((s) => s.status !== "idle")) && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="overflow-hidden"
                  >
                    <div className={cn(CARD, "p-4")}>
                      <p className="mb-3 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                        <ClipboardList size={11} /> Extraction pipeline
                      </p>
                      <Pipeline stages={stages} />
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* ══════════ Right — result space */}
            <div ref={resultRef} className="min-w-0 space-y-4">
              {!result && !busy && (
                <div className={cn(CARD, "flex min-h-[240px] flex-col items-center justify-center gap-3 px-6 py-16 text-center")}>
                  <Logo size={72} className="opacity-90 drop-shadow-[0_10px_40px_rgba(124,58,237,0.35)]" />
                  <p className="mt-1 text-[13.5px] font-medium text-slate-400">Nothing extracted yet</p>
                  <p className="max-w-xs text-[12px] leading-relaxed text-slate-600">
                    Use sample buttons for a one-click walkthrough, or drop your own
                    document — the pipeline handles rate limits, empty inputs and
                    missing data gracefully.
                  </p>
                </div>
              )}

              {busy && (
                <div className={cn(CARD, "space-y-3 p-5")}>
                  {[...Array(6)].map((_, i) => (
                    <div key={i} className={cn("h-4 animate-pulse rounded bg-white/[0.05]",
                      i === 0 ? "w-1/3" : i % 3 === 0 ? "w-2/3" : "w-full")} />
                  ))}
                </div>
              )}

              {result && <ResultPanel result={result} />}
            </div>
          </div>
        )}

        {tab === "history" && <HistoryTab />}
        {tab === "stats" && <StatsTab />}
      </main>

      <footer className="relative border-t border-white/[0.05] py-5 text-center text-[11px] text-slate-600">
        TechTaru DocIQ · Structured Document Intelligence · built by TechTaru Digital
      </footer>
    </div>
  );
}
