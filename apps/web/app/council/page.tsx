"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import CouncilEmptyState from "@/components/council/council-empty-state";
import { ListDetailLayout } from "@/components/page/list-detail-layout";
import { HeroObject } from "@/components/ui/hero-object";
import { Icon, type IconName } from "@/components/ui/icon";
import { SurfaceCard } from "@/components/ui/surface";
import { trackCouncilViewed } from "@/lib/analytics/events";
import { formatLocaleDate, t } from "@/lib/i18n/catalog";
import { safeUserFacingError, stripTelemetryLabels } from "@/lib/user-facing-text";
import { useUILanguage } from "@/lib/use-ui-language";
import {
  CouncilCaseRecord,
  getActiveCouncilCaseId,
  getCouncilCase,
  getLatestCouncilCase,
  listCouncilCases,
  setActiveCouncilCaseId,
} from "@/lib/council";

type StatusFilter = "all" | "analyzed" | "in_progress" | "draft";

function getCaseStatusMeta(
  language: "vi" | "en",
  status: string,
): { label: string; className: string; icon: IconName } {
  switch (status) {
    case "analyzed":
      return {
        label: language === "vi" ? "Đã hội chẩn" : "Deliberated",
        className:
          "border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] text-[var(--text-brand)]",
        icon: "check",
      };
    case "specialists_ready":
      return {
        label: language === "vi" ? "Chờ rà soát" : "Ready for Review",
        className:
          "border-[color:var(--status-warning-border)] bg-[var(--surface-warning-soft)] text-[var(--text-warning)]",
        icon: "progress",
      };
    case "intake_ready":
      return {
        label: language === "vi" ? "Chờ chuyên khoa" : "Intake Ready",
        className:
          "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]",
        icon: "clinical-notes",
      };
    default:
      return {
        label: language === "vi" ? "Bản nháp" : "Draft",
        className:
          "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-muted)]",
        icon: "clinical-notes",
      };
  }
}

function resolveCaseHref(caseItem: CouncilCaseRecord): string {
  switch (caseItem.status) {
    case "analyzed":
      return `/council/result?caseId=${caseItem.id}`;
    case "specialists_ready":
      return `/council/new/review?caseId=${caseItem.id}`;
    case "intake_ready":
      return `/council/new/specialists?caseId=${caseItem.id}`;
    default:
      return `/council/new/intake?caseId=${caseItem.id}`;
  }
}

function resolveActionLabel(language: "vi" | "en", status: string): string {
  switch (status) {
    case "analyzed":
      return language === "vi" ? "Xem kết luận hội chẩn" : "View Council Result";
    case "specialists_ready":
      return language === "vi" ? "Rà soát & Bắt đầu" : "Review & Run";
    case "intake_ready":
      return language === "vi" ? "Chọn chuyên khoa" : "Select Specialists";
    default:
      return language === "vi" ? "Tiếp tục nhập liệu" : "Continue Intake";
  }
}

function getCaseSnippet(caseItem: CouncilCaseRecord): string {
  const request = (caseItem.request ?? {}) as Record<string, unknown>;
  if (typeof request.question === "string" && request.question.trim()) {
    return request.question.trim();
  }
  if (caseItem.result && typeof caseItem.result === "object") {
    const finalRec = (caseItem.result as Record<string, unknown>).final_recommendation;
    if (typeof finalRec === "string" && finalRec.trim()) {
      return stripTelemetryLabels(finalRec);
    }
  }
  if (Array.isArray(request.symptoms) && request.symptoms.length > 0) {
    return request.symptoms.map(String).join(", ");
  }
  if (caseItem.transcript) {
    return caseItem.transcript.slice(0, 140);
  }
  return "";
}

function getSpecialists(caseItem: CouncilCaseRecord): string[] {
  const request = (caseItem.request ?? {}) as Record<string, unknown>;
  if (Array.isArray(request.specialists)) {
    return request.specialists.map(String).filter(Boolean);
  }
  return [];
}

