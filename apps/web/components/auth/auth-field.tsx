"use client";

import { useMemo, useState } from "react";
import Icon from "@/components/ui/icon";

type AuthFieldProps = {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
  minLength?: number;
  maxLength?: number;
  type?: "text" | "email" | "password";
  autoComplete?: string;
  helperText?: string;
  error?: string;
  disabled?: boolean;
  as?: "input" | "textarea";
  rows?: number;
};

const baseControlClass =
  "min-h-[var(--touch-target-min)] w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3 text-base text-[var(--text-primary)] outline-none transition-[border-color,box-shadow] duration-150 placeholder:text-[var(--text-muted)] hover:border-[color:var(--shell-border-strong)] focus:border-[color:var(--brand-500)] focus:shadow-[var(--shadow-focus)] disabled:cursor-not-allowed disabled:opacity-60";

export default function AuthField({
  id,
  label,
  value,
  onChange,
  placeholder,
  required,
  minLength,
  maxLength,
  type = "text",
  autoComplete,
  helperText,
  error,
  disabled,
  as = "input",
  rows = 4
}: AuthFieldProps) {
  const [isPasswordVisible, setIsPasswordVisible] = useState(false);
  const helperId = helperText ? `${id}-helper` : undefined;
  const errorId = error ? `${id}-error` : undefined;

  const describedBy = useMemo(() => {
    const ids = [helperId, errorId].filter(Boolean) as string[];
    return ids.length > 0 ? ids.join(" ") : undefined;
  }, [errorId, helperId]);

  const isPasswordField = as === "input" && type === "password";
  const inputType = isPasswordField && isPasswordVisible ? "text" : type;
  const hasError = Boolean(error);

  return (
    <div className="space-y-2.5">
      <label htmlFor={id} className="block text-sm font-semibold text-[var(--text-primary)]">
        {label}
        {required ? (
          <span className="ml-1 text-[var(--status-danger-text)]" aria-hidden="true">
            *
          </span>
        ) : null}
      </label>

      {as === "textarea" ? (
        <textarea
          id={id}
          rows={rows}
          className={`${baseControlClass} min-h-[8.5rem] resize-y ${hasError ? "border-[color:var(--status-danger-border)] focus:border-[color:var(--status-danger-border)]" : ""}`}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          required={required}
          minLength={minLength}
          maxLength={maxLength}
          disabled={disabled}
          aria-required={required || undefined}
          aria-invalid={hasError || undefined}
          aria-describedby={describedBy}
        />
      ) : (
        <div className="relative">
          <input
            id={id}
            className={`${baseControlClass} ${isPasswordField ? "pr-16" : ""} ${hasError ? "border-[color:var(--status-danger-border)] focus:border-[color:var(--status-danger-border)]" : ""}`}
            type={inputType}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            placeholder={placeholder}
            required={required}
            minLength={minLength}
            maxLength={maxLength}
            autoComplete={autoComplete}
            disabled={disabled}
            inputMode={type === "email" ? "email" : undefined}
            autoCapitalize={type === "email" || type === "password" ? "none" : undefined}
            spellCheck={type === "email" || type === "password" ? false : undefined}
            aria-required={required || undefined}
            aria-invalid={hasError || undefined}
            aria-describedby={describedBy}
          />

          {isPasswordField ? (
            <button
              type="button"
              className="absolute right-3 top-1/2 inline-flex h-10 w-10 -translate-y-1/2 items-center justify-center border-0 bg-transparent p-0 text-[var(--text-secondary)] transition hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-500)]"
              onClick={() => setIsPasswordVisible((current) => !current)}
              aria-controls={id}
              aria-pressed={isPasswordVisible}
              aria-label={isPasswordVisible ? "An mat khau" : "Hien mat khau"}
              disabled={disabled}
            >
              <Icon name={isPasswordVisible ? "eye-off" : "eye"} size={18} aria-hidden="true" />
            </button>
          ) : null}
        </div>
      )}

      {helperText ? <p id={helperId} className="text-sm text-[var(--text-secondary)]">{helperText}</p> : null}
      {error ? (
        <p id={errorId} role="alert" className="text-sm font-medium text-[var(--status-danger-text)]">
          {error}
        </p>
      ) : null}
    </div>
  );
}
