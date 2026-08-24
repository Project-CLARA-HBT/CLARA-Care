import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import LivingEvidencePage from "./page";
import { getRole } from "@/lib/auth-store";
import {
  createEvidenceQuestion,
  confirmEvidenceQuestion,
  deleteEvidenceSubscription,
  getEvidenceDetails,
  listEvidenceChangeNotifications,
  listEvidenceSubscriptions,
  markEvidenceChangeNotificationRead,
  runEvidenceQuestion,
  subscribeToEvidenceRun,
  updateEvidenceSubscription,
} from "@/lib/living-evidence";
import { getLifeMapToday } from "@/lib/lifemap";

const mockReplace = vi.fn();
const mockPush = vi.fn();
const mockRouter = {
  replace: mockReplace,
  push: mockPush,
};

vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
}));

vi.mock("@/lib/use-ui-language", () => ({
  useUILanguage: () => "vi",
}));

vi.mock("@/lib/auth-store", () => ({
  getRole: vi.fn(() => "doctor"),
}));

vi.mock("@/lib/lifemap", () => ({
  getLifeMapToday: vi.fn(),
}));

vi.mock("@/lib/living-evidence", () => ({
  getEvidenceDetails: vi.fn(),
  createEvidenceQuestion: vi.fn(),
  confirmEvidenceQuestion: vi.fn(),
  runEvidenceQuestion: vi.fn(),
  pollEvidenceRun: vi.fn(),
  isEvidenceRunTerminal: vi.fn((run) => run.status.toLowerCase() === "completed"),
  listEvidenceSubscriptions: vi.fn(),
  deleteEvidenceSubscription: vi.fn(),
  subscribeToEvidenceRun: vi.fn(),
  updateEvidenceSubscription: vi.fn(),
  listEvidenceChangeNotifications: vi.fn(),
  markEvidenceChangeNotificationRead: vi.fn(),
}));

const mockEpisode = {
  id: "ep-1",
  title: "Theo dõi Tăng huyết áp & Đái tháo đường",
  condition: "Hypertension",
  status: "active" as const,
  started_at: "2026-01-01",
};

const mockQuestion = {
  id: "q-101",
  episode_id: "ep-1",
  question: "Hiệu quả của SGLT2i trên bệnh nhân suy tim có phân suất tống máu bảo tồn?",
  confirmed: false,
  requires_confirmation: false,
  compiled: {
    missing_dimensions: [],
  },
};

const mockRun = {
  id: "run-202",
  evidence_question_id: "q-101",
  status: "completed",
  release_status: "evidence_available",
  evidence_count: 3,
  source_class_counts: { guideline: 1 },
  safe_message: "Đã tổng hợp 3 nguồn y văn lâm sàng đã được thẩm định.",
  uncertainty: [
    { dimension: "Cỡ mẫu", status: "low", reason: "Cần thêm dữ liệu thử nghiệm pha 3 đa trung tâm" },
  ],
  completed_at: "2026-08-24T10:05:00Z",
};

const mockMatrix = {
  run_id: "run-202",
  release_status: "evidence_available",
  unavailable_reason: null,
  source_classes: {
    guideline: [
      {
        evidence_id: "ev-1",
        title: "Khuyến cáo điều trị Suy tim ESC 2023",
        provider: "ESC Guidelines",
        source_class: "guideline",
        study_design: "Clinical Guideline",
        published_at: "2023",
        url: "https://example.org/esc-2023",
        identifiers: { doi: "10.1093/eurheartj/ehad195" },
        excerpt: "SGLT2 inhibitors are recommended in patients with HFpEF to reduce HF hospitalization.",
      },
    ],
  },
};

const mockApplicability = {
  status: "matched",
  matches: ["adult"],
  mismatches: [],
  critical_exclusions: [],
  safe_message: "Bằng chứng phù hợp cao với đối tượng bệnh nhân trưởng thành có eGFR > 25 ml/phút.",
  unknowns: [],
};

const mockContradictions = {
  status: "none",
  safe_message: "Không ghi nhận mâu thuẫn lớn giữa các khuyến cáo hiện hành.",
  items: [],
};

