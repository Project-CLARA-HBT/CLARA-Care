"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import PageShell from "@/components/ui/page-shell";
import Button from "@/components/ui/button";
import { Field, Textarea } from "@/components/ui/field";
import { Badge } from "@/components/ui/badge";
import AsyncSection, {
  selectAsyncState,
  type AsyncState,
} from "@/components/ui/async-section";
import {
  DEFAULT_PHR_CAPABILITIES,
  getPhrCapabilities,
  getPhrCompleteness,
  getPhrRecord,
  type PhrAllergyItem,
  type PhrCapabilityFlags,
  type PhrCompleteness,
  type PhrCompletenessClass,
  type PhrConditionItem,
  type PhrMedicationItem,
  type PhrRecord,
  updatePhrRecord,
} from "@/lib/phr";
import {
  getStoredUILanguage,
  onUILanguageChange,
  type UILanguage,
} from "@/lib/ui-language";
import { formatLocaleDate } from "@/lib/i18n/catalog";
import type { PhrInformationSource, PhrVerificationStatus } from "@/lib/phr";
import OcrReviewModal from "@/components/phr/ocr-review-modal";
import PhrExportButton from "@/components/phr/export-button";
import ShareManager from "@/components/phr/share-manager";
import EmergencyCardEditor from "@/components/phr/emergency-card-editor";
import RemindersPanel from "@/components/phr/reminders-panel";

const COMPLETENESS_CLASS_LABELS: Record<
  PhrCompletenessClass,
  Record<UILanguage, string>
> = {
  patient_demographics: { vi: "Thông tin nhân khẩu", en: "Demographics" },
  allergies: { vi: "Dị ứng", en: "Allergies" },
  medications: { vi: "Thuốc", en: "Medications" },
  problems: { vi: "Bệnh nền", en: "Problems" },
  immunizations: { vi: "Tiêm chủng", en: "Immunizations" },
  procedures: { vi: "Thủ thuật", en: "Procedures" },
  labs: { vi: "Xét nghiệm", en: "Labs" },
};

const SOURCE_LABELS: Record<
  PhrInformationSource,
  Record<UILanguage, string>
> = {
  "self-declared": { vi: "Tự khai báo", en: "Self-declared" },
  ocr: { vi: "Quét OCR", en: "OCR import" },
  imported: { vi: "Nhập có cấu trúc", en: "Imported" },
};

const VERIFICATION_LABELS: Record<
  PhrVerificationStatus,
  Record<UILanguage, string>
> = {
  unconfirmed: { vi: "Chưa xác minh", en: "Unconfirmed" },
  confirmed: { vi: "Đã xác minh", en: "Confirmed" },
  provisional: { vi: "Tạm thời", en: "Provisional" },
  refuted: { vi: "Đã bác bỏ", en: "Refuted" },
  "entered-in-error": { vi: "Nhập sai", en: "Entered in error" },
};

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
    disclaimer:
      "Hồ sơ này do bạn tự khai báo, chỉ dùng để hỗ trợ ra quyết định — không phải hồ sơ bệnh án điện tử (EMR/EHR), không thay thế chẩn đoán của bác sĩ và không có giá trị pháp lý ràng buộc. Hãy luôn tham vấn nhân viên y tế trước khi hành động.",
    source: "Nguồn",
    verification: "Xác minh",
    consentTitle: "Đồng thuận dữ liệu",
    consentBody:
      "Việc dùng PHR để cá nhân hóa và chia sẻ hồ sơ được quản lý tại Trung tâm đồng thuận.",
    consentLink: "Mở Trung tâm đồng thuận",
    completenessTitle: "Mức độ hoàn thiện hồ sơ",
    completenessDescription:
      "Điểm dựa trên các nhóm dữ liệu USCDI có trong hồ sơ. Bổ sung nhóm còn thiếu giúp kiểm tra an toàn thuốc và cá nhân hóa tốt hơn.",
    completenessLoading: "Đang tính mức độ hoàn thiện...",
    completenessError: "Chưa thể tải mức độ hoàn thiện hồ sơ.",
    completenessComplete: "Hồ sơ đã đầy đủ các nhóm dữ liệu chính.",
    completenessPresent: "Đã có",
    completenessMissing: "Còn thiếu",
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
    disclaimer:
      "This record is self-declared and for decision support only — it is not an EMR/EHR, does not replace a clinician's diagnosis, and is not legally binding. Always review with a healthcare professional before acting.",
    source: "Source",
    verification: "Verification",
    consentTitle: "Data consent",
    consentBody:
      "Using your PHR for personalization and sharing is managed in the Consent Center.",
    consentLink: "Open Consent Center",
    completenessTitle: "Record completeness",
    completenessDescription:
      "Score based on the USCDI data classes present in your record. Filling in missing classes improves medication-safety checks and personalization.",
    completenessLoading: "Calculating completeness...",
    completenessError: "Unable to load record completeness.",
    completenessComplete: "Your record covers all core data classes.",
    completenessPresent: "Present",
    completenessMissing: "Missing",
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
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
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
    information_source: item.information_source ?? null,
    verification_status: item.verification_status ?? null,
  }));
  const normalizedConditions = (record.conditions ?? []).map((item) => ({
    id: item.id || makeId(),
    name: item.name ?? "",
    status: item.status ?? "unknown",
    diagnosed_on: item.diagnosed_on ?? null,
    note: item.note ?? "",
    information_source: item.information_source ?? null,
    verification_status: item.verification_status ?? null,
  }));
  const normalizedMeds = (record.medications ?? []).map((item) => ({
    id: item.id || makeId(),
    name: item.name ?? "",
    dose: item.dose ?? "",
    frequency: item.frequency ?? "",
    started_on: item.started_on ?? null,
    is_current: item.is_current ?? true,
    note: item.note ?? "",
    information_source: item.information_source ?? null,
    verification_status: item.verification_status ?? null,
  }));
  return {
    ...EMPTY_RECORD,
    ...record,
    allergies: normalizedAllergies,
    conditions: normalizedConditions,
    medications: normalizedMeds,
  };
}



