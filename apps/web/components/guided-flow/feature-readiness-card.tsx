"use client";

import type { MouseEventHandler } from "react";
import { useId } from "react";

import Button from "@/components/ui/button";
import { Icon, resolveIconName } from "@/components/ui/icon";

type ReadinessAction = {
  label: string;
  href?: string;
  onClick?: MouseEventHandler<HTMLButtonElement>;
};

export type FeatureReadinessState =
  | {
      kind: "ready";
      summary: string;
    }
  | {
      kind: "limited" | "unavailable";
      summary: string;
      reason: string;
      userAction: string;
      administratorAction: string;
      safeFallback: string;
    };

const STATUS_PRESENTATION = {
  ready: {
    label: "Sẵn sàng",
    icon: "check_circle",
    className:
      "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]",
  },
  limited: {
    label: "Hoạt động hạn chế",
    icon: "info",
    className:
      "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]",
  },
  unavailable: {
    label: "Tạm thời chưa sẵn sàng",
    icon: "error",
    className:
      "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]",
  },
} as const;

export function FeatureReadinessCard({
  title,
  state,
  action,
}: {
  title: string;
  state: FeatureReadinessState;
  action?: ReadinessAction;
}) {
  const headingId = useId();
  const status = STATUS_PRESENTATION[state.kind];

  return (
    <section
      aria-labelledby={headingId}
      className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-[var(--shadow-sm)]"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 id={headingId} className="font-semibold text-[var(--text-primary)]">
            {title}
          </h2>
          <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
            {state.summary}
          </p>
        </div>
        <p
          className={`inline-flex min-h-8 shrink-0 items-center gap-1.5 rounded-[var(--radius-pill)] border px-3 py-1 text-xs font-semibold ${status.className}`}
        >
          <Icon name={resolveIconName(status.icon)} size="1rem" />
          {status.label}
        </p>
      </div>

      {state.kind !== "ready" ? (
        <dl className="mt-4 divide-y divide-[color:var(--shell-border)] border-y border-[color:var(--shell-border)]">
          <div className="py-3">
            <dt className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
              Vì sao
            </dt>
            <dd className="mt-1 text-sm leading-6 text-[var(--text-primary)]">
              {state.reason}
            </dd>
          </div>
          <div className="py-3">
            <dt className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
              Bạn có thể làm gì
            </dt>
            <dd className="mt-1 text-sm leading-6 text-[var(--text-primary)]">
              {state.userAction}
            </dd>
          </div>
          <div className="py-3">
            <dt className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
              Quản trị viên cần làm gì
            </dt>
            <dd className="mt-1 text-sm leading-6 text-[var(--text-primary)]">
              {state.administratorAction}
            </dd>
          </div>
          <div className="py-3">
            <dt className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
              Cách tiếp tục an toàn
            </dt>
            <dd className="mt-1 text-sm leading-6 text-[var(--text-primary)]">
              {state.safeFallback}
            </dd>
          </div>
        </dl>
      ) : null}

      {action ? (
        <div className="mt-4">
          {action.href ? (
            <Button as="link" href={action.href} variant="secondary">
              {action.label}
            </Button>
          ) : (
            <Button type="button" variant="secondary" onClick={action.onClick}>
              {action.label}
            </Button>
          )}
        </div>
      ) : null}
    </section>
  );
}

export default FeatureReadinessCard;
