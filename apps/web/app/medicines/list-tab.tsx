"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Field } from "@/components/ui/field";
import { EmptyState, InlineError, LoadingCards, SurfaceCard } from "@/components/ui/surface";
import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import {
  checkDrugBankDdi,
  correctMedicationCourse,
  createMedicationCourse,
  endMedicationCourse,
  getMedicationCourses,
  type DrugBankDdiResult,
  type MedicationCourse,
} from "@/lib/medication-courses";

export default function MedicinesListTab() {
  const language = useUILanguage();
  const [courses, setCourses] = useState<MedicationCourse[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<DrugBankDdiResult | null>(null);
  const [name, setName] = useState("");
  const [dose, setDose] = useState("");
  const [schedule, setSchedule] = useState("");
  const [drugbankId, setDrugbankId] = useState("");
  const [route, setRoute] = useState("");
  const [form, setForm] = useState("");
  const [editing, setEditing] = useState<MedicationCourse | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setCourses(await getMedicationCourses());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t(language, "medicines.list.loadError"));
    } finally {
      setLoading(false);
    }
  }, [language]);

  useEffect(() => {
    void load();
  }, [load]);

  const add = async (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setError("");
    try {
      if (editing) {
        await correctMedicationCourse(editing.id, editing.version, {
          medication_name: name.trim(),
          dose_text: dose.trim(),
          schedule_text: schedule.trim(),
          route_text: route.trim(),
          form_text: form.trim(),
          reason: t(language, "medicines.list.correctionReason"),
        });
      } else {
        await createMedicationCourse({
          medication_name: name.trim(),
          dose_text: dose.trim(),
          schedule_text: schedule.trim(),
          route_text: route.trim(),
          form_text: form.trim(),
          drugbank_id: drugbankId.trim() || undefined,
        });
      }
      setName("");
      setDose("");
      setSchedule("");
      setDrugbankId("");
      setRoute("");
      setForm("");
      setEditing(null);
      setResult(null);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t(language, "medicines.list.saveError"));
    } finally {
      setSaving(false);
    }
  };

  const check = async () => {
    setChecking(true);
    setError("");
    setResult(null);
    try {
      setResult(
        await checkDrugBankDdi(
          courses
            .filter((course) => course.status === "active")
            .map((course) => course.id),
        ),
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t(language, "medicines.list.checkError"));
    } finally {
      setChecking(false);
    }
  };

  const edit = (course: MedicationCourse) => {
    setEditing(course);
    setName(course.medication_name);
    setDose(course.dose_text);
    setSchedule(course.schedule_text);
    setRoute(course.route_text);
    setForm(course.form_text);
    setDrugbankId(course.drugbank_id ?? "");
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
      setError(cause instanceof Error ? cause.message : t(language, "medicines.list.endError"));
    } finally {
      setSaving(false);
    }
  };

  const activeCourses = courses.filter((course) => course.status === "active");

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="space-y-5">
        {error ? <InlineError message={error} onRetry={() => void load()} /> : null}

        {loading ? (
          <LoadingCards count={2} />
        ) : (
          <>
            <SurfaceCard className="overflow-hidden">
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
                  <Button
                    size="sm"
                    disabled={activeCourses.length < 2}
                    loading={checking}
                    loadingLabel={t(language, "medicines.list.checkingDrugbank")}
                    onClick={() => void check()}
                    icon="labs"
                  >
                    {t(language, "medicines.list.checkDrugbank")}
                  </Button>
                </div>
              </div>
              {courses.length ? (
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
              ) : (
                <div className="p-5">
                  <EmptyState
                    icon="medication"
                    title={t(language, "medicines.list.emptyTitle")}
                    description={t(language, "medicines.list.emptyDescription")}
                  />
                </div>
              )}
            </SurfaceCard>

            {result ? (
              <SurfaceCard className="p-5">
                <div className="flex items-start gap-3">
                  <span
                    className="material-symbols-outlined text-[var(--status-ok-text)]"
                    aria-hidden="true"
                  >
                    verified
                  </span>
                  <div>
                    <p className="font-semibold text-[var(--text-primary)]">
                      {t(language, "medicines.list.verifiedResult")}
                    </p>
                    <p className="mt-1 text-sm text-[var(--text-secondary)]">
                      {t(language, "medicines.list.sourceVersion", { version: result.source_version })}
                    </p>
                  </div>
                </div>
                {result.ddi_alerts.length ? (
                  <ul className="mt-4 space-y-2">
                    {result.ddi_alerts.map((alert, index) => (
                      <li
                        key={index}
                        className="rounded-[var(--radius-lg)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] p-3 text-sm text-[var(--status-warn-text)]"
                      >
                        <p className="font-semibold">{alert.severity ?? t(language, "medicines.list.alert")}</p>
                        <p className="mt-1">
                          {alert.message ||
                            t(language, "medicines.list.alertFallback")}
                        </p>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-4 rounded-[var(--radius-lg)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] p-3 text-sm text-[var(--status-ok-text)]">
                    {t(language, "medicines.list.noAlerts")}
                  </p>
                )}
                {result.recommendation ? (
                  <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
                    {result.recommendation}
                  </p>
                ) : null}
              </SurfaceCard>
            ) : null}
          </>
        )}
      </div>

      <aside className="space-y-5">
        <SurfaceCard className="p-5">
          <h2 className="font-semibold text-[var(--text-primary)]">
            {editing ? t(language, "medicines.list.editTitle") : t(language, "medicines.list.addTitle")}
          </h2>
          <p className="mt-1 text-sm leading-5 text-[var(--text-secondary)]">
            {t(language, "medicines.list.formDescription")}
          </p>
          <form className="mt-4 space-y-3.5" onSubmit={(event) => void add(event)}>
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
            <Field
              label={t(language, "medicines.list.drugbankId")}
              optional
              value={drugbankId}
              onChange={(event) => setDrugbankId(event.target.value)}
              placeholder="DB…"
            />
            <Button
              type="submit"
              variant="secondary"
              block
              loading={saving}
              loadingLabel={t(language, "medicines.list.saving")}
              icon="save"
            >
              {editing ? t(language, "medicines.list.saveNew") : t(language, "medicines.list.saveConfirmed")}
            </Button>
            {editing ? (
              <Button
                type="button"
                variant="ghost"
                block
                onClick={() => {
                  setEditing(null);
                  setName("");
                  setDose("");
                  setSchedule("");
                  setRoute("");
                  setForm("");
                  setDrugbankId("");
                }}
              >
                {t(language, "medicines.list.cancelEdit")}
              </Button>
            ) : null}
          </form>
        </SurfaceCard>

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
