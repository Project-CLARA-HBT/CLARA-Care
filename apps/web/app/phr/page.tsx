"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import PageShell from "@/components/ui/page-shell";
import Button from "@/components/ui/button";
import Icon, { type IconName } from "@/components/ui/icon";
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
import { formatLocaleDate, t, type UITranslationKey } from "@/lib/i18n/catalog";
import { safeUserFacingError } from "@/lib/user-facing-text";
import type { PhrInformationSource, PhrVerificationStatus } from "@/lib/phr";
import OcrReviewModal from "@/components/phr/ocr-review-modal";
import PhrExportButton from "@/components/phr/export-button";
import ShareManager from "@/components/phr/share-manager";
import EmergencyCardEditor from "@/components/phr/emergency-card-editor";
import RemindersPanel from "@/components/phr/reminders-panel";

const COMPLETENESS_CLASS_LABEL_KEYS: Record<PhrCompletenessClass, UITranslationKey> = {
  patient_demographics: "phr.completeness.class.patientDemographics",
  allergies: "phr.completeness.class.allergies",
  medications: "phr.completeness.class.medications",
  problems: "phr.completeness.class.problems",
  immunizations: "phr.completeness.class.immunizations",
  procedures: "phr.completeness.class.procedures",
  labs: "phr.completeness.class.labs",
};

const SOURCE_LABEL_KEYS: Record<PhrInformationSource, UITranslationKey> = {
  "self-declared": "phr.source.selfDeclared",
  ocr: "phr.source.ocr",
  imported: "phr.source.imported",
};

const VERIFICATION_LABEL_KEYS: Record<PhrVerificationStatus, UITranslationKey> = {
  unconfirmed: "phr.verification.unconfirmed",
  confirmed: "phr.verification.confirmed",
  provisional: "phr.verification.provisional",
  refuted: "phr.verification.refuted",
  "entered-in-error": "phr.verification.enteredInError",
};

const PHR_TEXT_KEYS = {
  title: "phr.title", description: "phr.description", save: "phr.action.save",
  saving: "phr.action.saving", loading: "phr.loading", loadError: "phr.error.load",
  saveOk: "phr.notice.saved", saveError: "phr.error.save", profile: "phr.profile",
  allergies: "phr.allergies", conditions: "phr.conditions", medications: "phr.medications",
  add: "phr.action.add", remove: "phr.action.remove", fullName: "phr.field.fullName",
  dob: "phr.field.dob", gender: "phr.field.gender", bloodType: "phr.field.bloodType",
  height: "phr.field.height", weight: "phr.field.weight", phone: "phr.field.phone",
  address: "phr.field.address", emergencyName: "phr.field.emergencyName",
  emergencyPhone: "phr.field.emergencyPhone", insurance: "phr.field.insurance",
  notes: "phr.field.notes", allergyName: "phr.field.allergyName", reaction: "phr.field.reaction",
  severity: "phr.field.severity", conditionName: "phr.field.conditionName", status: "phr.field.status",
  diagnosedOn: "phr.field.diagnosedOn", medicationName: "phr.field.medicationName",
  dose: "phr.field.dose", frequency: "phr.field.frequency", startedOn: "phr.field.startedOn",
  current: "phr.field.current", itemNote: "phr.field.itemNote", updatedAt: "phr.updatedAt",
  unknown: "phr.unknown", disclaimer: "phr.disclaimer", source: "phr.source.label",
  verification: "phr.verification.label", consentTitle: "phr.consent.title",
  consentBody: "phr.consent.body", consentLink: "phr.consent.link",
  completenessTitle: "phr.completeness.title", completenessDescription: "phr.completeness.description",
  completenessLoading: "phr.completeness.loading", completenessError: "phr.completeness.error",
  completenessComplete: "phr.completeness.complete", completenessPresent: "phr.completeness.present",
  completenessMissing: "phr.completeness.missing",
} as const satisfies Record<string, UITranslationKey>;

type PhrText = { [Key in keyof typeof PHR_TEXT_KEYS]: string };

