"use client";

import { useState, useRef, type FormEvent, type KeyboardEvent } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/ui/icon";

export type AskActionType = "text" | "camera" | "file" | "voice";

export interface AskBarProps {
  placeholder?: string;
  initialValue?: string;
  onSubmit?: (query: string, actionType?: AskActionType) => void;
  onCameraClick?: () => void;
  onFileClick?: () => void;
  onVoiceClick?: () => void;
  targetHref?: string;
  disabled?: boolean;
  locale?: "vi" | "en";
  variant?: "default" | "compact" | "hero";
  className?: string;
  autoFocus?: boolean;
}

export function AskBar({
  placeholder,
  initialValue = "",
  onSubmit,
  onCameraClick,
  onFileClick,
  onVoiceClick,
  targetHref = "/ask",
  disabled = false,
  locale = "vi",
  variant = "default",
  className = "",
  autoFocus = false,
}: AskBarProps) {
  const [query, setQuery] = useState(initialValue);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  const isEn = locale === "en";
  const defaultPlaceholder =
    placeholder ??
    (isEn
      ? "Ask CLARA about health, symptoms, medicines..."
      : "Hỏi CLARA về sức khỏe, triệu chứng, đơn thuốc...");

  const labels = {
    camera: isEn ? "Scan medicine label or test" : "Chụp ảnh nhãn thuốc hoặc kết quả",
    file: isEn ? "Attach health document" : "Đính kèm tệp hồ sơ y tế",
    voice: isEn ? "Voice input" : "Nói câu hỏi",
    send: isEn ? "Ask CLARA" : "Gửi câu hỏi",
  };

  const handleSend = (e?: FormEvent) => {
    if (e) e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed && !onSubmit) return;

    if (onSubmit) {
      onSubmit(trimmed, "text");
    } else if (targetHref) {
      const url = trimmed
        ? `${targetHref}?q=${encodeURIComponent(trimmed)}`
        : targetHref;
      router.push(url);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleAction = (type: AskActionType, customHandler?: () => void) => {
    if (customHandler) {
      customHandler();
      return;
    }
    if (onSubmit) {
      onSubmit(query.trim(), type);
      return;
    }
    if (targetHref) {
      const url = `${targetHref}?action=${type}${query.trim() ? `&q=${encodeURIComponent(query.trim())}` : ""}`;
      router.push(url);
    }
  };

  const isHero = variant === "hero";
  const isCompact = variant === "compact";

  return (
    <form
      onSubmit={handleSend}
      className={`relative flex items-center gap-1.5 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] transition-all duration-150 focus-within:border-[color:var(--brand-500)] focus-within:shadow-[0_0_0_2px_rgba(164,201,255,0.15)] ${
        isHero ? "p-2 sm:p-2.5 shadow-[var(--shadow-float)]" : isCompact ? "p-1" : "p-1.5"
      } ${className}`}
      data-testid="ask-bar"
    >
      <div className="pl-2.5 text-[var(--text-muted)]">
        <Icon name="search" size={isHero ? "1.25rem" : "1.1rem"} />
      </div>

      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={defaultPlaceholder}
        disabled={disabled}
        autoFocus={autoFocus}
        className="w-full min-w-0 flex-1 border-0 bg-transparent px-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-0 sm:text-base"
        aria-label={defaultPlaceholder}
        data-testid="ask-bar-input"
      />

      <div className="flex items-center gap-1 pr-1 shrink-0">
        <button
          type="button"
          onClick={() => handleAction("camera", onCameraClick)}
          disabled={disabled}
          title={labels.camera}
          aria-label={labels.camera}
          className="inline-flex h-9 w-9 items-center justify-center rounded-[var(--radius-md)] text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] disabled:opacity-40"
          data-testid="ask-bar-camera-button"
        >
          <Icon name="scan" size="1.15rem" />
        </button>

        <button
          type="button"
          onClick={() => handleAction("file", onFileClick)}
          disabled={disabled}
          title={labels.file}
          aria-label={labels.file}
          className="inline-flex h-9 w-9 items-center justify-center rounded-[var(--radius-md)] text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] disabled:opacity-40"
          data-testid="ask-bar-file-button"
        >
          <Icon name="folder" size="1.15rem" />
        </button>

        <button
          type="button"
          onClick={() => handleAction("voice", onVoiceClick)}
          disabled={disabled}
          title={labels.voice}
          aria-label={labels.voice}
          className="inline-flex h-9 w-9 items-center justify-center rounded-[var(--radius-md)] text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] disabled:opacity-40"
          data-testid="ask-bar-voice-button"
        >
          <Icon name="notifications" size="1.15rem" />
        </button>

        <button
          type="submit"
          disabled={disabled || !query.trim()}
          title={labels.send}
          aria-label={labels.send}
          className="inline-flex h-9 min-w-[2.25rem] items-center justify-center rounded-[var(--radius-md)] bg-[var(--brand-600)] px-3 text-sm font-semibold text-[var(--button-primary-text)] transition-colors hover:bg-[var(--brand-700)] disabled:cursor-not-allowed disabled:opacity-45"
          data-testid="ask-bar-submit-button"
        >
          <Icon name="send" size="1rem" />
          {!isCompact && <span className="hidden sm:inline ml-1.5">{labels.send}</span>}
        </button>
      </div>
    </form>
  );
}

export default AskBar;
