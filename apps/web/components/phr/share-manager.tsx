"use client";

import { useState } from "react";
import {
  createPhrShare,
  revokePhrShare,
  type PhrShare,
  type PhrShareScope,
} from "@/lib/phr";
import { formatLocaleDate, t, type UITranslationKey } from "@/lib/i18n/catalog";
import type { UILanguage } from "@/lib/ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";

/**
 * Read-only share manager (personal-health-record Requirement 12.1, 12.3).
 * Creates scoped share links (full record or emergency card only) with an
 * optional expiry, lists links created in this session, and revokes them. The
 * backend rejects creation (428) when sharing consent is absent — that message
 * is surfaced inline. Rendered only when the `sharing` capability is effective
 * (Requirement 18.1).
 */

function shareUrl(token: string): string {
  if (typeof window === "undefined") return token;
  return `${window.location.origin}/phr/shared/${token}`;
}

export default function ShareManager({
  uiLanguage,
}: {
  uiLanguage: UILanguage;
}) {
  const copy = (key: UITranslationKey) => t(uiLanguage, key);
  const [scope, setScope] = useState<PhrShareScope>("full");
  const [expiry, setExpiry] = useState<string>("");
  const [links, setLinks] = useState<PhrShare[]>([]);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [copiedToken, setCopiedToken] = useState("");
  const [revokingShareId, setRevokingShareId] = useState<number | null>(null);

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
      setError(safeUserFacingError(err, copy("phr.share.createError")));
    } finally {
      setCreating(false);
    }
  };

  const onRevoke = async (shareId: number) => {
    setRevokingShareId(shareId);
    setError("");
    try {
      await revokePhrShare(shareId);
      setLinks((prev) => prev.filter((l) => l.share_id !== shareId));
    } catch (err) {
      setError(safeUserFacingError(err, copy("phr.share.revokeError")));
    } finally {
      setRevokingShareId(null);
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
        {copy("phr.share.title")}
      </p>
      <p className="mt-1 text-[13px] leading-6 text-[var(--text-secondary)]">
        {copy("phr.share.description")}
      </p>

      <div className="mt-3 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-bold uppercase tracking-[0.08em] text-[#374151] dark:text-slate-200">
            {copy("phr.share.scope")}
          </span>
          <select
            className="input"
            value={scope}
            onChange={(e) => setScope(e.target.value as PhrShareScope)}
          >
            <option value="full">{copy("phr.share.scopeFull")}</option>
            <option value="emergency_card">{copy("phr.share.scopeEmergency")}</option>
          </select>
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-bold uppercase tracking-[0.08em] text-[#374151] dark:text-slate-200">
            {copy("phr.share.expiry")}
          </span>
          <input
            inputMode="numeric"
            className="input w-36"
            placeholder={copy("phr.share.noExpiry")}
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
          {creating ? copy("phr.share.creating") : copy("phr.share.create")}
        </button>
      </div>

      {error ? <p className="mt-3 text-sm text-rose-500">{error}</p> : null}

      <div className="mt-4">
        <p className="text-xs font-bold uppercase tracking-[0.08em] text-[#374151] dark:text-slate-200">
          {copy("phr.share.activeLinks")}
        </p>
        {links.length === 0 ? (
          <p className="mt-2 text-[13px] text-[var(--text-secondary)]">
            {copy("phr.share.noLinks")}
          </p>
        ) : (
          <ul className="mt-2 space-y-2">
            {links.map((link) => (
              <li
                key={link.share_id}
                className="flex flex-wrap items-center gap-2 rounded-2xl border border-[#93C5FD] bg-[#EEF6FF] p-3 dark:border-sky-700/70 dark:bg-slate-800/80"
              >
                <code className="min-w-0 flex-1 truncate text-[12px] text-[var(--text-primary)]">
                  {shareUrl(link.share_token)}
                </code>
                <span className="text-[11px] text-[var(--text-secondary)]">
                  {link.scope === "emergency_card"
                    ? copy("phr.share.scopeEmergency")
                    : copy("phr.share.scopeFull")}{" "}
                  · {copy("phr.share.expiresAt")}: {" "}
                  {link.expires_at
                    ? formatLocaleDate(uiLanguage, link.expires_at)
                    : copy("phr.share.never")}
                </span>
                <button
                  type="button"
                  onClick={() => onCopy(link.share_token)}
                  className="rounded-full border border-slate-300 bg-slate-50 px-3 py-1 text-xs font-bold text-slate-700 transition hover:bg-slate-100 dark:border-slate-600/70 dark:bg-slate-700/40 dark:text-slate-200"
                >
                  {copiedToken === link.share_token
                    ? copy("phr.share.copied")
                    : copy("phr.share.copy")}
                </button>
                <button
                  type="button"
                  onClick={() => onRevoke(link.share_id)}
                  disabled={revokingShareId === link.share_id}
                  className="rounded-full border border-rose-300 bg-rose-50 px-3 py-1 text-xs font-bold text-rose-700 transition hover:bg-rose-100 disabled:opacity-60 dark:border-rose-500/70 dark:bg-rose-500/15 dark:text-rose-100"
                >
                  {revokingShareId === link.share_id
                    ? copy("phr.share.revoking")
                    : copy("phr.share.revoke")}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
