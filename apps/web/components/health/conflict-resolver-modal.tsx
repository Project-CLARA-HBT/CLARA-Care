"use client";

import { useMemo } from "react";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Badge } from "@/components/ui/badge";

export interface ConflictResolverModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  resourceName?: string;
  clientDraft: Record<string, unknown>;
  serverState: Record<string, unknown>;
  changedFields?: string[];
  onKeepClient: () => void;
  onAcceptServer: () => void;
  locale?: "vi" | "en";
  isSubmitting?: boolean;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "(trống)";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function ConflictResolverModal({
  open,
  onClose,
  title,
  resourceName = "dữ liệu",
  clientDraft,
  serverState,
  changedFields,
  onKeepClient,
  onAcceptServer,
  locale = "vi",
  isSubmitting = false,
}: ConflictResolverModalProps) {
  const isEn = locale === "en";

  const diffKeys = useMemo(() => {
    if (changedFields && changedFields.length > 0) {
      return changedFields;
    }
    const allKeys = new Set([...Object.keys(clientDraft), ...Object.keys(serverState)]);
    const ignored = new Set(["base_version", "id", "created_at", "updated_at"]);
    const diffs: string[] = [];
    for (const key of allKeys) {
      if (ignored.has(key)) continue;
      if (JSON.stringify(clientDraft[key]) !== JSON.stringify(serverState[key])) {
        diffs.push(key);
      }
    }
    return diffs.length > 0 ? diffs : Array.from(allKeys).filter((k) => !ignored.has(k));
  }, [clientDraft, serverState, changedFields]);

  const defaultTitle = isEn
    ? `Conflict Detected: ${resourceName}`
    : `Xung đột dữ liệu: ${resourceName}`;

  const description = isEn
    ? "This record was updated by another action or source while you were editing. Review the differences below and choose how to proceed."
    : "Bản ghi này đã được cập nhật bởi một thao tác hoặc nguồn khác trong khi bạn đang sửa. Vui lòng đối chiếu sự khác biệt và chọn cách xử lý.";

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title || defaultTitle}
      description={description}
      size="lg"
      role="alertdialog"
      closeLabel={isEn ? "Close" : "Đóng"}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={isSubmitting}>
            {isEn ? "Cancel & Review" : "Hủy & Xem lại"}
          </Button>
          <Button
            variant="secondary"
            onClick={onAcceptServer}
            disabled={isSubmitting}
            icon="folder"
          >
            {isEn ? "Use Server Version" : "Chấp nhận bản máy chủ"}
          </Button>
          <Button
            variant="primary"
            onClick={onKeepClient}
            loading={isSubmitting}
            icon="check"
          >
            {isEn ? "Keep My Edits" : "Giữ thay đổi của tôi"}
          </Button>
        </>
      }
    >
      <div className="space-y-4" data-testid="conflict-resolver-content">
        <div
          role="alert"
          className="flex items-start gap-3 rounded-[var(--radius-md)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] p-3 text-xs text-[var(--status-warn-text)] sm:text-sm"
        >
          <Icon name="warning" size="1.2rem" className="mt-0.5 shrink-0" />
          <div>
            <span className="font-semibold">
              {isEn
                ? "Your local edits were preserved."
                : "Thay đổi của bạn đã được bảo toàn an toàn."}
            </span>
            <p className="mt-0.5 text-xs opacity-90">
              {isEn
                ? "Choose 'Keep My Edits' to overwrite with your version, or 'Use Server Version' to discard your local edits."
                : "Chọn 'Giữ thay đổi của tôi' để áp dụng lại bản sửa của bạn, hoặc 'Chấp nhận bản máy chủ' để sử dụng phiên bản mới nhất."}
            </p>
          </div>
        </div>

        <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] overflow-hidden">
          <div className="grid grid-cols-1 divide-y divide-[color:var(--shell-border)] sm:grid-cols-2 sm:divide-y-0 sm:divide-x">
            {/* Server Version Column */}
            <div className="bg-[var(--surface-muted)]/40 p-3 sm:p-4">
              <div className="flex items-center justify-between pb-2 border-b border-[color:var(--shell-border)]/50">
                <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">
                  {isEn ? "Server Version (Current)" : "Bản ghi trên máy chủ (Mới nhất)"}
                </span>
                <Badge tone="neutral">{isEn ? "Server" : "Máy chủ"}</Badge>
              </div>
              <dl className="mt-3 space-y-2.5 text-xs sm:text-sm">
                {diffKeys.map((key) => (
                  <div key={`server-${key}`} className="rounded-[var(--radius-sm)] bg-[var(--surface-panel)] p-2">
                    <dt className="font-medium text-[var(--text-muted)] text-[11px] uppercase">{key}</dt>
                    <dd className="mt-0.5 font-semibold text-[var(--text-primary)] break-words">
                      {formatValue(serverState[key])}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>

            {/* Client Draft Column */}
            <div className="bg-[var(--surface-brand-soft)]/20 p-3 sm:p-4">
              <div className="flex items-center justify-between pb-2 border-b border-[color:var(--shell-border)]/50">
                <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
                  {isEn ? "Your Draft (Local)" : "Thay đổi của bạn (Bản nháp)"}
                </span>
                <Badge tone="brand">{isEn ? "You" : "Bạn sửa"}</Badge>
              </div>
              <dl className="mt-3 space-y-2.5 text-xs sm:text-sm">
                {diffKeys.map((key) => (
                  <div key={`client-${key}`} className="rounded-[var(--radius-sm)] bg-[var(--surface-panel)] border border-[color:var(--brand-500)]/30 p-2">
                    <dt className="font-medium text-[var(--text-brand)] text-[11px] uppercase">{key}</dt>
                    <dd className="mt-0.5 font-semibold text-[var(--text-primary)] break-words">
                      {formatValue(clientDraft[key])}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        </div>
      </div>
    </Modal>
  );
}

export default ConflictResolverModal;
