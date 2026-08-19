"use client";

import { useState } from "react";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { Field, Select, Textarea } from "@/components/ui/field";
import { InlineError } from "@/components/shared/inline-error";
import {
  apiV2AddMeasurement,
  type HealthMeasurementDto,
} from "@/lib/api/v2-client";

export interface MeasurementEditorModalProps {
  open: boolean;
  onClose: () => void;
  defaultType?: string;
  onSuccess?: () => void;
  locale?: "vi" | "en";
}

const MEASUREMENT_TYPES = [
  { key: "blood_pressure", labelVi: "Huyết áp (Huyết áp tâm thu / tâm trương)", labelEn: "Blood Pressure", defaultUnit: "mmHg" },
  { key: "heart_rate", labelVi: "Nhịp tim", labelEn: "Heart Rate", defaultUnit: "bpm" },
  { key: "blood_glucose", labelVi: "Đường huyết", labelEn: "Blood Glucose", defaultUnit: "mmol/L" },
  { key: "spo2", labelVi: "Độ bão hòa oxy trong máu (SpO2)", labelEn: "SpO2 (Blood Oxygen)", defaultUnit: "%" },
  { key: "weight", labelVi: "Cân nặng", labelEn: "Weight", defaultUnit: "kg" },
  { key: "height", labelVi: "Chiều cao", labelEn: "Height", defaultUnit: "cm" },
  { key: "temperature", labelVi: "Thân nhiệt", labelEn: "Body Temperature", defaultUnit: "°C" },
];

