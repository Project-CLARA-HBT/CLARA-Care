"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import CouncilFlowStepper from "@/components/council/council-flow-stepper";
import { Icon } from "@/components/ui/icon";
import PageShell from "@/components/ui/page-shell";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import { safeUserFacingError } from "@/lib/user-facing-text";
import { useUILanguage } from "@/lib/use-ui-language";
import {
  CouncilCaseRecord,
  getActiveCouncilCaseId,
  getCouncilCase,
  setActiveCouncilCaseId,
  updateCouncilCase,
} from "@/lib/council";
import { clamp, SPECIALIST_OPTIONS } from "@/lib/council-wizard";

type SpecialistDraft = {
  specialistCount: number;
  selectedSpecialists: string[];
};

const SPECIALIST_LABEL_KEYS: Record<string, UITranslationKey> = {
  cardiology: "council.specialist.cardiology",
  neurology: "council.specialist.neurology",
  endocrinology: "council.specialist.endocrinology",
  pharmacology: "council.specialist.pharmacology",
  nephrology: "council.specialist.nephrology",
};

const SPECIALIST_RATIONALES: Record<string, { vi: string; en: string }> = {
  cardiology: {
    vi: "Đánh giá huyết động, nguy cơ thiếu máu cơ tim, loạn nhịp và tối ưu thuốc tim mạch.",
    en: "Evaluates hemodynamics, ischemic risks, arrhythmias, and cardiovascular therapies.",
  },
  neurology: {
    vi: "Đánh giá dấu hiệu thần kinh khu trú, nguy cơ tai biến mạch máu não và ý thức.",
    en: "Evaluates focal neurological deficits, stroke risk, and consciousness alterations.",
  },
  endocrinology: {
    vi: "Kiểm soát đường huyết, kháng insulin, rối loạn điện giải và chuyển hóa.",
    en: "Manages glycemic control, insulin resistance, and metabolic disorders.",
  },
  pharmacology: {
    vi: "Rà soát tương tác thuốc (DDI), điều chỉnh liều theo chức năng thận/gan và cảnh báo tác dụng phụ.",
    en: "Reviews drug-drug interactions (DDI), renal dosage adjustments, and adverse reaction alerts.",
  },
  nephrology: {
    vi: "Theo dõi Creatinine, eGFR, độc tính trên thận và cân bằng nội môi.",
    en: "Monitors Creatinine, eGFR, nephrotoxicity risks, and renal clearance safety.",
  },
};

function hydrateFromCase(caseItem: CouncilCaseRecord): SpecialistDraft {
  const request = (caseItem.request ?? {}) as Record<string, unknown>;
  const selected = Array.isArray(request.specialists)
    ? request.specialists
        .map((item) => String(item))
        .filter((id) => SPECIALIST_OPTIONS.some((option) => option.id === id))
    : SPECIALIST_OPTIONS.slice(0, 3).map((item) => item.id);
  const rawCount = Number((request.specialist_count ?? selected.length) || 3);
  const specialistCount = clamp(Number.isFinite(rawCount) ? Math.trunc(rawCount) : 3, 2, SPECIALIST_OPTIONS.length);
  return {
    specialistCount,
    selectedSpecialists: selected.slice(0, specialistCount),
  };
}