function getPhrText(language: UILanguage): PhrText {
  return Object.fromEntries(
    Object.entries(PHR_TEXT_KEYS).map(([name, key]) => [name, t(language, key as UITranslationKey)]),
  ) as PhrText;
}

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
          {sourceLabel}: {t(uiLanguage, SOURCE_LABEL_KEYS[source])}
        </Badge>
      ) : null}
      {verification ? (
        <Badge tone="neutral">
          {verificationLabel}: {t(uiLanguage, VERIFICATION_LABEL_KEYS[verification])}
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
  text: PhrText;
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
                        {t(uiLanguage, COMPLETENESS_CLASS_LABEL_KEYS[cls])}
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
                        {t(uiLanguage, COMPLETENESS_CLASS_LABEL_KEYS[cls])}
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
  record,
  loading,
  error,
}: {
  text: PhrText;
  uiLanguage: UILanguage;
  capabilities: PhrCapabilityFlags;
  record: PhrRecord;
  loading: boolean;
  error: string;
}) {
  const copy = useCallback(
    (key: UITranslationKey) => t(uiLanguage, key),
    [uiLanguage],
  );
  type HubItem = {
    href: string;
    icon: IconName;
    title: string;
    description: string;
    complete?: boolean;
  };

  const sections: HubItem[] = [
    {
      href: "/phr/identity",
      icon: "user-card",
      title: copy("phr.hub.identity.title"),
      description: copy("phr.hub.identity.description"),
      complete: Boolean(record.full_name.trim() && record.date_of_birth),
    },
    {
      href: "/phr/body",
      icon: "body",
      title: copy("phr.hub.body.title"),
      description: copy("phr.hub.body.description"),
      complete: record.height_cm !== null && record.weight_kg !== null,
    },
    {
      href: "/phr/contact",
      icon: "contact",
      title: copy("phr.hub.contact.title"),
      description: copy("phr.hub.contact.description"),
      complete: Boolean(record.phone.trim() || record.emergency_contact_phone.trim()),
    },
    {
      href: "/phr/allergies",
      icon: "warning",
      title: text.allergies,
      description: copy("phr.hub.allergies.description"),
      complete: record.allergies.length > 0,
    },
    {
      href: "/phr/conditions",
      icon: "clinical-notes",
      title: text.conditions,
      description: copy("phr.hub.conditions.description"),
      complete: record.conditions.length > 0,
    },
    {
      href: "/phr/medications",
      icon: "medication",
      title: text.medications,
      description: copy("phr.hub.medications.description"),
      complete: record.medications.length > 0,
    },
  ];

  const tools: HubItem[] = [
    capabilities.completeness_meter
      ? {
          href: "/phr/status",
          icon: "progress" as const,
          title: text.completenessTitle,
          description: copy("phr.hub.status.description"),
        }
      : null,
    capabilities.ocr_import
      ? {
          href: "/phr/ocr",
          icon: "scan" as const,
          title: copy("phr.hub.ocr.title"),
          description: copy("phr.hub.ocr.description"),
        }
      : null,
    capabilities.export
      ? {
          href: "/phr/export",
          icon: "download",
          title: copy("phr.hub.export.title"),
          description: copy("phr.hub.export.description"),
        }
      : null,
    capabilities.sharing
      ? {
          href: "/phr/sharing",
          icon: "share",
          title: copy("phr.hub.sharing.title"),
          description: copy("phr.hub.sharing.description"),
        }
      : null,
    capabilities.enhanced
      ? {
          href: "/phr/emergency-card",
          icon: "emergency",
          title: copy("phr.hub.emergencyCard.title"),
          description: copy("phr.hub.emergencyCard.description"),
        }
      : null,
    capabilities.reminders
      ? {
          href: "/phr/reminders",
          icon: "notifications" as const,
          title: copy("phr.hub.reminders.title"),
          description: copy("phr.hub.reminders.description"),
        }
      : null,
  ].filter((tool): tool is HubItem => tool !== null);
  const completed = sections.filter((item) => item.complete).length;
  const nextSection = sections.find((item) => !item.complete) ?? sections[0];
  const renderSectionRows = (items: HubItem[]) => items.map((item) => (
    <Button key={item.href} as="link" href={item.href} variant="secondary" className="h-auto min-h-[76px] w-full justify-start whitespace-normal p-4 text-left">
      <span className="flex w-full items-center gap-3">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-[var(--radius-lg)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"><Icon name={item.icon} size={21} /></span>
        <span className="min-w-0 flex-1"><span className="block text-sm font-bold text-[var(--text-primary)]">{item.title}</span><span className="mt-1 block text-[13px] font-normal leading-5 text-[var(--text-secondary)]">{item.description}</span></span>
        <span className={`shrink-0 text-xs font-semibold ${item.complete ? "text-[var(--status-ok-text)]" : "text-[var(--text-muted)]"}`}>{item.complete ? copy("phr.hub.status.complete") : copy("phr.hub.status.incomplete")}</span>
      </span>
    </Button>
  ));

  return (
    <PageShell variant="plain" title={text.title} description={text.description}>
      <div className="space-y-5">
        {error ? <p role="alert" className="rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 py-3 text-sm text-[var(--status-danger-text)]">{error}</p> : null}
        <section className="chrome-panel rounded-[var(--radius-xl)] p-5 sm:p-6" aria-label={copy("phr.hub.progress.label")}>
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">{copy("phr.hub.progress.eyebrow")}</p>
              <h2 className="mt-2 text-xl font-semibold text-[var(--text-primary)]">{t(uiLanguage, "phr.hub.progress.title", { completed, total: sections.length })}</h2>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">{copy("phr.hub.progress.description")}</p>
            </div>
            {!loading ? <Button as="link" href={nextSection.href} icon="arrow_forward" iconTrailing>{copy("phr.hub.progress.continue")}</Button> : null}
          </div>
          <div className="mt-5 grid grid-cols-6 gap-2" role="progressbar" aria-valuemin={0} aria-valuemax={sections.length} aria-valuenow={completed} aria-label={copy("phr.hub.progress.label")}>
            {sections.map((item) => <span key={item.href} className={`h-2 rounded-full ${item.complete ? "bg-[var(--brand-500)]" : "bg-[var(--surface-muted)]"}`} />)}
          </div>
        </section>
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-6" aria-label={copy("phr.hub.sections.record")}>
            <section className="space-y-2"><h2 className="px-1 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">{copy("phr.hub.sections.personal")}</h2>{renderSectionRows(sections.slice(0, 3))}</section>
            <section className="space-y-2"><h2 className="px-1 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">{copy("phr.hub.sections.important")}</h2>{renderSectionRows(sections.slice(3))}</section>
          </div>
          <aside className="space-y-4">
            <section className="chrome-panel rounded-[var(--radius-xl)] p-5"><span className="material-symbols-outlined text-[var(--text-brand)]" aria-hidden="true">shield_lock</span><h2 className="mt-3 text-lg font-semibold text-[var(--text-primary)]">{text.consentTitle}</h2><p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{text.consentBody}</p><Button as="link" href="/account/consent" variant="secondary" size="sm" className="mt-4">{text.consentLink}</Button></section>
            <p role="note" className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4 text-[13px] leading-6 text-[var(--text-secondary)]">{text.disclaimer}</p>
          </aside>
        </div>
        {tools.length > 0 ? (
          <section aria-label={copy("phr.hub.sections.tools")} className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {tools.map((item) => (
              <Button key={item.href} as="link" href={item.href} variant="ghost" className="h-auto min-h-28 justify-start whitespace-normal p-4 text-left">
                <span className="flex items-start gap-3">
                  <Icon name={item.icon} size={22} className="mt-0.5 text-[var(--text-secondary)]" />
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

  const text = useMemo(() => getPhrText(uiLanguage), [uiLanguage]);
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
  const needsRecord = isHub || isRecordEditor || section === "reminders";

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
      setError(safeUserFacingError(err, text.saveError));
    } finally {
      setSaving(false);
    }
  };

  if (isHub) {
    return <PhrHub text={text} uiLanguage={uiLanguage} capabilities={capabilities} record={record} loading={loading} error={error} />;
  }

  if (!section) {
    return (
      <PageShell
        variant="plain"
        title={t(uiLanguage, "phr.error.sectionNotFound.title")}
        description={t(uiLanguage, "phr.error.sectionNotFound.description")}
      >
        <Button as="link" href="/phr" variant="secondary">
          {t(uiLanguage, "phr.action.backToRecord")}
        </Button>
      </PageShell>
    );
  }

  const sectionCopy: Record<PhrSection, { title: string; description: string }> = {
    identity: {
      title: t(uiLanguage, "phr.hub.identity.title"),
      description: t(uiLanguage, "phr.section.identity.description"),
    },
    body: {
      title: t(uiLanguage, "phr.hub.body.title"),
      description: t(uiLanguage, "phr.section.body.description"),
    },
    contact: {
      title: t(uiLanguage, "phr.hub.contact.title"),
      description: t(uiLanguage, "phr.section.contact.description"),
    },
    allergies: { title: text.allergies, description: t(uiLanguage, "phr.section.allergies.description") },
    conditions: { title: text.conditions, description: t(uiLanguage, "phr.section.conditions.description") },
    medications: { title: text.medications, description: t(uiLanguage, "phr.section.medications.description") },
    status: { title: text.completenessTitle, description: text.completenessDescription },
    ocr: { title: t(uiLanguage, "phr.hub.ocr.title"), description: t(uiLanguage, "phr.section.ocr.description") },
    export: { title: t(uiLanguage, "phr.hub.export.title"), description: t(uiLanguage, "phr.hub.export.description") },
    sharing: { title: t(uiLanguage, "phr.hub.sharing.title"), description: t(uiLanguage, "phr.section.sharing.description") },
    "emergency-card": { title: t(uiLanguage, "phr.hub.emergencyCard.title"), description: t(uiLanguage, "phr.section.emergencyCard.description") },
    reminders: { title: t(uiLanguage, "phr.hub.reminders.title"), description: t(uiLanguage, "phr.section.reminders.description") },
  };
  return (
    <PageShell
      variant="plain"
      title={sectionCopy[section].title}
      description={sectionCopy[section].description}
    >
      <div className="space-y-5">
        <Button as="link" href="/phr" variant="ghost" size="sm" icon="arrow_back">
          {t(uiLanguage, "phr.action.recordHome")}
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
