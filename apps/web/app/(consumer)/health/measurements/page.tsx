"use client";

import { useMemo, useState } from "react";
import { HealthPageHeader } from "@/components/consumer/health-page-header";
import { SourceBadge } from "@/components/health/source-badge";
import { MeasurementEditorModal } from "@/components/health/measurement-editor-modal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { EmptyState } from "@/components/shared/empty-state";
import { InlineError } from "@/components/shared/inline-error";
import { useUILanguage } from "@/lib/use-ui-language";
import { formatLocaleDate } from "@/lib/i18n/catalog";
import { getActiveProfileId } from "@/lib/profile-context";
import { useQuery } from "@/lib/query/use-query";
import { queryKeys } from "@/lib/query/query-keys";
import { v2Client, type HealthMeasurementDto, type HealthSummaryDto } from "@/lib/api/v2-client";

function MeasurementsPageContent() {
  const uiLanguage = useUILanguage();
  const isEn = uiLanguage === "en";
  const [activeProfileId, setActiveProfileId] = useState<string | null>(getActiveProfileId());
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedTypeFilter, setSelectedTypeFilter] = useState<string>("all");

  const queryKey = queryKeys.profile(activeProfileId).health.summary();
  const { data, isLoading, isError, error, refetch } = useQuery<HealthSummaryDto>({
    queryKey,
    queryFn: () => v2Client.getHealthSummary(activeProfileId),
  });

  const measurements = useMemo(() => {
    return data?.current?.important_measurements ?? [];
  }, [data]);

  const filteredMeasurements = useMemo(() => {
    if (selectedTypeFilter === "all") return measurements;
    return measurements.filter((m) => m.type === selectedTypeFilter);
  }, [measurements, selectedTypeFilter]);

  return (
    <div
      className="mx-auto max-w-5xl space-y-6 pb-12"
      data-testid="health-measurements-page"
    >
      <HealthPageHeader
        title={isEn ? "Vital Signs & Measurements" : "Chỉ số sức khỏe & Sinh hiệu"}
        subtitle={
          isEn
            ? "Log and monitor blood pressure, blood glucose, heart rate, weight, and connected medical device metrics."
            : "Theo dõi huyết áp, nhịp tim, đường huyết, cân nặng và các dữ liệu đồng bộ từ thiết bị y tế cá nhân."
        }
        backHref="/health"
        backLabel={isEn ? "Back to Health" : "Quay lại Sức khỏe"}
        locale={uiLanguage}
        primaryAction={{
          label: isEn ? "+ Log Measurement" : "+ Ghi nhận chỉ số",
          onClick: () => setShowAddModal(true),
          icon: "scan",
        }}
      />

      {/* Metric Category Quick Filters */}
      <section
        className="flex flex-wrap items-center gap-2 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3"
        data-testid="measurement-filters"
      >
        <button
          type="button"
          onClick={() => setSelectedTypeFilter("all")}
          className={`rounded-[var(--radius-pill)] border px-3 py-1 text-xs font-semibold transition ${
            selectedTypeFilter === "all"
              ? "border-[color:var(--brand-600)] bg-[var(--brand-600)] text-[var(--button-primary-text)]"
              : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]"
          }`}
        >
          {isEn ? "All Metrics" : "Tất cả chỉ số"}
        </button>
        {["blood_pressure", "heart_rate", "blood_glucose", "spo2", "weight", "height", "temperature"].map((tKey) => (
          <button
            key={tKey}
            type="button"
            onClick={() => setSelectedTypeFilter(tKey)}
            className={`rounded-[var(--radius-pill)] border px-3 py-1 text-xs font-semibold transition ${
              selectedTypeFilter === tKey
                ? "border-[color:var(--brand-600)] bg-[var(--brand-600)] text-[var(--button-primary-text)]"
                : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]"
            }`}
          >
            {tKey === "blood_pressure"
              ? isEn ? "Blood Pressure" : "Huyết áp"
              : tKey === "heart_rate"
                ? isEn ? "Heart Rate" : "Nhịp tim"
                : tKey === "blood_glucose"
                  ? isEn ? "Glucose" : "Đường huyết"
                  : tKey === "spo2"
                    ? "SpO2"
                    : tKey === "weight"
                      ? isEn ? "Weight" : "Cân nặng"
                      : tKey === "height"
                        ? isEn ? "Height" : "Chiều cao"
                        : isEn ? "Temperature" : "Thân nhiệt"}
          </button>
        ))}
      </section>

      {/* Error state */}
      {isError && (
        <InlineError
          severity="error"
          title={isEn ? "Failed to load measurements" : "Không thể tải chỉ số"}
          message={error instanceof Error ? error.message : "Error"}
          onRetry={() => void refetch()}
        />
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 animate-pulse">
          {[1, 2, 3, 4, 5, 6].map((n) => (
            <div
              key={n}
              className="h-36 rounded-[var(--radius-xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]"
            />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && filteredMeasurements.length === 0 && (
        <EmptyState
          title={isEn ? "No measurements recorded" : "Chưa có chỉ số nào"}
          description={
            isEn
              ? "Start tracking your blood pressure, glucose, or weight to build a longitudinal health record."
              : "Bấm '+ Ghi nhận chỉ số' để thêm lần đo đầu tiên của bạn hoặc kết nối thiết bị y tế."
          }
          icon="body"
        >
          <div className="mt-3">
            <Button variant="primary" onClick={() => setShowAddModal(true)} icon="plus">
              {isEn ? "Log First Measurement" : "Ghi nhận chỉ số ngay"}
            </Button>
          </div>
        </EmptyState>
      )}

      {/* Grid of measurement cards */}
      {!isLoading && filteredMeasurements.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3" data-testid="measurements-grid">
          {filteredMeasurements.map((m) => {
            const formattedDate = m.recorded_at
              ? formatLocaleDate(uiLanguage, m.recorded_at, {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })
              : "";

            return (
              <article
                key={m.id}
                className="flex flex-col justify-between rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5 shadow-xs transition hover:border-[color:var(--brand-500)]"
                data-testid={`measurement-card-${m.id}`}
              >
                <div>
                  <div className="flex items-center justify-between gap-2 border-b border-[color:var(--shell-border)]/50 pb-2.5">
                    <span className="font-bold text-xs uppercase tracking-wider text-[var(--text-secondary)]">
                      {m.label || m.type}
                    </span>
                    {m.status && (
                      <Badge
                        tone={
                          m.status === "critical"
                            ? "danger"
                            : m.status === "high" || m.status === "low"
                              ? "warn"
                              : "ok"
                        }
                      >
                        {m.status}
                      </Badge>
                    )}
                  </div>

                  <div className="my-3">
                    <div className="text-2xl font-black text-[var(--text-primary)]">
                      {m.value}{" "}
                      <span className="text-sm font-normal text-[var(--text-secondary)]">
                        {m.unit}
                      </span>
                    </div>
                    {m.reference_range && (
                      <p className="text-[11px] text-[var(--text-muted)] mt-0.5">
                        {isEn ? "Normal: " : "Bình thường: "}{m.reference_range}
                      </p>
                    )}
                    {m.notes && (
                      <p className="text-xs text-[var(--text-secondary)] mt-1 italic">
                        &ldquo;{m.notes}&rdquo;
                      </p>
                    )}
                  </div>
                </div>

                <div className="flex items-center justify-between border-t border-[color:var(--shell-border)]/40 pt-2.5 text-xs text-[var(--text-muted)]">
                  {m.source_kind && (
                    <SourceBadge sourceKind={m.source_kind} locale={uiLanguage} />
                  )}
                  {formattedDate && <time dateTime={m.recorded_at}>{formattedDate}</time>}
                </div>
              </article>
            );
          })}
        </div>
      )}

      {/* Measurement Editor Modal */}
      {showAddModal && (
        <MeasurementEditorModal
          open={showAddModal}
          onClose={() => setShowAddModal(false)}
          defaultType={selectedTypeFilter !== "all" ? selectedTypeFilter : "blood_pressure"}
          onSuccess={() => void refetch()}
          locale={uiLanguage}
        />
      )}
    </div>
  );
}

export default function MeasurementsPage() {
  return <MeasurementsPageContent />;
}
