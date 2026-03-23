"use client";

import { FormEvent, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import { parseFreeTextList, parseLabsInput } from "@/lib/careguard";
import { CouncilRunResult, normalizeCouncilRunResult, runCouncil } from "@/lib/council";

type SpecialistOption = {
  id: string;
  label: string;
};

const SPECIALIST_OPTIONS: SpecialistOption[] = [
  { id: "cardiology", label: "Cardiology" },
  { id: "neurology", label: "Neurology" },
  { id: "endocrinology", label: "Endocrinology" },
  { id: "pharmacology", label: "Pharmacology" },
  { id: "nephrology", label: "Nephrology" }
];

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function getEmergencyBadgeClass(isEmergency: boolean): string {
  if (isEmergency) return "border-red-200 bg-red-50 text-red-700";
  return "border-emerald-200 bg-emerald-50 text-emerald-700";
}

export default function CouncilPage() {
  const [symptomsInput, setSymptomsInput] = useState("");
  const [labsInput, setLabsInput] = useState("");
  const [medicationsInput, setMedicationsInput] = useState("");
  const [historyInput, setHistoryInput] = useState("");

  const [specialistCount, setSpecialistCount] = useState(3);
  const [selectedSpecialists, setSelectedSpecialists] = useState<string[]>(
    SPECIALIST_OPTIONS.slice(0, 3).map((item) => item.id)
  );

  const [result, setResult] = useState<CouncilRunResult | null>(null);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const emergencyClass = useMemo(() => getEmergencyBadgeClass(result?.isEmergency ?? false), [result?.isEmergency]);

  const onSpecialistCountChange = (value: string) => {
    const parsed = Number(value);
    const nextCount = clamp(
      Number.isFinite(parsed) ? Math.trunc(parsed) : 2,
      2,
      SPECIALIST_OPTIONS.length
    );
    setSpecialistCount(nextCount);
    setSelectedSpecialists((current) => current.slice(0, nextCount));
  };

  const onToggleSpecialist = (specialistId: string) => {
    setSelectedSpecialists((current) => {
      if (current.includes(specialistId)) {
        return current.filter((item) => item !== specialistId);
      }
      if (current.length >= specialistCount) return current;
      return [...current, specialistId];
    });
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const payload = {
      symptoms: parseFreeTextList(symptomsInput),
      labs: parseLabsInput(labsInput),
      medications: parseFreeTextList(medicationsInput),
      history: historyInput.trim(),
      specialistCount,
      specialists: selectedSpecialists
    };

    if (
      payload.symptoms.length === 0 &&
      Object.keys(payload.labs).length === 0 &&
      payload.medications.length === 0 &&
      !payload.history
    ) {
      setError("Vui lòng nhập dữ liệu ca bệnh trước khi chạy AI Council.");
      return;
    }

    if (payload.specialists.length < 2) {
      setError("Vui lòng chọn tối thiểu 2 chuyên khoa.");
      return;
    }

    setError("");
    setIsSubmitting(true);
    setResult(null);

    try {
      const response = await runCouncil(payload);
      setResult(normalizeCouncilRunResult(response));
    } catch (submitError) {
      const fallbackMessage = "Không thể chạy AI Council. Vui lòng thử lại.";
      if (submitError instanceof Error && submitError.message) {
        setError(submitError.message);
      } else {
        setError(fallbackMessage);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <PageShell title="AI Council">
      <div className="space-y-4">
        <p className="text-sm text-slate-600">
          Nhập hồ sơ ca bệnh để chạy hội chẩn đa chuyên khoa và nhận tổng hợp reasoning, xung đột, đồng thuận và khuyến
          nghị cuối cùng.
        </p>

        <form className="space-y-3" onSubmit={onSubmit}>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-1">
              <span className="text-sm font-medium text-slate-700">Symptoms</span>
              <textarea
                className="h-28 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
                placeholder="Đau ngực, khó thở, sốt..."
                value={symptomsInput}
                onChange={(event) => setSymptomsInput(event.target.value)}
                disabled={isSubmitting}
              />
            </label>

            <label className="space-y-1">
              <span className="text-sm font-medium text-slate-700">Labs</span>
              <textarea
                className="h-28 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
                placeholder="troponin=1.2, CRP=45, creatinine=2.0"
                value={labsInput}
                onChange={(event) => setLabsInput(event.target.value)}
                disabled={isSubmitting}
              />
            </label>

            <label className="space-y-1">
              <span className="text-sm font-medium text-slate-700">Medications</span>
              <textarea
                className="h-28 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
                placeholder="Warfarin, Metformin..."
                value={medicationsInput}
                onChange={(event) => setMedicationsInput(event.target.value)}
                disabled={isSubmitting}
              />
            </label>

            <label className="space-y-1">
              <span className="text-sm font-medium text-slate-700">History</span>
              <textarea
                className="h-28 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
                placeholder="Tiền sử tăng huyết áp, đái tháo đường type 2..."
                value={historyInput}
                onChange={(event) => setHistoryInput(event.target.value)}
                disabled={isSubmitting}
              />
            </label>
          </div>

          <section className="space-y-2 rounded-md border border-slate-200 bg-slate-50 p-3">
            <div className="grid gap-2 md:grid-cols-[180px_1fr] md:items-center">
              <label className="space-y-1">
                <span className="text-sm font-medium text-slate-700">Specialists Count</span>
                <input
                  type="number"
                  min={2}
                  max={SPECIALIST_OPTIONS.length}
                  value={specialistCount}
                  onChange={(event) => onSpecialistCountChange(event.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
                  disabled={isSubmitting}
                />
              </label>
              <p className="text-xs text-slate-600">
                Chọn tối đa {specialistCount} chuyên khoa ({selectedSpecialists.length}/{specialistCount} đã chọn).
              </p>
            </div>

            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {SPECIALIST_OPTIONS.map((option) => {
                const checked = selectedSpecialists.includes(option.id);
                const disableUnchecked = !checked && selectedSpecialists.length >= specialistCount;

                return (
                  <label
                    key={option.id}
                    className={`flex items-center gap-2 rounded-md border px-3 py-2 text-sm ${
                      checked
                        ? "border-blue-300 bg-blue-50 text-blue-800"
                        : "border-slate-300 bg-white text-slate-700"
                    } ${disableUnchecked || isSubmitting ? "cursor-not-allowed opacity-70" : "cursor-pointer"}`}
                  >
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-slate-300"
                      checked={checked}
                      onChange={() => onToggleSpecialist(option.id)}
                      disabled={isSubmitting || disableUnchecked}
                    />
                    {option.label}
                  </label>
                );
              })}
            </div>
          </section>

          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded bg-primary px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-70"
          >
            {isSubmitting ? "Đang chạy AI Council..." : "Run AI Council"}
          </button>
        </form>

        {error ? (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
        ) : null}

        {result ? (
          <section className="space-y-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-medium text-slate-700">Emergency Status</p>
              <span className={`rounded-full border px-2 py-1 text-xs font-semibold uppercase ${emergencyClass}`}>
                {result.isEmergency ? "Escalated" : "Stable"}
              </span>
            </div>
            {result.escalationReason ? <p className="text-sm text-slate-700">{result.escalationReason}</p> : null}

            <div className="space-y-2">
              <p className="text-sm font-semibold text-slate-700">Specialist Reasoning Logs</p>
              {result.specialistReasoningLogs.length ? (
                <ul className="space-y-2">
                  {result.specialistReasoningLogs.map((log, index) => (
                    <li key={`${log.specialist}-${index}`} className="rounded-md border border-slate-200 bg-white p-3 text-sm">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-semibold text-slate-800">{log.specialist}</p>
                        {log.confidence ? (
                          <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-600">
                            confidence: {log.confidence}
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-2 whitespace-pre-wrap text-slate-700">{log.reasoning}</p>
                      {log.recommendation ? (
                        <p className="mt-2 rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-700">
                          Recommendation: {log.recommendation}
                        </p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-600">Không có reasoning logs trong phản hồi hiện tại.</p>
              )}
            </div>

            <div className="space-y-2">
              <p className="text-sm font-semibold text-slate-700">Conflicts</p>
              {result.conflicts.length ? (
                <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
                  {result.conflicts.map((item, index) => (
                    <li key={`${item}-${index}`}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-600">Không ghi nhận xung đột nổi bật.</p>
              )}
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <article className="rounded-md border border-slate-200 bg-white p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Consensus</p>
                <p className="mt-2 whitespace-pre-wrap text-sm text-slate-800">
                  {result.consensus || "Không có mô tả đồng thuận."}
                </p>
              </article>

              <article className="rounded-md border border-slate-200 bg-white p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Divergence</p>
                {result.divergence.length ? (
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-800">
                    {result.divergence.map((item, index) => (
                      <li key={`${item}-${index}`}>{item}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-sm text-slate-600">Không có điểm bất đồng đáng kể.</p>
                )}
              </article>
            </div>

            <article className="rounded-md border border-slate-200 bg-white p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Final Recommendation</p>
              <p className="mt-2 whitespace-pre-wrap text-sm text-slate-900">
                {result.finalRecommendation || "Không có khuyến nghị cuối trong phản hồi."}
              </p>
            </article>
          </section>
        ) : null}
      </div>
    </PageShell>
  );
}
