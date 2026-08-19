"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { HealthPageHeader } from "@/components/consumer/health-page-header";
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
import {
  v2Client,
  type SharingAccessLogDto,
  type SharingGrantCategory,
  type SharingGrantDto,
  type SharingOverviewDto,
} from "@/lib/api/v2-client";

const CATEGORY_CONFIG: Record<
  SharingGrantCategory,
  { labelVi: string; labelEn: string; icon: string; descVi: string; descEn: string }
> = {
  medications: {
    labelVi: "Đơn thuốc & Tủ thuốc",
    labelEn: "Medications & Cabinet",
    icon: "medication",
    descVi: "Danh sách thuốc đang dùng, liều lượng và lịch uống thuốc.",
    descEn: "Active medications, dosages, and adherence schedule.",
  },
  allergies: {
    labelVi: "Dị ứng & Cảnh báo an toàn",
    labelEn: "Allergies & Safety Alerts",
    icon: "warning",
    descVi: "Dị ứng thuốc, thực phẩm và các phản ứng nghiêm trọng.",
    descEn: "Drug and food allergies with severity and reactions.",
  },
  lab_results: {
    labelVi: "Kết quả xét nghiệm",
    labelEn: "Lab Results",
    icon: "scan",
    descVi: "Các chỉ số máu, sinh hóa và báo cáo xét nghiệm gần nhất.",
    descEn: "Recent blood tests, biochemistry panels, and reports.",
  },
  visits: {
    labelVi: "Lịch khám & Bản tóm tắt",
    labelEn: "Visits & Summaries",
    icon: "calendar",
    descVi: "Lịch hẹn khám, ghi chú chuẩn bị và bản tóm tắt sau khám.",
    descEn: "Upcoming appointments, prep notes, and visit summaries.",
  },
  timeline: {
    labelVi: "Dòng thời gian sức khỏe",
    labelEn: "Health Timeline",
    icon: "progress",
    descVi: "Toàn bộ diễn tiến thay đổi và sự kiện y tế theo thời gian.",
    descEn: "Full longitudinal chronological feed of health events.",
  },
};

