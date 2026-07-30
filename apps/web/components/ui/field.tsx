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
  "w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2.5 text-sm text-[var(--text-primary)] shadow-[var(--shadow-sm)] outline-none transition-[border-color,box-shadow] duration-150 placeholder:text-[var(--text-muted)] hover:border-[color:var(--shell-border-strong)] focus:border-[color:var(--brand-500)] focus:shadow-[var(--shadow-focus)] disabled:cursor-not-allowed disabled:opacity-60";

function Label({
  label,
  hint,
  optional,
  htmlFor,
}: {
  label: string;
  hint?: string;
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
      {hint ? <span className="ml-1 font-normal text-[var(--text-muted)]">{hint}</span> : null}
    </label>
  );
}

type FieldBase = {
  label?: string;
  hint?: string;
  optional?: boolean;
  wrapperClassName?: string;
};

export const Field = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement> & FieldBase
>(function Field(
  { label, hint, optional, wrapperClassName = "", className = "", id, ...rest },
  ref,
) {
  const autoId = useId();
  const fieldId = id ?? autoId;
  return (
    <div className={wrapperClassName}>
      {label ? <Label label={label} hint={hint} optional={optional} htmlFor={fieldId} /> : null}
      <input ref={ref} id={fieldId} className={`${CONTROL} ${className}`} {...rest} />
    </div>
  );
});

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement> & FieldBase
>(function Textarea(
  { label, hint, optional, wrapperClassName = "", className = "", id, ...rest },
  ref,
) {
  const autoId = useId();
  const fieldId = id ?? autoId;
  return (
    <div className={wrapperClassName}>
      {label ? <Label label={label} hint={hint} optional={optional} htmlFor={fieldId} /> : null}
      <textarea
        ref={ref}
        id={fieldId}
        className={`${CONTROL} min-h-20 resize-y ${className}`}
        {...rest}
      />
    </div>
  );
});

export const Select = forwardRef<
  HTMLSelectElement,
  SelectHTMLAttributes<HTMLSelectElement> & FieldBase & { children: ReactNode }
>(function Select(
  { label, hint, optional, wrapperClassName = "", className = "", id, children, ...rest },
  ref,
) {
  const autoId = useId();
  const fieldId = id ?? autoId;
  return (
    <div className={wrapperClassName}>
      {label ? <Label label={label} hint={hint} optional={optional} htmlFor={fieldId} /> : null}
      <select ref={ref} id={fieldId} className={`${CONTROL} ${className}`} {...rest}>
        {children}
      </select>
    </div>
  );
});
