"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import CouncilWorkspaceNav from "@/components/council/council-workspace-nav";
import PageShell from "@/components/ui/page-shell";
import { t } from "@/lib/i18n/catalog";
import { safeUserFacingError } from "@/lib/user-facing-text";
import { useUILanguage } from "@/lib/use-ui-language";
import {
  CouncilCaseRecord,
  createCouncilCase,
  getActiveCouncilCaseId,
  getCouncilCase,
  runCouncilCaseIntake,
  setActiveCouncilCaseId,
  updateCouncilCase,
} from "@/lib/council";

type IntakeMode = "transcript" | "audio";

type IntakeDraft = {
  symptomsInput: string;
  labsInput: string;
  medicationsInput: string;
  historyInput: string;
};

function listToText(value: unknown): string {
  if (!Array.isArray(value)) return "";
  return value.map((item) => String(item ?? "").trim()).filter(Boolean).join("\n");
}

function labsToText(value: unknown): string {
  if (!value || typeof value !== "object" || Array.isArray(value)) return "";
  return Object.entries(value as Record<string, unknown>)
    .map(([key, item]) => {
      const name = key.trim();
      const text = String(item ?? "").trim();
      if (!name || !text) return "";
      return `${name}=${text}`;
    })
    .filter(Boolean)
    .join("\n");
}

function historyToText(value: unknown): string {
  if (typeof value === "string") return value.trim();
  if (Array.isArray(value)) return listToText(value);
  if (value && typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, item]) => `${key}: ${String(item ?? "").trim()}`)
      .join("\n");
  }
  return "";
}

function hydrateDraftFromCase(caseItem: CouncilCaseRecord): IntakeDraft {
  const payload = (caseItem.request ?? {}) as Record<string, unknown>;
  return {
    symptomsInput: listToText(payload.symptoms),
    labsInput: labsToText(payload.labs),
    medicationsInput: listToText(payload.medications),
    historyInput: historyToText(payload.history),
  };
}

