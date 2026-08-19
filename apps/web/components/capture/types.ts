import type {
  CaptureArtifactV2,
  CaptureCandidateV2,
  CaptureCategory,
  CaptureSessionV2,
  CandidateReviewStatus,
} from "@/lib/api/v2-client";
import type { IconName } from "@/components/ui/icon";

export type CaptureMethod = "camera" | "upload" | "medicine_scan" | "voice" | "manual";

export interface CaptureMethodConfig {
  id: CaptureMethod;
  labelVi: string;
  labelEn: string;
  descriptionVi: string;
  descriptionEn: string;
  icon: IconName;
}

export const CAPTURE_METHODS: CaptureMethodConfig[] = [
  {
    id: "camera",
    labelVi: "Chụp ảnh",
    labelEn: "Camera",
    descriptionVi: "Chụp trực tiếp đơn thuốc, kết quả xét nghiệm hoặc nhãn thuốc",
    descriptionEn: "Directly photograph prescription, lab report, or medicine label",
    icon: "camera",
  },
  {
    id: "upload",
    labelVi: "Tải tài liệu/PDF",
    labelEn: "Upload Document",
    descriptionVi: "Tải file PDF, ảnh chụp tài liệu y tế sẵn có từ thiết bị",
    descriptionEn: "Upload existing PDF or medical document image from device",
    icon: "upload",
  },
  {
    id: "medicine_scan",
    labelVi: "Quét thuốc",
    labelEn: "Medicine Scan",
    descriptionVi: "Nhận diện vỏ hộp, vỉ thuốc hoặc toa thuốc theo đơn",
    descriptionEn: "Scan medicine box, blister pack, or prescription",
    icon: "medication",
  },
  {
    id: "voice",
    labelVi: "Ghi âm/Lời nói",
    labelEn: "Voice Input",
    descriptionVi: "Nói triệu chứng, chỉ số hoặc toa thuốc bằng giọng nói tiếng Việt",
    descriptionEn: "Speak symptoms, vitals, or medication details by voice",
    icon: "mic",
  },
  {
    id: "manual",
    labelVi: "Nhập thủ công",
    labelEn: "Manual Entry",
    descriptionVi: "Tự nhập thông tin trực tiếp hoặc khi ngoại tuyến",
    descriptionEn: "Manually enter details directly or when offline",
    icon: "edit",
  },
];

export interface CategoryMeta {
  labelVi: string;
  labelEn: string;
  icon: IconName;
  tone: "brand" | "ok" | "warn" | "danger" | "neutral";
}

export const CATEGORY_META_MAP: Record<string, CategoryMeta> = {
  medication: {
    labelVi: "Thuốc",
    labelEn: "Medication",
    icon: "medication",
    tone: "brand",
  },
  measurement: {
    labelVi: "Chỉ số",
    labelEn: "Measurement",
    icon: "progress",
    tone: "ok",
  },
  vital: {
    labelVi: "Sinh hiệu",
    labelEn: "Vital",
    icon: "progress",
    tone: "ok",
  },
  condition: {
    labelVi: "Bệnh lý",
    labelEn: "Condition",
    icon: "body",
    tone: "warn",
  },
  allergy: {
    labelVi: "Dị ứng",
    labelEn: "Allergy",
    icon: "warning",
    tone: "danger",
  },
  document: {
    labelVi: "Tài liệu",
    labelEn: "Document",
    icon: "clinical-notes",
    tone: "neutral",
  },
  lab: {
    labelVi: "Xét nghiệm",
    labelEn: "Lab Result",
    icon: "scan",
    tone: "neutral",
  },
  visit: {
    labelVi: "Lần khám",
    labelEn: "Visit",
    icon: "calendar",
    tone: "neutral",
  },
  clinical_note: {
    labelVi: "Ghi chú",
    labelEn: "Note",
    icon: "clinical-notes",
    tone: "neutral",
  },
  general: {
    labelVi: "Khác",
    labelEn: "General",
    icon: "clinical-notes",
    tone: "neutral",
  },
};

export function getCategoryMeta(category?: string | null): CategoryMeta {
  if (!category) return CATEGORY_META_MAP.general;
  const key = category.toLowerCase().trim();
  return CATEGORY_META_MAP[key] ?? {
    labelVi: category,
    labelEn: category,
    icon: "clinical-notes",
    tone: "neutral",
  };
}

