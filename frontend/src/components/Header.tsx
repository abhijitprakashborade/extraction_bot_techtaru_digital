import { BarChart3, History, Sparkles, ShieldCheck } from "lucide-react";
import { cn } from "@/utils/common";
import Logo from "@/components/Logo";
import type { HealthInfo } from "@/types";

export type Tab = "extract" | "history" | "stats";

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: "extract", label: "Extract", icon: <Sparkles size={13} /> },
  { id: "history", label: "History", icon: <History size={13} /> },
  { id: "stats",   label: "Analytics", icon: <BarChart3 size={13} /> },
];

export default function Header({
  tab, onTab, health,
}: {
  tab: Tab;
  onTab: (t: Tab) => void;
  health?: HealthInfo;
}) {
  const aiMode = health?.engine === "openai-structured";

  return (
    <header className="sticky top-0 z-50 border-b border-white/5 bg-[#0a0a12]/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 md:px-8">
        <div className="flex items-center gap-3">
          <Logo size={36} className="shadow-lg shadow-violet-600/25" />
          <div className="leading-tight">
            <div className="flex items-baseline gap-1.5">
              <span className="font-display text-[15px] font-semibold text-white">
                TechTaru <span className="bg-gradient-to-r from-indigo-400 to-fuchsia-400 bg-clip-text text-transparent">DocIQ</span>
              </span>
            </div>
            <span className="text-[10px] font-medium uppercase tracking-[0.14em] text-slate-500">
              by TechTaru Digital
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {health && (
            <div className="hidden items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-[11px] font-medium sm:flex"
                 title={aiMode
                   ? `OpenAI Structured Outputs · ${health.model}`
                   : "Deterministic heuristic engine — add OPENAI_API_KEY in backend/.env for AI extraction"}>
              <ShieldCheck size={12} className={aiMode ? "text-emerald-400" : "text-amber-400"} />
              {aiMode ? (
                <span className="text-emerald-400">AI Engine · {health.model}</span>
              ) : (
                <span className="text-amber-400">Demo Engine · rules-based</span>
              )}
            </div>
          )}

          <nav className="flex items-center gap-1 rounded-xl border border-white/10 bg-white/5 p-1">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => onTab(t.id)}
                className={cn(
                  "flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-[13px] font-medium transition-all",
                  tab === t.id
                    ? "bg-gradient-to-r from-indigo-500/90 to-violet-500/90 text-white shadow shadow-violet-500/20"
                    : "text-slate-400 hover:text-white",
                )}
              >
                {t.icon}
                <span className="hidden sm:inline">{t.label}</span>
              </button>
            ))}
          </nav>
        </div>
      </div>
    </header>
  );
}
