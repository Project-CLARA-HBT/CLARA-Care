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
import { v2Client, type HealthRecentResultDto, type HealthSummaryDto } from "@/lib/api/v2-client";
import { ResultExplanationModal } from "@/components/health/result-explanation-modal";

function getFlagTone(flag?: string) {
  switch (flag?.toLowerCase()) {
    case "critical_high":
    case "critical_low":
    case "critical":
      return "danger";
    case "high":
    case "low":
    case "abnormal":
      return "warn";
    case "normal":
    default:
      return "ok";
  }
}

/**
 * Accessible trend chart SVG component.
 * Renders data points, baseline reference range, and an accessible table view alternative.
 */
function TrendChart({
  result,
  locale = "vi",
}: {
  result: HealthRecentResultDto;
  locale?: "vi" | "en";
}) {
  const isEn = locale === "en";
  const points = result.history && result.history.length > 0
    ? result.history
    : [{ effective_at: result.effective_at, value: result.value, unit: result.unit, reference_range: result.reference_range, flag: result.flag }];

  const numericPoints = points
    .map((p) => ({
      date: p.effective_at,
      num: typeof p.value === "number" ? p.value : parseFloat(String(p.value).replace(/[^0-9.]/g, "")),
      raw: p.value,
      flag: p.flag,
    }))
    .filter((p) => !isNaN(p.num));

  if (numericPoints.length < 2) {
    return (
      <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)]/50 bg-[var(--surface-muted)]/20 p-3 text-xs text-[var(--text-muted)]">
        {isEn
          ? "Single measurement recorded. Trend charts become active as repeat test results are added."
          : "Chỉ có 1 lần đo. Biểu đồ xu hướng sẽ tự động vẽ khi có thêm kết quả xét nghiệm định kỳ."}
      </div>
    );
  }

  const values = numericPoints.map((p) => p.num);
  const minVal = Math.min(...values) * 0.9;
  const maxVal = Math.max(...values) * 1.1 || 1;
  const range = maxVal - minVal || 1;

  const width = 460;
  const height = 120;
  const padX = 35;
  const padY = 20;

  const coords = numericPoints.map((p, idx) => {
    const x = padX + (idx / (numericPoints.length - 1)) * (width - padX * 2);
    const y = height - padY - ((p.num - minVal) / range) * (height - padY * 2);
    return { x, y, ...p };
  });

  const polylineStr = coords.map((c) => `${c.x},${c.y}`).join(" ");

  return (
    <div
      className="space-y-2 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3"
      data-testid={`trend-chart-${result.id}`}
    >
      <div className="flex items-center justify-between text-xs">
        <span className="font-semibold text-[var(--text-primary)]">
          {isEn ? "Historical Trend" : "Biểu đồ xu hướng"} ({numericPoints.length} {isEn ? "points" : "lần xét nghiệm"})
        </span>
        <span className="text-[11px] text-[var(--text-muted)]">
          {result.unit ? `Đơn vị: ${result.unit}` : ""}
        </span>
      </div>

      <div className="relative overflow-x-auto">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-28 text-[var(--brand-600)]"
          aria-label={`Biểu đồ xu hướng cho ${result.test_name}`}
          role="img"
        >
          {/* Grid lines */}
          <line
            x1={padX}
            y1={height - padY}
            x2={width - padX}
            y2={height - padY}
            stroke="currentColor"
            strokeOpacity="0.15"
            strokeWidth="1"
          />
          <line
            x1={padX}
            y1={padY}
            x2={width - padX}
            y2={padY}
            stroke="currentColor"
            strokeOpacity="0.15"
            strokeWidth="1"
          />

          {/* Trend line */}
          <polyline
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            points={polylineStr}
          />

          {/* Data points */}
          {coords.map((c, i) => (
            <g key={i}>
              <circle
                cx={c.x}
                cy={c.y}
                r="4"
                className="fill-[var(--surface-panel)] stroke-[var(--brand-600)] stroke-2"
              />
              <text
                x={c.x}
                y={c.y - 7}
                textAnchor="middle"
                fontSize="10"
                fill="currentColor"
                fontWeight="bold"
              >
                {c.num}
              </text>
            </g>
          ))}
        </svg>
      </div>

      {/* Accessible data table for screen readers and high clarity */}
      <table className="sr-only" aria-label={`Bảng dữ liệu lịch sử cho ${result.test_name}`}>
        <thead>
          <tr>
            <th>{isEn ? "Date" : "Ngày"}</th>
            <th>{isEn ? "Value" : "Giá trị"}</th>
            <th>{isEn ? "Status" : "Trạng thái"}</th>
          </tr>
        </thead>
        <tbody>
          {numericPoints.map((p, idx) => (
            <tr key={idx}>
              <td>{p.date}</td>
              <td>{p.raw} {result.unit}</td>
              <td>{p.flag ?? "normal"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ResultsPageContent() {
  const uiLanguage = useUILanguage();
  const isEn = uiLanguage === "en";
  const [activeProfileId, setActiveProfileId] = useState<string | null>(getActiveProfileId());
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedResult, setSelectedResult] = useState<HealthRecentResultDto | null>(null);

  const queryKey = queryKeys.profile(activeProfileId).health.summary();
  const { data, isLoading, isError, error, refetch } = useQuery<HealthSummaryDto>({
    queryKey,
    queryFn: () => v2Client.getHealthSummary(activeProfileId),
  });

  const results = useMemo(() => {
    return data?.recent_results ?? [];
  }, [data?.recent_results]);

  const categories = useMemo(() => {
    const set = new Set<string>();
    for (const r of results) {
      if (r.category) set.add(r.category);
    }
    return Array.from(set);
  }, [results]);

  const filteredResults = useMemo(() => {
    return results.filter((r) => {
      const matchCat = categoryFilter === "all" || r.category === categoryFilter;
      const q = searchQuery.toLowerCase().trim();
      const matchQuery =
        !q ||
        r.test_name.toLowerCase().includes(q) ||
        (r.category && r.category.toLowerCase().includes(q));
      return matchCat && matchQuery;
    });
  }, [results, categoryFilter, searchQuery]);

  return (
    <div
      className="mx-auto max-w-5xl space-y-6 pb-12"
      data-testid="health-results-page"
    >
      <HealthPageHeader
        title={isEn ? "Lab & Diagnostic Results" : "Kết quả xét nghiệm & Chẩn đoán"}
        subtitle={
          isEn
            ? "Track lab values, reference intervals, historical trends, and clinician-verified test panels."
            : "Tra cứu chỉ số xét nghiệm, khoảng tham chiếu phòng lab, biểu đồ xu hướng và phân loại bất thường."
        }
        backHref="/health"
        backLabel={isEn ? "Back to Health" : "Quay lại Sức khỏe"}
        locale={uiLanguage}
      />

      {/* Filter Chips & Search */}
      <section
        className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5 space-y-3"
        data-testid="results-filters"
      >
        <Field
          type="search"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder={isEn ? "Search test name or category..." : "Tìm tên xét nghiệm, nhóm chỉ số..."}
          data-testid="results-search-input"
        />

        <div className="flex flex-wrap items-center gap-2 pt-1">
          <button
            type="button"
            onClick={() => setCategoryFilter("all")}
            className={`rounded-[var(--radius-pill)] border px-3 py-1 text-xs font-semibold transition ${
              categoryFilter === "all"
                ? "border-[color:var(--brand-600)] bg-[var(--brand-600)] text-[var(--button-primary-text)]"
                : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]"
            }`}
          >
            {isEn ? "All Panels" : "Tất cả xét nghiệm"}
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              type="button"
              onClick={() => setCategoryFilter(cat)}
              className={`rounded-[var(--radius-pill)] border px-3 py-1 text-xs font-semibold transition ${
                categoryFilter === cat
                  ? "border-[color:var(--brand-600)] bg-[var(--brand-600)] text-[var(--button-primary-text)]"
                  : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </section>

      {/* Error state */}
      {isError && (
        <InlineError
          severity="error"
          title={isEn ? "Failed to load results" : "Không thể tải kết quả xét nghiệm"}
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

      {/* Empty State */}
      {!isLoading && filteredResults.length === 0 && (
        <EmptyState
          title={isEn ? "No results found" : "Chưa có kết quả xét nghiệm"}
          description={
            isEn
              ? "No diagnostic reports match your current filters. Upload documents or sync lab records to populate results."
              : "Không tìm thấy kết quả nào phù hợp. Bạn có thể tải lên phiếu xét nghiệm tại mục Tài liệu để trích xuất chỉ số."
          }
          icon="scan"
        />
      )}

      {/* Results List with Reference Ranges & Trend Charts */}
      {!isLoading && filteredResults.length > 0 && (
        <div className="space-y-4" data-testid="results-list">
          {filteredResults.map((result) => {
            const formattedDate = result.effective_at
              ? formatLocaleDate(uiLanguage, result.effective_at, {
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                })
              : "";

            return (
              <article
                key={result.id}
                className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5 space-y-3 shadow-xs"
                data-testid={`result-card-${result.id}`}
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[color:var(--shell-border)]/50 pb-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-bold text-base text-[var(--text-primary)]">
                        {result.test_name}
                      </h3>
                      {result.category && (
                        <span className="rounded-[var(--radius-sm)] bg-[var(--surface-muted)] px-2 py-0.5 text-[11px] font-medium text-[var(--text-secondary)]">
                          {result.category}
                        </span>
                      )}
                      {result.flag && (
                        <Badge tone={getFlagTone(result.flag)}>
                          {result.flag}
                        </Badge>
                      )}
                    </div>
                    {formattedDate && (
                      <span className="text-xs text-[var(--text-muted)] mt-1 block">
                        {isEn ? "Tested on: " : "Ngày xét nghiệm: "}{formattedDate}
                        {result.source_name ? ` • ${result.source_name}` : ""}
                      </span>
                    )}
                  </div>

                  <div className="text-right sm:self-center shrink-0">
                    <div className="text-lg sm:text-xl font-extrabold text-[var(--text-primary)]">
                      {result.value}{" "}
                      <span className="text-xs font-normal text-[var(--text-secondary)]">
                        {result.unit}
                      </span>
                    </div>
                    {result.reference_range && (
                      <span className="text-[11px] text-[var(--text-muted)] block">
                        {isEn ? "Reference: " : "Tham chiếu: "}{result.reference_range}
                      </span>
                    )}
                  </div>
                </div>

                {/* Trend Chart component */}
                <TrendChart result={result} locale={uiLanguage} />

                <div className="flex justify-end pt-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    icon="help"
                    onClick={() => setSelectedResult(result)}
                    data-testid={`explain-result-${result.id}`}
                  >
                    {isEn ? "Explain this result" : "Giải thích chỉ số này"}
                  </Button>
                </div>
              </article>
            );
          })}
        </div>
      )}

      {/* Result Explanation Modal */}
      {selectedResult && (
        <ResultExplanationModal
          open={Boolean(selectedResult)}
          onClose={() => setSelectedResult(null)}
          result={selectedResult}
          locale={uiLanguage}
        />
      )}
    </div>
  );
}

export default function ResultsPage() {
  return <ResultsPageContent />;
}
