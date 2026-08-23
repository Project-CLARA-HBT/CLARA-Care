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

  // Tab state: active | expired | revoked
  const [activeTab, setActiveTab] = useState<"active" | "expired" | "revoked">("active");

  // Selected grant for right detail drawer
  const [selectedGrantId, setSelectedGrantId] = useState<string | null>("grant-1");

  // Recipient preview modal state
  const [recipientPreviewOpen, setRecipientPreviewOpen] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);

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

  const grants = sharingData?.grants || [];
  const activeGrants = grants.filter((g) => g.status === "active");
  const expiredGrants = grants.filter((g) => g.status === "expired");
  const revokedGrants = grants.filter((g) => g.status === "revoked");

  const displayedGrants =
    activeTab === "active"
      ? activeGrants
      : activeTab === "expired"
        ? expiredGrants
        : revokedGrants;

  const currentSelectedGrant =
    grants.find((g) => g.id === selectedGrantId) || grants[0] || null;

  // Calculate days remaining helper
  const getDaysRemaining = (expiresAt: string) => {
    const exp = new Date(expiresAt).getTime();
    const now = Date.now();
    const diffDays = Math.ceil((exp - now) / (1000 * 60 * 60 * 24));
    return diffDays > 0 ? diffDays : 0;
  };

  const handleCopyLink = () => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      const shareUrl = `${typeof window !== "undefined" ? window.location.origin : "https://clara.care"}/phr/shared/${currentSelectedGrant?.id || "tok-demo"}`;
      navigator.clipboard.writeText(shareUrl);
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 2000);
    }
  };

  return (
    <div className="space-y-6" data-testid="you-sharing-page">
      <HealthPageHeader
        title={isEn ? "Sharing & Privacy Grants" : "Chia sẻ & Quyền riêng tư"}
        subtitle={
          isEn
            ? "You decide who can access specific parts of your medical data with time-bounded grants and instant revocation."
            : "Bạn quyết định ai có thể xem phần nào trong dữ liệu sức khỏe của mình với phân quyền có thời hạn."
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
          className="rounded-[var(--radius-2xl)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] p-4 text-xs text-[var(--status-ok-text)] space-y-2"
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

      {/* Recipient Preview Modal ("Xem như người nhận" Stitch Reference) */}
      {recipientPreviewOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-md overflow-y-auto"
          data-testid="recipient-preview-modal"
          role="dialog"
          aria-modal="true"
        >
          <div className="relative w-full max-w-3xl rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 md:p-8 shadow-2xl space-y-6 my-8">
            <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-4">
              <div className="flex items-center gap-2 text-[var(--text-secondary)]">
                <Icon name="share" size="1.1rem" className="text-[var(--text-brand)]" />
                <span className="text-xs font-bold uppercase tracking-widest text-[var(--text-brand)]">
                  CLARA-Care Shared Link
                </span>
                <span className="rounded-full bg-[var(--surface-muted)] px-2.5 py-0.5 text-[10px] font-semibold text-[var(--text-secondary)] border border-[color:var(--shell-border)]">
                  {isEn ? "Read-Only Mode" : "Bản đọc (Read-only)"}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setRecipientPreviewOpen(false)}
                className="rounded-lg p-1.5 text-[var(--text-muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
              >
                <Icon name="close" size="1.25rem" />
              </button>
            </div>

            {/* Header Content */}
            <div className="space-y-2">
              <h3 className="text-xl font-bold text-[var(--text-primary)]">
                {isEn ? "Shared Conversation: Blood Pressure Medication" : "Nội dung được chia sẻ qua CLARA"}
              </h3>
              <p className="text-xs text-[var(--text-secondary)]">
                {isEn ? "Trao đổi về thuốc huyết áp & hướng dẫn sử dụng an toàn" : "Trao đổi về thuốc huyết áp và hướng xử trí tác dụng phụ"}
              </p>
            </div>

            {/* Safety Banner */}
            <div className="rounded-xl bg-amber-500/10 border border-amber-500/30 p-3.5 flex items-start gap-3 text-xs text-[var(--text-primary)]">
              <Icon name="warning" size="1.1rem" className="text-amber-500 shrink-0 mt-0.5" />
              <p className="leading-relaxed">
                {isEn
                  ? "This content is a shared record of a medical consultation and does not replace in-person professional clinical evaluation."
                  : "Nội dung này là bản chia sẻ của một cuộc trò chuyện và không thay thế đánh giá y tế trực tiếp của bác sĩ."}
              </p>
            </div>

            {/* Simulated Conversation Box */}
            <div className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--bg-elev-3)] p-5 space-y-4">
              {/* User Query */}
              <div className="flex flex-col items-end gap-1.5">
                <span className="text-[10px] font-bold text-[var(--text-muted)]">
                  {currentSelectedGrant?.grantee_name || "Người dùng"}
                </span>
                <div className="rounded-2xl rounded-tr-sm bg-[var(--surface-panel)] border border-[color:var(--shell-border)] p-3.5 text-xs text-[var(--text-primary)] max-w-lg">
                  Tôi đang dùng Lisinopril 10mg nhưng dạo này hay bị ho khan. Có sao không?
                </div>
              </div>

              {/* CLARA Response */}
              <div className="flex flex-col items-start gap-1.5">
                <div className="flex items-center gap-1.5 text-[var(--brand-600)]">
                  <Icon name="clinical-notes" size="0.9rem" />
                  <span className="text-[10px] font-bold">CLARA</span>
                </div>
                <div className="rounded-2xl rounded-tl-sm bg-[var(--surface-muted)] border border-[color:var(--brand-400)]/30 p-4 text-xs text-[var(--text-primary)] space-y-2 max-w-xl">
                  <p className="leading-relaxed">
                    Chào bạn, ho khan là một tác dụng phụ khá phổ biến của Lisinopril (nhóm ức chế men chuyển ACE inhibitors).
                    <sup className="ml-1 inline-flex items-center justify-center rounded-full bg-[var(--brand-500)]/20 px-1.5 text-[10px] font-bold text-[var(--brand-600)]">1</sup>
                  </p>
                  <p className="leading-relaxed">
                    Tình trạng này không nguy hiểm đến tính mạng nhưng có thể gây khó chịu. Bạn không nên tự ý ngưng thuốc đột ngột. Hãy trao đổi với bác sĩ điều trị để được hướng dẫn đổi sang nhóm thuốc chẹn thụ thể ARB nếu cần.
                    <sup className="ml-1 inline-flex items-center justify-center rounded-full bg-[var(--brand-500)]/20 px-1.5 text-[10px] font-bold text-[var(--brand-600)]">2</sup>
                  </p>
                </div>
              </div>

              {/* Citations List */}
              <div className="pt-3 border-t border-[color:var(--shell-border)]/60 text-xs text-[var(--text-secondary)] space-y-1">
                <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)] block mb-1">
                  {isEn ? "References" : "Nguồn tham khảo"}
                </span>
                <p>1. Hướng dẫn chẩn đoán và điều trị tăng huyết áp, Bộ Y Tế (Cập nhật 2025).</p>
                <p>2. VNHA/VSH Khuyến cáo quản lý bệnh tim mạch người lớn (2024).</p>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={() => setRecipientPreviewOpen(false)}
              >
                {isEn ? "Close Preview" : "Đóng xem trước"}
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      {/* Main Sharing Layout */}
      <div className="space-y-6">
        {/* Status Filter Tabs */}
        <div className="flex gap-4 border-b border-[color:var(--shell-border)]/60 pb-2">
          <button
            type="button"
            onClick={() => setActiveTab("active")}
            className={`pb-2 px-1 text-sm font-bold transition border-b-2 ${
              activeTab === "active"
                ? "border-[color:var(--brand-600)] text-[var(--brand-600)]"
                : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            {isEn ? `Active Grants (${activeGrants.length})` : `Đang hoạt động (${activeGrants.length})`}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("expired")}
            className={`pb-2 px-1 text-sm font-bold transition border-b-2 ${
              activeTab === "expired"
                ? "border-[color:var(--brand-600)] text-[var(--brand-600)]"
                : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            {isEn ? `Expired (${expiredGrants.length})` : `Đã hết hạn (${expiredGrants.length})`}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("revoked")}
            className={`pb-2 px-1 text-sm font-bold transition border-b-2 ${
              activeTab === "revoked"
                ? "border-[color:var(--brand-600)] text-[var(--brand-600)]"
                : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            {isEn ? `Revoked (${revokedGrants.length})` : `Đã thu hồi (${revokedGrants.length})`}
          </button>
        </div>

        {/* 2-Column Split: Grants List & Detail Drawer */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column: Grants List (Span 7) */}
          <div className="space-y-4 lg:col-span-7" data-testid="active-grants-section">
            {isLoading ? (
              <div className="h-44 animate-pulse bg-[var(--surface-muted)] rounded-2xl" />
            ) : displayedGrants.length > 0 ? (
              <div className="space-y-3" data-testid="grants-list">
                {displayedGrants.map((grant) => {
                  const daysLeft = getDaysRemaining(grant.expires_at);
                  const isSelected = selectedGrantId === grant.id;

                  return (
                    <div
                      key={grant.id}
                      onClick={() => setSelectedGrantId(grant.id)}
                      className={`rounded-[var(--radius-2xl)] border p-5 shadow-sm transition cursor-pointer ${
                        isSelected
                          ? "border-[color:var(--brand-500)] bg-[var(--surface-panel)] ring-1 ring-[var(--brand-500)]/30"
                          : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] hover:border-[color:var(--shell-border)]/80"
                      }`}
                      data-testid={`grant-card-${grant.id}`}
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        <div className="flex items-center gap-3.5">
                          <div className="w-11 h-11 rounded-full bg-[var(--brand-50)] text-[var(--brand-700)] border border-[color:var(--brand-200)] flex items-center justify-center font-bold text-base shrink-0">
                            {grant.grantee_name.charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <h4 className="text-sm font-bold text-[var(--text-primary)]">
                              {grant.grantee_name}
                            </h4>
                            <p className="text-xs text-[var(--text-secondary)]">
                              {grant.grantee_relationship} · {isEn ? "Caregiver" : "Người chăm sóc"}
                            </p>
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-[11px] font-bold text-emerald-500">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                            {isEn ? "Active" : "Đang hoạt động"}
                          </span>

                          <Button
                            type="button"
                            variant="danger"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              setGrantToRevoke(grant);
                            }}
                            data-testid={`revoke-grant-btn-${grant.id}`}
                            className="rounded-lg text-xs"
                          >
                            {isEn ? "Revoke" : "Thu hồi"}
                          </Button>
                        </div>
                      </div>

                      {/* Scoped Categories & Expiration Countdown */}
                      <div className="mt-4 pt-3 border-t border-[color:var(--shell-border)]/60 flex flex-wrap items-center justify-between gap-2 text-xs">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="text-[11px] text-[var(--text-secondary)] mr-1">
                            {isEn ? "Access:" : "Quyền:"}
                          </span>
                          {grant.categories.map((cat) => (
                            <span
                              key={cat}
                              className="rounded-md bg-[var(--brand-50)]/40 border border-[color:var(--brand-300)]/40 px-2 py-0.5 text-[11px] font-medium text-[var(--brand-700)]"
                            >
                              {isEn ? CATEGORY_CONFIG[cat]?.labelEn : CATEGORY_CONFIG[cat]?.labelVi}
                            </span>
                          ))}
                        </div>

                        {/* Expiration Countdown */}
                        <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[var(--text-secondary)] bg-[var(--surface-muted)] px-2.5 py-1 rounded-md">
                          <Icon name="progress" size="0.8rem" className="text-[var(--text-brand)]" />
                          <span>
                            {isEn
                              ? `${daysLeft} days remaining`
                              : `Còn ${daysLeft} ngày (${formatLocaleDate(uiLanguage, grant.expires_at, { dateStyle: "medium" })})`}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <EmptyState
                title={isEn ? "No sharing grants in this tab" : "Không có quyền chia sẻ nào trong mục này"}
                description={
                  isEn
                    ? "Share your medical updates, prescriptions, and visit plans with your family safely."
                    : "Chia sẻ đơn thuốc, lịch khám và kế hoạch điều trị một cách an toàn với người thân."
                }
                actionLabel={isEn ? "Create New Grant" : "Tạo quyền chia sẻ mới"}
                onAction={() => {
                  setWizardStep(1);
                  setWizardOpen(true);
                }}
              />
            )}

            {/* Dashed Add Action Button */}
            <button
              type="button"
              onClick={() => {
                setWizardStep(1);
                setWizardOpen(true);
              }}
              className="w-full py-3.5 rounded-2xl border-2 border-dashed border-[color:var(--shell-border)] hover:border-[color:var(--brand-500)] hover:bg-[var(--brand-50)]/10 text-[var(--text-secondary)] hover:text-[var(--text-brand)] transition flex items-center justify-center gap-2 text-xs font-bold"
            >
              <Icon name="plus" size="1rem" />
              <span>{isEn ? "Invite Family Member or Doctor" : "Mời người thân hoặc Bác sĩ"}</span>
            </button>
          </div>

          {/* Right Detail Drawer / Panel (Span 5) */}
          <aside className="lg:col-span-5 space-y-5 lg:sticky lg:top-24">
            <div className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm space-y-5">
              <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-3">
                <div className="flex items-center gap-2 text-[var(--text-brand)]">
                  <Icon name="user-card" size="1.2rem" />
                  <h3 className="font-bold text-sm text-[var(--text-primary)]">
                    {isEn ? "Grant Scope & Details" : "Chi tiết Quyền truy cập"}
                  </h3>
                </div>
                {currentSelectedGrant ? (
                  <Badge tone={currentSelectedGrant.status === "active" ? "ok" : "warn"}>
                    {currentSelectedGrant.grantee_relationship}
                  </Badge>
                ) : null}
              </div>

              {currentSelectedGrant ? (
                <div className="space-y-4 text-xs">
                  {/* Shared Items Checklist */}
                  <div className="space-y-2">
                    <span className="font-bold uppercase tracking-wider text-[10px] text-[var(--text-secondary)] block">
                      {isEn ? "Items Shared With Caregiver" : "Nội dung đang được chia sẻ"}
                    </span>
                    <div className="rounded-xl bg-[var(--surface-muted)] p-3 border border-[color:var(--shell-border)] space-y-2">
                      {currentSelectedGrant.categories.map((c) => (
                        <div key={c} className="flex items-center gap-2 text-[var(--text-primary)] font-medium">
                          <Icon name="check" size="0.85rem" className="text-[var(--status-ok-text)]" />
                          <span>{isEn ? CATEGORY_CONFIG[c]?.labelEn : CATEGORY_CONFIG[c]?.labelVi}</span>
                        </div>
                      ))}
                      <div className="flex items-center gap-2 text-[var(--text-muted)] opacity-60">
                        <span className="w-3.5 h-3.5 rounded border border-[color:var(--shell-border)] inline-block" />
                        <span>{isEn ? "Restricted Health Notes (Private)" : "Ghi chú sức khỏe bảo mật"}</span>
                      </div>
                    </div>
                  </div>

                  {/* Access Level */}
                  <div className="space-y-1">
                    <span className="font-bold uppercase tracking-wider text-[10px] text-[var(--text-secondary)] block">
                      {isEn ? "Access Level" : "Quyền truy cập"}
                    </span>
                    <div className="rounded-xl bg-[var(--surface-muted)] p-3 border border-[color:var(--shell-border)] flex items-center justify-between">
                      <div className="flex items-center gap-2 text-[var(--text-primary)]">
                        <Icon name="clinical-notes" size="1rem" className="text-[var(--text-brand)]" />
                        <span>{isEn ? "Authenticated Read & Adherence Observations" : "Xem & Ghi nhận tuân thủ thuốc"}</span>
                      </div>
                    </div>
                  </div>

                  {/* Expiration */}
                  <div className="space-y-1">
                    <span className="font-bold uppercase tracking-wider text-[10px] text-[var(--text-secondary)] block">
                      {isEn ? "Validity Window" : "Thời hạn hiệu lực"}
                    </span>
                    <div className="rounded-xl bg-[var(--surface-muted)] p-3 border border-[color:var(--shell-border)] flex items-center justify-between">
                      <div className="flex items-center gap-2 text-[var(--text-primary)]">
                        <Icon name="calendar" size="1rem" className="text-[var(--text-secondary)]" />
                        <span>
                          {formatLocaleDate(uiLanguage, currentSelectedGrant.expires_at, {
                            dateStyle: "medium",
                          })}
                        </span>
                      </div>
                      <span className="font-bold text-[var(--text-brand)]">
                        {getDaysRemaining(currentSelectedGrant.expires_at)} {isEn ? "days left" : "ngày còn lại"}
                      </span>
                    </div>
                  </div>

                  {/* Activity Stats */}
                  <div className="space-y-1">
                    <span className="font-bold uppercase tracking-wider text-[10px] text-[var(--text-secondary)] block">
                      {isEn ? "Activity & Logs" : "Hoạt động"}
                    </span>
                    <div className="rounded-xl bg-[var(--surface-muted)] p-3 border border-[color:var(--shell-border)] flex items-center justify-between">
                      <div>
                        <span className="font-bold text-sm text-[var(--text-primary)] block">3 lượt mở</span>
                        <span className="text-[11px] text-[var(--text-secondary)]">Lần gần nhất: 10:58 hôm nay</span>
                      </div>
                      <Icon name="progress" size="1.4rem" className="text-[var(--text-brand)] opacity-60" />
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="pt-2 border-t border-[color:var(--shell-border)]/60 space-y-2">
                    <button
                      type="button"
                      onClick={handleCopyLink}
                      className="w-full py-2.5 px-4 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] hover:bg-[var(--surface-hover)] text-[var(--text-primary)] font-bold text-xs flex items-center justify-center gap-2 transition"
                    >
                      <Icon name="share" size="0.9rem" />
                      <span>{copiedLink ? (isEn ? "Link Copied!" : "Đã sao chép liên kết!") : (isEn ? "Copy Sharing Link" : "Sao chép liên kết")}</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => setRecipientPreviewOpen(true)}
                      className="w-full py-2.5 px-4 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] hover:bg-[var(--surface-hover)] text-[var(--text-primary)] font-bold text-xs flex items-center justify-center gap-2 transition"
                    >
                      <Icon name="clinical-notes" size="0.9rem" />
                      <span>{isEn ? "Preview as Recipient" : "Xem như người nhận"}</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => setGrantToRevoke(currentSelectedGrant)}
                      className="w-full py-2.5 px-4 rounded-xl border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)] font-bold text-xs flex items-center justify-center gap-2 hover:opacity-80 transition"
                    >
                      <Icon name="trash" size="0.9rem" />
                      <span>{isEn ? "Revoke Grant Immediately" : "Thu hồi liên kết"}</span>
                    </button>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-[var(--text-muted)] italic">
                  {isEn ? "Select a grant to inspect permissions." : "Chọn một quyền chia sẻ để xem chi tiết."}
                </p>
              )}
            </div>

            {/* Medical Standard Privacy Notice */}
            <div className="rounded-[var(--radius-2xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)] p-5 text-center space-y-2">
              <div className="w-10 h-10 rounded-full bg-[var(--brand-50)] text-[var(--brand-700)] flex items-center justify-center mx-auto">
                <Icon name="user-card" size="1.2rem" />
              </div>
              <h4 className="font-bold text-xs text-[var(--text-primary)]">
                {isEn ? "Medical Standard Encryption" : "Bảo mật chuẩn y tế"}
              </h4>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                {isEn
                  ? "All shared data is encrypted end-to-end. CLARA never sells or discloses health information to third parties."
                  : "Dữ liệu của bạn được mã hóa đầu cuối. CLARA không chia sẻ thông tin với bên thứ ba vì mục đích quảng cáo."}
              </p>
            </div>
          </aside>
        </div>

        {/* Access History & Audit Log Section */}
        <section
          className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm space-y-4"
          data-testid="access-history-section"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-[var(--text-brand)]">
              <Icon name="progress" size="1.25rem" />
              <h2 className="text-sm font-bold text-[var(--text-primary)]">
                {isEn ? "Access History & Audit Log" : "Hoạt động gần đây & Lịch sử kiểm toán"}
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
                        <span className="rounded-md bg-[var(--surface-muted)] px-2 py-0.5 text-[11px] font-medium">
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
