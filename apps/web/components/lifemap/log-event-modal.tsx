"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Field, Select, Textarea } from "@/components/ui/field";
import { Modal } from "@/components/ui/modal";

export type LogEventCategory =
  | "symptom"
  | "vitals"
  | "medication"
  | "visit"
  | "lab"
  | "lifestyle"
  | "note";

export interface LogEventFormData {
  category: LogEventCategory;
  title: string;
  description: string;
  occurredAt: string;
  metrics?: Record<string, string | number>;
  episodeId?: string;
}

export interface LogEventModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: LogEventFormData) => Promise<void> | void;
  initialDate?: string;
  episodes?: Array<{ id: string; title: string }>;
  initialEpisodeId?: string;
  initialCategory?: LogEventCategory;
}

export function LogEventModal({
  open,
  onClose,
  onSubmit,
  initialDate,
  episodes = [],
  initialEpisodeId,
  initialCategory = "symptom",
}: LogEventModalProps) {
  const [category, setCategory] = useState<LogEventCategory>(initialCategory);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [occurredAt, setOccurredAt] = useState(() => {
    if (initialDate) return initialDate.includes("T") ? initialDate.slice(0, 16) : `${initialDate}T08:00`;
    const now = new Date();
    return new Date(now.getTime() - now.getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 16);
  });
  const [episodeId, setEpisodeId] = useState(initialEpisodeId ?? episodes[0]?.id ?? "");

  // Metric fields
  const [systolic, setSystolic] = useState("");
  const [diastolic, setDiastolic] = useState("");
  const [heartRate, setHeartRate] = useState("");
  const [dosage, setDosage] = useState("");
  const [severity, setSeverity] = useState("3");

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError("Vui lòng nhập tiêu đề sự kiện.");
      return;
    }

    const metrics: Record<string, string | number> = {};
    if (category === "vitals") {
      if (systolic && diastolic) {
        metrics["Huyết áp"] = `${systolic}/${diastolic} mmHg`;
      }
      if (heartRate) {
        metrics["Nhịp tim"] = `${heartRate} bpm`;
      }
    } else if (category === "medication" && dosage.trim()) {
      metrics["Liều dùng"] = dosage.trim();
    } else if (category === "symptom") {
      metrics["Mức độ"] = `${severity}/10`;
    }

    setSaving(true);
    setError("");

    try {
      await onSubmit({
        category,
        title: title.trim(),
        description: description.trim(),
        occurredAt: new Date(occurredAt).toISOString(),
        metrics: Object.keys(metrics).length > 0 ? metrics : undefined,
        episodeId: episodeId || undefined,
      });
      // Reset form
      setTitle("");
      setDescription("");
      setSystolic("");
      setDiastolic("");
      setHeartRate("");
      setDosage("");
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể lưu sự kiện.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Ghi nhận sự kiện sức khỏe mới"
      description="Lưu nhanh triệu chứng, chỉ số đo, liều thuốc hoặc nhật ký thăm khám vào LifeMap."
    >
      <form onSubmit={handleSubmit} className="space-y-4" data-testid="log-event-form">
        {error && (
          <div className="rounded-lg bg-red-50 p-3 text-xs font-semibold text-red-700 border border-red-200" role="alert">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Select
            id="event-category-select"
            label="Loại sự kiện"
            value={category}
            onChange={(e) => setCategory(e.target.value as LogEventCategory)}
          >
            <option value="symptom">Triệu chứng & Cảm giác</option>
            <option value="vitals">Chỉ số sinh tồn (Huyết áp/Nhịp tim)</option>
            <option value="medication">Dùng thuốc / Uống thuốc</option>
            <option value="visit">Thăm khám bác sĩ</option>
            <option value="lab">Kết quả xét nghiệm</option>
            <option value="lifestyle">Vận động & Sinh hoạt</option>
            <option value="note">Ghi chú theo dõi</option>
          </Select>

          {episodes.length > 0 && (
            <Select
              id="event-episode-select"
              label="Thuộc hành trình"
              value={episodeId}
              onChange={(e) => setEpisodeId(e.target.value)}
            >
              <option value="">(Không gán hành trình)</option>
              {episodes.map((ep) => (
                <option key={ep.id} value={ep.id}>
                  {ep.title}
                </option>
              ))}
            </Select>
          )}
        </div>

        <Field
          id="event-title-input"
          label="Tiêu đề sự kiện"
          value={title}
          onChange={(e) => {
            setTitle(e.target.value);
            if (error) setError("");
          }}
          placeholder="Ví dụ: Đo huyết áp sáng, Đau đầu sau khi làm việc..."
          required
          autoFocus
        />

        <Field
          id="event-occurred-at-input"
          label="Thời điểm diễn ra (Valid Time)"
          type="datetime-local"
          value={occurredAt}
          onChange={(e) => setOccurredAt(e.target.value)}
          required
        />

        {/* Dynamic Metric Fields */}
        {category === "vitals" && (
          <div className="grid grid-cols-3 gap-2 p-3 bg-[var(--surface-muted)] rounded-xl border border-[var(--shell-border)]">
            <Field
              id="vitals-systolic"
              label="Tâm thu (mmHg)"
              type="number"
              value={systolic}
              onChange={(e) => setSystolic(e.target.value)}
              placeholder="120"
            />
            <Field
              id="vitals-diastolic"
              label="Tâm trương (mmHg)"
              type="number"
              value={diastolic}
              onChange={(e) => setDiastolic(e.target.value)}
              placeholder="80"
            />
            <Field
              id="vitals-heartrate"
              label="Nhịp tim (bpm)"
              type="number"
              value={heartRate}
              onChange={(e) => setHeartRate(e.target.value)}
              placeholder="72"
            />
          </div>
        )}

        {category === "medication" && (
          <Field
            id="med-dosage-input"
            label="Liều dùng & Hướng dẫn"
            value={dosage}
            onChange={(e) => setDosage(e.target.value)}
            placeholder="Ví dụ: 1 viên 5mg sau ăn sáng"
          />
        )}

        {category === "symptom" && (
          <div className="p-3 bg-[var(--surface-muted)] rounded-xl border border-[var(--shell-border)] space-y-1">
            <label className="text-xs font-semibold text-[var(--text-secondary)] block">
              Mức độ khó chịu: {severity}/10
            </label>
            <input
              id="symptom-severity-slider"
              type="range"
              min="1"
              max="10"
              value={severity}
              onChange={(e) => setSeverity(e.target.value)}
              className="w-full accent-[var(--brand-primary)]"
            />
            <div className="flex justify-between text-[10px] text-[var(--text-muted)]">
              <span>1 (Rất nhẹ)</span>
              <span>5 (Vừa phải)</span>
              <span>10 (Rất nghiêm trọng)</span>
            </div>
          </div>
        )}

        <Textarea
          id="event-desc-input"
          label="Mô tả chi tiết hoặc hoàn cảnh"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Mô tả thêm các yếu tố đi kèm, cảm giác của bạn..."
          rows={3}
        />

        <div className="flex justify-end gap-2 pt-3 border-t border-[var(--shell-border)]">
          <Button type="button" variant="secondary" onClick={onClose} disabled={saving}>
            Hủy
          </Button>
          <Button type="submit" variant="primary" loading={saving}>
            {saving ? "Đang lưu..." : "Lưu vào LifeMap"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export default LogEventModal;
