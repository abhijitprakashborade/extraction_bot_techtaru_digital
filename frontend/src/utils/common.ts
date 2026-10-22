import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const DOC_TYPES: { value: import("@/types").DocumentType; label: string }[] = [
  { value: "UNKNOWN",       label: "Auto-detect" },
  { value: "RESUME",        label: "Resume / CV" },
  { value: "INVOICE",       label: "Invoice" },
  { value: "CONTRACT",      label: "Contract" },
  { value: "BUSINESS_CARD", label: "Business Card" },
  { value: "CUSTOM",        label: "Custom" },
];

export const confColor = (v: number) =>
  v >= 0.85 ? "text-emerald-400" : v >= 0.6 ? "text-amber-400" : "text-rose-400";

export const confBg = (v: number) =>
  v >= 0.85 ? "bg-emerald-500" : v >= 0.6 ? "bg-amber-500" : "bg-rose-500";

export const confText = (v: number) =>
  v >= 0.85 ? "text-emerald-400" : v >= 0.6 ? "text-amber-400" : "text-rose-400";

/** Human-friendly label for a snake_case / dotted field key. */
export const prettyField = (k: string) =>
  k
    .split(/[._]/)
    .map((p) => (p === "url" ? "URL" : p.charAt(0).toUpperCase() + p.slice(1)))
    .join(" › ")
    .replace(/\[[\d]+\]/g, "");

export const isDemoRun = (notes: string[]) =>
  notes.some((n) => /heuristic/i.test(n));
