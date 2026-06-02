"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import SelfMedConsentGate from "@/components/selfmed/selfmed-consent-gate";
import { CabinetItem, deleteCabinetItem, getCabinet } from "@/lib/selfmed";

type TimelineEntry = {
  id: number;
  time: string;
  title: string;
  note: string;
};

type MedicationAlert = {
  id: string;
  title: string;
  detail: string;
};

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

function normalizationLabel(source: string | null | undefined): string {
  if (source === "db") return "Khớp chuẩn";
  if (source === "candidate") return "Cần kiểm tra lại";
  if (source === "fallback") return "Nhập thủ công";
  return "Chưa rõ";
}

function normalizationClass(source: string | null | undefined): string {
  if (source === "db") return "border-emerald-300/60 bg-emerald-500/15 text-emerald-100";
  if (source === "candidate") return "border-amber-300/60 bg-amber-500/15 text-amber-100";
  if (source === "fallback") return "border-rose-300/60 bg-rose-500/15 text-rose-100";
  return "border-slate-400/35 bg-slate-500/20 text-slate-100";
}

function formatDate(value: string | null): string {
  if (!value) return "Chưa có";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Chưa có";
  return date.toLocaleDateString("vi-VN");
}

function riskTone(score: number): "low" | "moderate" | "high" {
  if (score >= 70) return "high";
  if (score >= 35) return "moderate";
  return "low";
}

function normalizeText(value: string | null | undefined): string {
  return String(value ?? "").trim().toLowerCase();
}

function buildMedicineText(item: CabinetItem): string {
  return [item.drug_name, item.normalized_name, item.brand_name, item.note].map((value) => normalizeText(value)).join(" ");
}

function includesAny(text: string, tokens: string[]): boolean {
  return tokens.some((token) => text.includes(token));
}

