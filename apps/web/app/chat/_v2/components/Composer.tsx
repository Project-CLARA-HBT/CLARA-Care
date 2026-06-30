"use client";

import { memo, type FormEvent } from "react";

import type { UILanguage } from "@/lib/ui-language";
import type {
  ResearchExecutionMode,
  ResearchRetrievalStackMode,
} from "@/lib/research";
import { Button, IconButton } from "@/app/chat/_v2/components/primitives";

/**
 * Answer-first composer for the rebuilt CLARA Chat (CHAT_V2).
 *
 * Prompt + mode selector (fast/deep/deep_beta) + personal-mode toggle +
 * send/cancel (Requirement 3.5, 4.4). Stays responsive during a run: while
 * running it offers a Cancel affordance instead of disabling the whole composer.
 * The live status note is exposed through an ARIA live region (Requirement 5.2).
 */

const MODE_OPTIONS: Array<{ id: ResearchExecutionMode; label: Record<UILanguage, string> }> = [
  { id: "fast", label: { vi: "Nhanh", en: "Quick" } },
  { id: "deep", label: { vi: "Tư duy", en: "Reason" } },
  { id: "deep_beta", label: { vi: "Pro", en: "Pro" } },
];

export type ComposerProps = {
  query: string;
  onChangeQuery: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  isRunning: boolean;
  onCancel: () => void;
  mode: ResearchExecutionMode;
  onChangeMode: (mode: ResearchExecutionMode) => void;
  retrievalStackMode: ResearchRetrievalStackMode;
  onChangeRetrievalStackMode: (mode: ResearchRetrievalStackMode) => void;
  personalMode: boolean;
  onTogglePersonalMode: () => void;
  liveStatusNote: string;
  uiLanguage: UILanguage;
};

function Composer(props: ComposerProps) {
  const {
    query,
    onChangeQuery,
    onSubmit,
    isRunning,
    onCancel,
    mode,
    onChangeMode,
    retrievalStackMode,
    onChangeRetrievalStackMode,
    personalMode,
    onTogglePersonalMode,
    liveStatusNote,
    uiLanguage,
  } = props;
  const isEn = uiLanguage === "en";
  const isFast = mode === "fast";

  return (
    <form
      onSubmit={onSubmit}
      className="border-t border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2.5"
      aria-label={isEn ? "Message composer" : "Khung soạn câu hỏi"}
    >
      <div className="mx-auto w-full max-w-3xl space-y-2">
        {/* Live region: streaming status updates (Req 5.2). The status text
            replaces wholesale on each token/stage update, so announce it
            atomically and keep it in the DOM (visually hidden when empty) so
            assistive tech reads the current status rather than diffed fragments. */}
        <p
          role="status"
          aria-live="polite"
          aria-atomic="true"
          className={[
            "min-h-[1rem] truncate text-[11px] text-[var(--text-muted)]",
            liveStatusNote ? "" : "sr-only",
          ].join(" ")}
        >
          {liveStatusNote}
        </p>

        <div className="flex flex-wrap items-center gap-1.5">
          <div
            role="group"
            aria-label={isEn ? "Response mode" : "Chế độ trả lời"}
            className="inline-flex rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-0.5"
          >
            {MODE_OPTIONS.map((option) => {
              const active = option.id === mode;
              return (
                <button
                  key={option.id}
                  type="button"
                  aria-pressed={active}
                  onClick={() => onChangeMode(option.id)}
                  className={[
                    "min-h-[30px] rounded-full px-3 text-[11px] font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--shell-border-strong)]",
                    active
                      ? "bg-[var(--brand-600)] text-white"
                      : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
                  ].join(" ")}
                >
                  {option.label[uiLanguage]}
                </button>
              );
            })}
          </div>

          <button
            type="button"
            aria-pressed={personalMode}
            onClick={onTogglePersonalMode}
            disabled={isFast}
            className={[
              "min-h-[30px] rounded-full border px-3 text-[11px] font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--shell-border-strong)] disabled:cursor-not-allowed disabled:opacity-50",
              personalMode
                ? "border-[color:var(--brand-600)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]",
            ].join(" ")}
            title={
              isFast
                ? isEn
                  ? "Personal mode needs Reason or Pro"
                  : "Chế độ cá nhân cần Tư duy hoặc Pro"
                : undefined
            }
          >
            {isEn ? "Personal" : "Cá nhân"}
          </button>

          {!isFast ? (
            <select
              value={retrievalStackMode}
              onChange={(event) =>
                onChangeRetrievalStackMode(event.target.value as ResearchRetrievalStackMode)
              }
              aria-label={isEn ? "Source depth" : "Độ sâu nguồn"}
              className="min-h-[30px] rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 text-[11px] text-[var(--text-secondary)]"
            >
              <option value="auto">{isEn ? "Auto sources" : "Nguồn tự chọn"}</option>
              <option value="full">{isEn ? "Full sources" : "Nguồn đầy đủ"}</option>
            </select>
          ) : null}
        </div>

        <div className="flex items-end gap-2">
          <label className="sr-only" htmlFor="chat-composer-input">
            {isEn ? "Your medical question" : "Câu hỏi y tế của bạn"}
          </label>
          <textarea
            id="chat-composer-input"
            value={query}
            onChange={(event) => onChangeQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            rows={1}
            placeholder={isEn ? "Enter your medical question..." : "Nhập câu hỏi y tế của bạn..."}
            className="min-h-[44px] max-h-40 flex-1 resize-y rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2.5 text-sm text-[var(--text-primary)] outline-none focus-visible:border-[color:var(--shell-border-strong)] focus-visible:ring-2 focus-visible:ring-[color:var(--shell-border-strong)]"
          />
          {isRunning ? (
            <IconButton
              label={isEn ? "Cancel run" : "Hủy phiên"}
              icon="stop_circle"
              variant="danger"
              onClick={onCancel}
            />
          ) : (
            <Button type="submit" variant="primary" disabled={!query.trim()}>
              {isEn ? "Send" : "Gửi"}
            </Button>
          )}
        </div>
      </div>
    </form>
  );
}

/**
 * Memoized: the composer receives stable callbacks (the shell wraps its
 * handlers in `useCallback`) plus primitive props, so it should not re-render
 * when unrelated shell state (search text, notices, the message log) changes
 * (Requirement 7.2, Property P9).
 */
export default memo(Composer);
