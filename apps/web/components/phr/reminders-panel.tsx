"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import AsyncSection, {
  selectAsyncState,
  type AsyncState,
} from "@/components/ui/async-section";
import {
  createPhrReminder,
  listPhrReminders,
  type PhrMedicationItem,
  type PhrReminder,
} from "@/lib/phr";
import type { UILanguage } from "@/lib/ui-language";

/**
 * Reminders panel (personal-health-record Requirement 14.1–14.5). Configures
 * medication reminders for current medications that have a defined frequency
 * (the backend rejects others with 422), tracks remaining supply / refill
 * threshold, and toggles the caregiver missed-dose nudge. Lists configured
 * reminders with the server's medication-due / refill-due decisions. Rendered
 * only when the `reminders` capability is effective (Requirement 18.1).
 */

const COPY = {
  vi: {
    title: "Nhắc uống thuốc",
    description:
      "Đặt nhắc cho thuốc đang dùng có tần suất, theo dõi lượng còn lại và nhắc người chăm sóc.",
    medication: "Thuốc",
    chooseMed: "Chọn thuốc",
    noEligible:
      "Chưa có thuốc đang dùng kèm tần suất. Hãy thêm tần suất cho thuốc trước.",
    frequency: "Tần suất",
    remaining: "Lượng còn lại",
    threshold: "Ngưỡng nạp thêm",
    caregiver: "Nhắc người chăm sóc khi quên liều",
    add: "Tạo nhắc",
    adding: "Đang tạo...",
    addError: "Tạo nhắc thất bại.",
    loading: "Đang tải danh sách nhắc...",
    listError: "Chưa thể tải danh sách nhắc.",
    empty: "Chưa có nhắc nào.",
    configured: "Nhắc đã đặt",
    due: "Đến giờ uống",
    refill: "Cần nạp thêm",
    nudgeOn: "Nhắc người chăm sóc: bật",
  },
  en: {
    title: "Medication reminders",
    description:
      "Set reminders for current medications with a frequency, track remaining supply, and nudge a caregiver.",
    medication: "Medication",
    chooseMed: "Choose medication",
    noEligible:
      "No current medication with a frequency yet. Add a frequency to a medication first.",
    frequency: "Frequency",
    remaining: "Remaining supply",
    threshold: "Refill threshold",
    caregiver: "Nudge caregiver on missed dose",
    add: "Create reminder",
    adding: "Creating...",
    addError: "Failed to create reminder.",
    loading: "Loading reminders...",
    listError: "Unable to load reminders.",
    empty: "No reminders configured yet.",
    configured: "Configured reminders",
    due: "Dose due",
    refill: "Refill due",
    nudgeOn: "Caregiver nudge: on",
  },
} as const;

