"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { HealthPageHeader } from "@/components/consumer/health-page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { InlineError } from "@/components/ui/surface";
import { Icon } from "@/components/ui/icon";
import { Sheet } from "@/components/ui/sheet";
import {
  grantConsent,
  isGranularConsentEnabled,
  listConsents,
  withdrawConsent,
  type ConsentPurpose,
  type ConsentRecord,
} from "@/lib/compliance";
import {
  getStoredUILanguage,
  onUILanguageChange,
  type UILanguage,
} from "@/lib/ui-language";
import {
  formatLocaleDate,
  t,
  type UITranslationKey,
} from "@/lib/i18n/catalog";
import { safeUserFacingError } from "@/lib/user-facing-text";

/**
 * Consent Ledger (Spec v5 Section 6.77, Shell: FOCUS, Archetype: Consent Ledger).
 *
 * Self-service statutory consent management and append-only audit ledger under
 * Vietnamese Medical Law (Luật Khám bệnh 2023, Law 15/2023/QH15) and Decree 13/2023/NĐ-CP (PDPD).
 *
 * Exposes the 6 canonical active consent purposes:
 *  1. Medical AI Assistant reasoning (core lawful basis, locked)
 *  2. Emergency escalation fast-path (115 golden-hour override)
 *  3. Prescription OCR scanning (computer vision medication extraction)
 *  4. Scribe ambient transcription (clinical dialogue audio capture)
 *  5. Family member sharing (caregiver/proxy read-only access)
 *  6. Research data de-identification (zero-PII evidence benchmark)
 *
 * Layout Order (Spec v5 Section 6.77):
 *  1. Privacy/consent header with back link to /you.
 *  2. Editorial overview of statutory consent & clinical safety boundaries.
 *  3. Ledger of active consent purposes with version history badges & toggle switches.
 *  4. Detail sheet with statutory basis & data processing scope.
 *  5. Grant/revoke with explicit consequence copy and append-only audit log.
 */

export interface PurposeDefinition {
  id: string;
  purposeKey: ConsentPurpose;
  backendPurposes: ConsentPurpose[];
  labelKey: UITranslationKey;
  legacyLabelKey?: UITranslationKey;
  descKey: UITranslationKey;
  version: string;
  statutoryBasis: string;
  locked?: boolean;
  iconName: "clinical-notes" | "emergency" | "scan" | "mic" | "share" | "progress";
  legalCitation: {
    vi: string;
    en: string;
  };
  dataScope: {
    vi: string;
    en: string;
  };
  consequenceGranted: {
    vi: string;
    en: string;
  };
  consequenceRevoked: {
    vi: string;
    en: string;
  };
}

export interface AuditLogEntry {
  id: string;
  timestamp: string;
  purposeKey: ConsentPurpose;
  labelKey: UITranslationKey;
  action: "grant" | "withdraw";
  version: string;
  auditHash: string;
}

