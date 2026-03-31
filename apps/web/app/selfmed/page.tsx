"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import SelfMedConsentGate from "@/components/selfmed/selfmed-consent-gate";
import { CabinetItem, deleteCabinetItem, getCabinet } from "@/lib/selfmed";

function sourceLabel(source: string): string {
  if (source === "ocr") return "OCR";
  if (source === "manual") return "Thủ công";
  if (source === "barcode") return "Barcode";
  if (source === "imported") return "Import";
  return source;
}

function sourceClass(source: string): string {
  if (source === "ocr") return "border-cyan-300/60 bg-cyan-500/15 text-cyan-100";
  if (source === "manual") return "border-slate-400/40 bg-slate-500/20 text-slate-100";
  if (source === "barcode") return "border-indigo-300/55 bg-indigo-500/20 text-indigo-100";
  if (source === "imported") return "border-sky-300/55 bg-sky-500/20 text-sky-100";
  return "border-slate-400/35 bg-slate-500/20 text-slate-100";
}

export default function SelfMedPage() {
  const [cabinetLabel, setCabinetLabel] = useState("Tủ thuốc cá nhân");
  const [items, setItems] = useState<CabinetItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const stats = useMemo(() => {
    const fromOcr = items.filter((item) => item.source === "ocr").length;
    const manual = items.filter((item) => item.source === "manual").length;
    return {
      total: items.length,
      fromOcr,
      manual
    };
  }, [items]);

  const refreshCabinet = async () => {
    setError("");
    setIsLoading(true);
    try {
      const response = await getCabinet();
      setCabinetLabel(response.label || "Tủ thuốc cá nhân");
      setItems(response.items ?? []);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tải tủ thuốc.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void refreshCabinet();
  }, []);

  const onDelete = async (itemId: number) => {
    setNotice("");
    setError("");
    try {
      await deleteCabinetItem(itemId);
      setNotice("Đã xóa thuốc khỏi tủ.");
      await refreshCabinet();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể xóa thuốc.");
    }
  };

  return (
    <PageShell
      title="CLARA Self-Med"
      description="Quản lý tủ thuốc cá nhân theo luồng rõ ràng: xem tủ thuốc, thêm thuốc, rồi kiểm tra DDI."
    >
      <SelfMedConsentGate>
        <div className="space-y-5">
          <section className="chrome-panel rounded-[1.35rem] p-5 sm:p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Tủ thuốc cá nhân</p>
                <h2 className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">{cabinetLabel}</h2>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--text-secondary)]">
                  Mỗi màn hình chỉ xử lý một nhiệm vụ để tránh rối: thêm thuốc ở trang riêng, DDI ở trang riêng.
                </p>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--text-secondary)]">
                  Dữ liệu ở đây và tại <Link href="/careguard" className="font-semibold text-cyan-300 underline underline-offset-2">/careguard</Link> dùng chung một backend truth, không dùng localStorage làm nguồn chính.
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                <Link
                  href="/selfmed/add"
                  className="inline-flex min-h-12 items-center rounded-xl border border-cyan-300/55 bg-cyan-500/20 px-4 py-2 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-500/30"
                >
                  + Thêm thuốc
                </Link>
                <Link
                  href="/selfmed/ddi"
                  className="inline-flex min-h-12 items-center rounded-xl border border-indigo-300/55 bg-indigo-500/20 px-4 py-2 text-sm font-semibold text-indigo-100 transition hover:bg-indigo-500/30"
                >
                  Chạy DDI
                </Link>
                <button
                  type="button"
                  onClick={() => void refreshCabinet()}
                  className="inline-flex min-h-12 items-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-2 text-sm font-semibold text-[var(--text-secondary)] transition hover:border-[color:var(--shell-border-strong)]"
                >
                  Làm mới
                </button>
              </div>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4">
                <p className="text-xs uppercase tracking-[0.14em] text-[var(--text-muted)]">Tổng thuốc</p>
                <p className="mt-2 text-3xl font-semibold text-[var(--text-primary)]">{stats.total}</p>
              </article>
              <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4">
                <p className="text-xs uppercase tracking-[0.14em] text-[var(--text-muted)]">Từ OCR</p>
                <p className="mt-2 text-3xl font-semibold text-[var(--text-primary)]">{stats.fromOcr}</p>
              </article>
              <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4">
                <p className="text-xs uppercase tracking-[0.14em] text-[var(--text-muted)]">Thêm tay</p>
                <p className="mt-2 text-3xl font-semibold text-[var(--text-primary)]">{stats.manual}</p>
              </article>
            </div>
          </section>

          <section className="chrome-panel rounded-[1.35rem] p-5 sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-xl font-semibold text-[var(--text-primary)]">Danh sách thuốc hiện tại</h3>
              <p className="text-sm text-[var(--text-muted)]">Nhấn xóa để loại khỏi tủ thuốc</p>
            </div>

            {isLoading ? <p className="mt-4 text-sm text-[var(--text-secondary)]">Đang tải tủ thuốc...</p> : null}
            {error ? <p className="mt-4 text-sm text-red-300">{error}</p> : null}
            {notice ? <p className="mt-4 text-sm text-emerald-300">{notice}</p> : null}

            {!isLoading && !items.length ? (
              <div className="mt-4 rounded-2xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-6">
                <p className="text-base font-medium text-[var(--text-primary)]">Tủ thuốc đang trống</p>
                <p className="mt-1 text-sm text-[var(--text-secondary)]">Bắt đầu bằng nút &quot;Thêm thuốc&quot; để scan OCR hoặc nhập thủ công.</p>
              </div>
            ) : null}

            {items.length ? (
              <ul className="mt-4 grid gap-3 lg:grid-cols-2">
                {items.map((item) => (
                  <li
                    key={item.id}
                    className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-base font-semibold text-[var(--text-primary)]">{item.drug_name}</p>
                        <p className="mt-1 text-sm text-[var(--text-secondary)]">
                          {item.dosage || "Chưa có liều dùng"} · Số lượng: {item.quantity}
                        </p>
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${sourceClass(item.source)}`}>
                            {sourceLabel(item.source)}
                          </span>
                          {item.ocr_confidence !== null ? (
                            <span className="rounded-full border border-emerald-300/60 bg-emerald-500/15 px-2.5 py-1 text-xs font-semibold text-emerald-200">
                              OCR {Math.round(item.ocr_confidence * 100)}%
                            </span>
                          ) : null}
                        </div>
                      </div>

                      <button
                        type="button"
                        onClick={() => void onDelete(item.id)}
                        className="inline-flex min-h-11 items-center rounded-xl border border-red-300/55 bg-red-500/15 px-3 py-1.5 text-xs font-semibold text-red-200 transition hover:bg-red-500/25"
                      >
                        Xóa
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            ) : null}
          </section>
        </div>
      </SelfMedConsentGate>
    </PageShell>
  );
}
