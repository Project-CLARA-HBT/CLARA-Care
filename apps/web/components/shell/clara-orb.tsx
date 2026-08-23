"use client";

import {
  forwardRef,
  useCallback,
  useMemo,
  type ButtonHTMLAttributes,
  type KeyboardEvent,
} from "react";
import type { ClaraOrbState } from "./shell-mode-provider";

export interface ClaraOrbProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  state?: ClaraOrbState;
  size?: "sm" | "md" | "lg" | "xl";
  interactive?: boolean;
  label?: string;
  showTooltip?: boolean;
  pulseEffect?: boolean;
  className?: string;
}

const STATE_CONFIG: Record<
  ClaraOrbState,
  {
    labelVi: string;
    labelEn: string;
    description: string;
    coreGradient: string;
    glowColor: string;
    ringColor: string;
    accentColor: string;
    pulseSpeed: string;
  }
> = {
  idle: {
    labelVi: "CLARA Trực tuyến",
    labelEn: "CLARA Online",
    description: "Sẵn sàng hỗ trợ bạn",
    coreGradient: "from-[#0053db] via-[#1a68f0] to-[#a4c9ff]",
    glowColor: "rgba(164, 201, 255, 0.28)",
    ringColor: "border-[#a4c9ff]/40",
    accentColor: "#a4c9ff",
    pulseSpeed: "animate-pulse",
  },
  hover: {
    labelVi: "Hỏi CLARA",
    labelEn: "Ask CLARA",
    description: "Nhấn để bắt đầu cuộc trò chuyện",
    coreGradient: "from-[#003ea8] via-[#0053db] to-[#cdd7ff]",
    glowColor: "rgba(164, 201, 255, 0.48)",
    ringColor: "border-[#cdd7ff]/60",
    accentColor: "#cdd7ff",
    pulseSpeed: "animate-pulse",
  },
  listening: {
    labelVi: "Đang lắng nghe...",
    labelEn: "Listening...",
    description: "CLARA đang tiếp nhận giọng nói hoặc chỉ dẫn của bạn",
    coreGradient: "from-[#0053db] via-[#2dd4bf] to-[#a4c9ff]",
    glowColor: "rgba(45, 212, 191, 0.42)",
    ringColor: "border-[#2dd4bf]/70",
    accentColor: "#2dd4bf",
    pulseSpeed: "animate-ping",
  },
  processing: {
    labelVi: "Đang xử lý...",
    labelEn: "Processing...",
    description: "CLARA đang tra cứu y khoa & đối chiếu bằng chứng",
    coreGradient: "from-[#002a78] via-[#0053db] to-[#a4c9ff]",
    glowColor: "rgba(164, 201, 255, 0.38)",
    ringColor: "border-[#a4c9ff]/50",
    accentColor: "#a4c9ff",
    pulseSpeed: "animate-spin",
  },
  ready: {
    labelVi: "Đã có kết quả",
    labelEn: "Ready",
    description: "Câu trả lời y khoa an toàn đã sẵn sàng",
    coreGradient: "from-[#0053db] via-[#38bdf8] to-[#bae6fd]",
    glowColor: "rgba(56, 189, 248, 0.45)",
    ringColor: "border-[#38bdf8]/60",
    accentColor: "#38bdf8",
    pulseSpeed: "animate-pulse",
  },
  attention: {
    labelVi: "Cần chú ý an toàn",
    labelEn: "Attention Required",
    description: "Có cảnh báo tương tác thuốc hoặc phân loại y tế",
    coreGradient: "from-[#9a6700] via-[#fabd34] to-[#fef08a]",
    glowColor: "rgba(250, 189, 52, 0.45)",
    ringColor: "border-[#fabd34]/70",
    accentColor: "#fabd34",
    pulseSpeed: "animate-pulse",
  },
  error: {
    labelVi: "Giới hạn an toàn",
    labelEn: "Safety Boundary",
    description: "Yêu cầu nằm ngoài phạm vi hoặc gặp lỗi kết nối",
    coreGradient: "from-[#93000a] via-[#dc2626] to-[#ffb4ab]",
    glowColor: "rgba(255, 180, 171, 0.42)",
    ringColor: "border-[#ffb4ab]/60",
    accentColor: "#ffb4ab",
    pulseSpeed: "animate-pulse",
  },
};

const SIZE_CLASSES = {
  sm: {
    container: "h-8 w-8 min-w-[32px] min-h-[32px]",
    core: "h-5 w-5",
    orbit: "h-7 w-7",
    indicator: "h-1.5 w-1.5",
  },
  md: {
    container: "h-11 w-11 min-w-[44px] min-h-[44px]",
    core: "h-7 w-7",
    orbit: "h-10 w-10",
    indicator: "h-2 w-2",
  },
  lg: {
    container: "h-14 w-14 min-w-[56px] min-h-[56px]",
    core: "h-9 w-9",
    orbit: "h-12 w-12",
    indicator: "h-2.5 w-2.5",
  },
  xl: {
    container: "h-[4.5rem] w-[4.5rem] min-w-[72px] min-h-[72px]",
    core: "h-12 w-12",
    orbit: "h-16 w-16",
    indicator: "h-3 w-3",
  },
};