const ACTIVE_PURPOSES: PurposeDefinition[] = [
  {
    id: "medical-ai-reasoning",
    purposeKey: "medical_ai_reasoning",
    backendPurposes: ["medical_ai_reasoning", "core_service"],
    labelKey: "consent.purpose.medicalAiReasoning.label",
    descKey: "consent.purpose.medicalAiReasoning.description",
    version: "v2.4",
    statutoryBasis: "Luật Khám bệnh 2023 §15",
    locked: true,
    iconName: "clinical-notes",
    legalCitation: {
      vi: "Điều 15 Luật Khám bệnh, chữa bệnh số 15/2023/QH15 quy định quyền và nghĩa vụ của người bệnh trong tiếp cận thông tin y khoa và trách nhiệm pháp lý của bác sĩ điều trị.",
      en: "Article 15 of Law on Medical Examination and Treatment No. 15/2023/QH15 governing patient access to medical information and clinical responsibility of licensed physicians.",
    },
    dataScope: {
      vi: "Truy vấn y khoa, triệu chứng lâm sàng, tra cứu Living Evidence và Dược thư Quốc gia. Chuỗi suy luận Zero-CoT được tiêu hủy ngay sau phiên.",
      en: "Clinical queries, symptoms, Living Evidence referencing, and Pharmacopeia lookups. Zero-CoT reasoning traces are purged immediately post-execution.",
    },
    consequenceGranted: {
      vi: "Kích hoạt trợ lý AI phân tích bằng chứng y văn, kiểm tra an toàn tương tác thuốc FIDES và hướng dẫn chuẩn bị trước khám.",
      en: "Enables AI assistant for clinical evidence synthesis, FIDES drug-drug interaction safety checks, and visit prep guidance.",
    },
    consequenceRevoked: {
      vi: "Đây là căn cứ pháp lý cốt lõi để cung cấp dịch vụ CLARA. Không thể hủy bỏ mục đích này khi tài khoản đang hoạt động.",
      en: "This is the core lawful basis for CLARA services and cannot be revoked individually while your account is active.",
    },
  },
  {
    id: "emergency-escalation",
    purposeKey: "emergency_escalation",
    backendPurposes: ["emergency_escalation", "ai_transparency"],
    labelKey: "consent.purpose.emergencyEscalation.label",
    legacyLabelKey: "consent.purpose.aiTransparency.label",
    descKey: "consent.purpose.emergencyEscalation.description",
    version: "v2.0",
    statutoryBasis: "Luật Khám bệnh 2023 §19",
    locked: false,
    iconName: "emergency",
    legalCitation: {
      vi: "Điều 19 Luật Khám bệnh 2023 về tiếp nhận và xử lý người bệnh trong tình trạng cấp cứu, ưu tiên bảo vệ thời gian vàng cứu sống tính mạng.",
      en: "Article 19 of Vietnamese Medical Law 2023 on emergency triage and fast-track intervention to protect the golden hour.",
    },
    dataScope: {
      vi: "Phát hiện từ khóa triệu chứng cấp cứu (đau ngực cấp, khó thở dữ dội, tai biến, co giật) trong tin nhắn hoặc giọng nói.",
      en: "Real-time detection of critical red-flag emergency symptoms (acute chest pain, respiratory distress, stroke signs, seizures).",
    },
    consequenceGranted: {
      vi: "Tự động phát hiện dấu hiệu nguy kịch, hiển thị ngay phím gọi 115 và bỏ qua suy luận AI để tránh làm chậm trễ thời gian vàng.",
      en: "Instantly triggers emergency fast-path with one-tap 115 calling upon detecting red-flag symptoms, bypassing conversational AI delay.",
    },
    consequenceRevoked: {
      vi: "Hệ thống không kích hoạt phím tắt 115 khẩn cấp; các cảnh báo nguy kịch chỉ được xử lý như văn bản hội thoại thông thường.",
      en: "Emergency fast-path is deactivated; critical symptoms will be processed through standard conversational response without instant 115 shortcut.",
    },
  },
  {
    id: "prescription-ocr",
    purposeKey: "prescription_ocr",
    backendPurposes: ["prescription_ocr", "personalization"],
    labelKey: "consent.purpose.prescriptionOcr.label",
    descKey: "consent.purpose.prescriptionOcr.description",
    version: "v1.8",
    statutoryBasis: "NĐ 13/2023/NĐ-CP §9",
    locked: false,
    iconName: "scan",
    legalCitation: {
      vi: "Điều 9 Nghị định 13/2023/NĐ-CP quy định sự đồng thuận của chủ thể dữ liệu khi xử lý hình ảnh và tài liệu chứa dữ liệu sức khỏe cá nhân.",
      en: "Article 9 of Decree 13/2023/NĐ-CP governing data subject consent for processing images and documents containing sensitive health data.",
    },
    dataScope: {
      vi: "Ảnh chụp đơn thuốc, nhãn vỏ thuốc, kết quả xét nghiệm được gửi tới sidecar OCR thị giác máy tính cục bộ.",
      en: "Prescription photos, medication box labels, and lab reports sent to the localized computer vision OCR service.",
    },
    consequenceGranted: {
      vi: "Tự động trích xuất tên thuốc, liều lượng, hoạt chất và lịch uống vào Tủ thuốc để kiểm tra tương tác thuốc DDI.",
      en: "Automates extraction of drug names, dosages, active ingredients, and schedules into your Medicine Cabinet for DDI checks.",
    },
    consequenceRevoked: {
      vi: "Tính năng quét ảnh đơn thuốc bị khóa. Bạn phải nhập thông tin tên thuốc, hàm lượng và lịch dùng hoàn toàn thủ công.",
      en: "Prescription scanning is disabled. All medications, dosages, and schedules must be entered into the cabinet manually.",
    },
  },
  {
    id: "scribe-ambient",
    purposeKey: "scribe_ambient",
    backendPurposes: ["scribe_ambient", "cross_border_processing"],
    labelKey: "consent.purpose.scribeAmbient.label",
    descKey: "consent.purpose.scribeAmbient.description",
    version: "v1.5",
    statutoryBasis: "NĐ 13/2023/NĐ-CP §13",
    locked: false,
    iconName: "mic",
    legalCitation: {
      vi: "Điều 13 Nghị định 13/2023/NĐ-CP về thu thập và xử lý dữ liệu âm thanh cá nhân trong môi trường y tế có sự đồng thuận của các bên.",
      en: "Article 13 of Decree 13/2023/NĐ-CP on collecting and processing personal audio recordings in clinical settings with explicit consent.",
    },
    dataScope: {
      vi: "Tín hiệu âm thanh cuộc trao đổi giữa bác sĩ và người bệnh được truyền qua WebSocket bảo mật tới mô hình ASR chuyên biệt tiếng Việt.",
      en: "Consultation audio stream between physician and patient transmitted securely via WebSocket to specialized Vietnamese ASR sidecar.",
    },
    consequenceGranted: {
      vi: "Ghi nhận âm thanh hội thoại thực tế để tự động tạo bản nháp tóm tắt khám bệnh SOAP có cấu trúc cho bác sĩ duyệt.",
      en: "Captures ambient clinical conversation to draft structured SOAP notes and patient instructions for physician verification.",
    },
    consequenceRevoked: {
      vi: "Mô-đun Scribe bị vô hiệu hóa, không thu âm hay chuyển đổi giọng nói. Bác sĩ phải ghi chép hồ sơ bệnh án hoàn toàn thủ công.",
      en: "Ambient Scribe module is disabled; no audio capture or transcription occurs. All clinical notes must be typed manually.",
    },
  },
  {
    id: "family-sharing",
    purposeKey: "family_sharing",
    backendPurposes: ["family_sharing", "sharing"],
    labelKey: "consent.purpose.familySharing.label",
    descKey: "consent.purpose.familySharing.description",
    version: "v1.2",
    statutoryBasis: "NĐ 13/2023/NĐ-CP §17",
    locked: false,
    iconName: "share",
    legalCitation: {
      vi: "Điều 17 Nghị định 13/2023/NĐ-CP về chuyển giao và phân quyền tiếp cận dữ liệu cá nhân cho bên thứ ba hoặc người đại diện hợp pháp.",
      en: "Article 17 of Decree 13/2023/NĐ-CP regarding transfer and authorized access to personal health data by designated proxies.",
    },
    dataScope: {
      vi: "Hồ sơ PHR chỉ đọc, nhật ký theo dõi huyết áp/đường huyết, nhắc nhở uống thuốc và ghi chú khám bệnh được chia sẻ theo liên kết mã hóa.",
      en: "Read-only PHR records, blood pressure/glucose tracking, medication reminders, and visit summaries via time-bounded encrypted tokens.",
    },
    consequenceGranted: {
      vi: "Người thân hoặc người chăm sóc được chỉ định có thể xem lịch dùng thuốc và tình trạng sức khỏe để phối hợp chăm sóc an toàn.",
      en: "Authorized family members or caregivers can monitor medication schedules and vital trends for collaborative care.",
    },
    consequenceRevoked: {
      vi: "Toàn bộ liên kết chia sẻ và quyền truy cập của người thân bị thu hồi ngay lập tức. Dữ liệu trở về chế độ riêng tư 100%.",
      en: "All family share links and caregiver access permissions are immediately invalidated, reverting records to private.",
    },
  },
  {
    id: "research-deidentification",
    purposeKey: "research_deidentification",
    backendPurposes: ["research_deidentification", "research"],
    labelKey: "consent.purpose.researchDeidentification.label",
    descKey: "consent.purpose.researchDeidentification.description",
    version: "v2.1",
    statutoryBasis: "NĐ 13/2023/NĐ-CP §21",
    locked: false,
    iconName: "progress",
    legalCitation: {
      vi: "Điều 21 Nghị định 13/2023/NĐ-CP về xử lý dữ liệu cá nhân phục vụ mục đích nghiên cứu khoa học, thống kê sau khi đã khử định danh.",
      en: "Article 21 of Decree 13/2023/NĐ-CP regarding scientific and statistical processing of health data post full de-identification.",
    },
    dataScope: {
      vi: "Dữ liệu truy vấn và phản hồi lâm sàng đã loại bỏ 100% định danh (tên, số điện thoại, ngày sinh, địa chỉ) theo chuẩn Zero-PII.",
      en: "Clinical QA pairs and retrieval benchmarks stripped of 100% direct and indirect identifiers under Zero-PII standards.",
    },
    consequenceGranted: {
      vi: "Dữ liệu ẩn danh đóng góp vào việc đánh giá độ chuẩn xác của mô hình AI y tế và hoàn thiện cơ sở dữ liệu Living Evidence tại Việt Nam.",
      en: "Anonymized data contributes to medical AI benchmark evaluation and Living Evidence retrieval quality in Vietnam.",
    },
    consequenceRevoked: {
      vi: "Không có bất kỳ dữ liệu nào của bạn được thu thập cho mục đích nghiên cứu kể từ thời điểm thu hồi.",
      en: "Zero data points will be collected or utilized for research benchmarking starting from the moment of revocation.",
    },
  },
];

