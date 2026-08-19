"use client";

import { useMemo, useState } from "react";
import type {
  CandidateReviewStatus,
  CaptureCandidateV2,
} from "@/lib/api/v2-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import {
  formatCandidateFieldName,
  formatCandidateValue,
  getCategoryMeta,
} from "./types";

export interface CandidateReviewSheetProps {
  candidates: CaptureCandidateV2[];
  selectedCandidateId?: string | null;
  onSelectCandidate?: (candidateId: string) => void;
  onAcceptCandidate: (candidateId: string) => void;
  onRejectCandidate: (candidateId: string) => void;
  onEditCandidate: (
    candidateId: string,
    newValue: string | number | Record<string, unknown>,
  ) => void;
  onAcceptAll?: () => void;
  onRejectAll?: () => void;
  locale?: "vi" | "en";
  className?: string;
}

export function CandidateReviewSheet({
  candidates,
  selectedCandidateId = null,
  onSelectCandidate,
  onAcceptCandidate,
  onRejectCandidate,
  onEditCandidate,
  onAcceptAll,
  onRejectAll,
  locale = "vi",
  className = "",
}: CandidateReviewSheetProps) {
  const isEn = locale === "en";

  // Filter state: 'all' | 'pending' | 'uncertain' | 'accepted' | 'rejected'
  const [filter, setFilter] = useState<string>("all");
  const [editingCandidateId, setEditingCandidateId] = useState<string | null>(null);
  const [editValueText, setEditValueText] = useState<string>("");

  const startEditing = (candidate: CaptureCandidateV2) => {
    setEditingCandidateId(candidate.id);
    const val =
      typeof candidate.value === "object"
        ? JSON.stringify(candidate.value, null, 2)
        : String(candidate.value ?? "");
    setEditValueText(val);
  };

  const saveEditing = (candidateId: string) => {
    let parsed: string | number | Record<string, unknown> = editValueText.trim();
    if (parsed.startsWith("{") && parsed.endsWith("}")) {
      try {
        parsed = JSON.parse(parsed);
      } catch {
        // keep as string
      }
    } else if (/^-?\d+(\.\d+)?$/.test(parsed)) {
      parsed = Number(parsed);
    }
    onEditCandidate(candidateId, parsed);
    setEditingCandidateId(null);
  };

  const cancelEditing = () => {
    setEditingCandidateId(null);
  };

  const counts = useMemo(() => {
    const total = candidates.length;
    const accepted = candidates.filter(
      (c) => c.status === "accepted" || c.status === "confirmed",
    ).length;
    const rejected = candidates.filter((c) => c.status === "rejected").length;
    const pending = candidates.filter(
      (c) => c.status === "pending" || (!c.status && c.status !== "rejected"),
    ).length;
    const uncertain = candidates.filter(
      (c) =>
        c.has_uncertainty ||
        (c.confidence !== null && c.confidence !== undefined && c.confidence < 0.8) ||
        (c.ocr_confidence !== null &&
          c.ocr_confidence !== undefined &&
          c.confidence !== null &&
          c.confidence !== undefined &&
          Math.abs(c.ocr_confidence - c.confidence) > 0.2),
    ).length;

    return { total, accepted, rejected, pending, uncertain };
  }, [candidates]);

  const filteredCandidates = useMemo(() => {
    if (filter === "all") return candidates;
    if (filter === "accepted") {
      return candidates.filter((c) => c.status === "accepted" || c.status === "confirmed");
    }
    if (filter === "rejected") {
      return candidates.filter((c) => c.status === "rejected");
    }
    if (filter === "pending") {
      return candidates.filter(
        (c) => c.status === "pending" || (!c.status && c.status !== "rejected"),
      );
    }
    if (filter === "uncertain") {
      return candidates.filter(
        (c) =>
          c.has_uncertainty ||
          (c.confidence !== null && c.confidence !== undefined && c.confidence < 0.8) ||
          (c.ocr_confidence !== null &&
            c.ocr_confidence !== undefined &&
            c.confidence !== null &&
            c.confidence !== undefined &&
            Math.abs(c.ocr_confidence - c.confidence) > 0.2),
      );
    }
    return candidates;
  }, [candidates, filter]);

  return (
    <div
      className={`candidate-review-sheet flex flex-col rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] overflow-hidden shadow-sm ${className}`}
      data-testid="candidate-review-sheet"
    >
      {/* Top Header with title and bulk actions */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 px-4 py-3 sm:px-6">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm sm:text-base font-bold text-[var(--text-primary)]">
              {isEn ? "Extracted Information Review" : "Kiểm tra thông tin trích xuất"}
            </h3>
            <Badge tone="brand" className="text-xs">
              {candidates.length} {isEn ? "items" : "mục"}
            </Badge>
          </div>
          <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
            {isEn
              ? "Review, edit if needed, and confirm items to add to your health record"
              : "Vui lòng xem lại, sửa đổi nếu cần và xác nhận các mục sẽ lưu vào hồ sơ"}
          </p>
        </div>

        {/* Bulk Accept / Reject Buttons */}
        <div className="flex items-center gap-2">
          {onAcceptAll ? (
            <Button
              variant="secondary"
              size="sm"
              icon="check"
              onClick={onAcceptAll}
              disabled={candidates.length === 0}
              className="text-xs"
              data-testid="review-accept-all-btn"
            >
              {isEn ? "Accept all" : "Chấp nhận tất cả"}
            </Button>
          ) : null}

          {onRejectAll ? (
            <Button
              variant="ghost"
              size="sm"
              icon="trash"
              onClick={onRejectAll}
              disabled={candidates.length === 0}
              className="text-xs text-[var(--text-muted)] hover:text-[var(--status-danger-text)]"
              data-testid="review-reject-all-btn"
            >
              {isEn ? "Reject all" : "Từ chối tất cả"}
            </Button>
          ) : null}
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-1.5 overflow-x-auto border-b border-[color:var(--shell-border)] px-4 py-2 bg-[var(--surface-panel)] scrollbar-none">
        <button
          type="button"
          onClick={() => setFilter("all")}
          className={`inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] px-3 py-1 text-xs font-medium transition-colors ${
            filter === "all"
              ? "bg-[var(--brand-600)] text-white"
              : "bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
          data-testid="filter-all"
        >
          <span>{isEn ? "All" : "Tất cả"}</span>
          <span className="opacity-80">({counts.total})</span>
        </button>

        <button
          type="button"
          onClick={() => setFilter("pending")}
          className={`inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] px-3 py-1 text-xs font-medium transition-colors ${
            filter === "pending"
              ? "bg-[var(--brand-600)] text-white"
              : "bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
          data-testid="filter-pending"
        >
          <span>{isEn ? "Pending" : "Chờ duyệt"}</span>
          <span className="opacity-80">({counts.pending})</span>
        </button>

        {counts.uncertain > 0 ? (
          <button
            type="button"
            onClick={() => setFilter("uncertain")}
            className={`inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] px-3 py-1 text-xs font-medium transition-colors ${
              filter === "uncertain"
                ? "bg-[var(--status-warn-border)] text-white font-semibold"
                : "bg-[var(--status-warn-bg)] text-[var(--status-warn-text)] border border-[color:var(--status-warn-border)]/40"
            }`}
            data-testid="filter-uncertain"
          >
            <Icon name="warning" size="0.85rem" />
            <span>{isEn ? "Uncertain" : "Cần kiểm tra"}</span>
            <span className="opacity-80">({counts.uncertain})</span>
          </button>
        ) : null}

        <button
          type="button"
          onClick={() => setFilter("accepted")}
          className={`inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] px-3 py-1 text-xs font-medium transition-colors ${
            filter === "accepted"
              ? "bg-[var(--brand-600)] text-white"
              : "bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
          data-testid="filter-accepted"
        >
          <span>{isEn ? "Accepted" : "Đã nhận"}</span>
          <span className="opacity-80">({counts.accepted})</span>
        </button>

        <button
          type="button"
          onClick={() => setFilter("rejected")}
          className={`inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] px-3 py-1 text-xs font-medium transition-colors ${
            filter === "rejected"
              ? "bg-[var(--brand-600)] text-white"
              : "bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
          data-testid="filter-rejected"
        >
          <span>{isEn ? "Rejected" : "Đã từ chối"}</span>
          <span className="opacity-80">({counts.rejected})</span>
        </button>
      </div>

      {/* Candidate Cards List */}
      <div
        className="divide-y divide-[color:var(--shell-border)]/60 max-h-[500px] overflow-y-auto p-4 sm:p-5 space-y-3"
        role="list"
        aria-label={isEn ? "Extracted candidates list" : "Danh sách các mục đã trích xuất"}
      >
        {filteredCandidates.length === 0 ? (
          <div className="py-8 text-center text-xs sm:text-sm text-[var(--text-muted)]">
            <Icon name="clinical-notes" size="2rem" className="mx-auto mb-2 opacity-40" />
            <p>
              {isEn
                ? "No extracted items match this filter."
                : "Không có mục trích xuất nào trong bộ lọc này."}
            </p>
          </div>
        ) : (
          filteredCandidates.map((candidate) => {
            const isSelected = candidate.id === selectedCandidateId;
            const isEditing = candidate.id === editingCandidateId;
            const isAccepted =
              candidate.status === "accepted" || candidate.status === "confirmed";
            const isRejected = candidate.status === "rejected";
            const categoryMeta = getCategoryMeta(candidate.category);

            const isUncertain =
              candidate.has_uncertainty ||
              (candidate.confidence !== null &&
                candidate.confidence !== undefined &&
                candidate.confidence < 0.8) ||
              (candidate.ocr_confidence !== null &&
                candidate.ocr_confidence !== undefined &&
                candidate.confidence !== null &&
                candidate.confidence !== undefined &&
                Math.abs(candidate.ocr_confidence - candidate.confidence) > 0.2);

            return (
              <div
                key={candidate.id}
                role="listitem"
                tabIndex={0}
                onClick={() => onSelectCandidate?.(candidate.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    onSelectCandidate?.(candidate.id);
                  }
                }}
                className={`rounded-[var(--radius-lg)] border p-4 transition-all duration-150 cursor-pointer ${
                  isSelected
                    ? "border-[color:var(--brand-600)] bg-[var(--surface-brand-soft)] ring-1 ring-[color:var(--brand-600)] shadow-sm"
                    : isAccepted
                    ? "border-[color:var(--status-ok-border)]/60 bg-[var(--status-ok-bg)]/20 hover:border-[color:var(--status-ok-border)]"
                    : isRejected
                    ? "border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 opacity-60 hover:opacity-100"
                    : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] hover:border-[color:var(--shell-border-strong)]"
                }`}
                data-testid={`candidate-card-${candidate.id}`}
              >
                {/* Top Row: Category Badge + Uncertainty + Confirmation Toggle */}
                <div className="flex flex-wrap items-center justify-between gap-2 mb-2.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={categoryMeta.tone} icon={categoryMeta.icon}>
                      {isEn ? categoryMeta.labelEn : categoryMeta.labelVi}
                    </Badge>

                    {/* Uncertainty Badge */}
                    {isUncertain ? (
                      <Badge
                        tone="warn"
                        icon="warning"
                        className="text-[11px]"
                        title={
                          candidate.uncertainty_reason ||
                          (isEn
                            ? "Low OCR confidence or model disagreement"
                            : "Độ tin cậy OCR thấp hoặc cần xác minh lại")
                        }
                        data-testid={`uncertainty-badge-${candidate.id}`}
                      >
                        {isEn ? "OCR Disagreement / Verify" : "Chưa chắc chắn"}
                      </Badge>
                    ) : null}

                    {candidate.status === "edited" ? (
                      <Badge tone="neutral" icon="edit" className="text-[11px]">
                        {isEn ? "Edited" : "Đã sửa"}
                      </Badge>
                    ) : null}
                  </div>

                  {/* Confirmation Toggle */}
                  <div className="flex items-center gap-2">
                    <label
                      className="inline-flex items-center gap-1.5 text-xs font-semibold cursor-pointer select-none"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <input
                        type="checkbox"
                        checked={isAccepted}
                        onChange={(e) => {
                          if (e.target.checked) {
                            onAcceptCandidate(candidate.id);
                          } else {
                            onRejectCandidate(candidate.id);
                          }
                        }}
                        className="h-4 w-4 rounded text-[var(--brand-600)] focus:ring-[var(--brand-500)]"
                        aria-label={
                          isEn
                            ? `Accept ${candidate.field_name}`
                            : `Chấp nhận ${formatCandidateFieldName(candidate.field_name, locale)}`
                        }
                        data-testid={`candidate-toggle-${candidate.id}`}
                      />
                      <span className={isAccepted ? "text-[var(--status-ok-text)]" : "text-[var(--text-secondary)]"}>
                        {isAccepted
                          ? isEn
                            ? "Accepted"
                            : "Đã chọn"
                          : isEn
                          ? "Include"
                          : "Thêm vào hồ sơ"}
                      </span>
                    </label>
                  </div>
                </div>

                {/* Field Name and Value Display or Inline Edit */}
                <div className="space-y-1.5">
                  <div className="text-xs font-semibold text-[var(--text-secondary)]">
                    {formatCandidateFieldName(candidate.field_name, locale)}
                  </div>

                  {isEditing ? (
                    <div
                      className="space-y-2 pt-1"
                      onClick={(e) => e.stopPropagation()}
                      data-testid={`inline-edit-form-${candidate.id}`}
                    >
                      <textarea
                        value={editValueText}
                        onChange={(e) => setEditValueText(e.target.value)}
                        rows={2}
                        className="w-full rounded-[var(--radius-md)] border border-[color:var(--brand-500)] bg-[var(--surface-panel)] p-2.5 text-xs sm:text-sm font-medium text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[color:var(--brand-500)]"
                        placeholder={isEn ? "Enter value..." : "Nhập giá trị..."}
                        autoFocus
                        data-testid={`edit-input-${candidate.id}`}
                      />
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={cancelEditing}
                          className="text-xs"
                          data-testid={`cancel-edit-${candidate.id}`}
                        >
                          {isEn ? "Cancel" : "Hủy"}
                        </Button>
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => saveEditing(candidate.id)}
                          className="text-xs"
                          data-testid={`save-edit-${candidate.id}`}
                        >
                          {isEn ? "Save" : "Lưu thay đổi"}
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-start justify-between gap-3">
                      <div className="text-sm sm:text-base font-bold text-[var(--text-primary)] break-words">
                        {formatCandidateValue(candidate.value)}
                      </div>
                    </div>
                  )}

                  {/* Source Snippet / Page Info */}
                  {candidate.source_snippet || candidate.source_page ? (
                    <div className="mt-1 flex items-start gap-1.5 text-xs text-[var(--text-muted)] bg-[var(--surface-muted)]/60 rounded-[var(--radius-md)] p-2">
                      <Icon name="search" size="0.85rem" className="mt-0.5 shrink-0" />
                      <span className="italic leading-relaxed">
                        {candidate.source_page ? `Trang ${candidate.source_page}: ` : ""}
                        &ldquo;{candidate.source_snippet}&rdquo;
                      </span>
                    </div>
                  ) : null}
                </div>

                {/* Bottom Action Buttons: Accept / Edit / Reject */}
                {!isEditing && (
                  <div
                    className="mt-3 flex flex-wrap items-center justify-end gap-2 border-t border-[color:var(--shell-border)]/40 pt-2.5"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Button
                      variant="ghost"
                      size="sm"
                      icon="edit"
                      onClick={() => startEditing(candidate)}
                      className="text-xs !min-h-8 px-2.5 text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                      data-testid={`btn-edit-${candidate.id}`}
                    >
                      {isEn ? "Edit" : "Sửa"}
                    </Button>

                    <Button
                      variant={isRejected ? "danger" : "ghost"}
                      size="sm"
                      icon="trash"
                      onClick={() => onRejectCandidate(candidate.id)}
                      className={`text-xs !min-h-8 px-2.5 ${
                        isRejected
                          ? ""
                          : "text-[var(--text-muted)] hover:text-[var(--status-danger-text)] hover:bg-[var(--status-danger-bg)]"
                      }`}
                      data-testid={`btn-reject-${candidate.id}`}
                    >
                      {isEn ? "Reject" : "Từ chối"}
                    </Button>

                    <Button
                      variant={isAccepted ? "primary" : "secondary"}
                      size="sm"
                      icon="check"
                      onClick={() => onAcceptCandidate(candidate.id)}
                      className="text-xs !min-h-8 px-3"
                      data-testid={`btn-accept-${candidate.id}`}
                    >
                      {isAccepted
                        ? isEn
                          ? "Accepted"
                          : "Đã chấp nhận"
                        : isEn
                        ? "Accept"
                        : "Chấp nhận"}
                    </Button>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

export default CandidateReviewSheet;
