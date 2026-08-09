import { ReactNode } from "react";

function toneClass(tone: "success" | "error" | "info"): string {
  if (tone === "success") {
    return "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]";
  }

  if (tone === "error") {
    return "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]";
  }

  return "border-[color:var(--shell-border)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]";
}

export function AuthMessage({ tone, children }: { tone: "success" | "error" | "info"; children: ReactNode }) {
  const role = tone === "error" ? "alert" : "status";
  const liveMode = tone === "error" ? "assertive" : "polite";

  return (
    <div
      className={`flex items-start gap-3 rounded-[var(--radius-lg)] border px-4 py-3 text-sm leading-6 sm:text-base ${toneClass(tone)}`}
      role={role}
      aria-live={liveMode}
      aria-atomic="true"
    >
      <span className="mt-1 inline-flex h-2.5 w-2.5 shrink-0 rounded-full bg-current opacity-80" aria-hidden="true" />
      <div>{children}</div>
    </div>
  );
}

export default function AuthFeedback({
  notice,
  error,
  noticeNode,
  errorNode
}: {
  notice?: string;
  error?: string;
  noticeNode?: ReactNode;
  errorNode?: ReactNode;
}) {
  if (!notice && !error) return null;

  return (
    <div className="space-y-3">
      {notice ? <AuthMessage tone="success">{noticeNode ?? notice}</AuthMessage> : null}
      {error ? <AuthMessage tone="error">{errorNode ?? error}</AuthMessage> : null}
    </div>
  );
}