export function formatCandidateFieldName(
  fieldName: string,
  locale: "vi" | "en" = "vi",
): string {
  const isEn = locale === "en";
  const nameMap: Record<string, { vi: string; en: string }> = {
    medication_name: { vi: "Tên thuốc", en: "Medication Name" },
    drug_name: { vi: "Tên thuốc", en: "Drug Name" },
    dosage: { vi: "Liều lượng", en: "Dosage" },
    strength: { vi: "Hàm lượng", en: "Strength" },
    frequency: { vi: "Tần suất dùng", en: "Frequency" },
    instructions: { vi: "Hướng dẫn dùng", en: "Instructions" },
    route: { vi: "Đường dùng", en: "Route" },
    start_date: { vi: "Ngày bắt đầu", en: "Start Date" },
    end_date: { vi: "Ngày kết thúc", en: "End Date" },
    prescribed_by: { vi: "Bác sĩ kê đơn", en: "Prescribed By" },
    condition_name: { vi: "Tên chẩn đoán / bệnh", en: "Condition Name" },
    diagnosis: { vi: "Chẩn đoán", en: "Diagnosis" },
    clinical_status: { vi: "Tình trạng lâm sàng", en: "Clinical Status" },
    onset_date: { vi: "Ngày phát hiện", en: "Onset Date" },
    substance: { vi: "Dị nguyên / Chất gây dị ứng", en: "Allergen / Substance" },
    reaction: { vi: "Phản ứng", en: "Reaction" },
    severity: { vi: "Mức độ nghiêm trọng", en: "Severity" },
    measurement_type: { vi: "Loại chỉ số", en: "Measurement Type" },
    type: { vi: "Loại", en: "Type" },
    value: { vi: "Giá trị", en: "Value" },
    systolic: { vi: "Huyết áp tâm thu", en: "Systolic BP" },
    diastolic: { vi: "Huyết áp tâm trương", en: "Diastolic BP" },
    heart_rate: { vi: "Nhịp tim", en: "Heart Rate" },
    blood_glucose: { vi: "Đường huyết", en: "Blood Glucose" },
    temperature: { vi: "Thân nhiệt", en: "Body Temp" },
    weight: { vi: "Cân nặng", en: "Weight" },
    height: { vi: "Chiều cao", en: "Height" },
    spo2: { vi: "Độ bão hòa oxy (SpO2)", en: "SpO2" },
    unit: { vi: "Đơn vị", en: "Unit" },
    recorded_at: { vi: "Thời điểm ghi nhận", en: "Recorded At" },
    document_type: { vi: "Loại tài liệu", en: "Document Type" },
    document_date: { vi: "Ngày lập tài liệu", en: "Document Date" },
    facility: { vi: "Cơ sở y tế", en: "Facility" },
    notes: { vi: "Ghi chú", en: "Notes" },
  };

  const formatted = nameMap[fieldName.toLowerCase()];
  if (formatted) return isEn ? formatted.en : formatted.vi;

  // Fallback: title case snake_case
  return fieldName
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatCandidateValue(
  value: string | number | Record<string, unknown> | null | undefined,
): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);

  // If object has common fields
  if (typeof value === "object") {
    const obj = value as Record<string, unknown>;
    if (obj.systolic !== undefined && obj.diastolic !== undefined) {
      return `${obj.systolic}/${obj.diastolic} ${obj.unit || "mmHg"}`;
    }
    if (obj.value !== undefined) {
      return `${obj.value}${obj.unit ? ` ${obj.unit}` : ""}`;
    }
    if (obj.name) return String(obj.name);
    if (obj.medication_name) {
      const parts = [obj.medication_name];
      if (obj.dosage || obj.strength) parts.push(String(obj.dosage || obj.strength));
      if (obj.frequency) parts.push(String(obj.frequency));
      return parts.join(" • ");
    }
    return JSON.stringify(obj);
  }

  return String(value);
}

export type {
  CaptureArtifactV2,
  CaptureCandidateV2,
  CaptureCategory,
  CaptureSessionV2,
  CandidateReviewStatus,
};
