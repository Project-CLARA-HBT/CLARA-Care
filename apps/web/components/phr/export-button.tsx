"use client";

import { useState } from "react";
import {
  exportPhr,
  PHR_EXPORT_RESOURCES,
  type PhrExportResource,
} from "@/lib/phr";
import type { UILanguage } from "@/lib/ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";

/**
 * FHIR export button (personal-health-record Requirement 11.1–11.4). Lets the
 * owner pick a resource scope and download the record as an
 * `application/fhir+json` bundle. Rendered only when the `export` capability is
 * effective (Requirement 18.1).
 */

const COPY = {
  vi: {
    title: "Xuất hồ sơ (FHIR)",
    description:
      "Tải hồ sơ dưới định dạng FHIR R4 (application/fhir+json) để chia sẻ với cơ sở y tế.",
    scope: "Phạm vi",
    download: "Tải xuống",
    downloading: "Đang xuất...",
    error: "Xuất hồ sơ thất bại.",
  },
  en: {
    title: "Export record (FHIR)",
    description:
      "Download your record as a FHIR R4 bundle (application/fhir+json) to share with a clinic.",
    scope: "Scope",
    download: "Download",
    downloading: "Exporting...",
    error: "Export failed.",
  },
} as const;

const RESOURCE_LABELS: Record<PhrExportResource, Record<UILanguage, string>> = {
  all: { vi: "Toàn bộ", en: "All" },
  patient: { vi: "Bệnh nhân", en: "Patient" },
  allergy: { vi: "Dị ứng", en: "Allergies" },
  condition: { vi: "Bệnh nền", en: "Conditions" },
  medication: { vi: "Thuốc", en: "Medications" },
  observation: { vi: "Chỉ số", en: "Observations" },
};

export default function PhrExportButton({
  uiLanguage,
}: {
  uiLanguage: UILanguage;
}) {
  const text = COPY[uiLanguage];
  const [resource, setResource] = useState<PhrExportResource>("all");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const onDownload = async () => {
    setBusy(true);
    setError("");
    try {
      await exportPhr(resource);
    } catch (err) {
      setError(safeUserFacingError(err, text.error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-2xl border border-[#B6D4FE] bg-white p-5 shadow-sm dark:border-sky-700/60 dark:bg-slate-900/90">
      <p className="text-sm font-semibold text-[var(--text-primary)]">
        {text.title}
      </p>
      <p className="mt-1 text-[13px] leading-6 text-[var(--text-secondary)]">
        {text.description}
      </p>
      <div className="mt-3 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-bold uppercase tracking-[0.08em] text-[#374151] dark:text-slate-200">
            {text.scope}
          </span>
          <select
            className="input"
            value={resource}
            onChange={(e) => setResource(e.target.value as PhrExportResource)}
          >
            {PHR_EXPORT_RESOURCES.map((r) => (
              <option key={r} value={r}>
                {RESOURCE_LABELS[r][uiLanguage]}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={onDownload}
          disabled={busy}
          className="inline-flex min-h-[38px] items-center rounded-lg border border-[#93C5FD] bg-[#EFF6FF] px-4 text-sm font-semibold text-[#1D4ED8] transition hover:bg-[#DBEAFE] disabled:cursor-not-allowed disabled:opacity-60 dark:border-sky-500/70 dark:bg-sky-500/18 dark:text-sky-100"
        >
          {busy ? text.downloading : text.download}
        </button>
      </div>
      {error ? <p className="mt-3 text-sm text-rose-500">{error}</p> : null}
    </section>
  );
}
