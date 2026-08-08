"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import CouncilWorkspaceNav from "@/components/council/council-workspace-nav";
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

        <section className="rounded-[14px] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
            {t(language, "council.step", { step: 2, id: caseItem?.id ?? "--" })}
          </p>
          <h2 className="mt-2 text-xl font-semibold text-[var(--text-primary)]">{t(language, "council.specialists.heading")}</h2>

          <label className="mt-4 block max-w-xs space-y-1">
            <span className="text-sm font-medium">{t(language, "council.specialists.count")}</span>
            <input
              type="number"
              min={2}
              max={SPECIALIST_OPTIONS.length}
              value={draft.specialistCount}
              onChange={(event) => onSpecialistCountChange(event.target.value)}
              className="min-h-[44px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-sm"
            />
          </label>

          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {SPECIALIST_OPTIONS.map((option) => {
              const checked = draft.selectedSpecialists.includes(option.id);
              const disableUnchecked = !checked && draft.selectedSpecialists.length >= draft.specialistCount;
              return (
                <label
                  key={option.id}
                  className={`flex min-h-[44px] items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
                    checked
                      ? "border-[color:var(--brand-primary)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                      : "border-[color:var(--shell-border)] bg-[var(--surface-muted)]"
                  } ${disableUnchecked ? "opacity-60" : "cursor-pointer"}`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => onToggleSpecialist(option.id)}
                    disabled={disableUnchecked}
                    className="h-4 w-4"
                  />
                  {t(language, SPECIALIST_LABEL_KEYS[option.id] ?? "council.specialist.cardiology")}
                </label>
              );
            })}
          </div>

          <p className="mt-3 text-xs text-[var(--text-muted)]">
            {t(language, "council.specialists.selected", {
              selected: draft.selectedSpecialists.length,
              total: draft.specialistCount,
            })}
          </p>
        </section>

        {error ? <p className="text-sm text-[var(--status-danger-text)]">{error}</p> : null}

        <div className="flex flex-wrap justify-between gap-2">
          <Link
            href={caseItem ? `/council/new/intake?caseId=${caseItem.id}` : "/council/new/intake"}
            className="inline-flex min-h-[42px] items-center rounded-lg border border-[color:var(--shell-border)] px-4 text-sm font-semibold"
          >
            {t(language, "council.action.backStep", { step: 1 })}
          </Link>
          <button
            type="button"
            onClick={() => void onSaveAndNext()}
            disabled={isSaving || !caseItem}
            className="inline-flex min-h-[44px] items-center rounded-lg border border-[color:var(--brand-600)] bg-[var(--brand-600)] px-4 text-sm font-semibold text-[var(--on-secondary-container)] transition-colors hover:bg-[var(--brand-700)] disabled:opacity-60"
          >
            {isSaving ? t(language, "council.action.saving") : t(language, "council.action.nextStep", { step: 3 })}
          </button>
        </div>
      </div>
    </PageShell>
  );
}
