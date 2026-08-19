"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { HealthPageHeader } from "@/components/consumer/health-page-header";
import { HealthStateBadge } from "@/components/health/health-state-badge";
import { SourceBadge } from "@/components/health/source-badge";
import { DemographicsEditorModal } from "@/components/health/demographics-editor-modal";
import { AllergyEditorModal } from "@/components/health/allergy-editor-modal";
import { ConditionEditorModal } from "@/components/health/condition-editor-modal";
import { MeasurementEditorModal } from "@/components/health/measurement-editor-modal";
import { ConflictResolverModal } from "@/components/health/conflict-resolver-modal";
import { UniversalCaptureModal } from "@/components/capture/universal-capture-modal";
import { InlineError } from "@/components/shared/inline-error";
import { EmptyState } from "@/components/shared/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { useUILanguage } from "@/lib/use-ui-language";
import { getActiveProfileId } from "@/lib/profile-context";
import { useQuery } from "@/lib/query/use-query";
import { queryKeys } from "@/lib/query/query-keys";
import {
  v2Client,
  type HealthAllergyDto,
  type HealthConditionDto,
  type HealthConflictDto,
  type HealthSummaryDto,
} from "@/lib/api/v2-client";

export interface HealthOverviewProps {
  initialProfileId?: string | null;
  initialData?: HealthSummaryDto;
  className?: string;
}

