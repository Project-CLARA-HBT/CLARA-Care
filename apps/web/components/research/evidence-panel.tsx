import { Tier2Citation } from "@/lib/research";

type EvidencePanelProps = {
  citations: Tier2Citation[];
};

export default function EvidencePanel({ citations }: EvidencePanelProps) {
  return (
    <section className="rounded-3xl border border-slate-200/85 bg-white/90 p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">Evidence</p>
        <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] text-slate-600 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300">
          {citations.length}
        </span>
      </div>

      {citations.length ? (
        <div className="mt-3 space-y-2">
          {citations.map((citation, index) => (
            <article
              id={`citation-${index + 1}`}
              key={`${citation.title}-${index}`}
              className="rounded-2xl border border-slate-200 bg-slate-50/90 p-3 dark:border-slate-700 dark:bg-slate-800/75"
            >
              <p className="text-xs font-semibold text-sky-700 dark:text-sky-300">
                [{index + 1}] {citation.source ?? citation.title}
              </p>
              <p className="mt-1 text-sm text-slate-700 dark:text-slate-200">{citation.title}</p>
              {citation.trustTier !== undefined || citation.publishedAt ? (
                <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                  {citation.trustTier !== undefined ? (
                    <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
                      Tier {citation.trustTier}
                    </span>
                  ) : null}
                  {citation.publishedAt ? (
                    <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-medium text-slate-600 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300">
                      {citation.publishedAt}
                    </span>
                  ) : null}
                </div>
              ) : null}
              {citation.snippet ? (
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{citation.snippet}</p>
              ) : null}
              {citation.url ? (
                <a
                  href={citation.url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 inline-block text-xs font-semibold text-sky-700 hover:underline dark:text-sky-300"
                >
                  Mở nguồn
                </a>
              ) : (
                <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">Nguồn nội bộ hoặc tài liệu upload.</p>
              )}
            </article>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">Chưa có nguồn bằng chứng cho câu trả lời hiện tại.</p>
      )}
    </section>
  );
}
