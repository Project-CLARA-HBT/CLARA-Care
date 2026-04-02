import api from "@/lib/http-client";
import { CareguardAnalyzeRawResponse, CareguardAnalyzeResult, normalizeCareguardResult } from "@/lib/careguard";

export type CabinetItem = {
  id: number;
  drug_name: string;
  normalized_name: string;
  normalization_source?: "db" | "candidate" | "fallback" | null;
  normalization_confidence?: number | null;
  dosage: string;
  dosage_form: string;
  quantity: number;
  source: string;
  rx_cui: string;
  ocr_confidence: number | null;
  expires_on: string | null;
  note: string;
  created_at: string;
  updated_at: string;
};

export type CabinetResponse = {
  cabinet_id: number;
  label: string;
  items: CabinetItem[];
};

export type ScanDetection = {
  drug_name: string;
  normalized_name: string;
  confidence: number;
  evidence: string;
  requires_manual_confirm?: boolean;
  confirmed?: boolean;
  mapping_source?: "db" | "candidate" | "fallback" | null;
  mapping_confidence?: number | null;
};

export const LOW_CONFIDENCE_DETECTION_THRESHOLD = 0.9;

export function isLowConfidenceDetection(detection: ScanDetection): boolean {
  return detection.confidence < LOW_CONFIDENCE_DETECTION_THRESHOLD;
}

type ScanResponse = {
  detections: ScanDetection[];
  extracted_text?: string | null;
  ocr_provider?: string | null;
  ocr_endpoint?: string | null;
};

export type AddCabinetItemPayload = {
  drug_name: string;
  dosage?: string;
  dosage_form?: string;
  quantity?: number;
  source?: "manual" | "ocr" | "barcode" | "imported";
  rx_cui?: string;
  ocr_confidence?: number | null;
  expires_on?: string | null;
  note?: string;
};

export type UpdateCabinetItemPayload = Partial<AddCabinetItemPayload>;

type AutoDdiRequest = {
  symptoms?: string[];
  labs?: Record<string, number | string>;
  allergies?: string[];
};

export async function getCabinet(): Promise<CabinetResponse> {
  const response = await api.get<CabinetResponse>("/careguard/cabinet");
  return response.data;
}

export async function addCabinetItem(payload: AddCabinetItemPayload): Promise<CabinetItem> {
  const response = await api.post<CabinetItem>("/careguard/cabinet/items", payload);
  return response.data;
}

export async function updateCabinetItem(
  itemId: number,
  payload: UpdateCabinetItemPayload
): Promise<CabinetItem> {
  const response = await api.patch<CabinetItem>(`/careguard/cabinet/items/${itemId}`, payload);
  return response.data;
}

export async function deleteCabinetItem(itemId: number): Promise<void> {
  await api.delete(`/careguard/cabinet/items/${itemId}`);
}

export async function scanReceiptText(text: string): Promise<ScanDetection[]> {
  const response = await api.post<ScanResponse>("/careguard/cabinet/scan-text", { text });
  return response.data.detections ?? [];
}

export async function scanReceiptFile(file: File): Promise<ScanDetection[]> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await api.post<ScanResponse>("/careguard/cabinet/scan-file", formData, {
    headers: { "Content-Type": "multipart/form-data" }
  });
  return response.data.detections ?? [];
}

export async function importDetections(detections: ScanDetection[]): Promise<number> {
  const response = await api.post<{ inserted: number }>("/careguard/cabinet/import-detections", { detections });
  return response.data.inserted ?? 0;
}

export async function runCabinetAutoDdi(payload: AutoDdiRequest): Promise<CareguardAnalyzeResult> {
  const response = await api.post<CareguardAnalyzeRawResponse>("/careguard/cabinet/auto-ddi-check", payload);
  return normalizeCareguardResult(response.data);
}
