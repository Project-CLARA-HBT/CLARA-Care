"use client";

import { useMemo, useState } from "react";

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
  "w-full rounded-2xl border bg-white/80 px-4 py-3 text-base text-slate-900 shadow-sm outline-none transition duration-200 placeholder:text-slate-400 focus:border-sky-400 focus:ring-4 focus:ring-sky-200/70 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-600 dark:bg-slate-900/85 dark:text-slate-100 dark:placeholder:text-slate-400 dark:focus:border-sky-500 dark:focus:ring-sky-500/25";

function EyeOpenIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-5 w-5"
    >
      <path d="M2 12s3.6-6 10-6 10 6 10 6-3.6 6-10 6-10-6-10-6Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeClosedIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-5 w-5"
    >
      <path d="M3 3l18 18" />
      <path d="M10.6 10.7A3 3 0 0 0 13.4 13.5" />
      <path d="M9.9 5.2A11 11 0 0 1 12 5c6.4 0 10 7 10 7a17.2 17.2 0 0 1-4.1 4.8" />
      <path d="M6.7 6.8C3.9 8.6 2 12 2 12a17.7 17.7 0 0 0 7.3 6.1" />
    </svg>
  );
}

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
      <label htmlFor={id} className="block text-base font-semibold text-slate-800 dark:text-slate-100">
        {label}
        {required ? (
          <span className="ml-1 text-red-600" aria-hidden="true">
            *
          </span>
        ) : null}
      </label>

      {as === "textarea" ? (
        <textarea
          id={id}
          rows={rows}
          className={`${baseControlClass} min-h-[8.5rem] resize-y ${hasError ? "border-red-400 focus:border-red-500 focus:ring-red-200/70 dark:border-red-500 dark:focus:border-red-400 dark:focus:ring-red-500/25" : "border-slate-300"}`}
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
            className={`${baseControlClass} min-h-12 ${isPasswordField ? "pr-16" : ""} ${hasError ? "border-red-400 focus:border-red-500 focus:ring-red-200/70 dark:border-red-500 dark:focus:border-red-400 dark:focus:ring-red-500/25" : "border-slate-300"}`}
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
              className="absolute right-3 top-1/2 inline-flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full border border-slate-200/90 bg-white/95 text-slate-500 transition hover:border-slate-300 hover:bg-white hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:border-slate-600 dark:bg-slate-900/95 dark:text-slate-300 dark:hover:border-slate-500 dark:hover:bg-slate-900 dark:hover:text-slate-100"
              onClick={() => setIsPasswordVisible((current) => !current)}
              aria-controls={id}
              aria-pressed={isPasswordVisible}
              aria-label={isPasswordVisible ? "An mat khau" : "Hien mat khau"}
              disabled={disabled}
            >
              {isPasswordVisible ? <EyeClosedIcon /> : <EyeOpenIcon />}
            </button>
          ) : null}
        </div>
      )}

      {helperText ? <p id={helperId} className="text-sm text-slate-600 dark:text-slate-300">{helperText}</p> : null}
      {error ? (
        <p id={errorId} role="alert" className="text-sm font-medium text-red-700 dark:text-red-300">
          {error}
        </p>
      ) : null}
    </div>
  );
}
