"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import CouncilWorkspaceNav from "@/components/council/council-workspace-nav";
import PageShell from "@/components/ui/page-shell";
import { formatLocaleDate, t } from "@/lib/i18n/catalog";
import { safeUserFacingError } from "@/lib/user-facing-text";
import { useUILanguage } from "@/lib/use-ui-language";
import {
  CouncilCaseRecord,
  createCouncilCase,
  listCouncilCases,
  setActiveCouncilCaseId,
} from "@/lib/council";

function formatTime(language: "vi" | "en", value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  return formatLocaleDate(language, date, {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function CouncilNewPage() {
  const router = useRouter();
  const language = useUILanguage();
  const [cases, setCases] = useState<CouncilCaseRecord[]>([]);
  const [error, setError] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setIsLoading(true);
      setError("");
      try {
        const response = await listCouncilCases(10, 0);
        setCases(response.items);
      } catch (cause) {
        setError(safeUserFacingError(cause, t(language, "council.error.loadCases")));
      } finally {
        setIsLoading(false);
      }
    };
    void load();
  }, [language]);

  const onCreateCase = async () => {
    setIsCreating(true);
    setError("");
    try {
      const created = await createCouncilCase({
        title: t(language, "council.new.caseFallback", {
          id: formatLocaleDate(language, new Date(), { dateStyle: "short", timeStyle: "short" }),
        }),
      });
      setActiveCouncilCaseId(created.id);
      router.push(`/council/new/intake?caseId=${created.id}`);
    } catch (cause) {
      setError(safeUserFacingError(cause, t(language, "council.error.createCase")));
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <PageShell
      title={t(language, "council.new.title")}
      description={t(language, "council.new.description")}
      variant="plain"
    >
      <div className="space-y-5">
        <CouncilWorkspaceNav />

        <section className="rounded-[var(--radius-xl)] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">{t(language, "council.new.flow")}</p>
          <h2 className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">{t(language, "council.new.heading")}</h2>
          <p className="mt-2 text-sm leading-7 text-[var(--text-secondary)]">
            {t(language, "council.new.intro")}
          </p>

          <button
            type="button"
            onClick={() => void onCreateCase()}
            disabled={isCreating}
            className="mt-5 inline-flex min-h-[46px] items-center rounded-[var(--radius-md)] border border-[color:var(--brand-700)] bg-[var(--brand-600)] px-5 text-sm font-semibold text-[#cdd7ff] transition-colors hover:bg-[var(--brand-700)] disabled:opacity-60"
          >
            {isCreating ? t(language, "council.new.creating") : t(language, "council.new.create")}
          </button>
        </section>

        <section className="rounded-[var(--radius-xl)] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">{t(language, "council.new.recent")}</h3>
            <Link href="/council" className="text-xs font-semibold text-[var(--text-brand)] hover:underline">
              {t(language, "council.new.openLanding")}
            </Link>
          </div>

          {isLoading ? <p className="text-sm text-[var(--text-secondary)]">{t(language, "council.new.loading")}</p> : null}
          {!isLoading && cases.length === 0 ? (
            <p className="text-sm text-[var(--text-secondary)]">{t(language, "council.new.empty")}</p>
          ) : null}

          <div className="space-y-2">
            {cases.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  setActiveCouncilCaseId(item.id);
                  router.push(`/council/new/intake?caseId=${item.id}`);
                }}
                className="flex w-full items-center justify-between rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-3 text-left transition-colors hover:border-[color:var(--brand-primary)]/40"
              >
                <span>
                  <p className="text-sm font-semibold text-[var(--text-primary)]">{item.title || t(language, "council.new.caseFallback", { id: item.id })}</p>
                  <p className="text-xs text-[var(--text-secondary)]">
                    #{item.id} · {item.status} · {formatTime(language, item.updated_at)}
                  </p>
                </span>
                <span className="material-symbols-outlined text-[var(--text-secondary)]">chevron_right</span>
              </button>
            ))}
          </div>
        </section>

        {error ? <p className="text-sm text-[var(--status-danger-text)]">{error}</p> : null}
      </div>
    </PageShell>
  );
}