export default function CouncilNewIntakePage() {
  const router = useRouter();
  const language = useUILanguage();
  const [queryCaseId, setQueryCaseId] = useState<number | null>(null);
  const [caseItem, setCaseItem] = useState<CouncilCaseRecord | null>(null);
  const [draft, setDraft] = useState<IntakeDraft>({
    symptomsInput: "",
    labsInput: "",
    medicationsInput: "",
    historyInput: "",
  });
  const [intakeMode, setIntakeMode] = useState<IntakeMode>("transcript");
  const [transcriptInput, setTranscriptInput] = useState("");
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [isExtracting, setIsExtracting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [extractNotice, setExtractNotice] = useState("");
  const [extractWarnings, setExtractWarnings] = useState<string[]>([]);
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
        let resolvedCase: CouncilCaseRecord | null = null;
        if (queryCaseId) {
          resolvedCase = await getCouncilCase(queryCaseId);
        } else {
          resolvedCase = await createCouncilCase({
            title: t(language, "council.new.caseFallback", {
              id: new Intl.DateTimeFormat(language === "vi" ? "vi-VN" : "en-US", {
                dateStyle: "short",
                timeStyle: "short",
              }).format(new Date()),
            }),
          });
          router.replace(`/council/new/intake?caseId=${resolvedCase.id}`);
        }

        if (!resolvedCase) return;
        setActiveCouncilCaseId(resolvedCase.id);
        setCaseItem(resolvedCase);
        setDraft(hydrateDraftFromCase(resolvedCase));
        setTranscriptInput(resolvedCase.transcript ?? "");
      } catch (cause) {
        setError(safeUserFacingError(cause, t(language, "council.error.loadCase")));
      }
    };
    if (queryCaseId !== null) {
      void bootstrap();
    }
  }, [language, queryCaseId, router]);

  const onExtractIntake = async () => {
    if (!caseItem) return;
    setError("");
    setExtractNotice("");
    setExtractWarnings([]);

    if (intakeMode === "transcript" && !transcriptInput.trim()) {
      setError(t(language, "council.intake.transcriptRequired"));
      return;
    }
    if (intakeMode === "audio" && !audioFile && !transcriptInput.trim()) {
      setError(t(language, "council.intake.audioRequired"));
      return;
    }

    setIsExtracting(true);
    try {
      const updated = await runCouncilCaseIntake(caseItem.id, {
        transcript: transcriptInput,
        audioFile: intakeMode === "audio" ? audioFile : null,
      });
      setCaseItem(updated);
      setTranscriptInput(updated.transcript || transcriptInput);
      setDraft(hydrateDraftFromCase(updated));
      const warnings = Array.isArray(updated.intake?.warnings)
        ? updated.intake?.warnings.map((item) => String(item))
        : [];
      setExtractWarnings(warnings);
      setExtractNotice(t(language, "council.intake.normalized"));
    } catch (cause) {
      setError(safeUserFacingError(cause, t(language, "council.error.extractIntake")));
    } finally {
      setIsExtracting(false);
    }
  };

  const onSaveAndNext = async () => {
    if (!caseItem) return;
    setError("");
    setIsSaving(true);
    try {
      const requestPayload = {
        symptoms: draft.symptomsInput
          .split("\n")
          .map((item) => item.trim())
          .filter(Boolean),
        labs: draft.labsInput
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean)
          .reduce<Record<string, string>>((acc, line) => {
            const [left, ...rest] = line.split("=");
            const key = left?.trim();
            const value = rest.join("=").trim();
            if (key && value) acc[key] = value;
            return acc;
          }, {}),
        medications: draft.medicationsInput
          .split("\n")
          .map((item) => item.trim())
          .filter(Boolean),
        history: draft.historyInput.trim(),
      };

      await updateCouncilCase(caseItem.id, {
        transcript: transcriptInput,
        status: "intake_ready",
        request: requestPayload,
      });
      setActiveCouncilCaseId(caseItem.id);
      router.push(`/council/new/specialists?caseId=${caseItem.id}`);
    } catch (cause) {
      setError(safeUserFacingError(cause, t(language, "council.error.saveIntake")));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <PageShell
      title={t(language, "council.intake.title")}
      description={t(language, "council.intake.description")}
      variant="plain"
    >
      <div className="space-y-5">
        <CouncilWorkspaceNav />

        <section className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
            {t(language, "council.step", { step: 1, id: caseItem?.id ?? "--" })}
          </p>
          <h2 className="mt-2 text-xl font-semibold text-[var(--text-primary)]">{t(language, "council.intake.heading")}</h2>

          <div className="mt-4 flex gap-2">
            <button
              type="button"
              onClick={() => setIntakeMode("transcript")}
              className={`min-h-[42px] rounded-lg border px-3 text-sm font-semibold ${
                intakeMode === "transcript"
                  ? "border-[color:var(--brand-primary)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                  : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-primary)]"
              }`}
            >
              {t(language, "council.intake.mode.transcript")}
            </button>
            <button
              type="button"
              onClick={() => setIntakeMode("audio")}
              className={`min-h-[42px] rounded-lg border px-3 text-sm font-semibold ${
                intakeMode === "audio"
                  ? "border-[color:var(--brand-primary)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                  : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-primary)]"
              }`}
            >
              {t(language, "council.intake.mode.audio")}
            </button>
          </div>

          {intakeMode === "audio" ? (
            <div className="mt-3 rounded-xl border border-dashed border-[color:var(--shell-border)] p-4">
              <input
                type="file"
                accept="audio/*,.wav,.mp3,.m4a,.webm"
                onChange={(event) => setAudioFile(event.target.files?.[0] ?? null)}
                className="block w-full text-sm"
              />
              {audioFile ? <p className="mt-2 text-xs text-[var(--text-secondary)]">{t(language, "council.intake.fileSelected", { name: audioFile.name })}</p> : null}
            </div>
          ) : null}

          <textarea
            value={transcriptInput}
            onChange={(event) => setTranscriptInput(event.target.value)}
            placeholder={intakeMode === "audio" ? t(language, "council.intake.audioTranscriptPlaceholder") : t(language, "council.intake.transcriptPlaceholder")}
            className="mt-3 min-h-[160px] w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-sm"
          />

          <button
            type="button"
            onClick={() => void onExtractIntake()}
            disabled={isExtracting || !caseItem}
            className="mt-3 inline-flex min-h-[44px] items-center rounded-lg border border-[color:var(--brand-600)] bg-[var(--brand-600)] px-4 text-sm font-semibold text-[#cdd7ff] transition-colors hover:bg-[var(--brand-700)] disabled:opacity-60"
          >
            {isExtracting ? t(language, "council.intake.processing") : t(language, "council.intake.normalize")}
          </button>

          {extractNotice ? <p className="mt-3 text-sm text-[var(--text-brand)]">{extractNotice}</p> : null}
          {extractWarnings.length ? (
            <ul className="mt-2 list-disc pl-5 text-xs text-[var(--status-warn-text)]">
              {extractWarnings.map((item, index) => (
                <li key={`${item}-${index}`}>{item}</li>
              ))}
            </ul>
          ) : null}
        </section>

        <section className="grid gap-3 md:grid-cols-2">
          <label className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
            <span className="text-sm font-semibold">{t(language, "council.intake.symptoms")}</span>
            <textarea
              value={draft.symptomsInput}
              onChange={(event) => setDraft((current) => ({ ...current, symptomsInput: event.target.value }))}
              className="mt-2 min-h-[130px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-sm"
            />
          </label>
          <label className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
            <span className="text-sm font-semibold">{t(language, "council.intake.labs")}</span>
            <textarea
              value={draft.labsInput}
              onChange={(event) => setDraft((current) => ({ ...current, labsInput: event.target.value }))}
              className="mt-2 min-h-[130px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-sm"
            />
          </label>
          <label className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
            <span className="text-sm font-semibold">{t(language, "council.intake.medicines")}</span>
            <textarea
              value={draft.medicationsInput}
              onChange={(event) => setDraft((current) => ({ ...current, medicationsInput: event.target.value }))}
              className="mt-2 min-h-[130px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-sm"
            />
          </label>
          <label className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
            <span className="text-sm font-semibold">{t(language, "council.intake.history")}</span>
            <textarea
              value={draft.historyInput}
              onChange={(event) => setDraft((current) => ({ ...current, historyInput: event.target.value }))}
              className="mt-2 min-h-[130px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-sm"
            />
          </label>
        </section>

        {error ? <p className="text-sm text-red-400">{error}</p> : null}

        <div className="flex flex-wrap justify-between gap-2">
          <Link href="/council/new" className="inline-flex min-h-[42px] items-center rounded-lg border border-[color:var(--shell-border)] px-4 text-sm font-semibold">
            {t(language, "council.action.back")}
          </Link>
          <button
            type="button"
            onClick={() => void onSaveAndNext()}
            disabled={isSaving || !caseItem}
            className="inline-flex min-h-[44px] items-center rounded-lg border border-[color:var(--brand-600)] bg-[var(--brand-600)] px-4 text-sm font-semibold text-[#cdd7ff] transition-colors hover:bg-[var(--brand-700)] disabled:opacity-60"
          >
            {isSaving ? t(language, "council.action.saving") : t(language, "council.action.nextStep", { step: 2 })}
          </button>
        </div>
      </div>
    </PageShell>
  );
}
