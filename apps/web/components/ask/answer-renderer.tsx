"use client";

import Link from "next/link";
import type {
  ConsumerAnswerEnvelope,
  ConsumerAnswerActionDto,
  WriteProposalDto,
  ConsumerUnknownDto,
} from "@/lib/api/v2-client";
import { Icon } from "@/components/ui/icon";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { ContextDisclosureBadge } from "./context-disclosure-badge";
import { SaveProposalCard } from "./save-proposal-card";

export interface AnswerRendererProps {
  envelope: ConsumerAnswerEnvelope;
  onActionClick?: (action: ConsumerAnswerActionDto) => void;
  onConfirmProposal?: (proposal: WriteProposalDto) => Promise<void> | void;
  onRejectProposal?: (proposal: WriteProposalDto) => Promise<void> | void;
  onEditProposal?: (proposal: WriteProposalDto) => Promise<void> | void;
  onOpenEvidenceDrawer?: () => void;
  isStreaming?: boolean;
  locale?: "vi" | "en";
  className?: string;
}

function resolveSafetyTone(urgency?: string): {
  tone: BadgeTone;
  label: string;
  isEmergency: boolean;
  isUrgent: boolean;
} {
  switch (urgency?.toLowerCase()) {
    case "emergency":
    case "critical":
      return {
        tone: "danger",
        label: "Khẩn cấp / Cấp cứu",
        isEmergency: true,
        isUrgent: true,
      };
    case "urgent":
      return {
        tone: "danger",
        label: "Cần khám sớm",
        isEmergency: false,
        isUrgent: true,
      };
    case "soon":
    case "warning":
      return {
        tone: "warn",
        label: "Cần chú ý theo dõi",
        isEmergency: false,
        isUrgent: false,
      };
    case "routine":
      return {
        tone: "ok",
        label: "Theo dõi định kỳ",
        isEmergency: false,
        isUrgent: false,
      };
    default:
      return {
        tone: "neutral",
        label: "Thông tin tham khảo",
        isEmergency: false,
        isUrgent: false,
      };
  }
}