/**
 * Per-entry provenance + verification chips (personal-health-record Requirement
 * 6.5). Renders nothing when an entry carries no provenance (preserves the
 * legacy display when the PHR feature flag is off and the backend omits these
 * fields — Requirement 18.1).
 */
function ProvenanceBadges({
  source,
  verification,
  uiLanguage,
  sourceLabel,
  verificationLabel,
}: {
  source?: PhrInformationSource | null;
  verification?: PhrVerificationStatus | null;
  uiLanguage: UILanguage;
  sourceLabel: string;
  verificationLabel: string;
}) {
  if (!source && !verification) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {source ? (
        <Badge tone="brand">
          {sourceLabel}: {SOURCE_LABELS[source][uiLanguage]}
        </Badge>
      ) : null}
      {verification ? (
        <Badge tone="neutral">
          {verificationLabel}: {VERIFICATION_LABELS[verification][uiLanguage]}
        </Badge>
      ) : null}
    </div>
  );
}

/**
 * USCDI-aligned completeness meter (personal-health-record Requirement 16.2).
 * Rendered only when the `completeness_meter` capability is effective; the panel
 * shows the deterministic score plus the present/missing data classes via the
 * shared `AsyncSection` loading/empty/error/populated pattern. Class names are
 * localized vi/en; no PHR values are ever read here (Requirement 16.4).
 */