export default function RemindersPanel({
  uiLanguage,
  medications,
}: {
  uiLanguage: UILanguage;
  medications: PhrMedicationItem[];
}) {
  const text = COPY[uiLanguage];
  const eligible = useMemo(
    () =>
      medications.filter(
        (m) =>
          m.is_current &&
          String(m.frequency || "").trim().length > 0 &&
          String(m.id || "").trim().length > 0,
      ),
    [medications],
  );

  const [medId, setMedId] = useState("");
  const [remaining, setRemaining] = useState("");
  const [threshold, setThreshold] = useState("");
  const [nudge, setNudge] = useState(false);
  const [reminders, setReminders] = useState<PhrReminder[]>([]);
  const [loading, setLoading] = useState(false);
  const [listError, setListError] = useState("");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setListError("");
    try {
      setReminders(await listPhrReminders());
    } catch (err) {
      setListError(err instanceof Error ? err.message : text.listError);
    } finally {
      setLoading(false);
    }
  }, [text.listError]);

  useEffect(() => {
    load();
  }, [load]);

  const selectedMed = eligible.find((m) => m.id === medId);

  const onAdd = async () => {
    if (!selectedMed) return;
    setAdding(true);
    setAddError("");
    try {
      const parsedRemaining = remaining.trim() ? Number(remaining) : null;
      const parsedThreshold = threshold.trim() ? Number(threshold) : null;
      await createPhrReminder({
        medication_entry_id: selectedMed.id,
        schedule: { frequency: selectedMed.frequency },
        remaining_supply: Number.isFinite(parsedRemaining as number)
          ? parsedRemaining
          : null,
        refill_threshold: Number.isFinite(parsedThreshold as number)
          ? parsedThreshold
          : null,
        caregiver_nudge_enabled: nudge,
      });
      setMedId("");
      setRemaining("");
      setThreshold("");
      setNudge(false);
      await load();
    } catch (err) {
      setAddError(err instanceof Error ? err.message : text.addError);
    } finally {
      setAdding(false);
    }
  };

  const medName = (entryId: string) =>
    medications.find((m) => m.id === entryId)?.name || entryId;

  const state: AsyncState<PhrReminder[]> = selectAsyncState({
    loading,
    error: listError || null,
    data: reminders,
  });

  return (
    <section className="rounded-2xl border border-[#B6D4FE] bg-white p-5 shadow-sm dark:border-sky-700/60 dark:bg-slate-900/90">
      <p className="text-sm font-semibold text-[var(--text-primary)]">
        {text.title}
      </p>
      <p className="mt-1 text-[13px] leading-6 text-[var(--text-secondary)]">
        {text.description}
      </p>

      {eligible.length === 0 ? (
        <p className="mt-3 text-[13px] text-[var(--text-secondary)]">
          {text.noEligible}
        </p>
      ) : (
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1.5 sm:col-span-2">
            <span className="text-xs font-bold uppercase tracking-[0.08em] text-[#374151] dark:text-slate-200">
              {text.medication}
            </span>
            <select
              className="input"
              value={medId}
              onChange={(e) => setMedId(e.target.value)}
            >
              <option value="">{text.chooseMed}</option>
              {eligible.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} · {m.frequency}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-bold uppercase tracking-[0.08em] text-[#374151] dark:text-slate-200">
              {text.remaining}
            </span>
            <input
              inputMode="decimal"
              className="input"
              value={remaining}
              onChange={(e) =>
                setRemaining(e.target.value.replace(/[^0-9.]/g, ""))
              }
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-bold uppercase tracking-[0.08em] text-[#374151] dark:text-slate-200">
              {text.threshold}
            </span>
            <input
              inputMode="decimal"
              className="input"
              value={threshold}
              onChange={(e) =>
                setThreshold(e.target.value.replace(/[^0-9.]/g, ""))
              }
            />
          </label>
          <label className="inline-flex items-center gap-2 text-sm font-semibold text-[#374151] dark:text-slate-200 sm:col-span-2">
            <input
              type="checkbox"
              checked={nudge}
              onChange={(e) => setNudge(e.target.checked)}
            />
            {text.caregiver}
          </label>
          <div className="sm:col-span-2">
            <button
              type="button"
              onClick={onAdd}
              disabled={adding || !medId}
              className="inline-flex min-h-[38px] items-center rounded-lg border border-[#93C5FD] bg-[#EFF6FF] px-4 text-sm font-semibold text-[#1D4ED8] transition hover:bg-[#DBEAFE] disabled:cursor-not-allowed disabled:opacity-60 dark:border-sky-500/70 dark:bg-sky-500/18 dark:text-sky-100"
            >
              {adding ? text.adding : text.add}
            </button>
          </div>
        </div>
      )}

      {addError ? <p className="mt-3 text-sm text-rose-500">{addError}</p> : null}

      <div className="mt-4">
        <p className="text-xs font-bold uppercase tracking-[0.08em] text-[#374151] dark:text-slate-200">
          {text.configured}
        </p>
        <div className="mt-2">
          <AsyncSection<PhrReminder[]>
            state={state}
            loadingLabel={text.loading}
            emptyTitle={text.empty}
            emptyDescription=""
          >
            {(data) => (
              <ul className="space-y-2">
                {data.map((r) => (
                  <li
                    key={r.id}
                    className="flex flex-wrap items-center gap-2 rounded-2xl border border-[#93C5FD] bg-[#EEF6FF] p-3 dark:border-sky-700/70 dark:bg-slate-800/80"
                  >
                    <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                      {medName(r.medication_entry_id)}
                    </span>
                    {r.medication_due ? (
                      <span className="inline-flex items-center rounded-full border border-sky-300 bg-sky-50 px-2 py-0.5 text-[10px] font-semibold text-sky-700 dark:border-sky-500/60 dark:bg-sky-500/15 dark:text-sky-100">
                        {text.due}
                      </span>
                    ) : null}
                    {r.refill_due ? (
                      <span className="inline-flex items-center rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-800 dark:border-amber-500/50 dark:bg-amber-500/10 dark:text-amber-200">
                        {text.refill}
                      </span>
                    ) : null}
                    {r.caregiver_nudge_enabled ? (
                      <span className="inline-flex items-center rounded-full border border-slate-300 bg-slate-50 px-2 py-0.5 text-[10px] font-semibold text-slate-600 dark:border-slate-600/70 dark:bg-slate-700/40 dark:text-slate-200">
                        {text.nudgeOn}
                      </span>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </AsyncSection>
        </div>
      </div>
    </section>
  );
}
