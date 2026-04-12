import MarkdownAnswer from "@/components/research/markdown-answer";
import { formatHistoryTime } from "@/components/research/lib/research-page-helpers";
import { ConversationItem } from "@/components/research/lib/research-page-types";

type ChatTurnProps = {
  turn: ConversationItem;
};

function sanitizeChatboxAnswer(raw: string): string {
  if (!raw.trim()) return raw;

  let sanitized = raw;

  // Remove fallback-local sentence if model includes it in answer body.
  sanitized = sanitized.replace(
    /hệ thống tạm thời dùng fallback local để đảm bảo không gián đoạn trả lời\.?/gi,
    ""
  );

  // Trim duplicated empty lines after sanitization.
  sanitized = sanitized.replace(/\n{3,}/g, "\n\n").trim();
  return sanitized || raw;
}

export default function ChatTurn({ turn }: ChatTurnProps) {
  const result = turn.result;
  const answer = sanitizeChatboxAnswer(result.answer || "");
  const citations = result.tier === "tier2" ? result.citations : [];

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <article className="max-w-[90%] rounded-2xl rounded-tr-none bg-[var(--surface-muted)] px-5 py-3 text-sm text-[var(--text-primary)] shadow-sm">
          <p className="whitespace-pre-wrap">{turn.query}</p>
        </article>
      </div>

      <div className="flex justify-start gap-3">
        <div className="clara-glow-cyan flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-cyan-300/60 bg-cyan-500/10 dark:border-cyan-400/30">
          <span className="material-symbols-outlined text-cyan-700 dark:text-cyan-300" style={{ fontVariationSettings: "'FILL' 1" }}>
            smart_toy
          </span>
        </div>

        <article className="w-full space-y-4">
          {result.tier === "tier2" ? (
            <section className="clara-glass-panel rounded-xl border border-[color:var(--shell-border)] p-5">
              <h3 className="mb-3 flex items-center gap-2 text-sm font-bold text-[var(--text-secondary)]">
                <span className="material-symbols-outlined text-sm text-cyan-700 dark:text-cyan-300">subject</span>
                Phân tích chi tiết
              </h3>
              <MarkdownAnswer
                answer={answer}
                citations={citations}
                showInlineCitations={false}
                enableMermaid={false}
                stripReferenceSection={false}
                stripSafetyMatrixSection={false}
                stripMermaidBlocks={true}
                stripChartSpecBlocks={true}
              />
            </section>
          ) : (
            <div className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-4 sm:px-5">
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <span className="inline-flex min-h-[28px] items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--text-secondary)]">
                  CLARA
                </span>
                <span className="inline-flex min-h-[28px] items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--text-secondary)]">
                  Quick
                </span>
                <span className="text-[10px] text-[var(--text-muted)]">{formatHistoryTime(turn.createdAt)}</span>
              </div>
              <MarkdownAnswer
                answer={answer}
                citations={[]}
                showInlineCitations={false}
                enableMermaid={false}
                stripReferenceSection={false}
                stripSafetyMatrixSection={false}
                stripMermaidBlocks={true}
                stripChartSpecBlocks={true}
              />
            </div>
          )}
        </article>
      </div>
    </div>
  );
}
