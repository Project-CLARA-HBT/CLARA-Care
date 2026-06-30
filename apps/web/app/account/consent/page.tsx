"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import PageShell from "@/components/ui/page-shell";
import {
  grantConsent,
  isGranularConsentEnabled,
  listConsents,
  withdrawConsent,
  type ConsentPurpose,
  type ConsentRecord,
} from "@/lib/compliance";
import {
  getStoredUILanguage,
  onUILanguageChange,
  type UILanguage,
} from "@/lib/ui-language";

/**
 * Consent Center (regulatory-compliance Requirement 2.6, Property P10; PHR
 * Requirement 19.5).
 *
 * Self-service per-purpose consent toggles backed by the append-only consent
 * ledger. Withdrawal is exactly as easy as granting (a single toggle). All
 * mutations go through the shared `http-client`, which attaches the CSRF header
 * for cookie-authenticated requests.
 *
 * PHR sharing and personalization consents are surfaced HERE through the unified
 * purpose ledger rather than as a PHR-only toggle (PHR Req 19.5).
 *
 * The surface activates only when `NEXT_PUBLIC_COMPLIANCE_GRANULAR_CONSENT_ENABLED`
 * is on; otherwise it shows a "feature unavailable" notice and current behavior
 * is preserved (Requirement 8.1, 8.2).
 */

type PurposeCopy = {
  label: Record<UILanguage, string>;
  desc: Record<UILanguage, string>;
  /** Core service consent is the lawful basis for the product and is locked on. */
  locked?: boolean;
};

const PURPOSE_ORDER: ConsentPurpose[] = [
  "core_service",
  "personalization",
  "research",
  "cross_border_processing",
  "sharing",
];

const PURPOSE_COPY: Record<ConsentPurpose, PurposeCopy> = {
  core_service: {
    label: { vi: "Dịch vụ cốt lõi", en: "Core service" },
    desc: {
      vi: "Xử lý cần thiết để cung cấp chức năng cốt lõi của CLARA. Đây là căn cứ pháp lý của dịch vụ và không thể tắt khi đang dùng.",
      en: "Processing necessary to provide CLARA's core functionality. This is the lawful basis for the service and cannot be turned off while in use.",
    },
    locked: true,
  },
  personalization: {
    label: { vi: "Cá nhân hóa", en: "Personalization" },
    desc: {
      vi: "Dùng hồ sơ sức khỏe cá nhân (PHR), tủ thuốc và dị ứng của bạn để cá nhân hóa câu trả lời và kiểm tra tương tác thuốc.",
      en: "Use your personal health record (PHR), medicine cabinet, and allergies to personalize answers and interaction checks.",
    },
  },
  research: {
    label: { vi: "Nghiên cứu", en: "Research use" },
    desc: {
      vi: "Cho phép dùng dữ liệu đã khử định danh để cải thiện chất lượng truy xuất và kiểm chứng bằng chứng.",
      en: "Allow de-identified data to be used to improve retrieval quality and evidence verification.",
    },
  },
  cross_border_processing: {
    label: {
      vi: "Xử lý bởi mô hình bên thứ ba / xuyên biên giới",
      en: "Third-party / cross-border model processing",
    },
    desc: {
      vi: "Cho phép gửi dữ liệu cần thiết tới mô hình ngôn ngữ ngoài lãnh thổ Việt Nam. Khi tắt, hệ thống dùng đường xử lý nội địa hoặc trả lời dự phòng nội bộ.",
      en: "Allow necessary data to be sent to a language model outside Vietnam. When off, the system uses an in-country path or a local fallback answer.",
    },
  },
  sharing: {
    label: { vi: "Chia sẻ", en: "Sharing" },
    desc: {
      vi: "Cho phép tạo liên kết chia sẻ chỉ đọc cho hồ sơ và cuộc trò chuyện của bạn (ví dụ chia sẻ PHR với người chăm sóc hoặc bác sĩ).",
      en: "Allow creating read-only share links for your records and conversations (e.g. sharing your PHR with a caregiver or clinician).",
    },
  },
  ai_transparency: {
    label: { vi: "Minh bạch AI", en: "AI transparency" },
    desc: {
      vi: "Xác nhận thông báo minh bạch về hệ thống AI.",
      en: "Acknowledgement of the AI system transparency notice.",
    },
  },
};

const COPY = {
  vi: {
    title: "Trung tâm đồng thuận",
    description:
      "Cấp hoặc rút đồng thuận cho từng mục đích xử lý dữ liệu cá nhân của bạn. Rút đồng thuận dễ dàng như khi cấp.",
    loading: "Đang tải trạng thái đồng thuận...",
    loadError: "Không thể tải trạng thái đồng thuận. Vui lòng thử lại.",
    disabled:
      "Tính năng quản lý đồng thuận theo mục đích hiện chưa được bật cho môi trường này.",
    granted: "Đã đồng ý",
    notGranted: "Chưa đồng ý",
    locked: "Bắt buộc",
    enableAction: "Bật",
    disableAction: "Tắt",
    saving: "Đang lưu...",
    sensitiveNote:
      "Dữ liệu sức khỏe, truy vấn lâm sàng, PHR, tủ thuốc, dị ứng và bệnh nền được coi là dữ liệu cá nhân nhạy cảm theo Nghị định 13/2023/NĐ-CP và chỉ được xử lý theo đồng thuận của bạn.",
    updatedAt: "Cập nhật",
  },
  en: {
    title: "Consent Center",
    description:
      "Grant or withdraw consent for each purpose your personal data is processed for. Withdrawal is as easy as granting.",
    loading: "Loading consent status...",
    loadError: "Could not load consent status. Please try again.",
    disabled:
      "Purpose-based consent management is not enabled for this environment yet.",
    granted: "Granted",
    notGranted: "Not granted",
    locked: "Required",
    enableAction: "Enable",
    disableAction: "Disable",
    saving: "Saving...",
    sensitiveNote:
      "Health data, clinical queries, PHR, medicine cabinet, allergies, and conditions are treated as sensitive personal data under Decree 13/2023/NĐ-CP and are processed only per your consent.",
    updatedAt: "Updated",
  },
} as const;

