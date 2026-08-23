"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import CouncilFlowStepper from "@/components/council/council-flow-stepper";
import CouncilWorkspaceNav from "@/components/council/council-workspace-nav";
import { Icon } from "@/components/ui/icon";
import PageShell from "@/components/ui/page-shell";
import { trackCouncilRun } from "@/lib/analytics/events";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import { safeUserFacingError } from "@/lib/user-facing-text";
import { useUILanguage } from "@/lib/use-ui-language";
import {
  CouncilCaseRecord,
  CouncilStreamStage,
  getActiveCouncilCaseId,
  getCouncilCase,
  isCouncilStreamingEnabled,
  runCouncilCaseById,
  setActiveCouncilCaseId,
  streamCouncilRun,
} from "@/lib/council";

const SPECIALIST_LABEL_KEYS: Record<string, UITranslationKey> = {
  cardiology: "council.specialist.cardiology",
  neurology: "council.specialist.neurology",
  endocrinology: "council.specialist.endocrinology",
  pharmacology: "council.specialist.pharmacology",
  nephrology: "council.specialist.nephrology",
};

const DELIBERATION_STAGES = [
  { sequence: 1, labelVi: "Tiếp nhận bối cảnh ca bệnh", labelEn: "Ingesting clinical context" },
  { sequence: 2, labelVi: "Trích xuất thực thể & kiểm tra chất lượng", labelEn: "Extracting entities & quality check" },
  { sequence: 3, labelVi: "Điều phối hội đồng chuyên khoa AI", labelEn: "Orchestrating specialist deliberation" },
  { sequence: 4, labelVi: "Kiểm tra tương tác thuốc & an toàn", labelEn: "Checking medication safety & DDI" },
  { sequence: 5, labelVi: "Tổng hợp đồng thuận & phát hiện bất đồng", labelEn: "Synthesizing consensus & divergence" },
  { sequence: 6, labelVi: "Hoàn tất khuyến nghị lâm sàng", labelEn: "Finalizing clinical recommendation" },
];

function parseRequest(caseItem: CouncilCaseRecord | null) {
  const request = (caseItem?.request ?? {}) as Record<string, unknown>;
  const question = typeof request.question === "string" ? request.question.trim() : "";
  const symptoms = Array.isArray(request.symptoms)
    ? request.symptoms.map((item) => String(item).trim()).filter(Boolean)
    : [];
  const labs =
    request.labs && typeof request.labs === "object" && !Array.isArray(request.labs)
      ? (request.labs as Record<string, unknown>)
      : {};
  const medications = Array.isArray(request.medications)
    ? request.medications.map((item) => String(item).trim()).filter(Boolean)
    : [];
  const history = typeof request.history === "string" ? request.history.trim() : "";
  const specialistCount = Number(request.specialist_count ?? 3);
  const specialists = Array.isArray(request.specialists)
    ? request.specialists.map((item) => String(item)).filter(Boolean)
    : [];

  return {
    question,
    symptoms,
    labs,
    medications,
    history,
    specialistCount: Number.isFinite(specialistCount) ? Math.trunc(specialistCount) : 3,
    specialists,
  };
}

