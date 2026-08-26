"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getRole, type UserRole } from "@/lib/auth-store";
import { acceptConsent, getConsentStatus, type ConsentStatus } from "@/lib/consent";
import { getRoleHomePath } from "@/lib/navigation.config";
import {
  getPhrOnboarding,
  updatePhrOnboarding,
  type PhrOnboarding,
} from "@/lib/phr-onboarding";
import { useUILanguage } from "@/lib/use-ui-language";
import { Badge } from "@/components/ui/badge";
import Button from "@/components/ui/button";
import { Field, Select } from "@/components/ui/field";
import Icon from "@/components/ui/icon";
import { SurfaceCard } from "@/components/ui/surface";
import { Toggle } from "@/components/ui/toggle";

export type OnboardingTrack = "global" | "personal" | "professional" | "tools";

export default function OnboardingPage() {
  const router = useRouter();
  const language = useUILanguage();
  const [role, setRole] = useState<UserRole>("normal");
  const [activeTrack, setActiveTrack] = useState<OnboardingTrack>("global");

  // Global First Run State
  const [consentStatus, setConsentStatus] = useState<ConsentStatus | null>(null);
  const [isConsentLoading, setIsConsentLoading] = useState(true);
  const [isConsentAccepting, setIsConsentAccepting] = useState(false);
  const [consentError, setConsentError] = useState("");

  // Personal Health Setup State
  const [phrOnboarding, setPhrOnboarding] = useState<PhrOnboarding | null>(null);
  const [isPhrLoading, setIsPhrLoading] = useState(true);
  const [isPhrSaving, setIsPhrSaving] = useState(false);
  const [phrError, setPhrError] = useState("");
  const [fullName, setFullName] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [gender, setGender] = useState("");
  const [bloodType, setBloodType] = useState("");
  const [heightCm, setHeightCm] = useState("");
  const [weightKg, setWeightKg] = useState("");
  const [personalizationConsent, setPersonalizationConsent] = useState(false);
  const [confirmSelfDeclared, setConfirmSelfDeclared] = useState(false);
  const [personalSetupSaved, setPersonalSetupSaved] = useState(false);

  // Initialize Role & Data
  useEffect(() => {
    const currentRole = getRole();
    setRole(currentRole);

    // Default track based on role
    if (currentRole === "doctor" || currentRole === "researcher" || currentRole === "admin") {
      setActiveTrack("professional");
    } else {
      setActiveTrack("global");
    }

    // Load global consent status
    void getConsentStatus()
      .then((status) => setConsentStatus(status))
      .catch(() => {
        // Fallback placeholder if not loaded
        setConsentStatus({
          consent_type: "general_medical",
          required_version: "2026.1",
          accepted: false,
        });
      })
      .finally(() => setIsConsentLoading(false));

    // Load PHR onboarding state
    void getPhrOnboarding()
      .then((data) => {
        setPhrOnboarding(data);
        setFullName(data.record.full_name ?? "");
        setDateOfBirth(data.record.date_of_birth ?? "");
        setGender(data.record.gender ?? "");
        setBloodType(data.record.blood_type ?? "");
        setHeightCm(data.record.height_cm != null ? String(data.record.height_cm) : "");
        setWeightKg(data.record.weight_kg != null ? String(data.record.weight_kg) : "");
        setPersonalizationConsent(Boolean(data.personalization_consent));
      })
      .catch(() => {
        // Fail open
      })
      .finally(() => setIsPhrLoading(false));
  }, []);

  const handleAcceptGlobalConsent = async () => {
    if (!consentStatus?.required_version) return;
    setIsConsentAccepting(true);
    setConsentError("");
    try {
      await acceptConsent({
        consent_version: consentStatus.required_version,
        accepted: true,
      });
      const updated = await getConsentStatus();
      setConsentStatus(updated);
    } catch {
      setConsentError("Không thể ghi nhận đồng thuận. Vui lòng thử lại.");
    } finally {
      setIsConsentAccepting(false);
    }
  };

  const parseNumber = (val: string): number | null => {
    const clean = val.trim().replace(",", ".");
    const num = Number(clean);
    return clean && Number.isFinite(num) ? num : null;
  };

  const handleSavePersonalSetup = async (action: "complete" | "skip") => {
    if (action === "complete" && !confirmSelfDeclared) {
      setPhrError("Vui lòng tích xác nhận thông tin sức khỏe là do bạn tự khai.");
      return;
    }

    if (action === "complete") {
      const parsedHeight = heightCm.trim() ? parseNumber(heightCm) : null;
      const parsedWeight = weightKg.trim() ? parseNumber(weightKg) : null;

      if (heightCm.trim() && (parsedHeight === null || parsedHeight < 0 || parsedHeight > 300)) {
        setPhrError("Chiều cao không hợp lệ. Vui lòng nhập số từ 0 đến 300 cm.");
        return;
      }
      if (weightKg.trim() && (parsedWeight === null || parsedWeight < 0 || parsedWeight > 800)) {
        setPhrError("Cân nặng không hợp lệ. Vui lòng nhập số từ 0 đến 800 kg.");
        return;
      }
    }

    setIsPhrSaving(true);
    setPhrError("");
    try {
      const payload =
        action === "skip"
          ? { action: "skip" as const }
          : {
              action: "complete" as const,
              confirm_self_declared: true,
              personalization_consent: personalizationConsent,
              full_name: fullName.trim() || undefined,
              date_of_birth: dateOfBirth || null,
              gender: gender || undefined,
              blood_type: bloodType || undefined,
              height_cm: parseNumber(heightCm),
              weight_kg: parseNumber(weightKg),
            };
      const result = await updatePhrOnboarding(payload);
      setPhrOnboarding(result);
      setPersonalSetupSaved(true);
      router.replace(getRoleHomePath(role));
      router.refresh();
    } catch {
      setPhrError("Không thể lưu thông tin hồ sơ sức khỏe. Vui lòng thử lại.");
    } finally {
      setIsPhrSaving(false);
    }
  };

  const isProfessionalRole = role === "doctor" || role === "researcher" || role === "admin";

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Header & Title */}
      <div className="mb-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--brand-surface)] text-[var(--brand-primary)]">
              <Icon name="body" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                Thiết lập & Định hướng CLARA
              </h1>
              <p className="text-sm text-[var(--text-secondary)]">
                Hệ thống hướng dẫn đa luồng: Khởi động chung, Hồ sơ cá nhân, Định hướng chuyên môn và Đồng thuận công cụ.
              </p>
            </div>
          </div>
          <Badge tone={isProfessionalRole ? "brand" : "neutral"}>
            Vai trò: {role === "doctor" ? "Bác sĩ (Doctor)" : role === "researcher" ? "Nhà nghiên cứu (Researcher)" : role === "admin" ? "Quản trị viên (Admin)" : "Người dùng cá nhân (Consumer)"}
          </Badge>
        </div>
      </div>

      {/* Multi-Track Navigation Tabs */}
      <div className="mb-8 flex flex-wrap gap-2 border-b border-[color:var(--shell-border)] pb-4" role="tablist" aria-label="Các luồng hướng dẫn">
        <button
          type="button"
          role="tab"
          aria-selected={activeTrack === "global"}
          onClick={() => setActiveTrack("global")}
          className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition ${
            activeTrack === "global"
              ? "bg-[var(--brand-primary)] text-[var(--brand-on-primary)] shadow-sm"
              : "bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:bg-[var(--surface-card)] hover:text-[var(--text-primary)]"
          }`}
        >
          <Icon name="warning" />
          <span>1. Khởi động chung</span>
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeTrack === "personal"}
          onClick={() => setActiveTrack("personal")}
          className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition ${
            activeTrack === "personal"
              ? "bg-[var(--brand-primary)] text-[var(--brand-on-primary)] shadow-sm"
              : "bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:bg-[var(--surface-card)] hover:text-[var(--text-primary)]"
          }`}
        >
          <Icon name="user-card" />
          <span>2. Hồ sơ sức khỏe (Tùy chọn)</span>
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeTrack === "professional"}
          onClick={() => setActiveTrack("professional")}
          className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition ${
            activeTrack === "professional"
              ? "bg-[var(--brand-primary)] text-[var(--brand-on-primary)] shadow-sm"
              : "bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:bg-[var(--surface-card)] hover:text-[var(--text-primary)]"
          }`}
        >
          <Icon name="clinical-notes" />
          <span>3. Định hướng chuyên môn</span>
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeTrack === "tools"}
          onClick={() => setActiveTrack("tools")}
          className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition ${
            activeTrack === "tools"
              ? "bg-[var(--brand-primary)] text-[var(--brand-on-primary)] shadow-sm"
              : "bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:bg-[var(--surface-card)] hover:text-[var(--text-primary)]"
          }`}
        >
          <Icon name="check" />
          <span>4. Đồng thuận công cụ</span>
        </button>
      </div>

      {/* TRACK 1: GLOBAL FIRST RUN */}
      {activeTrack === "global" && (
        <div className="space-y-6" data-testid="track-global">
          <SurfaceCard className="space-y-4">
            <div className="flex items-start gap-3">
              <Icon name="warning" className="text-[var(--brand-primary)]" />
              <div>
                <h2 className="text-lg font-bold text-[var(--text-primary)]">
                  Tuyên bố miễn trừ trách nhiệm y khoa & Cam kết an toàn
                </h2>
                <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">
                  CLARA (Clinical Agent for Retrieval & Analysis) là hệ thống AI hỗ trợ ra quyết định lâm sàng và tra cứu y tế dựa trên dữ liệu tự khai và y văn đối chứng. CLARA <strong>không phải là bác sĩ</strong> và <strong>không thay thế cho chẩn đoán, điều trị hay đánh giá chuyên môn y khoa</strong>.
                </p>
              </div>
            </div>
            <div className="rounded-xl border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-4 text-sm text-[var(--status-danger-text)]">
              <strong>Cấp cứu & Khẩn cấp:</strong> Nếu bạn đang gặp các triệu chứng cấp tính (đau thắt ngực, khó thở nghiêm trọng, co giật, sốt cao mê sảng...), hãy liên hệ cấp cứu 115 hoặc đến cơ sở y tế gần nhất ngay lập tức.
            </div>
          </SurfaceCard>

          <SurfaceCard className="space-y-4">
            <h3 className="text-base font-semibold text-[var(--text-primary)]">
              Chính sách bảo mật & Quyền riêng tư
            </h3>
            <p className="text-sm text-[var(--text-secondary)]">
              Hệ thống vận hành theo nguyên tắc bảo vệ quyền riêng tư nghiêm ngặt. Dữ liệu chỉ số y tế chỉ được xử lý khi có sự chấp thuận rõ ràng của bạn và không bao giờ bị sử dụng cho mục đích quảng cáo hay thương mại.
            </p>
            <div className="flex flex-wrap gap-4 text-sm">
              <Link href="/legal/terms" className="font-semibold text-[var(--brand-primary)] hover:underline">
                Điều khoản dịch vụ →
              </Link>
              <Link href="/legal/privacy" className="font-semibold text-[var(--brand-primary)] hover:underline">
                Chính sách bảo mật →
              </Link>
              <Link href="/legal/consent" className="font-semibold text-[var(--brand-primary)] hover:underline">
                Văn bản đồng thuận y tế →
              </Link>
            </div>
          </SurfaceCard>

          <SurfaceCard className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold text-[var(--text-primary)]">
                  Đồng thuận y tế phiên bản {consentStatus?.required_version || "2026.1"}
                </h3>
                <p className="text-xs text-[var(--text-muted)]">
                  {consentStatus?.accepted
                    ? `Đã đồng thuận lúc ${consentStatus.accepted_at ? new Date(consentStatus.accepted_at).toLocaleString("vi-VN") : "trước đó"}`
                    : "Yêu cầu xác nhận đồng thuận trước khi tra cứu nội dung y khoa."}
                </p>
              </div>
              {consentStatus?.accepted ? (
                <Badge tone="ok">
                  Đã chấp thuận
                </Badge>
              ) : (
                <Button
                  variant="primary"
                  loading={isConsentAccepting}
                  disabled={isConsentAccepting || isConsentLoading}
                  onClick={handleAcceptGlobalConsent}
                >
                  Xác nhận đồng thuận
                </Button>
              )}
            </div>
            {consentError && (
              <p className="text-sm text-[var(--status-danger-text)]">{consentError}</p>
            )}
          </SurfaceCard>

          <div className="flex flex-wrap items-center justify-between gap-4 pt-4">
            <Button
              variant="secondary"
              onClick={() => router.replace(getRoleHomePath(role))}
            >
              Vào trang chủ ngay
            </Button>
            <Button
              variant="primary"
              onClick={() => setActiveTrack(isProfessionalRole ? "professional" : "personal")}
            >
              Tiếp tục bước tiếp theo →
            </Button>
          </div>
        </div>
      )}

      {/* TRACK 2: PERSONAL HEALTH SETUP */}
      {activeTrack === "personal" && (
        <div className="space-y-6" data-testid="track-personal">
          <SurfaceCard className="space-y-3">
            <div className="flex items-center gap-2">
              <Icon name="clinical-notes" className="text-[var(--brand-primary)]" />
              <h2 className="text-lg font-bold text-[var(--text-primary)]">
                Thiết lập Hồ sơ Sức khỏe Cá nhân (Tùy chọn)
              </h2>
            </div>
            <p className="text-sm text-[var(--text-secondary)]">
              Dành cho việc theo dõi chỉ số cá nhân. <strong>Mọi trường đều không bắt buộc</strong> và bạn có thể bỏ qua bất cứ lúc nào. Thông tin này giúp CLARA cá nhân hóa cảnh báo tương tác thuốc và nhắc nhở sức khỏe.
            </p>
          </SurfaceCard>

          <SurfaceCard className="space-y-5">
            <Field
              label="Họ và tên"
              optional
              maxLength={100}
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="VD: Nguyễn Văn A"
            />

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field
                label="Ngày sinh"
                optional
                type="date"
                max={new Date().toISOString().split("T")[0]}
                value={dateOfBirth}
                onChange={(e) => setDateOfBirth(e.target.value)}
              />

              <Select
                label="Giới tính"
                optional
                value={gender}
                onChange={(e) => setGender(e.target.value)}
              >
                <option value="">Không cung cấp</option>
                <option value="male">Nam</option>
                <option value="female">Nữ</option>
                <option value="other">Khác</option>
              </Select>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Select
                label="Nhóm máu"
                optional
                value={bloodType}
                onChange={(e) => setBloodType(e.target.value)}
              >
                <option value="">Chưa rõ</option>
                <option value="A">A</option>
                <option value="B">B</option>
                <option value="AB">AB</option>
                <option value="O">O</option>
              </Select>

              <Field
                label="Chiều cao"
                optional
                hint="cm"
                type="number"
                min={0}
                max={300}
                value={heightCm}
                onChange={(e) => setHeightCm(e.target.value)}
                placeholder="170"
              />

              <Field
                label="Cân nặng"
                optional
                hint="kg"
                type="number"
                min={0}
                max={800}
                value={weightKg}
                onChange={(e) => setWeightKg(e.target.value)}
                placeholder="65"
              />
            </div>

            <div className="pt-2">
              <Toggle
                checked={personalizationConsent}
                onChange={setPersonalizationConsent}
                label="Cho phép cá nhân hóa trải nghiệm"
                description="Sử dụng các chỉ số tự khai trên để đối chiếu liều lượng và cảnh báo tương tác thuốc trong các câu trả lời."
              />
            </div>

            <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4">
              <input
                type="checkbox"
                checked={confirmSelfDeclared}
                onChange={(e) => setConfirmSelfDeclared(e.target.checked)}
                className="mt-1 h-5 w-5 rounded border-[color:var(--shell-border-strong)] text-[var(--brand-primary)] focus:ring-[var(--brand-primary)]"
              />
              <span className="text-sm text-[var(--text-primary)]">
                Tôi xác nhận các thông tin trên là do tôi tự nguyện cung cấp và tự khai.
              </span>
            </label>

            {phrError && (
              <p className="text-sm font-semibold text-[var(--status-danger-text)]">{phrError}</p>
            )}

            <div className="flex flex-wrap items-center justify-between gap-4 pt-4">
              <Button
                variant="secondary"
                disabled={isPhrSaving}
                onClick={() => handleSavePersonalSetup("skip")}
              >
                Bỏ qua thiết lập hồ sơ
              </Button>
              <Button
                variant="primary"
                loading={isPhrSaving}
                disabled={isPhrSaving || !confirmSelfDeclared}
                onClick={() => handleSavePersonalSetup("complete")}
              >
                Lưu và hoàn tất hồ sơ
              </Button>
            </div>
          </SurfaceCard>
        </div>
      )}

      {/* TRACK 3: PROFESSIONAL ORIENTATION */}
      {activeTrack === "professional" && (
        <div className="space-y-6" data-testid="track-professional">
          <SurfaceCard className="space-y-3">
            <div className="flex items-center gap-2">
              <Icon name="clinical-notes" className="text-[var(--brand-primary)]" />
              <h2 className="text-lg font-bold text-[var(--text-primary)]">
                Không gian Làm việc Dành cho Bác sĩ & Nhà nghiên cứu
              </h2>
            </div>
            <p className="text-sm leading-6 text-[var(--text-secondary)]">
              Bác sĩ và chuyên gia y tế được cấp quyền truy cập trực tiếp vào các công cụ lâm sàng chuyên sâu mà <strong>không bị chặn bởi biểu mẫu sinh trắc học cá nhân (chiều cao, cân nặng, nhóm máu)</strong>.
            </p>
          </SurfaceCard>

          {/* Professional Features Grid */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <SurfaceCard className="space-y-3">
              <div className="flex items-center gap-2 text-[var(--brand-primary)]">
                <Icon name="contact" />
                <h3 className="text-base font-bold text-[var(--text-primary)]">Hội đồng Hội chẩn AI (Council)</h3>
              </div>
              <p className="text-sm text-[var(--text-secondary)]">
                Tổ chức phiên hội chẩn đa tác nhân (Nội khoa, Tim mạch, Dược lâm sàng, Cấp cứu), phân tích mức độ đồng thuận và điểm bất đồng y khoa kèm bằng chứng dẫn xuất.
              </p>
              <Link href="/council" className="inline-flex items-center gap-1 text-sm font-semibold text-[var(--brand-primary)] hover:underline">
                Đến Hội đồng Hội chẩn →
              </Link>
            </SurfaceCard>

            <SurfaceCard className="space-y-3">
              <div className="flex items-center gap-2 text-[var(--brand-primary)]">
                <Icon name="mic" />
                <h3 className="text-base font-bold text-[var(--text-primary)]">Ghi chép Lâm sàng (Scribe)</h3>
              </div>
              <p className="text-sm text-[var(--text-secondary)]">
                Lắng nghe cuộc trao đổi khám chữa bệnh và tự động soạn thảo bệnh án chuẩn cấu trúc SOAP. Bảo mật tuyệt đối và có cơ chế kiểm tra đồng thuận người bệnh.
              </p>
              <Link href="/scribe" className="inline-flex items-center gap-1 text-sm font-semibold text-[var(--brand-primary)] hover:underline">
                Đến Ghi chép Scribe →
              </Link>
            </SurfaceCard>

            <SurfaceCard className="space-y-3">
              <div className="flex items-center gap-2 text-[var(--brand-primary)]">
                <Icon name="clinical-notes" />
                <h3 className="text-base font-bold text-[var(--text-primary)]">Bằng chứng Sống & Y văn (Evidence)</h3>
              </div>
              <p className="text-sm text-[var(--text-secondary)]">
                Tra cứu y văn đối chiếu nguồn PubMed, Dược thư Quốc gia Việt Nam (VN-DIADR) và kiểm tra tương tác thuốc nghiêm ngặt qua CareGuard FIDES.
              </p>
              <Link href="/chat" className="inline-flex items-center gap-1 text-sm font-semibold text-[var(--brand-primary)] hover:underline">
                Đến Tra cứu Chat Y khoa →
              </Link>
            </SurfaceCard>

            <SurfaceCard className="space-y-3">
              <div className="flex items-center gap-2 text-[var(--brand-primary)]">
                <Icon name="clinical-notes" />
                <h3 className="text-base font-bold text-[var(--text-primary)]">Bảng Điều khiển Tổng quan (Dashboard)</h3>
              </div>
              <p className="text-sm text-[var(--text-secondary)]">
                Theo dõi tiến độ ca bệnh, ca hội chẩn chờ phản hồi, thống kê vận hành và tài liệu nghiên cứu trong ngày.
              </p>
              <Link href="/dashboard" className="inline-flex items-center gap-1 text-sm font-semibold text-[var(--brand-primary)] hover:underline">
                Đến Bảng điều khiển →
              </Link>
            </SurfaceCard>
          </div>

          <SurfaceCard className="space-y-3">
            <h4 className="text-sm font-bold text-[var(--text-primary)]">
              Nguyên tắc Bác sĩ là Trung tâm Quyết định
            </h4>
            <p className="text-sm text-[var(--text-secondary)]">
              CLARA hỗ trợ tổng hợp thông tin, trích xuất y văn và giảm tải công việc hành chính. Mọi quyết định chẩn đoán, phác đồ điều trị và kê đơn thuốc cuối cùng luôn thuộc về thẩm quyền chuyên môn của Bác sĩ.
            </p>
          </SurfaceCard>

          <div className="flex flex-wrap items-center justify-between gap-4 pt-4">
            <Button
              variant="secondary"
              onClick={() => setActiveTrack("tools")}
            >
              Xem đồng thuận công cụ →
            </Button>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="secondary"
                onClick={() => router.push("/council")}
              >
                Mở Hội chẩn (Council)
              </Button>
              <Button
                variant="primary"
                onClick={() => router.replace(getRoleHomePath(role))}
              >
                Vào Không gian Chuyên môn
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* TRACK 4: TOOL-SPECIFIC CONSENT */}
      {activeTrack === "tools" && (
        <div className="space-y-6" data-testid="track-tools">
          <SurfaceCard className="space-y-3">
            <div className="flex items-center gap-2">
              <Icon name="warning" className="text-[var(--brand-primary)]" />
              <h2 className="text-lg font-bold text-[var(--text-primary)]">
                Đồng thuận theo Ngữ cảnh cho Công cụ (Contextual Tool Consent)
              </h2>
            </div>
            <p className="text-sm text-[var(--text-secondary)]">
              CLARA áp dụng cơ chế <strong>đồng thuận đúng thời điểm (Just-in-Time Consent)</strong>. Các công cụ có mức độ tác động cao sẽ yêu cầu sự xác nhận độc lập ngay trước khi kích hoạt.
            </p>
          </SurfaceCard>

          <div className="space-y-4">
            <SurfaceCard className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-semibold text-[var(--text-primary)]">
                  <Icon name="mic" className="text-[var(--brand-primary)]" />
                  <span>Đồng thuận Ghi âm Scribe</span>
                </div>
                <Badge tone="brand">Theo từng phiên</Badge>
              </div>
              <p className="text-sm text-[var(--text-secondary)]">
                Yêu cầu sự đồng ý của bệnh nhân trước khi mở microphone. Bản ghi âm thô được xử lý thành văn bản và không lưu trữ vĩnh viễn file âm thanh nếu chưa được cấp quyền.
              </p>
            </SurfaceCard>

            <SurfaceCard className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-semibold text-[var(--text-primary)]">
                  <Icon name="medication" className="text-[var(--brand-primary)]" />
                  <span>Đồng thuận Kiểm tra Thuốc & DDI (CareGuard)</span>
                </div>
                <Badge tone="ok">Tự động đối chiếu</Badge>
              </div>
              <p className="text-sm text-[var(--text-secondary)]">
                Dữ liệu thuốc tự khai hoặc quét nhãn được đối chiếu với cơ sở dữ liệu Dược thư Quốc gia Việt Nam để cảnh báo chống chỉ định và tương tác thuốc nguy hiểm.
              </p>
            </SurfaceCard>

            <SurfaceCard className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-semibold text-[var(--text-primary)]">
                  <Icon name="share" className="text-[var(--brand-primary)]" />
                  <span>Đồng thuận Chia sẻ Hồ sơ & Gia đình</span>
                </div>
                <Badge tone="neutral">Phân quyền rõ ràng</Badge>
              </div>
              <p className="text-sm text-[var(--text-secondary)]">
                Người dùng có thể tạo liên kết chia sẻ hồ sơ có thời hạn cho bác sĩ hoặc thành viên gia đình và có quyền thu hồi quyền truy cập (Right to Revoke) bất kỳ lúc nào.
              </p>
            </SurfaceCard>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-4 pt-4">
            <Link
              href="/legal/consent"
              className="text-sm font-semibold text-[var(--brand-primary)] hover:underline"
            >
              Xem toàn bộ văn bản pháp lý & đồng thuận →
            </Link>
            <Button
              variant="primary"
              onClick={() => router.replace(getRoleHomePath(role))}
            >
              Hoàn tất & Bắt đầu sử dụng
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