export const ClaraOrb = forwardRef<HTMLButtonElement, ClaraOrbProps>(
  function ClaraOrb(
    {
      state = "idle",
      size = "md",
      interactive = true,
      label,
      showTooltip = true,
      pulseEffect = true,
      className = "",
      onClick,
      onKeyDown,
      ...buttonProps
    },
    ref,
  ) {
    const config = STATE_CONFIG[state] ?? STATE_CONFIG.idle;
    const sizeConfig = SIZE_CLASSES[size] ?? SIZE_CLASSES.md;

    const accessibleLabel = label ?? `${config.labelVi} — ${config.description}`;

    const handleKeyDown = useCallback(
      (event: KeyboardEvent<HTMLButtonElement>) => {
        if (onKeyDown) {
          onKeyDown(event);
        }
        if (interactive && (event.key === "Enter" || event.key === " ")) {
          event.preventDefault();
          onClick?.(event as unknown as React.MouseEvent<HTMLButtonElement>);
        }
      },
      [interactive, onClick, onKeyDown],
    );

    const orbContent = useMemo(
      () => (
        <span className="relative flex h-full w-full items-center justify-center pointer-events-none">
          {/* Outer Ambient Glow Aura */}
          <span
            className={[
              "absolute inset-0 rounded-full blur-md transition-all duration-500 ease-out",
              pulseEffect ? "motion-safe:animate-pulse" : "",
            ].join(" ")}
            style={{
              backgroundColor: config.glowColor,
              opacity: state === "listening" || state === "attention" ? 0.9 : 0.65,
            }}
            aria-hidden="true"
          />

          {/* Listening concentric soundwave ring */}
          {state === "listening" && (
            <span
              className="absolute inset-0 rounded-full border border-teal-300/60 motion-safe:animate-ping opacity-75 pointer-events-none"
              aria-hidden="true"
            />
          )}

          {/* Processing Orbital Spinning Ring */}
          {state === "processing" && (
            <span
              className="absolute inset-0.5 rounded-full border-2 border-transparent border-t-[#a4c9ff] border-r-[#0053db] motion-safe:animate-spin pointer-events-none"
              style={{ animationDuration: "1.2s" }}
              aria-hidden="true"
            />
          )}

          {/* Outer Structural Ring with Glass Border */}
          <span
            className={[
              "absolute inset-1 rounded-full border backdrop-blur-sm transition-all duration-300 pointer-events-none",
              config.ringColor,
            ].join(" ")}
            style={{
              backgroundColor: "rgba(16, 20, 25, 0.45)",
            }}
            aria-hidden="true"
          />

          {/* Core Radiant Gradient Node */}
          <span
            className={[
              "relative z-10 rounded-full bg-gradient-to-tr shadow-inner transition-transform duration-300",
              sizeConfig.core,
              config.coreGradient,
              state === "hover" ? "scale-110" : "scale-100",
            ].join(" ")}
            aria-hidden="true"
          >
            {/* Center Luminous Spark Highlight */}
            <span
              className="absolute top-1 left-1.5 h-1.5 w-1.5 rounded-full bg-white/70 blur-[0.5px]"
              aria-hidden="true"
            />

            {/* Inner dynamic indicator for Attention or Error */}
            {state === "attention" && (
              <span
                className="absolute inset-0 flex items-center justify-center font-bold text-[10px] text-amber-950"
                aria-hidden="true"
              >
                !
              </span>
            )}
            {state === "error" && (
              <span
                className="absolute inset-0 flex items-center justify-center font-bold text-[10px] text-white"
                aria-hidden="true"
              >
                ×
              </span>
            )}
          </span>

          {/* Accessibility Status Description for Screen Readers */}
          <span className="sr-only" aria-live="polite">
            {accessibleLabel}
          </span>
        </span>
      ),
      [
        config.coreGradient,
        config.glowColor,
        config.ringColor,
        pulseEffect,
        sizeConfig.core,
        state,
        accessibleLabel,
      ],
    );

    if (!interactive) {
      return (
        <div
          className={[
            "relative inline-flex items-center justify-center select-none",
            sizeConfig.container,
            className,
          ].join(" ")}
          role="status"
          aria-label={accessibleLabel}
          title={showTooltip ? accessibleLabel : undefined}
        >
          {orbContent}
        </div>
      );
    }

    return (
      <button
        ref={ref}
        type="button"
        className={[
          "group relative inline-flex items-center justify-center rounded-full p-0.5 transition-all duration-300",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-500)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-canvas)]",
          "hover:scale-105 active:scale-95 cursor-pointer touch-manipulation",
          sizeConfig.container,
          className,
        ].join(" ")}
        role="button"
        aria-label={accessibleLabel}
        title={showTooltip ? accessibleLabel : undefined}
        onClick={onClick}
        onKeyDown={handleKeyDown}
        {...buttonProps}
      >
        {orbContent}
      </button>
    );
  },
);

export default ClaraOrb;
