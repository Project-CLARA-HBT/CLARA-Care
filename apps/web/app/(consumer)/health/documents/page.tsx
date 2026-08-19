"use client";

import { useMemo, useState } from "react";
import { HealthPageHeader } from "@/components/consumer/health-page-header";
import { SourceBadge } from "@/components/health/source-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { EmptyState } from "@/components/shared/empty-state";
import { InlineError } from "@/components/shared/inline-error";
import { useUILanguage } from "@/lib/use-ui-language";
import { formatLocaleDate } from "@/lib/i18n/catalog";
import { getActiveProfileId } from "@/lib/profile-context";
import { useQuery } from "@/lib/query/use-query";
import { queryKeys } from "@/lib/query/query-keys";
import { v2Client, type HealthDocumentDto, type HealthSummaryDto } from "@/lib/api/v2-client";

function getDocumentKindMeta(kind?: string, locale: "vi" | "en" = "vi") {
  const isEn = locale === "en";
  switch (kind?.toLowerCase()) {
    case "prescription":
      return { label: isEn ? "Prescription" : "Đơn thuốc", tone: "brand" as const, icon: "medication" as const };
    case "lab_report":
      return { label: isEn ? "Lab Report" : "Phiếu xét nghiệm", tone: "brand" as const, icon: "scan" as const };
    case "discharge_summary":
      return { label: isEn ? "Discharge Summary" : "Giấy ra viện", tone: "ok" as const, icon: "clinical-notes" as const };
    case "clinical_note":
      return { label: isEn ? "Clinical Note" : "Tóm tắt bệnh án", tone: "ok" as const, icon: "clinical-notes" as const };
    case "imaging":
      return { label: isEn ? "Medical Imaging" : "Chẩn đoán hình ảnh", tone: "neutral" as const, icon: "scan" as const };
    default:
      return { label: isEn ? "Health Document" : "Tài liệu y tế", tone: "neutral" as const, icon: "folder" as const };
  }
}

