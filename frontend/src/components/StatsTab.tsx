import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Clock, FileStack, Gauge, Layers, Zap } from "lucide-react";
import { cn, confColor } from "@/utils/common";
import { getStats, getHistory } from "@/utils/api";
import type { HistoryItem } from "@/types";

const CARD = "rounded-2xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-sm";

const BAR_COLORS = ["#818cf8", "#a78bfa", "#c084fc", "#f472b6", "#38bdf8", "#34d399", "#fbbf24"];

export default function StatsTab() {
  const { data: stats } = useQuery({ queryKey: ["stats"], queryFn: getStats });
  const { data: history = [] } = useQuery<HistoryItem[]>({
    queryKey: ["history"],
    queryFn: () => getHistory({ limit: 50 }),
  });

  if (!stats) return null;

  const chartData = Object.entries(stats.by_document_type)
    .sort(([, a], [, b]) => b - a)
    .map(([type, count]) => ({ type: type.replace("_", " "), count }));

  const trend = [...history]
    .reverse()
    .slice(-20)
    .map((h, i) => ({ n: i + 1, conf: Math.round(h.overall_confidence * 100) }));

  const cards = [
    { label: "Total extractions", value: stats.total_extractions.toLocaleString(), icon: <Zap size={15} className="text-indigo-400" /> },
    { label: "Avg confidence", value: `${(stats.avg_confidence * 100).toFixed(1)}%`, icon: <Gauge size={15} className="text-emerald-400" /> },
    { label: "Avg processing", value: `${stats.avg_processing_ms.toFixed(0)} ms`, icon: <Clock size={15} className="text-amber-400" /> },
    { label: "Doc types used", value: chartData.length, icon: <Layers size={15} className="text-fuchsia-400" /> },
  ];

  return (
    <div className="space-y-4">
      <h2 className="font-display text-lg font-semibold text-white">Analytics</h2>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {cards.map((c) => (
          <div key={c.label} className={cn(CARD, "p-4")}>
            <div className="mb-2 flex items-center gap-2 text-[12px] text-slate-400">{c.icon} {c.label}</div>
            <div className="font-display text-2xl font-bold text-white">{c.value}</div>
          </div>
        ))}
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <div className={cn(CARD, "p-4 md:p-5")}>
          <p className="mb-4 flex items-center gap-2 text-[12px] font-semibold text-slate-300">
            <FileStack size={13} className="text-indigo-400" /> Extractions by document type
          </p>
          {chartData.length === 0 ? (
            <p className="py-12 text-center text-[13px] text-slate-500">No data yet</p>
          ) : (
            <div className="h-52">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
                  <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis dataKey="type" tick={{ fill: "#94a3b8", fontSize: 10.5 }} axisLine={false} tickLine={false} />
                  <YAxis allowDecimals={false} tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip
                    cursor={{ fill: "rgba(255,255,255,0.04)" }}
                    contentStyle={{ background: "#12121c", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 10, fontSize: 12 }}
                    itemStyle={{ color: "#e2e8f0" }}
                  />
                  <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                    {chartData.map((_, i) => (
                      <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div className={cn(CARD, "p-4 md:p-5")}>
          <p className="mb-4 flex items-center gap-2 text-[12px] font-semibold text-slate-300">
            <Gauge size={13} className="text-emerald-400" /> Confidence over recent runs
          </p>
          {trend.length === 0 ? (
            <p className="py-12 text-center text-[13px] text-slate-500">No data yet</p>
          ) : (
            <div className="flex h-52 items-end gap-[3px]">
              {trend.map((t) => (
                <div key={t.n} className="group flex-1" title={`run ${t.n}: ${t.conf}%`}>
                  <div className="flex h-44 items-end">
                    <div
                      className={cn(
                        "w-full rounded-t-md transition-all",
                        t.conf >= 85 ? "bg-emerald-500/70 group-hover:bg-emerald-400" :
                        t.conf >= 60 ? "bg-amber-500/70 group-hover:bg-amber-400" :
                                       "bg-rose-500/70 group-hover:bg-rose-400",
                      )}
                      style={{ height: `${Math.max(t.conf, 2)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
          {trend.length > 0 && (
            <div className="mt-3 flex justify-center text-[11px] text-slate-500">
              avg {trend.reduce((a, b) => a + b.conf, 0) / trend.length >= 85 ? (
                <span className="text-emerald-400">{(trend.reduce((a, b) => a + b.conf, 0) / trend.length).toFixed(0)}%</span>
              ) : (
                <span>{(trend.reduce((a, b) => a + b.conf, 0) / trend.length).toFixed(0)}%</span>
              )} across last {trend.length} runs
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
