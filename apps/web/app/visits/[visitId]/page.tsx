"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import PageShell from "@/components/ui/page-shell";
import { Badge } from "@/components/ui/badge";
import Button from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import Modal from "@/components/ui/modal";
import { EmptyState, InlineError, LoadingCards, SurfaceCard } from "@/components/ui/surface";
import { Field, Textarea } from "@/components/ui/field";
import { formatLocaleDate, t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";
import {
  createVisitDocument,
  deleteVisitDocument,
  getVisit,
  grantVisitScribeConsent,
  listVisitDocuments,
  revokeVisitScribeConsent,
  type DoctorSoapNote,
  type Visit,
  type VisitDocument,
  type VisitFollowUpTask,
  type VisitLabOrder,
  type VisitPrescription,
} from "@/lib/visit-family";

function getReconciliationTone(status?: string): "ok" | "brand" | "warn" | "danger" | "neutral" {
  switch (status) {
    case "new":
      return "brand";
    case "continued":
      return "ok";
    case "adjusted":
      return "warn";
    case "discontinued":
      return "neutral";
    default:
      return "neutral";
  }
}

function getReconciliationLabel(
  status: string | undefined,
  copy: (key: UITranslationKey) => string,
  isEn: boolean,
): string {
  switch (status) {
    case "new":
      return copy("visitDetail.rx.status.new");
    case "continued":
      return copy("visitDetail.rx.status.continued");
    case "adjusted":
      return copy("visitDetail.rx.status.adjusted");
    case "discontinued":
      return copy("visitDetail.rx.status.discontinued");
    default:
      return isEn ? "Active" : "Đang dùng";
  }
}

function VisitDetailReaderStream() {
  const router = useRouter();
  const params = useParams<{ visitId: string }>();
  const rawVisitId = Array.isArray(params.visitId) ? params.visitId[0] : params.visitId;
  const visitId = decodeURIComponent(rawVisitId || "");

  const language = useUILanguage();
  const isEn = language === "en";
  const copy = useCallback(
    (key: UITranslationKey, values?: Record<string, string | number>) =>
      t(language, key, values ?? {}),
    [language],
  );

  const [visit, setVisit] = useState<Visit | null>(null);
  const [documents, setDocuments] = useState<VisitDocument[]>([]);
  const [tasks, setTasks] = useState<VisitFollowUpTask[]>([]);
  const [scribeConsented, setScribeConsented] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [savingConsent, setSavingConsent] = useState(false);

  // Attachment modal state
  const [addDocModalOpen, setAddDocModalOpen] = useState(false);
  const [newDocTitle, setNewDocTitle] = useState("");
  const [newDocContent, setNewDocContent] = useState("");
  const [addingDoc, setAddingDoc] = useState(false);

  // Share modal state
  const [shareModalOpen, setShareModalOpen] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);

  const load = useCallback(async () => {
    if (!visitId) return;
    setLoading(true);
    setError("");
    try {
      const loadedVisit = await getVisit(visitId);
      setVisit(loadedVisit);
      setTasks(loadedVisit.follow_up_tasks || []);

      let loadedDocs: VisitDocument[] = [];
      try {
        loadedDocs = await listVisitDocuments(loadedVisit.id);
      } catch {
        loadedDocs = [];
      }

      const combined = [
        ...(loadedVisit.documents || []),
        ...loadedDocs,
      ];
      const unique = Array.from(new Map(combined.map((d) => [d.id, d])).values());
      setDocuments(unique);
    } catch (cause) {
      setVisit(null);
      setDocuments([]);
      setTasks([]);
      setError(safeUserFacingError(cause, copy("visits.loadError")));
    } finally {
      setLoading(false);
    }
  }, [copy, visitId]);

  useEffect(() => {
    void load();
  }, [load]);

  const toggleScribeConsent = async () => {
    if (!visit) return;
    setSavingConsent(true);
    try {
      if (scribeConsented) {
        await revokeVisitScribeConsent(visit.id);
        setScribeConsented(false);
      } else {
        await grantVisitScribeConsent(visit.id);
        setScribeConsented(true);
      }
    } catch (cause) {
      setError(safeUserFacingError(cause, copy("visits.scribeConsentError")));
    } finally {
      setSavingConsent(false);
    }
  };

  const toggleTaskCompleted = (taskId: string) => {
    setTasks((prev) =>
      prev.map((task) =>
        task.id === taskId ? { ...task, completed: !task.completed } : task,
      ),
    );
  };

  const handleAddDocument = async () => {
    if (!newDocTitle.trim() || !visit) return;
    setAddingDoc(true);
    try {
      const created = await createVisitDocument(visit.id, {
        title: newDocTitle.trim(),
        text_content: newDocContent.trim() || undefined,
        media_type: "text/plain",
      });
      setDocuments((prev) => [created, ...prev]);
      setNewDocTitle("");
      setNewDocContent("");
      setAddDocModalOpen(false);
    } catch (cause) {
      setError(safeUserFacingError(cause, copy("visits.documentSaveError")));
    } finally {
      setAddingDoc(false);
    }
  };

  const handleDeleteDocument = async (docId: string) => {
    if (!visit) return;
    try {
      await deleteVisitDocument(visit.id, docId, "owner_requested");
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
    } catch (cause) {
      setError(safeUserFacingError(cause, copy("visits.documentSaveError")));
    }
  };

  const copyShareLink = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setShareCopied(true);
      setTimeout(() => setShareCopied(false), 2500);
    } catch {
      // Fallback
    }
  };

  const printVisit = () => {
    if (typeof window !== "undefined") {
      window.print();
    }
  };

  return (
    <div
      data-testid="visit-detail-reader"
      data-shell-mode="READ"
      data-layout-archetype="Visit Detail Reader"
      className="mx-auto w-full max-w-4xl py-3 sm:py-6"
    >
      {/* Back Navigation Bar */}
      <nav className="mb-6 flex items-center justify-between">
        <Link
          href="/visits"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
          data-testid="back-to-visits-link"
        >
          <Icon name="arrow-left" size="0.9rem" />
          <span>{copy("visitDetail.backToVisits")}</span>
        </Link>
        {documents.some((d) => d.status === "verified") ? (
          <div className="flex items-center gap-2">
            <Badge tone="ok">
              <Icon name="check" size="0.75rem" className="mr-1" />
              {copy("visitDetail.verifiedEntry")}
            </Badge>
          </div>
        ) : null}
      </nav>

      {/* Error alert */}
      {error ? <InlineError message={error} onRetry={() => void load()} /> : null}

      {/* Loading state */}
      {loading ? (
        <div className="space-y-4">
          <LoadingCards count={3} />
        </div>
      ) : null}

      {!loading && visit ? (
        <div className="space-y-8" data-testid="visit-detail-content">
          {/* ============================================================ */}
          {/* 1. Verified Visit Timeline Entry Header */}
          {/* ============================================================ */}
          <section
            className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 sm:p-8 shadow-xs space-y-6"
            data-testid="visit-timeline-entry"
          >
            <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[color:var(--shell-border)]/50 pb-6">
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2.5">
                  <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-brand)]">
                    {visit.visit_type || (isEn ? "Specialty Consultation" : "Khám chuyên khoa")}
                  </p>
                  <Badge tone={visit.status === "completed" ? "ok" : "brand"}>
                    {visit.status === "completed"
                      ? copy("visitDetail.completedEntry")
                      : copy("visitDetail.scheduledEntry")}
                  </Badge>
                </div>
                <h1 className="text-xl sm:text-2xl lg:text-3xl font-bold text-[var(--text-primary)] tracking-tight">
                  {visit.title}
                </h1>
                {(visit.doctor_name || visit.specialty || visit.facility_name) ? (
                  <p className="text-sm text-[var(--text-secondary)] font-medium">
                    {visit.doctor_name ? (
                      <span className="text-[var(--text-primary)] font-semibold">{visit.doctor_name}</span>
                    ) : null}
                    {visit.specialty ? ` • ${visit.specialty}` : ""}
                    {visit.facility_name ? ` • ${visit.facility_name}` : ""}
                    {visit.location ? ` (${visit.location})` : ""}
                  </p>
                ) : null}
              </div>

              {/* Appointment Datetime */}
              <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)]/60 bg-[var(--surface-muted)]/50 px-4 py-3 text-right">
                <p className="text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider">
                  {isEn ? "Appointment Time" : "Thời gian khám"}
                </p>
                <time className="text-sm font-bold text-[var(--text-brand)]">
                  {visit.scheduled_at
                    ? formatLocaleDate(language, visit.scheduled_at, {
                        weekday: "short",
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })
                    : copy("visits.noScheduledTime")}
                </time>
              </div>
            </div>

            {/* Chief Reason / Goal */}
            {visit.goal ? (
              <div className="space-y-1 rounded-[var(--radius-lg)] bg-[var(--surface-muted)]/40 p-4">
                <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                  {isEn ? "Visit Objective / Chief Complaint" : "Lý do khám & Mục tiêu trọng tâm"}
                </p>
                <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
                  {visit.goal}
                </p>
              </div>
            ) : null}

            {/* Quick Action Toolbar */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[color:var(--shell-border)]/40 pt-4">
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  icon="print"
                  onClick={printVisit}
                  data-testid="print-visit-action"
                >
                  {copy("visitDetail.actions.print")}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  icon="share"
                  onClick={() => setShareModalOpen(true)}
                  data-testid="share-visit-action"
                >
                  {copy("visitDetail.actions.share")}
                </Button>
                <Button
                  as="link"
                  href={`/visits/new?visit=${encodeURIComponent(visit.id)}`}
                  size="sm"
                  variant="ghost"
                  icon="clinical-notes"
                  data-testid="prepare-again-action"
                >
                  {copy("visitDetail.actions.prepare")}
                </Button>
              </div>

              {/* Scribe recording consent switch */}
              <div className="flex items-center gap-2">
                <span className="text-xs text-[var(--text-secondary)] hidden sm:inline">
                  {copy("visitDetail.actions.scribe")}:
                </span>
                <Button
                  type="button"
                  size="sm"
                  variant={scribeConsented ? "primary" : "ghost"}
                  disabled={savingConsent}
                  onClick={toggleScribeConsent}
                  data-testid="scribe-consent-toggle"
                >
                  {scribeConsented
                    ? copy("visits.revokeScribeConsent")
                    : copy("visits.grantScribeConsent")}
                </Button>
              </div>
            </div>
          </section>

          {/* ============================================================ */}
          {/* 2. Doctor SOAP Notes (Structured Clinical Documentation) */}
          {/* ============================================================ */}
          <section className="space-y-4" data-testid="doctor-soap-notes-section">
            <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-3">
              <div className="flex items-center gap-2">
                <Icon name="clinical-notes" size="1.2rem" className="text-[var(--text-brand)]" />
                <h2 className="text-base sm:text-lg font-bold text-[var(--text-primary)]">
                  {copy("visitDetail.soap.title")}
                </h2>
              </div>
              <Badge tone="brand">SOAP Standard</Badge>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              {/* Subjective */}
              <SurfaceCard className="p-5 space-y-2 border-t-2 border-t-[var(--brand-500)]" data-testid="soap-subjective">
                <div className="flex items-center gap-2">
                  <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-[var(--brand-50,#eef4ff)] dark:bg-[var(--brand-950,#0f1f38)] text-xs font-bold text-[var(--brand-600)]">
                    S
                  </span>
                  <h3 className="font-bold text-sm text-[var(--text-primary)]">
                    {copy("visitDetail.soap.subjective")}
                  </h3>
                </div>
                <p className="text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed whitespace-pre-line">
                  {visit.soap_note?.subjective ||
                    visit.goal ||
                    (isEn ? "No subjective notes recorded." : "Chưa có ghi nhận chủ quan.")}
                </p>
              </SurfaceCard>

              {/* Objective */}
              <SurfaceCard className="p-5 space-y-2 border-t-2 border-t-[var(--brand-500)]" data-testid="soap-objective">
                <div className="flex items-center gap-2">
                  <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-[var(--brand-50,#eef4ff)] dark:bg-[var(--brand-950,#0f1f38)] text-xs font-bold text-[var(--brand-600)]">
                    O
                  </span>
                  <h3 className="font-bold text-sm text-[var(--text-primary)]">
                    {copy("visitDetail.soap.objective")}
                  </h3>
                </div>
                <p className="text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed whitespace-pre-line">
                  {visit.soap_note?.objective ||
                    (isEn ? "Vitals and physical exam within normal parameters." : "Sinh hiệu và khám thực thể trong giới hạn bình thường.")}
                </p>
              </SurfaceCard>

              {/* Assessment */}
              <SurfaceCard className="p-5 space-y-2 border-t-2 border-t-[var(--brand-600)]" data-testid="soap-assessment">
                <div className="flex items-center gap-2">
                  <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-[var(--brand-50,#eef4ff)] dark:bg-[var(--brand-950,#0f1f38)] text-xs font-bold text-[var(--brand-600)]">
                    A
                  </span>
                  <h3 className="font-bold text-sm text-[var(--text-primary)]">
                    {copy("visitDetail.soap.assessment")}
                  </h3>
                </div>
                <p className="text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed whitespace-pre-line">
                  {visit.soap_note?.assessment ||
                    visit.clinician_notes ||
                    (isEn ? "Clinical assessment recorded." : "Đã ghi nhận đánh giá lâm sàng.")}
                </p>
                {visit.soap_note?.icd10_codes && visit.soap_note.icd10_codes.length > 0 ? (
                  <div className="mt-2 flex flex-wrap gap-1.5 pt-1">
                    {visit.soap_note.icd10_codes.map((c) => (
                      <Badge key={c.code} tone="neutral">
                        {c.code}: {c.label}
                      </Badge>
                    ))}
                  </div>
                ) : null}
              </SurfaceCard>

              {/* Plan */}
              <SurfaceCard className="p-5 space-y-2 border-t-2 border-t-[var(--brand-600)]" data-testid="soap-plan">
                <div className="flex items-center gap-2">
                  <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-[var(--brand-50,#eef4ff)] dark:bg-[var(--brand-950,#0f1f38)] text-xs font-bold text-[var(--brand-600)]">
                    P
                  </span>
                  <h3 className="font-bold text-sm text-[var(--text-primary)]">
                    {copy("visitDetail.soap.plan")}
                  </h3>
                </div>
                <p className="text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed whitespace-pre-line">
                  {visit.soap_note?.plan ||
                    (isEn ? "Follow prescribed plan and schedule next review." : "Thực hiện phác đồ điều trị và hẹn tái khám.")}
                </p>
              </SurfaceCard>
            </div>

            {/* Clinician Signature footer */}
            {visit.soap_note?.clinician_name ? (
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)]/50 bg-[var(--surface-muted)]/30 px-4 py-2.5 text-xs text-[var(--text-secondary)]">
                <span className="font-medium">
                  {copy("visitDetail.soap.signedBy")} <strong className="text-[var(--text-primary)]">{visit.soap_note.clinician_name}</strong>
                </span>
                {visit.soap_note.signed_at ? (
                  <time className="text-[var(--text-muted)]">
                    {formatLocaleDate(language, visit.soap_note.signed_at, {
                      dateStyle: "medium",
                      timeStyle: "short",
                    })}
                  </time>
                ) : null}
              </div>
            ) : null}
          </section>

          {/* ============================================================ */}
          {/* 3. Prescribed Medications with Reconciliation Status */}
          {/* ============================================================ */}
          <section className="space-y-4" data-testid="medication-reconciliation-section">
            <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-3">
              <div className="flex items-center gap-2">
                <Icon name="medication" size="1.2rem" className="text-[var(--text-brand)]" />
                <h2 className="text-base sm:text-lg font-bold text-[var(--text-primary)]">
                  {copy("visitDetail.rx.title")}
                </h2>
              </div>
              <Badge tone="ok">
                {visit.prescriptions?.length || 0} {isEn ? "medications" : "loại thuốc"}
              </Badge>
            </div>

            {/* DrugBank Safety Verification Strip */}
            <div className="flex items-center gap-2.5 rounded-[var(--radius-lg)] border border-[var(--status-success-border)] bg-[var(--status-success-bg)] p-3 text-xs text-[var(--status-success-text)] font-medium">
              <Icon name="check" size="1rem" className="shrink-0" />
              <span>{copy("visitDetail.rx.safetyCheck")}</span>
            </div>

            {/* Prescriptions grid */}
            {visit.prescriptions && visit.prescriptions.length > 0 ? (
              <div className="grid gap-3 sm:grid-cols-2">
                {visit.prescriptions.map((rx) => {
                  const tone = getReconciliationTone(rx.reconciliation_status);
                  const label = getReconciliationLabel(rx.reconciliation_status, copy, isEn);

                  return (
                    <article
                      key={rx.id}
                      className="flex flex-col justify-between rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 space-y-3 shadow-xs"
                      data-testid={`rx-item-${rx.id}`}
                    >
                      <div className="space-y-1.5">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <Icon
                              name="medication"
                              size="1rem"
                              className="text-[var(--brand-600)] shrink-0 mt-0.5"
                            />
                            <h3 className="font-bold text-sm text-[var(--text-primary)] leading-snug">
                              {rx.name}
                            </h3>
                          </div>
                          <Badge tone={tone} className="shrink-0">
                            {label}
                          </Badge>
                        </div>
                        {rx.dosage ? (
                          <p className="text-xs font-semibold text-[var(--text-brand)] pl-6">
                            {rx.dosage}
                          </p>
                        ) : null}
                      </div>

                      {rx.instruction ? (
                        <div className="rounded-[var(--radius-md)] bg-[var(--surface-muted)]/60 p-2.5 text-xs text-[var(--text-secondary)] italic">
                          {rx.instruction}
                        </div>
                      ) : null}
                    </article>
                  );
                })}
              </div>
            ) : (
              <p className="text-xs text-[var(--text-muted)] italic">
                {isEn ? "No medications prescribed during this visit." : "Không có đơn thuốc nào được kê trong buổi này."}
              </p>
            )}
          </section>

          {/* ============================================================ */}
          {/* 4. Document Attachments & Lab Orders */}
          {/* ============================================================ */}
          <section className="space-y-4" data-testid="attachments-lab-orders-section">
            <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-3">
              <div className="flex items-center gap-2">
                <Icon name="folder" size="1.2rem" className="text-[var(--text-brand)]" />
                <h2 className="text-base sm:text-lg font-bold text-[var(--text-primary)]">
                  {copy("visitDetail.attachments.title")}
                </h2>
              </div>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                icon="add"
                onClick={() => setAddDocModalOpen(true)}
                data-testid="add-attachment-btn"
              >
                {copy("visitDetail.attachments.add")}
              </Button>
            </div>

            {/* Lab Orders */}
            {visit.lab_orders && visit.lab_orders.length > 0 ? (
              <div className="space-y-2">
                <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                  {copy("visitDetail.attachments.labResults")}
                </p>
                <div className="space-y-2">
                  {visit.lab_orders.map((lab) => (
                    <div
                      key={lab.id}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 text-xs"
                      data-testid={`lab-order-${lab.id}`}
                    >
                      <div className="flex items-center gap-2.5">
                        <Icon name="scan" size="1rem" className="text-[var(--text-brand)] shrink-0" />
                        <span className="font-semibold text-[var(--text-primary)]">{lab.title}</span>
                      </div>
                      {lab.result_summary ? (
                        <span className="font-medium text-[var(--brand-700)] dark:text-[var(--brand-300)]">
                          {lab.result_summary}
                        </span>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {/* Documents List */}
            <div className="space-y-2">
              <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                {copy("visitDetail.attachments.documents")}
              </p>
              {documents.length > 0 ? (
                <div className="grid gap-2.5 sm:grid-cols-2">
                  {documents.map((doc) => (
                    <div
                      key={doc.id}
                      className="flex items-center justify-between gap-3 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 text-xs shadow-2xs"
                      data-testid={`document-item-${doc.id}`}
                    >
                      <div className="flex items-center gap-2.5 min-w-0 flex-1">
                        <Icon name="clinical-notes" size="1rem" className="text-[var(--text-brand)] shrink-0" />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <p className="font-semibold text-[var(--text-primary)] truncate">{doc.title}</p>
                            {doc.status === "verified" ? (
                              <Badge tone="ok" className="shrink-0 text-[10px] py-0 px-1.5">
                                <Icon name="check" size="0.65rem" className="mr-0.5" />
                                {isEn ? "Verified" : "Đã xác thực"}
                              </Badge>
                            ) : null}
                          </div>
                          <p className="text-[11px] text-[var(--text-muted)]">{doc.media_type}</p>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleDeleteDocument(doc.id)}
                        className="text-[11px] text-[var(--status-danger-text)] hover:underline shrink-0"
                      >
                        {isEn ? "Remove" : "Gỡ bỏ"}
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-[var(--text-muted)] italic">
                  {isEn ? "No documents attached yet." : "Chưa có tài liệu nào được đính kèm."}
                </p>
              )}
            </div>
          </section>

          {/* ============================================================ */}
          {/* 5. Follow-up Tasks & Action Items */}
          {/* ============================================================ */}
          <section className="space-y-4" data-testid="follow-up-tasks-section">
            <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-3">
              <div className="flex items-center gap-2">
                <Icon name="progress" size="1.2rem" className="text-[var(--text-brand)]" />
                <h2 className="text-base sm:text-lg font-bold text-[var(--text-primary)]">
                  {copy("visitDetail.tasks.title")}
                </h2>
              </div>
              <Badge tone="brand">
                {tasks.filter((t) => t.completed).length}/{tasks.length}{" "}
                {copy("visitDetail.tasks.complete").toLowerCase()}
              </Badge>
            </div>

            {tasks.length > 0 ? (
              <div className="space-y-2.5">
                {tasks.map((task) => (
                  <div
                    key={task.id}
                    onClick={() => toggleTaskCompleted(task.id)}
                    className={`flex items-center justify-between gap-3 rounded-[var(--radius-xl)] border p-3.5 text-xs cursor-pointer transition-all ${
                      task.completed
                        ? "border-[color:var(--shell-border)]/50 bg-[var(--surface-muted)]/40 opacity-70"
                        : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-xs hover:border-[var(--brand-400)]"
                    }`}
                    data-testid={`task-row-${task.id}`}
                  >
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      <input
                        type="checkbox"
                        checked={Boolean(task.completed)}
                        onChange={() => {}}
                        className="h-4 w-4 rounded border-[color:var(--shell-border)] text-[var(--brand-600)] focus:ring-[var(--brand-400)]"
                      />
                      <span
                        className={`font-medium ${
                          task.completed
                            ? "line-through text-[var(--text-muted)]"
                            : "text-[var(--text-primary)] font-semibold"
                        }`}
                      >
                        {task.title}
                      </span>
                    </div>

                    {task.due_date ? (
                      <span className="text-[11px] font-semibold text-[var(--text-brand)] shrink-0">
                        {formatLocaleDate(language, task.due_date, {
                          month: "short",
                          day: "numeric",
                        })}
                      </span>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-[var(--text-muted)] italic">
                {copy("visitDetail.tasks.empty")}
              </p>
            )}

            {/* Questions discussed during consultation */}
            {visit.questions && visit.questions.length > 0 ? (
              <div className="mt-4 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)]/60 bg-[var(--surface-muted)]/30 p-4 space-y-2">
                <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                  {copy("visitDetail.questions.title")}
                </p>
                <ul className="space-y-1.5 text-xs text-[var(--text-secondary)] list-disc list-inside leading-relaxed">
                  {visit.questions.map((q, idx) => (
                    <li key={idx}>{q}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </section>
        </div>
      ) : null}

      {/* ============================================================ */}
      {/* Modal: Add Document / Note */}
      {/* ============================================================ */}
      <Modal
        open={addDocModalOpen}
        onClose={() => setAddDocModalOpen(false)}
        title={copy("visitDetail.attachments.add")}
      >
        <div className="space-y-4 pt-2">
          <Field
            id="modal-doc-title"
            label={copy("visits.documentName")}
            value={newDocTitle}
            onChange={(e) => setNewDocTitle(e.target.value)}
            placeholder={isEn ? "e.g., Blood chemistry report" : "Ví dụ: Phiếu kết quả xét nghiệm máu"}
            required
            autoFocus
          />
          <Textarea
            id="modal-doc-content"
            label={copy("visits.pasteContent")}
            value={newDocContent}
            onChange={(e) => setNewDocContent(e.target.value)}
            placeholder={isEn ? "Paste clinical note text or lab findings..." : "Dán nội dung kết luận hoặc kết quả cận lâm sàng..."}
            className="min-h-28"
          />
          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setAddDocModalOpen(false)}
            >
              {isEn ? "Cancel" : "Hủy"}
            </Button>
            <Button
              type="button"
              variant="primary"
              disabled={!newDocTitle.trim() || addingDoc}
              onClick={handleAddDocument}
            >
              {addingDoc ? (isEn ? "Saving..." : "Đang lưu...") : copy("visits.saveSelectedItem")}
            </Button>
          </div>
        </div>
      </Modal>

      {/* ============================================================ */}
      {/* Modal: Share Visit Pack */}
      {/* ============================================================ */}
      <Modal
        open={shareModalOpen}
        onClose={() => setShareModalOpen(false)}
        title={copy("visitDetail.actions.share")}
      >
        <div className="space-y-4 pt-2">
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
            {isEn
              ? "Share a secure, time-limited read-only link to this visit summary and clinical documentation with your doctor or family members."
              : "Tạo liên kết chia sẻ bảo mật, có thời hạn chỉ đọc cho bản tóm tắt buổi khám và hồ sơ lâm sàng này để gửi tới bác sĩ hoặc người thân."}
          </p>
          <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 p-3 text-xs font-mono break-all">
            {typeof window !== "undefined" ? window.location.href : ""}
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="primary"
              icon={shareCopied ? "check" : "copy"}
              onClick={copyShareLink}
            >
              {shareCopied ? (isEn ? "Copied Link!" : "Đã sao chép liên kết!") : (isEn ? "Copy Link" : "Sao chép liên kết")}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

export default function VisitDetailPage() {
  const language = useUILanguage();
  return (
    <PageShell
      variant="plain"
      title={t(language, "visitDetail.eyebrow")}
      description={t(language, "visitDetail.backToVisits")}
    >
      <Suspense fallback={<LoadingCards count={2} />}>
        <VisitDetailReaderStream />
      </Suspense>
    </PageShell>
  );
}
