"use client";

import { useId } from "react";

import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import { Icon } from "@/components/ui/icon";

export type GuidedFlowError = {
  id: string;
  message: string;
  fieldId?: string;
  fieldLabel?: string;
};

export function ErrorSummary({
  errors,
  title,
  description,
}: {
  errors: GuidedFlowError[];
  title?: string;
  description?: string;
}) {
  const language = useUILanguage();
  const headingId = useId();
  const descriptionId = useId();

  if (errors.length === 0) return null;

  return (
    <section
      role="alert"
      aria-labelledby={headingId}
      aria-describedby={descriptionId}
      className="rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-4 text-[var(--status-danger-text)]"
    >
      <div className="flex items-start gap-3">
        <Icon name="warning" size="1.25rem" className="mt-0.5" />
        <div className="min-w-0">
          <h2 id={headingId} className="text-sm font-semibold">
            {title ?? t(language, "flow.checkInformation")}
          </h2>
          <p id={descriptionId} className="mt-1 text-sm leading-5">
            {description ?? t(language, "flow.fixBeforeContinue")}
          </p>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-sm">
            {errors.map((error) => (
              <li key={error.id}>
                {error.fieldId ? (
                  <a
                    href={`#${error.fieldId}`}
                    className="focus-ring rounded-[var(--radius-sm)] font-semibold underline decoration-current underline-offset-2"
                  >
                    {error.fieldLabel ? `${error.fieldLabel}: ` : null}
                    {error.message}
                  </a>
                ) : (
                  <>
                    {error.fieldLabel ? (
                      <span className="font-semibold">
                        {error.fieldLabel}:{" "}
                      </span>
                    ) : null}
                    {error.message}
                  </>
                )}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

export default ErrorSummary;
