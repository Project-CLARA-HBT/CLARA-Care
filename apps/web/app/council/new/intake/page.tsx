"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import CouncilWorkspaceNav from "@/components/council/council-workspace-nav";
import PageShell from "@/components/ui/page-shell";
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
          resolvedCase = await createCouncilCase({ title: `Case ${new Date().toLocaleString("vi-VN")}` });
          router.replace(`/council/new/intake?caseId=${resolvedCase.id}`);
        }

        if (!resolvedCase) return;
        setActiveCouncilCaseId(resolvedCase.id);
        setCaseItem(resolvedCase);
        setDraft(hydrateDraftFromCase(resolvedCase));
        setTranscriptInput(resolvedCase.transcript ?? "");
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Không thể tải case.");
      }
    };
    if (queryCaseId !== null) {
      void bootstrap();
    }
  }, [queryCaseId, router]);

  const onExtractIntake = async () => {
    if (!caseItem) return;
    setError("");
    setExtractNotice("");
    setExtractWarnings([]);

    if (intakeMode === "transcript" && !transcriptInput.trim()) {
      setError("Vui lòng dán transcript trước khi chạy chuẩn hóa.");
      return;
    }
    if (intakeMode === "audio" && !audioFile && !transcriptInput.trim()) {
      setError("Vui lòng upload audio hoặc dán transcript hỗ trợ.");
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
      setExtractNotice("Đã chuẩn hóa intake vào case hiện tại. Bạn có thể chỉnh tay trước khi sang bước 2.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể chuẩn hóa dữ liệu intake lúc này.");
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
      setError(cause instanceof Error ? cause.message : "Không thể lưu intake.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <PageShell
      title="Council Wizard - Intake"
      description="Bước 1/3: nhập dữ liệu ca bệnh thật vào case."
      variant="plain"
    >
      <div className="space-y-5">
        <CouncilWorkspaceNav />

        <section className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
            Step 1/3 · Case #{caseItem?.id ?? "--"}
          </p>
          <h2 className="mt-2 text-xl font-semibold text-[var(--text-primary)]">Intake ca bệnh</h2>

          <div className="mt-4 flex gap-2">
            <button
              type="button"
              onClick={() => setIntakeMode("transcript")}
              className={`min-h-[42px] rounded-lg border px-3 text-sm font-semibold ${
                intakeMode === "transcript"
                  ? "border-cyan-400 bg-cyan-100 text-cyan-900"
                  : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-primary)]"
              }`}
            >
              Transcript
            </button>
            <button
              type="button"
              onClick={() => setIntakeMode("audio")}
              className={`min-h-[42px] rounded-lg border px-3 text-sm font-semibold ${
                intakeMode === "audio"
                  ? "border-cyan-400 bg-cyan-100 text-cyan-900"
                  : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-primary)]"
              }`}
            >
              Audio
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
              {audioFile ? <p className="mt-2 text-xs text-[var(--text-secondary)]">Đã chọn: {audioFile.name}</p> : null}
            </div>
          ) : null}

          <textarea
            value={transcriptInput}
            onChange={(event) => setTranscriptInput(event.target.value)}
            placeholder={intakeMode === "audio" ? "(Tùy chọn) Dán transcript hỗ trợ..." : "Dán transcript tại đây..."}
            className="mt-3 min-h-[160px] w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-sm"
          />

          <button
            type="button"
            onClick={() => void onExtractIntake()}
            disabled={isExtracting || !caseItem}
            className="mt-3 inline-flex min-h-[44px] items-center rounded-lg border border-cyan-300/65 bg-gradient-to-r from-sky-600 to-cyan-500 px-4 text-sm font-semibold text-white disabled:opacity-60"
          >
            {isExtracting ? "Đang xử lý..." : "Chuẩn hóa intake"}
          </button>

          {extractNotice ? <p className="mt-3 text-sm text-emerald-400">{extractNotice}</p> : null}
          {extractWarnings.length ? (
            <ul className="mt-2 list-disc pl-5 text-xs text-amber-300">
              {extractWarnings.map((item, index) => (
                <li key={`${item}-${index}`}>{item}</li>
              ))}
            </ul>
          ) : null}
        </section>

        <section className="grid gap-3 md:grid-cols-2">
          <label className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
            <span className="text-sm font-semibold">Triệu chứng</span>
            <textarea
              value={draft.symptomsInput}
              onChange={(event) => setDraft((current) => ({ ...current, symptomsInput: event.target.value }))}
              className="mt-2 min-h-[130px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-sm"
            />
          </label>
          <label className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
            <span className="text-sm font-semibold">Xét nghiệm</span>
            <textarea
              value={draft.labsInput}
              onChange={(event) => setDraft((current) => ({ ...current, labsInput: event.target.value }))}
              className="mt-2 min-h-[130px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-sm"
            />
          </label>
          <label className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
            <span className="text-sm font-semibold">Thuốc</span>
            <textarea
              value={draft.medicationsInput}
              onChange={(event) => setDraft((current) => ({ ...current, medicationsInput: event.target.value }))}
              className="mt-2 min-h-[130px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-sm"
            />
          </label>
          <label className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
            <span className="text-sm font-semibold">Bệnh sử</span>
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
            Quay lại
          </Link>
          <button
            type="button"
            onClick={() => void onSaveAndNext()}
            disabled={isSaving || !caseItem}
            className="inline-flex min-h-[44px] items-center rounded-lg border border-cyan-300/65 bg-gradient-to-r from-sky-600 to-cyan-500 px-4 text-sm font-semibold text-white disabled:opacity-60"
          >
            {isSaving ? "Đang lưu..." : "Sang bước 2"}
          </button>
        </div>
      </div>
    </PageShell>
  );
}