export default function CouncilPage() {
  const router = useRouter();
  const language = useUILanguage();
  const [cases, setCases] = useState<CouncilCaseRecord[]>([]);
  const [activeCase, setActiveCase] = useState<CouncilCaseRecord | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    trackCouncilViewed({ view: "landing" });
  }, []);

  useEffect(() => {
    const load = async () => {
      setIsLoading(true);
      setError("");
      try {
        const storedActiveId = getActiveCouncilCaseId();
        const [caseList, latest] = await Promise.all([
          listCouncilCases(50, 0),
          storedActiveId ? getCouncilCase(storedActiveId).catch(() => getLatestCouncilCase()) : getLatestCouncilCase(),
        ]);
        setCases(caseList.items || []);
        if (latest) {
          setActiveCase(latest);
          setActiveCouncilCaseId(latest.id);
        } else if (caseList.items && caseList.items.length > 0) {
          setActiveCase(caseList.items[0]);
          setActiveCouncilCaseId(caseList.items[0].id);
        } else {
          setActiveCase(null);
        }
      } catch (cause) {
        setError(safeUserFacingError(cause, t(language, "council.error.loadCases")));
      } finally {
        setIsLoading(false);
      }
    };
    void load();
  }, [language]);

  const filteredCases = useMemo(() => {
    return cases.filter((item) => {
      if (statusFilter === "analyzed" && item.status !== "analyzed") return false;
      if (statusFilter === "in_progress" && (item.status === "analyzed" || item.status === "created")) return false;
      if (statusFilter === "draft" && item.status !== "created" && item.status !== "intake_ready") return false;

      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase().trim();
      const titleMatch = (item.title || "").toLowerCase().includes(q);
      const idMatch = String(item.id).includes(q);
      const snippetMatch = getCaseSnippet(item).toLowerCase().includes(q);
      return titleMatch || idMatch || snippetMatch;
    });
  }, [cases, searchQuery, statusFilter]);

  const onSelectCase = (item: CouncilCaseRecord) => {
    setActiveCouncilCaseId(item.id);
    setActiveCase(item);
    const href = resolveCaseHref(item);
    router.push(href);
  };

  const activeCaseMeta = activeCase ? getCaseStatusMeta(language, activeCase.status) : null;
  const activeCaseSpecialists = activeCase ? getSpecialists(activeCase) : [];

  return (
    <ListDetailLayout
      data-workspace="clinical"
      workspace="clinical"
      eyebrow={language === "vi" ? "Hội đồng Chuyên khoa" : "Clinical Council Library"}
      title={language === "vi" ? "Thư viện ca hội chẩn" : "Case Library"}
      subtitle={
        language === "vi"
          ? "Quản lý danh sách ca bệnh lâm sàng, tiếp tục ca đang thực hiện hoặc khởi tạo phiên hội chẩn mới."
          : "Manage clinical cases, resume active deliberation, or create a new multi-specialty council."
      }
      badges={
        cases.length > 0 ? (
          <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-0.5 text-xs font-semibold text-[var(--text-muted)]">
            {cases.length} {language === "vi" ? "ca bệnh" : "cases"}
          </span>
        ) : null
      }
      headerActions={
        <div className="flex items-center gap-3 shrink-0">
          <Link
            href="/council/new"
            className="inline-flex min-h-[44px] items-center gap-2 rounded-xl border border-[color:var(--brand-700)] bg-[var(--brand-600)] px-5 text-sm font-bold text-[var(--on-secondary-container)] shadow-sm transition hover:bg-[var(--brand-700)]"
          >
            <Icon name="progress" size={16} />
            <span>+ {language === "vi" ? "Tạo ca mới" : "New Council"}</span>
          </Link>
        </div>
      }
      toolbar={
        <div className="space-y-4">
          {error ? (
            <div className="rounded-xl border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-4 text-sm font-semibold text-[var(--status-danger-text)]">
              {error}
            </div>
          ) : null}

          {/* Active Case Hero Object */}
          {activeCase ? (
            <div aria-label="Active resumable case">
              <HeroObject
                variant="clinical"
                contextTag={language === "vi" ? "Ca đang thực hiện" : "Active Case"}
                supportingMeta={
                  <span className="font-mono text-xs text-[var(--text-muted)]">
                    {formatLocaleDate(language, activeCase.updated_at, {
                      day: "2-digit",
                      month: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                }
                status={
                  activeCaseMeta ? (
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-0.5 text-xs font-bold ${activeCaseMeta.className}`}
                    >
                      <Icon name={activeCaseMeta.icon} size={12} />
                      {activeCaseMeta.label}
                    </span>
                  ) : null
                }
                title={
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-base font-bold text-[var(--text-brand)]">
                      #{activeCase.id}
                    </span>
                    <span>{activeCase.title || t(language, "council.new.caseFallback", { id: activeCase.id })}</span>
                  </div>
                }
                description={getCaseSnippet(activeCase)}
                primaryAction={{
                  label: resolveActionLabel(language, activeCase.status),
                  onClick: () => onSelectCase(activeCase),
                  icon: "arrow-right",
                  tone: "primary",
                }}
                secondaryAction={{
                  label: language === "vi" ? "Khởi tạo ca khác" : "Create another case",
                  href: "/council/new",
                  tone: "secondary",
                }}
              >
                <div className="mt-3 space-y-2">
                  {activeCaseSpecialists.length > 0 ? (
                    <div className="flex flex-wrap items-center gap-1.5 pt-1">
                      <span className="text-xs font-bold text-[var(--text-muted)]">
                        {language === "vi" ? "Chuyên khoa:" : "Specialists:"}
                      </span>
                      {activeCaseSpecialists.map((s) => (
                        <span
                          key={s}
                          className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-0.5 text-xs font-semibold text-[var(--text-primary)]"
                        >
                          {s}
                        </span>
                      ))}
                    </div>
                  ) : null}

                  {activeCase.oversight_state === "paused" ? (
                    <div className="rounded-xl border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] p-3 text-xs font-semibold text-[var(--status-warn-text)]">
                      {language === "vi"
                        ? "Quy trình hội chẩn ca này đang tạm dừng để bác sĩ đối chiếu chuyên môn."
                        : "Council process is currently paused for clinician review."}
                    </div>
                  ) : null}
                </div>
              </HeroObject>
            </div>
          ) : null}

          {/* Filter & Search Bar */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between pt-2">
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold text-[var(--text-primary)]">
                {language === "vi" ? "Danh sách ca gần đây" : "Recent Cases"}
              </h3>
              <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-0.5 text-xs font-bold text-[var(--text-secondary)]">
                {filteredCases.length}
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <div className="flex rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-1">
                <button
                  type="button"
                  onClick={() => setStatusFilter("all")}
                  className={`rounded-lg px-3 py-1 text-xs font-bold transition ${
                    statusFilter === "all"
                      ? "bg-[var(--surface-panel)] text-[var(--text-primary)] shadow-sm"
                      : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                  }`}
                >
                  {language === "vi" ? "Tất cả" : "All"}
                </button>
                <button
                  type="button"
                  onClick={() => setStatusFilter("analyzed")}
                  className={`rounded-lg px-3 py-1 text-xs font-bold transition ${
                    statusFilter === "analyzed"
                      ? "bg-[var(--surface-panel)] text-[var(--text-brand)] shadow-sm"
                      : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                  }`}
                >
                  {language === "vi" ? "Đã hội chẩn" : "Deliberated"}
                </button>
                <button
                  type="button"
                  onClick={() => setStatusFilter("in_progress")}
                  className={`rounded-lg px-3 py-1 text-xs font-bold transition ${
                    statusFilter === "in_progress"
                      ? "bg-[var(--surface-panel)] text-[var(--text-warning)] shadow-sm"
                      : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                  }`}
                >
                  {language === "vi" ? "Đang xử lý" : "In Progress"}
                </button>
              </div>

              <div className="relative min-w-[200px]">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder={language === "vi" ? "Tìm theo tiêu đề, #ID..." : "Search title, #ID..."}
                  className="w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3.5 py-1.5 text-xs text-[var(--text-primary)] focus:border-[color:var(--brand-600)] focus:outline-none"
                />
              </div>
            </div>
          </div>
        </div>
      }
      splitRatio="65/35"
      selectedId={activeCase?.id}
      list={
        <div className="space-y-3">
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="h-20 animate-pulse rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]"
                />
              ))}
            </div>
          ) : null}

          {!isLoading && filteredCases.length === 0 ? (
            <CouncilEmptyState
              title={t(language, "council.empty.title")}
              description={
                searchQuery
                  ? language === "vi"
                    ? "Không tìm thấy ca bệnh nào phù hợp với bộ lọc."
                    : "No cases match your search filter."
                  : t(language, "council.new.empty")
              }
            />
          ) : null}

          {!isLoading && filteredCases.length > 0 ? (
            <div className="divide-y divide-[color:var(--shell-border)] rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] overflow-hidden shadow-sm">
              {filteredCases.map((item) => {
                const meta = getCaseStatusMeta(language, item.status);
                const snippet = getCaseSnippet(item);
                const specialists = getSpecialists(item);
                const isSelected = activeCase?.id === item.id;

                return (
                  <article
                    key={item.id}
                    onClick={() => onSelectCase(item)}
                    className={`cursor-pointer p-4 sm:p-5 transition-colors hover:bg-[var(--surface-muted)] flex flex-col sm:flex-row sm:items-center justify-between gap-4 ${
                      isSelected ? "bg-[var(--surface-brand-soft)]/40 border-l-4 border-l-[color:var(--brand-600)]" : ""
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs font-bold text-[var(--text-brand)]">
                          #{item.id}
                        </span>
                        <h4 className="text-sm font-bold text-[var(--text-primary)] truncate">
                          {item.title || t(language, "council.new.caseFallback", { id: item.id })}
                        </h4>
                        <span
                          className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-bold ${meta.className}`}
                        >
                          <Icon name={meta.icon} size={11} />
                          {meta.label}
                        </span>
                      </div>

                      {snippet ? (
                        <p className="mt-1.5 text-xs text-[var(--text-secondary)] line-clamp-1">
                          {snippet}
                        </p>
                      ) : null}

                      {specialists.length > 0 ? (
                        <div className="mt-2 flex flex-wrap items-center gap-1.5">
                          {specialists.slice(0, 4).map((spec) => (
                            <span
                              key={spec}
                              className="rounded bg-[var(--surface-muted)] px-2 py-0.5 text-[10px] font-medium text-[var(--text-muted)]"
                            >
                              {spec}
                            </span>
                          ))}
                          {specialists.length > 4 ? (
                            <span className="text-[10px] text-[var(--text-muted)]">
                              +{specialists.length - 4}
                            </span>
                          ) : null}
                        </div>
                      ) : null}
                    </div>

                    <div className="flex items-center justify-between sm:justify-end gap-3 shrink-0">
                      <span className="font-mono text-xs text-[var(--text-muted)]">
                        {formatLocaleDate(language, item.updated_at, {
                          day: "2-digit",
                          month: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectCase(item);
                        }}
                        className="inline-flex min-h-[36px] items-center gap-1.5 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3.5 text-xs font-bold text-[var(--text-primary)] hover:border-[color:var(--brand-600)] hover:bg-[var(--surface-panel)] transition"
                      >
                        <span>{resolveActionLabel(language, item.status)}</span>
                        <Icon name="arrow-right" size={14} />
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          ) : null}
        </div>
      }
      detail={
        activeCase ? (
          <SurfaceCard className="p-5 sm:p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-[color:var(--shell-border)] pb-3">
              <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
                {language === "vi" ? "Thông tin ca hội chẩn" : "Case Quick Inspector"}
              </span>
              <span className="font-mono text-xs font-bold text-[var(--text-muted)]">
                #{activeCase.id}
              </span>
            </div>

            <div>
              <h3 className="text-base font-bold text-[var(--text-primary)]">
                {activeCase.title || t(language, "council.new.caseFallback", { id: activeCase.id })}
              </h3>
              <p className="mt-1 text-xs text-[var(--text-secondary)] leading-relaxed">
                {getCaseSnippet(activeCase) || (language === "vi" ? "Chưa có tóm tắt lâm sàng" : "No clinical summary")}
              </p>
            </div>

            {activeCaseSpecialists.length > 0 ? (
              <div>
                <p className="text-xs font-bold text-[var(--text-muted)] mb-1.5">
                  {language === "vi" ? "Hội đồng chuyên khoa tham gia:" : "Consulting Specialists:"}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {activeCaseSpecialists.map((s) => (
                    <span
                      key={s}
                      className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 text-xs font-semibold text-[var(--text-primary)]"
                    >
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="pt-3 border-t border-[color:var(--shell-border)] space-y-2">
              <button
                type="button"
                onClick={() => onSelectCase(activeCase)}
                className="w-full inline-flex min-h-[44px] items-center justify-center gap-2 rounded-xl border border-[color:var(--brand-700)] bg-[var(--brand-600)] px-4 text-sm font-bold text-[var(--on-secondary-container)] shadow-sm transition hover:bg-[var(--brand-700)]"
              >
                <span>{resolveActionLabel(language, activeCase.status)}</span>
                <Icon name="arrow-right" size={16} />
              </button>

              <Link
                href="/council/new"
                className="w-full inline-flex min-h-[44px] items-center justify-center gap-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 text-xs font-semibold text-[var(--text-primary)] hover:bg-[var(--surface-panel)]"
              >
                {language === "vi" ? "Tạo ca hội chẩn mới" : "Start New Council Case"}
              </Link>
            </div>
          </SurfaceCard>
        ) : null
      }
    />
  );
}
