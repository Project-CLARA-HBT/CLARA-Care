"use client";

import { useId, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Select, Textarea } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Modal } from "@/components/ui/modal";
import { SurfaceCard } from "@/components/ui/surface";
import { formatLocaleDate } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import {
  LifeMapConflictProvenanceHelper,
  type ContradictionSource,
  type MultiSourceContradiction,
  type ResolutionActionInput,
} from "@/lib/lifemap-conflict-provenance";

export interface ConflictProvenanceInspectorProps {
  contradiction: MultiSourceContradiction;
  open: boolean;
  onClose: () => void;
  onResolve?: (action: ResolutionActionInput) => Promise<void>;
  readOnly?: boolean;
  className?: string;
}

export function ConflictProvenanceInspector({
  contradiction,
  open,
  onClose,
  onResolve,
  readOnly = false,
  className = "",
}: ConflictProvenanceInspectorProps) {
  const language = useUILanguage();
  const isEn = language === "en";

  const reasonId = useId();
  const actionSelectId = useId();
  const sourceSelectId = useId();

  const [selectedAction, setSelectedAction] = useState<
    "accept_source" | "dispute_all" | "amendment" | "dismiss"
  >("accept_source");
  const [chosenSourceId, setChosenSourceId] = useState<string>(
    contradiction.sources[0]?.sourceId || "",
  );
  const [resolutionReason, setResolutionReason] = useState("");
  const [amendmentNote, setAmendmentNote] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [actionError, setActionError] = useState("");

  const severityTone: Record<string, "danger" | "warn" | "neutral"> = {
    critical: "danger",
    warning: "warn",
    advisory: "neutral",
  };

  const handleActionSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionError("");

    const validation = LifeMapConflictProvenanceHelper.validateResolutionReason(
      resolutionReason,
    );
    if (!validation.valid) {
      setActionError(
        validation.error || (isEn ? "Invalid reason" : "Lý do không hợp lệ"),
      );
      return;
    }

    if (!onResolve) return;

    setIsSubmitting(true);
    try {
      const latestRev = Math.max(
        ...contradiction.sources.map((s) => s.revision || 1),
        1,
      );
      const actionInput: ResolutionActionInput = {
        conflictId: contradiction.id,
        eventId: contradiction.eventId,
        currentRevision: latestRev,
        action: selectedAction,
        chosenSourceId:
          selectedAction === "accept_source" ? chosenSourceId : undefined,
        reason: resolutionReason.trim(),
        amendmentPayload:
          selectedAction === "amendment"
            ? { note: amendmentNote.trim() || resolutionReason.trim() }
            : undefined,
      };

      await onResolve(actionInput);
      onClose();
    } catch (err) {
      setActionError(
        err instanceof Error
          ? err.message
          : isEn
            ? "Failed to record resolution."
            : "Không thể lưu quyết định giải quyết mâu thuẫn.",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={
        isEn
          ? `Conflict Provenance: ${contradiction.fieldKey}`
          : `Đối chiếu & Thẩm định mâu thuẫn: ${contradiction.fieldKey}`
      }
      description={contradiction.description}
      size="lg"
      role="dialog"
      closeLabel={isEn ? "Close" : "Đóng"}
    >
      <div className={`space-y-6 ${className}`} data-testid="conflict-provenance-inspector">
        {/* Severity & Context Ribbon */}
        <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-xl bg-[var(--surface-muted)] border border-[var(--shell-border)]">
          <div className="flex items-center gap-2">
            <Badge tone={severityTone[contradiction.severity] || "neutral"}>
              {contradiction.severity.toUpperCase()}
            </Badge>
            <span className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
              {contradiction.type.replace("_", " ")}
            </span>
          </div>

          <div className="text-xs text-[var(--text-muted)] font-mono">
            {isEn ? "Detected at:" : "Phát hiện lúc:"}{" "}
            {formatLocaleDate(language, contradiction.detectedAt, {
              dateStyle: "medium",
              timeStyle: "short",
            })}
          </div>
        </div>

        {/* Multi-Source Provenance Comparison Matrix */}
        <div className="space-y-3">
          <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">
            {isEn
              ? `Multi-Source Contradiction Matrix (${contradiction.sources.length} sources)`
              : `Ma trận đối chiếu đa nguồn (${contradiction.sources.length} nguồn dữ liệu)`}
          </h4>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {contradiction.sources.map((src) => {
              const isSelected = chosenSourceId === src.sourceId;
              return (
                <SurfaceCard
                  key={src.sourceId}
                  className={`p-4 rounded-xl border transition-all ${
                    isSelected && selectedAction === "accept_source"
                      ? "border-[var(--brand-500)] ring-1 ring-[var(--brand-500)] bg-[var(--surface-container-high)]"
                      : "border-[var(--shell-border)] bg-[var(--surface-panel)]"
                  }`}
                  data-testid={`source-card-${src.sourceId}`}
                >
                  {/* Source Header */}
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <Badge tone={src.isAuthoritative ? "ok" : "warn"}>
                      {src.sourceType.replace("_", " ")}
                    </Badge>
                    <span className="text-xs text-[var(--text-muted)] font-mono">
                      Rev #{src.revision}
                    </span>
                  </div>

                  {/* Value Claim */}
                  <div className="my-2 p-2.5 rounded-lg bg-[var(--surface-muted)] border border-[var(--shell-border)]">
                    <span className="text-xs text-[var(--text-secondary)] block mb-0.5">
                      {isEn ? "Reported Value / Fact:" : "Giá trị ghi nhận:"}
                    </span>
                    <p className="text-sm font-semibold text-[var(--text-primary)]">
                      {src.valueDisplay}
                    </p>
                  </div>

                  {/* Bitemporal Coordinates */}
                  <div className="grid grid-cols-2 gap-2 text-[11px] pt-2 border-t border-[var(--shell-border)] text-[var(--text-muted)]">
                    <div>
                      <span className="block font-semibold text-[var(--text-secondary)]">
                        {isEn ? "Valid Time:" : "Thời điểm diễn ra:"}
                      </span>
                      {formatLocaleDate(language, src.occurredAt, {
                        dateStyle: "short",
                        timeStyle: "short",
                      })}
                    </div>
                    <div>
                      <span className="block font-semibold text-[var(--text-secondary)]">
                        {isEn ? "System Time:" : "Ghi nhận lúc:"}
                      </span>
                      {formatLocaleDate(language, src.recordedAt, {
                        dateStyle: "short",
                        timeStyle: "short",
                      })}
                    </div>
                  </div>

                  {/* Attribution & Cryptographic Lineage */}
                  <div className="mt-2.5 pt-2 border-t border-[var(--shell-border)] text-xs text-[var(--text-secondary)] space-y-1">
                    <p>
                      <strong>{isEn ? "Attribution:" : "Nguồn:"}</strong> {src.attribution}
                    </p>
                    {src.authorName ? (
                      <p>
                        <strong>{isEn ? "Author:" : "Người ghi:"}</strong> {src.authorName}
                      </p>
                    ) : null}
                    <p className="font-mono text-[10px] text-[var(--text-muted)] truncate">
                      SHA256: {src.contentHash}
                    </p>
                  </div>

                  {!readOnly && selectedAction === "accept_source" && (
                    <div className="mt-3 pt-2 flex justify-end">
                      <Button
                        size="sm"
                        variant={isSelected ? "primary" : "secondary"}
                        onClick={() => setChosenSourceId(src.sourceId)}
                      >
                        {isSelected
                          ? isEn
                            ? "✓ Chosen Truth Source"
                            : "✓ Nguồn chuẩn đã chọn"
                          : isEn
                            ? "Select As Canonical"
                            : "Chọn nguồn này làm chuẩn"}
                      </Button>
                    </div>
                  )}
                </SurfaceCard>
              );
            })}
          </div>
        </div>

        {/* Existing Resolution Notice if already resolved */}
        {contradiction.status === "resolved" && contradiction.resolution && (
          <div className="p-4 rounded-xl bg-[var(--status-ok-bg,rgba(52,168,83,0.1))] border border-[var(--status-ok-border,#34a853)] text-xs text-[var(--text-primary)] space-y-1.5">
            <div className="flex items-center gap-1.5 font-semibold text-[var(--ok-600,#16a34a)]">
              <Icon name="check" size={16} />
              <span>
                {isEn ? "Conflict Resolved via Audit" : "Mâu thuẫn đã được xử lý qua kiểm toán"}
              </span>
            </div>
            <p>
              <strong>{isEn ? "Action:" : "Hành động:"}</strong>{" "}
              {contradiction.resolution.action}
            </p>
            <p>
              <strong>{isEn ? "Rationale:" : "Căn cứ lâm sàng:"}</strong>{" "}
              {contradiction.resolution.reason}
            </p>
            <p className="font-mono text-[10px] text-[var(--text-muted)]">
              {isEn ? "Audit Receipt ID:" : "Mã biên lai kiểm toán:"}{" "}
              {contradiction.resolution.auditReceiptId} (
              {formatLocaleDate(language, contradiction.resolution.resolvedAt, {
                dateStyle: "short",
                timeStyle: "short",
              })}
              )
            </p>
          </div>
        )}

        {/* Audit Resolution Workflow (Only when unresolved and not read-only) */}
        {!readOnly && contradiction.status !== "resolved" && onResolve && (
          <form
            onSubmit={handleActionSubmit}
            className="space-y-4 pt-4 border-t border-[var(--shell-border)]"
            data-testid="resolution-form"
          >
            <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">
              {isEn ? "Clinical Audit Resolution Workflow" : "Quy trình giải quyết & Thẩm định kiểm toán"}
            </h4>

            {actionError && (
              <div className="p-3 rounded-lg bg-[var(--status-danger-bg,#fee2e2)] text-[var(--status-danger-text,#dc2626)] text-xs font-medium">
                {actionError}
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <Select
                  id={actionSelectId}
                  label={isEn ? "Resolution Action" : "Hành động xử lý"}
                  value={selectedAction}
                  onChange={(e) =>
                    setSelectedAction(
                      e.target.value as "accept_source" | "dispute_all" | "amendment" | "dismiss",
                    )
                  }
                >
                  <option value="accept_source">
                    {isEn ? "Accept Single Source as Canonical" : "Chấp nhận 1 nguồn làm chuẩn"}
                  </option>
                  <option value="dispute_all">
                    {isEn ? "Dispute All (Escalate to Doctor)" : "Báo sai toàn bộ (Chuyển bác sĩ)"}
                  </option>
                  <option value="amendment">
                    {isEn ? "Create Corrective Amendment" : "Ghi chú điều chỉnh / đính chính"}
                  </option>
                  <option value="dismiss">
                    {isEn ? "Dismiss (Not Clinically Significant)" : "Bỏ qua (Không ảnh hưởng lâm sàng)"}
                  </option>
                </Select>
              </div>

              {selectedAction === "accept_source" && (
                <div>
                  <Select
                    id={sourceSelectId}
                    label={isEn ? "Select Canonical Source" : "Nguồn được chọn làm chuẩn"}
                    value={chosenSourceId}
                    onChange={(e) => setChosenSourceId(e.target.value)}
                  >
                    {contradiction.sources.map((s) => (
                      <option key={s.sourceId} value={s.sourceId}>
                        {s.attribution} ({s.sourceType})
                      </option>
                    ))}
                  </Select>
                </div>
              )}
            </div>

            {selectedAction === "amendment" && (
              <Field
                id="amendment-note"
                label={isEn ? "Amended Value / Clinical Correction" : "Nội dung giá trị điều chỉnh"}
                value={amendmentNote}
                onChange={(e) => setAmendmentNote(e.target.value)}
                placeholder={
                  isEn
                    ? "e.g. Corrected dosage to 5mg after cross-referencing discharge papers"
                    : "Ví dụ: Điều chỉnh liều thành 5mg sau khi đối chiếu giấy ra viện"
                }
                required
              />
            )}

            <Textarea
              id={reasonId}
              label={isEn ? "Audit Justification (Required)" : "Căn cứ kiểm toán & Lý do (Bắt buộc)"}
              value={resolutionReason}
              onChange={(e) => setResolutionReason(e.target.value)}
              placeholder={
                isEn
                  ? "Enter clinical rationale for non-repudiation and immutable audit trail..."
                  : "Nhập lý do kiểm toán, căn cứ lâm sàng để lưu bất biến vào hồ sơ..."
              }
              rows={3}
              required
            />

            <div className="flex justify-end gap-2 pt-2 border-t border-[var(--shell-border)]">
              <Button
                type="button"
                variant="secondary"
                onClick={onClose}
                disabled={isSubmitting}
              >
                {isEn ? "Cancel" : "Hủy"}
              </Button>
              <Button
                type="submit"
                variant="primary"
                loading={isSubmitting}
                disabled={!resolutionReason.trim()}
              >
                {isEn ? "Commit Resolution & Audit" : "Ghi nhận quyết định & Lưu kiểm toán"}
              </Button>
            </div>
          </form>
        )}
      </div>
    </Modal>
  );
}
