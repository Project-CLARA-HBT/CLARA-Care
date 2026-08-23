"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import CouncilFlowStepper from "@/components/council/council-flow-stepper";
import CouncilWorkspaceNav from "@/components/council/council-workspace-nav";
import { Icon } from "@/components/ui/icon";
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
  questionInput: string;
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
  const question = typeof payload.question === "string" ? payload.question : "";
  return {
    questionInput: question,
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
    questionInput: "",
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
      setDraft((curr) => ({
        ...hydrateDraftFromCase(updated),
        questionInput: curr.questionInput,
      }));
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
        question: draft.questionInput.trim(),
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

  const applyQuestionTemplate = (template: string) => {
    setDraft((curr) => ({ ...curr, questionInput: template }));
  };

  return (
    <PageShell
      title={t(language, "council.intake.title")}
      description={t(language, "council.intake.description")}
      variant="plain"
    >
      <div className="space-y-5">
        <CouncilWorkspaceNav />
        <CouncilFlowStepper currentStep="question" caseId={caseItem?.id} />

        {/* Step 2: Clinical Question Section */}
        <section className="rounded-[14px] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6">
          <div className="flex items-center gap-2">
            <span className="rounded-md border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
              {language === "vi" ? "Bước 2: Câu hỏi lâm sàng" : "Step 2: Clinical Question"}
            </span>
          </div>
          <h2 className="mt-2 text-xl font-bold text-[var(--text-primary)]">
            {t(language, "council.question.heading")}
          </h2>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">
            {language === "vi"
              ? "Xác định trọng tâm hội đồng chuyên khoa AI cần giải đáp và đưa ra khuyến nghị."
              : "Define the core question for the AI multi-specialty council to address."}
          </p>

          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() =>
                applyQuestionTemplate(
                  language === "vi"
                    ? "Chẩn đoán phân biệt và chiến lược điều trị tối ưu"
                    : "Differential diagnosis and optimal treatment strategy",
                )
              }
              className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:border-[color:var(--brand-600)] hover:text-[var(--text-primary)]"
            >
              + {t(language, "council.question.template.diagnosis")}
            </button>
            <button
              type="button"
              onClick={() =>
                applyQuestionTemplate(
                  language === "vi"
                    ? "Đánh giá tương tác thuốc tiềm ẩn và nguy cơ tác dụng phụ"
                    : "Assess potential drug interactions and adverse effect risks",
                )
              }
              className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:border-[color:var(--brand-600)] hover:text-[var(--text-primary)]"
            >
              + {t(language, "council.question.template.ddi")}
            </button>
            <button
              type="button"
              onClick={() =>
                applyQuestionTemplate(
                  language === "vi"
                    ? "Điều chỉnh liều thuốc dựa trên chức năng thận và gan"
                    : "Adjust medication dosage based on renal and hepatic function",
                )
              }
              className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:border-[color:var(--brand-600)] hover:text-[var(--text-primary)]"
            >
              + {t(language, "council.question.template.dosage")}
            </button>
            <button
              type="button"
              onClick={() =>
                applyQuestionTemplate(
                  language === "vi"
                    ? "Chiến lược can thiệp và các xét nghiệm chuyên sâu cần làm thêm"
                    : "Intervention strategy and recommended advanced diagnostic workup",
                )
              }
              className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:border-[color:var(--brand-600)] hover:text-[var(--text-primary)]"
            >
              + {t(language, "council.question.template.treatment")}
            </button>
          </div>

          <textarea
            value={draft.questionInput}
            onChange={(e) => setDraft((curr) => ({ ...curr, questionInput: e.target.value }))}
            placeholder={t(language, "council.question.placeholder")}
            className="mt-3 min-h-[90px] w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-3 text-sm text-[var(--text-primary)] focus:border-[color:var(--brand-600)] focus:outline-none"
          />
        </section>

        {/* Step 3: Clinical Context (Extraction / Input) */}
        <section className="rounded-[14px] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6">
          <div className="flex items-center gap-2">
            <span className="rounded-md border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
              {language === "vi" ? "Bước 3: Bối cảnh lâm sàng" : "Step 3: Clinical Context"}
            </span>
          </div>
          <h2 className="mt-2 text-xl font-bold text-[var(--text-primary)]">
            {t(language, "council.intake.heading")}
          </h2>

          <div className="mt-4 flex gap-2">
            <button
              type="button"
              onClick={() => setIntakeMode("transcript")}
              className={`min-h-[42px] rounded-xl border px-4 text-sm font-bold ${
                intakeMode === "transcript"
                  ? "border-[color:var(--brand-600)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                  : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-primary)]"
              }`}
            >
              {t(language, "council.intake.mode.transcript")}
            </button>
            <button
              type="button"
              onClick={() => setIntakeMode("audio")}
              className={`min-h-[42px] rounded-xl border px-4 text-sm font-bold ${
                intakeMode === "audio"
                  ? "border-[color:var(--brand-600)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                  : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-primary)]"
              }`}
            >
              {t(language, "council.intake.mode.audio")}
            </button>
          </div>

          {intakeMode === "audio" ? (
            <div className="mt-3 rounded-xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4">
              <input
                type="file"
                accept="audio/*,.wav,.mp3,.m4a,.webm"
                onChange={(event) => setAudioFile(event.target.files?.[0] ?? null)}
                className="block w-full text-sm text-[var(--text-secondary)]"
              />
              {audioFile ? (
                <p className="mt-2 text-xs font-semibold text-[var(--text-brand)]">
                  {t(language, "council.intake.fileSelected", { name: audioFile.name })}
                </p>
              ) : null}
            </div>
          ) : null}

          <textarea
            value={transcriptInput}
            onChange={(event) => setTranscriptInput(event.target.value)}
            placeholder={
              intakeMode === "audio"
                ? t(language, "council.intake.audioTranscriptPlaceholder")
                : t(language, "council.intake.transcriptPlaceholder")
            }
            className="mt-3 min-h-[140px] w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-3 text-sm text-[var(--text-primary)] focus:border-[color:var(--brand-600)] focus:outline-none"
          />

          <button
            type="button"
            onClick={() => void onExtractIntake()}
            disabled={isExtracting || !caseItem}
            className="mt-3 inline-flex min-h-[44px] items-center gap-2 rounded-xl border border-[color:var(--brand-700)] bg-[var(--brand-600)] px-5 text-sm font-bold text-[var(--on-secondary-container)] shadow-sm transition-colors hover:bg-[var(--brand-700)] disabled:opacity-60"
          >
            <Icon name="clinical-notes" size={16} />
            {isExtracting ? t(language, "council.intake.processing") : t(language, "council.intake.normalize")}
          </button>

          {extractNotice ? <p className="mt-3 text-sm font-semibold text-[var(--text-brand)]">{extractNotice}</p> : null}
          {extractWarnings.length ? (
            <ul className="mt-2 list-disc pl-5 text-xs text-[var(--status-warn-text)]">
              {extractWarnings.map((item, index) => (
                <li key={`${item}-${index}`}>{item}</li>
              ))}
            </ul>
          ) : null}
        </section>

        {/* Clinical Data Fields */}
        <section className="grid gap-4 md:grid-cols-2">
          <label className="rounded-[14px] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
            <span className="text-sm font-bold text-[var(--text-primary)]">
              {t(language, "council.intake.symptoms")}
            </span>
            <textarea
              value={draft.symptomsInput}
              onChange={(event) => setDraft((current) => ({ ...current, symptomsInput: event.target.value }))}
              placeholder={language === "vi" ? "Mỗi dòng 1 triệu chứng..." : "One symptom per line..."}
              className="mt-2 min-h-[120px] w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2.5 text-sm text-[var(--text-primary)]"
            />
          </label>
          <label className="rounded-[14px] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
            <span className="text-sm font-bold text-[var(--text-primary)]">
              {t(language, "council.intake.labs")}
            </span>
            <textarea
              value={draft.labsInput}
              onChange={(event) => setDraft((current) => ({ ...current, labsInput: event.target.value }))}
              placeholder="Creatinine=1.8&#10;Troponin_I=0.45&#10;eGFR=42"
              className="mt-2 min-h-[120px] w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2.5 text-sm font-mono text-[var(--text-primary)]"
            />
          </label>
          <label className="rounded-[14px] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
            <span className="text-sm font-bold text-[var(--text-primary)]">
              {t(language, "council.intake.medicines")}
            </span>
            <textarea
              value={draft.medicationsInput}
              onChange={(event) => setDraft((current) => ({ ...current, medicationsInput: event.target.value }))}
              placeholder={language === "vi" ? "Aspirin 81mg&#10;Clopidogrel 75mg&#10;Atorvastatin 40mg" : "Aspirin 81mg&#10;Clopidogrel 75mg"}
              className="mt-2 min-h-[120px] w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2.5 text-sm text-[var(--text-primary)]"
            />
          </label>
          <label className="rounded-[14px] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
            <span className="text-sm font-bold text-[var(--text-primary)]">
              {t(language, "council.intake.history")}
            </span>
            <textarea
              value={draft.historyInput}
              onChange={(event) => setDraft((current) => ({ ...current, historyInput: event.target.value }))}
              placeholder={language === "vi" ? "Tiền sử tăng huyết áp 10 năm, ĐTĐ type 2 5 năm, CKD giai đoạn 3..." : "HTN 10y, T2D 5y, CKD Stage 3..."}
              className="mt-2 min-h-[120px] w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2.5 text-sm text-[var(--text-primary)]"
            />
          </label>
        </section>

        {error ? <p className="text-sm font-semibold text-[var(--status-danger-text)]">{error}</p> : null}

        <div className="flex flex-wrap justify-between gap-3">
          <Link
            href="/council/new"
            className="inline-flex min-h-[44px] items-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-5 text-sm font-semibold text-[var(--text-primary)] hover:bg-[var(--surface-muted)]"
          >
            {t(language, "council.action.back")}
          </Link>
          <button
            type="button"
            onClick={() => void onSaveAndNext()}
            disabled={isSaving || !caseItem}
            className="inline-flex min-h-[44px] items-center gap-2 rounded-xl border border-[color:var(--brand-700)] bg-[var(--brand-600)] px-6 text-sm font-bold text-[var(--on-secondary-container)] shadow-sm transition-colors hover:bg-[var(--brand-700)] disabled:opacity-60"
          >
            <Icon name="arrow-right" size={16} />
            {isSaving ? t(language, "council.action.saving") : t(language, "council.action.nextStep", { step: 3 })}
          </button>
        </div>
      </div>
    </PageShell>
  );
}
