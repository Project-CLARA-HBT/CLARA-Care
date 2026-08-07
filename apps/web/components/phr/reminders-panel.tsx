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
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import type { UILanguage } from "@/lib/ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";

/**
 * Reminders panel (personal-health-record Requirement 14.1–14.5). Configures
 * medication reminders for current medications that have a defined frequency
 * (the backend rejects others with 422), tracks remaining supply / refill
 * threshold, and toggles the caregiver missed-dose nudge. Lists configured
 * reminders with the server's medication-due / refill-due decisions. Rendered
 * only when the `reminders` capability is effective (Requirement 18.1).
 */

export default function RemindersPanel({
  uiLanguage,
  medications,
}: {
  uiLanguage: UILanguage;
  medications: PhrMedicationItem[];
}) {
  const copy = (key: UITranslationKey) => t(uiLanguage, key);
  const listErrorText = copy("phr.reminders.listError");
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
      setListError(safeUserFacingError(err, listErrorText));
    } finally {
      setLoading(false);
    }
  }, [listErrorText]);

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
      setAddError(safeUserFacingError(err, copy("phr.reminders.addError")));
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
    <section className="rounded-[14px] border border-[color:var(--shell-border)] border-t-[#2A3950] bg-[var(--surface-panel)] p-6">
      <p className="text-sm font-semibold text-[var(--text-primary)]">
        {copy("phr.reminders.title")}
      </p>
      <p className="mt-1 text-[13px] leading-6 text-[var(--text-secondary)]">
        {copy("phr.reminders.description")}
      </p>

      {eligible.length === 0 ? (
        <p className="mt-3 text-[13px] text-[var(--text-secondary)]">
          {copy("phr.reminders.noEligible")}
        </p>
      ) : (
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1.5 sm:col-span-2">
            <span className="text-xs font-bold uppercase tracking-[0.08em] text-[var(--text-secondary)]">
              {copy("phr.reminders.medication")}
            </span>
            <select
              className="input"
              value={medId}
              onChange={(e) => setMedId(e.target.value)}
            >
              <option value="">{copy("phr.reminders.chooseMed")}</option>
              {eligible.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} · {m.frequency}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-bold uppercase tracking-[0.08em] text-[var(--text-secondary)]">
              {copy("phr.reminders.remaining")}
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
            <span className="text-xs font-bold uppercase tracking-[0.08em] text-[var(--text-secondary)]">
              {copy("phr.reminders.threshold")}
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
          <label className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--text-secondary)] sm:col-span-2">
            <input
              type="checkbox"
              checked={nudge}
              onChange={(e) => setNudge(e.target.checked)}
            />
            {copy("phr.reminders.caregiver")}
          </label>
          <div className="sm:col-span-2">
            <button
              type="button"
              onClick={onAdd}
              disabled={adding || !medId}
              className="inline-flex min-h-[38px] items-center rounded-lg bg-[#60a5fa] px-4 text-sm font-semibold text-[#003a6b] transition hover:bg-[#a4c9ff] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {adding ? copy("phr.reminders.adding") : copy("phr.reminders.add")}
            </button>
          </div>
        </div>
      )}

      {addError ? <p className="mt-3 text-sm text-[#ffb4ab]">{addError}</p> : null}

      <div className="mt-4">
        <p className="text-xs font-bold uppercase tracking-[0.08em] text-[var(--text-secondary)]">
          {copy("phr.reminders.configured")}
        </p>
        <div className="mt-2">
          <AsyncSection<PhrReminder[]>
            state={state}
            loadingLabel={copy("phr.reminders.loading")}
            emptyTitle={copy("phr.reminders.empty")}
            emptyDescription=""
          >
            {(data) => (
              <ul className="space-y-2">
                {data.map((r) => (
                  <li
                    key={r.id}
                    className="flex flex-wrap items-center gap-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--bg-elev-3)] p-3"
                  >
                    <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                      {medName(r.medication_entry_id)}
                    </span>
                    {r.medication_due ? (
                      <span className="inline-flex items-center rounded-full border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-2 py-0.5 text-[10px] font-semibold text-[var(--status-ok-text)]">
                        {copy("phr.reminders.due")}
                      </span>
                    ) : null}
                    {r.refill_due ? (
                      <span className="inline-flex items-center rounded-full border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-2 py-0.5 text-[10px] font-semibold text-[var(--status-warn-text)]">
                        {copy("phr.reminders.refill")}
                      </span>
                    ) : null}
                    {r.caregiver_nudge_enabled ? (
                      <span className="inline-flex items-center rounded-full border border-[color:var(--status-neutral-border)] bg-[var(--status-neutral-bg)] px-2 py-0.5 text-[10px] font-semibold text-[var(--status-neutral-text)]">
                        {copy("phr.reminders.nudgeOn")}
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
