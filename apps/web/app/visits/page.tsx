"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import PageShell from "@/components/ui/page-shell";
import { Badge } from "@/components/ui/badge";
import Button from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { HeroObject } from "@/components/ui/hero-object";
import {
  Timeline,
  TimelineContent,
  TimelineItem,
  TimelineNode,
} from "@/components/ui/timeline";
import { EmptyState } from "@/components/ui/empty-state";
import { InlineError, LoadingCards, SurfaceCard } from "@/components/ui/surface";
import { formatLocaleDate, t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";
import {
  grantVisitScribeConsent,
  listVisitDocuments,
  listVisits,
  revokeVisitScribeConsent,
  type Visit,
  type VisitDocument,
} from "@/lib/visit-family";

function getPrepStatusTone(status?: string): "ok" | "brand" | "warn" {
  switch (status) {
    case "completed":
    case "ready":
      return "ok";
    case "in_progress":
      return "brand";
    case "not_started":
    default:
      return "warn";
  }
}

function getPrepStatusLabel(
  status: string | undefined,
  copy: (key: UITranslationKey) => string,
): string {
  switch (status) {
    case "completed":
      return copy("visits.prepStatusCompleted");
    case "ready":
      return copy("visits.prepStatusReady");
    case "in_progress":
      return copy("visits.prepStatusInProgress");
    case "not_started":
    default:
      return copy("visits.prepStatusNotStarted");
  }
}

function VisitsTimelineStream() {
  const language = useUILanguage();
  const copy = useCallback(
    (key: UITranslationKey, values?: Record<string, string | number>) =>
      t(language, key, values ?? {}),
    [language],
  );

  const [visits, setVisits] = useState<Visit[]>([]);
  const [documentsMap, setDocumentsMap] = useState<Record<string, VisitDocument[]>>({});
  const [scribeConsents, setScribeConsents] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [savingConsent, setSavingConsent] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await listVisits();
      setVisits(result);

      // Load documents for visits in parallel
      if (result.length > 0) {
        const docEntries = await Promise.all(
          result.map(async (v) => {
            try {
              const docs = await listVisitDocuments(v.id);
              return [v.id, docs] as const;
            } catch {
              return [v.id, []] as const;
            }
          }),
        );
        setDocumentsMap(Object.fromEntries(docEntries));
      }
    } catch (cause) {
      setError(safeUserFacingError(cause, copy("visits.loadError")));
    } finally {
      setLoading(false);
    }
  }, [copy]);

  useEffect(() => {
    void load();
  }, [load]);

  // Identify upcoming visit vs past visits
  const now = useMemo(() => Date.now(), []);

  const upcomingVisit = useMemo(() => {
    if (!visits.length) return null;
    return (
      visits.find((v) => {
        if (v.status === "completed" || v.status === "cancelled") return false;
        if (!v.scheduled_at) return true;
        return new Date(v.scheduled_at).getTime() >= now;
      }) ??
      visits.find((v) => v.status !== "completed") ??
      visits[0]
    );
  }, [visits, now]);

  const pastVisits = useMemo(() => {
    return visits
      .filter((v) => v.id !== upcomingVisit?.id)
      .sort((a, b) => {
        const timeA = a.scheduled_at ? new Date(a.scheduled_at).getTime() : 0;
        const timeB = b.scheduled_at ? new Date(b.scheduled_at).getTime() : 0;
        return timeB - timeA;
      });
  }, [visits, upcomingVisit]);

  const toggleScribeConsent = async (visitId: string) => {
    setSavingConsent(true);
    setError("");
    const isCurrentlyConsented = Boolean(scribeConsents[visitId]);
    try {
      if (isCurrentlyConsented) {
        await revokeVisitScribeConsent(visitId);
      } else {
        await grantVisitScribeConsent(visitId);
      }
      setScribeConsents((current) => ({
        ...current,
        [visitId]: !isCurrentlyConsented,
      }));
    } catch (cause) {
      setError(safeUserFacingError(cause, copy("visits.scribeConsentError")));
    } finally {
      setSavingConsent(false);
    }
  };

  return (
    <PageShell
      variant="plain"
      title={copy("visits.title")}
      description={copy("visits.description")}
    >
      <div className="space-y-8" data-testid="visits-timeline-page">
        {/* 1. Header Row + "Chuẩn bị lần khám mới" CTA */}
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[color:var(--shell-border)] pb-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-brand)]">
              {copy("visits.timelineStream")}
            </p>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              {copy("visits.description")}
            </p>
          </div>
          <Button
            as="link"
            href="/visits/new"
            icon="add"
            variant="primary"
            className="shrink-0"
            data-testid="prepare-new-visit-cta"
          >
            {copy("visits.newVisitCta")}
          </Button>
        </div>

        {/* Inline Error Alert */}
        {error ? <InlineError message={error} onRetry={() => void load()} /> : null}

        {/* Loading State */}
        {loading ? (
          <div className="space-y-4">
            <LoadingCards count={2} />
          </div>
        ) : null}

        {/* 4. Empty State with guidance on how visit preparation works */}
        {!loading && visits.length === 0 ? (
          <div className="space-y-6" data-testid="visits-empty-state">
            <EmptyState
              icon={<Icon name="calendar" size="2rem" />}
              title={copy("visits.emptyTitle")}
              description={copy("visits.emptyDescription")}
              primaryAction={{
                label: copy("visits.newVisitCta"),
                href: "/visits/new",
              }}
            />

            {/* Guidance Section: How visit preparation works */}
            <SurfaceCard className="p-5 sm:p-6 space-y-4 max-w-3xl mx-auto">
              <div className="flex items-center gap-2">
                <Icon name="clinical-notes" size="1.2rem" className="text-[var(--text-brand)]" />
                <h3 className="font-bold text-base text-[var(--text-primary)]">
                  {copy("visits.howPrepWorksTitle")}
                </h3>
              </div>
              <p className="text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed">
                {copy("visits.howPrepWorksDesc")}
              </p>
              <div className="grid gap-3 pt-1 sm:grid-cols-2">
                <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)]/60 bg-[var(--surface-muted)]/40 p-3 text-xs text-[var(--text-secondary)]">
                  {copy("visits.guidanceStep1")}
                </div>
                <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)]/60 bg-[var(--surface-muted)]/40 p-3 text-xs text-[var(--text-secondary)]">
                  {copy("visits.guidanceStep2")}
                </div>
                <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)]/60 bg-[var(--surface-muted)]/40 p-3 text-xs text-[var(--text-secondary)]">
                  {copy("visits.guidanceStep3")}
                </div>
                <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)]/60 bg-[var(--surface-muted)]/40 p-3 text-xs text-[var(--text-secondary)]">
                  {copy("visits.guidanceStep4")}
                </div>
              </div>
            </SurfaceCard>
          </div>
        ) : null}

        {/* 2. Upcoming visit HeroObject */}
        {!loading && upcomingVisit ? (
          <section className="space-y-3" data-testid="upcoming-visit-section">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-brand)]">
                {copy("visits.upcomingEyebrow")}
              </p>
              <Badge tone={getPrepStatusTone(upcomingVisit.prep_status)}>
                {getPrepStatusLabel(upcomingVisit.prep_status, copy)}
              </Badge>
            </div>

            <HeroObject
              id={`upcoming-visit-${upcomingVisit.id}`}
              variant="primary"
              contextTag={copy("visits.upcomingEyebrow")}
              title={upcomingVisit.title}
              description={upcomingVisit.goal || undefined}
              icon="calendar"
              supportingMeta={
                upcomingVisit.scheduled_at ? (
                  <span className="inline-flex items-center gap-1 font-semibold text-[var(--text-brand)]">
                    <Icon name="calendar" size="0.9rem" />
                    <span>
                      {formatLocaleDate(language, upcomingVisit.scheduled_at, {
                        weekday: "short",
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  </span>
                ) : (
                  copy("visits.noScheduledTime")
                )
              }
              primaryAction={{
                label: copy("visits.prepareVisitAction"),
                href: `/visits/new?visit=${encodeURIComponent(upcomingVisit.id)}`,
                icon: "clinical-notes",
                tone: "primary",
              }}
              secondaryAction={{
                label: copy("visits.newVisitCta"),
                href: "/visits/new",
                icon: "add",
                tone: "secondary",
              }}
            >
              <div className="mt-4 space-y-4 border-t border-[color:var(--shell-border)]/60 pt-4">
                {/* Doctor, Specialty, Facility */}
                {(upcomingVisit.doctor_name || upcomingVisit.specialty || upcomingVisit.facility_name) ? (
                  <div className="rounded-[var(--radius-lg)] bg-[var(--surface-muted)]/60 p-3 text-xs space-y-1">
                    {upcomingVisit.doctor_name ? (
                      <p className="font-bold text-[var(--text-primary)]">
                        {upcomingVisit.doctor_name}
                        {upcomingVisit.specialty ? ` • ${upcomingVisit.specialty}` : ""}
                      </p>
                    ) : null}
                    {upcomingVisit.facility_name ? (
                      <p className="text-[var(--text-secondary)]">
                        {upcomingVisit.facility_name}
                        {upcomingVisit.location ? ` (${upcomingVisit.location})` : ""}
                      </p>
                    ) : null}
                  </div>
                ) : null}

                {/* Preparation Pack Status & Questions Ready */}
                <div className="grid gap-3 sm:grid-cols-2 text-xs">
                  <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)]/70 bg-[var(--surface-lowest,#0b0e13)]/40 p-3 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-[var(--text-muted)]">
                        {copy("visits.prepPackStatus")}
                      </span>
                      <Badge tone={getPrepStatusTone(upcomingVisit.prep_status)}>
                        {getPrepStatusLabel(upcomingVisit.prep_status, copy)}
                      </Badge>
                    </div>
                    <p className="text-[11px] text-[var(--text-secondary)]">
                      {copy("visits.controlDescription")}
                    </p>
                  </div>

                  <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)]/70 bg-[var(--surface-lowest,#0b0e13)]/40 p-3 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-[var(--text-muted)]">
                        {copy("visits.questionsReady")}
                      </span>
                      <Badge tone="brand">
                        {upcomingVisit.questions?.length
                          ? copy("visits.questionsCount", { count: upcomingVisit.questions.length })
                          : copy("visits.priorityRoutine")}
                      </Badge>
                    </div>
                    {upcomingVisit.questions && upcomingVisit.questions.length > 0 ? (
                      <ul className="mt-1 space-y-0.5 text-[11px] text-[var(--text-secondary)] list-disc list-inside">
                        {upcomingVisit.questions.slice(0, 2).map((q, idx) => (
                          <li key={idx} className="truncate">{q}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-[11px] text-[var(--text-muted)]">
                        {copy("visits.oneQuestionAtATime")}
                      </p>
                    )}
                  </div>
                </div>

                {/* Scribe Consent Control Context */}
                <div className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)]/40 bg-[var(--surface-muted)]/30 p-3 text-xs">
                  <div>
                    <p className="font-semibold text-[var(--text-primary)]">
                      {copy("visits.scribeTitle")}
                    </p>
                    <p className="text-[11px] text-[var(--text-secondary)]">
                      {copy("visits.scribeDescription")}
                    </p>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant={scribeConsents[upcomingVisit.id] ? "secondary" : "ghost"}
                    disabled={savingConsent}
                    onClick={() => toggleScribeConsent(upcomingVisit.id)}
                  >
                    {scribeConsents[upcomingVisit.id]
                      ? copy("visits.revokeScribeConsent")
                      : copy("visits.grantScribeConsent")}
                  </Button>
                </div>
              </div>
            </HeroObject>
          </section>
        ) : null}

        {/* 3. Chronological Past Visit Timeline Rows */}
        {!loading && pastVisits.length > 0 ? (
          <section className="space-y-4" data-testid="past-visits-timeline-stream">
            <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-3">
              <div className="flex items-center gap-2">
                <Icon name="progress" size="1.1rem" className="text-[var(--text-brand)]" />
                <h2 className="text-base font-bold text-[var(--text-primary)] sm:text-lg">
                  {copy("visits.pastVisitsEyebrow")}
                </h2>
              </div>
              <Badge tone="neutral">
                {pastVisits.length} {copy("visits.listEyebrow").toLowerCase()}
              </Badge>
            </div>

            <Timeline orientation="vertical" className="pl-1 sm:pl-2 pt-2">
              {pastVisits.map((visit, index) => {
                const isLast = index === pastVisits.length - 1;
                const docs = documentsMap[visit.id] || visit.documents || [];
                const formattedTime = visit.scheduled_at
                  ? formatLocaleDate(language, visit.scheduled_at, {
                      dateStyle: "medium",
                      timeStyle: "short",
                    })
                  : copy("visits.noScheduledTime");

                return (
                  <TimelineItem
                    key={visit.id}
                    state="completed"
                    isLast={isLast}
                    className="pb-8"
                    data-testid={`past-visit-item-${visit.id}`}
                  >
                    <TimelineNode state="completed" icon="check" size="md" />
                    <TimelineContent>
                      <article className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5 space-y-3.5 shadow-xs">
                        {/* Visit Title, Specialty & Appointment Time */}
                        <div className="flex flex-wrap items-start justify-between gap-2 border-b border-[color:var(--shell-border)]/40 pb-3">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <h3 className="font-bold text-sm sm:text-base text-[var(--text-primary)]">
                                {visit.title}
                              </h3>
                              <Badge tone="neutral">
                                {visit.visit_type || "Khám chuyên khoa"}
                              </Badge>
                            </div>
                            {(visit.doctor_name || visit.specialty || visit.facility_name) ? (
                              <p className="mt-1 text-xs text-[var(--text-secondary)]">
                                {visit.doctor_name ? (
                                  <span className="font-semibold text-[var(--text-primary)]">
                                    {visit.doctor_name}
                                  </span>
                                ) : null}
                                {visit.specialty ? ` • ${visit.specialty}` : ""}
                                {visit.facility_name ? ` • ${visit.facility_name}` : ""}
                              </p>
                            ) : null}
                          </div>

                          <time className="text-xs font-semibold text-[var(--text-brand)]">
                            {formattedTime}
                          </time>
                        </div>

                        {/* Clinician Notes */}
                        {(visit.clinician_notes || visit.notes || visit.goal) ? (
                          <div className="space-y-1.5 rounded-[var(--radius-lg)] bg-[var(--surface-muted)]/50 p-3">
                            <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] flex items-center gap-1.5">
                              <Icon name="clinical-notes" size="0.85rem" className="text-[var(--text-brand)]" />
                              <span>{copy("visits.clinicianNotes")}</span>
                            </p>
                            <p className="text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed">
                              {visit.clinician_notes || visit.notes || visit.goal}
                            </p>
                          </div>
                        ) : null}

                        {/* Prescriptions */}
                        {visit.prescriptions && visit.prescriptions.length > 0 ? (
                          <div className="space-y-2">
                            <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] flex items-center gap-1.5">
                              <Icon name="medication" size="0.85rem" className="text-[var(--brand-600)]" />
                              <span>{copy("visits.prescriptions")}</span>
                            </p>
                            <div className="grid gap-2 sm:grid-cols-2">
                              {visit.prescriptions.map((rx) => (
                                <div
                                  key={rx.id}
                                  className="flex items-start gap-2 rounded-[var(--radius-md)] border border-[color:var(--shell-border)]/60 bg-[var(--surface-lowest,#0b0e13)]/40 p-2.5 text-xs"
                                >
                                  <Icon
                                    name="medication"
                                    size="0.9rem"
                                    className="text-[var(--text-brand)] shrink-0 mt-0.5"
                                  />
                                  <div className="min-w-0 flex-1">
                                    <p className="font-semibold text-[var(--text-primary)] truncate">
                                      {rx.name}
                                    </p>
                                    {rx.dosage ? (
                                      <p className="text-[11px] text-[var(--text-secondary)]">
                                        {rx.dosage}
                                      </p>
                                    ) : null}
                                    {rx.instruction ? (
                                      <p className="mt-0.5 text-[11px] text-[var(--text-muted)] italic">
                                        {rx.instruction}
                                      </p>
                                    ) : null}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : null}

                        {/* Lab Orders & Document Attachments */}
                        {((visit.lab_orders && visit.lab_orders.length > 0) || docs.length > 0) ? (
                          <div className="space-y-2 border-t border-[color:var(--shell-border)]/40 pt-3">
                            <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] flex items-center gap-1.5">
                              <Icon name="folder" size="0.85rem" className="text-[var(--text-brand)]" />
                              <span>{copy("visits.labOrders")}</span>
                            </p>
                            <div className="flex flex-wrap gap-2">
                              {visit.lab_orders?.map((lab) => (
                                <div
                                  key={lab.id}
                                  className="inline-flex items-center gap-1.5 rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/60 px-2.5 py-1 text-xs"
                                >
                                  <Icon name="scan" size="0.8rem" className="text-[var(--text-brand)]" />
                                  <span className="font-medium text-[var(--text-primary)]">
                                    {lab.title}
                                  </span>
                                  {lab.result_summary ? (
                                    <span className="text-[11px] text-[var(--text-muted)]">
                                      ({lab.result_summary})
                                    </span>
                                  ) : null}
                                </div>
                              ))}
                              {docs.map((doc) => (
                                <div
                                  key={doc.id}
                                  className="inline-flex items-center gap-1.5 rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/60 px-2.5 py-1 text-xs"
                                >
                                  <Icon name="clinical-notes" size="0.8rem" className="text-[var(--text-brand)]" />
                                  <span className="font-medium text-[var(--text-primary)]">
                                    {doc.title}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : null}
                      </article>
                    </TimelineContent>
                  </TimelineItem>
                );
              })}
            </Timeline>
          </section>
        ) : null}

        {/* Guidance / Privacy Control Footer */}
        {!loading && visits.length > 0 ? (
          <SurfaceCard className="p-4 sm:p-5">
            <div className="flex items-start gap-3">
              <Icon name="check" size="1.2rem" className="text-[var(--brand-600)] shrink-0 mt-0.5" />
              <div className="text-xs space-y-1">
                <p className="font-semibold text-[var(--text-primary)]">
                  {copy("visits.controlTitle")}
                </p>
                <p className="text-[var(--text-secondary)] leading-relaxed">
                  {copy("visits.controlDescription")}
                </p>
              </div>
            </div>
          </SurfaceCard>
        ) : null}
      </div>
    </PageShell>
  );
}

export default function VisitsPage() {
  return (
    <Suspense fallback={null}>
      <VisitsTimelineStream />
    </Suspense>
  );
}