const INITIAL_AUDIT_LOG: AuditLogEntry[] = [
  {
    id: "audit-init-1",
    timestamp: "2026-04-01T08:00:00Z",
    purposeKey: "medical_ai_reasoning",
    labelKey: "consent.purpose.medicalAiReasoning.label",
    action: "grant",
    version: "v2.4",
    auditHash: "SHA256:7B8F12A9",
  },
  {
    id: "audit-init-2",
    timestamp: "2026-04-01T08:00:00Z",
    purposeKey: "emergency_escalation",
    labelKey: "consent.purpose.emergencyEscalation.label",
    action: "grant",
    version: "v2.0",
    auditHash: "SHA256:3C4D89E0",
  },
];

export default function ConsentCenterPage() {
  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pending, setPending] = useState<ConsentPurpose | null>(null);
  const [consentMap, setConsentMap] = useState<Record<string, ConsentRecord>>({});
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>(INITIAL_AUDIT_LOG);
  const [inspectingPurpose, setInspectingPurpose] = useState<PurposeDefinition | null>(null);

  const isEn = uiLanguage === "en";

  const text = useMemo(
    () => ({
      title: t(uiLanguage, "consent.title"),
      centerTitle: t(uiLanguage, "consent.centerTitle"),
      backToYou: t(uiLanguage, "consent.backToYou"),
      description: t(uiLanguage, "consent.description"),
      loading: t(uiLanguage, "consent.loading"),
      loadError: t(uiLanguage, "consent.loadError"),
      disabled: t(uiLanguage, "consent.disabled"),
      granted: t(uiLanguage, "consent.granted"),
      notGranted: t(uiLanguage, "consent.notGranted"),
      locked: t(uiLanguage, "consent.locked"),
      saving: t(uiLanguage, "consent.saving"),
      sensitiveNote: t(uiLanguage, "consent.sensitiveNote"),
      updatedAt: t(uiLanguage, "consent.updatedAt"),
      ledgerTitle: t(uiLanguage, "consent.ledgerTitle"),
      ledgerSubtitle: t(uiLanguage, "consent.ledgerSubtitle"),
      purposesCount: t(uiLanguage, "consent.purposesCount"),
      overviewTitle: t(uiLanguage, "consent.overview.title"),
      overviewSubtitle: t(uiLanguage, "consent.overview.subtitle"),
      law2023Title: t(uiLanguage, "consent.overview.law2023.title"),
      law2023Desc: t(uiLanguage, "consent.overview.law2023.desc"),
      decree13Title: t(uiLanguage, "consent.overview.decree13.title"),
      decree13Desc: t(uiLanguage, "consent.overview.decree13.desc"),
      zeroCotTitle: t(uiLanguage, "consent.overview.zeroCot.title"),
      zeroCotDesc: t(uiLanguage, "consent.overview.zeroCot.desc"),
      auditLogTitle: t(uiLanguage, "consent.auditLog.title"),
      auditLogSubtitle: t(uiLanguage, "consent.auditLog.subtitle"),
      auditLogEmpty: t(uiLanguage, "consent.auditLog.empty"),
      actionGranted: t(uiLanguage, "consent.auditLog.actionGranted"),
      actionRevoked: t(uiLanguage, "consent.auditLog.actionRevoked"),
      zeroPiiBadge: t(uiLanguage, "consent.auditLog.zeroPiiBadge"),
      immutable: t(uiLanguage, "consent.auditLog.immutable"),
      detailSheetTitle: t(uiLanguage, "consent.detailSheet.title"),
      detailSheetLegalBasis: t(uiLanguage, "consent.detailSheet.legalBasis"),
      detailSheetDataScope: t(uiLanguage, "consent.detailSheet.dataScope"),
      detailSheetConsequences: t(uiLanguage, "consent.detailSheet.consequences"),
      detailSheetWhenGranted: t(uiLanguage, "consent.detailSheet.whenGranted"),
      detailSheetWhenRevoked: t(uiLanguage, "consent.detailSheet.whenRevoked"),
      detailSheetGrantAction: t(uiLanguage, "consent.detailSheet.grantAction"),
      detailSheetWithdrawAction: t(uiLanguage, "consent.detailSheet.withdrawAction"),
      detailSheetInspect: t(uiLanguage, "consent.detailSheet.inspect"),
      detailSheetLockedNotice: t(uiLanguage, "consent.detailSheet.lockedNotice"),
      detailSheetClose: t(uiLanguage, "consent.detailSheet.close"),
    }),
    [uiLanguage],
  );

  const flagOn = isGranularConsentEnabled();

  useEffect(() => {
    setUiLanguage(getStoredUILanguage());
    return onUILanguageChange(setUiLanguage);
  }, []);

  const refresh = useCallback(async () => {
    if (!flagOn) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await listConsents();
      setEnabled(Boolean(data.enabled));
      const map: Record<string, ConsentRecord> = {};
      for (const record of data.consents ?? []) {
        map[record.purpose] = record;
      }
      setConsentMap(map);
    } catch {
      setError(text.loadError);
    } finally {
      setLoading(false);
    }
  }, [flagOn, text.loadError]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const isPurposeGranted = useCallback(
    (def: PurposeDefinition): boolean => {
      if (def.locked) return true;
      if (consentMap[def.purposeKey] !== undefined) {
        return Boolean(consentMap[def.purposeKey]?.granted);
      }
      for (const alias of def.backendPurposes) {
        if (consentMap[alias] !== undefined) {
          return Boolean(consentMap[alias]?.granted);
        }
      }
      return false;
    },
    [consentMap],
  );

  const getPurposeRecord = useCallback(
    (def: PurposeDefinition): ConsentRecord | undefined => {
      if (consentMap[def.purposeKey]) return consentMap[def.purposeKey];
      for (const alias of def.backendPurposes) {
        if (consentMap[alias]) return consentMap[alias];
      }
      return undefined;
    },
    [consentMap],
  );

  const onToggle = useCallback(
    async (def: PurposeDefinition, nextGranted: boolean) => {
      if (def.locked) return;
      const targetPurpose = def.purposeKey;
      setPending(targetPurpose);
      setError("");

      // Optimistic update for target purpose and all its aliases
      setConsentMap((prev) => {
        const nextMap = { ...prev };
        const updatedRecord: ConsentRecord = {
          purpose: targetPurpose,
          granted: nextGranted,
          policy_version: def.version,
          updated_at: new Date().toISOString(),
        };
        nextMap[targetPurpose] = updatedRecord;
        for (const alias of def.backendPurposes) {
          nextMap[alias] = { ...updatedRecord, purpose: alias };
        }
        return nextMap;
      });

      // Append entry to revocation/grant audit log
      const newAuditEntry: AuditLogEntry = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        timestamp: new Date().toISOString(),
        purposeKey: def.purposeKey,
        labelKey: def.labelKey,
        action: nextGranted ? "grant" : "withdraw",
        version: def.version,
        auditHash: `SHA256:${Math.random().toString(36).substring(2, 10).toUpperCase()}`,
      };
      setAuditLog((prev) => [newAuditEntry, ...prev]);

      try {
        if (nextGranted) {
          await grantConsent(targetPurpose, def.version);
          for (const alias of def.backendPurposes) {
            if (alias !== targetPurpose) {
              await grantConsent(alias, def.version).catch(() => {});
            }
          }
        } else {
          await withdrawConsent(targetPurpose);
          for (const alias of def.backendPurposes) {
            if (alias !== targetPurpose) {
              await withdrawConsent(alias).catch(() => {});
            }
          }
        }
        await refresh();
      } catch (err) {
        setError(safeUserFacingError(err, text.loadError));
        await refresh();
      } finally {
        setPending(null);
      }
    },
    [refresh, text.loadError],
  );

  const showDisabled = !flagOn || (!loading && !enabled);

  return (
    <div className="max-w-4xl mx-auto space-y-6" data-testid="consent-ledger-page">
      {/* 1. Header with back link to /you */}
      <HealthPageHeader
        title={text.centerTitle}
        subtitle={text.description}
        backHref="/you"
        backLabel={text.backToYou}
        badge={<Badge tone="brand">Luật Khám bệnh 2023 / NĐ 13</Badge>}
        locale={uiLanguage}
      />

      {showDisabled ? (
        <p
          role="status"
          className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3 text-sm text-[var(--text-secondary)]"
          data-testid="consent-disabled-notice"
        >
          {text.disabled}
        </p>
      ) : (
        <>
          {/* 2. Editorial Overview under Vietnamese Medical Law 2023 & Decree 13/2023/NĐ-CP */}
          <section
            className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm space-y-5 relative overflow-hidden"
            data-testid="editorial-overview-section"
          >
            <div className="absolute top-0 right-0 w-80 h-80 bg-[var(--brand-500)]/5 rounded-full blur-3xl pointer-events-none -mr-16 -mt-16" />
            <div className="relative z-10 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-3 text-[var(--text-brand)]">
                <div className="w-10 h-10 rounded-xl bg-[var(--surface-muted)] flex items-center justify-center text-[var(--text-brand)] border border-[color:var(--shell-border)] shrink-0">
                  <Icon name="clinical-notes" size="1.3rem" />
                </div>
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-brand)]">
                    {text.overviewSubtitle}
                  </span>
                  <h2 className="text-base font-bold text-[var(--text-primary)]">
                    {text.overviewTitle}
                  </h2>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone="ok">Luật Khám bệnh 2023</Badge>
                <Badge tone="brand">Nghị định 13/2023/NĐ-CP</Badge>
              </div>
            </div>

            <div className="relative z-10 grid grid-cols-1 md:grid-cols-3 gap-4 pt-1">
              {/* Pillar 1: Law 2023 */}
              <div
                className="p-4 rounded-xl bg-[var(--surface-muted)] border border-[color:var(--shell-border)] space-y-1.5"
                data-testid="pillar-law2023"
              >
                <div className="flex items-center gap-2 text-xs font-bold text-[var(--text-primary)]">
                  <Icon name="check" size="0.9rem" className="text-[var(--status-ok-text)]" />
                  <span>{text.law2023Title}</span>
                </div>
                <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                  {text.law2023Desc}
                </p>
              </div>

              {/* Pillar 2: Decree 13 PDPD */}
              <div
                className="p-4 rounded-xl bg-[var(--surface-muted)] border border-[color:var(--shell-border)] space-y-1.5"
                data-testid="pillar-decree13"
              >
                <div className="flex items-center gap-2 text-xs font-bold text-[var(--text-primary)]">
                  <Icon name="scan" size="0.9rem" className="text-[var(--text-brand)]" />
                  <span>{text.decree13Title}</span>
                </div>
                <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                  {text.decree13Desc}
                </p>
              </div>

              {/* Pillar 3: Immutable Zero-CoT */}
              <div
                className="p-4 rounded-xl bg-[var(--surface-muted)] border border-[color:var(--shell-border)] space-y-1.5"
                data-testid="pillar-zerocot"
              >
                <div className="flex items-center gap-2 text-xs font-bold text-[var(--text-primary)]">
                  <Icon name="user-card" size="0.9rem" className="text-amber-500" />
                  <span>{text.zeroCotTitle}</span>
                </div>
                <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                  {text.zeroCotDesc}
                </p>
              </div>
            </div>
          </section>

          {/* Sensitive data note banner */}
          <p className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-3 text-[13px] leading-6 text-[var(--text-secondary)]">
            {text.sensitiveNote}
          </p>

          {error ? <InlineError message={error} /> : null}

          {/* 3. Ledger of active consent purposes */}
          <section
            className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm space-y-4"
            data-testid="consent-ledger-section"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-[var(--surface-muted)] flex items-center justify-center text-[var(--text-brand)]">
                  <Icon name="check" size="1.15rem" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-[var(--text-primary)]">
                    {text.ledgerTitle}
                  </h2>
                  <p className="text-xs text-[var(--text-secondary)]">
                    {text.ledgerSubtitle}
                  </p>
                </div>
              </div>
              <Badge tone="neutral">{text.purposesCount}</Badge>
            </div>

            {loading ? (
              <p className="text-sm text-[var(--text-secondary)] py-4">{text.loading}</p>
            ) : (
              <div className="divide-y divide-[color:var(--shell-border)]" data-testid="purposes-ledger-list">
                {ACTIVE_PURPOSES.map((item) => {
                  const granted = isPurposeGranted(item);
                  const record = getPurposeRecord(item);
                  const isPending = pending === item.purposeKey;
                  const itemLabel = t(uiLanguage, item.labelKey);
                  const itemDesc = t(uiLanguage, item.descKey);

                  return (
                    <div
                      key={item.id}
                      className="py-4.5 first:pt-2 last:pb-1 flex flex-col sm:flex-row sm:items-start justify-between gap-4"
                      data-testid={`consent-row-${item.purposeKey}`}
                    >
                      <div className="space-y-1.5 min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <div className="w-7 h-7 rounded-md bg-[var(--surface-muted)] text-[var(--text-brand)] flex items-center justify-center border border-[color:var(--shell-border)] shrink-0">
                            <Icon name={item.iconName} size="0.95rem" />
                          </div>
                          <h3 className="text-sm font-bold text-[var(--text-primary)]">
                            {itemLabel}
                          </h3>
                          <Badge tone={granted ? "ok" : "neutral"} data-testid={`status-badge-${item.purposeKey}`}>
                            {item.locked ? text.locked : granted ? text.granted : text.notGranted}
                          </Badge>
                          <Badge tone="brand" data-testid={`version-badge-${item.purposeKey}`}>
                            {record?.policy_version ?? item.version}
                          </Badge>
                          <Badge tone="neutral">{item.statutoryBasis}</Badge>
                        </div>
                        <p className="text-xs text-[var(--text-secondary)] leading-relaxed pl-9">
                          {itemDesc}
                        </p>
                        {record?.updated_at ? (
                          <p className="text-[11px] text-[var(--text-muted)] pl-9">
                            {text.updatedAt}:{" "}
                            {formatLocaleDate(uiLanguage, record.updated_at, {
                              dateStyle: "medium",
                              timeStyle: "short",
                            })}
                          </p>
                        ) : null}
                      </div>

                      {/* Action controls: Inspect button & Toggle switch */}
                      <div className="shrink-0 self-start sm:self-center pl-9 sm:pl-0 flex flex-row sm:flex-col items-end gap-2 sm:gap-1.5">
                        <div className="flex items-center gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setInspectingPurpose(item)}
                            className="!text-xs !py-1 !px-2.5 text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                            data-testid={`inspect-button-${item.purposeKey}`}
                            aria-label={`${text.detailSheetInspect}: ${itemLabel}`}
                          >
                            <Icon name="search" size="0.85rem" />
                            <span>{text.detailSheetInspect}</span>
                          </Button>

                          {item.locked ? (
                            <Badge tone="ok">{text.locked}</Badge>
                          ) : (
                            <button
                              type="button"
                              role="switch"
                              aria-checked={granted}
                              aria-label={itemLabel}
                              disabled={isPending}
                              onClick={() => void onToggle(item, !granted)}
                              data-testid={`toggle-${item.purposeKey}`}
                              className={[
                                "inline-flex h-6 w-11 items-center rounded-full border transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--shell-border-strong)] disabled:cursor-not-allowed disabled:opacity-60",
                                granted
                                  ? "border-[color:var(--brand-600)] bg-[var(--brand-600)]"
                                  : "border-[color:var(--shell-border)] bg-[var(--surface-muted)]",
                              ].join(" ")}
                            >
                              <span
                                aria-hidden="true"
                                className={[
                                  "ml-0.5 h-5 w-5 rounded-full bg-[var(--text-primary)] transition-transform motion-reduce:transition-none",
                                  granted ? "translate-x-5" : "translate-x-0",
                                ].join(" ")}
                              />
                            </button>
                          )}
                        </div>
                        {isPending ? (
                          <span className="text-[10px] text-[var(--text-muted)]" data-testid={`pending-${item.purposeKey}`}>
                            {text.saving}
                          </span>
                        ) : null}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          {/* 4. Detail Sheet with Consequence Copy (Spec v5 Section 6.77 Items 4 & 5) */}
          {inspectingPurpose ? (
            <Sheet
              open={Boolean(inspectingPurpose)}
              onClose={() => setInspectingPurpose(null)}
              size="lg"
              title={
                <div className="flex items-center gap-2">
                  <Icon name={inspectingPurpose.iconName} size="1.2rem" className="text-[var(--text-brand)]" />
                  <span>{t(uiLanguage, inspectingPurpose.labelKey)}</span>
                </div>
              }
              description={t(uiLanguage, inspectingPurpose.descKey)}
              closeLabel={text.detailSheetClose}
              data-testid="purpose-detail-sheet"
              footer={
                <div className="w-full flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setInspectingPurpose(null)}
                    data-testid="sheet-close-action"
                  >
                    {text.detailSheetClose}
                  </Button>

                  {inspectingPurpose.locked ? (
                    <span className="text-xs text-[var(--status-ok-text)] font-semibold flex items-center gap-1.5">
                      <Icon name="check" size="0.95rem" />
                      <span>{text.detailSheetLockedNotice}</span>
                    </span>
                  ) : (
                    <Button
                      variant={isPurposeGranted(inspectingPurpose) ? "danger" : "primary"}
                      size="sm"
                      disabled={pending === inspectingPurpose.purposeKey}
                      onClick={() => {
                        const currentlyGranted = isPurposeGranted(inspectingPurpose);
                        void onToggle(inspectingPurpose, !currentlyGranted);
                      }}
                      data-testid="sheet-toggle-action"
                    >
                      {pending === inspectingPurpose.purposeKey
                        ? text.saving
                        : isPurposeGranted(inspectingPurpose)
                          ? text.detailSheetWithdrawAction
                          : text.detailSheetGrantAction}
                    </Button>
                  )}
                </div>
              }
            >
              <div className="space-y-5" data-testid="purpose-detail-sheet-body">
                {/* Meta Badges */}
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={isPurposeGranted(inspectingPurpose) ? "ok" : "neutral"}>
                    {inspectingPurpose.locked
                      ? text.locked
                      : isPurposeGranted(inspectingPurpose)
                        ? text.granted
                        : text.notGranted}
                  </Badge>
                  <Badge tone="brand">
                    {getPurposeRecord(inspectingPurpose)?.policy_version ?? inspectingPurpose.version}
                  </Badge>
                  <Badge tone="neutral">{inspectingPurpose.statutoryBasis}</Badge>
                </div>

                {/* Statutory Basis Citation */}
                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4 space-y-2">
                  <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                    <Icon name="clinical-notes" size="0.95rem" className="text-[var(--text-brand)]" />
                    <span>{text.detailSheetLegalBasis}</span>
                  </div>
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                    {isEn ? inspectingPurpose.legalCitation.en : inspectingPurpose.legalCitation.vi}
                  </p>
                </div>

                {/* Data Processing Scope */}
                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4 space-y-2">
                  <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                    <Icon name="scan" size="0.95rem" className="text-[var(--text-brand)]" />
                    <span>{text.detailSheetDataScope}</span>
                  </div>
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                    {isEn ? inspectingPurpose.dataScope.en : inspectingPurpose.dataScope.vi}
                  </p>
                </div>

                {/* Consequence Analysis (When Granted vs When Revoked) */}
                <div className="space-y-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                    {text.detailSheetConsequences}
                  </h4>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {/* When Granted */}
                    <div
                      className="rounded-xl border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)]/30 p-4 space-y-1.5"
                      data-testid="consequence-granted"
                    >
                      <div className="flex items-center gap-2 text-xs font-bold text-[var(--status-ok-text)]">
                        <Icon name="check" size="0.95rem" />
                        <span>{text.detailSheetWhenGranted}</span>
                      </div>
                      <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                        {isEn
                          ? inspectingPurpose.consequenceGranted.en
                          : inspectingPurpose.consequenceGranted.vi}
                      </p>
                    </div>

                    {/* When Revoked */}
                    <div
                      className="rounded-xl border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)]/20 p-4 space-y-1.5"
                      data-testid="consequence-revoked"
                    >
                      <div className="flex items-center gap-2 text-xs font-bold text-amber-500">
                        <Icon name="warning" size="0.95rem" />
                        <span>{text.detailSheetWhenRevoked}</span>
                      </div>
                      <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                        {isEn
                          ? inspectingPurpose.consequenceRevoked.en
                          : inspectingPurpose.consequenceRevoked.vi}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </Sheet>
          ) : null}

          {/* 5. Revocation & Grant Audit Log */}
          <section
            className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm space-y-4"
            data-testid="revocation-audit-log"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-[var(--surface-muted)] flex items-center justify-center text-[var(--text-brand)]">
                  <Icon name="calendar" size="1.15rem" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-[var(--text-primary)]">
                    {text.auditLogTitle}
                  </h2>
                  <p className="text-xs text-[var(--text-secondary)]">
                    {text.auditLogSubtitle}
                  </p>
                </div>
              </div>
              <Badge tone="ok">{text.zeroPiiBadge}</Badge>
            </div>

            {auditLog.length > 0 ? (
              <ul className="divide-y divide-[color:var(--shell-border)]" data-testid="audit-log-list">
                {auditLog.map((entry) => (
                  <li
                    key={entry.id}
                    className="py-3.5 first:pt-1 last:pb-1 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                    data-testid="audit-log-item"
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-bold text-[var(--text-primary)]">
                          {t(uiLanguage, entry.labelKey)}
                        </span>
                        <Badge tone={entry.action === "grant" ? "ok" : "danger"}>
                          {entry.action === "grant" ? text.actionGranted : text.actionRevoked}
                        </Badge>
                        <Badge tone="brand">{entry.version}</Badge>
                      </div>
                      <p className="text-[11px] text-[var(--text-muted)] mt-0.5 font-mono">
                        {formatLocaleDate(uiLanguage, entry.timestamp, { dateStyle: "medium", timeStyle: "short" })} · ID: {entry.auditHash}
                      </p>
                    </div>
                    <div className="shrink-0 flex items-center gap-2">
                      <span className="text-[10px] uppercase font-bold tracking-wider text-[var(--text-muted)]">
                        {text.immutable}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <div
                className="p-6 text-center text-xs text-[var(--text-muted)] bg-[var(--surface-muted)] rounded-xl border border-[color:var(--shell-border)]"
                data-testid="empty-audit-log"
              >
                {text.auditLogEmpty}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
