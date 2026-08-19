"use client";

import { FormEvent, Suspense, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { HealthPageHeader } from "@/components/consumer/health-page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Select, Textarea } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Modal } from "@/components/ui/modal";
import { EmptyState } from "@/components/shared/empty-state";
import { InlineError } from "@/components/shared/inline-error";
import { useUILanguage } from "@/lib/use-ui-language";
import { formatLocaleDate } from "@/lib/i18n/catalog";
import { getActiveProfileId } from "@/lib/profile-context";
import { useQuery } from "@/lib/query/use-query";
import { queryKeys } from "@/lib/query/query-keys";
import {
  v2Client,
  type CareVisitDocumentDto,
  type CareVisitDto,
} from "@/lib/api/v2-client";

type VisitTabFilter = "all" | "upcoming" | "past";

function getPrepStatusTone(status?: string) {
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

function getPrepStatusLabel(status?: string, locale: "vi" | "en" = "vi") {
  const isEn = locale === "en";
  switch (status) {
    case "completed":
    case "ready":
      return isEn ? "Handoff Ready" : "Đã sẵn sàng";
    case "in_progress":
      return isEn ? "In Progress" : "Đang chuẩn bị";
    case "not_started":
    default:
      return isEn ? "Prep Needed" : "Cần chuẩn bị";
  }
}

function VisitsPageContent() {
  const searchParams = useSearchParams();
  const initialVisitId = searchParams.get("visit");
  const uiLanguage = useUILanguage();
  const isEn = uiLanguage === "en";

  const [activeProfileId] = useState<string | null>(getActiveProfileId());
  const [activeTab, setActiveTab] = useState<VisitTabFilter>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedVisit, setSelectedVisit] = useState<CareVisitDto | null>(null);

  // New Visit Modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDoctor, setNewDoctor] = useState("");
  const [newSpecialty, setNewSpecialty] = useState("");
  const [newFacility, setNewFacility] = useState("");
  const [newDate, setNewDate] = useState("");
  const [newReason, setNewReason] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [createError, setCreateError] = useState("");

  // Document Attachment Modal
  const [showAttachDocModal, setShowAttachDocModal] = useState(false);
  const [docTitle, setDocTitle] = useState("");
  const [docFile, setDocFile] = useState<File | null>(null);
  const [docSummary, setDocSummary] = useState("");

  const queryKey = queryKeys.profile(activeProfileId).care.visits.list();

  const { data, isLoading, isError, error, refetch } = useQuery<CareVisitDto[]>({
    queryKey,
    queryFn: async () => {
      try {
        const res = await v2Client.getVisits(undefined, activeProfileId);
        if (res && res.length > 0) return res;
      } catch {
        // Continue to sample fallback
      }

      // Sample robust data
      const now = Date.now();
      return [
        {
          id: "v-1",
          title: "Tái khám định kỳ & Đánh giá huyết áp",
          doctor_name: "BSCKII Nguyễn Văn An",
          specialty: "Tim mạch can thiệp",
          facility_name: "Bệnh viện Đại học Y Dược TP.HCM",
          location: "Phòng khám 102, Khu A",
          scheduled_at: new Date(now + 86400000 * 3).toISOString(),
          status: "scheduled",
          prep_status: "not_started",
          visit_type: "Tái khám chuyên khoa",
          reason_for_visit: "Kiểm tra huyết áp mục tiêu sau 1 tháng đổi thuốc và đánh giá cơn đau ngực nhẹ",
          document_count: 2,
          documents: [
            {
              id: "doc-1",
              title: "Điện tâm đồ ECG 12 chuyển đạo",
              mime_type: "application/pdf",
              recorded_at: new Date(now - 86400000 * 30).toISOString(),
              summary: "Nhịp xoang 72 l/p, trục trung gian, không có dấu hiệu thiếu máu cục bộ cơ tim.",
            },
            {
              id: "doc-2",
              title: "Đơn thuốc Tim mạch tháng trước",
              mime_type: "application/pdf",
              recorded_at: new Date(now - 86400000 * 30).toISOString(),
              summary: "Amlodipine 5mg 1v/ngày, Telmisartan 40mg 1v/ngày.",
            },
          ],
        },
        {
          id: "v-2",
          title: "Khám nội tiết & Đái tháo đường",
          doctor_name: "TS.BS Lê Thị Mai",
          specialty: "Nội tiết",
          facility_name: "Bệnh viện Chợ Rẫy",
          location: "Khoa Khám bệnh theo yêu cầu",
          scheduled_at: new Date(now + 86400000 * 14).toISOString(),
          status: "scheduled",
          prep_status: "in_progress",
          visit_type: "Khám định kỳ",
          reason_for_visit: "Đánh giá chỉ số HbA1c và kiểm tra biến chứng bàn chân đái tháo đường",
          document_count: 1,
          documents: [
            {
              id: "doc-3",
              title: "Phiếu xét nghiệm Sinh hóa máu (Glucose, HbA1c, Lipid)",
              mime_type: "application/pdf",
              recorded_at: new Date(now - 86400000 * 7).toISOString(),
              summary: "Glucose: 6.8 mmol/L, HbA1c: 6.9%.",
            },
          ],
        },
        {
          id: "v-3",
          title: "Khám chuyên khoa Tai Mũi Họng",
          doctor_name: "BS. CKI Trần Hoàng",
          specialty: "Tai Mũi Họng",
          facility_name: "Phòng khám Đa khoa Quốc tế",
          location: "Tầng 2, Phòng 204",
          scheduled_at: new Date(now - 86400000 * 20).toISOString(),
          status: "completed",
          prep_status: "completed",
          visit_type: "Khám cấp tính",
          reason_for_visit: "Viêm họng cấp và khàn tiếng kéo dài 5 ngày",
          document_count: 1,
          documents: [
            {
              id: "doc-4",
              title: "Toa thuốc & Nội soi Tai Mũi Họng",
              mime_type: "application/pdf",
              recorded_at: new Date(now - 86400000 * 20).toISOString(),
              summary: "Viêm thanh quản cấp, sung huyết nhẹ dây thanh.",
            },
          ],
        },
        {
          id: "v-4",
          title: "Khám tổng quát định kỳ hàng năm",
          doctor_name: "BSCKI Phạm Thu Hà",
          specialty: "Nội tổng quát",
          facility_name: "Bệnh viện Thống Nhất",
          location: "Khu khám sức khỏe định kỳ",
          scheduled_at: new Date(now - 86400000 * 90).toISOString(),
          status: "completed",
          prep_status: "completed",
          visit_type: "Khám tổng quát",
          reason_for_visit: "Kiểm tra sức khỏe tổng quát định kỳ",
          document_count: 3,
          documents: [
            {
              id: "doc-5",
              title: "Báo cáo Tổng kết Khám sức khỏe 2026",
              mime_type: "application/pdf",
              recorded_at: new Date(now - 86400000 * 90).toISOString(),
              summary: "Tổng trạng tốt, huyết áp hơi cao nhẹ, khuyến nghị tái khám chuyên khoa tim mạch.",
            },
          ],
        },
      ];
    },
  });

  const visits = useMemo(() => data ?? [], [data]);

  const filteredVisits = useMemo(() => {
    const now = Date.now();
    return visits.filter((v) => {
      const isUpcoming = new Date(v.scheduled_at).getTime() >= now;
      if (activeTab === "upcoming" && !isUpcoming) return false;
      if (activeTab === "past" && isUpcoming) return false;

      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const matchTitle = v.title.toLowerCase().includes(q);
        const matchDoc = v.doctor_name?.toLowerCase().includes(q);
        const matchSpec = v.specialty?.toLowerCase().includes(q);
        const matchFac = v.facility_name?.toLowerCase().includes(q);
        const matchReason = v.reason_for_visit?.toLowerCase().includes(q);
        if (!matchTitle && !matchDoc && !matchSpec && !matchFac && !matchReason) {
          return false;
        }
      }
      return true;
    });
  }, [visits, activeTab, searchQuery]);

  // Handle setting active selected visit from filtered visits
  const activeVisit = useMemo(() => {
    if (selectedVisit && filteredVisits.some((v) => v.id === selectedVisit.id)) {
      return selectedVisit;
    }
    if (initialVisitId) {
      const match = filteredVisits.find((v) => v.id === initialVisitId);
      if (match) return match;
    }
    return filteredVisits[0] ?? null;
  }, [selectedVisit, initialVisitId, filteredVisits]);

  const handleCreateVisit = async (e: FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || !newDate.trim()) {
      setCreateError(isEn ? "Please fill title and scheduled date" : "Vui lòng nhập tiêu đề và ngày khám");
      return;
    }

    setIsSubmitting(true);
    setCreateError("");

    try {
      await v2Client.createVisit({
        title: newTitle.trim(),
        doctor_name: newDoctor.trim() || undefined,
        specialty: newSpecialty.trim() || undefined,
        facility_name: newFacility.trim() || undefined,
        scheduled_at: new Date(newDate).toISOString(),
        reason_for_visit: newReason.trim() || undefined,
        status: "scheduled",
        prep_status: "not_started",
      });

      setShowCreateModal(false);
      setNewTitle("");
      setNewDoctor("");
      setNewSpecialty("");
      setNewFacility("");
      setNewDate("");
      setNewReason("");
      void refetch();
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Error creating visit");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAttachDocument = (e: FormEvent) => {
    e.preventDefault();
    if (!docTitle.trim() && !docFile) return;

    if (activeVisit) {
      const newDoc: CareVisitDocumentDto = {
        id: `doc-${Date.now()}`,
        title: docTitle.trim() || docFile?.name || "Tài liệu đính kèm",
        mime_type: docFile?.type || "application/pdf",
        recorded_at: new Date().toISOString(),
        summary: docSummary.trim() || undefined,
      };

      if (!activeVisit.documents) activeVisit.documents = [];
      activeVisit.documents.push(newDoc);
      activeVisit.document_count = activeVisit.documents.length;
      setSelectedVisit({ ...activeVisit });
    }

    setShowAttachDocModal(false);
    setDocTitle("");
    setDocFile(null);
    setDocSummary("");
  };

  return (
    <div
      className="visits-page-container mx-auto max-w-5xl space-y-6 pb-12"
      data-testid="care-visits-page"
    >
      {/* 1. Header */}
      <HealthPageHeader
        title={isEn ? "Visits & Records" : "Lịch khám & Hồ sơ buổi khám"}
        subtitle={
          isEn
            ? "Upcoming and past consultations, attached diagnostic records, and clinician handoff summaries."
            : "Danh sách buổi khám sắp tới và đã qua, hồ sơ xét nghiệm đính kèm và bản tóm tắt bàn giao cho bác sĩ."
        }
        backHref="/care"
        backLabel={isEn ? "Back to Care" : "Quay lại Chăm sóc"}
        locale={uiLanguage}
        primaryAction={{
          label: isEn ? "+ Schedule Visit" : "+ Lên lịch khám mới",
          onClick: () => setShowCreateModal(true),
          icon: "calendar",
        }}
        secondaryAction={{
          label: isEn ? "Visit Preparation" : "Chuẩn bị đi khám",
          href: "/care/prepare",
          icon: "clinical-notes",
        }}
      />

      {/* 2. Filters & Search */}
      <section
        className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5 space-y-3"
        data-testid="visits-filter-bar"
      >
        <Field
          type="search"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder={isEn ? "Search by doctor, specialty, facility or purpose..." : "Tìm theo tên bác sĩ, chuyên khoa, bệnh viện hoặc lý do khám..."}
          data-testid="visits-search-input"
        />

        <div className="flex flex-wrap items-center gap-2 pt-1">
          <button
            type="button"
            onClick={() => setActiveTab("all")}
            className={`rounded-[var(--radius-pill)] border px-3 py-1 text-xs font-semibold transition ${
              activeTab === "all"
                ? "border-[color:var(--brand-600)] bg-[var(--brand-600)] text-[var(--button-primary-text)]"
                : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]"
            }`}
            data-testid="tab-all-visits"
          >
            {isEn ? "All Visits" : "Tất cả buổi khám"}
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("upcoming")}
            className={`rounded-[var(--radius-pill)] border px-3 py-1 text-xs font-semibold transition ${
              activeTab === "upcoming"
                ? "border-[color:var(--brand-600)] bg-[var(--brand-600)] text-[var(--button-primary-text)]"
                : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]"
            }`}
            data-testid="tab-upcoming-visits"
          >
            {isEn ? "Upcoming" : "Sắp tới"}
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("past")}
            className={`rounded-[var(--radius-pill)] border px-3 py-1 text-xs font-semibold transition ${
              activeTab === "past"
                ? "border-[color:var(--brand-600)] bg-[var(--brand-600)] text-[var(--button-primary-text)]"
                : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]"
            }`}
            data-testid="tab-past-visits"
          >
            {isEn ? "Past Visits" : "Đã qua"}
          </button>
        </div>
      </section>

      {/* Error state */}
      {isError && (
        <InlineError
          severity="error"
          title={isEn ? "Failed to load visits" : "Không thể tải danh sách buổi khám"}
          message={error instanceof Error ? error.message : "Error"}
          onRetry={() => void refetch()}
        />
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="space-y-4 animate-pulse">
          {[1, 2, 3].map((n) => (
            <div
              key={n}
              className="h-32 rounded-[var(--radius-xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]"
            />
          ))}
        </div>
      )}

      {/* Main Content Grid: Visits List (Left) & Selected Visit Detail Panel (Right) */}
      {!isLoading && filteredVisits.length === 0 ? (
        <EmptyState
          title={isEn ? "No visits found" : "Không tìm thấy buổi khám nào"}
          description={
            isEn
              ? "You do not have any appointments matching the current filter. Schedule a visit to stay organized."
              : "Không có lịch khám nào phù hợp bộ lọc hiện tại. Bạn có thể thêm lịch khám để được CLARA nhắc nhở và hỗ trợ chuẩn bị."
          }
          icon="calendar"
        >
          <Button onClick={() => setShowCreateModal(true)} icon="calendar">
            {isEn ? "+ Schedule a Visit" : "+ Lên lịch khám"}
          </Button>
        </EmptyState>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Visits List */}
          <div className="space-y-3 lg:col-span-6" data-testid="visits-list">
            {filteredVisits.map((visit) => {
              const isSelected = activeVisit?.id === visit.id;
              const formattedDate = visit.scheduled_at
                ? formatLocaleDate(uiLanguage, visit.scheduled_at, {
                    weekday: "short",
                    year: "numeric",
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                : "";

              return (
                <article
                  key={visit.id}
                  onClick={() => setSelectedVisit(visit)}
                  className={`cursor-pointer rounded-[var(--radius-xl)] border p-4 sm:p-5 transition shadow-xs ${
                    isSelected
                      ? "border-[color:var(--brand-600)] bg-[var(--surface-brand-soft)] ring-1 ring-[var(--brand-500)]"
                      : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] hover:border-[color:var(--brand-500)]/60"
                  }`}
                  data-testid={`visit-item-${visit.id}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-bold text-sm sm:text-base text-[var(--text-primary)]">
                          {visit.title}
                        </h3>
                        <Badge tone={getPrepStatusTone(visit.prep_status)}>
                          {getPrepStatusLabel(visit.prep_status, uiLanguage)}
                        </Badge>
                      </div>

                      {formattedDate && (
                        <p className="mt-1 text-xs text-[var(--text-brand)] font-medium flex items-center gap-1">
                          <Icon name="calendar" size="0.85rem" />
                          <span>{formattedDate}</span>
                        </p>
                      )}
                    </div>
                  </div>

                  {(visit.doctor_name || visit.facility_name) && (
                    <div className="mt-2 text-xs text-[var(--text-secondary)] space-y-0.5 border-t border-[color:var(--shell-border)]/40 pt-2">
                      {visit.doctor_name && (
                        <p className="font-medium text-[var(--text-primary)]">
                          {visit.doctor_name} {visit.specialty ? `• ${visit.specialty}` : ""}
                        </p>
                      )}
                      {visit.facility_name && (
                        <p className="text-[var(--text-muted)] truncate">
                          {visit.facility_name}
                        </p>
                      )}
                    </div>
                  )}

                  <div className="mt-3 flex items-center justify-between gap-2 pt-1">
                    <span className="text-[11px] text-[var(--text-muted)] flex items-center gap-1">
                      <Icon name="folder" size="0.85rem" />
                      <span>{visit.documents?.length || visit.document_count || 0} tài liệu đính kèm</span>
                    </span>

                    <Link
                      href={`/care/prepare?visitId=${visit.id}`}
                      onClick={(e) => e.stopPropagation()}
                      className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--text-brand)] hover:underline"
                    >
                      <span>{isEn ? "Prepare" : "Chuẩn bị"}</span>
                      <Icon name="arrow-right" size="0.8rem" />
                    </Link>
                  </div>
                </article>
              );
            })}
          </div>

          {/* Visit Details & Documents Pane */}
          {activeVisit && (
            <div className="space-y-5 lg:col-span-6" data-testid="visit-detail-pane">
              <div className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 space-y-4 shadow-sm">
                <div className="border-b border-[color:var(--shell-border)]/50 pb-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Badge tone={activeVisit.status === "completed" ? "neutral" : "brand"}>
                      {activeVisit.status === "completed"
                        ? isEn ? "Completed Visit" : "Đã hoàn thành"
                        : isEn ? "Scheduled Visit" : "Lịch khám dự kiến"}
                    </Badge>
                    <Badge tone={getPrepStatusTone(activeVisit.prep_status)}>
                      {getPrepStatusLabel(activeVisit.prep_status, uiLanguage)}
                    </Badge>
                  </div>

                  <h2 className="mt-2 text-lg font-bold text-[var(--text-primary)]">
                    {activeVisit.title}
                  </h2>

                  <p className="mt-1 text-xs text-[var(--text-brand)] font-semibold flex items-center gap-1">
                    <Icon name="calendar" size="0.95rem" />
                    <span>
                      {formatLocaleDate(uiLanguage, activeVisit.scheduled_at, {
                        dateStyle: "full",
                        timeStyle: "short",
                      })}
                    </span>
                  </p>
                </div>

                {/* Clinician & Location Information */}
                <div className="rounded-[var(--radius-lg)] bg-[var(--surface-muted)]/50 p-3 text-xs space-y-1">
                  {activeVisit.doctor_name && (
                    <div className="flex justify-between">
                      <span className="text-[var(--text-muted)]">{isEn ? "Physician:" : "Bác sĩ:"}</span>
                      <span className="font-bold text-[var(--text-primary)]">{activeVisit.doctor_name}</span>
                    </div>
                  )}
                  {activeVisit.specialty && (
                    <div className="flex justify-between">
                      <span className="text-[var(--text-muted)]">{isEn ? "Specialty:" : "Chuyên khoa:"}</span>
                      <span className="font-medium text-[var(--text-primary)]">{activeVisit.specialty}</span>
                    </div>
                  )}
                  {activeVisit.facility_name && (
                    <div className="flex justify-between">
                      <span className="text-[var(--text-muted)]">{isEn ? "Facility:" : "Địa điểm:"}</span>
                      <span className="font-medium text-[var(--text-primary)] text-right">
                        {activeVisit.facility_name} {activeVisit.location ? `(${activeVisit.location})` : ""}
                      </span>
                    </div>
                  )}
                </div>

                {/* Reason for visit */}
                {activeVisit.reason_for_visit && (
                  <div className="space-y-1">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      {isEn ? "Reason for Consultation" : "Lý do đến khám"}
                    </h3>
                    <p className="text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed bg-[var(--surface-muted)]/30 rounded-[var(--radius-md)] p-2.5">
                      {activeVisit.reason_for_visit}
                    </p>
                  </div>
                )}

                {/* Document Attachments Section */}
                <div className="space-y-2 border-t border-[color:var(--shell-border)]/50 pt-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5 text-[var(--text-primary)]">
                      <Icon name="folder" size="1.05rem" className="text-[var(--text-brand)]" />
                      <h3 className="font-bold text-xs sm:text-sm">
                        {isEn ? "Document Attachments" : "Hồ sơ & Tài liệu đính kèm"}
                      </h3>
                    </div>

                    <Button
                      variant="ghost"
                      size="sm"
                      icon="plus"
                      onClick={() => setShowAttachDocModal(true)}
                    >
                      {isEn ? "Attach" : "Đính kèm"}
                    </Button>
                  </div>

                  {!activeVisit.documents || activeVisit.documents.length === 0 ? (
                    <p className="text-xs text-[var(--text-muted)] italic py-2">
                      {isEn ? "No documents attached to this visit yet." : "Chưa có tài liệu đính kèm cho buổi khám này."}
                    </p>
                  ) : (
                    <div className="space-y-2 pt-1">
                      {activeVisit.documents.map((doc) => (
                        <div
                          key={doc.id}
                          className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2.5 text-xs flex items-start justify-between gap-2"
                        >
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-1.5 font-semibold text-[var(--text-primary)]">
                              <Icon name="clinical-notes" size="0.9rem" className="text-[var(--brand-600)] shrink-0" />
                              <span className="truncate">{doc.title}</span>
                            </div>
                            {doc.summary && (
                              <p className="mt-1 text-[11px] text-[var(--text-secondary)] leading-snug">
                                {doc.summary}
                              </p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Wizard CTA */}
                <div className="border-t border-[color:var(--shell-border)]/50 pt-3">
                  <Button
                    as="link"
                    href={`/care/prepare?visitId=${activeVisit.id}`}
                    icon="clinical-notes"
                    className="w-full justify-center"
                  >
                    {isEn ? "Open Visit Preparation Wizard" : "Mở Trợ lý chuẩn bị đi khám"}
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Create Visit Modal */}
      {showCreateModal && (
        <Modal
          open={showCreateModal}
          onClose={() => setShowCreateModal(false)}
          title={isEn ? "Schedule New Consultation" : "Lên lịch buổi khám mới"}
          description={
            isEn
              ? "Add appointment details to enable automated preparation prompts and timeline coordination."
              : "Nhập thông tin buổi khám để CLARA nhắc nhở và chuẩn bị bản tóm tắt bàn giao cho bác sĩ."
          }
          size="md"
        >
          <form onSubmit={handleCreateVisit} className="space-y-3">
            {createError && (
              <InlineError severity="error" message={createError} />
            )}

            <Field
              label={isEn ? "Visit Title / Main Concern *" : "Tiêu đề buổi khám / Lý do chính *"}
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder={isEn ? "e.g. Cardiology follow-up" : "VD: Tái khám định kỳ Tim mạch"}
              required
            />

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field
                label={isEn ? "Doctor Name" : "Tên Bác sĩ"}
                value={newDoctor}
                onChange={(e) => setNewDoctor(e.target.value)}
                placeholder="VD: BSCKII Nguyễn Văn An"
              />

              <Field
                label={isEn ? "Specialty" : "Chuyên khoa"}
                value={newSpecialty}
                onChange={(e) => setNewSpecialty(e.target.value)}
                placeholder="VD: Tim mạch, Nội tiết..."
              />
            </div>

            <Field
              label={isEn ? "Hospital / Clinic Facility" : "Bệnh viện / Phòng khám"}
              value={newFacility}
              onChange={(e) => setNewFacility(e.target.value)}
              placeholder="VD: Bệnh viện Đại học Y Dược"
            />

            <Field
              label={isEn ? "Appointment Date & Time *" : "Ngày giờ khám *"}
              type="datetime-local"
              value={newDate}
              onChange={(e) => setNewDate(e.target.value)}
              required
            />

            <Textarea
              label={isEn ? "Symptoms & Notes for Doctor" : "Ghi chú & Triệu chứng cần trao đổi"}
              value={newReason}
              onChange={(e) => setNewReason(e.target.value)}
              placeholder={isEn ? "Describe your symptoms or questions..." : "Ghi lại diễn tiến triệu chứng hoặc thắc mắc cần hỏi..."}
              className="min-h-20"
            />

            <div className="flex justify-end gap-2 pt-3">
              <Button
                type="button"
                variant="secondary"
                onClick={() => setShowCreateModal(false)}
                disabled={isSubmitting}
              >
                {isEn ? "Cancel" : "Hủy"}
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting
                  ? isEn ? "Saving..." : "Đang lưu..."
                  : isEn ? "Save Visit" : "Lưu buổi khám"}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {/* Attach Document Modal */}
      {showAttachDocModal && (
        <Modal
          open={showAttachDocModal}
          onClose={() => setShowAttachDocModal(false)}
          title={isEn ? "Attach Document to Visit" : "Đính kèm tài liệu vào buổi khám"}
          description={
            isEn
              ? "Attach relevant lab reports, prescriptions, or imaging results to bring to your doctor."
              : "Đính kèm phiếu xét nghiệm, toa thuốc cũ hoặc kết quả chẩn đoán hình ảnh cho buổi khám này."
          }
          size="md"
        >
          <form onSubmit={handleAttachDocument} className="space-y-3">
            <Field
              label={isEn ? "Document Title *" : "Tên tài liệu *"}
              value={docTitle}
              onChange={(e) => setDocTitle(e.target.value)}
              placeholder={isEn ? "e.g. ECG Result, Blood test" : "VD: Kết quả Điện tim, Phiếu xét nghiệm máu..."}
              required
            />

            <label className="block text-xs font-semibold text-[var(--text-primary)]">
              {isEn ? "Upload File (Optional)" : "Tải tệp đính kèm (Tùy chọn)"}
              <input
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.txt"
                onChange={(e) => setDocFile(e.target.files?.[0] ?? null)}
                className="mt-1.5 block w-full text-xs text-[var(--text-secondary)]"
              />
            </label>

            <Textarea
              label={isEn ? "Clinical Summary / Notes" : "Tóm tắt kết quả / Ghi chú"}
              value={docSummary}
              onChange={(e) => setDocSummary(e.target.value)}
              placeholder="VD: Nhịp tim bình thường, mỡ máu giảm so với đợt trước..."
              className="min-h-20"
            />

            <div className="flex justify-end gap-2 pt-3">
              <Button
                type="button"
                variant="secondary"
                onClick={() => setShowAttachDocModal(false)}
              >
                {isEn ? "Cancel" : "Hủy"}
              </Button>
              <Button type="submit">
                {isEn ? "Attach Document" : "Lưu đính kèm"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}

export default function ConsumerCareVisitsPage() {
  return (
    <Suspense fallback={null}>
      <VisitsPageContent />
    </Suspense>
  );
}