export function HealthOverviewSkeleton() {
  return (
    <div
      className="space-y-6 animate-pulse"
      aria-busy="true"
      aria-label="Đang tải tổng quan sức khỏe"
      data-testid="health-overview-skeleton"
    >
      <div className="flex flex-col gap-3 pb-4 border-b border-[color:var(--shell-border)]/60 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-2">
          <div className="h-7 w-48 rounded-[var(--radius-md)] bg-[var(--surface-muted)]" />
          <div className="h-4 w-72 rounded-[var(--radius-md)] bg-[var(--surface-muted)]" />
        </div>
        <div className="h-9 w-32 rounded-[var(--radius-lg)] bg-[var(--surface-muted)]" />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {[1, 2, 3, 4, 5].map((i) => (
          <div
            key={i}
            className="h-20 rounded-[var(--radius-xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]"
          />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="space-y-6 lg:col-span-8">
          <div className="h-48 rounded-[var(--radius-xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]" />
          <div className="h-48 rounded-[var(--radius-xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]" />
        </div>
        <div className="space-y-6 lg:col-span-4">
          <div className="h-36 rounded-[var(--radius-xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]" />
          <div className="h-48 rounded-[var(--radius-xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]" />
        </div>
      </div>
    </div>
  );
}

export function HealthOverview({
  initialProfileId,
  initialData,
  className = "",
}: HealthOverviewProps) {
  const uiLanguage = useUILanguage();
  const isEn = uiLanguage === "en";

  const [activeProfileId, setActiveProfileId] = useState<string | null>(
    initialProfileId ?? getActiveProfileId(),
  );

  // Modals state
  const [showDemographicsModal, setShowDemographicsModal] = useState(false);
  const [showAllergyModal, setShowAllergyModal] = useState(false);
  const [selectedAllergy, setSelectedAllergy] = useState<HealthAllergyDto | null>(null);

  const [showConditionModal, setShowConditionModal] = useState(false);
  const [selectedCondition, setSelectedCondition] = useState<HealthConditionDto | null>(null);

  const [showMeasurementModal, setShowMeasurementModal] = useState(false);
  const [showCaptureModal, setShowCaptureModal] = useState(false);

  // Active conflict resolution
  const [activeConflict, setActiveConflict] = useState<HealthConflictDto | null>(null);

  useEffect(() => {
    const handleContextChange = () => {
      setActiveProfileId(getActiveProfileId());
    };
    window.addEventListener("clara:profile-context-changed", handleContextChange);
    return () => {
      window.removeEventListener("clara:profile-context-changed", handleContextChange);
    };
  }, []);

  const queryKey = queryKeys.profile(activeProfileId).health.summary();

  const { data, isLoading, isError, error, refetch } = useQuery<HealthSummaryDto>({
    queryKey,
    queryFn: () => v2Client.getHealthSummary(activeProfileId),
    initialData,
  });

  const activeProfileName =
    data?.profile?.display_name || (isEn ? "You" : "Bạn");

  const allergies = data?.current?.allergies ?? [];
  const conditions = data?.current?.conditions ?? [];
  const medications = data?.current?.medications ?? [];
  const measurements = data?.current?.important_measurements ?? [];
  const recentResults = data?.recent_results ?? [];
  const conflicts = data?.conflicts ?? [];
  const demographics = data?.demographics;

  return (
    <div
      className={`health-overview-container mx-auto max-w-5xl space-y-6 pb-12 ${className}`}
      data-testid="health-overview"
    >
      {/* 1. Header */}
      <HealthPageHeader
        title={isEn ? "Health Record Overview" : "Hồ sơ sức khỏe tổng quan"}
        subtitle={
          isEn
            ? "Unified health profile, active conditions, allergies, medications, and vital metrics."
            : "Hồ sơ y tế hợp nhất: dị ứng, bệnh nền, đơn thuốc đang dùng và các chỉ số sinh hiệu."
        }
        activeProfile={{
          id: data?.profile?.id ?? activeProfileId ?? undefined,
          name: activeProfileName,
          relationship: data?.profile?.relationship ?? undefined,
        }}
        locale={uiLanguage}
        primaryAction={{
          label: isEn ? "+ Record Metric" : "+ Ghi nhận chỉ số",
          onClick: () => setShowMeasurementModal(true),
          icon: "scan",
        }}
        secondaryAction={{
          label: isEn ? "Add health info" : "Thêm thông tin sức khỏe",
          onClick: () => setShowCaptureModal(true),
          icon: "camera",
        }}
      />

      {/* 2. Sub-Navigation Hub Cards */}
      <nav
        aria-label={isEn ? "Health Sub-sections" : "Các phân hệ sức khỏe"}
        className="grid grid-cols-2 sm:grid-cols-5 gap-3"
      >
        <Link
          href="/health/timeline"
          className="group flex flex-col items-center justify-center p-3 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] hover:border-[color:var(--brand-500)] transition text-center shadow-xs"
          data-testid="subnav-timeline"
        >
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-[var(--radius-lg)] bg-[var(--surface-muted)] text-[var(--text-brand)] group-hover:scale-105 transition-transform">
            <Icon name="progress" size="1.2rem" />
          </span>
          <span className="mt-2 text-xs font-bold text-[var(--text-primary)]">
            {isEn ? "Timeline" : "Dòng thời gian"}
          </span>
          <span className="text-[10px] text-[var(--text-muted)]">
            {isEn ? "Longitudinal events" : "Nhật ký & Lịch sử"}
          </span>
        </Link>

        <Link
          href="/health/medications"
          className="group flex flex-col items-center justify-center p-3 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] hover:border-[color:var(--brand-500)] transition text-center shadow-xs"
          data-testid="subnav-medications"
        >
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-[var(--radius-lg)] bg-[var(--surface-muted)] text-[var(--text-brand)] group-hover:scale-105 transition-transform">
            <Icon name="medication" size="1.2rem" />
          </span>
          <span className="mt-2 text-xs font-bold text-[var(--text-primary)]">
            {isEn ? "Medications" : "Thuốc & Tủ thuốc"}
          </span>
          <span className="text-[10px] text-[var(--text-muted)]">
            {isEn ? `${medications.length} active` : `${medications.length} đang dùng`}
          </span>
        </Link>

        <Link
          href="/health/results"
          className="group flex flex-col items-center justify-center p-3 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] hover:border-[color:var(--brand-500)] transition text-center shadow-xs"
          data-testid="subnav-results"
        >
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-[var(--radius-lg)] bg-[var(--surface-muted)] text-[var(--text-brand)] group-hover:scale-105 transition-transform">
            <Icon name="scan" size="1.2rem" />
          </span>
          <span className="mt-2 text-xs font-bold text-[var(--text-primary)]">
            {isEn ? "Lab Results" : "Kết quả xét nghiệm"}
          </span>
          <span className="text-[10px] text-[var(--text-muted)]">
            {isEn ? `${recentResults.length} records` : `${recentResults.length} kết quả`}
          </span>
        </Link>

        <Link
          href="/health/measurements"
          className="group flex flex-col items-center justify-center p-3 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] hover:border-[color:var(--brand-500)] transition text-center shadow-xs"
          data-testid="subnav-measurements"
        >
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-[var(--radius-lg)] bg-[var(--surface-muted)] text-[var(--text-brand)] group-hover:scale-105 transition-transform">
            <Icon name="body" size="1.2rem" />
          </span>
          <span className="mt-2 text-xs font-bold text-[var(--text-primary)]">
            {isEn ? "Measurements" : "Chỉ số & Sinh hiệu"}
          </span>
          <span className="text-[10px] text-[var(--text-muted)]">
            {isEn ? `${measurements.length} logged` : `${measurements.length} chỉ số`}
          </span>
        </Link>

        <Link
          href="/health/documents"
          className="col-span-2 sm:col-span-1 group flex flex-col items-center justify-center p-3 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] hover:border-[color:var(--brand-500)] transition text-center shadow-xs"
          data-testid="subnav-documents"
        >
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-[var(--radius-lg)] bg-[var(--surface-muted)] text-[var(--text-brand)] group-hover:scale-105 transition-transform">
            <Icon name="folder" size="1.2rem" />
          </span>
          <span className="mt-2 text-xs font-bold text-[var(--text-primary)]">
            {isEn ? "Documents" : "Tài liệu & Hồ sơ"}
          </span>
          <span className="text-[10px] text-[var(--text-muted)]">
            {isEn ? "Extracted library" : "Thư viện hồ sơ"}
          </span>
        </Link>
      </nav>

      {/* 3. Loading Skeleton */}
      {isLoading && !data && <HealthOverviewSkeleton />}

      {/* 4. Error State */}
      {isError && !data && (
        <section data-testid="health-overview-error">
          <InlineError
            severity="error"
            title={isEn ? "Failed to load health summary" : "Không thể tải hồ sơ sức khỏe"}
            message={
              error instanceof Error
                ? error.message
                : isEn
                  ? "An error occurred while loading health data."
                  : "Đã xảy ra sự cố khi tải dữ liệu hồ sơ sức khỏe. Vui lòng thử lại."
            }
            onRetry={() => void refetch()}
            retryLabel={isEn ? "Retry" : "Thử lại"}
          />
        </section>
      )}

      {/* 5. Main Content */}
      {data && (
        <div className="space-y-6">
          {/* Conflict Review Banners (HEALTH-009) */}
          {conflicts.length > 0 && (
            <section className="space-y-3" data-testid="health-conflicts-banner">
              {conflicts.map((conflict) => (
                <div
                  key={conflict.id}
                  role="alert"
                  className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-[var(--radius-lg)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] p-4 text-sm text-[var(--status-warn-text)] shadow-sm"
                  data-testid={`conflict-item-${conflict.id}`}
                >
                  <div className="flex items-start gap-3">
                    <Icon name="warning" size="1.3rem" className="mt-0.5 shrink-0" />
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold">{conflict.title}</span>
                        <Badge tone="warn">{isEn ? "Discrepancy" : "Có mâu thuẫn"}</Badge>
                      </div>
                      <p className="mt-1 text-xs opacity-90 leading-relaxed">
                        {conflict.description}
                      </p>
                      <div className="mt-2 flex flex-wrap gap-3 text-xs opacity-80">
                        <span>• {conflict.source_a.label}: <strong>{conflict.source_a.value}</strong></span>
                        <span>• {conflict.source_b.label}: <strong>{conflict.source_b.value}</strong></span>
                      </div>
                    </div>
                  </div>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setActiveConflict(conflict)}
                    icon="clinical-notes"
                    className="self-end sm:self-center shrink-0"
                  >
                    {isEn ? "Review & Resolve" : "Xem & Đối chiếu"}
                  </Button>
                </div>
              ))}
            </section>
          )}

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            {/* Left Column: Allergies, Conditions, Medications */}
            <div className="space-y-6 lg:col-span-8">
              {/* Allergies Section */}
              <section
                className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5"
                data-testid="health-allergies-section"
              >
                <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-3">
                  <div className="flex items-center gap-2">
                    <Icon name="warning" size="1.2rem" className="text-[var(--danger-500)]" />
                    <h2 className="text-base font-semibold text-[var(--text-primary)]">
                      {isEn ? "Allergies & Adverse Reactions" : "Dị ứng & Phản ứng có hại"}
                    </h2>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon="plus"
                    onClick={() => {
                      setSelectedAllergy(null);
                      setShowAllergyModal(true);
                    }}
                  >
                    {isEn ? "Add Allergy" : "Thêm dị ứng"}
                  </Button>
                </div>

                {allergies.length === 0 ? (
                  <p className="mt-4 text-xs sm:text-sm text-[var(--text-muted)]">
                    {isEn
                      ? "No recorded allergies. Add known drug or food allergies for safety alerts."
                      : "Chưa ghi nhận dị ứng nào. Hãy thêm nếu có để hệ thống bảo vệ an toàn khi dùng thuốc."}
                  </p>
                ) : (
                  <div className="mt-3 divide-y divide-[color:var(--shell-border)]/40">
                    {allergies.map((allergy) => (
                      <div
                        key={allergy.id}
                        className="group flex items-center justify-between gap-3 py-3"
                        data-testid={`allergy-row-${allergy.id}`}
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-semibold text-sm text-[var(--text-primary)]">
                              {allergy.substance}
                            </span>
                            {allergy.severity && (
                              <Badge
                                tone={
                                  allergy.severity === "severe"
                                    ? "danger"
                                    : allergy.severity === "moderate"
                                      ? "warn"
                                      : "neutral"
                                }
                              >
                                {allergy.severity}
                              </Badge>
                            )}
                            {allergy.verification_state && (
                              <HealthStateBadge state={allergy.verification_state as any} locale={uiLanguage} />
                            )}
                          </div>
                          {allergy.reaction && (
                            <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
                              {isEn ? "Reaction: " : "Biểu hiện: "}
                              {allergy.reaction}
                            </p>
                          )}
                        </div>

                        <Button
                          variant="ghost"
                          size="sm"
                          icon="clinical-notes"
                          onClick={() => {
                            setSelectedAllergy(allergy);
                            setShowAllergyModal(true);
                          }}
                          aria-label={isEn ? `Edit ${allergy.substance}` : `Sửa ${allergy.substance}`}
                        />
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* Conditions Section */}
              <section
                className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5"
                data-testid="health-conditions-section"
              >
                <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-3">
                  <div className="flex items-center gap-2">
                    <Icon name="clinical-notes" size="1.2rem" className="text-[var(--text-brand)]" />
                    <h2 className="text-base font-semibold text-[var(--text-primary)]">
                      {isEn ? "Active Diagnoses & Conditions" : "Bệnh nền & Tình trạng sức khỏe"}
                    </h2>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon="plus"
                    onClick={() => {
                      setSelectedCondition(null);
                      setShowConditionModal(true);
                    }}
                  >
                    {isEn ? "Add Condition" : "Thêm bệnh nền"}
                  </Button>
                </div>

                {conditions.length === 0 ? (
                  <p className="mt-4 text-xs sm:text-sm text-[var(--text-muted)]">
                    {isEn
                      ? "No active diagnoses recorded."
                      : "Chưa ghi nhận bệnh nền nào. Thêm các chẩn đoán để cá nhân hóa hỗ trợ y tế."}
                  </p>
                ) : (
                  <div className="mt-3 divide-y divide-[color:var(--shell-border)]/40">
                    {conditions.map((cond) => (
                      <div
                        key={cond.id}
                        className="group flex items-center justify-between gap-3 py-3"
                        data-testid={`condition-row-${cond.id}`}
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-semibold text-sm text-[var(--text-primary)]">
                              {cond.name}
                            </span>
                            <Badge
                              tone={
                                cond.clinical_status === "active"
                                  ? "ok"
                                  : cond.clinical_status === "resolved"
                                    ? "neutral"
                                    : "warn"
                              }
                            >
                              {cond.clinical_status}
                            </Badge>
                            {cond.verification_status && (
                              <HealthStateBadge state={cond.verification_status as any} locale={uiLanguage} />
                            )}
                          </div>
                          {cond.notes && (
                            <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
                              {cond.notes}
                            </p>
                          )}
                        </div>

                        <Button
                          variant="ghost"
                          size="sm"
                          icon="clinical-notes"
                          onClick={() => {
                            setSelectedCondition(cond);
                            setShowConditionModal(true);
                          }}
                          aria-label={isEn ? `Edit ${cond.name}` : `Sửa ${cond.name}`}
                        />
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* Medications Summary */}
              <section
                className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5"
                data-testid="health-medications-summary"
              >
                <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-3">
                  <div className="flex items-center gap-2">
                    <Icon name="medication" size="1.2rem" className="text-[var(--text-brand)]" />
                    <h2 className="text-base font-semibold text-[var(--text-primary)]">
                      {isEn ? "Current Medications" : "Thuốc đang sử dụng"}
                    </h2>
                  </div>
                  <Link
                    href="/health/medications"
                    className="text-xs font-semibold text-[var(--text-brand)] hover:underline flex items-center gap-1"
                  >
                    <span>{isEn ? "Open Hub" : "Quản lý tủ thuốc"}</span>
                    <Icon name="arrow-right" size="0.85rem" />
                  </Link>
                </div>

                {medications.length === 0 ? (
                  <p className="mt-4 text-xs sm:text-sm text-[var(--text-muted)]">
                    {isEn
                      ? "No active medication courses. Add or scan prescriptions in the Medication Hub."
                      : "Chưa có đơn thuốc đang hoạt động. Bạn có thể thêm hoặc quét toa tại Tủ thuốc."}
                  </p>
                ) : (
                  <div className="mt-3 divide-y divide-[color:var(--shell-border)]/40">
                    {medications.map((med) => (
                      <div
                        key={med.id}
                        className="flex items-center justify-between gap-3 py-3"
                        data-testid={`med-summary-row-${med.id}`}
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-semibold text-sm text-[var(--text-primary)]">
                              {med.name}
                            </span>
                            <Badge tone={med.status === "active" ? "ok" : "neutral"}>
                              {med.status}
                            </Badge>
                            {med.source_kind && (
                              <SourceBadge sourceKind={med.source_kind} locale={uiLanguage} />
                            )}
                          </div>
                          {(med.dosage || med.instructions) && (
                            <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
                              {med.dosage ? `${med.dosage} • ` : ""}
                              {med.instructions}
                            </p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </div>

            {/* Right Column: Demographics, Vitals, Recent Results */}
            <div className="space-y-6 lg:col-span-4">
              {/* Demographics Card */}
              <section
                className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5"
                data-testid="health-demographics-card"
              >
                <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-3">
                  <div className="flex items-center gap-2">
                    <Icon name="user-card" size="1.2rem" className="text-[var(--text-brand)]" />
                    <h2 className="text-base font-semibold text-[var(--text-primary)]">
                      {isEn ? "Demographics" : "Thông tin cá nhân"}
                    </h2>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon="clinical-notes"
                    onClick={() => setShowDemographicsModal(true)}
                  >
                    {isEn ? "Edit" : "Sửa"}
                  </Button>
                </div>

                <dl className="mt-3 space-y-2 text-xs sm:text-sm">
                  <div className="flex justify-between py-1 border-b border-[color:var(--shell-border)]/30">
                    <dt className="text-[var(--text-muted)]">{isEn ? "Full Name" : "Họ và tên"}</dt>
                    <dd className="font-semibold text-[var(--text-primary)]">
                      {demographics?.full_name || activeProfileName}
                    </dd>
                  </div>
                  <div className="flex justify-between py-1 border-b border-[color:var(--shell-border)]/30">
                    <dt className="text-[var(--text-muted)]">{isEn ? "Blood Type" : "Nhóm máu"}</dt>
                    <dd className="font-semibold text-[var(--text-primary)]">
                      {demographics?.blood_type || (isEn ? "Not specified" : "Chưa rõ")}
                    </dd>
                  </div>
                  <div className="flex justify-between py-1 border-b border-[color:var(--shell-border)]/30">
                    <dt className="text-[var(--text-muted)]">{isEn ? "Gender" : "Giới tính"}</dt>
                    <dd className="font-semibold text-[var(--text-primary)] capitalize">
                      {demographics?.gender || (isEn ? "Not specified" : "Chưa rõ")}
                    </dd>
                  </div>
                  {demographics?.emergency_contact?.name && (
                    <div className="py-1">
                      <dt className="text-[var(--text-muted)] text-[11px] uppercase">
                        {isEn ? "Emergency Contact" : "Liên hệ khẩn cấp"}
                      </dt>
                      <dd className="mt-0.5 font-semibold text-[var(--text-primary)]">
                        {demographics.emergency_contact.name}{" "}
                        {demographics.emergency_contact.relationship
                          ? `(${demographics.emergency_contact.relationship})`
                          : ""}
                        {demographics.emergency_contact.phone
                          ? ` • ${demographics.emergency_contact.phone}`
                          : ""}
                      </dd>
                    </div>
                  )}
                </dl>
              </section>

              {/* Vitals Summary */}
              <section
                className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5"
                data-testid="health-vitals-summary"
              >
                <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-3">
                  <div className="flex items-center gap-2">
                    <Icon name="body" size="1.2rem" className="text-[var(--text-brand)]" />
                    <h2 className="text-base font-semibold text-[var(--text-primary)]">
                      {isEn ? "Vital Signs" : "Chỉ số sinh hiệu"}
                    </h2>
                  </div>
                  <Link
                    href="/health/measurements"
                    className="text-xs font-semibold text-[var(--text-brand)] hover:underline flex items-center gap-1"
                  >
                    <span>{isEn ? "All" : "Tất cả"}</span>
                    <Icon name="arrow-right" size="0.85rem" />
                  </Link>
                </div>

                {measurements.length === 0 ? (
                  <p className="mt-4 text-xs text-[var(--text-muted)]">
                    {isEn ? "No recent vital readings." : "Chưa có chỉ số đo gần đây."}
                  </p>
                ) : (
                  <div className="mt-3 space-y-2.5">
                    {measurements.map((m) => (
                      <div
                        key={m.id}
                        className="flex items-center justify-between rounded-[var(--radius-lg)] border border-[color:var(--shell-border)]/60 bg-[var(--surface-muted)]/40 p-2.5"
                        data-testid={`vital-card-${m.type}`}
                      >
                        <div>
                          <span className="text-[11px] font-medium text-[var(--text-muted)] uppercase block">
                            {m.label || m.type}
                          </span>
                          <span className="text-sm font-bold text-[var(--text-primary)]">
                            {m.value} <span className="text-xs font-normal text-[var(--text-secondary)]">{m.unit}</span>
                          </span>
                        </div>
                        {m.status && (
                          <Badge tone={m.status === "critical" ? "danger" : m.status === "high" || m.status === "low" ? "warn" : "ok"}>
                            {m.status}
                          </Badge>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* Recent Results */}
              <section
                className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5"
                data-testid="health-recent-results-summary"
              >
                <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-3">
                  <div className="flex items-center gap-2">
                    <Icon name="scan" size="1.2rem" className="text-[var(--text-brand)]" />
                    <h2 className="text-base font-semibold text-[var(--text-primary)]">
                      {isEn ? "Recent Results" : "Xét nghiệm gần đây"}
                    </h2>
                  </div>
                  <Link
                    href="/health/results"
                    className="text-xs font-semibold text-[var(--text-brand)] hover:underline flex items-center gap-1"
                  >
                    <span>{isEn ? "Trends" : "Xem biểu đồ"}</span>
                    <Icon name="arrow-right" size="0.85rem" />
                  </Link>
                </div>

                {recentResults.length === 0 ? (
                  <p className="mt-4 text-xs text-[var(--text-muted)]">
                    {isEn ? "No recent test results." : "Chưa có kết quả xét nghiệm."}
                  </p>
                ) : (
                  <div className="mt-3 space-y-2">
                    {recentResults.map((r) => (
                      <div
                        key={r.id}
                        className="py-2 first:pt-1 border-b border-[color:var(--shell-border)]/30 last:border-0"
                        data-testid={`result-item-${r.id}`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-xs text-[var(--text-primary)]">
                            {r.test_name}
                          </span>
                          <span className="font-bold text-xs text-[var(--text-primary)]">
                            {r.value} {r.unit}
                          </span>
                        </div>
                        {r.reference_range && (
                          <div className="flex items-center justify-between text-[11px] text-[var(--text-muted)] mt-0.5">
                            <span>{isEn ? "Ref: " : "Tham chiếu: "}{r.reference_range}</span>
                            {r.flag && r.flag !== "normal" && (
                              <Badge tone="warn">{r.flag}</Badge>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </div>
          </div>
        </div>
      )}

      {/* Modals */}
      {showDemographicsModal && (
        <DemographicsEditorModal
          open={showDemographicsModal}
          onClose={() => setShowDemographicsModal(false)}
          initialData={demographics}
          onSuccess={() => void refetch()}
          locale={uiLanguage}
        />
      )}

      {showAllergyModal && (
        <AllergyEditorModal
          open={showAllergyModal}
          onClose={() => {
            setShowAllergyModal(false);
            setSelectedAllergy(null);
          }}
          allergy={selectedAllergy}
          onSuccess={() => void refetch()}
          locale={uiLanguage}
        />
      )}

      {showConditionModal && (
        <ConditionEditorModal
          open={showConditionModal}
          onClose={() => {
            setShowConditionModal(false);
            setSelectedCondition(null);
          }}
          condition={selectedCondition}
          onSuccess={() => void refetch()}
          locale={uiLanguage}
        />
      )}

      {showMeasurementModal && (
        <MeasurementEditorModal
          open={showMeasurementModal}
          onClose={() => setShowMeasurementModal(false)}
          onSuccess={() => void refetch()}
          locale={uiLanguage}
        />
      )}

      {showCaptureModal && (
        <UniversalCaptureModal
          open={showCaptureModal}
          onClose={() => setShowCaptureModal(false)}
          onCommitSuccess={() => void refetch()}
          locale={uiLanguage}
        />
      )}

      {activeConflict && (
        <ConflictResolverModal
          open={Boolean(activeConflict)}
          onClose={() => setActiveConflict(null)}
          resourceName={activeConflict.domain}
          title={activeConflict.title}
          clientDraft={{ [activeConflict.source_a.label]: activeConflict.source_a.value }}
          serverState={{ [activeConflict.source_b.label]: activeConflict.source_b.value }}
          changedFields={[activeConflict.source_a.label]}
          onKeepClient={() => setActiveConflict(null)}
          onAcceptServer={() => setActiveConflict(null)}
          locale={uiLanguage}
        />
      )}
    </div>
  );
}

export default HealthOverview;
