"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import CouncilWorkspaceNav from "@/components/council/council-workspace-nav";
import PageShell from "@/components/ui/page-shell";
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
        setError(cause instanceof Error ? cause.message : "Không thể tải case.");
      }
    };
    if (queryCaseId !== null) {
      void bootstrap();
    }
  }, [queryCaseId, router]);

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
      setError("Vui lòng chọn tối thiểu 2 chuyên khoa.");
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
      setError(cause instanceof Error ? cause.message : "Không thể lưu specialist.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <PageShell
      title="Council Wizard - Specialists"
      description="Bước 2/3: chọn chuyên khoa cho case thật."
      variant="plain"
    >
      <div className="space-y-5">
        <CouncilWorkspaceNav />

        <section className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
            Step 2/3 · Case #{caseItem?.id ?? "--"}
          </p>
          <h2 className="mt-2 text-xl font-semibold text-[var(--text-primary)]">Chọn chuyên khoa</h2>

          <label className="mt-4 block max-w-xs space-y-1">
            <span className="text-sm font-medium">Số chuyên khoa (2-5)</span>
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
                      ? "border-sky-400 bg-sky-100 text-sky-900"
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
                  {option.label}
                </label>
              );
            })}
          </div>

          <p className="mt-3 text-xs text-[var(--text-muted)]">
            Đã chọn {draft.selectedSpecialists.length}/{draft.specialistCount} chuyên khoa.
          </p>
        </section>

        {error ? <p className="text-sm text-red-400">{error}</p> : null}

        <div className="flex flex-wrap justify-between gap-2">
          <Link
            href={caseItem ? `/council/new/intake?caseId=${caseItem.id}` : "/council/new/intake"}
            className="inline-flex min-h-[42px] items-center rounded-lg border border-[color:var(--shell-border)] px-4 text-sm font-semibold"
          >
            Quay lại bước 1
          </Link>
          <button
            type="button"
            onClick={() => void onSaveAndNext()}
            disabled={isSaving || !caseItem}
            className="inline-flex min-h-[44px] items-center rounded-lg border border-cyan-300/65 bg-gradient-to-r from-sky-600 to-cyan-500 px-4 text-sm font-semibold text-white disabled:opacity-60"
          >
            {isSaving ? "Đang lưu..." : "Sang bước 3"}
          </button>
        </div>
      </div>
    </PageShell>
  );
}
