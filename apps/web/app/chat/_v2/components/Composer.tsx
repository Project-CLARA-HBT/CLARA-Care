"use client";

import { memo, type FormEvent } from "react";

import type { UserRole } from "@/lib/auth-store";
import { t } from "@/lib/i18n/catalog";
import type { UILanguage } from "@/lib/ui-language";
import type {
  ResearchExecutionMode,
  ResearchOutputMode,
  ResearchRetrievalStackMode,
} from "@/lib/research";
import { IconButton } from "@/app/chat/_v2/components/primitives";

/**
 * Answer-first composer for the rebuilt CLARA Chat (CHAT_V2).
 *
 * Prompt + mode selector (fast/deep/deep_beta) + personal-mode toggle +
 * send/cancel (Requirement 3.5, 4.4). Stays responsive during a run: while
 * running it offers a Cancel affordance instead of disabling the whole composer.
 * The live status note is exposed through an ARIA live region (Requirement 5.2).
 */

const MODE_OPTIONS: Array<{
  id: ResearchExecutionMode;
  labelKey:
    | "chat.composer.mode.fast"
    | "chat.composer.mode.deep"
    | "chat.composer.mode.research";
}> = [
  { id: "fast", labelKey: "chat.composer.mode.fast" },
  { id: "deep", labelKey: "chat.composer.mode.deep" },
  { id: "deep_beta", labelKey: "chat.composer.mode.research" },
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
  outputModesEnabled: boolean;
  outputMode: ResearchOutputMode;
  onChangeOutputMode: (mode: ResearchOutputMode) => void;
  liveStatusNote: string;
  uiLanguage: UILanguage;
  userRole?: UserRole;
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
    outputModesEnabled,
    outputMode,
    onChangeOutputMode,
    liveStatusNote,
    uiLanguage,
    userRole = "normal",
  } = props;
  const isFast = mode === "fast";
  const canUseProfessionalOutput = userRole === "researcher" || userRole === "doctor" || userRole === "admin";
  const contextLabel = t(
    uiLanguage,
    userRole === "researcher"
      ? "chat.composer.context.sources"
      : userRole === "doctor" || userRole === "admin"
        ? "chat.composer.context.case"
        : "chat.composer.context.profile",
  );

  return (
    <form
      onSubmit={onSubmit}
      className="border-t border-[color:var(--shell-border)] bg-[var(--bg-canvas)] px-3 pb-3 pt-2 sm:px-5 sm:pb-4"
      aria-label={t(uiLanguage, "chat.composer.aria")}
    >
      <div className="mx-auto w-full max-w-3xl">
        {/* Live region: streaming status updates (Req 5.2). The status text
            replaces wholesale on each token/stage update, so announce it
            atomically and keep it in the DOM (visually hidden when empty) so
            assistive tech reads the current status rather than diffed fragments. */}
        <p
          role="status"
          aria-live="polite"
          aria-atomic="true"
          className={[
            "mb-1.5 min-h-[1rem] truncate px-2 text-[11px] text-[var(--text-muted)]",
            liveStatusNote ? "" : "sr-only",
          ].join(" ")}
        >
          {liveStatusNote}
        </p>

        <div className="rounded-[1.4rem] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2 shadow-[0_18px_50px_-34px_rgba(15,23,42,.55)] transition focus-within:border-[color:var(--shell-border-strong)] focus-within:shadow-[0_20px_55px_-32px_rgba(37,99,235,.4)]">
          <label className="sr-only" htmlFor="chat-composer-input">
            {t(uiLanguage, "chat.composer.questionLabel")}
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
            rows={2}
            placeholder={
              t(uiLanguage, "chat.composer.placeholder")
            }
            className="min-h-[58px] max-h-40 w-full resize-none bg-transparent px-2.5 py-2 text-[15px] leading-6 text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)]"
          />

          <div className="flex items-end justify-between gap-2 border-t border-[color:var(--shell-border)] px-0.5 pt-2">
            <div className="flex min-w-0 flex-wrap items-center gap-1.5">
              <div
                role="group"
                aria-label={t(uiLanguage, "chat.composer.mode")}
                className="inline-flex rounded-xl bg-[var(--surface-muted)] p-0.5"
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
                        "min-h-[30px] rounded-[0.65rem] px-2.5 text-[11px] font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-500)] sm:px-3",
                        active
                          ? "bg-[var(--surface-panel)] text-[var(--text-primary)] shadow-sm"
                          : "text-[var(--text-muted)] hover:text-[var(--text-primary)]",
                      ].join(" ")}
                    >
                      {t(uiLanguage, option.labelKey)}
                    </button>
                  );
                })}
              </div>

              {!isFast ? (
                <button
                  type="button"
                  aria-pressed={personalMode}
                  onClick={onTogglePersonalMode}
                  className={[
                    "hidden min-h-[31px] items-center gap-1 rounded-xl border px-2.5 text-[11px] font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-500)] sm:inline-flex",
                    personalMode
                      ? "border-[color:var(--brand-500)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                      : "border-[color:var(--shell-border)] text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]",
                  ].join(" ")}
                >
                  <span
                    className="material-symbols-outlined text-[15px]"
                    aria-hidden="true"
                  >
                    folder_shared
                  </span>
                  {contextLabel}
                </button>
              ) : null}

              {!isFast ? (
                <details className="relative">
                  <summary className="flex min-h-[31px] cursor-pointer list-none items-center gap-1 rounded-xl px-2 text-[11px] font-semibold text-[var(--text-muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]">
                    <span
                      className="material-symbols-outlined text-[16px]"
                      aria-hidden="true"
                    >
                      tune
                    </span>
                    <span className="hidden sm:inline">
                      {t(uiLanguage, "chat.composer.sources")}
                    </span>
                  </summary>
                  <div className="absolute bottom-10 left-0 z-20 min-w-48 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2 shadow-xl">
                    <button
                      type="button"
                      aria-pressed={personalMode}
                      aria-label={`${contextLabel}${t(uiLanguage, "chat.composer.mobileSuffix")}`}
                      onClick={onTogglePersonalMode}
                      className={[
                        "mb-2 flex min-h-[36px] w-full items-center gap-2 rounded-lg border px-2 text-left text-[11px] font-semibold sm:hidden",
                        personalMode
                          ? "border-[color:var(--brand-500)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                          : "border-[color:var(--shell-border)] text-[var(--text-secondary)]",
                      ].join(" ")}
                    >
                      <span
                        className="material-symbols-outlined text-[16px]"
                        aria-hidden="true"
                      >
                        folder_shared
                      </span>
                      {contextLabel}
                    </button>
                    <label
                      className="block px-1 pb-1.5 text-[10px] font-semibold text-[var(--text-muted)]"
                      htmlFor="chat-source-depth"
                    >
                      {t(uiLanguage, "chat.composer.evidenceSources")}
                    </label>
                    <select
                      id="chat-source-depth"
                      value={retrievalStackMode}
                      onChange={(event) =>
                        onChangeRetrievalStackMode(
                          event.target.value as ResearchRetrievalStackMode,
                        )
                      }
                      className="min-h-[36px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 text-xs text-[var(--text-primary)]"
                    >
                      <option value="auto">
                        {t(uiLanguage, "chat.composer.bestAvailable")}
                      </option>
                      <option value="full">
                        {t(uiLanguage, "chat.composer.allSources")}
                      </option>
                    </select>
                    {outputModesEnabled && canUseProfessionalOutput ? (
                      <label className="mt-2 block px-1 text-[10px] font-semibold text-[var(--text-muted)]">
                        {t(uiLanguage, "chat.composer.outputMode")}
                        <select
                          value={outputMode}
                          onChange={(event) =>
                            onChangeOutputMode(event.target.value as ResearchOutputMode)
                          }
                          className="mt-1 min-h-[36px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 text-xs text-[var(--text-primary)]"
                        >
                          <option value="plain_language">
                            {t(uiLanguage, "chat.composer.outputMode.plainLanguage")}
                          </option>
                          <option value="professional">
                            {t(uiLanguage, "chat.composer.outputMode.professional")}
                          </option>
                        </select>
                      </label>
                    ) : null}
                  </div>
                </details>
              ) : null}
            </div>

            {isRunning ? (
              <IconButton
                label={t(uiLanguage, "chat.composer.cancel")}
                icon="stop"
                variant="danger"
                onClick={onCancel}
                className="shrink-0 !h-10 !w-10"
              />
            ) : (
              <IconButton
                label={t(uiLanguage, "chat.composer.send")}
                icon="arrow_upward"
                variant="primary"
                type="submit"
                disabled={!query.trim()}
                className="shrink-0 !h-10 !w-10 !text-white"
              />
            )}
          </div>
        </div>
        <p className="mt-1.5 text-center text-[10px] text-[var(--text-muted)]">
          {t(uiLanguage, "chat.composer.safetyNote")}
        </p>
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
