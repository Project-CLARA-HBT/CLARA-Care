"use client";

import { forwardRef, useId } from "react";
import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";

import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

const CONTROL =
  "min-h-[var(--touch-target-min)] w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2.5 text-sm text-[var(--text-primary)] shadow-[var(--shadow-sm)] outline-none transition-[border-color,box-shadow] duration-150 placeholder:text-[var(--text-muted)] hover:border-[color:var(--shell-border-strong)] focus:border-[color:var(--brand-500)] focus:shadow-[var(--shadow-focus)] disabled:cursor-not-allowed disabled:opacity-60";

function Label({
  label,
  optional,
  htmlFor,
}: {
  label: string;
  optional?: boolean;
  htmlFor: string;
}) {
  const language = useUILanguage();
  return (
    <label
      htmlFor={htmlFor}
      className="mb-1.5 block text-sm font-medium text-[var(--text-primary)]"
    >
      {label}
      {optional ? (
        <span className="ml-1 font-normal text-[var(--text-muted)]">
          {t(language, "field.optional")}
        </span>
      ) : null}
    </label>
  );
}

type FieldBase = {
  label?: string;
  hint?: string;
  error?: string;
  optional?: boolean;
  wrapperClassName?: string;
};

function descriptions(fieldId: string, hint?: string, error?: string) {
  const ids = [hint ? `${fieldId}-hint` : "", error ? `${fieldId}-error` : ""].filter(Boolean);
  return ids.length ? ids.join(" ") : undefined;
}

function SupportingText({ fieldId, hint, error }: { fieldId: string; hint?: string; error?: string }) {
  return (
    <>
      {hint ? <p id={`${fieldId}-hint`} className="mt-1.5 text-xs leading-5 text-[var(--text-muted)]">{hint}</p> : null}
      {error ? <p id={`${fieldId}-error`} role="alert" className="mt-1.5 text-xs font-medium leading-5 text-[var(--status-danger-text)]">{error}</p> : null}
    </>
  );
}

export const Field = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement> & FieldBase
>(function Field(
  { label, hint, error, optional, wrapperClassName = "", className = "", id, ...rest },
  ref,
) {
  const autoId = useId();
  const fieldId = id ?? autoId;
  return (
    <div className={wrapperClassName}>
      {label ? <Label label={label} optional={optional} htmlFor={fieldId} /> : null}
      <input ref={ref} id={fieldId} aria-describedby={descriptions(fieldId, hint, error)} aria-invalid={error ? true : undefined} className={`${CONTROL} ${error ? "border-[color:var(--status-danger-border)]" : ""} ${className}`} {...rest} />
      <SupportingText fieldId={fieldId} hint={hint} error={error} />
    </div>
  );
});

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement> & FieldBase
>(function Textarea(
  { label, hint, error, optional, wrapperClassName = "", className = "", id, ...rest },
  ref,
) {
  const autoId = useId();
  const fieldId = id ?? autoId;
  return (
    <div className={wrapperClassName}>
      {label ? <Label label={label} optional={optional} htmlFor={fieldId} /> : null}
      <textarea
        ref={ref}
        id={fieldId}
        aria-describedby={descriptions(fieldId, hint, error)}
        aria-invalid={error ? true : undefined}
        className={`${CONTROL} min-h-20 resize-y ${error ? "border-[color:var(--status-danger-border)]" : ""} ${className}`}
        {...rest}
      />
      <SupportingText fieldId={fieldId} hint={hint} error={error} />
    </div>
  );
});

export const Select = forwardRef<
  HTMLSelectElement,
  SelectHTMLAttributes<HTMLSelectElement> & FieldBase & { children: ReactNode }
>(function Select(
  { label, hint, error, optional, wrapperClassName = "", className = "", id, children, ...rest },
  ref,
) {
  const autoId = useId();
  const fieldId = id ?? autoId;
  return (
    <div className={wrapperClassName}>
      {label ? <Label label={label} optional={optional} htmlFor={fieldId} /> : null}
      <select ref={ref} id={fieldId} aria-describedby={descriptions(fieldId, hint, error)} aria-invalid={error ? true : undefined} className={`${CONTROL} ${error ? "border-[color:var(--status-danger-border)]" : ""} ${className}`} {...rest}>
        {children}
      </select>
      <SupportingText fieldId={fieldId} hint={hint} error={error} />
    </div>
  );
});

export default Field;
