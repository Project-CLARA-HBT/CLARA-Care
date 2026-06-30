"use client";

import { useCallback, useEffect, useState } from "react";
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

const FALLBACK_TITLE: Record<UILanguage, string> = {
  vi: "Thông báo minh bạch về hệ thống AI",
  en: "AI System Transparency Notice",
};

const FALLBACK_BODY: Record<UILanguage, string[]> = {
  vi: [
    "Bạn đang tương tác với CLARA — một hệ thống trí tuệ nhân tạo hỗ trợ thông tin y tế.",
    "CLARA cung cấp thông tin tham khảo và hỗ trợ ra quyết định; CLARA KHÔNG thay thế bác sĩ hoặc nhân viên y tế có giấy phép, không kê đơn và không đưa ra chẩn đoán xác định.",
    "Câu trả lời có thể chưa đầy đủ hoặc chưa chính xác. Hãy luôn tham vấn chuyên môn y tế trước khi hành động.",
    "Theo Luật Trí tuệ nhân tạo số 134/2025/QH15, CLARA được phân loại là hệ thống AI rủi ro cao trong lĩnh vực y tế và luôn duy trì sự giám sát của con người.",
  ],
  en: [
    "You are interacting with CLARA — an artificial-intelligence medical information assistant.",
    "CLARA provides reference information and decision support; it does NOT replace a licensed clinician, does not prescribe, and does not give a definitive diagnosis.",
    "Answers may be incomplete or inaccurate. Always review with a qualified clinician before acting.",
    "Under the Law on Artificial Intelligence No. 134/2025/QH15, CLARA is classified as a high-risk AI system in the health domain and keeps a human in oversight.",
  ],
};

export default function TransparencyNoticeGate() {
  const pathname = usePathname();
  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");
  const [notice, setNotice] = useState<TransparencyNotice | null>(null);
  const [acknowledging, setAcknowledging] = useState(false);
  const [error, setError] = useState("");

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
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : uiLanguage === "en"
            ? "Could not record acknowledgement. Please try again."
            : "Không thể ghi nhận xác nhận. Vui lòng thử lại.",
      );
    } finally {
      setAcknowledging(false);
    }
  }, [notice, uiLanguage]);

  // Nothing to render: flag off, off a medical surface, no notice, feature
  // disabled server-side, or already acknowledged.
  if (!enabled || !onMedicalSurface) return null;
  if (!notice || !notice.enabled || notice.acknowledged) return null;

  const isEn = uiLanguage === "en";
  const title =
    notice.title?.[uiLanguage]?.trim() ||
    notice.title?.vi?.trim() ||
    FALLBACK_TITLE[uiLanguage];
  const bodyText = notice.body?.[uiLanguage]?.trim() || notice.body?.vi?.trim();
  const paragraphs = bodyText
    ? bodyText.split(/\n{2,}|\n/).map((line) => line.trim()).filter(Boolean)
    : FALLBACK_BODY[uiLanguage];

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
        className="flex max-h-[88vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-2xl"
      >
        <div className="border-b border-[color:var(--shell-border)] px-5 py-4">
          <p className="text-[10px] font-black uppercase tracking-[0.16em] text-[var(--text-brand)]">
            {isEn ? "AI Transparency · Law 134/2025" : "Minh bạch AI · Luật 134/2025"}
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
            {isEn ? "Notice version" : "Phiên bản thông báo"}: {notice.version}
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
            type="button"
            onClick={onAcknowledge}
            disabled={acknowledging}
            className="inline-flex min-h-[42px] items-center rounded-xl border border-[color:var(--brand-600)] bg-[var(--brand-600)] px-4 text-sm font-semibold text-white transition hover:bg-[var(--brand-700)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--shell-border-strong)] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {acknowledging
              ? isEn
                ? "Recording..."
                : "Đang ghi nhận..."
              : isEn
                ? "I understand and continue"
                : "Tôi đã hiểu và tiếp tục"}
          </button>
        </div>
      </div>
    </div>
  );
}
