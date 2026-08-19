"use client";

import { useState } from "react";
import type { WriteProposalDto } from "@/lib/api/v2-client";
import { Icon, type IconName } from "@/components/ui/icon";
import { Badge, type BadgeTone } from "@/components/ui/badge";

export interface SaveProposalCardProps {
  proposal: WriteProposalDto;
  onConfirm?: (proposal: WriteProposalDto) => Promise<void> | void;
  onReject?: (proposal: WriteProposalDto) => Promise<void> | void;
  onEditSave?: (updatedProposal: WriteProposalDto) => Promise<void> | void;
  className?: string;
}

function resolveProposalKindMeta(kind: string): { label: string; icon: IconName } {
  switch (kind?.toLowerCase()) {
    case "medication":
      return { label: "Thuốc mới", icon: "medication" };
    case "allergy":
      return { label: "Dị ứng mới", icon: "warning" };
    case "condition":
      return { label: "Tình trạng sức khỏe", icon: "body" };
    case "measurement":
      return { label: "Chỉ số đo", icon: "scan" };
    case "task":
      return { label: "Việc cần làm", icon: "check" };
    case "visit":
      return { label: "Lịch hẹn khám", icon: "calendar" };
    default:
      return { label: "Ghi nhận y tế", icon: "clinical-notes" };
  }
}

export function SaveProposalCard({
  proposal,
  onConfirm,
  onReject,
  onEditSave,
  className = "",
}: SaveProposalCardProps) {
  const [status, setStatus] = useState<"pending" | "confirmed" | "rejected" | "edited">(
    (proposal.status as any) || "pending"
  );
  const [isEditing, setIsEditing] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);

  // Edit fields
  const [editTitle, setEditTitle] = useState(proposal.title || "");
  const [editSummary, setEditSummary] = useState(proposal.summary || "");

  const kindMeta = resolveProposalKindMeta(proposal.kind);

  const handleConfirm = async () => {
    setIsProcessing(true);
    try {
      if (onConfirm) {
        await onConfirm(proposal);
      }
      setStatus("confirmed");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReject = async () => {
    setIsProcessing(true);
    try {
      if (onReject) {
        await onReject(proposal);
      }
      setStatus("rejected");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSaveEdit = async () => {
    const updated: WriteProposalDto = {
      ...proposal,
      title: editTitle.trim() || proposal.title,
      summary: editSummary.trim() || proposal.summary,
      status: "edited",
    };

    setIsProcessing(true);
    try {
      if (onEditSave) {
        await onEditSave(updated);
      } else if (onConfirm) {
        await onConfirm(updated);
      }
      setStatus("edited");
      setIsEditing(false);
    } finally {
      setIsProcessing(false);
    }
  };

  let statusBadge: { label: string; tone: BadgeTone } = {
    label: "Đề xuất mới",
    tone: "brand",
  };

  if (status === "confirmed") {
    statusBadge = { label: "Đã lưu vào hồ sơ", tone: "ok" };
  } else if (status === "rejected") {
    statusBadge = { label: "Đã bỏ qua", tone: "neutral" };
  } else if (status === "edited") {
    statusBadge = { label: "Đã sửa & lưu", tone: "ok" };
  }

  return (
    <div
      className={`rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-sm transition-all duration-150 ${
        status === "confirmed" || status === "edited"
          ? "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)]/30"
          : status === "rejected"
          ? "opacity-60 bg-[var(--surface-muted)]/50"
          : "hover:border-[color:var(--shell-border-strong)]"
      } ${className}`}
      data-testid={`save-proposal-card-${proposal.id}`}
    >
      {/* Card Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
            <Icon name={kindMeta.icon} size={16} aria-hidden="true" />
          </span>
          <div>
            <span className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">
              {kindMeta.label}
            </span>
          </div>
        </div>

        <Badge tone={statusBadge.tone}>{statusBadge.label}</Badge>
      </div>

      {/* Card Body */}
      {isEditing ? (
        <div className="mt-3 space-y-3">
          <div>
            <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
              Tên / Tiêu đề
            </label>
            <input
              type="text"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1.5 text-sm text-[var(--text-primary)] focus-ring"
              data-testid="proposal-edit-title-input"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
              Chi tiết / Liều lượng / Ghi chú
            </label>
            <textarea
              value={editSummary}
              onChange={(e) => setEditSummary(e.target.value)}
              rows={2}
              className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1.5 text-sm text-[var(--text-primary)] focus-ring"
              data-testid="proposal-edit-summary-input"
            />
          </div>

          <div className="flex items-center justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={() => setIsEditing(false)}
              disabled={isProcessing}
              className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
            >
              Hủy
            </button>
            <button
              type="button"
              onClick={handleSaveEdit}
              disabled={isProcessing || !editTitle.trim()}
              className="rounded-[var(--radius-md)] bg-[var(--brand-600)] px-3.5 py-1.5 text-xs font-semibold text-[var(--button-primary-text)] hover:bg-[var(--brand-700)] focus-ring"
              data-testid="proposal-save-edit-button"
            >
              {isProcessing ? "Đang lưu..." : "Lưu thay đổi"}
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-2.5">
          <h4 className="text-sm font-semibold text-[var(--text-primary)]">
            {proposal.title}
          </h4>

          {proposal.summary ? (
            <p className="mt-1 text-xs leading-relaxed text-[var(--text-secondary)]">
              {proposal.summary}
            </p>
          ) : null}

          {/* Key-Value payload preview if present */}
          {proposal.data && Object.keys(proposal.data).length > 0 ? (
            <div className="mt-2.5 flex flex-wrap gap-2 text-[11px] text-[var(--text-muted)] bg-[var(--surface-muted)]/60 p-2 rounded-[var(--radius-md)]">
              {Object.entries(proposal.data).map(([k, v]) => (
                <span key={k} className="inline-flex items-center gap-1">
                  <span className="font-medium text-[var(--text-secondary)]">{k}:</span>
                  <span>{String(v)}</span>
                </span>
              ))}
            </div>
          ) : null}

          {/* Action Buttons if still pending */}
          {status === "pending" ? (
            <div className="mt-3.5 flex flex-wrap items-center gap-2 pt-2 border-t border-[color:var(--shell-border)]/60">
              <button
                type="button"
                onClick={handleConfirm}
                disabled={isProcessing}
                className="inline-flex items-center gap-1.5 rounded-[var(--radius-md)] bg-[var(--brand-600)] px-3 py-1.5 text-xs font-semibold text-[var(--button-primary-text)] hover:bg-[var(--brand-700)] focus-ring disabled:opacity-50"
                data-testid="proposal-confirm-button"
              >
                <Icon name="check" size={14} aria-hidden="true" />
                <span>{isProcessing ? "Đang lưu..." : "Lưu vào hồ sơ"}</span>
              </button>

              <button
                type="button"
                onClick={() => setIsEditing(true)}
                disabled={isProcessing}
                className="inline-flex items-center gap-1.5 rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] focus-ring disabled:opacity-50"
                data-testid="proposal-edit-button"
              >
                <Icon name="clinical-notes" size={14} aria-hidden="true" />
                <span>Chỉnh sửa</span>
              </button>

              <button
                type="button"
                onClick={handleReject}
                disabled={isProcessing}
                className="inline-flex items-center gap-1 rounded-[var(--radius-md)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-secondary)] focus-ring disabled:opacity-50"
                data-testid="proposal-reject-button"
              >
                <span>Bỏ qua</span>
              </button>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}

export default SaveProposalCard;
