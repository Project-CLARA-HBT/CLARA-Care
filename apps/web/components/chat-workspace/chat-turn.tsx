import MarkdownAnswer from "@/components/research/markdown-answer";
import { formatHistoryTime } from "@/components/research/lib/research-page-helpers";
import { ConversationItem } from "@/components/research/lib/research-page-types";

type ChatTurnProps = {
  turn: ConversationItem;
};

export default function ChatTurn({ turn }: ChatTurnProps) {
  const result = turn.result;
  const answer = result.answer || "";
  const citations = result.tier === "tier2" ? result.citations : [];

  return (
    <div className="space-y-3.5">
      <div className="flex justify-end">
        <article className="max-w-[92%] rounded-2xl border border-cyan-300/50 bg-gradient-to-br from-cyan-500/15 to-sky-500/10 px-4 py-3 text-sm leading-7 text-[var(--text-primary)] shadow-[0_14px_28px_-24px_rgba(14,165,233,0.65)]">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-cyan-700 dark:text-cyan-300">
            Bạn
          </p>
          <p className="mt-1 whitespace-pre-wrap">{turn.query}</p>
        </article>
      </div>

      <div className="flex justify-start">
        <article className="w-full rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-4 sm:px-5">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <span className="inline-flex min-h-[28px] items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--text-secondary)]">
              CLARA
            </span>
            <span className="inline-flex min-h-[28px] items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--text-secondary)]">
              {result.tier === "tier2" ? "Research" : "Quick"}
            </span>
            <span className="text-[10px] text-[var(--text-muted)]">{formatHistoryTime(turn.createdAt)}</span>
          </div>

          <MarkdownAnswer answer={answer} citations={citations} />
        </article>
      </div>
    </div>
  );
}