function DocumentsPageContent() {
  const uiLanguage = useUILanguage();
  const isEn = uiLanguage === "en";
  const [activeProfileId, setActiveProfileId] = useState<string | null>(getActiveProfileId());
  const [selectedKindFilter, setSelectedKindFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  const queryKey = queryKeys.profile(activeProfileId).health.summary();
  const { data, isLoading, isError, error, refetch } = useQuery<HealthSummaryDto>({
    queryKey,
    queryFn: () => v2Client.getHealthSummary(activeProfileId),
  });

  const documents: HealthDocumentDto[] = useMemo(() => {
    return data?.documents ?? [];
  }, [data?.documents]);

  const filteredDocuments = useMemo(() => {
    return documents.filter((doc) => {
      const matchKind = selectedKindFilter === "all" || doc.kind === selectedKindFilter;
      const q = searchQuery.toLowerCase().trim();
      const matchQuery =
        !q ||
        doc.title.toLowerCase().includes(q) ||
        (doc.extracted_summary && doc.extracted_summary.toLowerCase().includes(q)) ||
        (doc.source_name && doc.source_name.toLowerCase().includes(q));
      return matchKind && matchQuery;
    });
  }, [documents, selectedKindFilter, searchQuery]);

  return (
    <div
      className="mx-auto max-w-5xl space-y-6 pb-12"
      data-testid="health-documents-page"
    >
      <HealthPageHeader
        title={isEn ? "Health Documents & Provenance" : "Tài liệu & Hồ sơ y tế"}
        subtitle={
          isEn
            ? "Central repository of medical records, discharge summaries, lab scans, and extracted clinical facts."
            : "Kho lưu trữ đơn thuốc, kết quả xét nghiệm, giấy ra viện và nguồn trích xuất dữ liệu y tế."
        }
        backHref="/health"
        backLabel={isEn ? "Back to Health" : "Quay lại Sức khỏe"}
        locale={uiLanguage}
        primaryAction={{
          label: isEn ? "Upload / Scan Document" : "Tải lên / Quét tài liệu",
          href: "/phr",
          icon: "folder",
        }}
      />

      {/* Filter and Search */}
      <section
        className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5 space-y-3"
        data-testid="documents-filters"
      >
        <Field
          type="search"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder={isEn ? "Search by document title, doctor, facility..." : "Tìm tên tài liệu, cơ sở y tế, bác sĩ..."}
          data-testid="documents-search-input"
        />

        <div className="flex flex-wrap items-center gap-2 pt-1">
          <button
            type="button"
            onClick={() => setSelectedKindFilter("all")}
            className={`rounded-[var(--radius-pill)] border px-3 py-1 text-xs font-semibold transition ${
              selectedKindFilter === "all"
                ? "border-[color:var(--brand-600)] bg-[var(--brand-600)] text-[var(--button-primary-text)]"
                : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]"
            }`}
          >
            {isEn ? "All Documents" : "Tất cả tài liệu"}
          </button>
          {[
            { key: "prescription", labelVi: "Đơn thuốc", labelEn: "Prescriptions" },
            { key: "lab_report", labelVi: "Phiếu xét nghiệm", labelEn: "Lab Reports" },
            { key: "discharge_summary", labelVi: "Giấy ra viện", labelEn: "Discharge Summaries" },
            { key: "clinical_note", labelVi: "Tóm tắt bệnh án", labelEn: "Clinical Notes" },
            { key: "imaging", labelVi: "Chẩn đoán hình ảnh", labelEn: "Imaging" },
          ].map((k) => (
            <button
              key={k.key}
              type="button"
              onClick={() => setSelectedKindFilter(k.key)}
              className={`rounded-[var(--radius-pill)] border px-3 py-1 text-xs font-semibold transition ${
                selectedKindFilter === k.key
                  ? "border-[color:var(--brand-600)] bg-[var(--brand-600)] text-[var(--button-primary-text)]"
                  : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]"
              }`}
            >
              {isEn ? k.labelEn : k.labelVi}
            </button>
          ))}
        </div>
      </section>

      {/* Error state */}
      {isError && (
        <InlineError
          severity="error"
          title={isEn ? "Failed to load documents" : "Không thể tải danh sách tài liệu"}
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

      {/* Empty state */}
      {!isLoading && filteredDocuments.length === 0 && (
        <EmptyState
          title={isEn ? "No documents found" : "Chưa có tài liệu nào"}
          description={
            isEn
              ? "Upload photos or scans of medical documents to keep them securely organized and extract key facts."
              : "Bạn có thể chụp ảnh hoặc tải lên đơn thuốc, kết quả xét nghiệm để lưu trữ và trích xuất thông tin."
          }
          icon="folder"
        >
          <div className="mt-3">
            <Button as="link" href="/phr" variant="primary" icon="folder">
              {isEn ? "Upload Document (OCR)" : "Tải lên tài liệu (OCR)"}
            </Button>
          </div>
        </EmptyState>
      )}

      {/* Documents Grid / List */}
      {!isLoading && filteredDocuments.length > 0 && (
        <div className="space-y-4" data-testid="documents-list">
          {filteredDocuments.map((doc) => {
            const meta = getDocumentKindMeta(doc.kind, uiLanguage);
            const formattedDate = doc.recorded_at
              ? formatLocaleDate(uiLanguage, doc.recorded_at, {
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                })
              : "";

            return (
              <article
                key={doc.id}
                className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5 shadow-xs transition hover:border-[color:var(--brand-500)]"
                data-testid={`document-card-${doc.id}`}
              >
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                  <div className="flex items-start gap-3 min-w-0 flex-1">
                    <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-[var(--radius-lg)] bg-[var(--surface-muted)] text-[var(--text-brand)]">
                      <Icon name={meta.icon} size="1.25rem" />
                    </span>

                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-bold text-base text-[var(--text-primary)]">
                          {doc.title}
                        </h3>
                        <Badge tone={meta.tone}>{meta.label}</Badge>
                        {doc.verification_state && (
                          <SourceBadge verificationState={doc.verification_state as any} locale={uiLanguage} />
                        )}
                      </div>

                      {doc.extracted_summary && (
                        <p className="text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed">
                          {doc.extracted_summary}
                        </p>
                      )}

                      <div className="flex flex-wrap items-center gap-3 text-xs text-[var(--text-muted)] pt-1">
                        {formattedDate && (
                          <span className="inline-flex items-center gap-1">
                            <Icon name="calendar" size="0.8rem" />
                            <time dateTime={doc.recorded_at}>{formattedDate}</time>
                          </span>
                        )}
                        {doc.source_name && <span>• {doc.source_name}</span>}
                        {doc.provenance?.facility && <span>• {doc.provenance.facility}</span>}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 self-end sm:self-start shrink-0">
                    {doc.file_url && (
                      <a
                        href={doc.file_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="fluent-button-secondary inline-flex min-h-[var(--touch-target-min)] items-center justify-center gap-1.5 rounded-[var(--radius-md)] px-3 py-1.5 text-xs font-semibold"
                      >
                        <Icon name="download" size="0.85rem" />
                        <span>{isEn ? "View File" : "Xem tệp"}</span>
                      </a>
                    )}
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function DocumentsPage() {
  return <DocumentsPageContent />;
}
