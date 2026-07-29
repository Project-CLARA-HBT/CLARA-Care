"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import PageShell from "@/components/ui/page-shell";
import Button from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { SurfaceCard, InlineError } from "@/components/ui/surface";
import {
  isDsarEnabled,
  listDsarRequests,
  requestDsarExport,
  submitDsarRequest,
  type DsarKind,
  type DsarRequestRecord,
} from "@/lib/compliance";
import { triggerBlobDownload } from "@/app/chat/_v2/lib/chat-format";
import {
  getStoredUILanguage,
  onUILanguageChange,
  type UILanguage,
} from "@/lib/ui-language";

/**
 * DSAR self-service (regulatory-compliance Requirement 3, design §C, Property
 * P7).
 *
 * Lets an authenticated data subject exercise their PDPD rights: export
 * (portability), correct, delete, restrict processing, and withdraw consent.
 * Each request is acknowledged and tracked against the statutory window by the
 * backend; this surface records the request type only (no extra PII).
 *
 * The surface activates only when `NEXT_PUBLIC_COMPLIANCE_DSAR_ENABLED` is on;
 * otherwise it shows a "feature unavailable" notice and current behavior is
 * preserved (Requirement 8.1, 8.2).
 */

type ActionCopy = {
  kind: DsarKind;
  label: Record<UILanguage, string>;
  desc: Record<UILanguage, string>;
  /** Destructive actions require an explicit confirm step. */
  destructive?: boolean;
};

const ACTIONS: ActionCopy[] = [
  {
    kind: "export",
    label: { vi: "Xuất dữ liệu", en: "Export my data" },
    desc: {
      vi: "Tải về bản sao có thể đọc bằng máy của toàn bộ dữ liệu cá nhân CLARA đang lưu về bạn (hồ sơ, PHR, tủ thuốc, đồng thuận).",
      en: "Download a machine-readable copy of all personal data CLARA holds about you (profile, PHR, medicine cabinet, consents).",
    },
  },
  {
    kind: "correct",
    label: { vi: "Yêu cầu chỉnh sửa", en: "Request correction" },
    desc: {
      vi: "Yêu cầu chỉnh sửa dữ liệu cá nhân không chính xác.",
      en: "Request correction of inaccurate personal data.",
    },
  },
  {
    kind: "restrict",
    label: { vi: "Hạn chế xử lý", en: "Restrict processing" },
    desc: {
      vi: "Yêu cầu tạm dừng hoặc hạn chế việc xử lý dữ liệu cá nhân của bạn.",
      en: "Request that processing of your personal data be paused or restricted.",
    },
  },
  {
    kind: "withdraw",
    label: { vi: "Rút đồng thuận", en: "Withdraw consent" },
    desc: {
      vi: "Rút đồng thuận xử lý. Bạn cũng có thể quản lý theo từng mục đích tại Trung tâm đồng thuận.",
      en: "Withdraw processing consent. You can also manage this per-purpose in the Consent Center.",
    },
  },
  {
    kind: "delete",
    label: { vi: "Xóa dữ liệu", en: "Delete my data" },
    desc: {
      vi: "Yêu cầu xóa hoặc ẩn danh hóa dữ liệu cá nhân của bạn, trừ dữ liệu phải lưu theo nghĩa vụ pháp lý (được công bố bên dưới).",
      en: "Request deletion or anonymization of your personal data, except data retained under disclosed legal obligations.",
    },
    destructive: true,
  },
];

const STATUS_LABELS: Record<
  DsarRequestRecord["status"],
  Record<UILanguage, string>
> = {
  received: { vi: "Đã tiếp nhận", en: "Received" },
  in_progress: { vi: "Đang xử lý", en: "In progress" },
  fulfilled: { vi: "Đã hoàn tất", en: "Fulfilled" },
  rejected: { vi: "Đã từ chối", en: "Rejected" },
};

const COPY = {
  vi: {
    title: "Dữ liệu của tôi",
    description:
      "Thực hiện quyền của chủ thể dữ liệu theo Nghị định 13/2023/NĐ-CP: truy cập, chỉnh sửa, xóa, hạn chế xử lý và rút đồng thuận.",
    disabled:
      "Tính năng yêu cầu quyền dữ liệu (DSAR) hiện chưa được bật cho môi trường này.",
    loading: "Đang tải các yêu cầu của bạn...",
    loadError: "Không thể tải danh sách yêu cầu. Vui lòng thử lại.",
    submit: "Gửi yêu cầu",
    submitting: "Đang gửi...",
    exporting: "Đang chuẩn bị bản xuất...",
    download: "Tải xuống",
    historyTitle: "Lịch sử yêu cầu",
    noHistory: "Bạn chưa gửi yêu cầu nào.",
    retentionNote:
      "Lưu ý: một số bản ghi audit/tuân thủ không chứa dữ liệu định danh sẽ được giữ lại theo nghĩa vụ pháp lý ngay cả sau khi xóa.",
    acknowledged: "Đã ghi nhận yêu cầu. Chúng tôi sẽ xử lý trong thời hạn luật định.",
    submittedAt: "Gửi lúc",
    dueAt: "Hạn xử lý",
  },
  en: {
    title: "My data",
    description:
      "Exercise your data-subject rights under Decree 13/2023/NĐ-CP: access, correction, deletion, restriction of processing, and consent withdrawal.",
    disabled: "Data-subject requests (DSAR) are not enabled for this environment yet.",
    loading: "Loading your requests...",
    loadError: "Could not load your requests. Please try again.",
    submit: "Submit request",
    submitting: "Submitting...",
    exporting: "Preparing export...",
    download: "Download",
    historyTitle: "Request history",
    noHistory: "You have not submitted any requests yet.",
    retentionNote:
      "Note: certain audit/compliance records that contain no identifying data are retained under legal obligations even after deletion.",
    acknowledged:
      "Your request has been recorded. We will process it within the statutory window.",
    submittedAt: "Submitted",
    dueAt: "Due",
  },
} as const;

