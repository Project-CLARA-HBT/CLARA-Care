"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import CouncilFlowStepper from "@/components/council/council-flow-stepper";
import CouncilWorkspaceNav from "@/components/council/council-workspace-nav";
import { Icon } from "@/components/ui/icon";
import PageShell from "@/components/ui/page-shell";
import { formatLocaleDate, t } from "@/lib/i18n/catalog";
import { safeUserFacingError } from "@/lib/user-facing-text";
import { useUILanguage } from "@/lib/use-ui-language";
import {
  CouncilCaseRecord,
  createCouncilCase,
  getActiveCouncilCaseId,
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
  const [activeCaseId, setActiveCaseId] = useState<number | null>(null);
  const [customTitle, setCustomTitle] = useState("");
  const [error, setError] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    setActiveCaseId(getActiveCouncilCaseId());
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
      const fallbackTitle = t(language, "council.new.caseFallback", {
        id: formatLocaleDate(language, new Date(), { dateStyle: "short", timeStyle: "short" }),
      });
      const created = await createCouncilCase({
        title: customTitle.trim() || fallbackTitle,
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
        <CouncilFlowStepper currentStep="case" caseId={activeCaseId} />

        <section className="rounded-[var(--radius-xl)] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6">
          <div className="flex items-center gap-2">
            <span className="rounded-md border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
              {language === "vi" ? "Bước 1: Khởi tạo ca bệnh" : "Step 1: Clinical Case"}
            </span>
          </div>
          <h2 className="mt-3 text-2xl font-bold tracking-tight text-[var(--text-primary)]">
            {t(language, "council.new.heading")}
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-[var(--text-secondary)]">
            {t(language, "council.new.intro")}
          </p>

          <div className="mt-5 max-w-xl space-y-3">
            <label htmlFor="case-title-input" className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
              {language === "vi" ? "Tiêu đề ca bệnh / Mã hồ sơ (tùy chọn)" : "Case Title / Identifier (optional)"}
            </label>
            <input
              id="case-title-input"
              type="text"
              value={customTitle}
              onChange={(e) => setCustomTitle(e.target.value)}
              placeholder={language === "vi" ? "Ví dụ: BN Nam 58T - Đau thắt ngực không ổn định / ĐTĐ type 2" : "e.g. 58yo Male - Unstable Angina / T2D"}
              className="w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-2.5 text-sm text-[var(--text-primary)] focus:border-[color:var(--brand-600)] focus:outline-none"
            />
          </div>

          <button
            type="button"
            onClick={() => void onCreateCase()}
            disabled={isCreating}
            className="mt-5 inline-flex min-h-[46px] items-center gap-2 rounded-xl border border-[color:var(--brand-700)] bg-[var(--brand-600)] px-6 text-sm font-bold text-[var(--on-secondary-container)] shadow-sm transition-colors hover:bg-[var(--brand-700)] disabled:opacity-60"
          >
            <Icon name="progress" size={18} />
            {isCreating ? t(language, "council.new.creating") : t(language, "council.new.create")}
          </button>
        </section>

        <section className="rounded-[var(--radius-xl)] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">
              {t(language, "council.new.recent")}
            </h3>
            <Link href="/council" className="text-xs font-bold text-[var(--text-brand)] hover:underline">
              {t(language, "council.new.openLanding")}
            </Link>
          </div>

          {isLoading ? <p className="text-sm text-[var(--text-secondary)]">{t(language, "council.new.loading")}</p> : null}
          {!isLoading && cases.length === 0 ? (
            <p className="text-sm text-[var(--text-secondary)]">{t(language, "council.new.empty")}</p>
          ) : null}

          <div className="space-y-2.5">
            {cases.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  setActiveCouncilCaseId(item.id);
                  router.push(`/council/new/intake?caseId=${item.id}`);
                }}
                className="flex w-full items-center justify-between rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-3.5 text-left transition-colors hover:border-[color:var(--brand-600)] hover:bg-[var(--surface-panel)]"
              >
                <div>
                  <p className="text-sm font-bold text-[var(--text-primary)]">
                    {item.title || t(language, "council.new.caseFallback", { id: item.id })}
                  </p>
                  <p className="mt-0.5 text-xs font-medium text-[var(--text-secondary)]">
                    #{item.id} · <span className="font-mono">{item.status}</span> · {formatTime(language, item.updated_at)}
                  </p>
                </div>
                <Icon name="arrow-right" size={18} className="text-[var(--text-secondary)]" />
              </button>
            ))}
          </div>
        </section>

        {error ? <p className="text-sm font-semibold text-[var(--status-danger-text)]">{error}</p> : null}
      </div>
    </PageShell>
  );
}
