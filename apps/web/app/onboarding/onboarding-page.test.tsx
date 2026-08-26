import type { ReactNode } from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const push = vi.fn();
  const replace = vi.fn();
  const refresh = vi.fn();
  let currentRole: string = "normal";
  return {
    getRole: () => currentRole,
    setTestRole: (r: string) => {
      currentRole = r;
    },
    getConsentStatus: vi.fn(),
    acceptConsent: vi.fn(),
    getPhrOnboarding: vi.fn(),
    updatePhrOnboarding: vi.fn(),
    push,
    replace,
    refresh,
    router: { push, replace, refresh },
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => mocks.router,
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/lib/auth-store", () => ({
  getRole: () => mocks.getRole(),
}));

vi.mock("@/lib/consent", () => ({
  getConsentStatus: mocks.getConsentStatus,
  acceptConsent: mocks.acceptConsent,
}));

vi.mock("@/lib/phr-onboarding", () => ({
  getPhrOnboarding: mocks.getPhrOnboarding,
  updatePhrOnboarding: mocks.updatePhrOnboarding,
}));

import OnboardingPage from "./page";

const dummyPhrOnboarding = {
  status: "pending",
  needs_onboarding: true,
  version: "2026-07-v1",
  completed_at: null,
  personalization_consent: false,
  optional_fields: ["full_name", "date_of_birth", "gender", "blood_type", "height_cm", "weight_kg"],
  record: {
    full_name: "",
    date_of_birth: null,
    gender: "",
    blood_type: "",
    height_cm: null,
    weight_kg: null,
    emergency_contact_name: "",
    emergency_contact_phone: "",
    allergies: [],
    conditions: [],
    medications: [],
  },
};

const dummyConsentStatus = {
  consent_type: "general_medical",
  required_version: "2026.1",
  accepted: false,
  accepted_version: null,
  accepted_at: null,
};

async function renderOnboardingPage() {
  const rendered = render(<OnboardingPage />);
  await waitFor(async () => {
    expect(mocks.getConsentStatus).toHaveBeenCalled();
    expect(mocks.getPhrOnboarding).toHaveBeenCalled();
    await Promise.all([
      mocks.getConsentStatus.mock.results[0]?.value,
      mocks.getPhrOnboarding.mock.results[0]?.value,
    ]);
  });
  return rendered;
}