export default function ConsentCenterPage() {
  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pending, setPending] = useState<ConsentPurpose | null>(null);
  const [consentMap, setConsentMap] = useState<Record<string, ConsentRecord>>({});

  const text = useMemo(() => COPY[uiLanguage], [uiLanguage]);
  const flagOn = isGranularConsentEnabled();

  useEffect(() => {
    setUiLanguage(getStoredUILanguage());
    return onUILanguageChange(setUiLanguage);
  }, []);

  const refresh = useCallback(async () => {
    if (!flagOn) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await listConsents();
      setEnabled(Boolean(data.enabled));
      const map: Record<string, ConsentRecord> = {};
      for (const record of data.consents ?? []) {
        map[record.purpose] = record;
      }
      setConsentMap(map);
    } catch {
      setError(text.loadError);
    } finally {
      setLoading(false);
    }
  }, [flagOn, text.loadError]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const onToggle = useCallback(
    async (purpose: ConsentPurpose, nextGranted: boolean) => {
      setPending(purpose);
      setError("");
      // Optimistic update; reconciled by the refresh below.
      setConsentMap((prev) => ({
        ...prev,
        [purpose]: { ...prev[purpose], purpose, granted: nextGranted },
      }));
      try {
        if (nextGranted) {
          await grantConsent(purpose);
        } else {
          await withdrawConsent(purpose);
        }
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : text.loadError);
        await refresh();
      } finally {
        setPending(null);
      }
    },
    [refresh, text.loadError],
  );

  const showDisabled = !flagOn || (!loading && !enabled);

  return (
    <PageShell variant="plain" title={text.title} description={text.description}>
      <div className="space-y-4">
        <p className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-3 text-[13px] leading-6 text-[var(--text-secondary)]">
          {text.sensitiveNote}
        </p>

        {showDisabled ? (
          <p
            role="status"
            className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3 text-sm text-[var(--text-secondary)]"
          >
            {text.disabled}
          </p>
        ) : loading ? (
          <p className="text-sm text-[var(--text-secondary)]">{text.loading}</p>
        ) : (
          <>
            {error ? (
              <p
                role="alert"
                className="rounded-xl border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 py-2.5 text-sm font-medium text-[var(--status-danger-text)]"
              >
                {error}
              </p>
            ) : null}

            <ul className="space-y-3">
              {PURPOSE_ORDER.map((purpose) => {
                const copy = PURPOSE_COPY[purpose];
                const record = consentMap[purpose];
                const granted = copy.locked ? true : Boolean(record?.granted);
                const isPending = pending === purpose;
                return (
                  <li
                    key={purpose}
                    className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <p className="text-sm font-bold text-[var(--text-primary)]">
                          {copy.label[uiLanguage]}
                        </p>
                        <p className="mt-1 text-[13px] leading-6 text-[var(--text-secondary)]">
                          {copy.desc[uiLanguage]}
                        </p>
                        {record?.updated_at ? (
                          <p className="mt-1 text-[11px] text-[var(--text-muted)]">
                            {text.updatedAt}:{" "}
                            {new Date(record.updated_at).toLocaleString()}
                          </p>
                        ) : null}
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-1.5">
                        <span
                          className={[
                            "rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.08em]",
                            granted
                              ? "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]"
                              : "border-[color:var(--status-neutral-border)] bg-[var(--status-neutral-bg)] text-[var(--status-neutral-text)]",
                          ].join(" ")}
                        >
                          {copy.locked
                            ? text.locked
                            : granted
                              ? text.granted
                              : text.notGranted}
                        </span>
                        {copy.locked ? null : (
                          <button
                            type="button"
                            role="switch"
                            aria-checked={granted}
                            aria-label={copy.label[uiLanguage]}
                            disabled={isPending}
                            onClick={() => void onToggle(purpose, !granted)}
                            className={[
                              "inline-flex h-6 w-11 items-center rounded-full border transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--shell-border-strong)] disabled:cursor-not-allowed disabled:opacity-60",
                              granted
                                ? "border-[color:var(--brand-600)] bg-[var(--brand-600)]"
                                : "border-[color:var(--shell-border)] bg-[var(--surface-muted)]",
                            ].join(" ")}
                          >
                            <span
                              aria-hidden="true"
                              className={[
                                "ml-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform motion-reduce:transition-none",
                                granted ? "translate-x-5" : "translate-x-0",
                              ].join(" ")}
                            />
                          </button>
                        )}
                        {isPending ? (
                          <span className="text-[10px] text-[var(--text-muted)]">
                            {text.saving}
                          </span>
                        ) : null}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </div>
    </PageShell>
  );
}