export default function CouncilNewSpecialistsPage() {
  const router = useRouter();
  const language = useUILanguage();
  const [queryCaseId, setQueryCaseId] = useState<number | null>(null);
  const [caseItem, setCaseItem] = useState<CouncilCaseRecord | null>(null);
  const [draft, setDraft] = useState<SpecialistDraft>({
    specialistCount: 3,
    selectedSpecialists: SPECIALIST_OPTIONS.slice(0, 3).map((item) => item.id),
  });
  const [showAdvancedRationale, setShowAdvancedRationale] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");

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
        setDraft(hydrateFromCase(loaded));
      } catch (cause) {
        setError(safeUserFacingError(cause, t(language, "council.error.loadCase")));
      }
    };
    if (queryCaseId !== null) {
      void bootstrap();
    }
  }, [language, queryCaseId, router]);

  const onSpecialistCountChange = (value: string) => {
    const parsed = Number(value);
    const nextCount = clamp(Number.isFinite(parsed) ? Math.trunc(parsed) : 2, 2, SPECIALIST_OPTIONS.length);
    setDraft((current) => ({
      specialistCount: nextCount,
      selectedSpecialists: current.selectedSpecialists.slice(0, nextCount),
    }));
  };

  const onToggleSpecialist = (specialistId: string) => {
    setDraft((current) => {
      const exists = current.selectedSpecialists.includes(specialistId);
      if (exists) {
        return {
          ...current,
          selectedSpecialists: current.selectedSpecialists.filter((item) => item !== specialistId),
        };
      }
      if (current.selectedSpecialists.length >= current.specialistCount) {
        return current;
      }
      return {
        ...current,
        selectedSpecialists: [...current.selectedSpecialists, specialistId],
      };
    });
  };

  const onSaveAndNext = async () => {
    if (!caseItem) return;
    if (draft.selectedSpecialists.length < 2) {
      setError(t(language, "council.specialists.minimum"));
      return;
    }
    setIsSaving(true);
    setError("");
    try {
      const request = (caseItem.request ?? {}) as Record<string, unknown>;
      const nextRequest = {
        ...request,
        specialist_count: draft.specialistCount,
        specialists: draft.selectedSpecialists,
      };
      await updateCouncilCase(caseItem.id, {
        status: "specialists_ready",
        request: nextRequest,
      });
      setActiveCouncilCaseId(caseItem.id);
      router.push(`/council/new/review?caseId=${caseItem.id}`);
    } catch (cause) {
      setError(safeUserFacingError(cause, t(language, "council.error.saveSpecialists")));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <PageShell
      title={t(language, "council.specialists.title")}
      description={t(language, "council.specialists.description")}
      variant="plain"
    >
      <div className="mx-auto max-w-4xl space-y-6">
        {/* Step Progress */}
        <CouncilFlowStepper currentStep="context" caseId={caseItem?.id} />

        {/* 2. Selectable Specialist Rows / Chips & System vs Clinician Distinction */}
        <section className="rounded-[1.55rem] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 sm:p-7 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="rounded-md border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
                {language === "vi" ? "Bước 3 / 4 · Hội đồng chuyên khoa" : "Step 3 / 4 · Specialist Selection"}
              </span>
            </div>
            <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1 text-xs font-bold text-[var(--text-secondary)]">
              {draft.selectedSpecialists.length}/{draft.specialistCount} {language === "vi" ? "đã chọn" : "selected"}
            </span>
          </div>

          <h2 className="mt-3 text-2xl font-bold tracking-tight text-[var(--text-primary)]">
            {t(language, "council.specialists.heading")}
          </h2>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            {language === "vi"
              ? "Chọn các chuyên khoa y khoa tham gia thẩm định đa chiều. Hệ thống khuyến nghị tối thiểu 2 góc nhìn chuyên môn độc lập."
              : "Select medical specialties to participate in the multi-perspective council. A minimum of 2 specialties is required."}
          </p>

          {/* System vs Clinician Selection Notice */}
          <div className="mt-4 rounded-xl border border-[color:var(--brand-primary)]/20 bg-[var(--surface-brand-soft)] p-3.5 text-xs text-[var(--text-primary)]">
            <span className="font-bold text-[var(--text-brand)]">
              {language === "vi" ? "Gợi ý tự động của CLARA: " : "System Recommendation: "}
            </span>
            {language === "vi"
              ? "Hệ thống tự động đề xuất dựa trên các triệu chứng và thuốc trong ca bệnh. Bác sĩ có thể tùy chỉnh hoặc thay đổi số lượng chuyên khoa bên dưới."
              : "Pre-selected based on extracted symptoms and medications. Attending clinicians can modify panel composition below."}
          </div>

          <div className="mt-6 flex items-center gap-3">
            <label htmlFor="specialist-count" className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
              {t(language, "council.specialists.count")}:
            </label>
            <input
              id="specialist-count"
              type="number"
              min={2}
              max={SPECIALIST_OPTIONS.length}
              value={draft.specialistCount}
              onChange={(event) => onSpecialistCountChange(event.target.value)}
              className="min-h-[40px] w-20 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-center text-sm font-bold text-[var(--text-primary)] focus:border-[color:var(--brand-600)] focus:outline-none"
            />
          </div>

          {/* Specialist Selection Rows */}
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {SPECIALIST_OPTIONS.map((option) => {
              const checked = draft.selectedSpecialists.includes(option.id);
              const disableUnchecked = !checked && draft.selectedSpecialists.length >= draft.specialistCount;
              const rationale = SPECIALIST_RATIONALES[option.id];

              return (
                <div
                  key={option.id}
                  onClick={() => {
                    if (!disableUnchecked) onToggleSpecialist(option.id);
                  }}
                  className={`rounded-2xl border p-4 transition-all ${
                    checked
                      ? "border-[color:var(--brand-600)] bg-[var(--surface-brand-soft)] shadow-sm"
                      : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] hover:border-[color:var(--shell-border-strong)]"
                  } ${disableUnchecked ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => onToggleSpecialist(option.id)}
                        disabled={disableUnchecked}
                        className="h-4 w-4 rounded text-[var(--brand-600)] focus:ring-[var(--brand-600)]"
                      />
                      <span className="text-sm font-bold text-[var(--text-primary)]">
                        {t(language, SPECIALIST_LABEL_KEYS[option.id] ?? "council.specialist.cardiology")}
                      </span>
                    </div>
                    {checked ? (
                      <span className="rounded bg-[var(--brand-600)] px-2 py-0.5 text-[10px] font-bold text-[var(--on-secondary-container)]">
                        {language === "vi" ? "Đã chọn" : "Selected"}
                      </span>
                    ) : null}
                  </div>

                  {rationale ? (
                    <p className="mt-2 text-xs leading-relaxed text-[var(--text-secondary)] pl-7">
                      {language === "vi" ? rationale.vi : rationale.en}
                    </p>
                  ) : null}
                </div>
              );
            })}
          </div>

          {/* 4. Advanced Rationale Collapsed */}
          <details
            open={showAdvancedRationale}
            onToggle={(e) => setShowAdvancedRationale((e.target as HTMLDetailsElement).open)}
            className="mt-6 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4 text-xs transition-all"
          >
            <summary className="cursor-pointer font-bold text-[var(--text-primary)] flex items-center justify-between">
              <span>{language === "vi" ? "Tiêu chuẩn lựa chọn chuyên khoa & Trọng số phân tích" : "Advanced Panel Composition & Weighting Rationale"}</span>
              <Icon name="arrow-right" size={14} className={`transition transform ${showAdvancedRationale ? "rotate-90" : ""}`} />
            </summary>
            <div className="mt-3 space-y-2 text-[var(--text-secondary)] leading-relaxed pt-2 border-t border-[color:var(--shell-border)]">
              <p>
                {language === "vi"
                  ? "• Mỗi chuyên khoa AI đại diện cho một tác tử chuyên sâu với tri thức y khoa đối chứng độc lập."
                  : "• Each AI specialist operates as an independent agent grounded in peer-reviewed medical domain ontologies."}
              </p>
              <p>
                {language === "vi"
                  ? "• Khuyến nghị Dược lâm sàng và Thận học đặc biệt quan trọng trong các ca bệnh có phối hợp nhiều nhóm thuốc hoặc suy giảm chức năng cơ quan."
                  : "• Pharmacology and Nephrology perspectives are essential when evaluating polypharmacy or compromised renal clearance."}
              </p>
            </div>
          </details>
        </section>

        {error ? <p className="text-sm font-semibold text-[var(--status-danger-text)]">{error}</p> : null}

        {/* 5. Navigation Actions */}
        <div className="flex flex-wrap justify-between gap-3 pt-2">
          <Link
            href={caseItem ? `/council/new/intake?caseId=${caseItem.id}` : "/council/new/intake"}
            className="inline-flex min-h-[44px] items-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-5 text-sm font-semibold text-[var(--text-primary)] hover:bg-[var(--surface-muted)]"
          >
            {t(language, "council.action.backStep", { step: 2 })}
          </Link>

          <button
            type="button"
            onClick={() => void onSaveAndNext()}
            disabled={isSaving || !caseItem || draft.selectedSpecialists.length < 2}
            className="inline-flex min-h-[44px] items-center gap-2 rounded-xl border border-[color:var(--brand-700)] bg-[var(--brand-600)] px-6 text-sm font-bold text-[var(--on-secondary-container)] shadow-sm transition hover:bg-[var(--brand-700)] disabled:opacity-60"
          >
            <span>{isSaving ? t(language, "council.action.saving") : t(language, "council.action.nextStep", { step: 4 })}</span>
            <Icon name="arrow-right" size={16} />
          </button>
        </div>
      </div>
    </PageShell>
  );
}