describe("OnboardingPage — Multi-Track Decoupled Onboarding", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.setTestRole("normal");
    mocks.getConsentStatus.mockResolvedValue({ ...dummyConsentStatus });
    mocks.getPhrOnboarding.mockResolvedValue({ ...dummyPhrOnboarding });
    mocks.updatePhrOnboarding.mockResolvedValue({ ...dummyPhrOnboarding, status: "completed", needs_onboarding: false });
    mocks.acceptConsent.mockResolvedValue(undefined);
  });

  afterEach(() => {
    cleanup();
  });

  it("renders the 4 multi-track navigation tabs", async () => {
    await renderOnboardingPage();

    expect(screen.getByRole("tab", { name: /1\. Khởi động chung/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /2\. Hồ sơ sức khỏe/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /3\. Định hướng chuyên môn/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /4\. Đồng thuận công cụ/i })).toBeInTheDocument();
  });

  describe("Track 1: Global First Run", () => {
    it("renders medical disclaimer, privacy policy links, and versioned consent button", async () => {
      await renderOnboardingPage();

      // Switch to Global track
      fireEvent.click(screen.getByRole("tab", { name: /1\. Khởi động chung/i }));

      // Medical disclaimer is visible
      expect(screen.getByText(/Tuyên bố miễn trừ trách nhiệm y khoa/i)).toBeInTheDocument();
      expect(screen.getByText(/không phải là bác sĩ/i)).toBeInTheDocument();
      expect(screen.getByText(/Cấp cứu & Khẩn cấp/i)).toBeInTheDocument();

      // Privacy policy and legal links
      expect(screen.getByRole("link", { name: /Điều khoản dịch vụ/i })).toHaveAttribute("href", "/legal/terms");
      expect(screen.getByRole("link", { name: /Chính sách bảo mật/i })).toHaveAttribute("href", "/legal/privacy");
      expect(screen.getByRole("link", { name: /Văn bản đồng thuận y tế/i })).toHaveAttribute("href", "/legal/consent");

      // Versioned consent action
      const consentBtn = await screen.findByRole("button", { name: /Xác nhận đồng thuận/i });
      await waitFor(() => expect(consentBtn).not.toBeDisabled());

      fireEvent.click(consentBtn);
      await waitFor(() => {
        expect(mocks.acceptConsent).toHaveBeenCalledWith({
          consent_version: "2026.1",
          accepted: true,
        });
        expect(mocks.getConsentStatus).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe("Track 2: Personal Health Setup", () => {
    it("renders optional PHR biometric inputs and supports saving or skipping", async () => {
      await renderOnboardingPage();

      // Switch to Personal Health track
      fireEvent.click(screen.getByRole("tab", { name: /2\. Hồ sơ sức khỏe/i }));

      expect(screen.getByText(/Thiết lập Hồ sơ Sức khỏe Cá nhân \(Tùy chọn\)/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Họ và tên/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Chiều cao/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Cân nặng/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Nhóm máu/i)).toBeInTheDocument();

      // Enter optional biometrics
      fireEvent.change(screen.getByLabelText(/Họ và tên/i), { target: { value: "Trần Minh" } });
      fireEvent.change(screen.getByLabelText(/Chiều cao/i), { target: { value: "175" } });
      fireEvent.change(screen.getByLabelText(/Cân nặng/i), { target: { value: "68" } });
      fireEvent.change(screen.getByLabelText(/Nhóm máu/i), { target: { value: "O" } });

      // Save button disabled until self-declared checkbox is checked
      const saveBtn = screen.getByRole("button", { name: /Lưu và hoàn tất hồ sơ/i });
      expect(saveBtn).toBeDisabled();

      // Check self-declared confirmation
      const confirmCheckbox = screen.getByRole("checkbox", { name: /Tôi xác nhận các thông tin trên là do tôi tự nguyện cung cấp và tự khai/i });
      fireEvent.click(confirmCheckbox);
      expect(saveBtn).not.toBeDisabled();

      fireEvent.click(saveBtn);
      await waitFor(() => {
        expect(mocks.updatePhrOnboarding).toHaveBeenCalledWith(
          expect.objectContaining({
            action: "complete",
            confirm_self_declared: true,
            full_name: "Trần Minh",
            height_cm: 175,
            weight_kg: 68,
            blood_type: "O",
          }),
        );
        expect(mocks.replace).toHaveBeenCalledWith("/home");
      });
    });

    it("validates height and weight bounds before submitting personal profile", async () => {
      await renderOnboardingPage();

      fireEvent.click(screen.getByRole("tab", { name: /2\. Hồ sơ sức khỏe/i }));

      fireEvent.change(screen.getByLabelText(/Chiều cao/i), { target: { value: "350" } });
      const confirmCheckbox = screen.getByRole("checkbox", {
        name: /Tôi xác nhận các thông tin trên là do tôi tự nguyện cung cấp và tự khai/i,
      });
      fireEvent.click(confirmCheckbox);

      const saveBtn = screen.getByRole("button", { name: /Lưu và hoàn tất hồ sơ/i });
      fireEvent.click(saveBtn);

      expect(screen.getByText(/Chiều cao không hợp lệ\. Vui lòng nhập số từ 0 đến 300 cm\./i)).toBeInTheDocument();
      expect(mocks.updatePhrOnboarding).not.toHaveBeenCalled();
    });

    it("allows skipping personal health profile setup immediately", async () => {
      await renderOnboardingPage();

      fireEvent.click(screen.getByRole("tab", { name: /2\. Hồ sơ sức khỏe/i }));

      const skipBtn = screen.getByRole("button", { name: /Bỏ qua thiết lập hồ sơ/i });
      fireEvent.click(skipBtn);

      await waitFor(() => {
        expect(mocks.updatePhrOnboarding).toHaveBeenCalledWith({ action: "skip" });
        expect(mocks.replace).toHaveBeenCalledWith("/home");
      });
    });
  });

  describe("Track 3: Professional Orientation (Crucial Rule: Doctors not blocked by PHR)", () => {
    it("defaults to Professional Orientation for clinician/doctor role and contains zero PHR biometric fields", async () => {
      mocks.setTestRole("doctor");
      await renderOnboardingPage();

      // Should default to professional track for doctor
      expect(screen.getByTestId("track-professional")).toBeInTheDocument();
      expect(screen.getByText(/Không gian Làm việc Dành cho Bác sĩ & Nhà nghiên cứu/i)).toBeInTheDocument();
      expect(screen.getByText(/không bị chặn bởi biểu mẫu sinh trắc học cá nhân/i)).toBeInTheDocument();

      // Explains Council, Scribe, Evidence, and Dashboard
      expect(screen.getByText(/Hội đồng Hội chẩn AI \(Council\)/i)).toBeInTheDocument();
      expect(screen.getByText(/Ghi chép Lâm sàng \(Scribe\)/i)).toBeInTheDocument();
      expect(screen.getByText(/Bằng chứng Sống & Y văn/i)).toBeInTheDocument();
      expect(screen.getByText(/Bảng Điều khiển Tổng quan/i)).toBeInTheDocument();

      // Professional judgment disclaimer
      expect(screen.getByText(/Nguyên tắc Bác sĩ là Trung tâm Quyết định/i)).toBeInTheDocument();

      // Direct tool links exist
      expect(screen.getByRole("link", { name: /Đến Hội đồng Hội chẩn/i })).toHaveAttribute("href", "/council");
      expect(screen.getByRole("link", { name: /Đến Ghi chép Scribe/i })).toHaveAttribute("href", "/scribe");
      expect(screen.getByRole("link", { name: /Đến Tra cứu Chat Y khoa/i })).toHaveAttribute("href", "/chat");

      // Verify no biometric questions in professional orientation
      expect(screen.queryByLabelText(/Chiều cao/i)).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/Cân nặng/i)).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/Nhóm máu/i)).not.toBeInTheDocument();

      // Doctor can click to enter professional workspace directly
      const enterBtn = screen.getByRole("button", { name: /Vào Không gian Chuyên môn/i });
      fireEvent.click(enterBtn);
      expect(mocks.replace).toHaveBeenCalledWith("/dashboard");
    });
  });

  describe("Track 4: Tool-Specific Consent", () => {
    it("renders contextual consent architecture info for Scribe, CareGuard, and Family sharing", async () => {
      await renderOnboardingPage();

      // Switch to Tool Consent track
      fireEvent.click(screen.getByRole("tab", { name: /4\. Đồng thuận công cụ/i }));

      expect(screen.getByTestId("track-tools")).toBeInTheDocument();
      expect(screen.getByText(/Đồng thuận theo Ngữ cảnh cho Công cụ/i)).toBeInTheDocument();
      expect(screen.getByText(/Đồng thuận Ghi âm Scribe/i)).toBeInTheDocument();
      expect(screen.getByText(/Đồng thuận Kiểm tra Thuốc & DDI/i)).toBeInTheDocument();
      expect(screen.getByText(/Đồng thuận Chia sẻ Hồ sơ & Gia đình/i)).toBeInTheDocument();

      const completeBtn = screen.getByRole("button", { name: /Hoàn tất & Bắt đầu sử dụng/i });
      fireEvent.click(completeBtn);
      expect(mocks.replace).toHaveBeenCalledWith("/home");
    });
  });
});
