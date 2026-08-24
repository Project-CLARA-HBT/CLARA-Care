"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import CouncilFlowStepper from "@/components/council/council-flow-stepper";
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
        setCases(response.items || []);
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
      <div className="mx-auto max-w-3xl space-y-6">
        {/* Step Progress */}
        <CouncilFlowStepper currentStep="case" caseId={activeCaseId} />

        {/* 1. Concise Entry Explanation & Start Draft */}
        <section className="rounded-[1.55rem] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 sm:p-7 shadow-sm">
          <div className="flex items-center gap-2">
            <span className="rounded-md border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
              {language === "vi" ? "Bước 1 / 4 · Khởi tạo ca" : "Step 1 / 4 · Case Entry"}
            </span>
          </div>

          <h2 className="mt-3 text-2xl font-bold tracking-tight text-[var(--text-primary)]">
            {t(language, "council.new.heading")}
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-[var(--text-secondary)]">
            {t(language, "council.new.intro")}
          </p>

          <div className="mt-6 space-y-2">
            <label
              htmlFor="case-title-input"
              className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]"
            >
              {language === "vi" ? "Tiêu đề ca bệnh / Mã hồ sơ (tùy chọn)" : "Case Title / Identifier (optional)"}
            </label>
            <input
              id="case-title-input"
              type="text"
              value={customTitle}
              onChange={(e) => setCustomTitle(e.target.value)}
              placeholder={
                language === "vi"
                  ? "Ví dụ: BN Nam 58T - Đau thắt ngực không ổn định / ĐTĐ type 2"
                  : "e.g. 58yo Male - Unstable Angina / T2D"
              }
              className="w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-3 text-sm text-[var(--text-primary)] focus:border-[color:var(--brand-600)] focus:outline-none"
            />
            <p className="text-xs text-[var(--text-muted)]">
              {language === "vi"
                ? "Có thể bỏ trống để tự động tạo mã định danh theo thời gian."
                : "Leave blank to auto-generate a timestamped case identifier."}
            </p>
          </div>

          <div className="mt-6 flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-[color:var(--shell-border)]">
            <Link
              href="/council"
              className="inline-flex min-h-[44px] items-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-5 text-sm font-semibold text-[var(--text-secondary)] hover:bg-[var(--surface-panel)]"
            >
              {t(language, "council.action.back")}
            </Link>

            <button
              type="button"
              onClick={() => void onCreateCase()}
              disabled={isCreating}
              className="inline-flex min-h-[46px] items-center gap-2 rounded-xl border border-[color:var(--brand-700)] bg-[var(--brand-600)] px-6 text-sm font-bold text-[var(--on-secondary-container)] shadow-sm transition hover:bg-[var(--brand-700)] disabled:opacity-60"
            >
              <Icon name="progress" size={18} />
              <span>{isCreating ? t(language, "council.new.creating") : t(language, "council.new.create")}</span>
              <Icon name="arrow-right" size={16} />
            </button>
          </div>
        </section>

        {/* 2. Resume Draft / Recent Unfinished Cases */}
        {cases.length > 0 ? (
          <section className="rounded-[1.55rem] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">
                {language === "vi" ? "Hoặc tiếp tục ca gần đây" : "Or Resume a Recent Case"}
              </h3>
              <Link href="/council" className="text-xs font-bold text-[var(--text-brand)] hover:underline">
                {t(language, "council.new.openLanding")}
              </Link>
            </div>

            <div className="divide-y divide-[color:var(--shell-border)] rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] overflow-hidden">
              {cases.slice(0, 5).map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => {
                    setActiveCouncilCaseId(item.id);
                    router.push(
                      item.status === "analyzed"
                        ? `/council/result?caseId=${item.id}`
                        : `/council/new/intake?caseId=${item.id}`,
                    );
                  }}
                  className="flex w-full items-center justify-between p-3.5 text-left transition hover:bg-[var(--surface-panel)]"
                >
                  <div className="min-w-0 pr-3">
                    <p className="text-sm font-bold text-[var(--text-primary)] truncate">
                      {item.title || t(language, "council.new.caseFallback", { id: item.id })}
                    </p>
                    <p className="mt-0.5 font-mono text-xs text-[var(--text-muted)]">
                      #{item.id} · <span className="font-sans font-medium">{item.status}</span> ·{" "}
                      {formatLocaleDate(language, item.updated_at, {
                        day: "2-digit",
                        month: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
                  </div>
                  <Icon name="arrow-right" size={16} className="text-[var(--text-muted)] shrink-0" />
                </button>
              ))}
            </div>
          </section>
        ) : null}

        {error ? <p className="text-sm font-semibold text-[var(--status-danger-text)]">{error}</p> : null}
      </div>
    </PageShell>
  );
}