export function AnswerRenderer({
  envelope,
  onActionClick,
  onConfirmProposal,
  onRejectProposal,
  onEditProposal,
  onOpenEvidenceDrawer,
  isStreaming = false,
  locale = "vi",
  className = "",
}: AnswerRendererProps) {
  const {
    answer,
    personal_evidence = [],
    external_sources = [],
    unknowns = [],
    safety,
    write_proposals = [],
    disclosure,
  } = envelope;

  const mainMessage = answer?.main_message ?? "";
  const actions = answer?.actions ?? [];
  const sections = answer?.sections ?? [];
  const totalEvidenceCount = personal_evidence.length + external_sources.length;

  const safetyMeta = resolveSafetyTone(safety?.urgency);

  return (
    <div
      className={`space-y-5 text-[var(--text-primary)] ${className}`}
      data-testid="answer-renderer"
    >
      {/* 5. Khi nào cần hỗ trợ y tế (Safety Banner Top if Emergency / Urgent) */}
      {safety && (safetyMeta.isEmergency || safetyMeta.isUrgent) ? (
        <section
          aria-label="Cảnh báo an toàn y tế khẩn cấp"
          className="rounded-[var(--radius-xl)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-4 shadow-sm"
          data-testid="answer-safety-emergency-banner"
        >
          <div className="flex items-start gap-3">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--danger-500)] text-white shadow-xs">
              <Icon name="emergency" size={18} aria-hidden="true" />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-[var(--status-danger-text)] uppercase tracking-wide">
                  5. Khi nào cần hỗ trợ y tế
                </h3>
                <Badge tone="danger">{safetyMeta.label}</Badge>
              </div>

              {safety.guidance ? (
                <p className="mt-1.5 text-sm font-semibold leading-relaxed text-[var(--status-danger-text)]">
                  {safety.guidance}
                </p>
              ) : null}

              {safety.red_flags && safety.red_flags.length > 0 ? (
                <div className="mt-2 space-y-1 text-xs text-[var(--status-danger-text)]">
                  <p className="font-semibold">Dấu hiệu cảnh báo cần đi cấp cứu ngay:</p>
                  <ul className="list-disc pl-5 space-y-0.5">
                    {safety.red_flags.map((flag, idx) => (
                      <li key={idx}>{flag}</li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {safetyMeta.isEmergency ? (
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <a
                    href="tel:115"
                    className="inline-flex items-center gap-1.5 rounded-[var(--radius-md)] bg-[var(--danger-500)] px-3.5 py-1.5 text-xs font-bold text-white shadow-xs hover:brightness-110 focus-ring"
                    data-testid="emergency-call-115-button"
                  >
                    <Icon name="emergency" size={14} aria-hidden="true" />
                    <span>Gọi Cấp Cứu 115</span>
                  </a>
                  <span className="text-xs text-[var(--status-danger-text)] font-medium">
                    hoặc đến ngay phòng cấp cứu bệnh viện gần nhất
                  </span>
                </div>
              ) : null}
            </div>
          </div>
        </section>
      ) : null}

      {/* 1. ĐIỀU QUAN TRỌNG NHẤT (Main Message) */}
      <section
        aria-label="Điều quan trọng nhất"
        className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm"
        data-testid="answer-main-message-section"
      >
        <div className="flex items-center gap-2 mb-2.5">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
            <Icon name="clinical-notes" size={14} aria-hidden="true" />
          </span>
          <h2 className="text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
            1. Điều quan trọng nhất
          </h2>
        </div>

        <div
          className="text-base leading-relaxed text-[var(--text-primary)] font-medium whitespace-pre-line"
          data-testid="answer-main-message"
        >
          {mainMessage}
          {isStreaming ? (
            <span className="inline-block h-4 w-2 ml-1 animate-pulse bg-[var(--brand-500)] align-middle" />
          ) : null}
        </div>

        {/* Narrative subsections if present */}
        {sections.length > 0 ? (
          <div className="mt-4 space-y-3 pt-3 border-t border-[color:var(--shell-border)]/60">
            {sections.map((sec, idx) => (
              <div key={idx} className="space-y-1">
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                  {sec.title}
                </h3>
                <p className="text-sm leading-relaxed text-[var(--text-secondary)] whitespace-pre-line">
                  {sec.content}
                </p>
              </div>
            ))}
          </div>
        ) : null}
      </section>

      {/* Write Proposals (Đề xuất ghi nhận vào hồ sơ) if present */}
      {write_proposals.length > 0 ? (
        <section
          aria-label="Đề xuất lưu thông tin vào hồ sơ"
          className="space-y-3"
          data-testid="answer-proposals-section"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Icon name="clinical-notes" size={16} className="text-[var(--brand-500)]" aria-hidden="true" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                Đề xuất cập nhật hồ sơ ({write_proposals.length})
              </h3>
            </div>
            <span className="text-[11px] text-[var(--text-muted)]">
              Bạn có toàn quyền xác nhận hoặc bỏ qua
            </span>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {write_proposals.map((prop) => (
              <SaveProposalCard
                key={prop.id}
                proposal={prop}
                onConfirm={onConfirmProposal}
                onReject={onRejectProposal}
                onEditSave={onEditProposal}
              />
            ))}
          </div>
        </section>
      ) : null}

      {/* 2. BẠN CÓ THỂ LÀM GÌ TIẾP THEO (Actions) */}
      {actions.length > 0 ? (
        <section
          aria-label="Bạn có thể làm gì tiếp theo"
          className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-xs"
          data-testid="answer-actions-section"
        >
          <div className="flex items-center gap-2 mb-3">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]">
              <Icon name="check" size={14} aria-hidden="true" />
            </span>
            <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
              2. Bạn có thể làm gì tiếp theo
            </h3>
          </div>

          <div className="grid gap-2.5 sm:grid-cols-2">
            {actions.map((act) => {
              const hasTarget = Boolean(act.target);

              return (
                <div
                  key={act.id}
                  className="flex flex-col justify-between rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 p-3 transition-colors hover:border-[color:var(--shell-border-strong)]"
                  data-testid={`action-card-${act.id}`}
                >
                  <div>
                    <h4 className="text-sm font-semibold text-[var(--text-primary)]">
                      {act.label}
                    </h4>
                    {act.description ? (
                      <p className="mt-1 text-xs text-[var(--text-secondary)] leading-relaxed">
                        {act.description}
                      </p>
                    ) : null}
                  </div>

                  <div className="mt-3 pt-2 border-t border-[color:var(--shell-border)]/40 flex justify-end">
                    {hasTarget ? (
                      <Link
                        href={act.target!}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--text-brand)] hover:underline focus-ring rounded"
                        onClick={() => onActionClick?.(act)}
                      >
                        <span>Thực hiện ngay</span>
                        <Icon name="arrow-right" size={13} aria-hidden="true" />
                      </Link>
                    ) : (
                      <button
                        type="button"
                        onClick={() => onActionClick?.(act)}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--text-brand)] hover:underline focus-ring rounded"
                      >
                        <span>Thực hiện ngay</span>
                        <Icon name="arrow-right" size={13} aria-hidden="true" />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      ) : null}

      {/* 3. DỰA TRÊN ĐÂU (Personal evidence & External sources + Disclosure) */}
      <section
        aria-label="Dựa trên đâu"
        className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-xs"
        data-testid="answer-evidence-section"
      >
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
              <Icon name="folder" size={14} aria-hidden="true" />
            </span>
            <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
              3. Dựa trên đâu
            </h3>
          </div>

          {onOpenEvidenceDrawer && totalEvidenceCount > 0 ? (
            <button
              type="button"
              onClick={onOpenEvidenceDrawer}
              className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--text-brand)] hover:underline focus-ring rounded"
              data-testid="answer-evidence-drawer-button"
            >
              <span>Xem chi tiết hồ sơ & nguồn ({totalEvidenceCount})</span>
              <Icon name="arrow-right" size={13} aria-hidden="true" />
            </button>
          ) : null}
        </div>

        {/* Context Disclosure Badge */}
        {disclosure && disclosure.used_personal_context ? (
          <div className="mb-3">
            <ContextDisclosureBadge
              disclosure={disclosure}
              personalEvidenceCount={personal_evidence.length}
              onOpenEvidenceDrawer={onOpenEvidenceDrawer}
            />
          </div>
        ) : null}

        {/* Evidence items summary strip */}
        <div className="flex flex-wrap gap-2 text-xs">
          {personal_evidence.slice(0, 3).map((item) => (
            <span
              key={item.id}
              className="inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1 text-[var(--text-secondary)]"
            >
              <Icon name="check" size={12} className="text-[var(--status-ok-text)]" aria-hidden="true" />
              <span className="font-medium text-[var(--text-primary)]">{item.title}</span>
            </span>
          ))}

          {external_sources.slice(0, 2).map((src) => (
            <span
              key={src.id}
              className="inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1 text-[var(--text-muted)]"
            >
              <Icon name="clinical-notes" size={12} aria-hidden="true" />
              <span className="truncate max-w-[180px]">{src.title}</span>
            </span>
          ))}

          {totalEvidenceCount === 0 && !disclosure?.used_personal_context ? (
            <p className="text-xs text-[var(--text-muted)]">
              Trả lời dựa trên kiến thức y khoa đại chúng và mô tả trong câu hỏi của bạn.
            </p>
          ) : null}
        </div>
      </section>

      {/* 4. ĐIỀU CLARA CHƯA BIẾT HOẶC CHƯA CHẮC (Unknowns) */}
      {unknowns.length > 0 ? (
        <section
          aria-label="Điều CLARA chưa biết hoặc chưa chắc"
          className="rounded-[var(--radius-xl)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)]/40 p-4 shadow-xs"
          data-testid="answer-unknowns-section"
        >
          <div className="flex items-center gap-2 mb-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]">
              <Icon name="help" size={14} aria-hidden="true" />
            </span>
            <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--status-warn-text)]">
              4. Điều CLARA chưa biết hoặc chưa chắc
            </h3>
          </div>

          <p className="text-xs text-[var(--text-secondary)] mb-2.5">
            Các yếu tố sau có thể làm thay đổi câu trả lời hoặc cần bác sĩ trực tiếp đánh giá:
          </p>

          <ul className="space-y-1.5 text-xs text-[var(--text-primary)] list-disc pl-5">
            {unknowns.map((unk: ConsumerUnknownDto, idx: number) => {
              if (typeof unk === "string") {
                return <li key={idx}>{unk}</li>;
              }
              return (
                <li key={unk.id || idx}>
                  <span className="font-semibold">{unk.missing_factor}: </span>
                  <span className="text-[var(--text-secondary)]">{unk.why_it_matters}</span>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      {/* 5. KHI NÀO CẦN HỖ TRỢ Y TẾ (Routine / Non-emergency Safety Section) */}
      {safety && !safetyMeta.isEmergency && !safetyMeta.isUrgent ? (
        <section
          aria-label="Khi nào cần hỗ trợ y tế"
          className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 p-4 shadow-xs"
          data-testid="answer-safety-routine-section"
        >
          <div className="flex items-center gap-2 mb-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
              <Icon name="warning" size={14} aria-hidden="true" />
            </span>
            <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
              5. Khi nào cần hỗ trợ y tế
            </h3>
            <Badge tone={safetyMeta.tone}>{safetyMeta.label}</Badge>
          </div>

          <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
            {safety.guidance ||
              "Nếu triệu chứng kéo dài hoặc xuất hiện dấu hiệu bất thường, hãy trao đổi trực tiếp với bác sĩ điều trị để được chẩn đoán chính xác."}
          </p>
        </section>
      ) : null}
    </div>
  );
}

export default AnswerRenderer;
