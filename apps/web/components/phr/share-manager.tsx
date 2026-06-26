"use client";

import { useState } from "react";
import {
  createPhrShare,
  revokePhrShare,
  type PhrShare,
  type PhrShareScope,
} from "@/lib/phr";
import type { UILanguage } from "@/lib/ui-language";

/**
 * Read-only share manager (personal-health-record Requirement 12.1, 12.3).
 * Creates scoped share links (full record or emergency card only) with an
 * optional expiry, lists links created in this session, and revokes them. The
 * backend rejects creation (428) when sharing consent is absent — that message
 * is surfaced inline. Rendered only when the `sharing` capability is effective
 * (Requirement 18.1).
 */

const COPY = {
  vi: {
    title: "Chia sẻ hồ sơ (chỉ đọc)",
    description:
      "Tạo liên kết chỉ đọc để chia sẻ hồ sơ. Bạn có thể thu hồi bất cứ lúc nào.",
    scope: "Phạm vi",
    scopeFull: "Toàn bộ hồ sơ",
    scopeEmergency: "Chỉ thẻ khẩn cấp",
    expiry: "Hết hạn sau (ngày)",
    noExpiry: "Không giới hạn",
    create: "Tạo liên kết",
    creating: "Đang tạo...",
    createError: "Tạo liên kết chia sẻ thất bại.",
    activeLinks: "Liên kết đã tạo",
    noLinks: "Chưa có liên kết nào trong phiên này.",
    copy: "Sao chép",
    copied: "Đã sao chép",
    revoke: "Thu hồi",
    revoking: "Đang thu hồi...",
    revokeError: "Thu hồi liên kết thất bại.",
    expiresAt: "Hết hạn",
    never: "không giới hạn",
  },
  en: {
    title: "Share record (read-only)",
    description:
      "Create read-only links to share your record. You can revoke them anytime.",
    scope: "Scope",
    scopeFull: "Full record",
    scopeEmergency: "Emergency card only",
    expiry: "Expires in (days)",
    noExpiry: "No expiry",
    create: "Create link",
    creating: "Creating...",
    createError: "Failed to create share link.",
    activeLinks: "Created links",
    noLinks: "No links created in this session yet.",
    copy: "Copy",
    copied: "Copied",
    revoke: "Revoke",
    revoking: "Revoking...",
    revokeError: "Failed to revoke link.",
    expiresAt: "Expires",
    never: "no expiry",
  },
} as const;

function shareUrl(token: string): string {
  if (typeof window === "undefined") return token;
  return `${window.location.origin}/phr/shared/${token}`;
}