export function MeasurementEditorModal({
  open,
  onClose,
  defaultType = "blood_pressure",
  onSuccess,
  locale = "vi",
}: MeasurementEditorModalProps) {
  const isEn = locale === "en";

  const [type, setType] = useState(defaultType);
  const [systolic, setSystolic] = useState("");
  const [diastolic, setDiastolic] = useState("");
  const [singleValue, setSingleValue] = useState("");
  const [unit, setUnit] = useState(
    MEASUREMENT_TYPES.find((m) => m.key === defaultType)?.defaultUnit ?? "mmHg",
  );
  const [recordedAt, setRecordedAt] = useState(
    () => new Date().toISOString().slice(0, 16),
  );
  const [sourceKind, setSourceKind] = useState("patient");
  const [notes, setNotes] = useState("");

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleTypeChange = (newType: string) => {
    setType(newType);
    const matched = MEASUREMENT_TYPES.find((m) => m.key === newType);
    if (matched) setUnit(matched.defaultUnit);
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setErrorMessage(null);

    let finalValue: string | number = "";
    let finalSystolic: number | undefined = undefined;
    let finalDiastolic: number | undefined = undefined;

    if (type === "blood_pressure") {
      const sysNum = Number(systolic);
      const diaNum = Number(diastolic);
      if (!systolic || !diastolic || isNaN(sysNum) || isNaN(diaNum)) {
        setIsSubmitting(false);
        setErrorMessage(
          isEn
            ? "Please enter valid systolic and diastolic values"
            : "Vui lòng nhập đầy đủ chỉ số huyết áp tâm thu và tâm trương",
        );
        return;
      }
      finalSystolic = sysNum;
      finalDiastolic = diaNum;
      finalValue = `${sysNum}/${diaNum}`;
    } else {
      if (!singleValue.trim()) {
        setIsSubmitting(false);
        setErrorMessage(
          isEn ? "Please enter a measurement value" : "Vui lòng nhập giá trị đo",
        );
        return;
      }
      finalValue = singleValue.trim();
    }

    try {
      const payload: Omit<HealthMeasurementDto, "id"> = {
        type,
        value: finalValue,
        unit,
        systolic: finalSystolic,
        diastolic: finalDiastolic,
        recorded_at: recordedAt ? new Date(recordedAt).toISOString() : new Date().toISOString(),
        source_kind: sourceKind,
        verification_state: sourceKind === "device" ? "device" : sourceKind === "clinician" ? "confirmed" : "user-reported",
        notes: notes.trim() || undefined,
      };

      await apiV2AddMeasurement(payload);
      setIsSubmitting(false);
      if (onSuccess) onSuccess();
      onClose();
    } catch (err) {
      setIsSubmitting(false);
      setErrorMessage(
        err instanceof Error ? err.message : isEn ? "Failed to save measurement" : "Không thể lưu chỉ số",
      );
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEn ? "Record Measurement / Vital Signs" : "Ghi nhận chỉ số sức khỏe & Sinh hiệu"}
      description={
        isEn
          ? "Add a single vital sign or device reading. Track historical trends over time."
          : "Ghi nhận chỉ số đo tại nhà hoặc từ thiết bị để theo dõi biểu đồ tiến triển."
      }
      size="md"
      closeLabel={isEn ? "Close" : "Đóng"}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={isSubmitting}>
            {isEn ? "Cancel" : "Hủy"}
          </Button>
          <Button
            variant="primary"
            onClick={() => void handleSubmit()}
            loading={isSubmitting}
            icon="scan"
          >
            {isEn ? "Save Measurement" : "Lưu chỉ số"}
          </Button>
        </>
      }
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void handleSubmit();
        }}
        className="space-y-4"
        data-testid="measurement-editor-form"
      >
        {errorMessage && (
          <InlineError
            severity="error"
            title={isEn ? "Save Failed" : "Lưu thất bại"}
            message={errorMessage}
            onRetry={() => void handleSubmit()}
          />
        )}

        <Select
          label={isEn ? "Measurement Type *" : "Loại chỉ số *"}
          value={type}
          onChange={(e) => handleTypeChange(e.target.value)}
          data-testid="field-measurement-type"
        >
          {MEASUREMENT_TYPES.map((m) => (
            <option key={m.key} value={m.key}>
              {isEn ? m.labelEn : m.labelVi}
            </option>
          ))}
        </Select>

        {type === "blood_pressure" ? (
          <div className="grid grid-cols-2 gap-3">
            <Field
              type="number"
              label={isEn ? "Systolic (Tâm thu) *" : "Tâm thu (Systolic) *"}
              value={systolic}
              onChange={(e) => setSystolic(e.target.value)}
              placeholder="120"
              hint="mmHg"
              required
              data-testid="field-measurement-systolic"
            />
            <Field
              type="number"
              label={isEn ? "Diastolic (Tâm trương) *" : "Tâm trương (Diastolic) *"}
              value={diastolic}
              onChange={(e) => setDiastolic(e.target.value)}
              placeholder="80"
              hint="mmHg"
              required
              data-testid="field-measurement-diastolic"
            />
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <Field
                type="text"
                label={isEn ? "Measured Value *" : "Giá trị đo *"}
                value={singleValue}
                onChange={(e) => setSingleValue(e.target.value)}
                placeholder="Ví dụ: 5.6"
                required
                data-testid="field-measurement-value"
              />
            </div>
            <Field
              label={isEn ? "Unit" : "Đơn vị"}
              value={unit}
              onChange={(e) => setUnit(e.target.value)}
              data-testid="field-measurement-unit"
            />
          </div>
        )}

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field
            type="datetime-local"
            label={isEn ? "Recorded Date & Time" : "Thời điểm đo"}
            value={recordedAt}
            onChange={(e) => setRecordedAt(e.target.value)}
            data-testid="field-measurement-recorded-at"
          />

          <Select
            label={isEn ? "Measurement Source" : "Nguồn ghi nhận"}
            value={sourceKind}
            onChange={(e) => setSourceKind(e.target.value)}
            data-testid="field-measurement-source"
          >
            <option value="patient">{isEn ? "Self-measured (Patient)" : "Tự đo tại nhà"}</option>
            <option value="device">{isEn ? "Connected Medical Device" : "Thiết bị y tế kết nối"}</option>
            <option value="clinician">{isEn ? "Hospital / Clinician" : "Nhân viên y tế đo"}</option>
          </Select>
        </div>

        <Textarea
          label={isEn ? "Context / Notes" : "Bối cảnh đo / Ghi chú"}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder={isEn ? "e.g. Measured in morning before breakfast..." : "Ví dụ: Đo lúc sáng sớm khi vừa thức dậy..."}
          data-testid="field-measurement-notes"
        />
      </form>
    </Modal>
  );
}

export default MeasurementEditorModal;
