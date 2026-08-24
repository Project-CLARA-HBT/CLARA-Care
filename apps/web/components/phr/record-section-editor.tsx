"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import PageShell from "@/components/ui/page-shell";
import Button from "@/components/ui/button";
import Icon from "@/components/ui/icon";
import { Field, Textarea } from "@/components/ui/field";
import { Badge } from "@/components/ui/badge";
import { useShellMode } from "@/components/shell/shell-mode-provider";
import {
  DEFAULT_PHR_CAPABILITIES,
  createPhrBodyMeasurement,
  getPhrBodyMeasurements,
  getPhrCapabilities,
  getPhrCompleteness,
  getPhrRecord,
  type PhrAllergyItem,
  type PhrBodyMeasurement,
  type PhrCapabilityFlags,
  type PhrCompleteness,
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
import { formatLocaleDate, t } from "@/lib/i18n/catalog";
import { safeUserFacingError } from "@/lib/user-facing-text";
import { selectAsyncState, type AsyncState } from "@/components/ui/async-section";
import OcrReviewModal from "@/components/phr/ocr-review-modal";
import PhrExportButton from "@/components/phr/export-button";
import ShareManager from "@/components/phr/share-manager";
import EmergencyCardEditor from "@/components/phr/emergency-card-editor";
import RemindersPanel from "@/components/phr/reminders-panel";
import {
  BodyMassIndexTrend,
  CompletenessMeter,
  EMPTY_RECORD,
  getPhrText,
  makeId,
  normalizeRecord,
  parseInputNumber,
  phrColumnClass,
  phrItemClass,
  phrPanelClass,
  ProvenanceBadges,
  toInputDate,
  type PhrCanonicalSection,
} from "@/components/phr/phr-shared";

export interface RecordSectionEditorProps {
  section: string;
}

export default function RecordSectionEditor({
  section: initialSection,
}: RecordSectionEditorProps) {
  const router = useRouter();
  const { setMode } = useShellMode();

  useEffect(() => {
    setMode("focus");
  }, [setMode]);

  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");
  const [record, setRecord] = useState<PhrRecord>(EMPTY_RECORD);
  const [initialRecord, setInitialRecord] = useState<PhrRecord>(EMPTY_RECORD);
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
  const [bodyMeasurements, setBodyMeasurements] = useState<
    PhrBodyMeasurement[]
  >([]);
  const [bodyMeasurementsLoading, setBodyMeasurementsLoading] = useState(false);
  const [bodyMeasurementSaving, setBodyMeasurementSaving] = useState(false);
  const [bodyMeasurementDate, setBodyMeasurementDate] = useState("");

  const text = useMemo(() => getPhrText(uiLanguage), [uiLanguage]);
  const section = (initialSection || "").toLowerCase().trim();

  useEffect(() => {
    setUiLanguage(getStoredUILanguage());
    return onUILanguageChange(setUiLanguage);
  }, []);

  useEffect(() => {
    let mounted = true;
    getPhrCapabilities().then((flags) => {
      if (mounted) setCapabilities(flags);
    });
    return () => {
      mounted = false;
    };
  }, []);

  const isRecordEditor = [
    "identity",
    "demographics",
    "body",
    "measurements",
    "contact",
    "allergies",
    "conditions",
    "medications",
  ].includes(section);

  const needsRecord = isRecordEditor || section === "reminders";

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
        const normalized = normalizeRecord(data);
        setRecord(normalized);
        setInitialRecord(normalized);
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

  const reloadRecord = useCallback(async () => {
    try {
      const data = await getPhrRecord();
      const normalized = normalizeRecord(data);
      setRecord(normalized);
      setInitialRecord(normalized);
    } catch {
      setError(text.loadError);
    }
  }, [text.loadError]);

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

  useEffect(() => {
    let mounted = true;
    const isBodySection = section === "body" || section === "measurements";
    if (!isBodySection || !capabilities.observations) {
      setBodyMeasurements([]);
      return () => {
        mounted = false;
      };
    }
    setBodyMeasurementsLoading(true);
    getPhrBodyMeasurements()
      .then((items) => {
        if (mounted) setBodyMeasurements(items);
      })
      .catch(() => {
        if (mounted) setBodyMeasurements([]);
      })
      .finally(() => {
        if (mounted) setBodyMeasurementsLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [capabilities.observations, section]);

  const completenessState: AsyncState<PhrCompleteness> = selectAsyncState({
    loading: completenessLoading,
    error: completenessError || null,
    data: completeness,
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
      allergy_status: "recorded",
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

  const saveBodyMeasurement = async () => {
    const heightCm = record.height_cm;
    const weightKg = record.weight_kg;
    if (heightCm == null || weightKg == null) {
      setError(text.saveError);
      return;
    }
    setBodyMeasurementSaving(true);
    setMessage("");
    setError("");
    try {
      const created = await createPhrBodyMeasurement({
        height_cm: heightCm,
        weight_kg: weightKg,
        ...(bodyMeasurementDate ? { observed_on: bodyMeasurementDate } : {}),
      });
      setBodyMeasurements((previous) => [
        created,
        ...previous.filter((item) => item.observed_on !== created.observed_on),
      ]);
      setRecord((previous) => ({
        ...previous,
        height_cm: created.height_cm,
        weight_kg: created.weight_kg,
      }));
      setMessage(text.saveOk);
    } catch (err) {
      setError(safeUserFacingError(err, text.saveError));
    } finally {
      setBodyMeasurementSaving(false);
    }
  };

  const persistRecord = async (recordToSave: PhrRecord) => {
    setSaving(true);
    setMessage("");
    setError("");
    try {
      const payload: PhrRecord = {
        ...recordToSave,
        full_name: recordToSave.full_name.trim(),
        gender: recordToSave.gender.trim(),
        blood_type: recordToSave.blood_type.trim().toUpperCase(),
        phone: recordToSave.phone.trim(),
        contact_email: recordToSave.contact_email.trim(),
        address: recordToSave.address.trim(),
        emergency_contact_name: recordToSave.emergency_contact_name.trim(),
        emergency_contact_phone: recordToSave.emergency_contact_phone.trim(),
        emergency_contact_relationship:
          recordToSave.emergency_contact_relationship.trim(),
        emergency_contact_note: recordToSave.emergency_contact_note.trim(),
        insurance_provider: recordToSave.insurance_provider.trim(),
        insurance_id: recordToSave.insurance_id.trim(),
        notes: recordToSave.notes.trim(),
      };
      const saved = await updatePhrRecord(payload);
      const normalized = normalizeRecord(saved);
      setRecord(normalized);
      setInitialRecord(normalized);
      setMessage(text.saveOk);
      void refreshCompleteness();
    } catch (err) {
      setError(safeUserFacingError(err, text.saveError));
    } finally {
      setSaving(false);
    }
  };

  const onSave = async () => {
    await persistRecord(record);
  };

  const onCancel = () => {
    setRecord(initialRecord);
    setMessage("");
    setError("");
    if (router?.push) {
      router.push("/phr");
    } else if (typeof window !== "undefined") {
      window.location.href = "/phr";
    }
  };

  const markNoKnownAllergies = async () => {
    const nextRecord = {
      ...record,
      allergy_status: "none_known" as const,
      allergies: [],
    };
    setRecord(nextRecord);
    await persistRecord(nextRecord);
  };

  const currentMedications = record.medications.filter(
    (item) => item.is_current,
  );
  const pastMedications = record.medications.filter(
    (item) => !item.is_current,
  );

  const sectionCopy: Record<string, { title: string; description: string }> = {
    demographics: {
      title: t(uiLanguage, "phr.hub.identity.title"),
      description: t(uiLanguage, "phr.section.identity.description"),
    },
    identity: {
      title: t(uiLanguage, "phr.hub.identity.title"),
      description: t(uiLanguage, "phr.section.identity.description"),
    },
    measurements: {
      title: t(uiLanguage, "phr.hub.body.title"),
      description: t(uiLanguage, "phr.section.body.description"),
    },
    body: {
      title: t(uiLanguage, "phr.hub.body.title"),
      description: t(uiLanguage, "phr.section.body.description"),
    },
    contact: {
      title: t(uiLanguage, "phr.hub.contact.title"),
      description: t(uiLanguage, "phr.section.contact.description"),
    },
    allergies: {
      title: text.allergies,
      description: t(uiLanguage, "phr.section.allergies.description"),
    },
    conditions: {
      title: text.conditions,
      description: t(uiLanguage, "phr.section.conditions.description"),
    },
    medications: {
      title: text.medications,
      description: t(uiLanguage, "phr.section.medications.description"),
    },
    documents: {
      title: t(uiLanguage, "phr.hub.ocr.title"),
      description: t(uiLanguage, "phr.section.ocr.description"),
    },
    ocr: {
      title: t(uiLanguage, "phr.hub.ocr.title"),
      description: t(uiLanguage, "phr.section.ocr.description"),
    },
    status: {
      title: text.completenessTitle,
      description: text.completenessDescription,
    },
    export: {
      title: t(uiLanguage, "phr.hub.export.title"),
      description: t(uiLanguage, "phr.hub.export.description"),
    },
    sharing: {
      title: t(uiLanguage, "phr.hub.sharing.title"),
      description: t(uiLanguage, "phr.section.sharing.description"),
    },
    "emergency-card": {
      title: t(uiLanguage, "phr.hub.emergencyCard.title"),
      description: t(uiLanguage, "phr.section.emergencyCard.description"),
    },
    reminders: {
      title: t(uiLanguage, "phr.hub.reminders.title"),
      description: t(uiLanguage, "phr.section.reminders.description"),
    },
  };

  const currentCopy = sectionCopy[section];

  if (!currentCopy) {
    return (
      <PageShell
        variant="plain"
        title={t(uiLanguage, "phr.error.sectionNotFound.title")}
        description={t(uiLanguage, "phr.error.sectionNotFound.description")}
      >
        <div className="space-y-4">
          <Button as="link" href="/phr" variant="secondary" icon="arrow_back">
            {t(uiLanguage, "phr.action.backToRecord")}
          </Button>
        </div>
      </PageShell>
    );
  }

  const isDemographicsSection =
    section === "identity" || section === "demographics" || section === "contact";
  const isMeasurementsSection = section === "body" || section === "measurements";
  const isOcrOrDocumentsSection = section === "ocr" || section === "documents";

  return (
    <PageShell
      variant="plain"
      title={currentCopy.title}
      description={currentCopy.description}
    >
      <div className="space-y-6">
        {/* Navigation & Section switcher */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Button
            as="link"
            href="/phr"
            variant="ghost"
            size="sm"
            icon="arrow_back"
          >
            {t(uiLanguage, "phr.action.recordHome")}
          </Button>

          <div className="flex flex-wrap items-center gap-1.5 text-xs text-[var(--text-secondary)]">
            <Link
              href="/phr"
              className="hover:text-[var(--text-primary)] transition"
            >
              PHR
            </Link>
            <span>/</span>
            <span className="font-semibold text-[var(--text-brand)]">
              {currentCopy.title}
            </span>
          </div>
        </div>

        {/* Persistent self-declared, decision-support-only disclaimer */}
        <p
          role="note"
          className="rounded-[var(--radius-lg)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-4 py-3 text-[13px] leading-6 text-[var(--status-warn-text)]"
        >
          {text.disclaimer}
        </p>

        {/* USCDI completeness meter view */}
        {section === "status" && capabilities.completeness_meter ? (
          <CompletenessMeter
            state={completenessState}
            text={text}
            uiLanguage={uiLanguage}
          />
        ) : null}

        {/* Dedicated Document / OCR scan section */}
        {isOcrOrDocumentsSection && capabilities.ocr_import ? (
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

        {/* Export surface */}
        {section === "export" && capabilities.export ? (
          <PhrExportButton uiLanguage={uiLanguage} />
        ) : null}

        {/* Sharing manager surface */}
        {section === "sharing" && capabilities.sharing ? (
          <ShareManager uiLanguage={uiLanguage} />
        ) : null}

        {/* Emergency card surface */}
        {section === "emergency-card" && capabilities.enhanced ? (
          <EmergencyCardEditor uiLanguage={uiLanguage} />
        ) : null}

        {/* Reminders surface */}
        {section === "reminders" && capabilities.reminders ? (
          <RemindersPanel
            uiLanguage={uiLanguage}
            medications={record.medications}
          />
        ) : null}

        {/* Action bar and status indicator for record editors */}
        {isRecordEditor ? (
          <section className={phrPanelClass}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-col gap-1 text-xs text-[var(--text-secondary)]">
                <div>
                  {text.updatedAt}:{" "}
                  {record.updated_at
                    ? formatLocaleDate(uiLanguage, record.updated_at, {
                        dateStyle: "medium",
                        timeStyle: "short",
                      })
                    : text.unknown}
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone="brand">{text.source}: {text.source.includes("Tự") ? "Tự khai báo" : "Self-declared"}</Badge>
                  <Badge tone="neutral">{text.verification}: {text.verification.includes("Xác minh") ? "Đã xác minh" : "Confirmed"}</Badge>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={onCancel}
                  disabled={saving}
                >
                  {text.cancel}
                </Button>
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
            </div>

            {loading ? (
              <p className="mt-3 text-sm text-[var(--text-secondary)]">
                {text.loading}
              </p>
            ) : null}
            {message ? (
              <p className="mt-3 text-sm text-[var(--status-ok-text)]">
                {message}
              </p>
            ) : null}
            {error ? (
              <p role="alert" className="mt-3 text-sm text-[var(--status-danger-text)]">
                {error}
              </p>
            ) : null}
          </section>
        ) : null}

        {/* Section: Demographics / Identity / Contact */}
        {isDemographicsSection ? (
          <section className={phrPanelClass}>
            <p className="mb-4 text-sm font-semibold text-[var(--text-primary)]">
              {currentCopy.title}
            </p>
            <div className="grid gap-4 md:grid-cols-2">
              {(section === "identity" || section === "demographics") ? (
                <>
                  <Field
                    label={text.fullName}
                    value={record.full_name}
                    onChange={(e) => setField("full_name", e.target.value)}
                  />
                  <Field
                    label={text.dob}
                    type="date"
                    value={toInputDate(record.date_of_birth)}
                    onChange={(e) =>
                      setField("date_of_birth", e.target.value || null)
                    }
                  />
                  <Field
                    label={text.gender}
                    value={record.gender}
                    onChange={(e) => setField("gender", e.target.value)}
                  />
                  <Field
                    label={text.bloodType}
                    value={record.blood_type}
                    onChange={(e) => setField("blood_type", e.target.value)}
                  />
                </>
              ) : null}

              {(section === "contact" || section === "demographics") ? (
                <>
                  <p className="md:col-span-2 border-b border-[color:var(--shell-border)] pb-2 text-sm font-semibold text-[var(--text-primary)]">
                    Thông tin liên hệ
                  </p>
                  <Field
                    label={text.phone}
                    value={record.phone}
                    onChange={(e) => setField("phone", e.target.value)}
                  />
                  <Field
                    label="Email"
                    type="email"
                    value={record.contact_email}
                    onChange={(e) =>
                      setField("contact_email", e.target.value)
                    }
                  />
                  <Field
                    label={text.address}
                    wrapperClassName="md:col-span-2"
                    value={record.address}
                    onChange={(e) => setField("address", e.target.value)}
                  />

                  <p className="md:col-span-2 mt-2 border-b border-[color:var(--shell-border)] pb-2 text-sm font-semibold text-[var(--text-primary)]">
                    Liên hệ khẩn cấp
                  </p>
                  <Field
                    label={text.emergencyName}
                    value={record.emergency_contact_name}
                    onChange={(e) =>
                      setField("emergency_contact_name", e.target.value)
                    }
                  />
                  <Field
                    label={text.emergencyPhone}
                    value={record.emergency_contact_phone}
                    onChange={(e) =>
                      setField("emergency_contact_phone", e.target.value)
                    }
                  />
                  <Field
                    label="Mối quan hệ"
                    value={record.emergency_contact_relationship}
                    onChange={(e) =>
                      setField(
                        "emergency_contact_relationship",
                        e.target.value,
                      )
                    }
                  />
                  <Field
                    label="Lưu ý liên hệ khẩn cấp"
                    wrapperClassName="md:col-span-2"
                    value={record.emergency_contact_note}
                    onChange={(e) =>
                      setField("emergency_contact_note", e.target.value)
                    }
                  />

                  <p className="md:col-span-2 mt-2 border-b border-[color:var(--shell-border)] pb-2 text-sm font-semibold text-[var(--text-primary)]">
                    Bảo hiểm y tế
                  </p>
                  <Field
                    label="Nhà cung cấp bảo hiểm"
                    value={record.insurance_provider}
                    onChange={(e) =>
                      setField("insurance_provider", e.target.value)
                    }
                  />
                  <Field
                    label={text.insurance}
                    value={record.insurance_id}
                    onChange={(e) => setField("insurance_id", e.target.value)}
                  />
                  <Field
                    label="Ngày hết hạn bảo hiểm"
                    type="date"
                    value={toInputDate(record.insurance_expiry)}
                    onChange={(e) =>
                      setField("insurance_expiry", e.target.value || null)
                    }
                  />
                  <Textarea
                    label={text.notes}
                    wrapperClassName="md:col-span-2"
                    className="min-h-[84px]"
                    value={record.notes}
                    onChange={(e) => setField("notes", e.target.value)}
                  />
                </>
              ) : null}
            </div>
          </section>
        ) : null}

        {/* Section: Body / Measurements */}
        {isMeasurementsSection ? (
          <section className={phrPanelClass}>
            <p className="mb-4 text-sm font-semibold text-[var(--text-primary)]">
              {currentCopy.title}
            </p>
            <div className="grid gap-4 md:grid-cols-2">
              <Field
                label={text.height}
                inputMode="decimal"
                value={record.height_cm ?? ""}
                onChange={(e) =>
                  setField("height_cm", parseInputNumber(e.target.value))
                }
              />
              <Field
                label={text.weight}
                inputMode="decimal"
                value={record.weight_kg ?? ""}
                onChange={(e) =>
                  setField("weight_kg", parseInputNumber(e.target.value))
                }
              />
              <Field
                label="Ngày đo"
                type="date"
                wrapperClassName="md:col-span-2 md:max-w-[calc(50%-0.5rem)]"
                value={bodyMeasurementDate}
                onChange={(event) =>
                  setBodyMeasurementDate(event.target.value)
                }
              />
            </div>

            <div className="mt-6 border-t border-[color:var(--shell-border)] pt-5">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
                    {text.bodyBmi}
                  </p>
                  {record.height_cm && record.weight_kg ? (
                    <div className="flex items-center gap-3 mt-1">
                      <p className="text-2xl font-semibold tabular-nums text-[var(--text-primary)]">
                        {(
                          record.weight_kg /
                          ((record.height_cm / 100) ** 2)
                        ).toFixed(1)}
                      </p>
                      <Badge tone="brand">
                        BMI {(
                          record.weight_kg /
                          ((record.height_cm / 100) ** 2)
                        ).toFixed(1)}
                      </Badge>
                    </div>
                  ) : (
                    <p className="mt-1 text-sm text-[var(--text-secondary)]">
                      {text.bodyHistoryEmpty}
                    </p>
                  )}
                </div>
                {capabilities.observations ? (
                  <Button
                    type="button"
                    variant="secondary"
                    icon="add"
                    onClick={saveBodyMeasurement}
                    disabled={
                      bodyMeasurementSaving ||
                      record.height_cm === null ||
                      record.weight_kg === null
                    }
                    loading={bodyMeasurementSaving}
                    loadingLabel={text.bodyHistorySaving}
                  >
                    {text.bodyHistorySave}
                  </Button>
                ) : null}
              </div>

              {capabilities.observations ? (
                <div className="mt-5">
                  <p className="text-sm font-semibold text-[var(--text-primary)]">
                    {text.bodyHistory}
                  </p>
                  {bodyMeasurementsLoading ? (
                    <p className="mt-3 text-sm text-[var(--text-secondary)]">
                      {text.loading}
                    </p>
                  ) : bodyMeasurements.length === 0 ? (
                    <p className="mt-3 rounded-[var(--radius-lg)] bg-[var(--surface-muted)] p-4 text-sm leading-6 text-[var(--text-secondary)]">
                      {text.bodyHistoryEmpty}
                    </p>
                  ) : (
                    <>
                      <BodyMassIndexTrend
                        measurements={bodyMeasurements}
                        title={text.bodyTrend}
                        needMore={text.bodyTrendNeedMore}
                      />
                      <ul className="mt-3 divide-y divide-[color:var(--shell-border)] rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]">
                        {bodyMeasurements.map((measurement) => (
                          <li
                            key={measurement.observed_on}
                            className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                          >
                            <span className="text-sm font-semibold text-[var(--text-primary)]">
                              {formatLocaleDate(
                                uiLanguage,
                                measurement.observed_on,
                                { dateStyle: "medium" },
                              )}
                            </span>
                            <span className="text-sm text-[var(--text-secondary)]">
                              {measurement.height_cm} cm ·{" "}
                              {measurement.weight_kg} kg
                            </span>
                            <Badge tone="brand">BMI {measurement.bmi}</Badge>
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                </div>
              ) : null}
            </div>
          </section>
        ) : null}

        {/* Section: Allergies */}
        {section === "allergies" ? (
          <section className="grid gap-4">
            <article className={phrColumnClass}>
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
                {record.allergies.length === 0 ? (
                  <div className="rounded-[var(--radius-xl)] border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-6 text-center">
                    <Icon
                      name="clinical-notes"
                      size={36}
                      className="text-[var(--text-brand)] mx-auto"
                      aria-hidden="true"
                    />
                    <p className="mt-3 text-base font-semibold text-[var(--text-primary)]">
                      {record.allergy_status === "none_known"
                        ? text.allergyEmptyNoneKnown
                        : text.allergyEmptyUnknown}
                    </p>
                    <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[var(--text-secondary)]">
                      {text.noAllergies}
                    </p>
                    <div className="mt-5 flex flex-wrap justify-center gap-3">
                      <Button
                        type="button"
                        size="sm"
                        icon="add"
                        onClick={addAllergy}
                      >
                        {text.add}
                      </Button>
                      {record.allergy_status !== "none_known" ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="secondary"
                          onClick={markNoKnownAllergies}
                          loading={saving}
                        >
                          {text.allergyNoneKnownAction}
                        </Button>
                      ) : null}
                    </div>
                  </div>
                ) : null}
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
            </article>
          </section>
        ) : null}

        {/* Section: Conditions */}
        {section === "conditions" ? (
          <section className="grid gap-4">
            <article className={phrColumnClass}>
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
                {record.conditions.length === 0 ? (
                  <div className="rounded-[var(--radius-lg)] border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-5 text-sm leading-6 text-[var(--text-secondary)]">
                    {text.noConditions}
                  </div>
                ) : null}
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
            </article>
          </section>
        ) : null}

        {/* Section: Medications */}
        {section === "medications" ? (
          <section className="grid gap-4">
            <article className={phrColumnClass}>
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
                {currentMedications.length === 0 ? (
                  <div className="rounded-[var(--radius-lg)] border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-5 text-sm leading-6 text-[var(--text-secondary)]">
                    {text.noMedications}
                  </div>
                ) : null}
                {currentMedications.map((item) => (
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
                          updateMedication(item.id, {
                            frequency: e.target.value,
                          })
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
                {pastMedications.length > 0 ? (
                  <details className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                    <summary className="cursor-pointer text-sm font-semibold text-[var(--text-secondary)]">
                      {text.pastMedications} ({pastMedications.length})
                    </summary>
                    <div className="mt-3 space-y-3">
                      {pastMedications.map((item) => (
                        <div
                          key={item.id}
                          className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-md)] bg-[var(--surface-base)] px-3 py-2 text-sm text-[var(--text-secondary)]"
                        >
                          <span>{item.name || text.unknown}</span>
                          <Button
                            type="button"
                            size="sm"
                            variant="secondary"
                            onClick={() =>
                              updateMedication(item.id, { is_current: true })
                            }
                          >
                            {text.resumeMedication}
                          </Button>
                        </div>
                      ))}
                    </div>
                  </details>
                ) : null}
              </div>
            </article>
          </section>
        ) : null}
      </div>
    </PageShell>
  );
}
