"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Field } from "@/components/ui/field";
import { EmptyState, InlineError, LoadingCards, SurfaceCard } from "@/components/ui/surface";
import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";
import {
  correctMedicationCourse,
  endMedicationCourse,
  getMedicationCourses,
  type MedicationCourse,
} from "@/lib/medication-courses";

export default function MedicinesListTab() {
  const language = useUILanguage();
  const [courses, setCourses] = useState<MedicationCourse[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
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
      setCourses(await getMedicationCourses());
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
    if (
      !window.confirm(
        t(language, "medicines.list.endConfirm"),
      )
    ) {
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

  const hasCourses = courses.length > 0;

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="space-y-5">
        {error ? <InlineError message={error} onRetry={() => void load()} /> : null}

        {loading ? (
          <LoadingCards count={2} />
        ) : (
          <>
            <SurfaceCard className="overflow-hidden">
              {hasCourses ? (
                <>
                  <div className="flex flex-col gap-3 border-b border-[color:var(--shell-border)] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <h2 className="font-semibold text-[var(--text-primary)]">{t(language, "medicines.list.trackedTitle")}</h2>
                      <p className="mt-1 text-sm text-[var(--text-secondary)]">
                        {t(language, "medicines.list.trackedDescription")}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button as="link" href="/medicines/add" size="sm" icon="add">
                        {t(language, "medicines.list.addStepByStep")}
                      </Button>
                      <Button as="link" href="/medicines?tab=safety" size="sm" variant="secondary" icon="labs">
                        {t(language, "medicines.list.openSafety")}
                      </Button>
                    </div>
                  </div>
                <ul className="divide-y divide-[color:var(--shell-border)]">
                  {courses.map((course) => (
                    <li key={course.id} className="flex items-start gap-3 px-5 py-4">
                      <span
                        className="grid h-10 w-10 shrink-0 place-items-center rounded-[var(--radius-lg)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                        aria-hidden="true"
                      >
                        <span className="material-symbols-outlined">medication</span>
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-[var(--text-primary)]">
                          {course.medication_name}
                        </p>
                        <p className="mt-0.5 text-sm text-[var(--text-secondary)]">
                          {[
                            course.dose_text,
                            course.schedule_text,
                            course.route_text,
                            course.form_text,
                          ].filter(Boolean).join(" · ") ||
                            t(language, "medicines.list.noDoseOrSchedule")}
                        </p>
                        {course.drugbank_id ? (
                          <p className="mt-1 text-xs text-[var(--text-muted)]">
                            DrugBank ID: {course.drugbank_id}
                          </p>
                        ) : null}
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-2">
                        <Badge
                          tone={course.status === "active" ? "ok" : "neutral"}
                          icon={course.status === "active" ? "check_circle" : "history"}
                        >
                          {course.status === "active" ? t(language, "medicines.list.active") : t(language, "medicines.list.ended")}
                        </Badge>
                        <Badge
                          tone={
                            course.reconciliation_status === "matched" ? "brand" : "warn"
                          }
                        >
                          {course.reconciliation_status === "matched"
                            ? t(language, "medicines.list.reconciled")
                            : t(language, "medicines.list.notReconciled")}
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
                          {course.status === "active" ? (
                            <Button
                              size="sm"
                              variant="ghost"
                              icon="stop_circle"
                              onClick={() => void end(course)}
                            >
                              {t(language, "medicines.list.end")}
                            </Button>
                          ) : null}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
                </>
              ) : (
                <div className="px-5 py-8 sm:px-8 sm:py-12">
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
                      <li key={String(icon)} className="flex items-center gap-3 text-left sm:flex-col sm:text-center">
                        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-[var(--surface-muted)] text-[var(--text-brand)]">
                          <span className="material-symbols-outlined text-lg" aria-hidden="true">{icon}</span>
                        </span>
                        <span className="text-sm text-[var(--text-secondary)]">
                          <span className="mr-1 font-semibold text-[var(--text-primary)]">{index + 1}.</span>{label}
                        </span>
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </SurfaceCard>

          </>
        )}
      </div>

      <aside className="space-y-5">
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
          <h2 className="font-semibold text-[var(--text-primary)]">{t(language, "medicines.list.cabinetTitle")}</h2>
          <p className="mt-1 text-sm leading-5 text-[var(--text-secondary)]">
            {t(language, "medicines.list.cabinetDescription")}
          </p>
          <Link
            href="/medicines?tab=cabinet"
            className="focus-ring mt-4 inline-flex items-center gap-1 rounded-lg text-sm font-semibold text-[var(--text-brand)] hover:underline"
          >
            {t(language, "medicines.list.openCabinet")}
            <span className="material-symbols-outlined text-base" aria-hidden="true">
              arrow_forward
            </span>
          </Link>
        </SurfaceCard>
      </aside>
    </div>
  );
}
