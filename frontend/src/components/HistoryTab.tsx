import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { JsonView, allExpanded, darkStyles } from "react-json-view-lite";
import { Clock, Download, Eye, FileText, Trash2, X, Filter } from "lucide-react";
import { cn, confColor } from "@/utils/common";
import { deleteHistoryItem, getHistory, getHistoryItem, getExportUrl, getStats } from "@/utils/api";
import type { HistoryItem, ExtractionResponse } from "@/types";

const CARD = "rounded-2xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-sm";

export default function HistoryTab() {
  const qc = useQueryClient();
  const [typeFilter, setTypeFilter] = useState("");
  const [detail, setDetail] = useState<ExtractionResponse | null>(null);

  const { data: history = [], isLoading } = useQuery<HistoryItem[]>({
    queryKey: ["history"],
    queryFn: () => getHistory({ limit: 50 }),
  });

  const { data: stats } = useQuery({ queryKey: ["stats"], queryFn: getStats });
  const typeOptions = Object.keys(stats?.by_document_type ?? {});

  const del = useMutation({
    mutationFn: deleteHistoryItem,
    onSuccess: (_d, id) => {
      qc.invalidateQueries({ queryKey: ["history"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      if (detail?.id === id) setDetail(null);
      toast.success("Record deleted");
    },
    onError: () => toast.error("Failed to delete record"),
  });

  const openDetail = async (id: number) => {
    try {
      setDetail(await getHistoryItem(id));
    } catch {
      toast.error("Failed to load record");
    }
  };

  const filtered = typeFilter
    ? history.filter((h) => h.document_type === typeFilter)
    : history;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <h2 className="font-display text-lg font-semibold text-white">Extraction history</h2>
        <div className="flex items-center gap-2">
          <Filter size={13} className="text-slate-500" />
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-[12px] text-slate-300 outline-none transition-colors hover:bg-white/10"
          >
            <option value="">All types</option>
            {typeOptions.map((t) => (
              <option key={t} value={t}>{t.replace("_", " ")}</option>
            ))}
          </select>
        </div>
      </div>

      {detail && (
        <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} className={cn(CARD)}>
          <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-2.5">
            <span className="text-[12px] font-semibold text-slate-200">
              {detail.file_name || "text-input"}
              <span className="ml-2 rounded bg-white/10 px-1.5 py-0.5 font-mono text-[10px] text-slate-400">
                #{detail.id}
              </span>
            </span>
            <button onClick={() => setDetail(null)} className="text-slate-500 hover:text-white"><X size={15} /></button>
          </div>
          <div className="max-h-[420px] overflow-y-auto p-4 font-mono text-[12px]">
            <JsonView data={detail.data} shouldExpandNode={allExpanded} style={darkStyles} />
          </div>
        </motion.div>
      )}

      <div className={cn(CARD, "overflow-hidden")}>
        {isLoading ? (
          <div className="space-y-2 p-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-10 animate-pulse rounded-lg bg-white/5" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="px-4 py-14 text-center">
            <FileText size={26} className="mx-auto mb-3 text-slate-700" />
            <p className="text-[13px] text-slate-500">No extractions yet — upload a document to get started.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  {["File", "Type", "Confidence", "Chars", "Time", "When", ""].map((h) => (
                    <th key={h} className="px-4 py-3 text-left text-[10.5px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {filtered.map((item) => (
                  <tr key={item.id} className="group transition-colors hover:bg-white/[0.03]">
                    <td className="max-w-[220px] truncate px-4 py-3 text-slate-200" title={item.file_name}>
                      {item.file_name}
                      {item.warnings_count > 0 && (
                        <span className="ml-2 rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-medium text-amber-400">
                          {item.warnings_count}w
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className="rounded-md border border-white/10 bg-white/5 px-2 py-0.5 font-mono text-[10.5px] text-slate-400">
                        {item.document_type.replace("_", " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={cn("font-mono text-[12px] font-semibold", confColor(item.overall_confidence))}>
                        {(item.overall_confidence * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-[11.5px] text-slate-500">{item.raw_text_length.toLocaleString()}</td>
                    <td className="px-4 py-3 font-mono text-[11.5px] text-slate-500">{item.processing_time_ms.toFixed(0)} ms</td>
                    <td className="px-4 py-3 text-[11.5px] text-slate-500">
                      <span className="inline-flex items-center gap-1"><Clock size={11} />
                        {new Date(item.created_at).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" })}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-0.5 opacity-40 transition-opacity group-hover:opacity-100">
                        <button onClick={() => openDetail(item.id)} title="View"
                          className="rounded-lg p-1.5 text-slate-400 hover:bg-white/10 hover:text-indigo-400"><Eye size={13} /></button>
                        <a href={getExportUrl(item.id, "json")} download title="Download JSON"
                          className="rounded-lg p-1.5 text-slate-400 hover:bg-white/10 hover:text-emerald-400"><Download size={13} /></a>
                        <button onClick={() => del.mutate(item.id)} title="Delete"
                          className="rounded-lg p-1.5 text-slate-400 hover:bg-white/10 hover:text-rose-400"><Trash2 size={13} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
