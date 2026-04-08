"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import CouncilWorkspaceNav from "@/components/council/council-workspace-nav";
import PageShell from "@/components/ui/page-shell";
import {
  CouncilCaseDraft,
  extractCouncilIntake,
  loadCouncilDraft,
  saveCouncilDraft,
} from "@/lib/council";
import { DEFAULT_DRAFT, normalizeDraft } from "@/lib/council-wizard";

type IntakeMode = "transcript" | "audio";

export default function CouncilNewIntakePage() {
  const router = useRouter();
  const [draft, setDraft] = useState<CouncilCaseDraft>(DEFAULT_DRAFT);
  const [intakeMode, setIntakeMode] = useState<IntakeMode>("transcript");
  const [transcriptInput, setTranscriptInput] = useState("");
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractNotice, setExtractNotice] = useState("");
  const [extractWarnings, setExtractWarnings] = useState<string[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    const cached = loadCouncilDraft();
    if (!cached) return;
    setDraft(normalizeDraft(cached));
  }, []);

  useEffect(() => {
    saveCouncilDraft(draft);
  }, [draft]);

  const hasData =
    Boolean(draft.symptomsInput.trim()) ||
    Boolean(draft.labsInput.trim()) ||
    Boolean(draft.medicationsInput.trim()) ||
    Boolean(draft.historyInput.trim());

  const onExtractIntake = async () => {
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
      const result = await extractCouncilIntake({
        transcript: transcriptInput,
        audioFile: intakeMode === "audio" ? audioFile : null,
      });

      setDraft((current) => ({
        ...current,
        symptomsInput: result.symptomsInput,
        labsInput: result.labsInput,
        medicationsInput: result.medicationsInput,
        historyInput: result.historyInput,
      }));
      if (result.transcript) {
        setTranscriptInput(result.transcript);
      }
      setExtractWarnings(result.warnings);
      setExtractNotice(`Đã chuẩn hóa bằng ${result.modelUsed}. Bạn có thể chỉnh tay rồi sang bước tiếp theo.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể chuẩn hóa dữ liệu intake lúc này.");
    } finally {
      setIsExtracting(false);
    }
  };

  return (
    <PageShell
      title="Council Wizard - Intake"
      description="Bước 1/3: nhập dữ liệu ca bệnh."
      variant="plain"
    >
      <div className="space-y-5">
        <CouncilWorkspaceNav />

        <section className="chrome-panel rounded-[1.5rem] p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Step 1/3</p>
          <h2 className="mt-2 text-xl font-semibold text-[var(--text-primary)]">Intake ca bệnh</h2>

          <div className="mt-4 flex gap-2">
            <button
              type="button"
              onClick={() => setIntakeMode("transcript")}
              className={`min-h-[42px] rounded-lg border px-3 text-sm font-semibold ${
                intakeMode === "transcript"
                  ? "border-cyan-400 bg-cyan-100 text-cyan-900"
                  : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-primary)]"
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
                  : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-primary)]"
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
            disabled={isExtracting}
            className="mt-3 inline-flex min-h-[44px] items-center rounded-lg border border-cyan-300/65 bg-gradient-to-r from-sky-600 to-cyan-500 px-4 text-sm font-semibold text-white disabled:opacity-60"
          >
            {isExtracting ? "Đang xử lý..." : "Chuẩn hóa intake"}
          </button>

          {extractNotice ? <p className="mt-3 text-sm text-emerald-700">{extractNotice}</p> : null}
          {extractWarnings.length ? (
            <ul className="mt-2 list-disc pl-5 text-xs text-amber-700">
              {extractWarnings.map((item, index) => (
                <li key={`${item}-${index}`}>{item}</li>
              ))}
            </ul>
          ) : null}
        </section>

        <section className="grid gap-3 md:grid-cols-2">
          <label className="chrome-panel rounded-xl p-4">
            <span className="text-sm font-semibold">Triệu chứng</span>
            <textarea
              value={draft.symptomsInput}
              onChange={(event) => setDraft((current) => ({ ...current, symptomsInput: event.target.value }))}
              className="mt-2 min-h-[130px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-sm"
            />
          </label>
          <label className="chrome-panel rounded-xl p-4">
            <span className="text-sm font-semibold">Xét nghiệm</span>
            <textarea
              value={draft.labsInput}
              onChange={(event) => setDraft((current) => ({ ...current, labsInput: event.target.value }))}
              className="mt-2 min-h-[130px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-sm"
            />
          </label>
          <label className="chrome-panel rounded-xl p-4">
            <span className="text-sm font-semibold">Thuốc</span>
            <textarea
              value={draft.medicationsInput}
              onChange={(event) => setDraft((current) => ({ ...current, medicationsInput: event.target.value }))}
              className="mt-2 min-h-[130px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-sm"
            />
          </label>
          <label className="chrome-panel rounded-xl p-4">
            <span className="text-sm font-semibold">Bệnh sử</span>
            <textarea
              value={draft.historyInput}
              onChange={(event) => setDraft((current) => ({ ...current, historyInput: event.target.value }))}
              className="mt-2 min-h-[130px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-sm"
            />
          </label>
        </section>

        {error ? <p className="text-sm text-red-700">{error}</p> : null}

        <div className="flex flex-wrap justify-between gap-2">
          <Link href="/council/new" className="inline-flex min-h-[42px] items-center rounded-lg border border-[color:var(--shell-border)] px-4 text-sm font-semibold">
            Quay lại
          </Link>
          <button
            type="button"
            onClick={() => router.push("/council/new/specialists")}
            className="inline-flex min-h-[44px] items-center rounded-lg border border-cyan-300/65 bg-gradient-to-r from-sky-600 to-cyan-500 px-4 text-sm font-semibold text-white"
          >
            Sang bước 2
          </button>
        </div>

        {!hasData ? <p className="text-xs text-[var(--text-muted)]">Bạn có thể sang bước 2 trước, nhưng nên nhập dữ liệu từ bước 1 để kết quả chính xác hơn.</p> : null}
      </div>
    </PageShell>
  );
}
