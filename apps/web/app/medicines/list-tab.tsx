"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Field } from "@/components/ui/field";
import { EmptyState, InlineError, LoadingCards, SurfaceCard } from "@/components/ui/surface";
import Icon, { type IconName } from "@/components/ui/icon";
import ActionObject from "@/components/ui/action-object";
import EditorialSection from "@/components/ui/editorial-section";
import { formatLocaleDate, formatLocaleNumber, t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";
import {
  correctMedicationCourse,
  endMedicationCourse,
  getMedicationCourses,
  type MedicationCourse,
} from "@/lib/medication-courses";
import { CabinetItem, getCabinet } from "@/lib/selfmed";
import { requiresTwoMedicines } from "@/lib/careguard";

const FIRST_RUN_ICON: Record<string, IconName> = {
  add_circle: "plus",
  fact_check: "check",
  health_and_safety: "warning",
};

export default function MedicinesListTab() {
  const language = useUILanguage();
  const [courses, setCourses] = useState<MedicationCourse[]>([]);
  const [cabinetItems, setCabinetItems] = useState<CabinetItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Edit form state
  const [name, setName] = useState("");
  const [dose, setDose] = useState("");
  const [schedule, setSchedule] = useState("");
  const [route, setRoute] = useState("");
  const [form, setForm] = useState("");
  const [editing, setEditing] = useState<MedicationCourse | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [coursesData, cabinetData] = await Promise.all([
        getMedicationCourses(),
        getCabinet().catch(() => ({ cabinet_id: 0, label: "", items: [] })),
      ]);
      setCourses(coursesData);
      setCabinetItems(cabinetData.items ?? []);
    } catch (cause) {
      setError(safeUserFacingError(cause, t(language, "medicines.list.loadError")));
    } finally {
      setLoading(false);
    }
  }, [language]);

  useEffect(() => {
    void load();
  }, [load]);

  const clearEditing = () => {
    setEditing(null);
    setName("");
    setDose("");
    setSchedule("");
    setRoute("");
    setForm("");
  };

  const saveCorrection = async (event: FormEvent) => {
    event.preventDefault();
    if (!editing || !name.trim()) return;
    setSaving(true);
    setError("");
    try {
      await correctMedicationCourse(editing.id, editing.version, {
        medication_name: name.trim(),
        dose_text: dose.trim(),
        schedule_text: schedule.trim(),
        route_text: route.trim(),
        form_text: form.trim(),
        reason: t(language, "medicines.list.correctionReason"),
      });
      clearEditing();
      await load();
    } catch (cause) {
      setError(safeUserFacingError(cause, t(language, "medicines.list.saveError")));
    } finally {
      setSaving(false);
    }
  };

  const edit = (course: MedicationCourse) => {
    setEditing(course);
    setName(course.medication_name);
    setDose(course.dose_text);
    setSchedule(course.schedule_text);
    setRoute(course.route_text);
    setForm(course.form_text);
  };

  const end = async (course: MedicationCourse) => {
    if (!window.confirm(t(language, "medicines.list.endConfirm"))) {
      return;
    }
    setSaving(true);
    setError("");
    try {
      await endMedicationCourse(
        course.id,
        course.version,
        t(language, "medicines.list.endReason"),
      );
      await load();
    } catch (cause) {
      setError(safeUserFacingError(cause, t(language, "medicines.list.endError")));
    } finally {
      setSaving(false);
    }
  };

  // Domain 1: Active confirmed medications (taking)
  const activeConfirmedCourses = useMemo(
    () =>
      courses.filter(
        (c) => c.status === "active" && c.reconciliation_status === "matched",
      ),
    [courses],
  );

  // Domain 2: Needs confirmation / unverified proposals (unresolved)
  const unresolvedCourses = useMemo(
    () =>
      courses.filter(
        (c) => c.status === "active" && c.reconciliation_status !== "matched",
      ),
    [courses],
  );

  // Ended / past courses
  const endedCourses = useMemo(
    () => courses.filter((c) => c.status !== "active"),
    [courses],
  );

  // Domain 3: Two-medicine interaction guard
  const distinctMedicineNames = useMemo(() => {
    const names = new Set<string>();
    courses
      .filter((c) => c.status === "active")
      .forEach((c) => {
        if (c.medication_name.trim()) names.add(c.medication_name.trim().toLowerCase());
      });
    cabinetItems.forEach((item) => {
      if (item.drug_name.trim()) names.add(item.drug_name.trim().toLowerCase());
    });
    return Array.from(names);
  }, [cabinetItems, courses]);

  const needsMoreMedicinesForDdi = requiresTwoMedicines(distinctMedicineNames);

  // Domain 4: Cabinet inventory stats & expiry
  const cabinetStats = useMemo(() => {
    const now = Date.now();
    const in30Days = now + 30 * 24 * 60 * 60 * 1000;
    let expired = 0;
    let expiringSoon = 0;
    let missingDosage = 0;

    cabinetItems.forEach((item) => {
      if (!String(item.dosage ?? "").trim()) {
        missingDosage += 1;
      }
      if (!item.expires_on) return;
      const expiresAt = Date.parse(item.expires_on);
      if (!Number.isFinite(expiresAt)) return;
      if (expiresAt < now) {
        expired += 1;
      } else if (expiresAt <= in30Days) {
        expiringSoon += 1;
      }
    });

    return {
      total: cabinetItems.length,
      expired,
      expiringSoon,
      missingDosage,
    };
  }, [cabinetItems]);

  const hasAnyCourses = courses.length > 0;

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="space-y-8">
        {error ? <InlineError message={error} onRetry={() => void load()} /> : null}

        {loading ? (
          <LoadingCards count={3} />
        ) : (
          <>
            {/* ================================================================= */}
            {/* DOMAIN 1: Current / Confirmed Active Medications (taking)         */}
            {/* ================================================================= */}
            <EditorialSection
              id="active-taking-domain"
              data-testid="domain-taking"
              eyebrow={t(language, "medicines.list.active")}
              title={t(language, "medicines.workspace.activeTaking.title")}
              description={t(language, "medicines.workspace.activeTaking.desc")}
              variant="card"
              action={
                hasAnyCourses ? (
                  <div className="flex flex-wrap gap-2">
                    <Button as="link" href="/medicines/add" size="sm" icon="add">
                      {t(language, "medicines.list.addStepByStep")}
                    </Button>
                    <Button
                      as="link"
                      href="/medicines?tab=safety"
                      size="sm"
                      variant="secondary"
                      icon="labs"
                    >
                      {t(language, "medicines.list.openSafety")}
                    </Button>
                  </div>
                ) : null
              }
            >
              {activeConfirmedCourses.length > 0 ? (
                <ul className="divide-y divide-[color:var(--shell-border)]">
                  {activeConfirmedCourses.map((course) => (
                    <li key={course.id} className="flex items-start gap-3.5 py-4 first:pt-1 last:pb-1">
                      <span
                        className="grid h-10 w-10 shrink-0 place-items-center rounded-[var(--radius-lg)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                        aria-hidden="true"
                      >
                        <Icon name="medication" aria-hidden="true" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="font-semibold text-[var(--text-primary)]">
                            {course.medication_name}
                          </p>
                          <Badge tone="brand" icon="check_circle">
                            {t(language, "medicines.list.reconciled")}
                          </Badge>
                        </div>
                        <p className="mt-1 text-sm text-[var(--text-secondary)]">
                          {[
                            course.dose_text,
                            course.schedule_text,
                            course.route_text,
                            course.form_text,
                          ]
                            .filter(Boolean)
                            .join(" · ") || t(language, "medicines.list.noDoseOrSchedule")}
                        </p>
                        {course.drugbank_id ? (
                          <p className="mt-1 text-xs text-[var(--text-muted)]">
                            DrugBank ID: {course.drugbank_id}
                          </p>
                        ) : null}
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-2">
                        <Badge tone="ok" icon="check_circle">
                          {t(language, "medicines.list.active")}
                        </Badge>
                        <div className="flex gap-1">
                          <Button
                            size="sm"
                            variant="ghost"
                            icon="edit"
                            onClick={() => edit(course)}
                          >
                            {t(language, "medicines.list.edit")}
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            icon="stop_circle"
                            onClick={() => void end(course)}
                          >
                            {t(language, "medicines.list.end")}
                          </Button>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : hasAnyCourses ? (
                <div className="rounded-xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-5 text-center">
                  <p className="text-sm text-[var(--text-secondary)]">
                    {t(language, "medicines.workspace.activeTaking.empty")}
                  </p>
                  <Button as="link" href="/medicines/add" size="sm" icon="add" className="mt-3">
                    {t(language, "medicines.list.addStepByStep")}
                  </Button>
                </div>
              ) : (
                <div className="py-6 sm:py-8">
                  <EmptyState
                    icon="medication"
                    title={t(language, "medicines.list.emptyTitle")}
                    description={t(language, "medicines.list.emptyDescription")}
                  >
                    <Button as="link" href="/medicines/add" icon="add">
                      {t(language, "medicines.list.addStepByStep")}
                    </Button>
                  </EmptyState>
                  <ol className="mx-auto mt-8 grid max-w-2xl gap-3 border-t border-[color:var(--shell-border)] pt-6 sm:grid-cols-3">
                    {[
                      ["add_circle", t(language, "medicines.list.firstRun.add")],
                      ["fact_check", t(language, "medicines.list.firstRun.confirm")],
                      ["health_and_safety", t(language, "medicines.list.firstRun.safety")],
                    ].map(([icon, label], index) => (
                      <li
                        key={String(icon)}
                        className="flex items-center gap-3 text-left sm:flex-col sm:text-center"
                      >
                        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-[var(--surface-muted)] text-[var(--text-brand)]">
                          <Icon
                            name={FIRST_RUN_ICON[String(icon)] ?? "clinical-notes"}
                            size={18}
                            aria-hidden="true"
                          />
                        </span>
                        <span className="text-sm text-[var(--text-secondary)]">
                          <span className="mr-1 font-semibold text-[var(--text-primary)]">
                            {index + 1}.
                          </span>
                          {label}
                        </span>
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </EditorialSection>

            {/* ================================================================= */}
            {/* DOMAIN 2: Needs Confirmation / Unverified Proposals (unresolved)  */}
            {/* ================================================================= */}
            <EditorialSection
              id="unresolved-proposals-domain"
              data-testid="domain-unresolved"
              eyebrow={t(language, "medicines.cabinet.normalization.review")}
              title={t(language, "medicines.workspace.unresolved.title")}
              description={t(language, "medicines.workspace.unresolved.desc")}
              variant="card"
            >
              {unresolvedCourses.length > 0 ? (
                <div className="space-y-3">
                  <div className="rounded-xl border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] p-3.5 text-xs font-semibold text-[var(--status-warn-text)]">
                    <p>
                      {t(language, "medicines.workspace.unresolved.pendingCount", {
                        count: formatLocaleNumber(language, unresolvedCourses.length),
                      })}
                    </p>
                  </div>
                  <ul className="divide-y divide-[color:var(--shell-border)]">
                    {unresolvedCourses.map((course) => (
                      <li
                        key={course.id}
                        className="flex items-start gap-3.5 py-4 first:pt-1 last:pb-1"
                      >
                        <span
                          className="grid h-10 w-10 shrink-0 place-items-center rounded-[var(--radius-lg)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]"
                          aria-hidden="true"
                        >
                          <Icon name="warning" aria-hidden="true" />
                        </span>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="font-semibold text-[var(--text-primary)]">
                              {course.medication_name}
                            </p>
                            <Badge tone="warn">
                              {t(language, "medicines.list.notReconciled")}
                            </Badge>
                          </div>
                          <p className="mt-1 text-sm text-[var(--text-secondary)]">
                            {[
                              course.dose_text,
                              course.schedule_text,
                              course.route_text,
                              course.form_text,
                            ]
                              .filter(Boolean)
                              .join(" · ") || t(language, "medicines.list.noDoseOrSchedule")}
                          </p>
                        </div>
                        <div className="flex shrink-0 gap-1">
                          <Button
                            size="sm"
                            variant="secondary"
                            icon="edit"
                            onClick={() => edit(course)}
                          >
                            {t(language, "medicines.list.edit")}
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            icon="stop_circle"
                            onClick={() => void end(course)}
                          >
                            {t(language, "medicines.list.end")}
                          </Button>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <div className="flex items-center gap-3 rounded-xl border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] p-4 text-xs font-semibold text-[var(--status-ok-text)]">
                  <Icon name="check" size={18} />
                  <span>{t(language, "medicines.workspace.unresolved.allReconciled")}</span>
                </div>
              )}
            </EditorialSection>

            {/* ================================================================= */}
            {/* DOMAIN 3: Drug Interaction Safety ActionObject                    */}
            {/* ================================================================= */}
            <div id="ddi-safety-domain" data-testid="domain-safety-action" className="space-y-2">
              <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
                {t(language, "medicines.safety.module")}
              </p>
              <ActionObject
                title={t(language, "medicines.workspace.ddi.title")}
                description={t(language, "medicines.workspace.ddi.desc")}
                badge={t(language, "medicines.workspace.ddi.badge")}
                tone={needsMoreMedicinesForDdi ? "warning" : "brand"}
                icon="labs"
                highlights={[
                  t(language, "medicines.workspace.ddi.highlight1"),
                  t(language, "medicines.workspace.ddi.highlight2"),
                  t(language, "medicines.workspace.ddi.highlight3"),
                ]}
                actionLabel={t(language, "medicines.workspace.ddi.action")}
                href="/medicines?tab=safety"
              >
                <div className="mt-2 rounded-lg border border-[color:var(--shell-border)]/60 bg-[var(--surface-muted)] px-3 py-2 text-xs text-[var(--text-secondary)]">
                  {needsMoreMedicinesForDdi ? (
                    <span className="font-medium text-[var(--status-warn-text)]">
                      {t(language, "medicines.workspace.ddi.needsTwo")}
                    </span>
                  ) : (
                    <span className="font-medium text-[var(--status-ok-text)]">
                      {t(language, "medicines.workspace.ddi.ready", {
                        count: formatLocaleNumber(language, distinctMedicineNames.length),
                      })}
                    </span>
                  )}
                </div>
              </ActionObject>
            </div>

            {/* ================================================================= */}
            {/* DOMAIN 4: Home Medicine Cabinet (cabinet_stored)                  */}
            {/* ================================================================= */}
            <EditorialSection
              id="cabinet-stored-domain"
              data-testid="domain-cabinet-stored"
              eyebrow={t(language, "medicines.cabinet.defaultLabel")}
              title={t(language, "medicines.workspace.cabinet.title")}
              description={t(language, "medicines.workspace.cabinet.desc")}
              variant="card"
              action={
                <div className="flex flex-wrap gap-2">
                  <Button as="link" href="/medicines/cabinet/add" size="sm" icon="add">
                    {t(language, "medicines.workspace.cabinet.add")}
                  </Button>
                  <Button as="link" href="/medicines?tab=cabinet" size="sm" variant="secondary">
                    {t(language, "medicines.workspace.cabinet.viewAll")}
                  </Button>
                </div>
              }
            >
              {/* Invariant callout: possession vs active usage */}
              <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3.5 text-xs text-[var(--text-secondary)]">
                <div className="flex items-start gap-2.5">
                  <Icon name="warning" size={16} className="mt-0.5 shrink-0 text-[var(--text-brand)]" />
                  <p>{t(language, "medicines.workspace.cabinet.disclaimer")}</p>
                </div>
              </div>

              {/* Cabinet metrics summary */}
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                    {t(language, "medicines.cabinet.currentList")}
                  </p>
                  <p className="mt-1 text-base font-bold text-[var(--text-primary)]">
                    {formatLocaleNumber(language, cabinetStats.total)}
                  </p>
                </div>
                <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                    {t(language, "medicines.cabinet.expiry")}
                  </p>
                  <p className="mt-1 text-base font-bold text-[var(--text-primary)]">
                    {cabinetStats.expired > 0 ? (
                      <span className="text-[var(--status-danger-text)]">
                        {t(language, "medicines.cabinet.expiredCount", {
                          count: formatLocaleNumber(language, cabinetStats.expired),
                        })}
                      </span>
                    ) : cabinetStats.expiringSoon > 0 ? (
                      <span className="text-[var(--status-warn-text)]">
                        {t(language, "medicines.cabinet.expiringCount", {
                          count: formatLocaleNumber(language, cabinetStats.expiringSoon),
                        })}
                      </span>
                    ) : (
                      t(language, "medicines.cabinet.noneExpired")
                    )}
                  </p>
                </div>
                <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                    {t(language, "medicines.cabinet.completeness")}
                  </p>
                  <p className="mt-1 text-base font-bold text-[var(--text-primary)]">
                    {cabinetStats.missingDosage > 0
                      ? t(language, "medicines.cabinet.missingDose", {
                          count: formatLocaleNumber(language, cabinetStats.missingDosage),
                        })
                      : t(language, "medicines.cabinet.basicDataReady")}
                  </p>
                </div>
                <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                    {t(language, "medicines.cabinet.defaultLabel")}
                  </p>
                  <Link
                    href="/medicines?tab=cabinet"
                    className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-[var(--text-brand)] hover:underline"
                  >
                    {t(language, "medicines.list.openCabinet")}
                    <Icon name="arrow-right" size={14} />
                  </Link>
                </div>
              </div>

              {/* Quick cabinet items preview */}
              {cabinetItems.length > 0 ? (
                <ul className="divide-y divide-[color:var(--shell-border)]">
                  {cabinetItems.slice(0, 3).map((item) => (
                    <li key={item.id} className="flex items-center justify-between py-3">
                      <div className="min-w-0 flex-1">
                        <p className="font-semibold text-[var(--text-primary)]">{item.drug_name}</p>
                        <p className="text-xs text-[var(--text-secondary)]">
                          {[
                            item.dosage || t(language, "medicines.cabinet.notAvailable"),
                            item.brand_name,
                            item.expires_on
                              ? t(language, "medicines.cabinet.expiryValue", {
                                  date: formatLocaleDate(language, new Date(item.expires_on)),
                                })
                              : null,
                          ]
                            .filter(Boolean)
                            .join(" · ")}
                        </p>
                      </div>
                      <Badge tone={item.source === "ocr" ? "brand" : "neutral"}>
                        {item.source === "ocr" ? "OCR" : t(language, "medicines.cabinet.source.manual")}
                      </Badge>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="py-2 text-center text-xs text-[var(--text-muted)]">
                  {t(language, "medicines.workspace.cabinet.empty")}
                </p>
              )}
            </EditorialSection>

            {/* Ended / Past courses archive if any */}
            {endedCourses.length > 0 && (
              <EditorialSection
                id="ended-courses-archive"
                eyebrow={t(language, "medicines.list.ended")}
                title={t(language, "medicines.list.ended")}
                variant="subtle"
              >
                <ul className="divide-y divide-[color:var(--shell-border)]/60">
                  {endedCourses.map((course) => (
                    <li key={course.id} className="flex items-center justify-between py-3">
                      <div>
                        <p className="font-medium text-[var(--text-secondary)] line-through">
                          {course.medication_name}
                        </p>
                        <p className="text-xs text-[var(--text-muted)]">
                          {course.dose_text || t(language, "medicines.list.noDoseOrSchedule")}
                        </p>
                      </div>
                      <Badge tone="neutral">{t(language, "medicines.list.ended")}</Badge>
                    </li>
                  ))}
                </ul>
              </EditorialSection>
            )}
          </>
        )}
      </div>

      {/* Aside: Edit form & Context panel */}
      <aside className="space-y-6">
        {editing ? (
          <SurfaceCard className="p-5">
            <h2 className="font-semibold text-[var(--text-primary)]">
              {t(language, "medicines.list.editTitle")}
            </h2>
            <p className="mt-1 text-sm leading-5 text-[var(--text-secondary)]">
              {t(language, "medicines.list.formDescription")}
            </p>
            <form className="mt-4 space-y-3.5" onSubmit={(event) => void saveCorrection(event)}>
              <Field
                label={t(language, "medicines.list.medicationName")}
                required
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
              <Field
                label={t(language, "medicines.list.dose")}
                optional
                value={dose}
                onChange={(event) => setDose(event.target.value)}
                placeholder={t(language, "medicines.list.doseExample")}
              />
              <Field
                label={t(language, "medicines.list.schedule")}
                optional
                value={schedule}
                onChange={(event) => setSchedule(event.target.value)}
                placeholder={t(language, "medicines.list.scheduleExample")}
              />
              <Field
                label={t(language, "medicines.list.route")}
                optional
                value={route}
                onChange={(event) => setRoute(event.target.value)}
                placeholder={t(language, "medicines.list.routeExample")}
              />
              <Field
                label={t(language, "medicines.list.form")}
                optional
                value={form}
                onChange={(event) => setForm(event.target.value)}
                placeholder={t(language, "medicines.list.formExample")}
              />
              <Button
                type="submit"
                variant="secondary"
                block
                loading={saving}
                loadingLabel={t(language, "medicines.list.saving")}
                icon="save"
              >
                {t(language, "medicines.list.saveNew")}
              </Button>
              <Button type="button" variant="ghost" block onClick={clearEditing}>
                {t(language, "medicines.list.cancelEdit")}
              </Button>
            </form>
          </SurfaceCard>
        ) : null}

        <SurfaceCard className="p-5">
          <h2 className="font-semibold text-[var(--text-primary)]">
            {t(language, "medicines.list.cabinetTitle")}
          </h2>
          <p className="mt-1 text-sm leading-5 text-[var(--text-secondary)]">
            {t(language, "medicines.list.cabinetDescription")}
          </p>
          <Link
            href="/medicines?tab=cabinet"
            className="focus-ring mt-4 inline-flex items-center gap-1 rounded-lg text-sm font-semibold text-[var(--text-brand)] hover:underline"
          >
            {t(language, "medicines.list.openCabinet")}
            <Icon name="arrow-right" size={16} aria-hidden="true" />
          </Link>
        </SurfaceCard>
      </aside>
    </div>
  );
}
