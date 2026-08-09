"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";

import {
  acknowledgeTransparencyNotice,
  getTransparencyNotice,
  isTransparencyNoticeEnabled,
  type TransparencyNotice,
} from "@/lib/compliance";
import {
  getStoredUILanguage,
  onUILanguageChange,
  type UILanguage,
} from "@/lib/ui-language";
import { t } from "@/lib/i18n/catalog";

/**
 * AI Transparency Notice gate (regulatory-compliance Requirement 1.1, 1.2, 1.6;
 * design §A, Property P9).
 *
 * When `NEXT_PUBLIC_COMPLIANCE_TRANSPARENCY_NOTICE_ENABLED` is on AND the
 * current notice version is unacknowledged, this intercepts the first medical
 * surface render with a blocking modal presenting the notice, and records the
 * acknowledgement through the existing endpoint before medical content is
 * served. With the flag off (the default) it renders nothing and makes no
 * network calls, so current behavior is preserved (Requirement 8.1, 8.2).
 *
 * It is deliberately resilient: any failure to read the notice leaves medical
 * content reachable (fail-open for safety, per design "Error Handling"), and
 * the emergency fast-path / disclaimers always still render.
 */

/** Route prefixes that present medical content and therefore require the notice. */
const MEDICAL_SURFACE_PREFIXES = [
  "/chat",
  "/phr",
  "/selfmed",
  "/careguard",
  "/council",
  "/scribe",
  "/research",
  "/dashboard",
];

function isMedicalSurface(pathname: string): boolean {
  return MEDICAL_SURFACE_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

function fallbackParagraphs(language: UILanguage): string[] {
  return [
    t(language, "compliance.transparency.fallbackBody.assistant"),
    t(language, "compliance.transparency.fallbackBody.scope"),
    t(language, "compliance.transparency.fallbackBody.limitations"),
    t(language, "compliance.transparency.fallbackBody.oversight"),
  ];
}

export default function TransparencyNoticeGate() {
  const pathname = usePathname();
  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");
  const [notice, setNotice] = useState<TransparencyNotice | null>(null);
  const [acknowledging, setAcknowledging] = useState(false);
  const [error, setError] = useState("");
  const acknowledgementButtonRef = useRef<HTMLButtonElement>(null);

  const enabled = isTransparencyNoticeEnabled();
  const onMedicalSurface = isMedicalSurface(pathname);

  useEffect(() => {
    setUiLanguage(getStoredUILanguage());
    return onUILanguageChange(setUiLanguage);
  }, []);

  useEffect(() => {
    if (!enabled || !onMedicalSurface) return;
    let cancelled = false;
    (async () => {
      try {
        const data = await getTransparencyNotice();
        if (cancelled) return;
        setNotice(data);
      } catch {
        // Fail open: an unreadable notice must not block access to care.
        if (!cancelled) setNotice(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [enabled, onMedicalSurface]);

  const onAcknowledge = useCallback(async () => {
    if (!notice) return;
    setAcknowledging(true);
    setError("");
    try {
      await acknowledgeTransparencyNotice(notice.version);
      setNotice((prev) =>
        prev
          ? { ...prev, acknowledged: true, acknowledged_version: prev.version }
          : prev,
      );
    } catch {
      // Do not surface raw transport errors on an End_User compliance gate.
      setError(t(uiLanguage, "compliance.transparency.acknowledgeError"));
    } finally {
      setAcknowledging(false);
    }
  }, [notice, uiLanguage]);

  const acknowledgementRequired = Boolean(
    enabled && onMedicalSurface && notice?.enabled && !notice.acknowledged,
  );

  // This is an acknowledgement-only regulatory gate: it deliberately has no
  // dismiss/Escape path. Keep focus in the one actionable control and lock the
  // document behind it while acknowledgement is required.
  useEffect(() => {
    if (!acknowledgementRequired) return;
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";
    const focusButton = () => acknowledgementButtonRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Tab") {
        event.preventDefault();
        focusButton();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    const timer = window.setTimeout(focusButton, 0);
    return () => {
      document.body.style.overflow = overflow;
      document.removeEventListener("keydown", onKeyDown);
      window.clearTimeout(timer);
    };
  }, [acknowledgementRequired]);

  // Nothing to render: flag off, off a medical surface, no notice, feature
  // disabled server-side, or already acknowledged.
  if (!enabled || !onMedicalSurface) return null;
  if (!notice || !notice.enabled || notice.acknowledged) return null;

  const title =
    notice.title?.[uiLanguage]?.trim() ||
    notice.title?.vi?.trim() ||
    t(uiLanguage, "compliance.transparency.fallbackTitle");
  const bodyText = notice.body?.[uiLanguage]?.trim() || notice.body?.vi?.trim();
  const paragraphs = bodyText
    ? bodyText.split(/\n{2,}|\n/).map((line) => line.trim()).filter(Boolean)
    : fallbackParagraphs(uiLanguage);

  return (
    <div
      className="fixed inset-0 z-[90] flex items-center justify-center bg-[var(--bg-canvas)] px-4 py-6"
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="transparency-notice-title"
        aria-describedby="transparency-notice-body"
        className="flex max-h-[88vh] w-full max-w-lg flex-col overflow-hidden rounded-[var(--radius-xl)] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)]"
      >
        <div className="border-b border-[color:var(--shell-border)] px-5 py-4">
          <p className="text-[10px] font-black uppercase tracking-[0.16em] text-[var(--text-brand)]">
            {t(uiLanguage, "compliance.transparency.badge")}
          </p>
          <h2
            id="transparency-notice-title"
            className="mt-1 text-lg font-bold text-[var(--text-primary)]"
          >
            {title}
          </h2>
        </div>

        <div
          id="transparency-notice-body"
          className="clara-scrollbar min-h-0 flex-1 space-y-3 overflow-y-auto px-5 py-4 text-sm leading-6 text-[var(--text-secondary)]"
        >
          {paragraphs.map((line, index) => (
            <p key={index}>{line}</p>
          ))}
          <p className="text-[11px] text-[var(--text-muted)]">
            {t(uiLanguage, "compliance.transparency.version")}: {notice.version}
          </p>
        </div>

        {error ? (
          <p
            role="alert"
            className="border-t border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-5 py-2 text-[12px] font-medium text-[var(--status-danger-text)]"
          >
            {error}
          </p>
        ) : null}

        <div className="flex items-center justify-end gap-2 border-t border-[color:var(--shell-border)] px-5 py-3">
          <button
            ref={acknowledgementButtonRef}
            type="button"
            onClick={onAcknowledge}
            disabled={acknowledging}
            className="inline-flex min-h-[42px] items-center rounded-[var(--radius-md)] border border-[color:var(--brand-600)] bg-[var(--brand-600)] px-4 text-sm font-semibold text-[var(--on-secondary-container)] transition hover:bg-[var(--brand-700)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--shell-border-strong)] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {acknowledging
              ? t(uiLanguage, "compliance.transparency.acknowledging")
              : t(uiLanguage, "compliance.transparency.acknowledge")}
          </button>
        </div>
      </div>
    </div>
  );
}
