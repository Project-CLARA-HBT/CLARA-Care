"use client";

import React, { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import Button from "@/components/ui/button";
import Badge from "@/components/ui/badge";
import Icon from "@/components/ui/icon";

const FOCUSABLE_SELECTOR =
  'a[href],button:not([disabled]),textarea:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])';

export interface LifeMapGuideModalProps {
  open: boolean;
  onClose: () => void;
  onStartExperience?: () => void;
  initialStep?: number;
  className?: string;
}

export type LifemapGuideModalProps = LifeMapGuideModalProps;

interface StepContent {
  id: string;
  number: number;
  title: string;
  shortTitle: string;
  tagline: string;
  summary: string;
  badge: string;
  badgeTone: "brand" | "ok" | "warn" | "neutral";
  highlights: Array<{
    icon: "clinical-notes" | "medication" | "progress" | "scan" | "check" | "warning" | "calendar";
    title: string;
    text: string;
  }>;
}

const TUTORIAL_STEPS: StepContent[] = [
  {
    id: "step-timeline",
    number: 1,
    title: "Bước 1: Dòng thời gian liên tục",
    shortTitle: "Dòng thời gian",
    tagline: "Bức tranh sức khỏe toàn diện theo thời gian thực",
    summary:
      "Hiểu cách LifeMap kết nối toàn bộ đơn thuốc, xét nghiệm và lần khám thành một bức tranh toàn diện.",
    badge: "Longitudinal Continuum",
    badgeTone: "brand",
    highlights: [
      {
        icon: "progress",
        title: "Xâu chuỗi đa nguồn tự động",
        text: "Tập hợp đơn thuốc, hình ảnh cận lâm sàng và ghi chú khám vào một trục thời gian duy nhất.",
      },
      {
        icon: "medication",
        title: "Mối liên kết nhân quả (Causal Linkage)",
        text: "Theo dõi rõ sự thay đổi của các chỉ số sinh tồn và triệu chứng sau khi điều chỉnh phác đồ thuốc.",
      },
      {
        icon: "check",
        title: "Bảo chứng dữ liệu FIDES",
        text: "Mỗi mốc sự kiện đều gắn liền với nguồn trích xuất gốc có thể kiểm chứng độc lập.",
      },
    ],
  },
  {
    id: "step-prep",
    number: 2,
    title: "Bước 2: Chuẩn bị đi khám bác sĩ",
    shortTitle: "Chuẩn bị đi khám",
    tagline: "Nắm bắt bệnh sử trong 30 giây",
    summary:
      "Cách tạo bản tóm tắt 1 trang giúp bác sĩ nắm bắt bệnh sử trong 30 giây.",
    badge: "1-Page Visit Summary",
    badgeTone: "ok",
    highlights: [
      {
        icon: "clinical-notes",
        title: "Bản tóm tắt lâm sàng 1 trang",
        text: "Cô đọng lý do khám, diễn tiến bệnh gần nhất và các cảnh báo nguy cơ quan trọng.",
      },
      {
        icon: "medication",
        title: "Rà soát thuốc & Tiền sử dị ứng",
        text: "Cung cấp danh mục thuốc đang sử dụng để bác sĩ tránh chỉ định trùng lặp hoặc tương tác thuốc (DDI).",
      },
      {
        icon: "scan",
        title: "Gợi ý câu hỏi thông minh",
        text: "Gợi ý sẵn những thắc mắc cốt lõi giúp bạn trao đổi tự tin và đúng trọng tâm với bác sĩ.",
      },
    ],
  },
  {
    id: "step-bitemporal",
    number: 3,
    title: "Bước 3: Đối chiếu 2 dòng thời gian (Bitemporal)",
    shortTitle: "Đối chiếu Bitemporal",
    tagline: "Chính xác thời điểm khởi phát để ngăn ngừa sai sót y khoa",
    summary:
      "Phân biệt thời gian triệu chứng bắt đầu và thời gian ghi vào hồ sơ để tránh sai sót y khoa.",
    badge: "Bitemporal Modeling",
    badgeTone: "warn",
    highlights: [
      {
        icon: "progress",
        title: "Thời gian thực tế (Valid Time)",
        text: "Thời điểm cơn đau, triệu chứng sốt hoặc việc uống thuốc thực sự diễn ra trong đời sống.",
      },
      {
        icon: "calendar",
        title: "Thời gian ghi nhận (Recorded Time)",
        text: "Thời điểm thông tin được người dùng hoặc bác sĩ nhập vào hệ thống hồ sơ y tế.",
      },
      {
        icon: "warning",
        title: "Ngăn chặn sai lệch chẩn đoán",
        text: "Đảm bảo AI và bác sĩ nắm chính xác độ dài cơn bệnh thực tế thay vì nhầm với thời gian nhập viện.",
      },
    ],
  },
  {
    id: "step-glhs",
    number: 4,
    title: "Bước 4: Cam kết an toàn GLHS",
    shortTitle: "An toàn GLHS",
    tagline: "Bảo vệ bất biến, minh bạch và thuộc quyền sở hữu của bạn",
    summary:
      "Mọi thay đổi dữ liệu y tế được bảo vệ bằng mã hóa, không bao giờ tự ý thay đổi hoặc xóa bỏ lịch sử khám.",
    badge: "GLHS Immutability",
    badgeTone: "brand",
    highlights: [
      {
        icon: "check",
        title: "Sổ cái bất biến (Append-Only)",
        text: "Lịch sử khám không bị ghi đè hay xóa mờ; mọi chỉnh sửa đều tạo phiên bản mới có lưu vết.",
      },
      {
        icon: "clinical-notes",
        title: "Bảo mật & Mã hóa cấp y tế",
        text: "Dữ liệu được mã hóa đầu cuối với quy trình Zero-PII telemetry, tuân thủ luật khám chữa bệnh.",
      },
      {
        icon: "progress",
        title: "Quyền đối chiếu & Khiếu nại",
        text: "Minh bạch tuyệt đối cho phép người bệnh kiểm tra nguồn gốc và gửi yêu cầu rà soát khi cần.",
      },
    ],
  },
];

export function LifeMapGuideModal({
  open,
  onClose,
  onStartExperience,
  initialStep = 0,
  className = "",
}: LifeMapGuideModalProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  const modalId = useId();
  const titleId = `${modalId}-title`;
  const descriptionId = `${modalId}-desc`;

  const [currentStepIndex, setCurrentStepIndex] = useState(() => {
    return Math.max(0, Math.min(TUTORIAL_STEPS.length - 1, initialStep));
  });

  // Step-specific interactive states for diagrams
  const [activeTimelineNode, setActiveTimelineNode] = useState<number>(0);
  const [activePrepTab, setActivePrepTab] = useState<"summary" | "meds" | "questions">("summary");
  const [bitemporalPerspective, setBitemporalPerspective] = useState<"bitemporal" | "traditional">("bitemporal");
  const [isIntegrityVerified, setIsIntegrityVerified] = useState<boolean>(false);
  const [isVerifying, setIsVerifying] = useState<boolean>(false);

  // Sync initialStep when opening
  useEffect(() => {
    if (open) {
      setCurrentStepIndex(Math.max(0, Math.min(TUTORIAL_STEPS.length - 1, initialStep)));
      setIsIntegrityVerified(false);
      setIsVerifying(false);
    }
  }, [open, initialStep]);

  // Focus trap & Escape key handler
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }

      if (event.key !== "Tab") return;

      const panel = panelRef.current;
      if (!panel) return;

      const focusableElements = Array.from(
        panel.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
      ).filter((node) => node.offsetParent !== null || node === document.activeElement);

      if (focusableElements.length === 0) return;

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];
      const activeElement = document.activeElement as HTMLElement | null;

      if (event.shiftKey && activeElement === firstElement) {
        event.preventDefault();
        lastElement.focus();
      } else if (!event.shiftKey && activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
      }
    },
    [onClose],
  );

  useEffect(() => {
    if (!open) return;

    previouslyFocusedRef.current = document.activeElement as HTMLElement | null;
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", handleKeyDown);

    const focusTimer = window.setTimeout(() => {
      const panel = panelRef.current;
      const firstFocusable = panel?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR);
      (firstFocusable ?? panel)?.focus();
    }, 0);

    return () => {
      document.body.style.overflow = originalOverflow;
      document.removeEventListener("keydown", handleKeyDown);
      window.clearTimeout(focusTimer);
      previouslyFocusedRef.current?.focus?.();
    };
  }, [open, handleKeyDown]);

  const currentStep = useMemo(() => {
    return TUTORIAL_STEPS[currentStepIndex] || TUTORIAL_STEPS[0];
  }, [currentStepIndex]);

  const handleNext = () => {
    if (currentStepIndex < TUTORIAL_STEPS.length - 1) {
      setCurrentStepIndex((prev) => prev + 1);
    } else {
      handleComplete();
    }
  };

  const handlePrev = () => {
    if (currentStepIndex > 0) {
      setCurrentStepIndex((prev) => prev - 1);
    }
  };

  const handleComplete = () => {
    if (onStartExperience) {
      onStartExperience();
    }
    onClose();
  };

  const handleTriggerVerification = () => {
    setIsVerifying(true);
    window.setTimeout(() => {
      setIsVerifying(false);
      setIsIntegrityVerified(true);
    }, 500);
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[80] flex items-end justify-center p-0 sm:items-center sm:p-4"
      data-testid="lifemap-guide-modal"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-[rgba(16,20,25,0.8)]"
        aria-hidden="true"
        onClick={onClose}
      />

      {/* Modal Dialog Container */}
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        tabIndex={-1}
        className={`relative z-[1] flex max-h-[92vh] w-full max-w-4xl flex-col rounded-t-[var(--radius-xl)] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-2xl sm:rounded-[var(--radius-xl)] ${className}`}
      >
        {/* Modal Top Header */}
        <div className="flex items-center justify-between border-b border-[color:var(--shell-border)] px-5 py-4 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[var(--surface-brand-soft)] text-[var(--text-brand)] border border-[color:var(--brand-500)]/30">
              <Icon name="progress" size="1.25rem" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 id={titleId} className="text-base font-bold text-[var(--text-primary)] sm:text-lg">
                  Hướng dẫn sử dụng LifeMap
                </h2>
                <Badge tone="brand" className="hidden xs:inline-flex text-[11px]">
                  Cẩm nang
                </Badge>
              </div>
              <p id={descriptionId} className="text-xs text-[var(--text-secondary)]">
                Bản đồ hành trình sức khỏe và hồ sơ y tế liên tục CLARA
              </p>
            </div>
          </div>

          <Button
            variant="ghost"
            size="sm"
            icon="close"
            aria-label="Đóng hướng dẫn"
            onClick={onClose}
            className="!min-h-9 shrink-0 text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          />
        </div>

        {/* Step Stepper Navigation Tabs */}
        <div className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 px-4 py-2 sm:px-6">
          <nav aria-label="Các bước hướng dẫn LifeMap" className="w-full">
            <ol role="tablist" className="grid grid-cols-4 gap-1.5 sm:gap-3">
              {TUTORIAL_STEPS.map((step, idx) => {
                const isActive = idx === currentStepIndex;
                const isCompleted = idx < currentStepIndex;

                return (
                  <li key={step.id} role="presentation" className="relative">
                    <button
                      type="button"
                      role="tab"
                      id={`${modalId}-tab-${idx}`}
                      aria-selected={isActive}
                      aria-controls={`${modalId}-panel-${idx}`}
                      onClick={() => setCurrentStepIndex(idx)}
                      className={`group flex w-full flex-col items-center rounded-lg p-2 text-center transition-all sm:flex-row sm:items-center sm:gap-2 sm:p-2.5 sm:text-left focus-ring ${
                        isActive
                          ? "bg-[var(--surface-panel)] text-[var(--text-primary)] border border-[color:var(--brand-500)]/40 shadow-xs"
                          : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
                      }`}
                    >
                      <span
                        className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold transition-all ${
                          isActive
                            ? "bg-[var(--brand-600)] text-white shadow-xs"
                            : isCompleted
                            ? "bg-[var(--status-ok-bg)] text-[var(--status-ok-text)] border border-[color:var(--status-ok-border)]"
                            : "bg-[var(--surface-muted)] text-[var(--text-muted)] border border-[color:var(--shell-border)]"
                        }`}
                      >
                        {isCompleted ? "✓" : step.number}
                      </span>
                      <div className="hidden min-w-0 flex-1 sm:block">
                        <div className="text-xs font-semibold truncate leading-tight">
                          {step.shortTitle}
                        </div>
                        <div className="text-[10px] text-[var(--text-secondary)] truncate">
                          Bước {step.number}
                        </div>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ol>
          </nav>
        </div>

        {/* Modal Scrollable Body */}
        <div
          id={`${modalId}-panel-${currentStepIndex}`}
          role="tabpanel"
          aria-labelledby={`${modalId}-tab-${currentStepIndex}`}
          className="flex-1 overflow-y-auto px-5 py-5 sm:px-8 sm:py-6 space-y-6"
        >
          {/* Step Header Banner */}
          <div className="flex flex-col gap-2 rounded-xl bg-[var(--surface-muted)]/60 border border-[color:var(--shell-border)] p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Badge tone={currentStep.badgeTone} className="text-xs font-semibold">
                  {currentStep.badge}
                </Badge>
                <span className="text-xs text-[var(--text-secondary)]">
                  Bước {currentStepIndex + 1} / {TUTORIAL_STEPS.length}
                </span>
              </div>
              <h3 className="text-lg font-bold text-[var(--text-primary)] leading-tight">
                {currentStep.title}
              </h3>
              <p className="text-sm text-[var(--text-secondary)]">
                {currentStep.summary}
              </p>
            </div>
            <div className="shrink-0 pt-2 sm:pt-0">
              <button
                type="button"
                onClick={handleComplete}
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--text-brand)] hover:underline"
              >
                Bỏ qua và bắt đầu
                <Icon name="arrow-right" size="0.9rem" />
              </button>
            </div>
          </div>

          {/* Interactive Visual Illustration / Diagram per step */}
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5">
            {/* STEP 1: Dòng thời gian liên tục */}
            {currentStepIndex === 0 && (
              <div className="space-y-4" data-testid="step-1-diagram">
                <div className="flex items-center justify-between">
                  <div className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                    Sơ đồ kết nối chuỗi sự kiện lâm sàng (Interactive Timeline)
                  </div>
                  <Badge tone="ok" icon="check" className="text-[11px]">
                    FIDES Đã xác thực
                  </Badge>
                </div>

                {/* Interactive Continuum Nodes */}
                <div className="relative py-2">
                  <div
                    aria-hidden="true"
                    className="absolute left-6 top-8 bottom-8 w-0.5 bg-gradient-to-b from-[var(--brand-600)] via-[#6941C6] to-[#14A88D] hidden sm:block sm:left-0 sm:right-0 sm:top-1/2 sm:bottom-auto sm:h-0.5 sm:w-full sm:-translate-y-1/2 sm:bg-gradient-to-r"
                  />
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 sm:gap-4 relative z-10">
                    {/* Node 1: Đơn thuốc */}
                    <button
                      type="button"
                      onClick={() => setActiveTimelineNode(0)}
                      className={`text-left rounded-xl p-3.5 transition-all border ${
                        activeTimelineNode === 0
                          ? "bg-[var(--surface-panel)] border-[color:var(--brand-500)] shadow-md ring-2 ring-[var(--brand-500)]/30"
                          : "bg-[var(--surface-panel)]/80 border-[color:var(--shell-border)] hover:border-[color:var(--shell-border-strong)]"
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-rose-500/10 text-rose-400 border border-rose-500/30">
                          <Icon name="medication" size="1rem" />
                        </span>
                        <div>
                          <div className="text-xs font-bold text-[var(--text-primary)]">
                            1. Đơn thuốc
                          </div>
                          <div className="text-[10px] text-[var(--text-secondary)]">
                            15/05/2026
                          </div>
                        </div>
                      </div>
                      <div className="text-xs font-medium text-[var(--text-primary)]">
                        Amlodipine 5mg
                      </div>
                      <div className="text-[11px] text-[var(--text-secondary)] mt-1 line-clamp-2">
                        Bắt đầu điều trị tăng huyết áp vô căn.
                      </div>
                    </button>

                    {/* Node 2: Xét nghiệm */}
                    <button
                      type="button"
                      onClick={() => setActiveTimelineNode(1)}
                      className={`text-left rounded-xl p-3.5 transition-all border ${
                        activeTimelineNode === 1
                          ? "bg-[var(--surface-panel)] border-[color:var(--brand-500)] shadow-md ring-2 ring-[var(--brand-500)]/30"
                          : "bg-[var(--surface-panel)]/80 border-[color:var(--shell-border)] hover:border-[color:var(--shell-border-strong)]"
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/30">
                          <Icon name="scan" size="1rem" />
                        </span>
                        <div>
                          <div className="text-xs font-bold text-[var(--text-primary)]">
                            2. Xét nghiệm
                          </div>
                          <div className="text-[10px] text-[var(--text-secondary)]">
                            01/06/2026
                          </div>
                        </div>
                      </div>
                      <div className="text-xs font-medium text-[var(--text-primary)]">
                        Sinh hóa máu & Chức năng thận
                      </div>
                      <div className="text-[11px] text-[var(--text-secondary)] mt-1 line-clamp-2">
                        eGFR 92 mL/min • Điện giải đồ ổn định.
                      </div>
                    </button>

                    {/* Node 3: Tái khám */}
                    <button
                      type="button"
                      onClick={() => setActiveTimelineNode(2)}
                      className={`text-left rounded-xl p-3.5 transition-all border ${
                        activeTimelineNode === 2
                          ? "bg-[var(--surface-panel)] border-[color:var(--brand-500)] shadow-md ring-2 ring-[var(--brand-500)]/30"
                          : "bg-[var(--surface-panel)]/80 border-[color:var(--shell-border)] hover:border-[color:var(--shell-border-strong)]"
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                          <Icon name="clinical-notes" size="1rem" />
                        </span>
                        <div>
                          <div className="text-xs font-bold text-[var(--text-primary)]">
                            3. Tái khám lâm sàng
                          </div>
                          <div className="text-[10px] text-[var(--text-secondary)]">
                            Hôm nay (Liên tục)
                          </div>
                        </div>
                      </div>
                      <div className="text-xs font-medium text-[var(--text-primary)]">
                        Huyết áp 120/80 mmHg
                      </div>
                      <div className="text-[11px] text-[var(--text-secondary)] mt-1 line-clamp-2">
                        Đáp ứng thuốc tích cực, tiếp tục duy trì liều.
                      </div>
                    </button>
                  </div>
                </div>

                {/* Node Detail Callout */}
                <div className="rounded-lg bg-[var(--surface-muted)] border border-[color:var(--brand-500)]/30 p-3 text-xs">
                  <div className="flex items-center gap-2 text-[var(--text-brand)] font-semibold mb-1">
                    <Icon name="progress" size="0.95rem" />
                    <span>
                      {activeTimelineNode === 0 && "Mốc 1: Khởi đầu điều trị dược lý"}
                      {activeTimelineNode === 1 && "Mốc 2: Đối chiếu cận lâm sàng theo dõi tác dụng phụ"}
                      {activeTimelineNode === 2 && "Mốc 3: Đánh giá hiệu quả lâm sàng toàn diện"}
                    </span>
                  </div>
                  <p className="text-[var(--text-secondary)]">
                    {activeTimelineNode === 0 &&
                      "Đơn thuốc được chuẩn hóa từ ảnh chụp đơn hoặc dữ liệu số, tự động tạo chu kỳ nhắc nhở và đối chiếu tương tác."}
                    {activeTimelineNode === 1 &&
                      "Kết quả xét nghiệm được gắn nhãn trực tiếp với đợt điều trị thuốc trước đó để xác minh chức năng lọc thận an toàn."}
                    {activeTimelineNode === 2 &&
                      "Hệ thống tự động liên kết dữ liệu đo huyết áp hàng ngày với đơn thuốc tháng 5 và xét nghiệm tháng 6 thành một chuỗi duy nhất."}
                  </p>
                </div>
              </div>
            )}

            {/* STEP 2: Chuẩn bị đi khám bác sĩ */}
            {currentStepIndex === 1 && (
              <div className="space-y-4" data-testid="step-2-diagram">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                    Mô phỏng bản tóm tắt khám bệnh 30 giây (1-Page Clinical Brief)
                  </div>
                  {/* Tab Selector */}
                  <div className="inline-flex rounded-lg bg-[var(--surface-panel)] p-0.5 border border-[color:var(--shell-border)]">
                    <button
                      type="button"
                      onClick={() => setActivePrepTab("summary")}
                      className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-all ${
                        activePrepTab === "summary"
                          ? "bg-[var(--brand-600)] text-white"
                          : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                      }`}
                    >
                      Bệnh sử
                    </button>
                    <button
                      type="button"
                      onClick={() => setActivePrepTab("meds")}
                      className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-all ${
                        activePrepTab === "meds"
                          ? "bg-[var(--brand-600)] text-white"
                          : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                      }`}
                    >
                      Thuốc & Dị ứng
                    </button>
                    <button
                      type="button"
                      onClick={() => setActivePrepTab("questions")}
                      className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-all ${
                        activePrepTab === "questions"
                          ? "bg-[var(--brand-600)] text-white"
                          : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                      }`}
                    >
                      Câu hỏi cho Bác sĩ
                    </button>
                  </div>
                </div>

                {/* 1-Page Summary Visual Mockup */}
                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 space-y-3">
                  <div className="flex items-center justify-between border-b border-[color:var(--shell-border)] pb-2.5">
                    <div className="flex items-center gap-2">
                      <Icon name="clinical-notes" size="1.1rem" className="text-[var(--text-brand)]" />
                      <span className="text-xs font-bold text-[var(--text-primary)]">
                        HỒ SƠ TÓM TẮT KHÁM BỆNH • BỆNH NHÂN TRẦN VĂN A (45T)
                      </span>
                    </div>
                    <Badge tone="ok" className="text-[10px]">
                      Sẵn sàng in / Xem nhanh
                    </Badge>
                  </div>

                  {activePrepTab === "summary" && (
                    <div className="space-y-2.5 text-xs">
                      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                        <div className="rounded-lg bg-[var(--surface-muted)] p-2.5 border border-[color:var(--shell-border)]">
                          <span className="text-[11px] font-semibold text-[var(--text-secondary)]">
                            Lý do khám chính (Chief Complaint)
                          </span>
                          <p className="mt-1 font-semibold text-[var(--text-primary)]">
                            Đau đầu vùng chẩm buổi sáng tái phát 3 ngày nay
                          </p>
                        </div>
                        <div className="rounded-lg bg-[var(--surface-muted)] p-2.5 border border-[color:var(--shell-border)]">
                          <span className="text-[11px] font-semibold text-[var(--text-secondary)]">
                            Chỉ số sinh tồn gần nhất
                          </span>
                          <p className="mt-1 font-semibold text-rose-400">
                            HA 145/92 mmHg • Mạch 78 bpm • SpO2 98%
                          </p>
                        </div>
                      </div>
                      <div className="rounded-lg bg-[var(--surface-muted)]/60 p-2.5 text-[var(--text-secondary)] border border-[color:var(--shell-border)]">
                        <span className="font-semibold text-[var(--text-primary)]">Diễn tiến bệnh:</span> Bệnh nhân có tiền sử tăng huyết áp 1 năm, đáp ứng tốt với Amlodipine nhưng gần đây có công việc căng thẳng và thiếu ngủ.
                      </div>
                    </div>
                  )}

                  {activePrepTab === "meds" && (
                    <div className="space-y-2 text-xs">
                      <div className="rounded-lg bg-[var(--surface-muted)] p-2.5 border border-[color:var(--shell-border)]">
                        <div className="font-semibold text-[var(--text-primary)] mb-1">
                          Đơn thuốc đang dùng hàng ngày:
                        </div>
                        <ul className="list-disc pl-4 space-y-1 text-[var(--text-secondary)]">
                          <li><strong className="text-[var(--text-primary)]">Amlodipine 5mg:</strong> 1 viên mỗi sáng sau ăn (Uống đều đặn).</li>
                          <li><strong className="text-[var(--text-primary)]">Vitamin C 500mg:</strong> 1 viên khi mệt mỏi.</li>
                        </ul>
                      </div>
                      <div className="rounded-lg bg-rose-500/10 border border-rose-500/30 p-2.5 text-rose-300">
                        <strong>Tiền sử dị ứng:</strong> Dị ứng Penicillin (Phát ban đỏ, ngứa ngáy năm 2021).
                      </div>
                    </div>
                  )}

                  {activePrepTab === "questions" && (
                    <div className="space-y-2 text-xs">
                      <div className="rounded-lg bg-[var(--surface-muted)] p-2.5 border border-[color:var(--shell-border)] space-y-1.5">
                        <div className="font-semibold text-[var(--text-brand)] flex items-center gap-1.5">
                          <Icon name="check" size="0.95rem" />
                          <span>3 câu hỏi gợi ý nên trao đổi với bác sĩ:</span>
                        </div>
                        <ol className="list-decimal pl-4 space-y-1 text-[var(--text-primary)]">
                          <li>Chỉ số huyết áp tăng gần đây có cần tăng liều hay phối hợp thêm thuốc không?</li>
                          <li>Cơn đau đầu buổi sáng có phải dấu hiệu tổn thương cơ quan đích không?</li>
                          <li>Tôi có cần làm thêm xét nghiệm điện giải đồ hoặc chức năng thận đợt này không?</li>
                        </ol>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* STEP 3: Đối chiếu 2 dòng thời gian (Bitemporal) */}
            {currentStepIndex === 2 && (
              <div className="space-y-4" data-testid="step-3-diagram">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                    Mô hình 2 trục thời gian (Bitemporal Axis Comparison)
                  </div>
                  <div className="inline-flex rounded-lg bg-[var(--surface-panel)] p-0.5 border border-[color:var(--shell-border)]">
                    <button
                      type="button"
                      onClick={() => setBitemporalPerspective("bitemporal")}
                      className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-all ${
                        bitemporalPerspective === "bitemporal"
                          ? "bg-[var(--brand-600)] text-white"
                          : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                      }`}
                    >
                      Bitemporal (CLARA)
                    </button>
                    <button
                      type="button"
                      onClick={() => setBitemporalPerspective("traditional")}
                      className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-all ${
                        bitemporalPerspective === "traditional"
                          ? "bg-amber-600 text-white"
                          : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                      }`}
                    >
                      Hồ sơ thường (Dễ sai lệch)
                    </button>
                  </div>
                </div>

                {/* Dual Track Visual */}
                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 space-y-4">
                  {/* Track 1: Valid Time (Thời gian thực tế) */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-bold text-[var(--text-brand)] flex items-center gap-1.5">
                        <Icon name="progress" size="0.95rem" />
                        Trục 1: Thời gian thực tế (Valid / Event Time)
                      </span>
                      <span className="text-[11px] text-[var(--text-secondary)]">
                        12/03 lúc 10:00 AM
                      </span>
                    </div>
                    <div className="relative flex items-center gap-3 rounded-lg bg-[var(--surface-muted)] p-3 border border-[color:var(--brand-500)]/40">
                      <div className="h-3 w-3 rounded-full bg-rose-500 animate-pulse shrink-0" />
                      <div className="text-xs">
                        <strong className="text-[var(--text-primary)]">Triệu chứng khởi phát:</strong> Cơn sốt cao 39°C và đau rát họng bắt đầu tại nhà.
                      </div>
                    </div>
                  </div>

                  {/* Connecting Gap Indicator */}
                  <div className="flex items-center gap-2 pl-4 text-[11px] text-amber-400 font-medium">
                    <div className="h-6 w-0.5 bg-amber-400/50" />
                    <span>Khoảng chênh lệch: +53.5 giờ (Thời gian di chuyển & chờ khám)</span>
                  </div>

                  {/* Track 2: Recorded Time (Thời gian ghi nhận) */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-bold text-[#14A88D] flex items-center gap-1.5">
                        <Icon name="calendar" size="0.95rem" />
                        Trục 2: Thời gian ghi nhận (Recorded / Transaction Time)
                      </span>
                      <span className="text-[11px] text-[var(--text-secondary)]">
                        14/03 lúc 03:30 PM
                      </span>
                    </div>
                    <div className="relative flex items-center gap-3 rounded-lg bg-[var(--surface-muted)] p-3 border border-[#14A88D]/40">
                      <div className="h-3 w-3 rounded-full bg-[#14A88D] shrink-0" />
                      <div className="text-xs">
                        <strong className="text-[var(--text-primary)]">Nhập vào hệ thống:</strong> Bác sĩ khám lâm sàng và lưu hồ sơ điện tử tại bệnh viện.
                      </div>
                    </div>
                  </div>

                  {/* Explanation Outcome */}
                  <div
                    className={`rounded-lg p-3 text-xs border ${
                      bitemporalPerspective === "bitemporal"
                        ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                        : "bg-amber-500/10 border-amber-500/30 text-amber-300"
                    }`}
                  >
                    {bitemporalPerspective === "bitemporal" ? (
                      <div>
                        <strong>Lợi ích Bitemporal của LifeMap:</strong> Bác sĩ và thuật toán nhận biết chính xác bệnh nhân đã sốt sang ngày thứ 3, từ đó chỉ định xét nghiệm công thức máu kiểm tra sốt xuất huyết kịp thời thay vì tưởng là ngày đầu tiên.
                      </div>
                    ) : (
                      <div>
                        <strong>Rủi ro ở hệ thống truyền thống:</strong> Hệ thống chỉ ghi nhận thời gian 14/03, làm bác sĩ tưởng cơn sốt mới bắt đầu vài giờ trước, dẫn đến đánh giá sai giai đoạn bệnh lý.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* STEP 4: Cam kết an toàn GLHS */}
            {currentStepIndex === 3 && (
              <div className="space-y-4" data-testid="step-4-diagram">
                <div className="flex items-center justify-between">
                  <div className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                    Cơ chế bảo vệ bất biến GLHS (Guaranteed Ledger Health Safety)
                  </div>
                  <Badge tone="brand" icon="check" className="text-[11px]">
                    Chuỗi khối bất biến
                  </Badge>
                </div>

                {/* Ledger & Security Visual */}
                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 space-y-3">
                  <div className="flex items-center justify-between border-b border-[color:var(--shell-border)] pb-2.5">
                    <div className="flex items-center gap-2">
                      <div className="flex h-6 w-6 items-center justify-center rounded-md bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
                        <Icon name="check" size="0.9rem" />
                      </div>
                      <span className="text-xs font-bold text-[var(--text-primary)]">
                        NHẬT KÝ PHIÊN BẢN HỒ SƠ Y TẾ BẤT BIẾN (APPEND-ONLY LEDGER)
                      </span>
                    </div>
                    <span className="text-[10px] text-[var(--text-secondary)] font-mono">
                      SHA256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4
                    </span>
                  </div>

                  {/* Versions Chain */}
                  <div className="space-y-2 text-xs">
                    <div className="flex items-center justify-between rounded-lg bg-[var(--surface-muted)] p-2.5 border border-[color:var(--shell-border)]">
                      <div className="flex items-center gap-2.5">
                        <span className="rounded bg-[var(--brand-600)] px-1.5 py-0.5 font-mono text-[10px] font-bold text-white">
                          v1.0
                        </span>
                        <div>
                          <div className="font-semibold text-[var(--text-primary)]">
                            Khởi tạo đơn thuốc ban đầu (Amlodipine 5mg)
                          </div>
                          <div className="text-[10px] text-[var(--text-secondary)]">
                            15/05/2026 08:30 • Nguồn: Đơn thuốc BV Bạch Mai
                          </div>
                        </div>
                      </div>
                      <Badge tone="ok" className="text-[10px]">
                        Khóa ghi nhận
                      </Badge>
                    </div>

                    <div className="flex items-center justify-between rounded-lg bg-[var(--surface-muted)] p-2.5 border border-[color:var(--shell-border)]">
                      <div className="flex items-center gap-2.5">
                        <span className="rounded bg-purple-600 px-1.5 py-0.5 font-mono text-[10px] font-bold text-white">
                          v2.0
                        </span>
                        <div>
                          <div className="font-semibold text-[var(--text-primary)]">
                            Cập nhật ghi chú đáp ứng thuốc & Bổ sung kết quả xét nghiệm
                          </div>
                          <div className="text-[10px] text-[var(--text-secondary)]">
                            01/06/2026 14:15 • Tạo bản ghi bổ sung (Không xóa v1.0)
                          </div>
                        </div>
                      </div>
                      <Badge tone="brand" className="text-[10px]">
                        Bản ghi mới
                      </Badge>
                    </div>
                  </div>

                  {/* Interactive Verification Test Action */}
                  <div className="pt-2 flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-[color:var(--shell-border)]">
                    <div className="text-xs text-[var(--text-secondary)]">
                      {isIntegrityVerified ? (
                        <span className="text-emerald-400 font-semibold flex items-center gap-1.5">
                          <Icon name="check" size="1rem" />
                          Hồ sơ đạt 100% tính toàn vẹn mã hóa • Không có chỉnh sửa ngầm.
                        </span>
                      ) : (
                        "Nhấn để kiểm tra đối chiếu chữ ký số và tính toàn vẹn hồ sơ:"
                      )}
                    </div>
                    <Button
                      variant={isIntegrityVerified ? "secondary" : "primary"}
                      size="sm"
                      loading={isVerifying}
                      onClick={handleTriggerVerification}
                      className="w-full sm:w-auto shrink-0"
                      icon={isIntegrityVerified ? "check" : "scan"}
                    >
                      {isIntegrityVerified ? "Đã xác thực toàn vẹn" : "Kiểm tra tính toàn vẹn"}
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Step 3 Pillars / Highlights Grid */}
          <div className="space-y-2">
            <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">
              Điểm cốt lõi cần nhớ trong bước này
            </h4>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {currentStep.highlights.map((h, i) => (
                <div
                  key={i}
                  className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-3.5 space-y-1.5 transition-all hover:bg-[var(--surface-muted)]"
                >
                  <div className="flex items-center gap-2">
                    <div className="flex h-6 w-6 items-center justify-center rounded-md bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
                      <Icon name={h.icon} size="0.9rem" />
                    </div>
                    <span className="text-xs font-bold text-[var(--text-primary)]">
                      {h.title}
                    </span>
                  </div>
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                    {h.text}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Modal Footer Controls */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-5 py-4 sm:px-6">
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              icon="arrow-left"
              disabled={currentStepIndex === 0}
              onClick={handlePrev}
              aria-label="Quay lại bước trước"
            >
              Quay lại
            </Button>
            <span className="text-xs text-[var(--text-secondary)] hidden xs:inline-block">
              Bước {currentStepIndex + 1} / {TUTORIAL_STEPS.length}
            </span>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2 sm:gap-3">
            {currentStepIndex < TUTORIAL_STEPS.length - 1 ? (
              <>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleComplete}
                  className="text-xs text-[var(--text-secondary)]"
                >
                  Bỏ qua
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  icon="arrow-right"
                  iconTrailing
                  onClick={handleNext}
                  aria-label="Tiếp tục sang bước tiếp theo"
                >
                  Tiếp tục
                </Button>
              </>
            ) : (
              <Button
                variant="primary"
                size="md"
                icon="check"
                onClick={handleComplete}
                className="bg-gradient-to-r from-[var(--brand-600)] to-[#14A88D] text-white shadow-lg font-bold"
                data-testid="start-experience-button"
              >
                Bắt đầu trải nghiệm ngay
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default LifeMapGuideModal;
