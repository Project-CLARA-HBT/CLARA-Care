"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import SelfMedConsentGate from "@/components/selfmed/selfmed-consent-gate";
import {
  DdiUserView,
  MINIMUM_DDI_MEDICINES,
  formatCareguardRiskLabel,
  requiresTwoMedicines,
  toCareguardUserMessage,
  toDdiUserView
} from "@/lib/careguard";
import { CabinetItem, getCabinet, runCabinetAutoDdi } from "@/lib/selfmed";
import { trackCareguardDdiChecked, trackCareguardViewed } from "@/lib/analytics/events";

function parseLineList(value: string): string[] {
  return value
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function riskLevel(value: string | null | undefined): "high" | "medium" | "low" | "unknown" {
  const normalized = (value ?? "").toLowerCase();
  if (/critical|severe|contra|major|high|red|danger/.test(normalized)) return "high";
  if (/moderate|medium|amber|intermediate/.test(normalized)) return "medium";
  if (/minor|low|green|safe|none/.test(normalized)) return "low";
  return "unknown";
}

function riskPillClass(value: string | null | undefined): string {
  const level = riskLevel(value);
  if (level === "high") return "border-red-300 bg-red-100 text-red-800 dark:border-red-500/60 dark:bg-red-500/20 dark:text-red-100";
  if (level === "medium") return "border-amber-300 bg-amber-100 text-amber-900 dark:border-amber-400/60 dark:bg-amber-500/20 dark:text-amber-100";
  if (level === "low") return "border-emerald-300 bg-emerald-100 text-emerald-800 dark:border-emerald-400/60 dark:bg-emerald-500/20 dark:text-emerald-100";
  return "border-slate-300 bg-slate-100 text-slate-700 dark:border-slate-500/60 dark:bg-slate-500/20 dark:text-slate-100";
}

function riskPanelClass(value: string | null | undefined): string {
  const level = riskLevel(value);
  if (level === "high") return "border-red-300 bg-red-50/85 dark:border-red-500/55 dark:bg-red-500/10";
  if (level === "medium") return "border-amber-300 bg-amber-50/90 dark:border-amber-400/55 dark:bg-amber-500/10";
  if (level === "low") return "border-emerald-300 bg-emerald-50/90 dark:border-emerald-400/55 dark:bg-emerald-500/10";
  return "border-[color:var(--shell-border)] bg-[var(--surface-muted)]";
}

export default function SelfMedDdiPage() {
  const [items, setItems] = useState<CabinetItem[]>([]);
  const [isLoadingCabinet, setIsLoadingCabinet] = useState(true);
  const [cabinetError, setCabinetError] = useState("");

  const [allergiesInput, setAllergiesInput] = useState("");
  const [result, setResult] = useState<DdiUserView | null>(null);
  const [error, setError] = useState("");
  const [isChecking, setIsChecking] = useState(false);

  // Distinct medicine names drive the two-medicine guard (Requirement 3.5).
  // A drug-drug interaction needs two *different* medicines, so the canonical
  // requiresTwoMedicines helper collapses case-insensitive duplicates.
  const medicineNames = useMemo(() => items.map((item) => item.drug_name), [items]);
  const needsMoreMedicines = useMemo(() => requiresTwoMedicines(medicineNames), [medicineNames]);

  const refreshCabinet = async () => {    setCabinetError("");
    setIsLoadingCabinet(true);
    try {
      const response = await getCabinet();
      setItems(response.items ?? []);
    } catch (cause) {
      setCabinetError(toCareguardUserMessage(cause, "Không thể tải tủ thuốc lúc này. Vui lòng thử lại."));
    } finally {
      setIsLoadingCabinet(false);
    }
  };

  useEffect(() => {
    // Named SelfMed/CareGuard product event (Req 9.1); consent/PII guarded.
    trackCareguardViewed({ surface: "selfmed" });
    void refreshCabinet();
  }, []);

  const onRunDdi = async () => {
    setError("");
    setResult(null);
    // Guard the analysis call: with fewer than two distinct medicines, prompt
    // the End_User to add at least two and do NOT call the DDI analysis
    // (Requirement 3.5).
    if (needsMoreMedicines) {
      setError(`Cần ít nhất ${MINIMUM_DDI_MEDICINES} thuốc trong tủ để kiểm tra tương tác. Vui lòng thêm thuốc.`);
      return;
    }
    setIsChecking(true);
    try {
      const next = await runCabinetAutoDdi({ allergies: parseLineList(allergiesInput) });
      // Render ONLY the End_User projection: risk level, alerts,
      // recommendations, and reference sources. Runtime mode, fallback flags,
      // and source_errors are dropped by toDdiUserView (Req 3.1, 3.6, 4.1).
      const view = toDdiUserView(next);
      setResult(view);
      // Coarse, non-PII aggregate signals only — no drug names (Req 9.1, 9.4).
      trackCareguardDdiChecked({
        riskLevel: view.riskLevel,
        alertCount: view.alerts.length,
        medicineCount: items.length,
        source: "selfmed"
      });
    } catch (cause) {
      setError(
        toCareguardUserMessage(cause, "Không thể hoàn tất phân tích tương tác thuốc. Vui lòng thử lại.")
      );
    } finally {
      setIsChecking(false);
    }
  };

  return (
    <PageShell
      title="Kiểm Tra Tương Tác Thuốc"
      description="Đọc các cặp thuốc cần lưu ý trong tủ thuốc cá nhân và khuyến nghị an toàn tiếp theo."
    >
      <SelfMedConsentGate>
        <div className="space-y-5">
          <section className="chrome-panel rounded-[1.35rem] p-5 sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Mô-đun an toàn thuốc</p>
                <h2 className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">Kiểm tra tương tác trong tủ thuốc</h2>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link
                  href="/selfmed"
                  className="inline-flex min-h-12 items-center rounded-xl border border-blue-200 bg-white px-4 py-2 text-sm font-bold text-slate-700 shadow-sm transition hover:border-blue-400 hover:bg-blue-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:border-sky-500 dark:hover:bg-slate-800"
                >
                  Về tủ thuốc
                </Link>
                <Link
                  href="/selfmed/add"
                  className="inline-flex min-h-12 items-center rounded-xl border border-blue-700 bg-blue-600 px-4 py-2 text-sm font-bold text-white shadow-sm transition hover:bg-blue-700 dark:border-sky-400 dark:bg-sky-500 dark:text-slate-950 dark:hover:bg-sky-400"
                >
                  Thêm thuốc
                </Link>
              </div>
            </div>
          </section>

          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
            <section className="chrome-panel rounded-[1.35rem] p-5 sm:p-6">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-xl font-semibold text-[var(--text-primary)]">Thuốc đang có trong tủ</h3>
                <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1 text-xs text-[var(--text-secondary)]">
                  {items.length} thuốc
                </span>
              </div>

              {isLoadingCabinet ? <p className="mt-3 text-sm text-[var(--text-secondary)]">Đang tải danh mục thuốc...</p> : null}
              {cabinetError ? <p className="mt-3 text-sm text-red-300">{cabinetError}</p> : null}

              {!isLoadingCabinet && !items.length ? (
                <div className="mt-3 rounded-2xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-5">
                  <p className="text-sm text-[var(--text-secondary)]">Tủ thuốc chưa có dữ liệu. Vui lòng thêm thuốc trước khi kiểm tra tương tác.</p>
                </div>
              ) : null}

              {items.length ? (
                <ul className="mt-3 grid gap-2 md:grid-cols-2">
                  {items.map((item) => (
                    <li
                      key={item.id}
                      className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-3"
                    >
                      <p className="text-sm font-semibold text-[var(--text-primary)]">{item.drug_name}</p>
                      <p className="mt-1 text-xs text-[var(--text-secondary)]">{item.dosage || "Chưa có liều"}</p>
                    </li>
                  ))}
                </ul>
              ) : null}
            </section>

            <section className="chrome-panel rounded-[1.35rem] p-5 sm:p-6">
              <h3 className="text-xl font-semibold text-[var(--text-primary)]">Thiết lập kiểm tra</h3>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">Có thể thêm dị ứng để tăng độ chính xác cảnh báo.</p>

              <label className="mt-3 block space-y-1">
                <span className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">Dị ứng (không bắt buộc)</span>
                <textarea
                  value={allergiesInput}
                  onChange={(event) => setAllergiesInput(event.target.value)}
                  placeholder="Mỗi dòng một dị ứng hoặc phân tách bằng dấu phẩy"
                  className="min-h-[140px] w-full rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-3 text-sm text-[var(--text-primary)]"
                />
              </label>

              <button
                type="button"
                onClick={() => void onRunDdi()}
                disabled={isChecking || needsMoreMedicines}
                className="mt-3 inline-flex min-h-12 items-center rounded-xl border border-blue-700 bg-blue-600 px-4 py-2 text-sm font-bold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:border-slate-300 disabled:bg-slate-200 disabled:text-slate-600 disabled:shadow-none dark:border-sky-400 dark:bg-sky-500 dark:text-slate-950 dark:hover:bg-sky-400 dark:disabled:border-slate-700 dark:disabled:bg-slate-800 dark:disabled:text-slate-400"
              >
                {isChecking ? "Đang kiểm tra tương tác..." : "Kiểm tra tương tác thuốc"}
              </button>

              {needsMoreMedicines ? <p className="mt-2 text-xs text-amber-200">Cần ít nhất {MINIMUM_DDI_MEDICINES} thuốc trong tủ để kiểm tra tương tác.</p> : null}
              {error ? <p className="mt-2 text-sm text-red-300">{error}</p> : null}
            </section>
          </div>

          {result ? (
            <section className={`chrome-panel rounded-[1.35rem] border p-5 sm:p-6 ${riskPanelClass(result.riskLevel)}`}>
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-semibold text-[var(--text-primary)]">Kết quả tổng quan</p>
                <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${riskPillClass(result.riskLevel)}`}>
                  Mức rủi ro: {formatCareguardRiskLabel(result.riskLevel)}
                </span>
              </div>

              {result.alerts.length ? (
                <ul className="mt-3 space-y-2">
                  {result.alerts.map((alert, index) => (
                    <li key={`${alert.message}-${index}`} className={`rounded-2xl border p-3 ${riskPanelClass(alert.severity)}`}>
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-semibold text-[var(--text-primary)]">{alert.message}</p>
                        <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${riskPillClass(alert.severity)}`}>
                          {formatCareguardRiskLabel(alert.severity)}
                        </span>
                      </div>
                      {alert.details ? <p className="mt-1 text-xs text-[var(--text-secondary)]">{alert.details}</p> : null}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-3 text-sm text-[var(--text-secondary)]">Chưa ghi nhận cảnh báo tương tác rõ ràng.</p>
              )}

              {result.recommendations.length ? (
                <article className="mt-3 rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4">
                  <p className="text-sm font-semibold text-[var(--text-primary)]">Khuyến nghị</p>
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-[var(--text-secondary)]">
                    {result.recommendations.map((item, index) => (
                      <li key={`${item}-${index}`}>{item}</li>
                    ))}
                  </ul>
                </article>
              ) : null}

              <article className="mt-3 rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4">
                <p className="text-sm font-semibold text-[var(--text-primary)]">Nguồn tham khảo</p>
                {result.sources.length ? (
                  <ul className="mt-1 flex flex-wrap gap-2">
                    {result.sources.map((source, index) => (
                      <li key={`${source.label}-${index}`}>
                        {source.url ? (
                          <a
                            href={source.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1 text-xs font-semibold text-[var(--text-brand)] underline"
                          >
                            {source.label}
                          </a>
                        ) : (
                          <span className="inline-flex items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1 text-xs font-semibold text-[var(--text-secondary)]">
                            {source.label}
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-1 text-sm text-[var(--text-secondary)]">Chưa có dữ liệu nguồn tham khảo.</p>
                )}
              </article>
            </section>
          ) : null}
        </div>
      </SelfMedConsentGate>
    </PageShell>
  );
}
