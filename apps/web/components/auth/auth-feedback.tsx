import { ReactNode } from "react";

function toneClass(tone: "success" | "error" | "info"): string {
  if (tone === "success") {
    return "border-emerald-300/80 bg-emerald-50/90 text-emerald-800 dark:border-emerald-500/40 dark:bg-emerald-950/40 dark:text-emerald-200";
  }

  if (tone === "error") {
    return "border-red-300/80 bg-red-50/90 text-red-800 dark:border-red-500/40 dark:bg-red-950/40 dark:text-red-200";
  }

  return "border-sky-300/80 bg-sky-50/90 text-sky-800 dark:border-sky-500/40 dark:bg-sky-950/40 dark:text-sky-200";
}

export function AuthMessage({ tone, children }: { tone: "success" | "error" | "info"; children: ReactNode }) {
  const role = tone === "error" ? "alert" : "status";
  const liveMode = tone === "error" ? "assertive" : "polite";

  return (
    <div
      className={`flex items-start gap-3 rounded-2xl border px-4 py-3 text-sm leading-6 sm:text-base ${toneClass(tone)}`}
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
