type HistoryItem = {
  id: string;
  label: string;
  timestamp: string;
  tier: "tier1" | "tier2";
  active: boolean;
};

type HistoryPanelProps = {
  items: HistoryItem[];
  suggestions: readonly string[];
  onOpenConversation: (id: string) => void;
  onPickSuggestion: (query: string) => void;
};

export default function HistoryPanel({
  items,
  suggestions,
  onOpenConversation,
  onPickSuggestion
}: HistoryPanelProps) {
  return (
    <div className="space-y-4">
      <section className="rounded-[14px] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
        <div className="flex items-center justify-between gap-2">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">
            Conversations
          </p>
          <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-0.5 text-[11px] text-[var(--text-secondary)]">
            {items.length}
          </span>
        </div>

        <div className="mt-3 space-y-2">
          {items.length ? (
            items.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => onOpenConversation(item.id)}
                className={[
                  "w-full rounded-2xl border px-3 py-2.5 text-left transition",
                  item.active
                    ? "border-[color:var(--status-ok-border)] bg-[var(--surface-brand-soft)] text-[var(--text-primary)]"
                    : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:border-[color:var(--shell-border-strong)] hover:bg-[var(--surface-panel)]"
                ].join(" ")}
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate text-xs font-semibold">{item.label}</p>
                  <span
                    className={[
                      "rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                      item.tier === "tier2"
                        ? "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]"
                        : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)]"
                    ].join(" ")}
                  >
                    {item.tier}
                  </span>
                </div>
                <p className="mt-1 text-[11px] opacity-80">{item.timestamp}</p>
              </button>
            ))
          ) : (
            <p className="rounded-xl border border-dashed border-[color:var(--shell-border)] px-3 py-3 text-xs text-[var(--text-muted)]">
              Chưa có hội thoại. Gửi câu hỏi đầu tiên để bắt đầu.
            </p>
          )}
        </div>
      </section>

      <section className="rounded-[14px] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">Starter Prompts</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {suggestions.map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => onPickSuggestion(item)}
              className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1.5 text-xs text-[var(--text-secondary)] transition hover:border-[color:var(--status-ok-border)] hover:text-[var(--text-brand)]"
            >
              {item}
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
