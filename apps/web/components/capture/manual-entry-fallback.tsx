"use client";

import { useState } from "react";
import type { CaptureCandidateV2, CaptureCategory } from "@/lib/api/v2-client";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { CATEGORY_META_MAP } from "./types";

export interface ManualEntryFallbackProps {
  onAddCandidate: (candidate: CaptureCandidateV2) => void;
  onAddMultipleCandidates?: (candidates: CaptureCandidateV2[]) => void;
  locale?: "vi" | "en";
  className?: string;
}

export function parseFreeformText(
  text: string,
  locale: "vi" | "en" = "vi",
): CaptureCandidateV2[] {
  const isEn = locale === "en";
  const trimmed = text.trim();
  if (!trimmed) return [];

  const candidates: CaptureCandidateV2[] = [];
  const lines = trimmed.split("\n").map((l) => l.trim()).filter(Boolean);

  for (const line of lines) {
    const id = `manual-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

    // 1. Blood Pressure match: e.g. "120/80", "HA 130/85"
    const bpMatch = line.match(/(?:huyết áp|ha|bp)?\s*[:=]?\s*(\d{2,3})\s*[\/|:]\s*(\d{2,3})\s*(?:mmhg)?/i);
    if (bpMatch) {
      const systolic = Number(bpMatch[1]);
      const diastolic = Number(bpMatch[2]);
      candidates.push({
        id,
        category: "measurement",
        field_name: "blood_pressure",
        display_name: isEn ? "Blood Pressure" : "Huyết áp",
        value: { systolic, diastolic, unit: "mmHg" },
        unit: "mmHg",
        status: "accepted",
        confidence: 1.0,
        source_snippet: line,
      });
      continue;
    }

    // 2. Heart rate / Pulse: e.g. "nhịp tim 75", "pulse 80 bpm"
    const hrMatch = line.match(/(?:nhịp tim|pulse|heart rate|mạch)\s*[:=]?\s*(\d{2,3})\s*(?:bpm|nhịp\/phút|lần\/phút)?/i);
    if (hrMatch) {
      candidates.push({
        id,
        category: "measurement",
        field_name: "heart_rate",
        display_name: isEn ? "Heart Rate" : "Nhịp tim",
        value: Number(hrMatch[1]),
        unit: "bpm",
        status: "accepted",
        confidence: 1.0,
        source_snippet: line,
      });
      continue;
    }

    // 3. Blood Glucose: e.g. "đường huyết 6.5 mmol/L" or "glucose 110 mg/dL"
    const bgMatch = line.match(/(?:đường huyết|glucose|blood sugar)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(mmol\/l|mg\/dl)?/i);
    if (bgMatch) {
      const unit = bgMatch[2] || "mmol/L";
      candidates.push({
        id,
        category: "measurement",
        field_name: "blood_glucose",
        display_name: isEn ? "Blood Glucose" : "Đường huyết",
        value: Number(bgMatch[1]),
        unit,
        status: "accepted",
        confidence: 1.0,
        source_snippet: line,
      });
      continue;
    }

    // 4. Medication match: e.g. "Paracetamol 500mg ngày 2 viên"
    const medMatch = line.match(/(?:uống|thuốc|medication|rx)?\s*([a-zA-ZÀ-ỹ0-9\s-]+?)\s+(\d+\s*(?:mg|g|ml|mcg|viên|ống|gói))\b(.*)/i);
    if (medMatch) {
      const medName = medMatch[1].trim();
      const dosage = medMatch[2].trim();
      const instructions = medMatch[3].trim();
      candidates.push({
        id,
        category: "medication",
        field_name: "medication_name",
        display_name: medName,
        value: {
          medication_name: medName,
          dosage,
          instructions: instructions || (isEn ? "As directed" : "Theo hướng dẫn"),
        },
        status: "accepted",
        confidence: 1.0,
        source_snippet: line,
      });
      continue;
    }

    // 5. General / Note fallback for the line
    candidates.push({
      id,
      category: "clinical_note",
      field_name: "notes",
      display_name: isEn ? "Clinical Note" : "Ghi chú sức khỏe",
      value: line,
      status: "accepted",
      confidence: 1.0,
      source_snippet: line,
    });
  }

  return candidates;
}

export function ManualEntryFallback({
  onAddCandidate,
  onAddMultipleCandidates,
  locale = "vi",
  className = "",
}: ManualEntryFallbackProps) {
  const isEn = locale === "en";

  const [mode, setMode] = useState<"form" | "freeform">("form");
  const [activeCategory, setActiveCategory] = useState<CaptureCategory>("medication");

  // Form states
  // Medication
  const [medName, setMedName] = useState("");
  const [medDosage, setMedDosage] = useState("");
  const [medFrequency, setMedFrequency] = useState("");
  const [medInstructions, setMedInstructions] = useState("");

  // Measurement
  const [measType, setMeasType] = useState("blood_pressure");
  const [measSystolic, setMeasSystolic] = useState("120");
  const [measDiastolic, setMeasDiastolic] = useState("80");
  const [measValue, setMeasValue] = useState("");
  const [measUnit, setMeasUnit] = useState("mmHg");

  // Condition
  const [condName, setCondName] = useState("");
  const [condStatus, setCondStatus] = useState("active");
  const [condNotes, setCondNotes] = useState("");

  // Allergy
  const [allergySubstance, setAllergySubstance] = useState("");
  const [allergyReaction, setAllergyReaction] = useState("");
  const [allergySeverity, setAllergySeverity] = useState("moderate");

  // Freeform text
  const [freeformText, setFreeformText] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const resetForms = () => {
    setMedName("");
    setMedDosage("");
    setMedFrequency("");
    setMedInstructions("");
    setMeasValue("");
    setCondName("");
    setCondNotes("");
    setAllergySubstance("");
    setAllergyReaction("");
    setFreeformText("");
    setFormError(null);
  };

  const handleAddFormItem = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    const id = `manual-${Date.now()}`;

    if (activeCategory === "medication") {
      if (!medName.trim()) {
        setFormError(isEn ? "Please enter medication name." : "Vui lòng nhập tên thuốc.");
        return;
      }
      onAddCandidate({
        id,
        category: "medication",
        field_name: "medication_name",
        display_name: medName.trim(),
        value: {
          medication_name: medName.trim(),
          dosage: medDosage.trim() || undefined,
          frequency: medFrequency.trim() || undefined,
          instructions: medInstructions.trim() || undefined,
        },
        status: "accepted",
        confidence: 1.0,
      });
      resetForms();
    } else if (activeCategory === "measurement") {
      if (measType === "blood_pressure") {
        if (!measSystolic || !measDiastolic) {
          setFormError(
            isEn ? "Please enter both systolic and diastolic values." : "Vui lòng nhập đầy đủ huyết áp tâm thu và tâm trương.",
          );
          return;
        }
        onAddCandidate({
          id,
          category: "measurement",
          field_name: "blood_pressure",
          display_name: isEn ? "Blood Pressure" : "Huyết áp",
          value: {
            systolic: Number(measSystolic),
            diastolic: Number(measDiastolic),
            unit: "mmHg",
          },
          unit: "mmHg",
          status: "accepted",
          confidence: 1.0,
        });
      } else {
        if (!measValue.trim()) {
          setFormError(isEn ? "Please enter measurement value." : "Vui lòng nhập giá trị đo.");
          return;
        }
        onAddCandidate({
          id,
          category: "measurement",
          field_name: measType,
          display_name: measType,
          value: Number(measValue) || measValue.trim(),
          unit: measUnit,
          status: "accepted",
          confidence: 1.0,
        });
      }
      resetForms();
    } else if (activeCategory === "condition") {
      if (!condName.trim()) {
        setFormError(isEn ? "Please enter condition name." : "Vui lòng nhập tên chẩn đoán/bệnh.");
        return;
      }
      onAddCandidate({
        id,
        category: "condition",
        field_name: "condition_name",
        display_name: condName.trim(),
        value: {
          name: condName.trim(),
          clinical_status: condStatus,
          notes: condNotes.trim() || undefined,
        },
        status: "accepted",
        confidence: 1.0,
      });
      resetForms();
    } else if (activeCategory === "allergy") {
      if (!allergySubstance.trim()) {
        setFormError(isEn ? "Please enter allergen substance." : "Vui lòng nhập tên chất gây dị ứng.");
        return;
      }
      onAddCandidate({
        id,
        category: "allergy",
        field_name: "allergy",
        display_name: allergySubstance.trim(),
        value: {
          substance: allergySubstance.trim(),
          reaction: allergyReaction.trim() || undefined,
          severity: allergySeverity,
        },
        status: "accepted",
        confidence: 1.0,
      });
      resetForms();
    }
  };

  const handleParseFreeform = () => {
    setFormError(null);
    if (!freeformText.trim()) {
      setFormError(isEn ? "Please enter text to extract." : "Vui lòng nhập nội dung cần trích xuất.");
      return;
    }
    const extracted = parseFreeformText(freeformText, locale);
    if (extracted.length === 0) {
      setFormError(isEn ? "Could not extract health information." : "Không thể nhận diện được thông tin y tế.");
      return;
    }
    if (onAddMultipleCandidates) {
      onAddMultipleCandidates(extracted);
    } else {
      extracted.forEach((c) => onAddCandidate(c));
    }
    setFreeformText("");
  };

  return (
    <div
      className={`manual-entry-fallback space-y-4 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm ${className}`}
      data-testid="manual-entry-fallback"
    >
      {/* Mode Switcher: Structured Form vs Quick Text */}
      <div className="flex items-center justify-between border-b border-[color:var(--shell-border)] pb-3">
        <div className="flex items-center gap-2">
          <Icon name="edit" size="1.25rem" className="text-[var(--text-brand)]" />
          <h3 className="text-sm sm:text-base font-bold text-[var(--text-primary)]">
            {isEn ? "Manual Entry / Offline Fallback" : "Nhập thủ công / Chế độ ngoại tuyến"}
          </h3>
        </div>

        <div className="flex items-center rounded-[var(--radius-lg)] bg-[var(--surface-muted)] p-1">
          <button
            type="button"
            onClick={() => setMode("form")}
            className={`px-3 py-1 text-xs font-semibold rounded-[var(--radius-md)] transition-colors ${
              mode === "form"
                ? "bg-[var(--surface-panel)] text-[var(--brand-600)] shadow-xs"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
            data-testid="manual-mode-form"
          >
            {isEn ? "Field Form" : "Biểu mẫu"}
          </button>
          <button
            type="button"
            onClick={() => setMode("freeform")}
            className={`px-3 py-1 text-xs font-semibold rounded-[var(--radius-md)] transition-colors ${
              mode === "freeform"
                ? "bg-[var(--surface-panel)] text-[var(--brand-600)] shadow-xs"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
            data-testid="manual-mode-freeform"
          >
            {isEn ? "Free Text" : "Văn bản tự do"}
          </button>
        </div>
      </div>

      {formError ? (
        <div
          className="flex items-center gap-2 rounded-[var(--radius-md)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-2.5 text-xs text-[var(--status-danger-text)]"
          role="alert"
        >
          <Icon name="warning" size="1rem" className="shrink-0" />
          <span>{formError}</span>
        </div>
      ) : null}

      {mode === "freeform" ? (
        /* Free Text Parsing Form */
        <div className="space-y-3">
          <p className="text-xs text-[var(--text-secondary)]">
            {isEn
              ? "Type or paste your health notes (e.g., 'Blood pressure 120/80', 'Paracetamol 500mg 2 pills/day'). We will automatically parse them."
              : "Nhập hoặc dán ghi chú y tế (Ví dụ: 'Huyết áp 120/80', 'Paracetamol 500mg ngày 2 viên'). Hệ thống sẽ tự động tách thành các mục."}
          </p>
          <textarea
            value={freeformText}
            onChange={(e) => setFreeformText(e.target.value)}
            rows={4}
            placeholder={
              isEn
                ? "E.g.:\nHuyết áp 120/80 mmHg\nParacetamol 500mg ngày 2 lần sau ăn\nĐường huyết 5.8 mmol/L"
                : "Ví dụ:\nHuyết áp 120/80 mmHg\nParacetamol 500mg ngày 2 lần sau ăn\nĐường huyết 5.8 mmol/L"
            }
            className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 text-xs sm:text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[color:var(--brand-500)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
            data-testid="freeform-textarea"
          />
          <div className="flex justify-end">
            <Button
              variant="primary"
              size="sm"
              icon="plus"
              onClick={handleParseFreeform}
              data-testid="btn-parse-freeform"
            >
              {isEn ? "Parse and Add Items" : "Tách thông tin và Thêm"}
            </Button>
          </div>
        </div>
      ) : (
        /* Structured Form */
        <form onSubmit={handleAddFormItem} className="space-y-4">
          {/* Category Tabs */}
          <div className="flex flex-wrap items-center gap-1.5 border-b border-[color:var(--shell-border)]/60 pb-2.5">
            {(["medication", "measurement", "condition", "allergy"] as CaptureCategory[]).map(
              (cat) => {
                const meta = CATEGORY_META_MAP[cat];
                const isActive = activeCategory === cat;
                return (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => {
                      setActiveCategory(cat);
                      setFormError(null);
                    }}
                    className={`inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] px-3 py-1 text-xs font-semibold transition-colors ${
                      isActive
                        ? "bg-[var(--brand-600)] text-white shadow-xs"
                        : "bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                    }`}
                    data-testid={`manual-cat-${cat}`}
                  >
                    <Icon name={meta.icon} size="0.9rem" />
                    <span>{isEn ? meta.labelEn : meta.labelVi}</span>
                  </button>
                );
              },
            )}
          </div>

          {/* Medication Form */}
          {activeCategory === "medication" && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3" data-testid="form-medication">
              <div className="space-y-1 sm:col-span-2">
                <label className="text-xs font-semibold text-[var(--text-secondary)]">
                  {isEn ? "Medication Name *" : "Tên thuốc *"}
                </label>
                <input
                  type="text"
                  value={medName}
                  onChange={(e) => setMedName(e.target.value)}
                  placeholder="Ví dụ: Panadol Extra, Amlodipine..."
                  className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-xs sm:text-sm text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
                  data-testid="input-med-name"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-[var(--text-secondary)]">
                  {isEn ? "Dosage / Strength" : "Liều lượng / Hàm lượng"}
                </label>
                <input
                  type="text"
                  value={medDosage}
                  onChange={(e) => setMedDosage(e.target.value)}
                  placeholder="Ví dụ: 500mg, 5mg..."
                  className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-xs sm:text-sm text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
                  data-testid="input-med-dosage"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-[var(--text-secondary)]">
                  {isEn ? "Frequency" : "Tần suất dùng"}
                </label>
                <input
                  type="text"
                  value={medFrequency}
                  onChange={(e) => setMedFrequency(e.target.value)}
                  placeholder="Ví dụ: 2 lần/ngày, 1 viên buổi sáng..."
                  className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-xs sm:text-sm text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
                  data-testid="input-med-frequency"
                />
              </div>
              <div className="space-y-1 sm:col-span-2">
                <label className="text-xs font-semibold text-[var(--text-secondary)]">
                  {isEn ? "Instructions" : "Hướng dẫn dùng"}
                </label>
                <input
                  type="text"
                  value={medInstructions}
                  onChange={(e) => setMedInstructions(e.target.value)}
                  placeholder="Ví dụ: Uống sau bữa ăn..."
                  className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-xs sm:text-sm text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
                  data-testid="input-med-instructions"
                />
              </div>
            </div>
          )}

          {/* Measurement Form */}
          {activeCategory === "measurement" && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3" data-testid="form-measurement">
              <div className="space-y-1 sm:col-span-2">
                <label className="text-xs font-semibold text-[var(--text-secondary)]">
                  {isEn ? "Measurement Type" : "Loại chỉ số"}
                </label>
                <select
                  value={measType}
                  onChange={(e) => {
                    setMeasType(e.target.value);
                    if (e.target.value === "blood_pressure") setMeasUnit("mmHg");
                    else if (e.target.value === "heart_rate") setMeasUnit("bpm");
                    else if (e.target.value === "blood_glucose") setMeasUnit("mmol/L");
                    else if (e.target.value === "temperature") setMeasUnit("°C");
                    else if (e.target.value === "weight") setMeasUnit("kg");
                    else if (e.target.value === "spo2") setMeasUnit("%");
                  }}
                  className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-xs sm:text-sm text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
                  data-testid="select-meas-type"
                >
                  <option value="blood_pressure">{isEn ? "Blood Pressure (Huyết áp)" : "Huyết áp (mmHg)"}</option>
                  <option value="heart_rate">{isEn ? "Heart Rate (Nhịp tim)" : "Nhịp tim (bpm)"}</option>
                  <option value="blood_glucose">{isEn ? "Blood Glucose (Đường huyết)" : "Đường huyết (mmol/L hoặc mg/dL)"}</option>
                  <option value="spo2">{isEn ? "SpO2 (Độ bão hòa oxy)" : "Độ bão hòa oxy SpO2 (%)"}</option>
                  <option value="temperature">{isEn ? "Body Temperature (Thân nhiệt)" : "Thân nhiệt (°C)"}</option>
                  <option value="weight">{isEn ? "Weight (Cân nặng)" : "Cân nặng (kg)"}</option>
                </select>
              </div>

              {measType === "blood_pressure" ? (
                <>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-[var(--text-secondary)]">
                      {isEn ? "Systolic (Tâm thu)" : "Tâm thu (Systolic)"}
                    </label>
                    <input
                      type="number"
                      value={measSystolic}
                      onChange={(e) => setMeasSystolic(e.target.value)}
                      placeholder="120"
                      className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-xs sm:text-sm text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
                      data-testid="input-systolic"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-[var(--text-secondary)]">
                      {isEn ? "Diastolic (Tâm trương)" : "Tâm trương (Diastolic)"}
                    </label>
                    <input
                      type="number"
                      value={measDiastolic}
                      onChange={(e) => setMeasDiastolic(e.target.value)}
                      placeholder="80"
                      className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-xs sm:text-sm text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
                      data-testid="input-diastolic"
                    />
                  </div>
                </>
              ) : (
                <>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-[var(--text-secondary)]">
                      {isEn ? "Value *" : "Giá trị đo *"}
                    </label>
                    <input
                      type="text"
                      value={measValue}
                      onChange={(e) => setMeasValue(e.target.value)}
                      placeholder="Ví dụ: 75, 6.2, 36.8..."
                      className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-xs sm:text-sm text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
                      data-testid="input-meas-value"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-[var(--text-secondary)]">
                      {isEn ? "Unit" : "Đơn vị"}
                    </label>
                    <input
                      type="text"
                      value={measUnit}
                      onChange={(e) => setMeasUnit(e.target.value)}
                      className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-xs sm:text-sm text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
                      data-testid="input-meas-unit"
                    />
                  </div>
                </>
              )}
            </div>
          )}

          {/* Condition Form */}
          {activeCategory === "condition" && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3" data-testid="form-condition">
              <div className="space-y-1 sm:col-span-2">
                <label className="text-xs font-semibold text-[var(--text-secondary)]">
                  {isEn ? "Condition / Diagnosis Name *" : "Tên bệnh lý / Chẩn đoán *"}
                </label>
                <input
                  type="text"
                  value={condName}
                  onChange={(e) => setCondName(e.target.value)}
                  placeholder="Ví dụ: Tăng huyết áp nguyên phát, Đái tháo đường type 2..."
                  className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-xs sm:text-sm text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
                  data-testid="input-cond-name"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-[var(--text-secondary)]">
                  {isEn ? "Status" : "Tình trạng"}
                </label>
                <select
                  value={condStatus}
                  onChange={(e) => setCondStatus(e.target.value)}
                  className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-xs sm:text-sm text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
                  data-testid="select-cond-status"
                >
                  <option value="active">{isEn ? "Active" : "Đang điều trị (Active)"}</option>
                  <option value="resolved">{isEn ? "Resolved" : "Đã khỏi / Ổn định"}</option>
                  <option value="remission">{isEn ? "Remission" : "Thuyên giảm"}</option>
                </select>
              </div>
              <div className="space-y-1 sm:col-span-2">
                <label className="text-xs font-semibold text-[var(--text-secondary)]">
                  {isEn ? "Notes" : "Ghi chú thêm"}
                </label>
                <input
                  type="text"
                  value={condNotes}
                  onChange={(e) => setCondNotes(e.target.value)}
                  placeholder="Bác sĩ chẩn đoán tại BV..."
                  className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-xs sm:text-sm text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
                  data-testid="input-cond-notes"
                />
              </div>
            </div>
          )}

          {/* Allergy Form */}
          {activeCategory === "allergy" && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3" data-testid="form-allergy">
              <div className="space-y-1 sm:col-span-2">
                <label className="text-xs font-semibold text-[var(--text-secondary)]">
                  {isEn ? "Allergen / Substance *" : "Chất / Dị nguyên gây dị ứng *"}
                </label>
                <input
                  type="text"
                  value={allergySubstance}
                  onChange={(e) => setAllergySubstance(e.target.value)}
                  placeholder="Ví dụ: Penicillin, Đậu phộng, Hải sản..."
                  className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-xs sm:text-sm text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
                  data-testid="input-allergy-substance"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-[var(--text-secondary)]">
                  {isEn ? "Reaction" : "Biểu hiện phản ứng"}
                </label>
                <input
                  type="text"
                  value={allergyReaction}
                  onChange={(e) => setAllergyReaction(e.target.value)}
                  placeholder="Ví dụ: Nổi mề đay, khó thở..."
                  className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-xs sm:text-sm text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
                  data-testid="input-allergy-reaction"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-[var(--text-secondary)]">
                  {isEn ? "Severity" : "Mức độ"}
                </label>
                <select
                  value={allergySeverity}
                  onChange={(e) => setAllergySeverity(e.target.value)}
                  className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-xs sm:text-sm text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
                  data-testid="select-allergy-severity"
                >
                  <option value="mild">{isEn ? "Mild (Nhẹ)" : "Nhẹ"}</option>
                  <option value="moderate">{isEn ? "Moderate (Trung bình)" : "Trung bình"}</option>
                  <option value="severe">{isEn ? "Severe (Nghiêm trọng)" : "Nghiêm trọng"}</option>
                </select>
              </div>
            </div>
          )}

          <div className="flex justify-end pt-2">
            <Button
              type="submit"
              variant="primary"
              size="sm"
              icon="plus"
              data-testid="btn-add-manual-item"
            >
              {isEn ? "Add to Review List" : "Thêm vào danh sách duyệt"}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}

export default ManualEntryFallback;