export default function CouncilNewReviewPage() {
  const router = useRouter();
  const language = useUILanguage();
  const [queryCaseId, setQueryCaseId] = useState<number | null>(null);
  const [caseItem, setCaseItem] = useState<CouncilCaseRecord | null>(null);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [currentStageIdx, setCurrentStageIdx] = useState(0);

  useEffect(() => {
    const raw = new URLSearchParams(window.location.search).get("caseId");
    const parsed = Number(raw);
    if (Number.isFinite(parsed) && parsed > 0) {
      setQueryCaseId(Math.trunc(parsed));
      return;
    }
    setQueryCaseId(getActiveCouncilCaseId());
  }, []);

  useEffect(() => {
    const bootstrap = async () => {
      setError("");
      try {
        const resolvedCaseId = queryCaseId;
        if (!resolvedCaseId) {
          router.replace("/council/new");
          return;
        }
        const loaded = await getCouncilCase(resolvedCaseId);
        setActiveCouncilCaseId(loaded.id);
        setCaseItem(loaded);
      } catch (cause) {
        setError(safeUserFacingError(cause, t(language, "council.error.loadCase")));
      }
    };
    if (queryCaseId !== null) {
      void bootstrap();
    }
  }, [language, queryCaseId, router]);

  const parsedCase = useMemo(() => parseRequest(caseItem), [caseItem]);
  const specialistNames = parsedCase.specialists
    .map((specialist) => t(language, SPECIALIST_LABEL_KEYS[specialist] ?? "council.review.noneSelected"))
    .join(", ");

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!caseItem) return;

    if (
      parsedCase.symptoms.length === 0 &&
      Object.keys(parsedCase.labs).length === 0 &&
      parsedCase.medications.length === 0 &&
      !parsedCase.history &&
      !parsedCase.question
    ) {
      setError(t(language, "council.review.dataRequired"));
      return;
    }

    if (parsedCase.specialists.length < 2) {
      setError(t(language, "council.specialists.minimum"));
      return;
    }

    setError("");
    setIsSubmitting(true);
    setCurrentStageIdx(1);

    try {
      if (isCouncilStreamingEnabled()) {
        try {
          await streamCouncilRun(
            caseItem.id,
            {
              request: caseItem.request ?? undefined,
              specialist_count: parsedCase.specialistCount,
              specialists: parsedCase.specialists,
            },
            {
              onStage: (stage: CouncilStreamStage) => {
                setCurrentStageIdx(Math.min(stage.sequence, DELIBERATION_STAGES.length));
              },
              onResult: () => {
                trackCouncilRun({ specialistCount: parsedCase.specialists.length });
                setActiveCouncilCaseId(caseItem.id);
                router.push(`/council/result?caseId=${caseItem.id}`);
              },
              onError: (err: string) => {
                throw new Error(err);
              },
            },
          );
          return;
        } catch {
          // Fall back to blocking run
        }
      }

      const updated = await runCouncilCaseById(caseItem.id, {
        request: caseItem.request ?? undefined,
        specialist_count: parsedCase.specialistCount,
        specialists: parsedCase.specialists,
      });

      trackCouncilRun({ specialistCount: parsedCase.specialists.length });
      setActiveCouncilCaseId(updated.id);
      router.push(`/council/result?caseId=${updated.id}`);
    } catch (cause) {
      setError(safeUserFacingError(cause, t(language, "council.error.run")));
      setIsSubmitting(false);
    }
  };

  return (
    <PageShell
      title={t(language, "council.review.title")}
      description={t(language, "council.review.description")}
      variant="plain"
    >
      <div className="space-y-5">
        <CouncilWorkspaceNav />
        <CouncilFlowStepper
          currentStep={isSubmitting ? "run" : "review"}
          caseId={caseItem?.id}
        />

        {isSubmitting ? (
          /* Step 5: Deliberation Execution & Progress */
          <section className="rounded-[var(--radius-xl)] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-8 text-center">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
              <Icon name="progress" size={32} className="animate-spin" />
            </div>
            <h2 className="mt-4 text-2xl font-bold text-[var(--text-primary)]">
              {language === "vi" ? "Hội đồng AI đang hội chẩn..." : "AI Council is deliberating..."}
            </h2>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              {language === "vi"
                ? "Đang phân tích đa chuyên khoa và đánh giá các nguy cơ tương tác."
                : "Analyzing multi-specialty perspectives and safety interactions."}
            </p>

            <div className="mx-auto mt-8 max-w-md space-y-3 text-left">
              {DELIBERATION_STAGES.map((stage, idx) => {
                const isPassed = currentStageIdx > idx + 1;
                const isCurrent = currentStageIdx === idx + 1;

                return (
                  <div
                    key={stage.sequence}
                    className={`flex items-center gap-3 rounded-xl border p-3 transition-colors ${
                      isCurrent
                        ? "border-[color:var(--brand-600)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                        : isPassed
                          ? "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-primary)]"
                          : "border-transparent bg-transparent text-[var(--text-muted)] opacity-60"
                    }`}
                  >
                    <span
                      className={`grid h-6 w-6 place-items-center rounded-full text-xs font-bold ${
                        isCurrent
                          ? "bg-[var(--brand-600)] text-[var(--on-secondary-container)]"
                          : isPassed
                            ? "bg-[var(--success-500)] text-white"
                            : "bg-[var(--surface-muted)] text-[var(--text-muted)]"
                      }`}
                    >
                      {isPassed ? <Icon name="check" size={14} /> : stage.sequence}
                    </span>
                    <span className="text-sm font-semibold">
                      {language === "vi" ? stage.labelVi : stage.labelEn}
                    </span>
                  </div>
                );
              })}
            </div>
          </section>
        ) : (
          /* Step 4: Review Summary Form */
          <form onSubmit={onSubmit} className="space-y-5">
            <section className="rounded-[var(--radius-xl)] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6">
              <div className="flex items-center gap-2">
                <span className="rounded-md border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
                  {language === "vi" ? "Bước 4: Rà soát tổng thể" : "Step 4: Clinical Review"}
                </span>
              </div>
              <h2 className="mt-2 text-xl font-bold text-[var(--text-primary)]">
                {t(language, "council.review.heading")}
              </h2>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">
                {language === "vi"
                  ? "Kiểm tra kỹ lưỡng câu hỏi trọng tâm, bối cảnh lâm sàng và danh sách chuyên khoa trước khi tiến hành hội chẩn."
                  : "Carefully verify clinical question, context, and selected specialties before initiating AI deliberation."}
              </p>

              <div className="mt-5 divide-y divide-[color:var(--shell-border)] rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]">
                {parsedCase.question ? (
                  <div className="p-4">
                    <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      {t(language, "council.question.heading")}
                    </p>
                    <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">
                      {parsedCase.question}
                    </p>
                  </div>
                ) : null}

                <div className="grid gap-4 p-4 sm:grid-cols-2">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      {t(language, "council.intake.symptoms")}
                    </p>
                    <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">
                      {t(language, "council.review.symptoms", { count: parsedCase.symptoms.length })}
                    </p>
                    {parsedCase.symptoms.length > 0 ? (
                      <p className="mt-1 text-xs text-[var(--text-secondary)]">
                        {parsedCase.symptoms.slice(0, 3).join(", ")}
                        {parsedCase.symptoms.length > 3 ? "..." : ""}
                      </p>
                    ) : null}
                  </div>

                  <div>
                    <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      {t(language, "council.intake.labs")}
                    </p>
                    <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">
                      {t(language, "council.review.labs", { count: Object.keys(parsedCase.labs).length })}
                    </p>
                    {Object.keys(parsedCase.labs).length > 0 ? (
                      <p className="mt-1 text-xs font-mono text-[var(--text-secondary)]">
                        {Object.entries(parsedCase.labs)
                          .slice(0, 3)
                          .map(([k, v]) => `${k}=${v}`)
                          .join(", ")}
                      </p>
                    ) : null}
                  </div>

                  <div>
                    <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      {t(language, "council.intake.medicines")}
                    </p>
                    <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">
                      {t(language, "council.review.medicines", { count: parsedCase.medications.length })}
                    </p>
                    {parsedCase.medications.length > 0 ? (
                      <p className="mt-1 text-xs text-[var(--text-secondary)]">
                        {parsedCase.medications.slice(0, 3).join(", ")}
                      </p>
                    ) : null}
                  </div>

                  <div>
                    <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      {t(language, "council.intake.history")}
                    </p>
                    <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">
                      {parsedCase.history
                        ? t(language, "council.review.historyPresent")
                        : t(language, "council.review.historyMissing")}
                    </p>
                  </div>
                </div>

                <div className="p-4">
                  <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                    {language === "vi" ? "Hội đồng chuyên khoa tham gia" : "Participating Specialists"}
                  </p>
                  <p className="mt-1 text-sm font-bold text-[var(--text-brand)]">
                    {specialistNames || t(language, "council.review.noneSelected")}
                  </p>
                </div>
              </div>
            </section>

            {/* Safety Invariants Card */}
            <section className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5">
              <div className="flex items-start gap-3">
                <Icon name="progress" size={20} className="text-[var(--text-brand)]" />
                <div className="text-xs leading-relaxed text-[var(--text-secondary)]">
                  <span className="font-bold text-[var(--text-primary)]">
                    {language === "vi" ? "Lưu ý an toàn lâm sàng: " : "Clinical Safety Notice: "}
                  </span>
                  {language === "vi"
                    ? "Kết quả hội chẩn là phân tích tham vấn hỗ trợ ra quyết định. Bác sĩ lâm sàng chịu trách nhiệm đánh giá và phê duyệt cuối cùng trước khi áp dụng trên bệnh nhân."
                    : "Council results are consultative decision-support outputs. Clinicians retain ultimate decision-making authority."}
                </div>
              </div>
            </section>

            {error ? <p className="text-sm font-semibold text-[var(--status-danger-text)]">{error}</p> : null}

            <div className="flex flex-wrap justify-between gap-3">
              <Link
                href={caseItem ? `/council/new/specialists?caseId=${caseItem.id}` : "/council/new/specialists"}
                className="inline-flex min-h-[44px] items-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-5 text-sm font-semibold text-[var(--text-primary)] hover:bg-[var(--surface-muted)]"
              >
                {t(language, "council.action.backStep", { step: 3 })}
              </Link>

              <button
                type="submit"
                disabled={isSubmitting || !caseItem}
                className="inline-flex min-h-[46px] items-center gap-2 rounded-xl border border-[color:var(--brand-700)] bg-[var(--brand-600)] px-6 text-sm font-bold text-[var(--on-secondary-container)] shadow-sm transition-colors hover:bg-[var(--brand-700)] disabled:opacity-60"
              >
                <Icon name="progress" size={18} />
                {isSubmitting ? t(language, "council.review.running") : t(language, "council.review.run")}
              </button>
            </div>
          </form>
        )}
      </div>
    </PageShell>
  );
}
