"use client";

import { useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import {
  getPhrRecord,
  type PhrAllergyItem,
  type PhrConditionItem,
  type PhrMedicationItem,
  type PhrRecord,
  updatePhrRecord,
} from "@/lib/phr";
import { getStoredUILanguage, onUILanguageChange, type UILanguage } from "@/lib/ui-language";

const COPY = {
  vi: {
    title: "Hồ sơ sức khỏe cá nhân",
    description: "Không gian quản lý hồ sơ sức khỏe cá nhân.",
    save: "Lưu hồ sơ",
    saving: "Đang lưu...",
    loading: "Đang tải hồ sơ...",
    loadError: "Chưa thể tải hồ sơ sức khỏe. Vui lòng thử lại sau.",
    saveOk: "Đã lưu hồ sơ PHR thành công.",
    saveError: "Lưu hồ sơ thất bại.",
    profile: "Thông tin hồ sơ",
    allergies: "Dị ứng",
    conditions: "Bệnh nền",
    medications: "Thuốc đang dùng",
    add: "Thêm",
    remove: "Xóa",
    fullName: "Họ và tên",
    dob: "Ngày sinh",
    gender: "Giới tính",
    bloodType: "Nhóm máu",
    height: "Chiều cao (cm)",
    weight: "Cân nặng (kg)",
    phone: "Số điện thoại",
    address: "Địa chỉ",
    emergencyName: "Người liên hệ khẩn cấp",
    emergencyPhone: "SĐT khẩn cấp",
    insurance: "Mã BHYT/Bảo hiểm",
    notes: "Ghi chú tổng quan",
    allergyName: "Tác nhân",
    reaction: "Phản ứng",
    severity: "Mức độ",
    conditionName: "Tên bệnh",
    status: "Trạng thái",
    diagnosedOn: "Ngày chẩn đoán",
    medicationName: "Tên thuốc",
    dose: "Liều dùng",
    frequency: "Tần suất",
    startedOn: "Bắt đầu từ",
    current: "Đang dùng",
    itemNote: "Ghi chú",
    updatedAt: "Cập nhật lần cuối",
    unknown: "Chưa rõ",
  },
  en: {
    title: "Personal Health Record",
    description: "Personal health record management workspace.",
    save: "Save record",
    saving: "Saving...",
    loading: "Loading PHR record...",
    loadError: "Unable to load your health record. Please try again later.",
    saveOk: "PHR record saved.",
    saveError: "Failed to save PHR record.",
    profile: "Profile",
    allergies: "Allergies",
    conditions: "Conditions",
    medications: "Medications",
    add: "Add",
    remove: "Remove",
    fullName: "Full name",
    dob: "Date of birth",
    gender: "Gender",
    bloodType: "Blood type",
    height: "Height (cm)",
    weight: "Weight (kg)",
    phone: "Phone",
    address: "Address",
    emergencyName: "Emergency contact",
    emergencyPhone: "Emergency phone",
    insurance: "Insurance ID",
    notes: "Clinical notes",
    allergyName: "Allergen",
    reaction: "Reaction",
    severity: "Severity",
    conditionName: "Condition",
    status: "Status",
    diagnosedOn: "Diagnosed on",
    medicationName: "Medication",
    dose: "Dose",
    frequency: "Frequency",
    startedOn: "Started on",
    current: "Current",
    itemNote: "Note",
    updatedAt: "Last updated",
    unknown: "Unknown",
  },
} as const;

const EMPTY_RECORD: PhrRecord = {
  full_name: "",
  date_of_birth: null,
  gender: "",
  blood_type: "",
  height_cm: null,
  weight_kg: null,
  phone: "",
  address: "",
  emergency_contact_name: "",
  emergency_contact_phone: "",
  insurance_id: "",
  notes: "",
  allergies: [],
  conditions: [],
  medications: [],
  created_at: null,
  updated_at: null,
};

function makeId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `phr_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

function toInputDate(value?: string | null): string {
  if (!value) return "";
  return String(value).slice(0, 10);
}

function parseInputNumber(value: string): number | null {
  const normalized = value.trim();
  if (!normalized) return null;
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

function normalizeRecord(record: PhrRecord): PhrRecord {
  const normalizedAllergies = (record.allergies ?? []).map((item) => ({
    id: item.id || makeId(),
    name: item.name ?? "",
    reaction: item.reaction ?? "",
    severity: item.severity ?? "unknown",
    note: item.note ?? "",
  }));
  const normalizedConditions = (record.conditions ?? []).map((item) => ({
    id: item.id || makeId(),
    name: item.name ?? "",
    status: item.status ?? "unknown",
    diagnosed_on: item.diagnosed_on ?? null,
    note: item.note ?? "",
  }));
  const normalizedMeds = (record.medications ?? []).map((item) => ({
    id: item.id || makeId(),
    name: item.name ?? "",
    dose: item.dose ?? "",
    frequency: item.frequency ?? "",
    started_on: item.started_on ?? null,
    is_current: item.is_current ?? true,
    note: item.note ?? "",
  }));
  return {
    ...EMPTY_RECORD,
    ...record,
    allergies: normalizedAllergies,
    conditions: normalizedConditions,
    medications: normalizedMeds,
  };
}

function InputLabel({ children }: { children: string }) {
  return <span className="text-xs font-bold uppercase tracking-[0.08em] text-[#374151] dark:text-slate-200">{children}</span>;
}

const phrPanelClass =
  "rounded-2xl border border-[#B6D4FE] bg-white p-5 shadow-sm dark:border-sky-700/60 dark:bg-slate-900/90 sm:p-6";
const phrColumnClass =
  "rounded-2xl border border-[#B6D4FE] bg-white p-4 shadow-sm dark:border-sky-700/60 dark:bg-slate-900/90";
const phrItemClass =
  "rounded-2xl border border-[#93C5FD] bg-[#EEF6FF] p-3 shadow-sm dark:border-sky-700/70 dark:bg-slate-800/90";
const addButtonClass =
  "inline-flex min-h-9 items-center rounded-full border border-[#93C5FD] bg-[#EFF6FF] px-3 text-sm font-bold text-[#1D4ED8] transition hover:bg-[#DBEAFE] hover:text-[#1E40AF] focus-visible:ring-4 focus-visible:ring-blue-100 dark:border-sky-500/70 dark:bg-sky-500/18 dark:text-sky-100 dark:hover:bg-sky-500/28";
const removeButtonClass =
  "justify-self-start rounded-full border border-rose-300 bg-rose-50 px-3 py-1.5 text-sm font-bold text-rose-700 transition hover:bg-rose-100 dark:border-rose-500/70 dark:bg-rose-500/15 dark:text-rose-100";

export default function PhrPage() {
  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");
  const [record, setRecord] = useState<PhrRecord>(EMPTY_RECORD);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string>("");
  const [error, setError] = useState<string>("");

  const text = useMemo(() => COPY[uiLanguage], [uiLanguage]);

  useEffect(() => {
    setUiLanguage(getStoredUILanguage());
    return onUILanguageChange(setUiLanguage);
  }, []);

  useEffect(() => {
    let mounted = true;
    async function run() {
      setLoading(true);
      setError("");
      try {
        const data = await getPhrRecord();
        if (!mounted) return;
        setRecord(normalizeRecord(data));
      } catch {
        if (!mounted) return;
        setError(text.loadError);
      } finally {
        if (mounted) setLoading(false);
      }
    }
    run();
    return () => {
      mounted = false;
    };
  }, [text.loadError]);

  const setField = <K extends keyof PhrRecord>(key: K, value: PhrRecord[K]) => {
    setRecord((prev) => ({ ...prev, [key]: value }));
  };

  const updateAllergy = (id: string, patch: Partial<PhrAllergyItem>) => {
    setRecord((prev) => ({
      ...prev,
      allergies: prev.allergies.map((item) => (item.id === id ? { ...item, ...patch } : item)),
    }));
  };

  const updateCondition = (id: string, patch: Partial<PhrConditionItem>) => {
    setRecord((prev) => ({
      ...prev,
      conditions: prev.conditions.map((item) => (item.id === id ? { ...item, ...patch } : item)),
    }));
  };

  const updateMedication = (id: string, patch: Partial<PhrMedicationItem>) => {
    setRecord((prev) => ({
      ...prev,
      medications: prev.medications.map((item) => (item.id === id ? { ...item, ...patch } : item)),
    }));
  };

  const addAllergy = () => {
    setRecord((prev) => ({
      ...prev,
      allergies: [
        ...prev.allergies,
        { id: makeId(), name: "", reaction: "", severity: "unknown", note: "" },
      ],
    }));
  };

  const addCondition = () => {
    setRecord((prev) => ({
      ...prev,
      conditions: [
        ...prev.conditions,
        { id: makeId(), name: "", status: "unknown", diagnosed_on: null, note: "" },
      ],
    }));
  };

  const addMedication = () => {
    setRecord((prev) => ({
      ...prev,
      medications: [
        ...prev.medications,
        { id: makeId(), name: "", dose: "", frequency: "", started_on: null, is_current: true, note: "" },
      ],
    }));
  };

  const onSave = async () => {
    setSaving(true);
    setMessage("");
    setError("");
    try {
      const payload: PhrRecord = {
        ...record,
        full_name: record.full_name.trim(),
        gender: record.gender.trim(),
        blood_type: record.blood_type.trim().toUpperCase(),
        phone: record.phone.trim(),
        address: record.address.trim(),
        emergency_contact_name: record.emergency_contact_name.trim(),
        emergency_contact_phone: record.emergency_contact_phone.trim(),
        insurance_id: record.insurance_id.trim(),
        notes: record.notes.trim(),
      };
      const saved = await updatePhrRecord(payload);
      setRecord(normalizeRecord(saved));
      setMessage(text.saveOk);
    } catch (err) {
      setError(err instanceof Error ? err.message : text.saveError);
    } finally {
      setSaving(false);
    }
  };

  return (
    <PageShell variant="plain" title={text.title} description={text.description}>
      <div className="space-y-5">
        <section className={phrPanelClass}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="text-xs text-[var(--text-secondary)]">
              {text.updatedAt}: {record.updated_at ? new Date(record.updated_at).toLocaleString() : text.unknown}
            </div>
            <button
              type="button"
              onClick={onSave}
              disabled={loading || saving}
              className="inline-flex min-h-[38px] items-center rounded-lg border border-cyan-300/65 bg-gradient-to-r from-sky-600 to-cyan-500 px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? text.saving : text.save}
            </button>
          </div>
          {loading ? <p className="mt-3 text-sm text-[var(--text-secondary)]">{text.loading}</p> : null}
          {message ? <p className="mt-3 text-sm text-emerald-300">{message}</p> : null}
          {error ? <p className="mt-3 text-sm text-rose-300">{error}</p> : null}
        </section>

        <section className={phrPanelClass}>
          <p className="mb-4 text-sm font-semibold text-[var(--text-primary)]">{text.profile}</p>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="flex flex-col gap-1.5">
              <InputLabel>{text.fullName}</InputLabel>
              <input className="input" value={record.full_name} onChange={(e) => setField("full_name", e.target.value)} />
            </label>
            <label className="flex flex-col gap-1.5">
              <InputLabel>{text.dob}</InputLabel>
              <input
                type="date"
                className="input"
                value={toInputDate(record.date_of_birth)}
                onChange={(e) => setField("date_of_birth", e.target.value || null)}
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <InputLabel>{text.gender}</InputLabel>
              <input className="input" value={record.gender} onChange={(e) => setField("gender", e.target.value)} />
            </label>
            <label className="flex flex-col gap-1.5">
              <InputLabel>{text.bloodType}</InputLabel>
              <input className="input" value={record.blood_type} onChange={(e) => setField("blood_type", e.target.value)} />
            </label>
            <label className="flex flex-col gap-1.5">
              <InputLabel>{text.height}</InputLabel>
              <input
                inputMode="decimal"
                className="input"
                value={record.height_cm ?? ""}
                onChange={(e) => setField("height_cm", parseInputNumber(e.target.value))}
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <InputLabel>{text.weight}</InputLabel>
              <input
                inputMode="decimal"
                className="input"
                value={record.weight_kg ?? ""}
                onChange={(e) => setField("weight_kg", parseInputNumber(e.target.value))}
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <InputLabel>{text.phone}</InputLabel>
              <input className="input" value={record.phone} onChange={(e) => setField("phone", e.target.value)} />
            </label>
            <label className="flex flex-col gap-1.5">
              <InputLabel>{text.insurance}</InputLabel>
              <input className="input" value={record.insurance_id} onChange={(e) => setField("insurance_id", e.target.value)} />
            </label>
            <label className="flex flex-col gap-1.5">
              <InputLabel>{text.emergencyName}</InputLabel>
              <input
                className="input"
                value={record.emergency_contact_name}
                onChange={(e) => setField("emergency_contact_name", e.target.value)}
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <InputLabel>{text.emergencyPhone}</InputLabel>
              <input
                className="input"
                value={record.emergency_contact_phone}
                onChange={(e) => setField("emergency_contact_phone", e.target.value)}
              />
            </label>
            <label className="flex flex-col gap-1.5 md:col-span-2">
              <InputLabel>{text.address}</InputLabel>
              <input className="input" value={record.address} onChange={(e) => setField("address", e.target.value)} />
            </label>
            <label className="flex flex-col gap-1.5 md:col-span-2">
              <InputLabel>{text.notes}</InputLabel>
              <textarea
                className="input min-h-[84px] resize-y py-2.5"
                value={record.notes}
                onChange={(e) => setField("notes", e.target.value)}
              />
            </label>
          </div>
        </section>

        <section className="grid gap-4 xl:grid-cols-3">
          <article className={phrColumnClass}>
            <div className="mb-3 flex items-center justify-between gap-3">
              <p className="text-base font-bold text-[#1F2937] dark:text-slate-100">{text.allergies}</p>
              <button type="button" onClick={addAllergy} className={addButtonClass}>
                + {text.add}
              </button>
            </div>
            <div className="space-y-3">
              {record.allergies.map((item) => (
                <div key={item.id} className={phrItemClass}>
                  <div className="grid gap-2">
                    <input className="input" placeholder={text.allergyName} value={item.name} onChange={(e) => updateAllergy(item.id, { name: e.target.value })} />
                    <input className="input" placeholder={text.reaction} value={item.reaction} onChange={(e) => updateAllergy(item.id, { reaction: e.target.value })} />
                    <input className="input" placeholder={text.severity} value={item.severity} onChange={(e) => updateAllergy(item.id, { severity: (e.target.value || "unknown") as PhrAllergyItem["severity"] })} />
                    <textarea className="input min-h-[56px] resize-y py-2.5" placeholder={text.itemNote} value={item.note} onChange={(e) => updateAllergy(item.id, { note: e.target.value })} />
                    <button type="button" onClick={() => setRecord((prev) => ({ ...prev, allergies: prev.allergies.filter((row) => row.id !== item.id) }))} className={removeButtonClass}>
                      {text.remove}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </article>

          <article className={phrColumnClass}>
            <div className="mb-3 flex items-center justify-between gap-3">
              <p className="text-base font-bold text-[#1F2937] dark:text-slate-100">{text.conditions}</p>
              <button type="button" onClick={addCondition} className={addButtonClass}>
                + {text.add}
              </button>
            </div>
            <div className="space-y-3">
              {record.conditions.map((item) => (
                <div key={item.id} className={phrItemClass}>
                  <div className="grid gap-2">
                    <input className="input" placeholder={text.conditionName} value={item.name} onChange={(e) => updateCondition(item.id, { name: e.target.value })} />
                    <input className="input" placeholder={text.status} value={item.status} onChange={(e) => updateCondition(item.id, { status: (e.target.value || "unknown") as PhrConditionItem["status"] })} />
                    <input type="date" className="input" placeholder={text.diagnosedOn} value={toInputDate(item.diagnosed_on)} onChange={(e) => updateCondition(item.id, { diagnosed_on: e.target.value || null })} />
                    <textarea className="input min-h-[56px] resize-y py-2.5" placeholder={text.itemNote} value={item.note} onChange={(e) => updateCondition(item.id, { note: e.target.value })} />
                    <button type="button" onClick={() => setRecord((prev) => ({ ...prev, conditions: prev.conditions.filter((row) => row.id !== item.id) }))} className={removeButtonClass}>
                      {text.remove}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </article>

          <article className={phrColumnClass}>
            <div className="mb-3 flex items-center justify-between gap-3">
              <p className="text-base font-bold text-[#1F2937] dark:text-slate-100">{text.medications}</p>
              <button type="button" onClick={addMedication} className={addButtonClass}>
                + {text.add}
              </button>
            </div>
            <div className="space-y-3">
              {record.medications.map((item) => (
                <div key={item.id} className={phrItemClass}>
                  <div className="grid gap-2">
                    <input className="input" placeholder={text.medicationName} value={item.name} onChange={(e) => updateMedication(item.id, { name: e.target.value })} />
                    <input className="input" placeholder={text.dose} value={item.dose} onChange={(e) => updateMedication(item.id, { dose: e.target.value })} />
                    <input className="input" placeholder={text.frequency} value={item.frequency} onChange={(e) => updateMedication(item.id, { frequency: e.target.value })} />
                    <input type="date" className="input" placeholder={text.startedOn} value={toInputDate(item.started_on)} onChange={(e) => updateMedication(item.id, { started_on: e.target.value || null })} />
                    <label className="inline-flex min-h-9 items-center gap-2 text-sm font-semibold text-[#374151] dark:text-slate-200">
                      <input type="checkbox" checked={item.is_current} onChange={(e) => updateMedication(item.id, { is_current: e.target.checked })} />
                      {text.current}
                    </label>
                    <textarea className="input min-h-[56px] resize-y py-2.5" placeholder={text.itemNote} value={item.note} onChange={(e) => updateMedication(item.id, { note: e.target.value })} />
                    <button type="button" onClick={() => setRecord((prev) => ({ ...prev, medications: prev.medications.filter((row) => row.id !== item.id) }))} className={removeButtonClass}>
                      {text.remove}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </article>
        </section>
      </div>
    </PageShell>
  );
}