function CompletenessMeter({
  state,
  text,
  uiLanguage,
}: {
  state: AsyncState<PhrCompleteness>;
  text: (typeof COPY)[UILanguage];
  uiLanguage: UILanguage;
}) {
  return (
    <section className={phrPanelClass}>
      <p className="text-sm font-semibold text-[var(--text-primary)]">
        {text.completenessTitle}
      </p>
      <p className="mt-1 text-[13px] leading-6 text-[var(--text-secondary)]">
        {text.completenessDescription}
      </p>
      <div className="mt-4">
        <AsyncSection<PhrCompleteness>
          state={state}
          loadingLabel={text.completenessLoading}
        >
          {(data) => {
            const percent = Math.round(data.score * 100);
            return (
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <div
                    className="h-2.5 flex-1 overflow-hidden rounded-full bg-[var(--surface-muted)]"
                    role="progressbar"
                    aria-valuenow={percent}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={text.completenessTitle}
                  >
                    <div
                      className="h-full rounded-full bg-[var(--brand-500)] transition-[width]"
                      style={{ width: `${percent}%` }}
                    />
                  </div>
                  <span className="text-sm font-bold tabular-nums text-[var(--text-primary)]">
                    {percent}%
                  </span>
                </div>
                {data.present.length > 0 ? (
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-xs font-semibold text-[var(--text-secondary)]">
                      {text.completenessPresent}:
                    </span>
                    {data.present.map((cls) => (
                      <Badge key={cls} tone="ok">
                        {COMPLETENESS_CLASS_LABELS[cls][uiLanguage]}
                      </Badge>
                    ))}
                  </div>
                ) : null}
                {data.missing.length > 0 ? (
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-xs font-semibold text-[var(--text-secondary)]">
                      {text.completenessMissing}:
                    </span>
                    {data.missing.map((cls) => (
                      <Badge key={cls} tone="warn">
                        {COMPLETENESS_CLASS_LABELS[cls][uiLanguage]}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="text-[13px] text-[var(--status-ok-text)]">
                    {text.completenessComplete}
                  </p>
                )}
              </div>
            );
          }}
        </AsyncSection>
      </div>
    </section>
  );
}

const phrPanelClass =
  "rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-[var(--shadow-sm)] sm:p-6";
const phrColumnClass =
  "rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-[var(--shadow-sm)]";
const phrItemClass =
  "rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 shadow-[var(--shadow-sm)]";

type PhrSection =
  | "identity"
  | "body"
  | "contact"
  | "allergies"
  | "conditions"
  | "medications"
  | "status"
  | "ocr"
  | "export"
  | "sharing"
  | "emergency-card"
  | "reminders";

const PHR_SECTIONS = new Set<PhrSection>([
  "identity",
  "body",
  "contact",
  "allergies",
  "conditions",
  "medications",
  "status",
  "ocr",
  "export",
  "sharing",
  "emergency-card",
  "reminders",
]);

function sectionFromPath(pathname: string): PhrSection | null {
  const candidate = pathname.replace(/^\/phr\/?/, "").split("/")[0];
  return PHR_SECTIONS.has(candidate as PhrSection)
    ? (candidate as PhrSection)
    : null;
}

function PhrHub({
  text,
  uiLanguage,
  capabilities,
}: {
  text: (typeof COPY)[UILanguage];
  uiLanguage: UILanguage;
  capabilities: PhrCapabilityFlags;
}) {
  const detail = uiLanguage === "vi";
  const sections = [
    {
      href: "/phr/identity",
      icon: "badge",
      title: detail ? "Danh tính cơ bản" : "Identity",
      description: detail
        ? "Họ tên, ngày sinh, giới tính và nhóm máu."
        : "Name, date of birth, gender, and blood type.",
    },
    {
      href: "/phr/body",
      icon: "accessibility_new",
      title: detail ? "Chỉ số cơ thể" : "Body measurements",
      description: detail
        ? "Chiều cao và cân nặng, trong một bước ngắn."
        : "Height and weight in one short step.",
    },
    {
      href: "/phr/contact",
      icon: "contact_phone",
      title: detail ? "Liên hệ & bảo hiểm" : "Contact & insurance",
      description: detail
        ? "Thông tin liên lạc, người liên hệ khẩn cấp và bảo hiểm."
        : "Contact details, emergency contact, and insurance.",
    },
    {
      href: "/phr/allergies",
      icon: "warning",
      title: text.allergies,
      description: detail
        ? "Khai báo từng dị ứng và phản ứng tương ứng."
        : "Add each allergy and its reaction.",
    },
    {
      href: "/phr/conditions",
      icon: "clinical_notes",
      title: text.conditions,
      description: detail
        ? "Theo dõi từng bệnh nền riêng biệt."
        : "Track each health condition separately.",
    },
    {
      href: "/phr/medications",
      icon: "medication",
      title: text.medications,
      description: detail
        ? "Ghi nhận từng thuốc bạn đang hoặc đã dùng."
        : "Record each medicine you currently use or used.",
    },
  ];

  const tools = [
    capabilities.completeness_meter
      ? {
          href: "/phr/status",
          icon: "donut_large",
          title: text.completenessTitle,
          description: detail
            ? "Xem nhóm thông tin còn thiếu trước khi bổ sung."
            : "See what information is still missing.",
        }
      : null,
    capabilities.ocr_import
      ? {
          href: "/phr/ocr",
          icon: "document_scanner",
          title: detail ? "Quét tài liệu" : "Scan a document",
          description: detail
            ? "Xem lại dữ liệu trước khi đưa vào hồ sơ."
            : "Review imported data before it reaches your record.",
        }
      : null,
    capabilities.export
      ? {
          href: "/phr/export",
          icon: "download",
          title: detail ? "Xuất dữ liệu" : "Export data",
          description: detail
            ? "Tạo bản sao hồ sơ do bạn kiểm soát."
            : "Create a copy of the record you control.",
        }
      : null,
    capabilities.sharing
      ? {
          href: "/phr/sharing",
          icon: "share",
          title: detail ? "Chia sẻ có kiểm soát" : "Controlled sharing",
          description: detail
            ? "Tạo hoặc thu hồi từng liên kết chia sẻ."
            : "Create or revoke individual share links.",
        }
      : null,
    capabilities.enhanced
      ? {
          href: "/phr/emergency-card",
          icon: "emergency",
          title: detail ? "Thẻ khẩn cấp" : "Emergency card",
          description: detail
            ? "Chọn thông tin tối thiểu dùng khi cần khẩn cấp."
            : "Choose the minimum information for an emergency.",
        }
      : null,
    capabilities.reminders
      ? {
          href: "/phr/reminders",
          icon: "notifications_active",
          title: detail ? "Nhắc nhở" : "Reminders",
          description: detail
            ? "Quản lý từng nhắc nhở thuốc."
            : "Manage one medication reminder at a time.",
        }
      : null,
  ].filter((tool): tool is NonNullable<typeof tool> => tool !== null);

  return (
    <PageShell variant="plain" title={text.title} description={text.description}>
      <div className="space-y-5">
        <p
          role="note"
          className="rounded-[var(--radius-lg)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-4 py-3 text-[13px] leading-6 text-[var(--status-warn-text)]"
        >
          {text.disclaimer}
        </p>
        <section className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-3">
          <div className="min-w-0">
            <p className="text-sm font-bold text-[var(--text-primary)]">{text.consentTitle}</p>
            <p className="mt-0.5 text-[13px] leading-6 text-[var(--text-secondary)]">{text.consentBody}</p>
          </div>
          <Button as="link" href="/account/consent" variant="secondary" size="sm">
            {text.consentLink}
          </Button>
        </section>
        <section aria-label={detail ? "Thông tin hồ sơ" : "Profile information"} className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {sections.map((item) => (
            <Button key={item.href} as="link" href={item.href} variant="secondary" className="h-auto min-h-36 justify-start whitespace-normal p-4 text-left">
              <span className="flex items-start gap-3">
                <span aria-hidden="true" className="material-symbols-rounded mt-0.5 text-[22px] text-[var(--brand-600)]">{item.icon}</span>
                <span>
                  <span className="block text-sm font-bold text-[var(--text-primary)]">{item.title}</span>
                  <span className="mt-1 block text-[13px] font-normal leading-5 text-[var(--text-secondary)]">{item.description}</span>
                </span>
              </span>
            </Button>
          ))}
        </section>
        {tools.length > 0 ? (
          <section aria-label={detail ? "Công cụ hồ sơ" : "Record tools"} className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {tools.map((item) => (
              <Button key={item.href} as="link" href={item.href} variant="ghost" className="h-auto min-h-28 justify-start whitespace-normal p-4 text-left">
                <span className="flex items-start gap-3">
                  <span aria-hidden="true" className="material-symbols-rounded mt-0.5 text-[22px] text-[var(--text-secondary)]">{item.icon}</span>
                  <span>
                    <span className="block text-sm font-bold text-[var(--text-primary)]">{item.title}</span>
                    <span className="mt-1 block text-[13px] font-normal leading-5 text-[var(--text-secondary)]">{item.description}</span>
                  </span>
                </span>
              </Button>
            ))}
          </section>
        ) : null}
      </div>
    </PageShell>
  );
}

export default function PhrPage() {
  const pathname = usePathname();
  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");
  const [record, setRecord] = useState<PhrRecord>(EMPTY_RECORD);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [capabilities, setCapabilities] = useState<PhrCapabilityFlags>(
    DEFAULT_PHR_CAPABILITIES,
  );
  const [completeness, setCompleteness] = useState<PhrCompleteness | null>(null);
  const [completenessLoading, setCompletenessLoading] = useState(false);
  const [completenessError, setCompletenessError] = useState<string>("");

  const text = useMemo(() => COPY[uiLanguage], [uiLanguage]);
  const isHub = pathname === "/phr" || pathname === "/phr/";
  const section = isHub ? null : sectionFromPath(pathname);
  const isRecordEditor = [
    "identity",
    "body",
    "contact",
    "allergies",
    "conditions",
    "medications",
  ].includes(section ?? "");
  const needsRecord = isRecordEditor || section === "reminders";

  useEffect(() => {
    setUiLanguage(getStoredUILanguage());
    return onUILanguageChange(setUiLanguage);
  }, []);

  // Resolve effective capability flags so flagged-off surfaces (the completeness
  // meter) stay hidden, preserving the legacy PHR view (Requirement 18.1).
  useEffect(() => {
    let mounted = true;
    getPhrCapabilities().then((flags) => {
      if (mounted) setCapabilities(flags);
    });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    async function run() {
      if (!needsRecord) {
        setLoading(false);
        return;
      }
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
  }, [needsRecord, text.loadError]);

  const setField = <K extends keyof PhrRecord>(key: K, value: PhrRecord[K]) => {
    setRecord((prev) => ({ ...prev, [key]: value }));
  };

  // Re-fetch the record after an out-of-band write (e.g. OCR confirm commits
  // new medications) so the page reflects the server state immediately.
  const reloadRecord = useCallback(async () => {
    try {
      const data = await getPhrRecord();
      setRecord(normalizeRecord(data));
    } catch {
      setError(text.loadError);
    }
  }, [text.loadError]);

  // Load the completeness score whenever the meter is enabled. Recomputed after
  // a save so adding data to a missing class updates the meter (Req 16.2/16.3).
  const refreshCompleteness = useCallback(async () => {
    if (section !== "status" || !capabilities.completeness_meter) return;
    setCompletenessLoading(true);
    setCompletenessError("");
    try {
      const data = await getPhrCompleteness();
      setCompleteness(data);
    } catch {
      setCompletenessError(text.completenessError);
    } finally {
      setCompletenessLoading(false);
    }
  }, [capabilities.completeness_meter, section, text.completenessError]);

  useEffect(() => {
    refreshCompleteness();
  }, [refreshCompleteness]);

  const completenessState: AsyncState<PhrCompleteness> = selectAsyncState({
    loading: completenessLoading,
    error: completenessError || null,
    data: completeness,
    // The score is always meaningful (even 0%), so never treat it as empty.
    isEmpty: () => false,
  });

  const updateAllergy = (id: string, patch: Partial<PhrAllergyItem>) => {
    setRecord((prev) => ({
      ...prev,
      allergies: prev.allergies.map((item) =>
        item.id === id ? { ...item, ...patch } : item,
      ),
    }));
  };

  const updateCondition = (id: string, patch: Partial<PhrConditionItem>) => {
    setRecord((prev) => ({
      ...prev,
      conditions: prev.conditions.map((item) =>
        item.id === id ? { ...item, ...patch } : item,
      ),
    }));
  };

  const updateMedication = (id: string, patch: Partial<PhrMedicationItem>) => {
    setRecord((prev) => ({
      ...prev,
      medications: prev.medications.map((item) =>
        item.id === id ? { ...item, ...patch } : item,
      ),
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
        {
          id: makeId(),
          name: "",
          status: "unknown",
          diagnosed_on: null,
          note: "",
        },
      ],
    }));
  };

  const addMedication = () => {
    setRecord((prev) => ({
      ...prev,
      medications: [
        ...prev.medications,
        {
          id: makeId(),
          name: "",
          dose: "",
          frequency: "",
          started_on: null,
          is_current: true,
          note: "",
        },
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
      // Recompute completeness so newly-added data classes reflect immediately.
      void refreshCompleteness();
    } catch (err) {
      setError(err instanceof Error ? err.message : text.saveError);
    } finally {
      setSaving(false);
    }
  };

  if (isHub) {
    return <PhrHub text={text} uiLanguage={uiLanguage} capabilities={capabilities} />;
  }

  if (!section) {
    return (
      <PageShell
        variant="plain"
        title={uiLanguage === "vi" ? "Mục hồ sơ không tồn tại" : "Record section not found"}
        description={uiLanguage === "vi" ? "Hãy trở về trung tâm hồ sơ để chọn một mục." : "Return to the record hub to choose a section."}
      >
        <Button as="link" href="/phr" variant="secondary">
          {uiLanguage === "vi" ? "Về hồ sơ sức khỏe" : "Back to health record"}
        </Button>
      </PageShell>
    );
  }

  const sectionCopy: Record<PhrSection, { title: string; description: string }> = {
    identity: {
      title: uiLanguage === "vi" ? "Danh tính cơ bản" : "Identity",
      description: uiLanguage === "vi" ? "Chỉ thông tin nhận diện và nhóm máu." : "Only identity information and blood type.",
    },
    body: {
      title: uiLanguage === "vi" ? "Chỉ số cơ thể" : "Body measurements",
      description: uiLanguage === "vi" ? "Cập nhật chiều cao và cân nặng." : "Update height and weight.",
    },
    contact: {
      title: uiLanguage === "vi" ? "Liên hệ & bảo hiểm" : "Contact & insurance",
      description: uiLanguage === "vi" ? "Cập nhật liên hệ, liên hệ khẩn cấp và bảo hiểm." : "Update contact, emergency contact, and insurance.",
    },
    allergies: { title: text.allergies, description: uiLanguage === "vi" ? "Thêm và xem lại từng dị ứng." : "Add and review one allergy at a time." },
    conditions: { title: text.conditions, description: uiLanguage === "vi" ? "Thêm và xem lại từng bệnh nền." : "Add and review one condition at a time." },
    medications: { title: text.medications, description: uiLanguage === "vi" ? "Thêm và xem lại từng thuốc." : "Add and review one medication at a time." },
    status: { title: text.completenessTitle, description: text.completenessDescription },
    ocr: { title: uiLanguage === "vi" ? "Quét tài liệu" : "Scan a document", description: uiLanguage === "vi" ? "Xem lại trước khi xác nhận nhập hồ sơ." : "Review before confirming an import." },
    export: { title: uiLanguage === "vi" ? "Xuất dữ liệu" : "Export data", description: uiLanguage === "vi" ? "Tạo bản sao hồ sơ do bạn kiểm soát." : "Create a copy of the record you control." },
    sharing: { title: uiLanguage === "vi" ? "Chia sẻ có kiểm soát" : "Controlled sharing", description: uiLanguage === "vi" ? "Tạo hoặc thu hồi từng liên kết chia sẻ." : "Create or revoke each share link." },
    "emergency-card": { title: uiLanguage === "vi" ? "Thẻ khẩn cấp" : "Emergency card", description: uiLanguage === "vi" ? "Chọn thông tin tối thiểu khi cần khẩn cấp." : "Choose the minimum information for an emergency." },
    reminders: { title: uiLanguage === "vi" ? "Nhắc nhở" : "Reminders", description: uiLanguage === "vi" ? "Quản lý từng nhắc nhở thuốc." : "Manage one medication reminder at a time." },
  };
  return (
    <PageShell
      variant="plain"
      title={sectionCopy[section].title}
      description={sectionCopy[section].description}
    >
      <div className="space-y-5">
        <Button as="link" href="/phr" variant="ghost" size="sm" icon="arrow_back">
          {uiLanguage === "vi" ? "Hồ sơ sức khỏe" : "Health record"}
        </Button>
        {/* Persistent self-declared, decision-support-only disclaimer
            (personal-health-record Requirement 18.4; Req 13.5). */}
        <p
          role="note"
          className="rounded-[var(--radius-lg)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-4 py-3 text-[13px] leading-6 text-[var(--status-warn-text)]"
        >
          {text.disclaimer}
        </p>

        {/* USCDI completeness meter — only when the capability is effective
            (personal-health-record Requirement 16.2; hidden flag-off per
            Requirement 18.1). */}
        {section === "status" && capabilities.completeness_meter ? (
          <CompletenessMeter
            state={completenessState}
            text={text}
            uiLanguage={uiLanguage}
          />
        ) : null}

        {/* Enhanced PHR tools — each surface is shown only when its effective
            capability flag is on, so with flags off the legacy view is preserved
            (personal-health-record Requirement 18.1). */}
        {section === "ocr" && capabilities.ocr_import ? (
          <section className={phrPanelClass}>
            <OcrReviewModal
              uiLanguage={uiLanguage}
              onConfirmed={() => {
                void reloadRecord();
                void refreshCompleteness();
              }}
            />
          </section>
        ) : null}

        {section === "export" && capabilities.export ? (
          <PhrExportButton uiLanguage={uiLanguage} />
        ) : null}

        {section === "sharing" && capabilities.sharing ? <ShareManager uiLanguage={uiLanguage} /> : null}

        {section === "emergency-card" && capabilities.enhanced ? (
          <EmergencyCardEditor uiLanguage={uiLanguage} />
        ) : null}

        {section === "reminders" && capabilities.reminders ? (
          <RemindersPanel
            uiLanguage={uiLanguage}
            medications={record.medications}
          />
        ) : null}

        {isRecordEditor ? <section className={phrPanelClass}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="text-xs text-[var(--text-secondary)]">
              {text.updatedAt}:{" "}
              {record.updated_at
                ? formatLocaleDate(uiLanguage, record.updated_at, {
                    dateStyle: "medium",
                    timeStyle: "short",
                  })
                : text.unknown}
            </div>
            <Button
              type="button"
              onClick={onSave}
              disabled={loading || saving}
              loading={saving}
              loadingLabel={text.saving}
              icon="save"
            >
              {text.save}
            </Button>
          </div>
          {loading ? (
            <p className="mt-3 text-sm text-[var(--text-secondary)]">
              {text.loading}
            </p>
          ) : null}
          {message ? (
            <p className="mt-3 text-sm text-[var(--status-ok-text)]">{message}</p>
          ) : null}
          {error ? (
            <p className="mt-3 text-sm text-[var(--status-danger-text)]">{error}</p>
          ) : null}
        </section> : null}

        {["identity", "body", "contact"].includes(section) ? <section className={phrPanelClass}>
          <p className="mb-4 text-sm font-semibold text-[var(--text-primary)]">
            {sectionCopy[section].title}
          </p>
          <div className="grid gap-4 md:grid-cols-2">
            {section === "identity" ? <Field
              label={text.fullName}
              value={record.full_name}
              onChange={(e) => setField("full_name", e.target.value)}
            /> : null}
            {section === "identity" ? <Field
              label={text.dob}
              type="date"
              value={toInputDate(record.date_of_birth)}
              onChange={(e) =>
                setField("date_of_birth", e.target.value || null)
              }
            /> : null}
            {section === "identity" ? <Field
              label={text.gender}
              value={record.gender}
              onChange={(e) => setField("gender", e.target.value)}
            /> : null}
            {section === "identity" ? <Field
              label={text.bloodType}
              value={record.blood_type}
              onChange={(e) => setField("blood_type", e.target.value)}
            /> : null}
            {section === "body" ? <Field
              label={text.height}
              inputMode="decimal"
              value={record.height_cm ?? ""}
              onChange={(e) =>
                setField("height_cm", parseInputNumber(e.target.value))
              }
            /> : null}
            {section === "body" ? <Field
              label={text.weight}
              inputMode="decimal"
              value={record.weight_kg ?? ""}
              onChange={(e) =>
                setField("weight_kg", parseInputNumber(e.target.value))
              }
            /> : null}
            {section === "contact" ? <Field
              label={text.phone}
              value={record.phone}
              onChange={(e) => setField("phone", e.target.value)}
            /> : null}
            {section === "contact" ? <Field
              label={text.insurance}
              value={record.insurance_id}
              onChange={(e) => setField("insurance_id", e.target.value)}
            /> : null}
            {section === "contact" ? <Field
              label={text.emergencyName}
              value={record.emergency_contact_name}
              onChange={(e) =>
                setField("emergency_contact_name", e.target.value)
              }
            /> : null}
            {section === "contact" ? <Field
              label={text.emergencyPhone}
              value={record.emergency_contact_phone}
              onChange={(e) =>
                setField("emergency_contact_phone", e.target.value)
              }
            /> : null}
            {section === "contact" ? <Field
              label={text.address}
              wrapperClassName="md:col-span-2"
              value={record.address}
              onChange={(e) => setField("address", e.target.value)}
            /> : null}
            {section === "contact" ? <Textarea
              label={text.notes}
              wrapperClassName="md:col-span-2"
              className="min-h-[84px]"
              value={record.notes}
              onChange={(e) => setField("notes", e.target.value)}
            /> : null}
          </div>
        </section> : null}

        {(["allergies", "conditions", "medications"] as const).includes(section as "allergies" | "conditions" | "medications") ? <section className="grid gap-4">
          {section === "allergies" ? <article className={phrColumnClass}>
            <div className="mb-3 flex items-center justify-between gap-3">
              <p className="text-base font-bold text-[var(--text-primary)]">
                {text.allergies}
              </p>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                icon="add"
                onClick={addAllergy}
              >
                {text.add}
              </Button>
            </div>
            <div className="space-y-3">
              {record.allergies.map((item) => (
                <div key={item.id} className={phrItemClass}>
                  <div className="grid gap-2">
                    <Field
                      aria-label={text.allergyName}
                      placeholder={text.allergyName}
                      value={item.name}
                      onChange={(e) =>
                        updateAllergy(item.id, { name: e.target.value })
                      }
                    />
                    <Field
                      aria-label={text.reaction}
                      placeholder={text.reaction}
                      value={item.reaction}
                      onChange={(e) =>
                        updateAllergy(item.id, { reaction: e.target.value })
                      }
                    />
                    <Field
                      aria-label={text.severity}
                      placeholder={text.severity}
                      value={item.severity}
                      onChange={(e) =>
                        updateAllergy(item.id, {
                          severity: (e.target.value ||
                            "unknown") as PhrAllergyItem["severity"],
                        })
                      }
                    />
                    <Textarea
                      aria-label={text.itemNote}
                      className="min-h-[56px]"
                      placeholder={text.itemNote}
                      value={item.note}
                      onChange={(e) =>
                        updateAllergy(item.id, { note: e.target.value })
                      }
                    />
                    <ProvenanceBadges
                      source={item.information_source}
                      verification={item.verification_status}
                      uiLanguage={uiLanguage}
                      sourceLabel={text.source}
                      verificationLabel={text.verification}
                    />
                    <Button
                      type="button"
                      variant="danger"
                      size="sm"
                      icon="delete"
                      className="justify-self-start"
                      onClick={() =>
                        setRecord((prev) => ({
                          ...prev,
                          allergies: prev.allergies.filter(
                            (row) => row.id !== item.id,
                          ),
                        }))
                      }
                    >
                      {text.remove}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </article> : null}

          {section === "conditions" ? <article className={phrColumnClass}>
            <div className="mb-3 flex items-center justify-between gap-3">
              <p className="text-base font-bold text-[var(--text-primary)]">
                {text.conditions}
              </p>
              <Button
                type="button"
                onClick={addCondition}
                variant="secondary"
                size="sm"
                icon="add"
              >
                {text.add}
              </Button>
            </div>
            <div className="space-y-3">
              {record.conditions.map((item) => (
                <div key={item.id} className={phrItemClass}>
                  <div className="grid gap-2">
                    <Field
                      aria-label={text.conditionName}
                      placeholder={text.conditionName}
                      value={item.name}
                      onChange={(e) =>
                        updateCondition(item.id, { name: e.target.value })
                      }
                    />
                    <Field
                      aria-label={text.status}
                      placeholder={text.status}
                      value={item.status}
                      onChange={(e) =>
                        updateCondition(item.id, {
                          status: (e.target.value ||
                            "unknown") as PhrConditionItem["status"],
                        })
                      }
                    />
                    <Field
                      aria-label={text.diagnosedOn}
                      type="date"
                      placeholder={text.diagnosedOn}
                      value={toInputDate(item.diagnosed_on)}
                      onChange={(e) =>
                        updateCondition(item.id, {
                          diagnosed_on: e.target.value || null,
                        })
                      }
                    />
                    <Textarea
                      aria-label={text.itemNote}
                      className="min-h-[56px]"
                      placeholder={text.itemNote}
                      value={item.note}
                      onChange={(e) =>
                        updateCondition(item.id, { note: e.target.value })
                      }
                    />
                    <ProvenanceBadges
                      source={item.information_source}
                      verification={item.verification_status}
                      uiLanguage={uiLanguage}
                      sourceLabel={text.source}
                      verificationLabel={text.verification}
                    />
                    <Button
                      type="button"
                      onClick={() =>
                        setRecord((prev) => ({
                          ...prev,
                          conditions: prev.conditions.filter(
                            (row) => row.id !== item.id,
                          ),
                        }))
                      }
                      variant="danger"
                      size="sm"
                      icon="delete"
                      className="justify-self-start"
                    >
                      {text.remove}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </article> : null}

          {section === "medications" ? <article className={phrColumnClass}>
            <div className="mb-3 flex items-center justify-between gap-3">
              <p className="text-base font-bold text-[var(--text-primary)]">
                {text.medications}
              </p>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                icon="add"
                onClick={addMedication}
              >
                {text.add}
              </Button>
            </div>
            <div className="space-y-3">
              {record.medications.map((item) => (
                <div key={item.id} className={phrItemClass}>
                  <div className="grid gap-2">
                    <Field
                      aria-label={text.medicationName}
                      placeholder={text.medicationName}
                      value={item.name}
                      onChange={(e) =>
                        updateMedication(item.id, { name: e.target.value })
                      }
                    />
                    <Field
                      aria-label={text.dose}
                      placeholder={text.dose}
                      value={item.dose}
                      onChange={(e) =>
                        updateMedication(item.id, { dose: e.target.value })
                      }
                    />
                    <Field
                      aria-label={text.frequency}
                      placeholder={text.frequency}
                      value={item.frequency}
                      onChange={(e) =>
                        updateMedication(item.id, { frequency: e.target.value })
                      }
                    />
                    <Field
                      aria-label={text.startedOn}
                      type="date"
                      placeholder={text.startedOn}
                      value={toInputDate(item.started_on)}
                      onChange={(e) =>
                        updateMedication(item.id, {
                          started_on: e.target.value || null,
                        })
                      }
                    />
                    <label className="inline-flex min-h-9 items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
                      <input
                        type="checkbox"
                        checked={item.is_current}
                        onChange={(e) =>
                          updateMedication(item.id, {
                            is_current: e.target.checked,
                          })
                        }
                      />
                      {text.current}
                    </label>
                    <Textarea
                      aria-label={text.itemNote}
                      className="min-h-[56px]"
                      placeholder={text.itemNote}
                      value={item.note}
                      onChange={(e) =>
                        updateMedication(item.id, { note: e.target.value })
                      }
                    />
                    <ProvenanceBadges
                      source={item.information_source}
                      verification={item.verification_status}
                      uiLanguage={uiLanguage}
                      sourceLabel={text.source}
                      verificationLabel={text.verification}
                    />
                    <Button
                      type="button"
                      variant="danger"
                      size="sm"
                      icon="delete"
                      onClick={() =>
                        setRecord((prev) => ({
                          ...prev,
                          medications: prev.medications.filter(
                            (row) => row.id !== item.id,
                          ),
                        }))
                      }
                    >
                      {text.remove}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </article> : null}
        </section> : null}
      </div>
    </PageShell>
  );
}
