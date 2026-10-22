export type DocumentType =
  | "RESUME" | "INVOICE" | "CONTRACT"
  | "MEDICAL_RECORD" | "BUSINESS_CARD" | "CUSTOM" | "UNKNOWN";

export interface ExtractionResponse {
  id:                       number | null;
  document_type:            DocumentType;
  document_type_confidence: number;
  data:                     Record<string, unknown>;
  field_confidence:         Record<string, number>;
  overall_confidence:       number;
  warnings:                 string[];
  processing_notes:         string[];
  raw_text_length:          number;
  processing_time_ms:       number;
  file_name:                string | null;
}

export interface HistoryItem {
  id:                 number;
  file_name:          string;
  document_type:      string;
  overall_confidence: number;
  raw_text_length:    number;
  processing_time_ms: number;
  created_at:         string;
  warnings_count:     number;
}

export interface Stats {
  total_extractions:  number;
  avg_confidence:     number;
  avg_processing_ms:  number;
  by_document_type:   Record<string, number>;
}

export interface HealthInfo {
  status:                string;
  app:                   string;
  version:               string;
  engine:                "openai-structured" | "heuristic-demo";
  model:                 string;
  rate_limit_per_minute: number;
}

export type ExtractionMode = "file" | "text";

export interface PipelineStage {
  id:     string;
  label:  string;
  status: "idle" | "running" | "done" | "error";
}
