"use client";

import { FormEvent, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import {
  MedicalRecordNote,
  SoapSections,
  createSoap,
  normalizeMedicalRecordNote,
  normalizeSoapSections,
} from "@/lib/scribe";

function joinSoap(sections: SoapSections): string {
  return [
    `S: ${sections.subjective || "Chua co du lieu"}`,
    `O: ${sections.objective || "Chua co du lieu"}`,
    `A: ${sections.assessment || "Chua co du lieu"}`,
    `P: ${sections.plan || "Chua co du lieu"}`,
  ].join("\n\n");
}

function joinMedicalRecordNote(note: MedicalRecordNote): string {
  return [
    `Chief complaint: ${note.chiefComplaint || "N/A"}`,
    `HPI: ${note.hpi || "N/A"}`,
    `Objective: ${note.objective || "N/A"}`,
    `Assessment: ${note.assessment.length ? note.assessment.join("; ") : "N/A"}`,
    `Plan: ${note.plan.length ? note.plan.join("; ") : "N/A"}`,
    `Medications: ${note.medications.length ? note.medications.join("; ") : "N/A"}`,
    `Follow-up: ${note.followUp || "N/A"}`,
    `Warnings: ${note.warnings.length ? note.warnings.join("; ") : "N/A"}`,
  ].join("\n");
}

export default function ScribePage() {
  const [transcript, setTranscript] = useState("");
  const [sections, setSections] = useState<SoapSections | null>(null);
  const [medicalRecordNote, setMedicalRecordNote] = useState<MedicalRecordNote | null>(null);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [notice, setNotice] = useState<{
    tone: "success" | "error";
    message: string;
  } | null>(null);

  const hasSoapContent = useMemo(() => {
    if (!sections) return false;
    return Boolean(sections.subjective || sections.objective || sections.assessment || sections.plan);
  }, [sections]);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextTranscript = transcript.trim();
    if (!nextTranscript) return;

    setError("");
    setIsSubmitting(true);
    setSections(null);
    setMedicalRecordNote(null);
    setNotice(null);

    try {
      const response = await createSoap({ transcript: nextTranscript });
      setSections(normalizeSoapSections(response));
      setMedicalRecordNote(normalizeMedicalRecordNote(response));
    } catch (submitError) {
      const fallbackMessage = "Khong the tao SOAP note. Vui long thu lai.";
      if (submitError instanceof Error && submitError.message) {
        setError(submitError.message);
      } else {
        setError(fallbackMessage);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const pushNotice = (tone: "success" | "error", message: string) => {
    setNotice({ tone, message });
    window.setTimeout(() => {
      setNotice(null);
    }, 2500);
  };

  const onCopySoap = async () => {
    if (!sections) return;
    const soapText = joinSoap(sections).trim();
    const medicalRecordText = medicalRecordNote
      ? `\n\nMedical Record Note\n${joinMedicalRecordNote(medicalRecordNote)}`
      : "";
    const fullText = `${soapText}${medicalRecordText}`.trim();

    if (!fullText) {
      pushNotice("error", "Khong co noi dung SOAP de sao chep.");
      return;
    }

    if (!navigator?.clipboard) {
      pushNotice("error", "Trinh duyet chua ho tro sao chep tu dong.");
      return;
    }

    try {
      await navigator.clipboard.writeText(fullText);
      pushNotice("success", "Da sao chep SOAP + medical record note vao clipboard.");
    } catch {
      pushNotice("error", "Khong the sao chep. Vui long thu lai.");
    }
  };

  const onExportSoap = () => {
    if (!sections) return;
    const soapText = joinSoap(sections).trim();
    const medicalRecordText = medicalRecordNote
      ? `\n\n## Medical Record Note\n${joinMedicalRecordNote(medicalRecordNote)}`
      : "";
    const fullText = `${soapText}${medicalRecordText}`.trim();

    if (!fullText) {
      pushNotice("error", "Khong co noi dung SOAP de xuat file.");
      return;
    }

    try {
      const now = new Date();
      const pad = (value: number) => String(value).padStart(2, "0");
      const timestamp = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(
        now.getHours()
      )}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
      const fileName = `clara-soap-${timestamp}.md`;
      const content = `# SOAP Note\n\n${fullText}\n`;

      const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = fileName;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

      pushNotice("success", `Da xuat file ${fileName}.`);
    } catch {
      pushNotice("error", "Khong the xuat file. Vui long thu lai.");
    }
  };

  return (
    <PageShell title="Tro ly ghi chep y khoa">
      <div className="space-y-4">
        <p className="text-sm text-slate-600">Dan transcript buoi kham de tao nhanh SOAP draft (S/O/A/P).</p>

        <form className="space-y-3" onSubmit={onSubmit}>
          <textarea
            className="h-44 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
            placeholder="Vi du: BN nam 56 tuoi, than dau nguc 2 ngay..."
            value={transcript}
            onChange={(event) => setTranscript(event.target.value)}
            disabled={isSubmitting}
          />
          <button
            type="submit"
            className="rounded bg-primary px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-70"
            disabled={isSubmitting || !transcript.trim()}
          >
            {isSubmitting ? "Dang tao SOAP..." : "Tao SOAP"}
          </button>
        </form>

        {error ? (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
        ) : null}

        {sections ? (
          <section className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => void onCopySoap()}
                className="rounded border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={!hasSoapContent}
              >
                Sao chep
              </button>
              <button
                type="button"
                onClick={onExportSoap}
                className="rounded border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={!hasSoapContent}
              >
                Xuat file
              </button>
            </div>

            {notice ? (
              <p
                className={[
                  "rounded-md border px-3 py-2 text-xs",
                  notice.tone === "success"
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                    : "border-rose-200 bg-rose-50 text-rose-700",
                ].join(" ")}
              >
                {notice.message}
              </p>
            ) : null}

            <div className="grid gap-3 md:grid-cols-2">
              <article className="rounded-md border border-slate-200 bg-white p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">S - Subjective</p>
                <p className="mt-2 whitespace-pre-wrap text-sm text-slate-800">{sections.subjective || "Chua co du lieu"}</p>
              </article>

              <article className="rounded-md border border-slate-200 bg-white p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">O - Objective</p>
                <p className="mt-2 whitespace-pre-wrap text-sm text-slate-800">{sections.objective || "Chua co du lieu"}</p>
              </article>

              <article className="rounded-md border border-slate-200 bg-white p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">A - Assessment</p>
                <p className="mt-2 whitespace-pre-wrap text-sm text-slate-800">{sections.assessment || "Chua co du lieu"}</p>
              </article>

              <article className="rounded-md border border-slate-200 bg-white p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">P - Plan</p>
                <p className="mt-2 whitespace-pre-wrap text-sm text-slate-800">{sections.plan || "Chua co du lieu"}</p>
              </article>
            </div>

            {medicalRecordNote ? (
              <article className="rounded-md border border-cyan-200 bg-cyan-50 p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-cyan-700">Medical Record Note</p>
                <div className="mt-2 grid gap-2 text-sm text-slate-800 md:grid-cols-2">
                  <p>
                    <span className="font-semibold">Chief complaint:</span> {medicalRecordNote.chiefComplaint || "Chua co du lieu"}
                  </p>
                  <p>
                    <span className="font-semibold">HPI:</span> {medicalRecordNote.hpi || "Chua co du lieu"}
                  </p>
                  <p className="md:col-span-2">
                    <span className="font-semibold">Objective:</span> {medicalRecordNote.objective || "Chua co du lieu"}
                  </p>
                  <p className="md:col-span-2">
                    <span className="font-semibold">Assessment:</span>{" "}
                    {medicalRecordNote.assessment.length ? medicalRecordNote.assessment.join("; ") : "Chua co du lieu"}
                  </p>
                  <p className="md:col-span-2">
                    <span className="font-semibold">Plan:</span>{" "}
                    {medicalRecordNote.plan.length ? medicalRecordNote.plan.join("; ") : "Chua co du lieu"}
                  </p>
                  <p>
                    <span className="font-semibold">Medications:</span>{" "}
                    {medicalRecordNote.medications.length ? medicalRecordNote.medications.join("; ") : "Chua co du lieu"}
                  </p>
                  <p>
                    <span className="font-semibold">Follow-up:</span> {medicalRecordNote.followUp || "Chua co du lieu"}
                  </p>
                  <p className="md:col-span-2">
                    <span className="font-semibold">Warnings:</span>{" "}
                    {medicalRecordNote.warnings.length ? medicalRecordNote.warnings.join("; ") : "Khong co canh bao"}
                  </p>
                </div>
              </article>
            ) : null}

            <details className="rounded-md border border-dashed border-slate-300 bg-white p-3">
              <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-slate-500">
                Xem tong hop SOAP
              </summary>
              <pre className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{joinSoap(sections)}</pre>
            </details>
          </section>
        ) : null}
      </div>
    </PageShell>
  );
}
