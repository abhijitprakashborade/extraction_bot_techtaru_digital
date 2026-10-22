import axios from "axios";
import type { ExtractionResponse, HistoryItem, Stats, DocumentType, HealthInfo } from "@/types";

const api = axios.create({
  baseURL: "/api/v1",
  timeout: 120_000, // 2-min timeout — large files through OCR + LLM can take a while
});

export async function getHealth(): Promise<HealthInfo> {
  const { data } = await axios.get<HealthInfo>("/health");
  return data;
}

export async function extractFromFile(
  file: File,
  documentType?: DocumentType,
): Promise<ExtractionResponse> {
  const form = new FormData();
  form.append("file", file);
  if (documentType && documentType !== "UNKNOWN") {
    form.append("document_type", documentType);
  }
  const { data } = await api.post<ExtractionResponse>("/extract/file", form);
  return data;
}

export async function extractFromText(
  text: string,
  documentType?: DocumentType,
  customFields?: string[],
): Promise<ExtractionResponse> {
  const { data } = await api.post<ExtractionResponse>("/extract/text", {
    text,
    document_type: documentType || null,
    custom_fields: customFields || null,
  });
  return data;
}

export async function getHistory(params?: {
  limit?: number;
  offset?: number;
  document_type?: string;
}): Promise<HistoryItem[]> {
  const { data } = await api.get<HistoryItem[]>("/history", { params });
  return data;
}

export async function getHistoryItem(id: number): Promise<ExtractionResponse> {
  const { data } = await api.get<ExtractionResponse>(`/history/${id}`);
  return data;
}

export async function deleteHistoryItem(id: number): Promise<void> {
  await api.delete(`/history/${id}`);
}

export async function getStats(): Promise<Stats> {
  const { data } = await api.get<Stats>("/stats");
  return data;
}

export function getExportUrl(id: number, format: "json" | "csv"): string {
  return `/api/v1/history/${id}/export?format=${format}`;
}
