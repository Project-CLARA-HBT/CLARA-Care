"use client";

import { useEffect, useMemo, useState } from "react";
import Modal from "@/components/ui/modal";
import Button from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import {
  buildEncounterExportBundle,
  downloadFhirBundle,
  isFhirEncounterExportEnabled,
  sanitizeExportFilename,
  verifyExportConsent,
  type ConsentVerificationResult,
  type FhirEncounterExportOptions,
  type FhirExportFormat,
  type FhirExportPurpose,
} from "@/lib/fhir-encounter-export";
import type { Visit, VisitDocument } from "@/lib/visit-family";

export type FhirEncounterExportDialogProps = {
  open: boolean;
  onClose: () => void;
  visit: Partial<Visit>;
  documents?: VisitDocument[];
  profileId?: string | null;
  locale?: "vi" | "en";
};

export function FhirEncounterExportDialog({
  open,
  onClose,
  visit,
  documents = [],
  profileId,
  locale = "vi",
}: FhirEncounterExportDialogProps) {
  const isEn = locale === "en";

  const [enabled, setEnabled] = useState(false);
  const [purpose, setPurpose] = useState<FhirExportPurpose>("self_download");
  const [format, setFormat] = useState<FhirExportFormat>("fhir_json");
  const [includeDocuments, setIncludeDocuments] = useState(true);
  const [includePrescriptions, setIncludePrescriptions] = useState(true);
  const [includeSoapNote, setIncludeSoapNote] = useState(true);

  const [checkingConsent, setCheckingConsent] = useState(false);
  const [consentStatus, setConsentStatus] = useState<ConsentVerificationResult | null>(null);

  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successNotice, setSuccessNotice] = useState<string | null>(null);
  const [showPreview, setShowPreview] = useState(false);

  // Check feature flag and consent on open
  useEffect(() => {
    if (!open) return;
    const isFlagOn = isFhirEncounterExportEnabled();
    setEnabled(isFlagOn);
    setError(null);
    setSuccessNotice(null);

    let active = true;
    setCheckingConsent(true);
    verifyExportConsent(purpose, profileId)
      .then((res) => {
        if (active) {
          setConsentStatus(res);
          if (!res.allowed) {
            setError(res.reason || (isEn ? "Medical consent required." : "Cần xác nhận đồng thuận y tế."));
          }
        }
      })
      .catch((err) => {
        if (active) {
          setError(err instanceof Error ? err.message : String(err));
        }
      })
      .finally(() => {
        if (active) setCheckingConsent(false);
      });

    return () => {
      active = false;
    };
  }, [open, purpose, profileId, isEn]);

  const activeDocuments = useMemo(() => {
    return visit.documents && visit.documents.length > 0 ? visit.documents : documents;
  }, [visit.documents, documents]);

  const previewBundle = useMemo(() => {
    if (!open) return null;
    try {
      const mergedVisit: Partial<Visit> = {
        ...visit,
        documents: activeDocuments,
      };
      const opts: FhirEncounterExportOptions = {
        purpose,
        format,
        profileId,
        includeDocuments,
        includePrescriptions,
        includeSoapNote,
      };
      return buildEncounterExportBundle(mergedVisit, opts);
    } catch {
      return null;
    }
  }, [open, visit, activeDocuments, purpose, format, profileId, includeDocuments, includePrescriptions, includeSoapNote]);

  const handleDownload = async () => {
    if (!enabled) {
      setError(
        isEn
          ? "FHIR Encounter Export is currently in preview/disabled."
          : "Tính năng xuất FHIR Encounter đang trong giai đoạn thử nghiệm (Feature disabled).",
      );
      return;
    }

    if (consentStatus && !consentStatus.allowed) {
      setError(
        consentStatus.reason ||
          (isEn ? "Cannot export: active medical consent required." : "Không thể xuất: yêu cầu đồng thuận y tế còn hiệu lực."),
      );
      return;
    }

    setExporting(true);
    setError(null);
    setSuccessNotice(null);

    try {
      if (!previewBundle) {
        throw new Error(isEn ? "Failed to build FHIR bundle." : "Không thể tạo FHIR Bundle.");
      }

      const filename = sanitizeExportFilename(
        `encounter-${visit.id || "summary"}-${purpose}`,
        format === "ndjson" ? "ndjson" : "fhir.json",
      );

      downloadFhirBundle(previewBundle, filename);

      setSuccessNotice(
        isEn
          ? `Successfully generated ${filename} (${previewBundle.entry.length} resources).`
          : `Đã xuất thành công ${filename} (${previewBundle.entry.length} tài nguyên FHIR).`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : (isEn ? "Export failed." : "Xuất dữ liệu thất bại."));
    } finally {
      setExporting(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEn ? "Export FHIR R4 Encounter & Documents" : "Xuất hồ sơ lượt khám & tài liệu (FHIR R4)"}
      size="lg"
    >
      <div className="space-y-5 pt-1" data-testid="fhir-encounter-export-dialog">
        {/* Feature Flag Banner (if disabled) */}
        {!enabled ? (
          <div
            className="flex items-start gap-3 rounded-[var(--radius-lg)] border border-[var(--status-warning-border)] bg-[var(--status-warning-bg)] p-3.5 text-xs text-[var(--status-warning-text)]"
            data-testid="fhir-export-disabled-banner"
          >
            <Icon name="warning" size="1.1rem" className="shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="font-bold">
                {isEn ? "Feature in Preview Mode" : "Tính năng đang trong giai đoạn thử nghiệm"}
              </p>
              <p className="leading-relaxed opacity-90">
                {isEn
                  ? "FHIR R4 Encounter export is currently locked behind flag false pending clinical interoperability sign-off. Bundle structure preview is available below."
                  : "Tính năng xuất FHIR R4 Encounter đang được khóa sau cờ kiểm thử cho đến khi hoàn tất phê duyệt liên thông lâm sàng. Quý vị có thể xem trước cấu trúc Bundle bên dưới."}
              </p>
            </div>
          </div>
        ) : null}

        {/* Consent Status Indicator */}
        <div
          className={`flex items-center justify-between rounded-[var(--radius-md)] border p-3 text-xs ${
            consentStatus?.allowed
              ? "border-[var(--status-success-border)] bg-[var(--status-success-bg)] text-[var(--status-success-text)]"
              : "border-[var(--status-error-border)] bg-[var(--status-error-bg)] text-[var(--status-error-text)]"
          }`}
          data-testid="fhir-export-consent-indicator"
        >
          <div className="flex items-center gap-2">
            <Icon
              name={consentStatus?.allowed ? "check" : "warning"}
              size="1rem"
              className="shrink-0"
            />
            <span>
              {checkingConsent
                ? (isEn ? "Verifying medical consent..." : "Đang kiểm tra đồng thuận y tế...")
                : consentStatus?.allowed
                  ? (isEn ? "Medical consent verified (Ready for export)" : "Đồng thuận y tế hợp lệ (Sẵn sàng xuất hồ sơ)")
                  : (isEn ? "Medical consent required before export" : "Yêu cầu xác nhận đồng thuận trước khi xuất hồ sơ")}
            </span>
          </div>
          {consentStatus?.policy_type ? (
            <Badge tone={consentStatus.allowed ? "ok" : "warn"}>
              {consentStatus.policy_type}
            </Badge>
          ) : null}
        </div>

        {/* Purpose and Format Selection */}
        <div className="grid gap-4 sm:grid-cols-2">
          {/* Purpose */}
          <div className="space-y-1.5">
            <label className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">
              {isEn ? "Export Purpose" : "Mục đích xuất hồ sơ"}
            </label>
            <select
              value={purpose}
              onChange={(e) => setPurpose(e.target.value as FhirExportPurpose)}
              className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2.5 text-xs text-[var(--text-primary)] focus:border-[var(--brand-500)] focus:outline-none"
              data-testid="fhir-export-purpose-select"
            >
              <option value="self_download">
                {isEn ? "Personal Copy (Self-Download)" : "Lưu trữ cá nhân (Tự tải về)"}
              </option>
              <option value="care_coordination">
                {isEn ? "Care Coordination (Referral / Clinic)" : "Liên thông điều trị (Chuyển tuyến / Phòng khám)"}
              </option>
              <option value="legal_record">
                {isEn ? "Official Medical Record Extract" : "Trích lục hồ sơ bệnh án"}
              </option>
              <option value="audit">
                {isEn ? "Compliance & Security Audit" : "Kiểm toán bảo mật & tuân thủ"}
              </option>
            </select>
          </div>

          {/* Format */}
          <div className="space-y-1.5">
            <label className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">
              {isEn ? "Serialization Format" : "Định dạng dữ liệu"}
            </label>
            <select
              value={format}
              onChange={(e) => setFormat(e.target.value as FhirExportFormat)}
              className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2.5 text-xs text-[var(--text-primary)] focus:border-[var(--brand-500)] focus:outline-none"
              data-testid="fhir-export-format-select"
            >
              <option value="fhir_json">
                {isEn ? "FHIR R4 JSON Bundle (Standard)" : "FHIR R4 JSON Bundle (Chuẩn HL7)"}
              </option>
              <option value="ndjson">
                {isEn ? "Newline Delimited JSON (NDJSON Bulk)" : "Newline Delimited JSON (NDJSON)"}
              </option>
              <option value="fhir_composition">
                {isEn ? "FHIR Composition + Encounter" : "FHIR Composition + Lượt khám"}
              </option>
            </select>
          </div>
        </div>

        {/* Resources Included Checklist */}
        <div className="space-y-2 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)]/60 bg-[var(--surface-muted)]/30 p-3.5 text-xs">
          <p className="font-bold text-[var(--text-primary)]">
            {isEn ? "Included FHIR Resources:" : "Các tài nguyên FHIR bao gồm trong gói xuất:"}
          </p>
          <div className="grid gap-2 sm:grid-cols-2 pt-1">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked disabled className="rounded text-[var(--brand-600)]" />
              <span className="font-medium text-[var(--text-primary)]">
                FHIR Encounter <span className="text-[var(--text-muted)]">({visit.title || "Consultation"})</span>
              </span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={includeSoapNote}
                onChange={(e) => setIncludeSoapNote(e.target.checked)}
                className="rounded text-[var(--brand-600)]"
              />
              <span className="font-medium text-[var(--text-primary)]">
                FHIR Composition <span className="text-[var(--text-muted)]">(SOAP Note)</span>
              </span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={includePrescriptions}
                onChange={(e) => setIncludePrescriptions(e.target.checked)}
                className="rounded text-[var(--brand-600)]"
              />
              <span className="font-medium text-[var(--text-primary)]">
                MedicationStatements <span className="text-[var(--text-muted)]">({visit.prescriptions?.length || 0})</span>
              </span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={includeDocuments}
                onChange={(e) => setIncludeDocuments(e.target.checked)}
                className="rounded text-[var(--brand-600)]"
              />
              <span className="font-medium text-[var(--text-primary)]">
                DocumentReferences <span className="text-[var(--text-muted)]">({activeDocuments.length})</span>
              </span>
            </label>
          </div>
        </div>

        {/* Feedback Notices */}
        {error ? (
          <div
            className="rounded-[var(--radius-md)] border border-[var(--status-error-border)] bg-[var(--status-error-bg)] p-3 text-xs text-[var(--status-error-text)] font-medium"
            data-testid="fhir-export-error-message"
          >
            {error}
          </div>
        ) : null}

        {successNotice ? (
          <div
            className="rounded-[var(--radius-md)] border border-[var(--status-success-border)] bg-[var(--status-success-bg)] p-3 text-xs text-[var(--status-success-text)] font-medium"
            data-testid="fhir-export-success-message"
          >
            {successNotice}
          </div>
        ) : null}

        {/* JSON Preview Accordion */}
        <div className="space-y-1.5 border-t border-[color:var(--shell-border)]/50 pt-2">
          <button
            type="button"
            onClick={() => setShowPreview((v) => !v)}
            className="flex items-center gap-1.5 text-xs font-semibold text-[var(--text-brand)] hover:underline"
          >
            <Icon name={showPreview ? "chevron-down" : "arrow-right"} size="0.85rem" />
            <span>
              {showPreview
                ? (isEn ? "Hide FHIR Bundle JSON Preview" : "Ẩn bản xem trước JSON")
                : (isEn ? "Show FHIR Bundle JSON Preview" : "Xem trước cấu trúc FHIR Bundle")}
            </span>
          </button>

          {showPreview && previewBundle ? (
            <pre className="max-h-48 overflow-auto rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 text-[11px] font-mono text-[var(--text-secondary)]">
              {JSON.stringify(previewBundle, null, 2)}
            </pre>
          ) : null}
        </div>

        {/* Modal Actions */}
        <div className="flex flex-wrap items-center justify-end gap-2.5 pt-3 border-t border-[color:var(--shell-border)]/50">
          <Button type="button" variant="ghost" onClick={onClose}>
            {isEn ? "Close" : "Đóng"}
          </Button>

          <Button
            type="button"
            variant="primary"
            icon="clinical-notes"
            disabled={!enabled || (consentStatus !== null && !consentStatus.allowed) || exporting}
            onClick={handleDownload}
            data-testid="fhir-export-download-btn"
          >
            {exporting
              ? (isEn ? "Generating FHIR Bundle..." : "Đang tạo FHIR Bundle...")
              : (isEn ? "Download FHIR Bundle" : "Tải xuống FHIR Bundle")}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

export default FhirEncounterExportDialog;
