"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import AsyncSection, {
  selectAsyncState,
  type AsyncState,
} from "@/components/ui/async-section";
import {
  getPhrEmergencyCard,
  PHR_EMERGENCY_CARD_FIELDS,
  type PhrEmergencyCard,
  type PhrEmergencyCardField,
} from "@/lib/phr";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import type { UILanguage } from "@/lib/ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";

/**
 * Emergency-card field-inclusion editor (personal-health-record Requirement
 * 13.3). Fetches the owner's emergency-card projection and lets the user choose
 * which sections appear, rendering a live preview with the always-present
 * self-declared/decision-support disclaimer (Req 13.5). Empty sections render as
 * empty, never as an error (Req 13.4). Rendered only when the `enhanced`
 * capability is effective (Requirement 18.1).
 */

const FIELD_LABEL_KEYS: Record<PhrEmergencyCardField, UITranslationKey> = {
  allergies: "phr.emergencyCard.field.allergies",
  current_medications: "phr.emergencyCard.field.currentMedications",
  conditions: "phr.emergencyCard.field.conditions",
  blood_type: "phr.emergencyCard.field.bloodType",
  emergency_contact: "phr.emergencyCard.field.emergencyContact",
};

type Inclusion = Record<PhrEmergencyCardField, boolean>;

const ALL_INCLUDED: Inclusion = {
  allergies: true,
  current_medications: true,
  conditions: true,
  blood_type: true,
  emergency_contact: true,
};

export default function EmergencyCardEditor({
  uiLanguage,
}: {
  uiLanguage: UILanguage;
}) {
  const copy = (key: UITranslationKey) => t(uiLanguage, key);
  const loadErrorText = copy("phr.emergencyCard.error");
  const [card, setCard] = useState<PhrEmergencyCard | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [include, setInclude] = useState<Inclusion>(ALL_INCLUDED);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setCard(await getPhrEmergencyCard());
    } catch (err) {
      setError(safeUserFacingError(err, loadErrorText));
    } finally {
      setLoading(false);
    }
  }, [loadErrorText]);

  useEffect(() => {
    load();
  }, [load]);

  const state: AsyncState<PhrEmergencyCard> = selectAsyncState({
    loading,
    error: error || null,
    data: card,
    isEmpty: () => false,
  });

  const disclaimer = useMemo(() => {
    const d = card?.disclaimer;
    return d?.[uiLanguage] ?? d?.vi ?? d?.en ?? "";
  }, [card, uiLanguage]);

  return (
    <section className="rounded-2xl border border-[#B6D4FE] bg-white p-5 shadow-sm dark:border-sky-700/60 dark:bg-slate-900/90">
      <p className="text-sm font-semibold text-[var(--text-primary)]">
        {copy("phr.emergencyCard.title")}
      </p>
      <p className="mt-1 text-[13px] leading-6 text-[var(--text-secondary)]">
        {copy("phr.emergencyCard.description")}
      </p>

      <div className="mt-3 flex flex-wrap gap-2">
        {PHR_EMERGENCY_CARD_FIELDS.map((field) => (
          <label
            key={field}
            className="inline-flex items-center gap-2 rounded-full border border-[#93C5FD] bg-[#EFF6FF] px-3 py-1.5 text-xs font-semibold text-[#1D4ED8] dark:border-sky-500/70 dark:bg-sky-500/18 dark:text-sky-100"
          >
            <input
              type="checkbox"
              checked={include[field]}
              onChange={(e) =>
                setInclude((prev) => ({ ...prev, [field]: e.target.checked }))
              }
            />
            {copy(FIELD_LABEL_KEYS[field])}
          </label>
        ))}
      </div>

      <div className="mt-4">
        <AsyncSection<PhrEmergencyCard>
          state={state}
          loadingLabel={copy("phr.emergencyCard.loading")}
        >
          {(data) => (
            <div className="space-y-3 rounded-2xl border border-[#93C5FD] bg-[#EEF6FF] p-4 dark:border-sky-700/70 dark:bg-slate-800/80">
              <p className="text-xs font-bold uppercase tracking-[0.08em] text-[#374151] dark:text-slate-200">
                {copy("phr.emergencyCard.preview")}
              </p>

              {include.allergies ? (
                <div>
                  <p className="text-xs font-semibold text-[var(--text-secondary)]">
                    {copy(FIELD_LABEL_KEYS.allergies)}
                  </p>
                  {data.allergies && data.allergies.length > 0 ? (
                    <ul className="mt-1 list-disc pl-5 text-[13px] text-[var(--text-primary)]">
                      {data.allergies.map((a, i) => (
                        <li key={i}>
                          {a.name} {a.severity ? `· ${a.severity}` : ""}{" "}
                          {a.reaction ? `· ${a.reaction}` : ""}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-[13px] text-[var(--text-secondary)]">
                      {copy("phr.emergencyCard.none")}
                    </p>
                  )}
                </div>
              ) : null}

              {include.current_medications ? (
                <div>
                  <p className="text-xs font-semibold text-[var(--text-secondary)]">
                    {copy(FIELD_LABEL_KEYS.current_medications)}
                  </p>
                  {data.current_medications &&
                  data.current_medications.length > 0 ? (
                    <ul className="mt-1 list-disc pl-5 text-[13px] text-[var(--text-primary)]">
                      {data.current_medications.map((m, i) => (
                        <li key={i}>
                          {m.name} {m.dose ? `· ${m.dose}` : ""}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-[13px] text-[var(--text-secondary)]">
                      {copy("phr.emergencyCard.none")}
                    </p>
                  )}
                </div>
              ) : null}

              {include.conditions ? (
                <div>
                  <p className="text-xs font-semibold text-[var(--text-secondary)]">
                    {copy(FIELD_LABEL_KEYS.conditions)}
                  </p>
                  {data.conditions && data.conditions.length > 0 ? (
                    <ul className="mt-1 list-disc pl-5 text-[13px] text-[var(--text-primary)]">
                      {data.conditions.map((c, i) => (
                        <li key={i}>
                          {c.name} {c.status ? `· ${c.status}` : ""}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-[13px] text-[var(--text-secondary)]">
                      {copy("phr.emergencyCard.none")}
                    </p>
                  )}
                </div>
              ) : null}

              {include.blood_type ? (
                <p className="text-[13px] text-[var(--text-primary)]">
                  <span className="font-semibold text-[var(--text-secondary)]">
                    {copy(FIELD_LABEL_KEYS.blood_type)}:
                  </span>{" "}
                  {data.blood_type || copy("phr.emergencyCard.none")}
                </p>
              ) : null}

              {include.emergency_contact ? (
                <p className="text-[13px] text-[var(--text-primary)]">
                  <span className="font-semibold text-[var(--text-secondary)]">
                    {copy(FIELD_LABEL_KEYS.emergency_contact)}:
                  </span>{" "}
                  {data.emergency_contact?.name || copy("phr.emergencyCard.none")}
                  {data.emergency_contact?.phone
                    ? ` · ${data.emergency_contact.phone}`
                    : ""}
                </p>
              ) : null}

              {disclaimer ? (
                <p
                  role="note"
                  className="rounded-xl border border-amber-300/70 bg-amber-50 px-3 py-2 text-[12px] leading-5 text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200"
                >
                  {disclaimer}
                </p>
              ) : null}
            </div>
          )}
        </AsyncSection>
      </div>
    </section>
  );
}
