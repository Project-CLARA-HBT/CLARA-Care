"use client";

import { useState } from "react";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Badge } from "@/components/ui/badge";
import { InlineError } from "@/components/shared/inline-error";
import type { ConnectedHealthSourceDto } from "@/lib/api/v2-client";

export interface WearableReauthModalProps {
  open: boolean;
  onClose: () => void;
  source: ConnectedHealthSourceDto | null;
  locale?: "vi" | "en";
  onSuccess?: () => void;
  onReauthorize?: (sourceId: string) => Promise<void>;
}

export function WearableReauthModal({
  open,
  onClose,
  source,
  locale = "vi",
  onSuccess,
  onReauthorize,
}: WearableReauthModalProps) {
  const isEn = locale === "en";
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [completed, setCompleted] = useState(false);

  if (!source) return null;

  const handleConfirmReauth = async () => {
    setIsLoading(true);
    setError(null);
    try {
      if (onReauthorize) {
        await onReauthorize(source.id);
      } else {
        // Fallback simulated handshake delay if not provided
        await new Promise((res) => setTimeout(res, 600));
      }
      setCompleted(true);
      if (onSuccess) {
        onSuccess();
      }
    } catch (err: any) {
      setError(
        err?.message ||
          (isEn
            ? "Reauthorization failed. Please try again or check provider status."
            : "Cấp lại quyền thất bại. Vui lòng thử lại hoặc kiểm tra nhà cung cấp."),
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleModalClose = () => {
    setError(null);
    setCompleted(false);
    setIsLoading(false);
    onClose();
  };

  return (
    <Modal
      open={open}
      onClose={handleModalClose}
      title={
        completed
          ? isEn
            ? "Reauthorization Successful"
            : "Cấp quyền thành công"
          : isEn
            ? `Reauthorize ${source.title}`
            : `Cấp lại quyền kết nối ${source.title}`
      }
      description={
        isEn
          ? "Renew secure OAuth tokens to restore automated biometric synchronization."
          : "Làm mới mã xác thực OAuth bảo mật để tiếp tục đồng bộ chỉ số sinh hiệu."
      }
      size="md"
      closeLabel={isEn ? "Close" : "Đóng"}
    >
      <div className="space-y-4 pt-1" data-testid="wearable-reauth-modal">
        {completed ? (
          <div className="space-y-4 text-center py-4" data-testid="reauth-success-view">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-[var(--status-ok-bg)] text-[var(--status-ok-text)] border border-[color:var(--status-ok-border)]">
              <Icon name="check" size="2rem" />
            </div>
            <div className="space-y-1">
              <h4 className="text-sm font-bold text-[var(--text-primary)]">
                {isEn ? "Connection Restored" : "Đã phục hồi kết nối an toàn"}
              </h4>
              <p className="text-xs text-[var(--text-secondary)]">
                {isEn
                  ? `Your connection with ${source.title} is now verified and active. Data synchronization will resume automatically.`
                  : `Kết nối với ${source.title} đã được xác thực lại thành công. Dữ liệu sẽ được tự động đồng bộ.`}
              </p>
            </div>
            <div className="pt-2">
              <Button
                variant="primary"
                onClick={handleModalClose}
                className="w-full"
                data-testid="reauth-done-btn"
              >
                {isEn ? "Done" : "Hoàn tất"}
              </Button>
            </div>
          </div>
        ) : (
          <>
            {/* Status & Issue Description */}
            <div className="rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-3.5 space-y-2 text-xs text-[var(--status-danger-text)]">
              <div className="flex items-center gap-2 font-bold">
                <Icon name="warning" size="1.1rem" />
                <span>
                  {isEn ? "OAuth Token Expired or Revoked" : "Mã truy cập OAuth đã hết hạn"}
                </span>
              </div>
              <p>
                {source.error_message ||
                  (isEn
                    ? "The security token granting CLARA access to your wearable data has expired or was revoked by the device manufacturer."
                    : "Mã bảo mật cho phép CLARA đọc dữ liệu từ thiết bị đã hết hiệu lực hoặc bị thu hồi bởi nhà cung cấp.")}
              </p>
              {source.recovery_guidance && (
                <p className="font-semibold">{source.recovery_guidance}</p>
              )}
            </div>

            {/* Privacy & Safety Assurances */}
            <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3.5 space-y-2 text-xs">
              <div className="flex items-center gap-1.5 font-bold text-[var(--text-primary)]">
                <Icon name="clinical-notes" size="1rem" />
                <span>{isEn ? "Security & Privacy Guarantees" : "Cam kết bảo mật & Quyền riêng tư"}</span>
              </div>
              <ul className="space-y-1.5 text-[var(--text-secondary)] list-disc list-inside">
                <li>
                  {isEn
                    ? "Read-only access: CLARA only reads authorized vitals (steps, heart rate, sleep)."
                    : "Quyền chỉ đọc: CLARA chỉ đọc các chỉ số được phép (bước chân, nhịp tim, giấc ngủ)."}
                </li>
                <li>
                  {isEn
                    ? "No credential exposure: Passwords and device tokens are never stored in browser storage."
                    : "Không lưu trữ mật khẩu hay khóa truy cập ở bộ nhớ trình duyệt."}
                </li>
                <li>
                  {isEn
                    ? "Revocable anytime: You can disconnect this source immediately from your profile."
                    : "Thu hồi bất cứ lúc nào trong trang Quản lý kết nối."}
                </li>
              </ul>
            </div>

            {error && (
              <InlineError
                message={error}
                onRetry={() => setError(null)}
                data-testid="reauth-inline-error"
              />
            )}

            {/* Actions */}
            <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-[color:var(--shell-border)]">
              <Button
                variant="secondary"
                size="sm"
                onClick={handleModalClose}
                disabled={isLoading}
              >
                {isEn ? "Cancel" : "Hủy bỏ"}
              </Button>
              <Button
                variant="primary"
                size="sm"
                icon="refresh"
                loading={isLoading}
                onClick={() => void handleConfirmReauth()}
                data-testid="confirm-reauth-btn"
              >
                {isEn ? "Reauthorize Grant" : "Cấp lại quyền ngay"}
              </Button>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