const mockNotification = {
  id: "notif-1",
  status: "unread" as const,
  read_at: null,
  payload: {
    kind: "update",
    assessment_id: "a-1",
    message: "Có 2 bài báo mới cập nhật liên quan đến câu hỏi theo dõi SGLT2i.",
  },
  created_at: "2026-08-24T11:00:00Z",
};

describe("LivingEvidencePage (/evidence)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getRole).mockReturnValue("admin");
    vi.mocked(getLifeMapToday).mockResolvedValue({
      episodes: [mockEpisode],
      tasks: [],
      alerts: [],
      recent_vitals: [],
    } as any);
    vi.mocked(listEvidenceSubscriptions).mockResolvedValue([]);
    vi.mocked(listEvidenceChangeNotifications).mockResolvedValue([mockNotification]);
  });

  it("renders page header and question builder successfully for Admin role", async () => {
    vi.mocked(getRole).mockReturnValue("admin");
    render(<LivingEvidencePage />);

    await waitFor(() => {
      expect(screen.getByText("Bằng chứng đang cập nhật")).toBeInTheDocument();
    });

    expect(screen.getByText("Đặt câu hỏi theo hành trình")).toBeInTheDocument();
    expect(screen.getByText("Theo dõi Tăng huyết áp & Đái tháo đường")).toBeInTheDocument();
    expect(screen.getByText("Có 2 bài báo mới cập nhật liên quan đến câu hỏi theo dõi SGLT2i.")).toBeInTheDocument();
  });

  it("renders page without restriction for Doctor role", async () => {
    vi.mocked(getRole).mockReturnValue("doctor");
    render(<LivingEvidencePage />);

    await waitFor(() => {
      expect(screen.getByText("Bằng chứng đang cập nhật")).toBeInTheDocument();
    });
    expect(screen.getByText("Đặt câu hỏi theo hành trình")).toBeInTheDocument();
  });

  it("renders page without restriction for Researcher role", async () => {
    vi.mocked(getRole).mockReturnValue("researcher");
    render(<LivingEvidencePage />);

    await waitFor(() => {
      expect(screen.getByText("Bằng chứng đang cập nhật")).toBeInTheDocument();
    });
  });

  it("renders page without restriction for Normal (patient) role", async () => {
    vi.mocked(getRole).mockReturnValue("normal");
    render(<LivingEvidencePage />);

    await waitFor(() => {
      expect(screen.getByText("Bằng chứng đang cập nhật")).toBeInTheDocument();
    });
  });

  it("submits question, confirms, runs research, and displays evidence matrix & interpretation", async () => {
    vi.mocked(createEvidenceQuestion).mockResolvedValue(mockQuestion);
    vi.mocked(confirmEvidenceQuestion).mockResolvedValue({ ...mockQuestion, confirmed: true });
    vi.mocked(runEvidenceQuestion).mockResolvedValue(mockRun);
    vi.mocked(getEvidenceDetails).mockResolvedValue({
      matrix: mockMatrix,
      applicability: mockApplicability,
      contradictions: mockContradictions,
    });

    render(<LivingEvidencePage />);

    await waitFor(() => {
      expect(screen.getByText("Theo dõi Tăng huyết áp & Đái tháo đường")).toBeInTheDocument();
    });

    // Enter question text
    const questionInput = screen.getByLabelText(/Điều bạn muốn biết/i);
    fireEvent.change(questionInput, {
      target: { value: "Hiệu quả của SGLT2i trên bệnh nhân suy tim có phân suất tống máu bảo tồn?" },
    });

    // Save question
    const saveButton = screen.getByRole("button", { name: /Lưu để xem lại/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(createEvidenceQuestion).toHaveBeenCalledWith("ep-1", expect.objectContaining({
        question: "Hiệu quả của SGLT2i trên bệnh nhân suy tim có phân suất tống máu bảo tồn?",
      }));
    });

    // Confirm question
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Tôi đã kiểm tra câu hỏi/i })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: /Tôi đã kiểm tra câu hỏi/i }));

    await waitFor(() => {
      expect(confirmEvidenceQuestion).toHaveBeenCalledWith("q-101");
    });

    // Run evidence search
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Tìm bằng chứng/i })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: /Tìm bằng chứng/i }));

    await waitFor(() => {
      expect(runEvidenceQuestion).toHaveBeenCalledWith("q-101");
      expect(screen.getByText("Khuyến cáo điều trị Suy tim ESC 2023")).toBeInTheDocument();
    });

    expect(screen.getByText(/SGLT2 inhibitors are recommended in patients with HFpEF/i)).toBeInTheDocument();
    expect(screen.getByText(/Đã tổng hợp 3 nguồn y văn lâm sàng/i)).toBeInTheDocument();
    expect(screen.getByText(mockApplicability.safe_message)).toBeInTheDocument();
  });

  it("manages evidence subscription and allows interval updates", async () => {
    vi.mocked(createEvidenceQuestion).mockResolvedValue({ ...mockQuestion, confirmed: true });
    vi.mocked(runEvidenceQuestion).mockResolvedValue(mockRun);
    vi.mocked(getEvidenceDetails).mockResolvedValue({
      matrix: mockMatrix,
      applicability: mockApplicability,
      contradictions: mockContradictions,
    });
    vi.mocked(subscribeToEvidenceRun).mockResolvedValue({
      id: "sub-1",
      evidence_run_id: "run-202",
      delivery_channel: "email",
      interval_hours: 168,
      status: "active",
      next_check_at: "2026-08-25T10:00:00Z",
      last_checked_at: null,
      monitor_enabled: true,
    });
    vi.mocked(updateEvidenceSubscription).mockResolvedValue({
      id: "sub-1",
      evidence_run_id: "run-202",
      delivery_channel: "email",
      interval_hours: 720,
      status: "active",
      next_check_at: "2026-08-25T10:00:00Z",
      last_checked_at: null,
      monitor_enabled: true,
    });
    vi.mocked(deleteEvidenceSubscription).mockResolvedValue(undefined);

    render(<LivingEvidencePage />);

    await waitFor(() => {
      expect(screen.getByText("Theo dõi Tăng huyết áp & Đái tháo đường")).toBeInTheDocument();
    });

    // Set question and run
    const questionInput = screen.getByLabelText(/Điều bạn muốn biết/i);
    fireEvent.change(questionInput, { target: { value: "Hiệu quả SGLT2i?" } });
    fireEvent.click(screen.getByRole("button", { name: /Lưu để xem lại/i }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Tìm bằng chứng/i })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: /Tìm bằng chứng/i }));

    await waitFor(() => {
      expect(screen.getByText("Theo dõi thay đổi quan trọng")).toBeInTheDocument();
    });

    // Start subscription
    const startSubBtn = screen.getByRole("button", { name: /Theo dõi cập nhật quan trọng/i });
    fireEvent.click(startSubBtn);

    await waitFor(() => {
      expect(subscribeToEvidenceRun).toHaveBeenCalledWith("run-202", 168);
    });

    // Change interval to monthly
    const intervalSelect = screen.getByLabelText(/Tần suất kiểm tra/i);
    fireEvent.change(intervalSelect, { target: { value: "720" } });

    await waitFor(() => {
      expect(updateEvidenceSubscription).toHaveBeenCalledWith("sub-1", 720);
    });

    // Stop subscription
    const stopSubBtn = screen.getByRole("button", { name: /Dừng theo dõi cập nhật/i });
    fireEvent.click(stopSubBtn);

    await waitFor(() => {
      expect(deleteEvidenceSubscription).toHaveBeenCalledWith("sub-1");
    });
  });

  it("marks notification as read", async () => {
    vi.mocked(markEvidenceChangeNotificationRead).mockResolvedValue(undefined);
    render(<LivingEvidencePage />);

    await waitFor(() => {
      expect(screen.getByText("Đánh dấu đã đọc")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Đánh dấu đã đọc"));

    await waitFor(() => {
      expect(markEvidenceChangeNotificationRead).toHaveBeenCalledWith("notif-1");
    });
  });
});