function timelineLabelForItem(item: CabinetItem): string {
  const dosageText = normalizeText(item.dosage);
  const noteText = normalizeText(item.note);
  const fullText = `${dosageText} ${noteText}`;

  if (includesAny(fullText, ["sáng", "morning", "breakfast"])) return "Buổi sáng";
  if (includesAny(fullText, ["trưa", "noon", "lunch"])) return "Buổi trưa";
  if (includesAny(fullText, ["chiều", "afternoon"])) return "Buổi chiều";
  if (includesAny(fullText, ["tối", "đêm", "night", "evening", "bedtime"])) return "Buổi tối";
  return "Theo dõi";
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

    const now = Date.now();
    const in30Days = now + 30 * 24 * 60 * 60 * 1000;

    let expiringSoon = 0;
    let expired = 0;
    let missingDosage = 0;

    items.forEach((item) => {
      if (!String(item.dosage ?? "").trim()) {
        missingDosage += 1;
      }
      if (!item.expires_on) return;
      const expiresAt = Date.parse(item.expires_on);
      if (!Number.isFinite(expiresAt)) return;
      if (expiresAt < now) {
        expired += 1;
      } else if (expiresAt <= in30Days) {
        expiringSoon += 1;
      }
    });

    const computedRisk = Math.min(96, items.length * 12 + expired * 22 + expiringSoon * 10 + missingDosage * 8);

    return {
      total: items.length,
      fromOcr,
      manual,
      expiringSoon,
      expired,
      missingDosage,
      riskScore: computedRisk,
      riskTone: riskTone(computedRisk),
    };
  }, [items]);

  const canCheckInteractions = stats.total >= 2;

  const topItems = useMemo(
    () =>
      [...items]
        .sort((a, b) => Date.parse(b.updated_at || b.created_at) - Date.parse(a.updated_at || a.created_at))
        .slice(0, 6),
    [items]
  );

  const timelineItems = useMemo(
    (): TimelineEntry[] =>
      topItems.slice(0, 3).map((item, idx) => ({
        id: item.id,
        time: idx === 0 ? "Tiếp theo" : timelineLabelForItem(item),
        title: item.drug_name,
        note: item.dosage || "Cần bổ sung liều dùng",
      })),
    [topItems]
  );

  const medicationAlerts = useMemo((): MedicationAlert[] => {
    const alerts: MedicationAlert[] = [];
    if (items.length === 0) return alerts;

    const medicineTexts = items.map((item) => buildMedicineText(item));
    const hasMedicine = (tokens: string[]) => medicineTexts.some((text) => includesAny(text, tokens));

    const hasWarfarin = hasMedicine(["warfarin"]);
    const hasStatin = hasMedicine([
      "atorvastatin",
      "simvastatin",
      "rosuvastatin",
      "pravastatin",
      "lovastatin",
      "fluvastatin",
      "pitavastatin",
      "statin",
    ]);
    const hasNsaid = hasMedicine([
      "ibuprofen",
      "diclofenac",
      "naproxen",
      "ketoprofen",
      "meloxicam",
      "piroxicam",
      "celecoxib",
      "etoricoxib",
      "nsaid",
    ]);

    if (hasWarfarin) {
      alerts.push({
        id: "warfarin-bleeding",
        title: "Chảy máu bất thường",
        detail: "Phát hiện Warfarin trong tủ thuốc. Nếu có chảy máu bất thường, liên hệ bác sĩ ngay.",
      });
    }

    if (hasStatin) {
      alerts.push({
        id: "statin-myalgia",
        title: "Đau cơ dữ dội",
        detail: "Phát hiện thuốc nhóm statin. Theo dõi đau cơ, yếu cơ hoặc nước tiểu sậm màu.",
      });
    }

    if (hasWarfarin && hasNsaid) {
      alerts.push({
        id: "warfarin-nsaid",
        title: "Tăng nguy cơ xuất huyết",
        detail: "Warfarin dùng cùng NSAID có thể làm tăng nguy cơ chảy máu. Cần đánh giá DDI sớm.",
      });
    }

    if (stats.expired > 0) {
      alerts.push({
        id: "expired-medication",
        title: `Có ${stats.expired} thuốc đã hết hạn`,
        detail: "Rà soát và loại bỏ thuốc hết hạn trước khi tiếp tục sử dụng.",
      });
    }

    if (stats.missingDosage > 0) {
      alerts.push({
        id: "missing-dosage",
        title: `Thiếu liều dùng ở ${stats.missingDosage} thuốc`,
        detail: "Bổ sung liều dùng để hệ thống đánh giá tương tác và lịch dùng chính xác hơn.",
      });
    }

    return alerts.slice(0, 4);
  }, [items, stats.expired, stats.missingDosage]);

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
      title="Tủ Thuốc Cá Nhân CLARA"
      description="Lưu danh sách thuốc đang dùng, bổ sung liều nếu có, rồi kiểm tra tương tác khi dùng nhiều thuốc cùng lúc."
      variant="plain"
    >
      <SelfMedConsentGate>
        <div className="space-y-6">
          <section className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <h2 className="text-2xl font-extrabold tracking-tight text-[var(--text-primary)]">{cabinetLabel}</h2>
                <p className="mt-2 text-sm text-[var(--text-secondary)]">
                  Thêm các thuốc bạn đang dùng để CLARA kiểm tra tương tác và nhắc lịch dùng thuốc.
                </p>
              </div>
              <div className="flex flex-col items-start gap-2">
                <div className="flex flex-wrap gap-2">
                  <Link
                    href="/selfmed/add"
                    className="inline-flex min-h-11 items-center rounded-lg bg-gradient-to-br from-cyan-400 to-cyan-600 px-4 text-sm font-bold text-slate-950 shadow-lg shadow-cyan-900/20"
                  >
                    + Thêm thuốc
                  </Link>
                  {canCheckInteractions ? (
                    <Link
                      href="/selfmed/ddi"
                      className="inline-flex min-h-11 items-center rounded-lg border border-cyan-400/60 bg-cyan-500/15 px-4 text-sm font-semibold text-cyan-700 dark:text-cyan-100"
                    >
                      Kiểm tra tương tác thuốc
                    </Link>
                  ) : (
                    <button
                      type="button"
                      disabled
                      title="Cần thêm ít nhất 2 thuốc để kiểm tra tương tác."
                      className="inline-flex min-h-11 cursor-not-allowed items-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 text-sm font-semibold text-[var(--text-muted)]"
                    >
                      Kiểm tra tương tác thuốc
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => void refreshCabinet()}
                    className="inline-flex min-h-11 items-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 text-sm font-semibold text-[var(--text-secondary)]"
                  >
                    Làm mới
                  </button>
                </div>
                {!canCheckInteractions ? (
                  <p className="text-xs text-[var(--text-muted)]">Cần thêm ít nhất 2 thuốc để kiểm tra tương tác.</p>
                ) : null}
              </div>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-4 text-xs uppercase tracking-wider text-[var(--text-muted)]">
              <span className="inline-flex items-center gap-1"><i className="fa fa-lock" aria-hidden="true" /> Có cảnh báo an toàn y tế</span>
              <span className="inline-flex items-center gap-1"><i className="fa fa-database" aria-hidden="true" /> Dữ liệu lưu trên tài khoản</span>
              <span className="inline-flex items-center gap-1"><i className="fa fa-clock-o" aria-hidden="true" /> Có thể cập nhật bất cứ lúc nào</span>
            </div>
          </section>

          <section className="grid grid-cols-12 gap-6">
            <div className="col-span-12 lg:col-span-8 space-y-6">
              <article className="clara-glass-panel rounded-xl border border-[color:var(--shell-border)] p-6">
                <div className="mb-6 flex items-center justify-between">
                  <h3 className="text-sm uppercase tracking-widest text-[var(--text-secondary)]">Mức cần kiểm tra thuốc</h3>
                  <span
                    className={[
                      "rounded-sm border px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest",
                      stats.total === 0
                        ? "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-muted)]"
                        : stats.riskTone === "high"
                          ? "border-red-300/40 bg-red-500/15 text-red-700 dark:text-red-200"
                          : stats.riskTone === "moderate"
                            ? "border-amber-300/40 bg-amber-500/15 text-amber-700 dark:text-amber-200"
                            : "border-emerald-300/40 bg-emerald-500/15 text-emerald-700 dark:text-emerald-200",
                    ].join(" ")}
                  >
                    {stats.total === 0
                      ? "CHƯA CÓ THUỐC"
                      : stats.riskTone === "high"
                        ? "CẢNH BÁO CAO"
                        : stats.riskTone === "moderate"
                          ? "TRUNG BÌNH"
                          : "ỔN ĐỊNH"}
                  </span>
                </div>

                <div className="flex flex-col gap-8 md:flex-row md:items-center">
                  <div className="relative h-28 w-56">
                    <svg viewBox="0 0 220 120" className="h-full w-full" aria-hidden="true">
                      <path
                        d="M20 100 A90 90 0 0 1 200 100"
                        fill="none"
                        stroke="var(--shell-border)"
                        strokeWidth="12"
                        strokeLinecap="round"
                        pathLength={100}
                      />
                      <path
                        d="M20 100 A90 90 0 0 1 200 100"
                        fill="none"
                        stroke="rgb(34 211 238)"
                        strokeWidth="12"
                        strokeLinecap="round"
                        pathLength={100}
                        strokeDasharray={`${Math.max(0, Math.min(100, stats.riskScore))} 100`}
                      />
                    </svg>
                    <div className="absolute inset-0 flex flex-col items-center justify-end pb-2">
                      <span className="text-3xl font-extrabold text-cyan-300">{stats.riskScore}%</span>
                      <span className="text-[10px] uppercase text-[var(--text-muted)]">Điểm cần rà soát</span>
                    </div>
                  </div>

                  <div className="grid flex-1 grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                      <p className="mb-1 text-[10px] uppercase tracking-widest text-[var(--text-muted)]">Dữ liệu để kiểm tra tương tác</p>
                      <p className="text-sm font-medium text-[var(--text-primary)]">
                        {(stats.total ?? 0) < 2 ? "Cần ít nhất 2 thuốc" : `${stats.total} hoạt chất trong tủ`}
                      </p>
                      <div className="mt-2 h-1 w-full rounded-full bg-slate-200 dark:bg-slate-900/40">
                        <div className="h-full rounded-full bg-cyan-500 dark:bg-cyan-300" style={{ width: `${Math.min(100, stats.riskScore)}%` }} />
                      </div>
                    </div>
                    <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                      <p className="mb-1 text-[10px] uppercase tracking-widest text-[var(--text-muted)]">Độ đầy đủ dữ liệu</p>
                      <p className="text-sm font-medium text-[var(--text-primary)]">
                        {stats.missingDosage > 0 ? `${stats.missingDosage} thuốc thiếu liều` : "Đã đủ dữ liệu cơ bản"}
                      </p>
                      <div className="mt-2 h-1 w-full rounded-full bg-slate-200 dark:bg-slate-900/40">
                        <div
                          className="h-full rounded-full bg-cyan-500 dark:bg-cyan-300"
                          style={{ width: `${Math.max(8, Math.min(100, 100 - stats.missingDosage * 12))}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </article>

              <article className="space-y-4">
                <div className="flex items-center justify-between px-1">
                  <h3 className="text-lg font-bold text-[var(--text-primary)]">Danh Sách Thuốc Hiện Tại</h3>
                  <span className="text-xs text-[var(--text-muted)]">{stats.total} hoạt chất đang sử dụng</span>
                </div>

                {isLoading ? <p className="text-sm text-[var(--text-secondary)]">Đang tải tủ thuốc...</p> : null}
                {error ? <p className="text-sm text-red-300">{error}</p> : null}
                {notice ? <p className="text-sm text-emerald-300">{notice}</p> : null}

                {!isLoading && topItems.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-6">
                    <p className="text-base font-medium text-[var(--text-primary)]">Tủ thuốc đang trống.</p>
                    <p className="mt-1 text-sm text-[var(--text-secondary)]">Bắt đầu bằng &quot;Thêm Thuốc Mới&quot; để nhập tay hoặc quét OCR.</p>
                  </div>
                ) : null}

                {topItems.map((item) => (
                  <div
                    key={item.id}
                    className="group overflow-hidden rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] transition hover:border-cyan-400/30"
                  >
                    <div className="flex flex-col gap-4 p-5 md:flex-row md:items-center md:gap-6">
                      <div className="flex h-16 w-16 items-center justify-center rounded-lg bg-[var(--surface-muted)]">
                        <span className="material-symbols-outlined text-cyan-300 text-3xl">medication_liquid</span>
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="mb-1 flex flex-wrap items-center gap-2">
                          <h4 className="truncate text-lg font-bold text-[var(--text-primary)]">{item.drug_name}</h4>
                          <span className={`rounded-sm border px-2 py-0.5 text-[10px] font-bold ${sourceClass(item.source)}`}>
                            {sourceLabel(item.source)}
                          </span>
                          {item.normalization_source ? (
                            <span className={`rounded-sm border px-2 py-0.5 text-[10px] font-bold ${normalizationClass(item.normalization_source)}`}>
                              {normalizationLabel(item.normalization_source)}
                            </span>
                          ) : null}
                        </div>

                        <p className="text-sm text-[var(--text-secondary)]">
                          Liều dùng: {item.dosage || "Chưa có"} · Số lượng: {item.quantity}
                        </p>
                        <p className="mt-1 text-xs text-[var(--text-muted)]">
                          Tên thương mại: {item.brand_name || "Chưa có"} · Hãng: {item.manufacturer || "Chưa có"}
                        </p>

                        <div className="mt-2 flex flex-wrap items-center gap-3 text-[10px] text-[var(--text-muted)]">
                          <span className="inline-flex items-center gap-1">
                            <i className="fa fa-calendar" aria-hidden="true" /> HSD: {formatDate(item.expires_on)}
                          </span>
                          {item.ocr_confidence !== null ? (
                            <span className="inline-flex items-center gap-1 text-emerald-200">
                              <i className="fa fa-check-circle" aria-hidden="true" /> OCR {Math.round(item.ocr_confidence * 100)}%
                            </span>
                          ) : null}
                        </div>
                      </div>

                      <div className="text-right">
                        <p className="mb-1 text-[10px] uppercase tracking-widest text-[var(--text-muted)]">Số lượng</p>
                        <p className="text-xl font-extrabold text-[var(--text-primary)]">{item.quantity}</p>
                        <button
                          type="button"
                          onClick={() => void onDelete(item.id)}
                          className="mt-3 inline-flex min-h-10 items-center rounded-lg border border-red-300/50 bg-red-500/15 px-3 py-1.5 text-xs font-semibold text-red-200 transition hover:bg-red-500/25"
                        >
                          Xóa
                        </button>
                      </div>
                    </div>

                    <div className="border-t border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-5 py-3">
                      <div className="flex flex-wrap items-center gap-4 text-[10px] text-[var(--text-muted)]">
                        <span className="inline-flex items-center gap-1"><i className="fa fa-shield" aria-hidden="true" /> Đã lưu vào tủ thuốc</span>
                        <span className="inline-flex items-center gap-1"><i className="fa fa-history" aria-hidden="true" /> Cập nhật: {formatDate(item.updated_at)}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </article>
            </div>

            <div className="col-span-12 lg:col-span-4 space-y-6">
              <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6">
                <h3 className="mb-6 text-sm uppercase tracking-widest text-[var(--text-secondary)]">Lịch Trình Dùng Thuốc</h3>
                {timelineItems.length > 0 ? (
                  <div className="relative space-y-6 before:absolute before:left-[11px] before:top-2 before:bottom-2 before:w-[1px] before:bg-[color:var(--shell-border)]">
                    {timelineItems.map((entry, idx) => (
                      <div className="relative pl-8" key={entry.id}>
                        <div
                          className={[
                            "absolute top-1 z-10 rounded-full border-2 border-[var(--bg-canvas)]",
                            idx === 0 ? "left-0 w-6 h-6 bg-cyan-400" : "left-[5px] w-[14px] h-[14px] bg-[var(--surface-muted)]",
                          ].join(" ")}
                        />
                        <p className={`mb-1 text-[10px] font-bold uppercase ${idx === 0 ? "text-cyan-300" : "text-[var(--text-muted)]"}`}>{entry.time}</p>
                        <p className="text-sm font-bold text-[var(--text-primary)]">{entry.title}</p>
                        <p className="text-xs text-[var(--text-secondary)]">{entry.note}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-[var(--text-secondary)]">
                    Chưa có dữ liệu lịch trình từ tủ thuốc. Hãy thêm thuốc hoặc cập nhật liều dùng để hệ thống tạo timeline.
                  </p>
                )}
              </article>

              <article className="rounded-xl border border-red-300/30 bg-red-500/10 p-6">
                <div className="mb-4 flex items-center gap-3">
                  <span className="material-symbols-outlined text-red-300">emergency</span>
                  <h3 className="text-sm uppercase tracking-widest text-red-200">Phản Ứng Cần Lưu Ý</h3>
                </div>
                {medicationAlerts.length > 0 ? (
                  <ul className="space-y-3">
                    {medicationAlerts.map((alert) => (
                      <li className="flex items-start gap-2" key={alert.id}>
                        <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-red-300" />
                        <div>
                          <p className="text-xs font-bold text-[var(--text-primary)]">{alert.title}</p>
                          <p className="text-[10px] text-[var(--text-secondary)]">{alert.detail}</p>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-[var(--text-secondary)]">Chưa phát hiện cảnh báo tự động từ dữ liệu tủ thuốc hiện tại.</p>
                )}
                <Link
                  href="/careguard"
                  className="mt-4 inline-flex w-full items-center justify-center rounded-lg border border-red-300/40 py-2 text-[10px] font-bold uppercase tracking-widest text-red-100 hover:bg-red-500/10"
                >
                  Mở kiểm tra tương tác
                </Link>
              </article>

            </div>
          </section>
        </div>
      </SelfMedConsentGate>
    </PageShell>
  );
}
