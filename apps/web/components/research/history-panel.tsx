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
      <section className="rounded-3xl border border-slate-200/85 bg-white/90 p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
        <div className="flex items-center justify-between gap-2">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">
            Conversations
          </p>
          <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] text-slate-600 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300">
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
                    ? "border-sky-300 bg-gradient-to-r from-sky-50 to-cyan-50 text-sky-900 shadow-[inset_0_0_0_1px_rgba(96,165,250,0.25)] dark:border-sky-600 dark:from-sky-950/35 dark:to-cyan-950/35 dark:text-sky-200"
                    : "border-slate-200 bg-slate-50/80 text-slate-700 hover:border-slate-300 hover:bg-white dark:border-slate-700 dark:bg-slate-800/70 dark:text-slate-200 dark:hover:border-slate-600"
                ].join(" ")}
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate text-xs font-semibold">{item.label}</p>
                  <span
                    className={[
                      "rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                      item.tier === "tier2"
                        ? "border-cyan-300 bg-cyan-100 text-cyan-700 dark:border-cyan-700 dark:bg-cyan-950/40 dark:text-cyan-300"
                        : "border-slate-300 bg-slate-100 text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300"
                    ].join(" ")}
                  >
                    {item.tier}
                  </span>
                </div>
                <p className="mt-1 text-[11px] opacity-80">{item.timestamp}</p>
              </button>
            ))
          ) : (
            <p className="rounded-2xl border border-dashed border-slate-300 px-3 py-3 text-xs text-slate-500 dark:border-slate-700 dark:text-slate-400">
              Chưa có hội thoại. Gửi câu hỏi đầu tiên để bắt đầu.
            </p>
          )}
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200/85 bg-white/90 p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">Starter Prompts</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {suggestions.map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => onPickSuggestion(item)}
              className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 transition hover:border-sky-300 hover:text-sky-700 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-sky-400 dark:hover:text-sky-300"
            >
              {item}
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
