"use client";

import { useState } from "react";
import {
  exportPhr,
  PHR_EXPORT_RESOURCES,
  type PhrExportResource,
} from "@/lib/phr";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import type { UILanguage } from "@/lib/ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";

/**
 * FHIR export button (personal-health-record Requirement 11.1–11.4). Lets the
 * owner pick a resource scope and download the record as an
 * `application/fhir+json` bundle. Rendered only when the `export` capability is
 * effective (Requirement 18.1).
 */

const RESOURCE_LABEL_KEYS: Record<PhrExportResource, UITranslationKey> = {
  all: "phr.export.resource.all",
  patient: "phr.export.resource.patient",
  allergy: "phr.export.resource.allergy",
  condition: "phr.export.resource.condition",
  medication: "phr.export.resource.medication",
  observation: "phr.export.resource.observation",
};

export default function PhrExportButton({
  uiLanguage,
}: {
  uiLanguage: UILanguage;
}) {
  const copy = (key: UITranslationKey) => t(uiLanguage, key);
  const [resource, setResource] = useState<PhrExportResource>("all");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const onDownload = async () => {
    setBusy(true);
    setError("");
    try {
      await exportPhr(resource);
    } catch (err) {
      setError(safeUserFacingError(err, copy("phr.export.error")));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-[14px] border border-[color:var(--shell-border)] border-t-[#2A3950] bg-[var(--surface-panel)] p-6">
      <p className="text-sm font-semibold text-[var(--text-primary)]">
        {copy("phr.export.title")}
      </p>
      <p className="mt-1 text-[13px] leading-6 text-[var(--text-secondary)]">
        {copy("phr.export.description")}
      </p>
      <div className="mt-3 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-bold uppercase tracking-[0.08em] text-[var(--text-secondary)]">
            {copy("phr.export.scope")}
          </span>
          <select
            className="input"
            value={resource}
            onChange={(e) => setResource(e.target.value as PhrExportResource)}
          >
            {PHR_EXPORT_RESOURCES.map((r) => (
              <option key={r} value={r}>
                {copy(RESOURCE_LABEL_KEYS[r])}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={onDownload}
          disabled={busy}
          className="inline-flex min-h-[38px] items-center rounded-lg bg-[#60a5fa] px-4 text-sm font-semibold text-[#003a6b] transition hover:bg-[#a4c9ff] disabled:cursor-not-allowed disabled:opacity-60"
        >
          {busy ? copy("phr.export.downloading") : copy("phr.export.download")}
        </button>
      </div>
      {error ? <p className="mt-3 text-sm text-[#ffb4ab]">{error}</p> : null}
    </section>
  );
}
