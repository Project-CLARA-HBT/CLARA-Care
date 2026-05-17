"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import SelfMedConsentGate from "@/components/selfmed/selfmed-consent-gate";
import { CareguardAnalyzeResult, formatCareguardRiskLabel, toCareguardUserMessage } from "@/lib/careguard";
import { CabinetItem, getCabinet, runCabinetAutoDdi } from "@/lib/selfmed";

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
  if (level === "high") return "border-red-300/60 bg-red-500/20 text-red-100";
  if (level === "medium") return "border-amber-300/60 bg-amber-500/20 text-amber-100";
  if (level === "low") return "border-emerald-300/60 bg-emerald-500/20 text-emerald-100";
  return "border-slate-300/50 bg-slate-500/20 text-slate-100";
}

function riskPanelClass(value: string | null | undefined): string {
  const level = riskLevel(value);
  if (level === "high") return "border-red-300/55 bg-red-500/10";
  if (level === "medium") return "border-amber-300/55 bg-amber-500/10";
  if (level === "low") return "border-emerald-300/55 bg-emerald-500/10";
  return "border-[color:var(--shell-border)] bg-[var(--surface-muted)]";
}

export default function SelfMedDdiPage() {
  const [items, setItems] = useState<CabinetItem[]>([]);
  const [isLoadingCabinet, setIsLoadingCabinet] = useState(true);
  const [cabinetError, setCabinetError] = useState("");

  const [allergiesInput, setAllergiesInput] = useState("");
  const [result, setResult] = useState<CareguardAnalyzeResult | null>(null);
  const [error, setError] = useState("");
  const [isChecking, setIsChecking] = useState(false);

  const refreshCabinet = async () => {
    setCabinetError("");
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
    void refreshCabinet();
  }, []);

  const onRunDdi = async () => {
    setError("");
    setResult(null);
    setIsChecking(true);
    try {
      const next = await runCabinetAutoDdi({ allergies: parseLineList(allergiesInput) });
      setResult(next);
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
                  className="inline-flex min-h-12 items-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-2 text-sm font-semibold text-[var(--text-secondary)] transition hover:border-[color:var(--shell-border-strong)]"
                >
                  Về tủ thuốc
                </Link>
                <Link
                  href="/selfmed/add"
                  className="inline-flex min-h-12 items-center rounded-xl border border-cyan-300/55 bg-cyan-500/20 px-4 py-2 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-500/30"
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
                disabled={isChecking || items.length < 2}
                className="mt-3 inline-flex min-h-12 items-center rounded-xl border border-indigo-300/55 bg-indigo-500/20 px-4 py-2 text-sm font-semibold text-indigo-100 transition hover:bg-indigo-500/30 disabled:opacity-60"
              >
                {isChecking ? "Đang kiểm tra tương tác..." : "Kiểm tra tương tác thuốc"}
              </button>

              {items.length < 2 ? <p className="mt-2 text-xs text-amber-200">Cần ít nhất 2 thuốc trong tủ để kiểm tra tương tác.</p> : null}
              {error ? <p className="mt-2 text-sm text-red-300">{error}</p> : null}
            </section>
          </div>

          {result ? (
            <section className={`chrome-panel rounded-[1.35rem] border p-5 sm:p-6 ${riskPanelClass(result.riskTier)}`}>
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-semibold text-[var(--text-primary)]">Kết quả tổng quan</p>
                <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${riskPillClass(result.riskTier)}`}>
                  Mức rủi ro: {formatCareguardRiskLabel(result.riskTier)}
                </span>
              </div>

              {result.ddiAlerts.length ? (
                <ul className="mt-3 space-y-2">
                  {result.ddiAlerts.map((alert, index) => (
                    <li key={`${alert.title}-${index}`} className={`rounded-2xl border p-3 ${riskPanelClass(alert.severity ?? result.riskTier)}`}>
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-semibold text-[var(--text-primary)]">{alert.title}</p>
                        {alert.severity ? (
                          <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${riskPillClass(alert.severity)}`}>
                            {formatCareguardRiskLabel(alert.severity)}
                          </span>
                        ) : null}
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
                {result.attribution?.sources.length ? (
                  <p className="mt-1 text-sm text-[var(--text-secondary)]">
                    {result.attribution.sources.map((source) => source.name).join(", ")}
                  </p>
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
