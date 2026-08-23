"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import CouncilFlowStepper from "@/components/council/council-flow-stepper";
import CouncilWorkspaceNav from "@/components/council/council-workspace-nav";
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
      <div className="space-y-5">
        <CouncilWorkspaceNav />
        <CouncilFlowStepper currentStep="context" caseId={caseItem?.id} />

        <section className="rounded-[14px] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6">
          <div className="flex items-center gap-2">
            <span className="rounded-md border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
              {language === "vi" ? "Bước 3: Hội đồng chuyên khoa" : "Step 3: Specialist Panel"}
            </span>
          </div>
          <h2 className="mt-2 text-xl font-bold text-[var(--text-primary)]">
            {t(language, "council.specialists.heading")}
          </h2>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            {language === "vi"
              ? "Chọn các chuyên khoa tham gia hội chẩn đa chiều để đánh giá ca bệnh."
              : "Select medical specialties to participate in the multi-specialty council."}
          </p>

          <label className="mt-5 block max-w-xs space-y-1">
            <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
              {t(language, "council.specialists.count")}
            </span>
            <input
              type="number"
              min={2}
              max={SPECIALIST_OPTIONS.length}
              value={draft.specialistCount}
              onChange={(event) => onSpecialistCountChange(event.target.value)}
              className="min-h-[44px] w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-sm text-[var(--text-primary)] focus:border-[color:var(--brand-600)] focus:outline-none"
            />
          </label>

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {SPECIALIST_OPTIONS.map((option) => {
              const checked = draft.selectedSpecialists.includes(option.id);
              const disableUnchecked = !checked && draft.selectedSpecialists.length >= draft.specialistCount;
              return (
                <label
                  key={option.id}
                  className={`flex min-h-[48px] items-center gap-3 rounded-xl border px-4 py-3 text-sm font-semibold transition-colors ${
                    checked
                      ? "border-[color:var(--brand-600)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)] shadow-sm"
                      : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-primary)] hover:border-[color:var(--shell-border-strong)]"
                  } ${disableUnchecked ? "opacity-60" : "cursor-pointer"}`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => onToggleSpecialist(option.id)}
                    disabled={disableUnchecked}
                    className="h-4 w-4 rounded text-[var(--brand-600)] focus:ring-[var(--brand-600)]"
                  />
                  <span>{t(language, SPECIALIST_LABEL_KEYS[option.id] ?? "council.specialist.cardiology")}</span>
                </label>
              );
            })}
          </div>

          <p className="mt-4 text-xs font-medium text-[var(--text-secondary)]">
            {t(language, "council.specialists.selected", {
              selected: draft.selectedSpecialists.length,
              total: draft.specialistCount,
            })}
          </p>
        </section>

        {error ? <p className="text-sm font-semibold text-[var(--status-danger-text)]">{error}</p> : null}

        <div className="flex flex-wrap justify-between gap-3">
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
            className="inline-flex min-h-[44px] items-center gap-2 rounded-xl border border-[color:var(--brand-700)] bg-[var(--brand-600)] px-6 text-sm font-bold text-[var(--on-secondary-container)] shadow-sm transition-colors hover:bg-[var(--brand-700)] disabled:opacity-60"
          >
            <Icon name="arrow-right" size={16} />
            {isSaving ? t(language, "council.action.saving") : t(language, "council.action.nextStep", { step: 4 })}
          </button>
        </div>
      </div>
    </PageShell>
  );
}