export default function DataRightsPage() {
  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [pendingKind, setPendingKind] = useState<DsarKind | null>(null);
  const [requests, setRequests] = useState<DsarRequestRecord[]>([]);

  const text = useMemo(() => COPY[uiLanguage], [uiLanguage]);
  const flagOn = isDsarEnabled();

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
      const data = await listDsarRequests();
      setEnabled(Boolean(data.enabled));
      setRequests(data.requests ?? []);
    } catch {
      setError(text.loadError);
    } finally {
      setLoading(false);
    }
  }, [flagOn, text.loadError]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const onExport = useCallback(async () => {
    setPendingKind("export");
    setError("");
    setNotice("");
    try {
      const bundle = await requestDsarExport();
      const blob = new Blob([JSON.stringify(bundle, null, 2)], {
        type: "application/json",
      });
      const stamp = new Date().toISOString().slice(0, 10);
      triggerBlobDownload(blob, `clara-data-export-${stamp}.json`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : text.loadError);
    } finally {
      setPendingKind(null);
    }
  }, [refresh, text.loadError]);

  const onSubmit = useCallback(
    async (kind: Exclude<DsarKind, "export" | "delete">) => {
      setPendingKind(kind);
      setError("");
      setNotice("");
      try {
        await submitDsarRequest(kind);
        setNotice(text.acknowledged);
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : text.loadError);
      } finally {
        setPendingKind(null);
      }
    },
    [refresh, text.acknowledged, text.loadError],
  );

  const isEn = uiLanguage === "en";
  const showDisabled = !flagOn || (!loading && !enabled);

  return (
    <PageShell variant="plain" title={text.title} description={text.description}>
      <div className="space-y-4">
        {showDisabled ? (
          <p
            role="status"
            className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3 text-sm text-[var(--text-secondary)]"
          >
            {text.disabled}
          </p>
        ) : (
          <>
            {notice ? (
              <p
                role="status"
                className="rounded-[var(--radius-lg)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-4 py-2.5 text-sm font-medium text-[var(--status-ok-text)]"
              >
                {notice}
              </p>
            ) : null}
            {error ? <InlineError message={error} /> : null}

            <ul className="grid gap-3 md:grid-cols-2">
              {ACTIONS.map((action) => {
                const isPending = pendingKind === action.kind;
                const isExport = action.kind === "export";
                return (
                  <SurfaceCard
                    key={action.kind}
                    className="flex flex-col p-4"
                  >
                    <p className="text-sm font-bold text-[var(--text-primary)]">
                      {action.label[uiLanguage]}
                    </p>
                    <p className="mt-1 flex-1 text-[13px] leading-6 text-[var(--text-secondary)]">
                      {action.desc[uiLanguage]}
                    </p>
                    {action.destructive && action.kind === "delete" ? (
                      <p className="mt-2 text-[11px] leading-5 text-[var(--text-muted)]">
                        {text.retentionNote}
                      </p>
                    ) : null}

                    {action.destructive && action.kind === "delete" ? (
                      <div className="mt-3">
                        <Button
                          as="link"
                          href="/account/data/delete/review"
                          variant="danger"
                          size="sm"
                        >
                          {action.label[uiLanguage]}
                        </Button>
                      </div>
                    ) : (
                      <div className="mt-3">
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={isPending}
                          onClick={() =>
                            isExport
                              ? void onExport()
                              : void onSubmit(
                                  action.kind as Exclude<DsarKind, "export" | "delete">,
                                )
                          }
                        >
                          {isPending
                            ? isExport
                              ? text.exporting
                              : text.submitting
                            : isExport
                              ? text.download
                              : text.submit}
                        </Button>
                      </div>
                    )}
                  </SurfaceCard>
                );
              })}
            </ul>

            <SurfaceCard className="p-4">
              <p className="text-sm font-bold text-[var(--text-primary)]">
                {text.historyTitle}
              </p>
              {loading ? (
                <p className="mt-2 text-sm text-[var(--text-secondary)]">
                  {text.loading}
                </p>
              ) : requests.length ? (
                <ul className="mt-3 space-y-2">
                  {requests.map((request) => (
                    <li
                      key={request.id}
                      className="flex items-center justify-between gap-3 rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2"
                    >
                      <div className="min-w-0">
                        <p className="text-[13px] font-semibold text-[var(--text-primary)]">
                          {ACTIONS.find((a) => a.kind === request.kind)?.label[
                            uiLanguage
                          ] ?? request.kind}
                        </p>
                        <p className="text-[11px] text-[var(--text-muted)]">
                          {request.created_at
                            ? `${text.submittedAt}: ${new Date(request.created_at).toLocaleString()}`
                            : ""}
                          {request.due_at
                            ? ` · ${text.dueAt}: ${new Date(request.due_at).toLocaleDateString()}`
                            : ""}
                        </p>
                      </div>
                      <Badge tone="neutral">
                        {STATUS_LABELS[request.status]?.[uiLanguage] ??
                          request.status}
                      </Badge>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-sm text-[var(--text-muted)]">
                  {isEn ? COPY.en.noHistory : COPY.vi.noHistory}
                </p>
              )}
            </SurfaceCard>
          </>
        )}
      </div>
    </PageShell>
  );
}
