"use client";

import type { MouseEventHandler } from "react";

import Button from "@/components/ui/button";
import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

type SecondaryAction = {
  label: string;
  href?: string;
  onClick?: MouseEventHandler<HTMLButtonElement>;
  disabled?: boolean;
};

export function StepActions({
  nextLabel,
  nextType = "submit",
  onNext,
  nextDisabled = false,
  saving = false,
  savingLabel,
  back,
  skip,
}: {
  nextLabel?: string;
  nextType?: "button" | "submit";
  onNext?: MouseEventHandler<HTMLButtonElement>;
  nextDisabled?: boolean;
  saving?: boolean;
  savingLabel?: string;
  back?: SecondaryAction;
  skip?: SecondaryAction;
}) {
  const language = useUILanguage();

  return (
    <div className="border-t border-[color:var(--shell-border)] pt-5">
      <div className="flex flex-col gap-3 sm:flex-row-reverse sm:items-center">
        <Button
          type={nextType}
          onClick={onNext}
          disabled={nextDisabled}
          loading={saving}
          loadingLabel={savingLabel ?? t(language, "flow.saving")}
          icon="arrow_forward"
          iconTrailing
          className="sm:min-w-36"
        >
          {nextLabel ?? t(language, "flow.continue")}
        </Button>

        {back?.href && !saving ? (
          <Button as="link" href={back.href} variant="secondary" className="sm:min-w-28">
            {back.label}
          </Button>
        ) : back ? (
          <Button
            type="button"
            variant="secondary"
            onClick={back.onClick}
            disabled={back.disabled || saving}
            className="sm:min-w-28"
          >
            {back.label}
          </Button>
        ) : null}

        {skip?.href && !saving ? (
          <Button as="link" href={skip.href} variant="ghost" className="sm:mr-auto">
            {skip.label}
          </Button>
        ) : skip ? (
          <Button
            type="button"
            variant="ghost"
            onClick={skip.onClick}
            disabled={skip.disabled || saving}
            className="sm:mr-auto"
          >
            {skip.label}
          </Button>
        ) : null}
      </div>
    </div>
  );
}

export default StepActions;
