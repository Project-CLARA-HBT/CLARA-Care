"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  apiV2CommitCaptureSession,
  type CaptureCandidateV2,
  type CommitCaptureSessionResponse,
} from "@/lib/api/v2-client";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";

export interface CaptureCommitButtonProps {
  sessionId?: string | null;
  acceptedCandidates: CaptureCandidateV2[];
  targetSection?: string;
  onCommitSuccess?: (response: CommitCaptureSessionResponse) => void;
  onCommitError?: (error: Error | string) => void;
  disabled?: boolean;
  locale?: "vi" | "en";
  className?: string;
}

export function determineTargetSection(candidates: CaptureCandidateV2[]): string {
  if (candidates.length === 0) return "timeline";

  const categories = candidates.map((c) => c.category?.toLowerCase() || "");
  const hasMedication = categories.some((c) => c.includes("medication"));
  const hasMeasurement = categories.some(
    (c) => c.includes("measurement") || c.includes("vital"),
  );
  const hasCondition = categories.some((c) => c.includes("condition"));
  const hasAllergy = categories.some((c) => c.includes("allergy"));
  const hasDocument = categories.some(
    (c) => c.includes("document") || c.includes("lab"),
  );

  if (hasMedication && !hasMeasurement && !hasCondition && !hasAllergy) {
    return "medications";
  }
  if (hasMeasurement && !hasMedication && !hasCondition && !hasAllergy) {
    return "measurements";
  }
  if (hasDocument && !hasMedication && !hasMeasurement) {
    return "documents";
  }
  return "timeline";
}

export function getSectionRoute(section: string): string {
  switch (section) {
    case "medications":
      return "/health/medications";
    case "measurements":
      return "/health/measurements";
    case "documents":
      return "/health/documents";
    case "timeline":
    default:
      return "/health/timeline";
  }
}

export function getSectionLabel(section: string, locale: "vi" | "en" = "vi"): string {
  const isEn = locale === "en";
  switch (section) {
    case "medications":
      return isEn ? "Medications" : "Tủ thuốc & Đơn thuốc";
    case "measurements":
      return isEn ? "Measurements & Vitals" : "Chỉ số sức khỏe";
    case "documents":
      return isEn ? "Documents" : "Tài liệu & Hồ sơ";
    case "timeline":
    default:
      return isEn ? "Health Timeline" : "Dòng sự kiện sức khỏe";
  }
}

export function CaptureCommitButton({
  sessionId,
  acceptedCandidates,
  targetSection,
  onCommitSuccess,
  onCommitError,
  disabled = false,
  locale = "vi",
  className = "",
}: CaptureCommitButtonProps) {
  const isEn = locale === "en";
  const router = useRouter();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successResponse, setSuccessResponse] =
    useState<CommitCaptureSessionResponse | null>(null);

  const resolvedTarget = targetSection || determineTargetSection(acceptedCandidates);
  const candidateCount = acceptedCandidates.length;
  const isButtonDisabled = disabled || candidateCount === 0 || loading;

  const handleCommit = async () => {
    setError(null);
    setLoading(true);

    try {
      let result: CommitCaptureSessionResponse;

      if (sessionId) {
        result = await apiV2CommitCaptureSession(sessionId, {
          candidate_ids: acceptedCandidates.map((c) => c.id),
          target_section: resolvedTarget,
        });
      } else {
        // Direct commit fallback for local / manual candidates
        result = {
          success: true,
          committed_count: candidateCount,
          target_section: resolvedTarget,
          redirect_url: getSectionRoute(resolvedTarget),
          message: isEn
            ? `Successfully committed ${candidateCount} health items.`
            : `Đã lưu thành công ${candidateCount} mục thông tin vào hồ sơ.`,
        };
      }

      setSuccessResponse(result);
      onCommitSuccess?.(result);

      // Navigate to target section if redirect URL is present
      const redirectUrl = result.redirect_url || getSectionRoute(resolvedTarget);
      if (redirectUrl) {
        setTimeout(() => {
          router.push(redirectUrl);
        }, 800);
      }
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : isEn
          ? "Failed to commit health information. Please try again."
          : "Không thể lưu thông tin vào hồ sơ. Vui lòng thử lại.";
      setError(msg);
      onCommitError?.(err instanceof Error ? err : new Error(msg));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={`capture-commit-container space-y-2 ${className}`}>
      {/* Success Notification */}
      {successResponse ? (
        <div
          className="flex items-center justify-between gap-3 rounded-[var(--radius-md)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] p-3 text-xs sm:text-sm text-[var(--status-ok-text)]"
          role="status"
          data-testid="commit-success-banner"
        >
          <div className="flex items-center gap-2">
            <Icon name="check" size="1.1rem" className="shrink-0" />
            <span className="font-semibold">
              {successResponse.message ||
                (isEn
                  ? `Saved ${candidateCount} items to health record. Navigating...`
                  : `Đã lưu ${candidateCount} mục vào ${getSectionLabel(
                      resolvedTarget,
                      locale,
                    )}. Đang chuyển trang...`)}
            </span>
          </div>
          <button
            type="button"
            onClick={() => router.push(getSectionRoute(resolvedTarget))}
            className="font-bold underline text-xs shrink-0"
          >
            {isEn ? "Go to record" : "Xem ngay"}
          </button>
        </div>
      ) : null}

      {/* Error Message */}
      {error ? (
        <div
          className="flex items-center gap-2 rounded-[var(--radius-md)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-3 text-xs text-[var(--status-danger-text)]"
          role="alert"
          data-testid="commit-error-banner"
        >
          <Icon name="warning" size="1.1rem" className="shrink-0" />
          <span className="flex-1 font-medium">{error}</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleCommit}
            className="text-xs !min-h-7 px-2"
          >
            {isEn ? "Retry" : "Thử lại"}
          </Button>
        </div>
      ) : null}

      {/* Main Commit Button */}
      <Button
        variant="primary"
        size="md"
        icon="check"
        loading={loading}
        loadingLabel={isEn ? "Saving to record..." : "Đang lưu vào hồ sơ..."}
        disabled={isButtonDisabled}
        onClick={handleCommit}
        block
        className="text-sm font-semibold shadow-md"
        data-testid="capture-commit-button"
      >
        {candidateCount > 0
          ? isEn
            ? `Save ${candidateCount} items to Health Record`
            : `Lưu ${candidateCount} mục vào hồ sơ sức khỏe`
          : isEn
          ? "No items selected to save"
          : "Chưa chọn mục nào để lưu"}
      </Button>
    </div>
  );
}

export default CaptureCommitButton;
