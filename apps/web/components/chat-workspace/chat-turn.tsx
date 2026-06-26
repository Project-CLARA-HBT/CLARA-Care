import MarkdownAnswer from "@/components/research/markdown-answer";
import { formatHistoryTime } from "@/components/research/lib/research-page-helpers";
import { ConversationItem } from "@/components/research/lib/research-page-types";
import type { UILanguage } from "@/lib/ui-language";

type ChatTurnProps = {
  turn: ConversationItem;
  uiLanguage: UILanguage;
};

function sanitizeChatboxAnswer(raw: string): string {
  if (!raw.trim()) return raw;

  let sanitized = raw;

  sanitized = sanitized.replace(
    /hệ thống tạm thời dùng fallback local để đảm bảo không gián đoạn trả lời\.?/gi,
    ""
  );
  sanitized = sanitized.replace(
    /hệ thống chuyển sang chế độ tổng hợp an toàn để duy trì phản hồi ổn định\.?/gi,
    ""
  );
  sanitized = sanitized.replace(
    /-+\s*dưới đây là ngữ cảnh đã truy xuất và rút gọn ở chế độ cục bộ:\s*/gi,
    ""
  );

  sanitized = sanitized.replace(/\n{3,}/g, "\n\n").trim();
  return sanitized || raw;
}

export default function ChatTurn({ turn, uiLanguage }: ChatTurnProps) {
  const result = turn.result;
  const answer = sanitizeChatboxAnswer(result.answer || "");
  const citations = result.tier === "tier2" ? result.citations : [];
  // Claim-to-study traceability + Citation Registry (Requirement 11). Surfaced
  // only on tier2 results that carry them; tolerate persisted results where the
  // fields may be absent.
  const tracedClaims = result.tier === "tier2" ? result.tracedClaims ?? [] : [];
  const citationRegistry = result.tier === "tier2" ? result.citationRegistry ?? [] : [];

  return (
    <div className="space-y-1.5">
      <div className="flex justify-end pr-2 sm:pr-6">
        <article className="max-w-[88%] rounded-[0.78rem] rounded-tr-sm border border-cyan-200/70 bg-cyan-50/96 px-3.5 py-2 text-[13px] leading-6 text-slate-800 shadow-[0_10px_24px_-28px_rgba(14,116,144,0.34)] dark:border-cyan-500/20 dark:bg-cyan-500/10 dark:text-slate-100 sm:max-w-[58%]">
          <p className="whitespace-pre-wrap">{turn.query}</p>
        </article>
      </div>

      <div className="flex justify-start">
        <article className="min-w-0 w-full max-w-[85%] lg:max-w-[75%]">
          <div className="mb-1 flex flex-wrap items-center gap-2 text-[9px] text-[var(--text-muted)]">
            <span className="text-[10px] font-semibold text-[var(--text-primary)]">CLARA</span>
            <span className="h-1 w-1 rounded-full bg-[var(--text-muted)]/70" />
            <span>{formatHistoryTime(turn.createdAt)}</span>
          </div>

          <section className="rounded-[0.68rem] border border-[color:var(--shell-border-strong)] bg-[var(--surface-panel)] p-3.5 shadow-[0_12px_28px_-26px_rgba(15,23,42,0.28)] sm:p-4">
            <MarkdownAnswer
              answer={answer}
              citations={citations}
              showInlineCitations={true}
              enableMermaid={false}
              stripReferenceSection={true}
              stripSafetyMatrixSection={true}
              stripMermaidBlocks={true}
              stripChartSpecBlocks={true}
              uiLanguage={uiLanguage}
              tracedClaims={tracedClaims}
              citationRegistry={citationRegistry}
            />
          </section>
        </article>
      </div>
    </div>
  );
}
