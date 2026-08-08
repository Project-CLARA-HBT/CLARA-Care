"use client";

import { useEffect, useState } from "react";
import { SurfaceCard } from "@/components/ui/surface";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import { getPublicPhrShare } from "@/lib/phr";
import { useUILanguage } from "@/lib/use-ui-language";

type SharedPhrClientProps = { token: string };
type JsonRecord = Record<string, unknown>;
type SharedSection = { title: string; lines: string[] };
type SharedView = { title: string; sections: SharedSection[] };

const SHARED_KEYS = {
  eyebrow: "phr.shared.eyebrow",
  fullTitle: "phr.shared.fullTitle",
  emergencyTitle: "phr.shared.emergencyTitle",
  loading: "phr.shared.loading",
  unavailable: "phr.shared.unavailable",
  readOnly: "phr.shared.readOnly",
  empty: "phr.shared.empty",
  profile: "phr.shared.profile",
  allergies: "phr.shared.allergies",
  conditions: "phr.shared.conditions",
  medications: "phr.shared.medications",
  emergencyContact: "phr.shared.emergencyContact",
  safety: "phr.shared.safety",
  fullName: "phr.field.fullName",
  dob: "phr.field.dob",
  gender: "phr.field.gender",
  bloodType: "phr.field.bloodType",
  phone: "phr.field.emergencyPhone",
  valueMild: "phr.shared.value.mild",
  valueModerate: "phr.shared.value.moderate",
  valueSevere: "phr.shared.value.severe",
  valueUnknown: "phr.shared.value.unknown",
  valueActive: "phr.shared.value.active",
  valueResolved: "phr.shared.value.resolved",
  valueMonitoring: "phr.shared.value.monitoring",
  valueMale: "phr.shared.value.male",
  valueFemale: "phr.shared.value.female",
  valueOther: "phr.shared.value.other",
} as const satisfies Record<string, UITranslationKey>;

const CONTROLLED_VALUE_KEYS: Record<string, UITranslationKey> = {
  mild: SHARED_KEYS.valueMild,
  moderate: SHARED_KEYS.valueModerate,
  severe: SHARED_KEYS.valueSevere,
  high: SHARED_KEYS.valueSevere,
  unknown: SHARED_KEYS.valueUnknown,
  active: SHARED_KEYS.valueActive,
  resolved: SHARED_KEYS.valueResolved,
  monitoring: SHARED_KEYS.valueMonitoring,
  male: SHARED_KEYS.valueMale,
  female: SHARED_KEYS.valueFemale,
  nam: SHARED_KEYS.valueMale,
  nữ: SHARED_KEYS.valueFemale,
  other: SHARED_KEYS.valueOther,
};

function asRecord(value: unknown): JsonRecord {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as JsonRecord)
    : {};
}

function text(value: unknown): string {
  return typeof value === "string" || typeof value === "number"
    ? String(value).trim()
    : "";
}

function controlledText(
  value: unknown,
  copy: (key: UITranslationKey) => string,
): string {
  const raw = text(value);
  const key = CONTROLLED_VALUE_KEYS[raw.toLowerCase()];
  return key ? copy(key) : raw;
}

function recordList(value: unknown): JsonRecord[] {
  return Array.isArray(value)
    ? value.map(asRecord).filter((item) => Object.keys(item).length > 0)
    : [];
}

function labeled(label: string, value: unknown): string | null {
  const resolved = text(value);
  return resolved ? `${label}: ${resolved}` : null;
}

function joinKnown(...values: Array<string | null>): string | null {
  const result = values.filter((value): value is string => Boolean(value));
  return result.length ? result.join(" • ") : null;
}

function listLines(
  raw: unknown,
  fields: Array<{ key: string; controlled?: boolean }>,
  copy: (key: UITranslationKey) => string,
): string[] {
  return recordList(raw)
    .map((item) => {
      const primary = text(item.name) || text(item.substance);
      if (!primary) return null;
      const extras = fields
        .map(({ key, controlled }) => {
          const value = controlled
            ? controlledText(item[key], copy)
            : text(item[key]);
          return value || null;
        })
        .filter((value): value is string => Boolean(value));
      return extras.length ? `${primary} (${extras.join(" • ")})` : primary;
    })
    .filter((value): value is string => Boolean(value));
}

function section(
  title: string,
  lines: Array<string | null>,
): SharedSection | null {
  const safeLines = lines.filter((line): line is string => Boolean(line));
  return safeLines.length ? { title, lines: safeLines } : null;
}

