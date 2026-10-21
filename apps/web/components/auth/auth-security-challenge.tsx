"use client";

import { useCallback, useEffect, useState } from "react";
import Icon from "@/components/ui/icon";
import { t } from "@/lib/i18n/catalog";
import type { UILanguage } from "@/lib/ui-language";

export interface AuthSecurityChallengeProps {
  onSolvedChange: (solved: boolean) => void;
  isSolved: boolean;
  disabled?: boolean;
  language: UILanguage;
}

interface ChallengeQuestion {
  text: string;
  expectedAnswer: number;
}

function generateChallenge(): ChallengeQuestion {
  const isAddition = Math.random() > 0.4;
  if (isAddition) {
    const a = Math.floor(Math.random() * 8) + 2; // 2..9
    const b = Math.floor(Math.random() * 8) + 2; // 2..9
    return {
      text: `${a} + ${b}`,
      expectedAnswer: a + b,
    };
  } else {
    const b = Math.floor(Math.random() * 7) + 2; // 2..8
    const a = b + Math.floor(Math.random() * 8) + 2; // (b+2)..(b+9)
    return {
      text: `${a} - ${b}`,
      expectedAnswer: a - b,
    };
  }
}

export default function AuthSecurityChallenge({
  onSolvedChange,
  isSolved,
  disabled = false,
  language,
}: AuthSecurityChallengeProps) {
  const [challenge, setChallenge] = useState<ChallengeQuestion>(() => generateChallenge());
  const [userAnswer, setUserAnswer] = useState("");
  const [error, setError] = useState("");

  const refreshQuestion = useCallback(() => {
    setChallenge(generateChallenge());
    setUserAnswer("");
    setError("");
    onSolvedChange(false);
  }, [onSolvedChange]);

  const handleChange = (value: string) => {
    setUserAnswer(value);
    setError("");

    const trimmed = value.trim();
    if (!trimmed) {
      if (isSolved) onSolvedChange(false);
      return;
    }

    const parsed = parseInt(trimmed, 10);
    if (!Number.isNaN(parsed) && parsed === challenge.expectedAnswer) {
      setError("");
      onSolvedChange(true);
    } else {
      onSolvedChange(false);
      // If user typed equal or more digits than expected answer and it's wrong
      const expectedDigits = String(challenge.expectedAnswer).length;
      if (trimmed.length >= expectedDigits) {
        setError(t(language, "auth.rateLimit.challengeFailed"));
      }
    }
  };

  // When parent marks as unsolved, reset local answer if needed
  useEffect(() => {
    if (!isSolved && userAnswer && parseInt(userAnswer.trim(), 10) === challenge.expectedAnswer) {
      // Challenge was invalidated by an external failed attempt
      refreshQuestion();
    }
  }, [isSolved, challenge.expectedAnswer, refreshQuestion, userAnswer]);

  return (
    <div
      role="region"
      aria-label={t(language, "auth.rateLimit.challengeLabel")}
      className="space-y-3 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4"
      data-testid="auth-security-challenge"
    >
      <div className="flex items-center justify-between gap-2">
        <label
          htmlFor="security-challenge-answer"
          className="text-xs font-semibold text-[var(--text-primary)]"
        >
          {t(language, "auth.rateLimit.challengeLabel")}
        </label>
        <button
          type="button"
          onClick={refreshQuestion}
          disabled={disabled}
          className="focus-ring inline-flex items-center gap-1 rounded text-xs text-[var(--text-brand)] hover:underline disabled:opacity-50"
          aria-label={t(language, "auth.rateLimit.challengeRefresh")}
          title={t(language, "auth.rateLimit.challengeRefresh")}
        >
          <Icon name="refresh" size={14} aria-hidden="true" />
          <span>{t(language, "auth.rateLimit.challengeRefresh")}</span>
        </button>
      </div>

      <p className="text-xs text-[var(--text-secondary)]">
        {t(language, "auth.rateLimit.challengeRequired")}
      </p>

      <div className="flex items-center gap-3">
        <span
          className="inline-flex min-w-[5.5rem] items-center justify-center rounded-[var(--radius-md)] border border-[color:var(--shell-border-strong)] bg-[var(--surface-panel)] px-3 py-2 font-mono text-base font-bold tracking-wider text-[var(--text-primary)] shadow-xs select-none"
          aria-label={t(language, "auth.rateLimit.challengeQuestion", { question: challenge.text })}
        >
          {challenge.text} = ?
        </span>

        <input
          id="security-challenge-answer"
          type="text"
          inputMode="numeric"
          pattern="[0-9]*"
          maxLength={4}
          value={userAnswer}
          onChange={(e) => handleChange(e.target.value)}
          disabled={disabled || isSolved}
          placeholder={t(language, "auth.rateLimit.challengePlaceholder")}
          className="min-h-[var(--touch-target-min)] w-28 rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-center font-mono text-base font-medium text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[color:var(--brand-500)] focus:shadow-[var(--shadow-focus)] focus:outline-none disabled:opacity-60"
          aria-invalid={Boolean(error) || undefined}
        />

        {isSolved ? (
          <span
            role="status"
            className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--status-ok-text)]"
          >
            <Icon name="check" size={16} aria-hidden="true" />
            <span>{t(language, "auth.rateLimit.challengeSuccess")}</span>
          </span>
        ) : null}
      </div>

      {error ? (
        <p role="alert" className="text-xs font-medium text-[var(--status-danger-text)]">
          {error}
        </p>
      ) : null}
    </div>
  );
}
