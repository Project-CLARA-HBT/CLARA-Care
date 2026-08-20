"use client";

import { useState } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
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

  const mainMessage =
    answer?.main_message ||
    (envelope as any).main_message ||
    (typeof answer === "string" ? answer : "") ||
    (envelope as any).message ||
    (envelope as any).text ||
    "";
  const rawActions = (answer?.actions ?? (envelope as any).actions ?? []) as Array<
    ConsumerAnswerActionDto | string
  >;
  const actions: ConsumerAnswerActionDto[] = rawActions.map((act, idx) => {
    if (typeof act === "string") {
      return {
        id: `act_${idx}`,
        label: act,
        description: undefined,
        target: undefined,
      };
    }
    return {
      id: act.id || `act_${idx}`,
      label: act.label || (act as any).title || (act as any).name || String(act),
      description: act.description,
      target: act.target,
    };
  });

  const sections = answer?.sections ?? [];
  const totalEvidenceCount = personal_evidence.length + external_sources.length;

  const safetyMeta = resolveSafetyTone(safety?.urgency);
  const [copied, setCopied] = useState(false);
  const [showEvidence, setShowEvidence] = useState(false);

  const handleCopyAnswer = async () => {
    try {
      await navigator.clipboard.writeText(mainMessage);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore
    }
  };

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
        className="relative overflow-hidden rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-sm transition-all hover:shadow-md"
        data-testid="answer-main-message-section"
      >
        {/* Top subtle gradient accent line */}
        <div className="h-1 w-full bg-gradient-to-r from-[var(--brand-600)] via-[var(--brand-400)] to-emerald-400" />

        <div className="p-5 sm:p-6">
          <div className="flex items-center justify-between gap-3 mb-4 pb-3 border-b border-[color:var(--shell-border)]/50">
            <div className="flex items-center gap-2.5">
              <span className="flex h-7 w-7 items-center justify-center rounded-xl bg-[var(--surface-brand-soft)] text-[var(--text-brand)] shadow-xs">
                <Icon name="clinical-notes" size={15} aria-hidden="true" />
              </span>
              <div>
                <h2 className="text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
                  1. Điều quan trọng nhất
                </h2>
                <span className="text-[11px] text-[var(--text-muted)] font-normal">
                  Tổng hợp phân tích từ trợ lý y tế CLARA
                </span>
              </div>
            </div>

            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={handleCopyAnswer}
                className="inline-flex items-center gap-1.5 rounded-lg border border-[color:var(--shell-border)]/80 bg-[var(--surface-muted)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]/80 hover:text-[var(--text-primary)] transition-all focus-ring active:scale-95"
                title="Sao chép toàn bộ câu trả lời"
                aria-label="Sao chép nội dung câu trả lời"
              >
                <Icon name={copied ? "check" : "clinical-notes"} size={13} aria-hidden="true" className={copied ? "text-emerald-500" : ""} />
                <span className={copied ? "font-semibold text-emerald-600 dark:text-emerald-400" : ""}>
                  {copied ? "Đã sao chép!" : "Sao chép"}
                </span>
              </button>
            </div>
          </div>

          <div
            className="medical-markdown text-base leading-relaxed text-[var(--text-primary)] font-normal space-y-3"
            data-testid="answer-main-message"
          >
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                h1: ({ children }) => (
                  <h1 className="text-lg sm:text-xl font-bold text-[var(--text-primary)] mt-5 mb-3 pb-1.5 border-b border-[color:var(--shell-border)]/70">
                    {children}
                  </h1>
                ),
                h2: ({ children }) => (
                  <h2 className="text-base sm:text-lg font-bold text-[var(--text-brand)] mt-4 mb-2 pb-1 border-b border-[color:var(--shell-border)]/40 flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-[var(--brand-500)]" />
                    <span>{children}</span>
                  </h2>
                ),
                h3: ({ children }) => (
                  <h3 className="text-sm sm:text-base font-semibold text-[var(--text-primary)] mt-3.5 mb-1.5">
                    {children}
                  </h3>
                ),
                p: ({ children }) => (
                  <p className="mb-3 leading-[1.75] text-[15px] text-[var(--text-primary)] last:mb-0">
                    {children}
                  </p>
                ),
                ul: ({ children }) => (
                  <ul className="list-disc pl-6 my-3 space-y-2 text-[15px] text-[var(--text-primary)]">
                    {children}
                  </ul>
                ),
                ol: ({ children }) => (
                  <ol className="list-decimal pl-6 my-3 space-y-2 text-[15px] text-[var(--text-primary)]">
                    {children}
                  </ol>
                ),
                li: ({ children }) => (
                  <li className="leading-[1.7] pl-1">{children}</li>
                ),
                strong: ({ children }) => (
                  <strong className="font-bold text-[var(--text-primary)] bg-[var(--surface-brand-soft)]/60 text-[var(--text-brand-strong)] px-1.5 py-0.5 rounded-md shadow-xs">
                    {children}
                  </strong>
                ),
                table: ({ children }) => (
                  <div className="my-4 overflow-hidden rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-sm">
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-[color:var(--shell-border)] text-left text-xs sm:text-sm">
                        {children}
                      </table>
                    </div>
                  </div>
                ),
                thead: ({ children }) => (
                  <thead className="bg-[var(--surface-muted)] font-bold text-[var(--text-primary)] border-b border-[color:var(--shell-border)]">
                    {children}
                  </thead>
                ),
                tbody: ({ children }) => (
                  <tbody className="divide-y divide-[color:var(--shell-border)]/40">
                    {children}
                  </tbody>
                ),
                tr: ({ children }) => (
                  <tr className="hover:bg-[var(--surface-muted)]/50 transition-colors">
                    {children}
                  </tr>
                ),
                th: ({ children }) => (
                  <th className="px-4 py-3 text-xs sm:text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider">
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td className="px-4 py-3 text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed">
                    {children}
                  </td>
                ),
                blockquote: ({ children }) => (
                  <blockquote className="border-l-4 border-[var(--brand-500)] pl-4 py-2 my-3 text-sm italic text-[var(--text-secondary)] bg-[var(--surface-muted)]/60 rounded-r-xl">
                    {children}
                  </blockquote>
                ),
                hr: () => (
                  <hr className="my-5 border-t border-[color:var(--shell-border)]/80" />
                ),
              }}
            >
              {mainMessage}
            </ReactMarkdown>
            {isStreaming ? (
              <span className="inline-block h-4 w-2 ml-1 animate-pulse bg-[var(--brand-500)] align-middle rounded-xs" />
            ) : null}
          </div>

          {/* Narrative subsections if present */}
          {sections.length > 0 ? (
            <div className="mt-5 space-y-3 pt-4 border-t border-[color:var(--shell-border)]/70">
              {sections.map((sec, idx) => (
                <div key={idx} className="space-y-1.5 rounded-xl bg-[var(--surface-muted)]/40 p-3.5 border border-[color:var(--shell-border)]/40">
                  <h3 className="text-sm font-bold text-[var(--text-primary)] flex items-center gap-2">
                    <span className="h-1.5 w-1.5 rounded-full bg-[var(--brand-500)]" />
                    <span>{sec.title}</span>
                  </h3>
                  <div className="medical-markdown text-sm leading-relaxed text-[var(--text-secondary)]">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {sec.content}
                    </ReactMarkdown>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </div>
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
          className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-xs transition-all hover:shadow-sm"
          data-testid="answer-actions-section"
        >
          <div className="flex items-center gap-2.5 mb-4">
            <span className="flex h-7 w-7 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 shadow-xs">
              <Icon name="check" size={15} aria-hidden="true" />
            </span>
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                2. Bạn có thể làm gì tiếp theo
              </h3>
              <span className="text-[11px] text-[var(--text-muted)] font-normal">
                Kế hoạch theo dõi và chăm sóc được khuyến nghị
              </span>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {actions.map((act, idx) => {
              const hasTarget = Boolean(act.target);

              return (
                <div
                  key={act.id}
                  className="group relative flex flex-col justify-between rounded-xl border border-[color:var(--shell-border)]/80 bg-[var(--surface-muted)]/40 p-4 transition-all duration-200 hover:-translate-y-0.5 hover:border-[color:var(--brand-500)]/60 hover:bg-[var(--surface-muted)]/80 hover:shadow-sm"
                  data-testid={`action-card-${act.id}`}
                >
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[var(--surface-brand-soft)] text-[10px] font-bold text-[var(--text-brand)]">
                        {String(idx + 1).padStart(2, "0")}
                      </span>
                      <h4 className="text-sm font-semibold text-[var(--text-primary)] leading-snug">
                        {act.label}
                      </h4>
                    </div>
                    {act.description ? (
                      <p className="mt-1 text-xs text-[var(--text-secondary)] leading-relaxed pl-7">
                        {act.description}
                      </p>
                    ) : null}
                  </div>

                  <div className="mt-3.5 pt-2.5 border-t border-[color:var(--shell-border)]/50 flex justify-end">
                    {hasTarget ? (
                      <Link
                        href={act.target!}
                        className="inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--text-brand)] hover:underline focus-ring rounded group-hover:text-[var(--brand-600)] dark:group-hover:text-[var(--brand-400)]"
                        onClick={() => onActionClick?.(act)}
                      >
                        <span>Thực hiện ngay</span>
                        <Icon name="arrow-right" size={13} className="transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
                      </Link>
                    ) : (
                      <button
                        type="button"
                        onClick={() => onActionClick?.(act)}
                        className="inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--text-brand)] hover:underline focus-ring rounded group-hover:text-[var(--brand-600)] dark:group-hover:text-[var(--brand-400)]"
                      >
                        <span>Thực hiện ngay</span>
                        <Icon name="arrow-right" size={13} className="transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
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
        <div className="flex items-center justify-between mb-2.5">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
              <Icon name="folder" size={14} aria-hidden="true" />
            </span>
            <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
              3. Dựa trên đâu
            </h3>
            {totalEvidenceCount > 0 ? (
              <Badge tone="neutral">{totalEvidenceCount} nguồn</Badge>
            ) : null}
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
          <div className="mb-2.5">
            <ContextDisclosureBadge
              disclosure={disclosure}
              personalEvidenceCount={personal_evidence.length}
              onOpenEvidenceDrawer={onOpenEvidenceDrawer}
            />
          </div>
        ) : null}

        {/* Collapsible Evidence List (Hidden/Collapsed by default) */}
        <details
          className="group rounded-lg border border-[color:var(--shell-border)]/50 bg-[var(--surface-muted)]/30 p-2.5 transition-all"
          data-testid="answer-evidence-accordion"
        >
          <summary className="flex cursor-pointer select-none items-center justify-between text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
            <span className="flex items-center gap-1.5">
              <Icon name="clinical-notes" size={13} aria-hidden="true" />
              <span>Danh sách tài liệu tham khảo & hồ sơ ({totalEvidenceCount})</span>
            </span>
            <span className="text-[11px] text-[var(--text-brand)] underline">
              Bấm để xem/ẩn
            </span>
          </summary>

          <div className="mt-3 flex flex-wrap gap-2 pt-2.5 border-t border-[color:var(--shell-border)]/50 text-xs">
            {personal_evidence.map((item) => (
              <span
                key={item.id}
                className="inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1 text-[var(--text-secondary)]"
              >
                <Icon name="check" size={12} className="text-[var(--status-ok-text)]" aria-hidden="true" />
                <span className="font-medium text-[var(--text-primary)]">{item.title}</span>
              </span>
            ))}

            {external_sources.map((src) => (
              <span
                key={src.id}
                className="inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1 text-[var(--text-muted)]"
              >
                <Icon name="clinical-notes" size={12} aria-hidden="true" />
                <span className="truncate max-w-[240px]">{src.title}</span>
              </span>
            ))}

            {totalEvidenceCount === 0 && !disclosure?.used_personal_context ? (
              <p className="text-xs text-[var(--text-muted)]">
                Trả lời dựa trên kiến thức y khoa đại chúng và mô tả trong câu hỏi của bạn.
              </p>
            ) : null}
          </div>
        </details>
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
