"use client";

import { memo, useMemo, type FormEvent } from "react";

import type { UserRole } from "@/lib/auth-store";
import { t } from "@/lib/i18n/catalog";
import type { UILanguage } from "@/lib/ui-language";
import type {
  ResearchExecutionMode,
  ResearchOutputMode,
  ResearchRetrievalStackMode,
} from "@/lib/research";
import { IconButton } from "@/app/chat/_v2/components/primitives";
import Icon from "@/components/ui/icon";

/**
 * Modern floating chat composer with medical prompt suggestions for CLARA Chat.
 * Aligned with Stitch templates h_i_clara_active_conversation_refined & h_i_clara_new_conversation_refined.
 *
 * Prompt chips ("Tương tác thuốc", "Giải thích xét nghiệm", "Phác đồ điều trị")
 * + Mode switchers (fast/deep/deep_beta) + Depth selectors (sources/output mode)
 * + Personal-mode toggle + Send/Cancel.
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
  outputModesEnabled?: boolean;
  outputMode?: ResearchOutputMode;
  onChangeOutputMode?: (mode: ResearchOutputMode) => void;
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
    outputModesEnabled = false,
    outputMode = "plain_language",
    onChangeOutputMode = () => undefined,
    liveStatusNote,
    uiLanguage,
    userRole = "normal",
  } = props;
  const isFast = mode === "fast";
  const canUseProfessionalOutput =
    userRole === "researcher" || userRole === "doctor" || userRole === "admin";
  const contextLabel = t(
    uiLanguage,
    userRole === "researcher"
      ? "chat.composer.context.sources"
      : userRole === "doctor" || userRole === "admin"
        ? "chat.composer.context.case"
        : "chat.composer.context.profile",
  );

  const medicalSuggestions = useMemo(
    () => [
      {
        id: "interactions",
        icon: "medication" as const,
        label: t(uiLanguage, "chat.composer.suggestion.interactions.label"),
        prompt: t(uiLanguage, "chat.composer.suggestion.interactions.prompt"),
      },
      {
        id: "lab_result",
        icon: "scan" as const,
        label: t(uiLanguage, "chat.composer.suggestion.labResult.label"),
        prompt: t(uiLanguage, "chat.composer.suggestion.labResult.prompt"),
      },
      {
        id: "protocol",
        icon: "clinical-notes" as const,
        label: t(uiLanguage, "chat.composer.suggestion.protocol.label"),
        prompt: t(uiLanguage, "chat.composer.suggestion.protocol.prompt"),
      },
    ],
    [uiLanguage],
  );

  const contextualChips = useMemo(
    () => [
      {
        id: "side_effects",
        label: t(uiLanguage, "chat.composer.chip.sideEffects"),
        prompt: t(uiLanguage, "chat.composer.chip.sideEffects"),
      },
      {
        id: "alternatives",
        label: t(uiLanguage, "chat.composer.chip.alternatives"),
        prompt: t(uiLanguage, "chat.composer.chip.alternatives"),
      },
    ],
    [uiLanguage],
  );

  const handleSelectSuggestion = (promptText: string) => {
    onChangeQuery(promptText);
    const input = document.getElementById("chat-composer-input");
    if (input instanceof HTMLTextAreaElement) {
      input.focus();
    }
  };

  return (
    <form
      onSubmit={onSubmit}
      className="sticky bottom-0 z-20 w-full bg-gradient-to-t from-[var(--bg-canvas)] via-[var(--bg-canvas)]/95 to-transparent px-3 pb-3 pt-2 sm:px-6 sm:pb-4"
      aria-label={t(uiLanguage, "chat.composer.aria")}
    >
      <div className="mx-auto w-full max-w-3xl">
        {/* Live region: streaming status updates (Req 5.2). */}
        <div
          role="status"
          aria-live="polite"
          aria-atomic="true"
          className={[
            "mb-1.5 flex items-center gap-2 min-h-[1.25rem] truncate px-2 text-[11px] text-[var(--text-brand)]",
            liveStatusNote ? "" : "sr-only",
          ].join(" ")}
        >
          {liveStatusNote ? (
            <>
              <span className="inline-block h-2 w-2 shrink-0 rounded-full bg-[var(--brand-500)] motion-safe:animate-pulse" />
              <span className="truncate">{liveStatusNote}</span>
            </>
          ) : null}
        </div>

        {/* Floating Composer Container with Glow & Glass-Panel Shadow */}
        <div className="rounded-2xl border border-[color:var(--shell-border)]/80 dark:border-[#2A3950] bg-[var(--surface-panel)]/95 dark:bg-[#111C29]/95 p-3 shadow-[0_12px_40px_rgba(0,0,0,0.35)] backdrop-blur-xl transition focus-within:border-[color:var(--brand-500)]/60 focus-within:ring-1 focus-within:ring-[color:var(--brand-500)]/30">
          {/* Medical prompt suggestions row */}
          {!isRunning ? (
            <div className="mb-2.5 flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar text-xs">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] shrink-0 mr-1 hidden sm:inline">
                {t(uiLanguage, "chat.legacyComposer.promptTray")}:
              </span>
              {medicalSuggestions.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => handleSelectSuggestion(item.prompt)}
                  className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-[color:var(--shell-border)]/70 bg-[var(--surface-muted)]/80 px-3 py-1 text-[11px] font-semibold text-[var(--text-secondary)] transition hover:border-[color:var(--brand-500)]/50 hover:bg-[var(--surface-brand-soft)] hover:text-[var(--text-brand)] active:scale-95"
                >
                  <Icon name={item.icon} size={14} className="text-[var(--text-brand)]" />
                  <span>{item.label}</span>
                </button>
              ))}
              {query.trim()
                ? contextualChips.map((chip) => (
                    <button
                      key={chip.id}
                      type="button"
                      onClick={() => handleSelectSuggestion(chip.prompt)}
                      className="inline-flex shrink-0 items-center gap-1 rounded-full border border-[color:var(--shell-border)]/50 bg-[var(--surface-panel)] px-2.5 py-1 text-[11px] font-medium text-[var(--text-muted)] transition hover:border-[color:var(--brand-500)]/40 hover:text-[var(--text-primary)] active:scale-95"
                    >
                      <span>{chip.label}</span>
                    </button>
                  ))
                : null}
            </div>
          ) : null}

          <label className="sr-only" htmlFor="chat-composer-input">
            {t(uiLanguage, "chat.composer.questionLabel")}
          </label>
          <div className="relative flex items-center gap-2">
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
              placeholder={t(uiLanguage, "chat.composer.placeholder")}
              className="min-h-[52px] max-h-36 w-full resize-none bg-transparent px-1 py-1.5 text-sm sm:text-[15px] leading-relaxed text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)]"
            />
          </div>

          <div className="flex items-center justify-between gap-2 border-t border-[color:var(--shell-border)]/80 px-0.5 pt-2.5">
            <div className="flex min-w-0 flex-wrap items-center gap-1.5">
              {/* Attachment Button */}
              <button
                type="button"
                aria-label="Attach file"
                className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-[var(--text-muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] transition"
                onClick={() => {
                  const input = document.getElementById("chat-composer-input");
                  if (input instanceof HTMLTextAreaElement) input.focus();
                }}
              >
                <Icon name="plus" size={16} />
              </button>

              {/* Mic Voice Button */}
              <button
                type="button"
                aria-label="Voice input"
                className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-[var(--text-muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] transition"
                onClick={() => {
                  const input = document.getElementById("chat-composer-input");
                  if (input instanceof HTMLTextAreaElement) input.focus();
                }}
              >
                <Icon name="mic" size={16} />
              </button>

              {/* Mode Switcher Pill */}
              <div
                role="group"
                aria-label={t(uiLanguage, "chat.composer.mode")}
                className="inline-flex rounded-full bg-[var(--surface-muted)] p-0.5 border border-[color:var(--shell-border)]/40"
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
                        "min-h-[28px] rounded-full px-2.5 sm:px-3 text-[11px] font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-500)]",
                        active
                          ? "bg-[var(--brand-600)] text-[var(--on-secondary-container)] shadow-xs"
                          : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
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
                    "hidden min-h-[29px] items-center gap-1 rounded-full border px-2.5 text-[11px] font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-500)] sm:inline-flex",
                    personalMode
                      ? "border-[color:var(--brand-500)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                      : "border-[color:var(--shell-border)] text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]",
                  ].join(" ")}
                >
                  <Icon name="folder" size={14} aria-hidden="true" />
                  {contextLabel}
                </button>
              ) : null}

              {!isFast ? (
                <details className="relative">
                  <summary className="flex min-h-[29px] cursor-pointer list-none items-center gap-1 rounded-full border border-[color:var(--shell-border)] px-2.5 text-[11px] font-semibold text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]">
                    <Icon name="settings" size={15} aria-hidden="true" />
                    <span className="hidden sm:inline">
                      {t(uiLanguage, "chat.composer.sources")}
                    </span>
                  </summary>
                  <div className="absolute bottom-10 left-0 z-30 min-w-48 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 shadow-xl backdrop-blur-md">
                    <button
                      type="button"
                      aria-pressed={personalMode}
                      aria-label={`${contextLabel}${t(uiLanguage, "chat.composer.mobileSuffix")}`}
                      onClick={onTogglePersonalMode}
                      className={[
                        "mb-2 flex min-h-[34px] w-full items-center gap-2 rounded-lg border px-2.5 text-left text-[11px] font-semibold sm:hidden",
                        personalMode
                          ? "border-[color:var(--brand-500)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                          : "border-[color:var(--shell-border)] text-[var(--text-secondary)]",
                      ].join(" ")}
                    >
                      <Icon name="folder" size={15} aria-hidden="true" />
                      {contextLabel}
                    </button>
                    <label
                      className="block px-0.5 pb-1.5 text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider"
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
                      className="min-h-[34px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 text-xs text-[var(--text-primary)] outline-none focus:border-[color:var(--brand-500)]"
                    >
                      <option value="auto">
                        {t(uiLanguage, "chat.composer.bestAvailable")}
                      </option>
                      <option value="full">
                        {t(uiLanguage, "chat.composer.allSources")}
                      </option>
                    </select>
                    {outputModesEnabled && canUseProfessionalOutput ? (
                      <label className="mt-2 block px-0.5 text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">
                        {t(uiLanguage, "chat.composer.outputMode")}
                        <select
                          value={outputMode}
                          onChange={(event) =>
                            onChangeOutputMode(event.target.value as ResearchOutputMode)
                          }
                          className="mt-1 min-h-[34px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 text-xs text-[var(--text-primary)] outline-none focus:border-[color:var(--brand-500)]"
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
                className="shrink-0 !h-9 !w-9 !rounded-full shadow-md"
              />
            ) : (
              <IconButton
                label={t(uiLanguage, "chat.composer.send")}
                icon="arrow_upward"
                variant="primary"
                type="submit"
                disabled={!query.trim()}
                className="shrink-0 !h-9 !w-9 !rounded-full !bg-[var(--brand-600)] !text-[var(--on-secondary-container)] shadow-md hover:!bg-[var(--brand-700)] active:scale-95 disabled:!opacity-50"
              />
            )}
          </div>
        </div>
        <p className="mt-2 text-center text-[10px] text-[var(--text-muted)] opacity-80">
          {t(uiLanguage, "chat.composer.safetyNote")}
        </p>
      </div>
    </form>
  );
}

/**
 * Memoized: the composer receives stable callbacks plus primitive props,
 * so it should not re-render when unrelated shell state changes.
 */
export default memo(Composer);