function sharedView(
  payload: unknown,
  copy: (key: UITranslationKey) => string,
): SharedView {
  const envelope = asRecord(payload);
  const emergency = asRecord(envelope.emergency_card);
  const isEmergency =
    text(envelope.scope) === "emergency_card" ||
    Object.keys(emergency).length > 0;

  if (isEmergency) {
    const contact = asRecord(emergency.emergency_contact);
    const sections = [
      section(
        copy(SHARED_KEYS.allergies),
        listLines(
          emergency.allergies,
          [{ key: "severity", controlled: true }, { key: "reaction" }],
          copy,
        ),
      ),
      section(
        copy(SHARED_KEYS.medications),
        listLines(emergency.current_medications, [{ key: "dose" }], copy),
      ),
      section(
        copy(SHARED_KEYS.conditions),
        listLines(
          emergency.conditions,
          [{ key: "status", controlled: true }],
          copy,
        ),
      ),
      section(copy(SHARED_KEYS.profile), [
        labeled(copy(SHARED_KEYS.bloodType), emergency.blood_type),
      ]),
      section(copy(SHARED_KEYS.emergencyContact), [
        joinKnown(
          text(contact.name),
          labeled(copy(SHARED_KEYS.phone), contact.phone),
        ),
      ]),
    ].filter((value): value is SharedSection => Boolean(value));
    return { title: copy(SHARED_KEYS.emergencyTitle), sections };
  }

  const record = asRecord(envelope.record);
  const profile = asRecord(record.profile);
  const sections = [
    section(copy(SHARED_KEYS.profile), [
      labeled(copy(SHARED_KEYS.fullName), profile.full_name),
      labeled(copy(SHARED_KEYS.dob), profile.date_of_birth),
      labeled(copy(SHARED_KEYS.gender), controlledText(profile.gender, copy)),
      labeled(copy(SHARED_KEYS.bloodType), profile.blood_type),
    ]),
    section(
      copy(SHARED_KEYS.allergies),
      listLines(
        record.allergies,
        [{ key: "severity", controlled: true }, { key: "reaction" }],
        copy,
      ),
    ),
    section(
      copy(SHARED_KEYS.conditions),
      listLines(record.conditions, [{ key: "status", controlled: true }], copy),
    ),
    section(
      copy(SHARED_KEYS.medications),
      listLines(
        record.medications,
        [{ key: "dose" }, { key: "frequency" }],
        copy,
      ),
    ),
  ].filter((value): value is SharedSection => Boolean(value));
  return { title: copy(SHARED_KEYS.fullTitle), sections };
}

export default function SharedPhrClient({ token }: SharedPhrClientProps) {
  const language = useUILanguage();
  const copy = (key: UITranslationKey) => t(language, key);
  const [payload, setPayload] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setUnavailable(false);
    void getPublicPhrShare(token)
      .then((next) => {
        if (active) setPayload(next);
      })
      .catch(() => {
        if (active) setUnavailable(true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token]);

  const view = sharedView(payload, copy);

  return (
    <main className="mx-auto min-h-dvh max-w-3xl px-4 py-8 sm:px-6 sm:py-12">
      <SurfaceCard className="p-5 sm:p-7">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
          {copy(SHARED_KEYS.eyebrow)}
        </p>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-2xl font-semibold text-[var(--text-primary)]">
            {view.title}
          </h1>
          <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1 text-xs font-semibold text-[var(--text-secondary)]">
            {copy(SHARED_KEYS.readOnly)}
          </span>
        </div>
        <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
          {copy(SHARED_KEYS.safety)}
        </p>
      </SurfaceCard>

      {loading ? (
        <SurfaceCard className="mt-4 p-5 text-sm text-[var(--text-secondary)]">
          {copy(SHARED_KEYS.loading)}
        </SurfaceCard>
      ) : null}

      {unavailable ? (
        <SurfaceCard className="mt-4 border-[color:var(--status-danger-border)] p-5 text-sm text-[var(--status-danger-text)]">
          {copy(SHARED_KEYS.unavailable)}
        </SurfaceCard>
      ) : null}

      {!loading && !unavailable ? (
        view.sections.length ? (
          <div className="mt-4 space-y-4">
            {view.sections.map((item) => (
              <SurfaceCard key={item.title} className="p-5">
                <h2 className="font-semibold text-[var(--text-primary)]">
                  {item.title}
                </h2>
                <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--text-secondary)]">
                  {item.lines.map((line, index) => (
                    <li key={`${item.title}-${index}`}>{line}</li>
                  ))}
                </ul>
              </SurfaceCard>
            ))}
          </div>
        ) : (
          <SurfaceCard className="mt-4 p-5 text-sm text-[var(--text-secondary)]">
            {copy(SHARED_KEYS.empty)}
          </SurfaceCard>
        )
      ) : null}
    </main>
  );
}
