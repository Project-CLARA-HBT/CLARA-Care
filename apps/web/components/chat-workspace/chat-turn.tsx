import MarkdownAnswer from "@/components/research/markdown-answer";
import { formatHistoryTime } from "@/components/research/lib/research-page-helpers";
import { ConversationItem } from "@/components/research/lib/research-page-types";

type ChatTurnProps = {
  turn: ConversationItem;
};

function toTextSnippet(value: string, maxLength = 220): string {
  const normalized = value
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/[#>*_`~\[\]()]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!normalized) return "Không có tóm tắt ngắn cho lượt trả lời này.";
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength)}...`;
}

function confidenceToPercent(value?: number): number {
  if (typeof value !== "number" || Number.isNaN(value)) return 0;
  if (value > 1) return Math.max(0, Math.min(100, value));
  return Math.max(0, Math.min(100, value * 100));
}

export default function ChatTurn({ turn }: ChatTurnProps) {
  const result = turn.result;
  const answer = result.answer || "";
  const citations = result.tier === "tier2" ? result.citations : [];
  const confidence =
    result.tier === "tier2"
      ? confidenceToPercent(result.verificationStatus?.confidence ?? result.debug.routing?.confidence)
      : 0;

  const quickSummary = toTextSnippet(answer);
  const matrixRows =
    result.tier === "tier2"
      ? result.telemetry.verificationMatrix.slice(0, 3)
      : [];

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <article className="max-w-[82%] rounded-2xl rounded-tr-none bg-[var(--surface-muted)] px-5 py-3 text-sm text-[var(--text-primary)] shadow-sm">
          <p className="whitespace-pre-wrap">{turn.query}</p>
        </article>
      </div>

      <div className="flex justify-start gap-3">
        <div className="clara-glow-cyan flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-cyan-400/30 bg-cyan-400/10">
          <span className="material-symbols-outlined text-cyan-300" style={{ fontVariationSettings: "'FILL' 1" }}>
            smart_toy
          </span>
        </div>

        <article className="w-full space-y-4">
          {result.tier === "tier2" ? (
            <div className="grid grid-cols-12 gap-4">
              <section className="clara-glass-panel clara-glow-cyan col-span-12 rounded-xl border border-[color:var(--shell-border)] border-l-4 border-l-cyan-400 p-5">
                <h3 className="mb-2 text-[11px] font-bold uppercase tracking-[0.2em] text-cyan-300">Kết luận nhanh</h3>
                <p className="text-base font-semibold leading-snug text-[var(--text-primary)]">{quickSummary}</p>
              </section>

              <section className="col-span-12 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4 md:col-span-7">
                <div className="mb-3 flex items-center justify-between gap-2">
                  <h3 className="flex items-center gap-2 text-sm font-bold text-[var(--text-secondary)]">
                    <span className="material-symbols-outlined text-sm text-cyan-300">security</span>
                    Ma trận quyết định an toàn
                  </h3>
                  <span className="rounded bg-cyan-400/20 px-2 py-0.5 text-[10px] text-cyan-300">AI Verified</span>
                </div>

                {matrixRows.length ? (
                  <div className="space-y-2">
                    <div className="grid grid-cols-3 gap-2 text-[10px] font-bold uppercase text-[var(--text-muted)]">
                      <div>Claim</div>
                      <div>Verdict</div>
                      <div>Confidence</div>
                    </div>
                    {matrixRows.map((row, index) => (
                      <div
                        key={`${turn.id}-matrix-${index}`}
                        className="grid grid-cols-3 items-center gap-2 border-t border-[color:var(--shell-border)] py-2"
                      >
                        <div className="line-clamp-2 text-xs text-[var(--text-primary)]">{row.claim}</div>
                        <div className="text-xs text-cyan-300">{row.verdict || row.supportStatus || "N/A"}</div>
                        <div className="text-xs text-[var(--text-secondary)]">
                          {typeof row.confidence === "number" ? `${confidenceToPercent(row.confidence).toFixed(0)}%` : "--"}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-[var(--text-muted)]">Chưa có verification matrix cho lượt trả lời này.</p>
                )}
              </section>

              <section className="col-span-12 flex flex-col items-center justify-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 md:col-span-5">
                <h3 className="mb-4 w-full text-sm font-bold text-[var(--text-secondary)]">Độ tin cậy dữ liệu</h3>
                <div className="relative flex h-32 w-32 items-center justify-center">
                  <svg className="h-full w-full -rotate-90" viewBox="0 0 128 128" aria-hidden="true">
                    <circle cx="64" cy="64" r="58" fill="transparent" stroke="rgba(141,145,154,0.22)" strokeWidth="8" />
                    <circle
                      cx="64"
                      cy="64"
                      r="58"
                      fill="transparent"
                      stroke="rgb(40, 217, 243)"
                      strokeWidth="8"
                      strokeDasharray="364.4"
                      strokeDashoffset={String(364.4 - (Math.max(0, Math.min(100, confidence)) / 100) * 364.4)}
                    />
                  </svg>
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="text-2xl font-bold text-[var(--text-primary)]">{confidence.toFixed(0)}%</span>
                    <span className="text-[9px] uppercase tracking-[0.18em] text-[var(--text-muted)]">Confidence</span>
                  </div>
                </div>
                <p className="mt-4 text-center text-[10px] text-[var(--text-muted)]">
                  {citations.length} nguồn trích dẫn • {result.debug.telemetryDocCount} tài liệu đã đối chiếu
                </p>
              </section>

              <section className="clara-glass-panel col-span-12 rounded-xl border border-[color:var(--shell-border)] p-5">
                <h3 className="mb-3 flex items-center gap-2 text-sm font-bold text-[var(--text-secondary)]">
                  <span className="material-symbols-outlined text-sm text-cyan-300">subject</span>
                  Phân tích chi tiết
                </h3>
                <MarkdownAnswer answer={answer} citations={citations} />
              </section>
            </div>
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
              <MarkdownAnswer answer={answer} citations={[]} />
            </div>
          )}
        </article>
      </div>
    </div>
  );
}
