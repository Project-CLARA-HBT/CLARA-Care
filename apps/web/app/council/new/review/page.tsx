"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import CouncilWorkspaceNav from "@/components/council/council-workspace-nav";
import PageShell from "@/components/ui/page-shell";
import { trackCouncilRun } from "@/lib/analytics/events";
import {
  CouncilCaseRecord,
  getActiveCouncilCaseId,
  getCouncilCase,
  runCouncilCaseById,
  setActiveCouncilCaseId,
} from "@/lib/council";

function parseRequest(caseItem: CouncilCaseRecord | null) {
  const request = (caseItem?.request ?? {}) as Record<string, unknown>;
  const symptoms = Array.isArray(request.symptoms) ? request.symptoms.map((item) => String(item).trim()).filter(Boolean) : [];
  const labs =
    request.labs && typeof request.labs === "object" && !Array.isArray(request.labs)
      ? (request.labs as Record<string, unknown>)
      : {};
  const medications = Array.isArray(request.medications)
    ? request.medications.map((item) => String(item).trim()).filter(Boolean)
    : [];
  const history = typeof request.history === "string" ? request.history.trim() : "";
  const specialistCount = Number(request.specialist_count ?? 3);
  const specialists = Array.isArray(request.specialists)
    ? request.specialists.map((item) => String(item)).filter(Boolean)
    : [];

  return {
    symptoms,
    labs,
    medications,
    history,
    specialistCount: Number.isFinite(specialistCount) ? Math.trunc(specialistCount) : 3,
    specialists,
  };
}

export default function CouncilNewReviewPage() {
  const router = useRouter();
  const [queryCaseId, setQueryCaseId] = useState<number | null>(null);
  const [caseItem, setCaseItem] = useState<CouncilCaseRecord | null>(null);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

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
        const resolvedCaseId = queryCaseId;
        if (!resolvedCaseId) {
          router.replace("/council/new");
          return;
        }
        const loaded = await getCouncilCase(resolvedCaseId);
        setActiveCouncilCaseId(loaded.id);
        setCaseItem(loaded);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Không thể tải case review.");
      }
    };
    if (queryCaseId !== null) {
      void bootstrap();
    }
  }, [queryCaseId, router]);

  const parsedCase = useMemo(() => parseRequest(caseItem), [caseItem]);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!caseItem) return;

    if (
      parsedCase.symptoms.length === 0 &&
      Object.keys(parsedCase.labs).length === 0 &&
      parsedCase.medications.length === 0 &&
      !parsedCase.history
    ) {
      setError("Vui lòng nhập dữ liệu ca bệnh trước khi chạy hội chẩn.");
      return;
    }

    if (parsedCase.specialists.length < 2) {
      setError("Vui lòng chọn tối thiểu 2 chuyên khoa.");
      return;
    }

    setError("");
    setIsSubmitting(true);

    try {
      const updated = await runCouncilCaseById(caseItem.id, {
        request: caseItem.request ?? undefined,
        specialist_count: parsedCase.specialistCount,
        specialists: parsedCase.specialists,
      });
      // Emit a named Council product event through the consent/PII-guarded
      // analytics client. Only the coarse specialist count is recorded; no
      // case/patient content is included (Req 9.1, 9.4).
      trackCouncilRun({ specialistCount: parsedCase.specialists.length });
      setActiveCouncilCaseId(updated.id);
      router.push(`/council/result?caseId=${updated.id}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể chạy hội chẩn lúc này.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <PageShell
      title="Council Wizard - Review"
      description="Bước 3/3: kiểm tra cấu hình case rồi chạy hội chẩn."
      variant="plain"
    >
      <div className="space-y-5">
        <CouncilWorkspaceNav />

        <form onSubmit={onSubmit} className="space-y-5">
          <section className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
              Step 3/3 · Case #{caseItem?.id ?? "--"}
            </p>
            <h2 className="mt-2 text-xl font-semibold text-[var(--text-primary)]">Review trước khi chạy</h2>

            <ul className="mt-4 grid gap-2 text-sm text-[var(--text-secondary)] sm:grid-cols-2">
              <li>Triệu chứng: {parsedCase.symptoms.length}</li>
              <li>Xét nghiệm: {Object.keys(parsedCase.labs).length}</li>
              <li>Thuốc: {parsedCase.medications.length}</li>
              <li>Bệnh sử: {parsedCase.history ? "Đã có" : "Chưa có"}</li>
              <li className="sm:col-span-2">
                Chuyên khoa: {parsedCase.specialists.length}/{parsedCase.specialistCount} ({parsedCase.specialists.join(", ") || "chưa chọn"})
              </li>
            </ul>
          </section>

          {error ? <p className="text-sm text-red-400">{error}</p> : null}

          <div className="flex flex-wrap justify-between gap-2">
            <Link
              href={caseItem ? `/council/new/specialists?caseId=${caseItem.id}` : "/council/new/specialists"}
              className="inline-flex min-h-[42px] items-center rounded-lg border border-[color:var(--shell-border)] px-4 text-sm font-semibold"
            >
              Quay lại bước 2
            </Link>

            <button
              type="submit"
              disabled={isSubmitting || !caseItem}
              className="inline-flex min-h-[44px] items-center rounded-lg border border-cyan-300/65 bg-gradient-to-r from-sky-600 to-cyan-500 px-4 text-sm font-semibold text-white disabled:opacity-60"
            >
              {isSubmitting ? "Đang chạy hội chẩn..." : "Chạy hội chẩn AI"}
            </button>
          </div>
        </form>
      </div>
    </PageShell>
  );
}