export default function ShareManager({
  uiLanguage,
}: {
  uiLanguage: UILanguage;
}) {
  const text = COPY[uiLanguage];
  const [scope, setScope] = useState<PhrShareScope>("full");
  const [expiry, setExpiry] = useState<string>("");
  const [links, setLinks] = useState<PhrShare[]>([]);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [copiedToken, setCopiedToken] = useState("");
  const [revokingToken, setRevokingToken] = useState("");

  const onCreate = async () => {
    setCreating(true);
    setError("");
    try {
      const days = expiry.trim() ? Number(expiry) : null;
      const share = await createPhrShare(
        scope,
        Number.isFinite(days as number) ? days : null,
      );
      setLinks((prev) => [share, ...prev]);
    } catch (err) {
      setError(err instanceof Error ? err.message : text.createError);
    } finally {
      setCreating(false);
    }
  };

  const onRevoke = async (token: string) => {
    setRevokingToken(token);
    setError("");
    try {
      await revokePhrShare(token);
      setLinks((prev) => prev.filter((l) => l.share_token !== token));
    } catch (err) {
      setError(err instanceof Error ? err.message : text.revokeError);
    } finally {
      setRevokingToken("");
    }
  };

  const onCopy = async (token: string) => {
    try {
      await navigator.clipboard?.writeText(shareUrl(token));
      setCopiedToken(token);
      setTimeout(() => setCopiedToken(""), 1500);
    } catch {
      // Clipboard may be unavailable (insecure context); ignore silently.
    }
  };

  return (
    <section className="rounded-2xl border border-[#B6D4FE] bg-white p-5 shadow-sm dark:border-sky-700/60 dark:bg-slate-900/90">
      <p className="text-sm font-semibold text-[var(--text-primary)]">
        {text.title}
      </p>
      <p className="mt-1 text-[13px] leading-6 text-[var(--text-secondary)]">
        {text.description}
      </p>

      <div className="mt-3 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-bold uppercase tracking-[0.08em] text-[#374151] dark:text-slate-200">
            {text.scope}
          </span>
          <select
            className="input"
            value={scope}
            onChange={(e) => setScope(e.target.value as PhrShareScope)}
          >
            <option value="full">{text.scopeFull}</option>
            <option value="emergency_card">{text.scopeEmergency}</option>
          </select>
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-bold uppercase tracking-[0.08em] text-[#374151] dark:text-slate-200">
            {text.expiry}
          </span>
          <input
            inputMode="numeric"
            className="input w-36"
            placeholder={text.noExpiry}
            value={expiry}
            onChange={(e) => setExpiry(e.target.value.replace(/[^0-9]/g, ""))}
          />
        </label>
        <button
          type="button"
          onClick={onCreate}
          disabled={creating}
          className="inline-flex min-h-[38px] items-center rounded-lg border border-[#93C5FD] bg-[#EFF6FF] px-4 text-sm font-semibold text-[#1D4ED8] transition hover:bg-[#DBEAFE] disabled:cursor-not-allowed disabled:opacity-60 dark:border-sky-500/70 dark:bg-sky-500/18 dark:text-sky-100"
        >
          {creating ? text.creating : text.create}
        </button>
      </div>

      {error ? <p className="mt-3 text-sm text-rose-500">{error}</p> : null}

      <div className="mt-4">
        <p className="text-xs font-bold uppercase tracking-[0.08em] text-[#374151] dark:text-slate-200">
          {text.activeLinks}
        </p>
        {links.length === 0 ? (
          <p className="mt-2 text-[13px] text-[var(--text-secondary)]">
            {text.noLinks}
          </p>
        ) : (
          <ul className="mt-2 space-y-2">
            {links.map((link) => (
              <li
                key={link.share_token}
                className="flex flex-wrap items-center gap-2 rounded-2xl border border-[#93C5FD] bg-[#EEF6FF] p-3 dark:border-sky-700/70 dark:bg-slate-800/80"
              >
                <code className="min-w-0 flex-1 truncate text-[12px] text-[var(--text-primary)]">
                  {shareUrl(link.share_token)}
                </code>
                <span className="text-[11px] text-[var(--text-secondary)]">
                  {link.scope === "emergency_card"
                    ? text.scopeEmergency
                    : text.scopeFull}{" "}
                  · {text.expiresAt}:{" "}
                  {link.expires_at
                    ? new Date(link.expires_at).toLocaleDateString()
                    : text.never}
                </span>
                <button
                  type="button"
                  onClick={() => onCopy(link.share_token)}
                  className="rounded-full border border-slate-300 bg-slate-50 px-3 py-1 text-xs font-bold text-slate-700 transition hover:bg-slate-100 dark:border-slate-600/70 dark:bg-slate-700/40 dark:text-slate-200"
                >
                  {copiedToken === link.share_token ? text.copied : text.copy}
                </button>
                <button
                  type="button"
                  onClick={() => onRevoke(link.share_token)}
                  disabled={revokingToken === link.share_token}
                  className="rounded-full border border-rose-300 bg-rose-50 px-3 py-1 text-xs font-bold text-rose-700 transition hover:bg-rose-100 disabled:opacity-60 dark:border-rose-500/70 dark:bg-rose-500/15 dark:text-rose-100"
                >
                  {revokingToken === link.share_token
                    ? text.revoking
                    : text.revoke}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