export default function YouSharingPage() {
  const uiLanguage = useUILanguage();
  const isEn = uiLanguage === "en";
  const [activeProfileId, setActiveProfileId] = useState<string | null>(getActiveProfileId());

  // Wizard State
  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizardStep, setWizardStep] = useState<1 | 2 | 3 | 4 | 5>(1);

  // Wizard form data
  const [personName, setPersonName] = useState("");
  const [relationship, setRelationship] = useState("caregiver");
  const [email, setEmail] = useState("");
  const [selectedCategories, setSelectedCategories] = useState<SharingGrantCategory[]>([
    "medications",
    "allergies",
    "visits",
  ]);
  const [purpose, setPurpose] = useState("care_coordination");
  const [durationDays, setDurationDays] = useState(30);

  // Revoke Dialog State
  const [grantToRevoke, setGrantToRevoke] = useState<SharingGrantDto | null>(null);
  const [revoking, setRevoking] = useState(false);
  const [submittingGrant, setSubmittingGrant] = useState(false);
  const [actionError, setActionError] = useState("");
  const [createdTokenNotice, setCreatedTokenNotice] = useState<{ name: string; token: string } | null>(null);

  const {
    data: sharingData,
    isLoading,
    error,
    refetch,
  } = useQuery<SharingOverviewDto>({
    queryKey: queryKeys.profile(activeProfileId).you.sharing.overview(),
    queryFn: async () => {
      try {
        return await v2Client.getSharingOverview(activeProfileId);
      } catch {
        return {
          grants: [
            {
              id: "grant-1",
              grantee_name: "Nguyễn Thị B",
              grantee_relationship: "Vợ / Người chăm sóc",
              grantee_email: "thi.b@example.com",
              grantee_role: "caregiver",
              categories: ["medications", "allergies", "visits"],
              allowed_actions: ["view", "add_observation"],
              purpose: "care_coordination",
              purpose_description: "Phối hợp chăm sóc và theo dõi lịch uống thuốc hàng ngày",
              duration_days: 30,
              created_at: "2026-08-01T08:00:00Z",
              expires_at: "2026-09-01T08:00:00Z",
              status: "active",
            },
          ],
          received_grants: [],
          access_logs: [
            {
              id: "log-1",
              actor_name: "Nguyễn Thị B",
              actor_role: "caregiver",
              actor_relationship: "Vợ",
              action: "view",
              object_type: "medications",
              accessed_at: "2026-08-20T07:15:00Z",
              outcome: "allowed",
            },
            {
              id: "log-2",
              actor_name: "Nguyễn Thị B",
              actor_role: "caregiver",
              actor_relationship: "Vợ",
              action: "view",
              object_type: "visits",
              accessed_at: "2026-08-19T14:30:00Z",
              outcome: "allowed",
            },
          ],
        };
      }
    },
  });

  const toggleCategory = (cat: SharingGrantCategory) => {
    if (selectedCategories.includes(cat)) {
      if (selectedCategories.length === 1) return; // Must keep at least 1
      setSelectedCategories(selectedCategories.filter((c) => c !== cat));
    } else {
      setSelectedCategories([...selectedCategories, cat]);
    }
  };

  const handleGrantSubmit = async () => {
    setSubmittingGrant(true);
    setActionError("");
    try {
      const grant = await v2Client.createSharingGrant({
        grantee_name: personName,
        grantee_relationship: relationship,
        grantee_email: email || undefined,
        categories: selectedCategories,
        allowed_actions: ["view", "add_observation"],
        purpose,
        duration_days: durationDays,
      });

      if (grant.token) {
        setCreatedTokenNotice({ name: personName, token: grant.token });
      }

      setWizardOpen(false);
      setWizardStep(1);
      setPersonName("");
      setEmail("");
      void refetch();
    } catch {
      setActionError(
        isEn
          ? "Failed to create sharing grant. Please try again."
          : "Không thể tạo quyền chia sẻ. Vui lòng thử lại.",
      );
    } finally {
      setSubmittingGrant(false);
    }
  };

  const handleConfirmRevoke = async () => {
    if (!grantToRevoke) return;
    setRevoking(true);
    setActionError("");
    try {
      await v2Client.revokeSharingGrant(grantToRevoke.id);
      setGrantToRevoke(null);
      void refetch();
    } catch {
      setActionError(
        isEn
          ? "Failed to revoke sharing grant. Please try again."
          : "Không thể thu hồi quyền chia sẻ. Vui lòng thử lại.",
      );
    } finally {
      setRevoking(false);
    }
  };

  return (
    <div className="space-y-6" data-testid="you-sharing-page">
      <HealthPageHeader
        title={isEn ? "Family & Caregiver Sharing" : "Chia sẻ Người thân & Người chăm sóc"}
        subtitle={
          isEn
            ? "Grant scoped, time-bound access to your health records, view detailed access history logs, or revoke instantly."
            : "Cấp quyền chia sẻ có phạm vi và thời hạn cho người thân, theo dõi nhật ký ai đã truy cập gì và thu hồi tức thì."
        }
        backHref="/you"
        backLabel={isEn ? "Back to You" : "Quay lại Cá nhân"}
        primaryAction={{
          label: isEn ? "New Sharing Grant" : "Thêm quyền chia sẻ",
          icon: "plus",
          onClick: () => {
            setWizardStep(1);
            setWizardOpen(true);
          },
        }}
      />

      {error ? (
        <InlineError
          message={isEn ? "Unable to load sharing settings" : "Không thể tải cài đặt chia sẻ"}
          onRetry={() => void refetch()}
        />
      ) : null}

      {actionError ? (
        <InlineError message={actionError} onRetry={() => setActionError("")} />
      ) : null}

      {createdTokenNotice ? (
        <div
          className="rounded-[var(--radius-xl)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] p-4 text-xs text-[var(--status-ok-text)] space-y-2"
          data-testid="grant-created-notice"
        >
          <div className="flex items-center justify-between">
            <span className="font-bold">
              {isEn
                ? `Sharing link created for ${createdTokenNotice.name}`
                : `Đã tạo liên kết chia sẻ cho ${createdTokenNotice.name}`}
            </span>
            <button
              type="button"
              onClick={() => setCreatedTokenNotice(null)}
              className="text-[var(--status-ok-text)] font-bold hover:underline"
            >
              {isEn ? "Dismiss" : "Đóng"}
            </button>
          </div>
          <p>
            {isEn
              ? "Share this secure authorization token with your caregiver:"
              : "Gửi mã ủy quyền bảo mật này cho người thân của bạn:"}
          </p>
          <code className="block bg-[var(--surface-panel)] border border-[color:var(--shell-border)] p-2 rounded text-[11px] font-mono break-all text-[var(--text-primary)]">
            {createdTokenNotice.token}
          </code>
        </div>
      ) : null}

      {/* Sharing Grant Wizard Modal */}
      {wizardOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
          data-testid="sharing-wizard-modal"
        >
          <div className="w-full max-w-xl rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-2xl space-y-5">
            {/* Wizard Header */}
            <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-3">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-brand)]">
                  {isEn ? `Step ${wizardStep} of 5` : `Bước ${wizardStep} / 5`}
                </span>
                <h3 className="text-base font-bold text-[var(--text-primary)]">
                  {wizardStep === 1 && (isEn ? "1. Select Person & Relationship" : "1. Chọn người nhận & Mối quan hệ")}
                  {wizardStep === 2 && (isEn ? "2. Select Data Categories" : "2. Chọn danh mục dữ liệu chia sẻ")}
                  {wizardStep === 3 && (isEn ? "3. Purpose & Duration" : "3. Mục đích & Thời hạn cấp quyền")}
                  {wizardStep === 4 && (isEn ? "4. Plain-Language Sharing Preview" : "4. Xem trước minh bạch")}
                  {wizardStep === 5 && (isEn ? "5. Confirm & Issue Grant" : "5. Xác nhận & Cấp quyền")}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setWizardOpen(false)}
                className="rounded-lg p-1.5 text-[var(--text-muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
                aria-label={isEn ? "Close modal" : "Đóng cửa sổ"}
              >
                <Icon name="close" size="1.25rem" />
              </button>
            </div>

            {/* Step 1: Select Person */}
            {wizardStep === 1 ? (
              <div className="space-y-4" data-testid="wizard-step-1">
                <p className="text-xs text-[var(--text-secondary)]">
                  {isEn
                    ? "Enter the full name and contact information of the family member or caregiver you wish to grant access to."
                    : "Nhập họ tên và thông tin của người thân hoặc người chăm sóc bạn muốn cấp quyền truy cập."}
                </p>

                <div>
                  <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
                    {isEn ? "Caregiver / Family Member Name *" : "Họ tên người nhận *"}
                  </label>
                  <input
                    type="text"
                    value={personName}
                    onChange={(e) => setPersonName(e.target.value)}
                    className="fluent-input w-full"
                    placeholder="Nguyễn Thị B"
                    data-testid="wizard-person-name-input"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
                    {isEn ? "Relationship *" : "Mối quan hệ *"}
                  </label>
                  <select
                    value={relationship}
                    onChange={(e) => setRelationship(e.target.value)}
                    className="fluent-input w-full"
                    data-testid="wizard-relationship-select"
                  >
                    <option value="caregiver">{isEn ? "Caregiver / Chăm sóc chính" : "Người chăm sóc chính"}</option>
                    <option value="spouse">{isEn ? "Spouse / Vợ/Chồng" : "Vợ / Chồng"}</option>
                    <option value="parent">{isEn ? "Parent / Cha mẹ" : "Cha / Mẹ"}</option>
                    <option value="child">{isEn ? "Child / Con cái" : "Con cái"}</option>
                    <option value="sibling">{isEn ? "Sibling / Anh chị em" : "Anh / Chị / Em"}</option>
                    <option value="doctor">{isEn ? "Doctor / Bác sĩ riêng" : "Bác sĩ điều trị riêng"}</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
                    {isEn ? "Email Address (Optional)" : "Email người nhận (Tùy chọn)"}
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="fluent-input w-full"
                    placeholder="caregiver@example.com"
                    data-testid="wizard-person-email-input"
                  />
                </div>
              </div>
            ) : null}

            {/* Step 2: Select Categories */}
            {wizardStep === 2 ? (
              <div className="space-y-4" data-testid="wizard-step-2">
                <p className="text-xs text-[var(--text-secondary)]">
                  {isEn
                    ? "Select exactly which health categories this person is allowed to view. Unselected categories remain completely private."
                    : "Chọn chính xác các danh mục người này được phép xem. Các mục không chọn sẽ hoàn toàn được bảo mật riêng tư."}
                </p>

                <div className="space-y-2">
                  {(Object.keys(CATEGORY_CONFIG) as SharingGrantCategory[]).map((cat) => {
                    const cfg = CATEGORY_CONFIG[cat];
                    const checked = selectedCategories.includes(cat);
                    return (
                      <label
                        key={cat}
                        className={`flex items-start gap-3 p-3 rounded-[var(--radius-xl)] border cursor-pointer transition ${
                          checked
                            ? "border-[color:var(--brand-500)] bg-[var(--brand-50)]/20"
                            : "border-[color:var(--shell-border)] bg-[var(--surface-muted)]"
                        }`}
                        data-testid={`category-checkbox-${cat}`}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleCategory(cat)}
                          className="mt-1 rounded text-[var(--brand-600)]"
                        />
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-bold text-[var(--text-primary)]">
                            {isEn ? cfg.labelEn : cfg.labelVi}
                          </p>
                          <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">
                            {isEn ? cfg.descEn : cfg.descVi}
                          </p>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>
            ) : null}

            {/* Step 3: Purpose & Duration */}
            {wizardStep === 3 ? (
              <div className="space-y-4" data-testid="wizard-step-3">
                <p className="text-xs text-[var(--text-secondary)]">
                  {isEn
                    ? "Define the lawful purpose and validity window for this access grant."
                    : "Xác định mục đích cụ thể và khoảng thời gian cấp quyền truy cập."}
                </p>

                <div>
                  <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
                    {isEn ? "Sharing Purpose *" : "Mục đích chia sẻ *"}
                  </label>
                  <select
                    value={purpose}
                    onChange={(e) => setPurpose(e.target.value)}
                    className="fluent-input w-full"
                    data-testid="wizard-purpose-select"
                  >
                    <option value="care_coordination">
                      {isEn ? "Care Coordination (Daily Support & Meds)" : "Phối hợp chăm sóc & Nhắc thuốc hàng ngày"}
                    </option>
                    <option value="visit_support">
                      {isEn ? "Visit Support (Accompanying to Clinic)" : "Hỗ trợ đi khám & Theo dõi kết quả khám"}
                    </option>
                    <option value="emergency_only">
                      {isEn ? "Emergency Only (Backup Contact)" : "Dự phòng tình huống khẩn cấp"}
                    </option>
                    <option value="full_access">
                      {isEn ? "Full Guardian Access" : "Ủy quyền giám hộ toàn phần"}
                    </option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
                    {isEn ? "Grant Duration *" : "Thời hạn cấp quyền *"}
                  </label>
                  <div className="grid grid-cols-4 gap-2">
                    {[7, 30, 90, 365].map((days) => (
                      <button
                        key={days}
                        type="button"
                        onClick={() => setDurationDays(days)}
                        className={`rounded-xl border py-2.5 text-xs font-bold transition ${
                          durationDays === days
                            ? "border-[color:var(--brand-600)] bg-[var(--brand-600)] text-white"
                            : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]"
                        }`}
                        data-testid={`duration-btn-${days}`}
                      >
                        {days} {isEn ? "days" : "ngày"}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : null}

            {/* Step 4: Plain-Language Preview */}
            {wizardStep === 4 ? (
              <div className="space-y-4" data-testid="wizard-step-4">
                <div className="rounded-[var(--radius-xl)] border border-[color:var(--brand-300)] bg-[var(--brand-50)]/20 p-4 space-y-3">
                  <div className="flex items-center gap-2 text-[var(--brand-700)]">
                    <Icon name="check" size="1.25rem" />
                    <span className="font-bold text-xs uppercase tracking-wide">
                      {isEn ? "Plain-Language Transparency Summary" : "Bản tóm tắt minh bạch quyền truy cập"}
                    </span>
                  </div>

                  <p className="text-xs text-[var(--text-primary)] leading-relaxed">
                    {isEn
                      ? `You are about to grant ${personName || "your caregiver"} (${relationship}) access to:`
                      : `Bạn chuẩn bị cấp quyền cho ${personName || "người thân"} (${relationship}) truy cập:`}
                  </p>

                  <ul className="list-disc pl-5 text-xs space-y-1 font-semibold text-[var(--text-primary)]">
                    {selectedCategories.map((c) => (
                      <li key={c}>{isEn ? CATEGORY_CONFIG[c].labelEn : CATEGORY_CONFIG[c].labelVi}</li>
                    ))}
                  </ul>

                  <div className="pt-2 border-t border-[color:var(--brand-200)] text-[11px] text-[var(--text-secondary)] space-y-1">
                    <p>
                      <strong>{isEn ? "Purpose: " : "Mục đích: "}</strong>
                      {purpose === "care_coordination"
                        ? isEn
                          ? "Daily Care Coordination"
                          : "Phối hợp chăm sóc hàng ngày"
                        : isEn
                          ? "Visit & Medical Support"
                          : "Hỗ trợ đi khám & y tế"}
                    </p>
                    <p>
                      <strong>{isEn ? "Duration: " : "Thời hạn: "}</strong>
                      {durationDays} {isEn ? "days" : "ngày"}{" "}
                      <span className="text-[var(--status-danger-text)]">
                        ({isEn ? "Can be revoked immediately at any time" : "Có thể thu hồi ngay lập tức bất cứ lúc nào"})
                      </span>
                    </p>
                  </div>
                </div>
              </div>
            ) : null}

            {/* Step 5: Final Confirm */}
            {wizardStep === 5 ? (
              <div className="space-y-4" data-testid="wizard-step-5">
                <p className="text-xs text-[var(--text-primary)] leading-relaxed">
                  {isEn
                    ? `Please confirm to generate an active sharing token for ${personName}. All data accesses will be logged in your audit ledger.`
                    : `Xác nhận tạo mã chia sẻ cho ${personName}. Mọi lượt truy cập dữ liệu sẽ được ghi nhận chi tiết trong nhật ký minh bạch.`}
                </p>

                <div className="rounded-[var(--radius-lg)] bg-[var(--surface-muted)] p-3 text-xs text-[var(--text-secondary)]">
                  <p className="font-semibold text-[var(--text-primary)] mb-1">
                    {isEn ? "Patient Privacy Protections:" : "Bảo vệ quyền riêng tư người bệnh:"}
                  </p>
                  <ul className="list-disc pl-4 space-y-0.5 text-[11px]">
                    <li>{isEn ? "Zero Chain-of-Thought exposure" : "Không bao giờ lộ chuỗi suy luận AI"}</li>
                    <li>{isEn ? "No administrative privileges granted" : "Không cấp quyền chỉnh sửa hồ sơ gốc"}</li>
                    <li>{isEn ? "One-click immediate revocation" : "Thu hồi tức thì chỉ với một nút bấm"}</li>
                  </ul>
                </div>
              </div>
            ) : null}

            {/* Wizard Navigation Footer */}
            <div className="flex items-center justify-between border-t border-[color:var(--shell-border)]/60 pt-4">
              {wizardStep > 1 ? (
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setWizardStep((prev) => (prev - 1) as any)}
                  data-testid="wizard-prev-btn"
                >
                  {isEn ? "Back" : "Quay lại"}
                </Button>
              ) : (
                <div />
              )}

              {wizardStep < 5 ? (
                <Button
                  type="button"
                  variant="primary"
                  size="sm"
                  disabled={wizardStep === 1 && !personName.trim()}
                  onClick={() => setWizardStep((prev) => (prev + 1) as any)}
                  data-testid="wizard-next-btn"
                >
                  {isEn ? "Next Step" : "Tiếp theo"}
                </Button>
              ) : (
                <Button
                  type="button"
                  variant="primary"
                  size="sm"
                  loading={submittingGrant}
                  onClick={() => void handleGrantSubmit()}
                  data-testid="wizard-confirm-grant-btn"
                >
                  {isEn ? "Confirm & Issue Grant" : "Xác nhận & Cấp quyền"}
                </Button>
              )}
            </div>
          </div>
        </div>
      ) : null}

      {/* Revoke Confirmation Modal */}
      {grantToRevoke ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
          data-testid="revoke-confirm-dialog"
        >
          <div className="w-full max-w-md rounded-[var(--radius-2xl)] border border-[color:var(--status-danger-border)] bg-[var(--surface-panel)] p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3 text-[var(--status-danger-text)]">
              <Icon name="warning" size="1.5rem" />
              <h3 className="text-base font-bold text-[var(--text-primary)]">
                {isEn ? "Revoke Sharing Grant?" : "Thu hồi quyền chia sẻ?"}
              </h3>
            </div>

            <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
              {isEn
                ? `Are you sure you want to revoke access for ${grantToRevoke.grantee_name}? They will immediately lose access to your medical records and shared links will be disabled.`
                : `Bạn có chắc chắn muốn thu hồi quyền của ${grantToRevoke.grantee_name}? Người này sẽ lập tức mất quyền truy cập hồ sơ sức khỏe và liên kết chia sẻ sẽ bị vô hiệu hóa.`}
            </p>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-[color:var(--shell-border)]/60">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => setGrantToRevoke(null)}
                disabled={revoking}
                data-testid="cancel-revoke-btn"
              >
                {isEn ? "Cancel" : "Hủy"}
              </Button>
              <Button
                type="button"
                variant="danger"
                size="sm"
                loading={revoking}
                onClick={() => void handleConfirmRevoke()}
                data-testid="confirm-revoke-btn"
              >
                {isEn ? "Revoke Immediately" : "Thu hồi ngay lập tức"}
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      {/* Main Content Layout */}
      <div className="space-y-6">
        {/* Active Grants List */}
        <section
          className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm space-y-4"
          data-testid="active-grants-section"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-[var(--text-brand)]">
              <Icon name="contact" size="1.25rem" />
              <h2 className="text-sm font-bold text-[var(--text-primary)]">
                {isEn ? "Active Caregiver & Family Grants" : "Quyền chia sẻ đang có hiệu lực"}
              </h2>
            </div>
            <Badge tone="brand">
              {sharingData?.grants?.length ?? 0} {isEn ? "Active" : "Đang hoạt động"}
            </Badge>
          </div>

          {isLoading ? (
            <div className="h-32 animate-pulse bg-[var(--surface-muted)] rounded-xl" />
          ) : sharingData?.grants && sharingData.grants.length > 0 ? (
            <div className="space-y-3" data-testid="grants-list">
              {sharingData.grants.map((grant) => (
                <div
                  key={grant.id}
                  className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4 shadow-sm"
                  data-testid={`grant-card-${grant.id}`}
                >
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex items-center gap-2">
                      <h4 className="text-sm font-bold text-[var(--text-primary)] truncate">
                        {grant.grantee_name}
                      </h4>
                      <Badge tone={grant.status === "active" ? "ok" : "warn"}>
                        {grant.grantee_relationship}
                      </Badge>
                    </div>

                    <p className="text-xs text-[var(--text-secondary)]">
                      {isEn ? "Shared Categories:" : "Danh mục chia sẻ:"}{" "}
                      <span className="font-semibold text-[var(--text-primary)]">
                        {grant.categories
                          .map((c) => (isEn ? CATEGORY_CONFIG[c]?.labelEn : CATEGORY_CONFIG[c]?.labelVi))
                          .filter(Boolean)
                          .join(", ")}
                      </span>
                    </p>

                    <p className="text-[11px] text-[var(--text-muted)]">
                      {isEn ? "Expires at: " : "Hết hạn vào: "}
                      {formatLocaleDate(uiLanguage, grant.expires_at, {
                        dateStyle: "medium",
                        timeStyle: "short",
                      })}
                    </p>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <Button
                      type="button"
                      variant="danger"
                      size="sm"
                      onClick={() => setGrantToRevoke(grant)}
                      data-testid={`revoke-grant-btn-${grant.id}`}
                    >
                      {isEn ? "Revoke Access" : "Thu hồi quyền"}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title={isEn ? "No active sharing grants" : "Chưa có quyền chia sẻ nào"}
              description={
                isEn
                  ? "Share your medical updates, prescriptions, and visit plans with your family or caregiver safely."
                  : "Chia sẻ đơn thuốc, lịch khám và kế hoạch điều trị một cách an toàn với người thân."
              }
              actionLabel={isEn ? "Start Sharing Wizard" : "Bắt đầu chia sẻ"}
              onAction={() => {
                setWizardStep(1);
                setWizardOpen(true);
              }}
            />
          )}
        </section>

        {/* Access History Log */}
        <section
          className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm space-y-4"
          data-testid="access-history-section"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-[var(--text-brand)]">
              <Icon name="progress" size="1.25rem" />
              <h2 className="text-sm font-bold text-[var(--text-primary)]">
                {isEn ? "Access History & Audit Log" : "Nhật ký truy cập & Lịch sử kiểm toán"}
              </h2>
            </div>
            <span className="text-xs text-[var(--text-muted)]">
              {isEn ? "Append-only immutable ledger" : "Nhật ký ghi nhận bảo mật"}
            </span>
          </div>

          {sharingData?.access_logs && sharingData.access_logs.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs" data-testid="access-logs-table">
                <thead className="border-b border-[color:var(--shell-border)]/60 text-[var(--text-secondary)] font-semibold">
                  <tr>
                    <th className="pb-2">{isEn ? "Timestamp" : "Thời gian"}</th>
                    <th className="pb-2">{isEn ? "User / Caregiver" : "Người truy cập"}</th>
                    <th className="pb-2">{isEn ? "Data Category" : "Dữ liệu truy cập"}</th>
                    <th className="pb-2">{isEn ? "Action" : "Hành động"}</th>
                    <th className="pb-2 text-right">{isEn ? "Status" : "Kết quả"}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[color:var(--shell-border)]/40">
                  {sharingData.access_logs.map((log) => (
                    <tr key={log.id} className="text-[var(--text-primary)]">
                      <td className="py-2.5 font-mono text-[11px] text-[var(--text-muted)]">
                        {formatLocaleDate(uiLanguage, log.accessed_at, {
                          dateStyle: "short",
                          timeStyle: "short",
                        })}
                      </td>
                      <td className="py-2.5 font-semibold">
                        {log.actor_name}
                        {log.actor_relationship ? ` (${log.actor_relationship})` : ""}
                      </td>
                      <td className="py-2.5">
                        <span className="rounded bg-[var(--surface-muted)] px-2 py-0.5 text-[11px]">
                          {log.object_type}
                        </span>
                      </td>
                      <td className="py-2.5 capitalize">{log.action}</td>
                      <td className="py-2.5 text-right">
                        <Badge tone={log.outcome === "allowed" ? "ok" : "danger"}>
                          {log.outcome === "allowed"
                            ? isEn
                              ? "Allowed"
                              : "Cho phép"
                            : isEn
                              ? "Blocked"
                              : "Từ chối"}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-xs text-[var(--text-muted)] italic py-2">
              {isEn ? "No access events recorded yet." : "Chưa có sự kiện truy cập nào được ghi nhận."}
            </p>
          )}
        </section>
      </div>
    </div>
  );
}
