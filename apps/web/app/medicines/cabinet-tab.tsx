"use client";

import { useEffect, useMemo, useState } from "react";
import Button from "@/components/ui/button";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { SurfaceCard, EmptyState, InlineError } from "@/components/ui/surface";
import SelfMedConsentGate from "@/components/selfmed/selfmed-consent-gate";
import { CabinetItem, deleteCabinetItem, getCabinet } from "@/lib/selfmed";
import { trackCareguardViewed } from "@/lib/analytics/events";

type TimelineEntry = {
  id: number;
  time: string;
  title: string;
  note: string;
};

function sourceLabel(source: string): string {
  if (source === "ocr") return "OCR";
  if (source === "manual") return "Thủ công";
  if (source === "barcode") return "Barcode";
  if (source === "imported") return "Import";
  return source;
}

function sourceTone(source: string): BadgeTone {
  if (source === "ocr") return "brand";
  if (source === "manual") return "neutral";
  if (source === "barcode") return "brand";
  if (source === "imported") return "brand";
  return "neutral";
}

function normalizationLabel(source: string | null | undefined): string {
  if (source === "db" || source === "matched") return "Khớp chuẩn";
  if (source === "candidate") return "Cần kiểm tra lại";
  if (source === "needs_review") return "Cần xem lại";
  if (source === "fallback") return "Nhập thủ công";
  return "Chưa rõ";
}

function normalizationTone(source: string | null | undefined): BadgeTone {
  if (source === "db" || source === "matched") return "ok";
  if (source === "candidate") return "warn";
  if (source === "needs_review") return "danger";
  if (source === "fallback") return "danger";
  return "neutral";
}

function formatDate(value: string | null): string {
  if (!value) return "Chưa có";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Chưa có";
  return date.toLocaleDateString("vi-VN");
}

function normalizeText(value: string | null | undefined): string {
  return String(value ?? "").trim().toLowerCase();
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

export default function MedicinesCabinetTab() {
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

    return {
      total: items.length,
      fromOcr,
      manual,
      expiringSoon,
      expired,
      missingDosage,
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
    // Emit a named SelfMed/CareGuard product event (Req 9.1). The facade
    // suppresses transmission without consent/credentials and strips PII; only
    // the coarse surface label is sent.
    trackCareguardViewed({ surface: "selfmed" });
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
    <SelfMedConsentGate>
      <div className="space-y-6">
        <SurfaceCard className="p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h2 className="text-2xl font-extrabold tracking-tight text-[var(--text-primary)]">{cabinetLabel}</h2>
              <p className="mt-2 text-sm text-[var(--text-secondary)]">
                Thêm các thuốc bạn đang dùng để CLARA kiểm tra tương tác và nhắc lịch dùng thuốc.
              </p>
            </div>
            <div className="flex flex-col items-start gap-2">
              <div className="flex flex-wrap gap-2">
                <Button as="link" href="/selfmed/add" icon="add">
                  Thêm thuốc
                </Button>
                {canCheckInteractions ? (
                  <Button as="link" href="/medicines?tab=safety" variant="secondary">
                    Kiểm tra tương tác thuốc
                  </Button>
                ) : (
                  <Button
                    variant="secondary"
                    disabled
                    title="Cần thêm ít nhất 2 thuốc để kiểm tra tương tác."
                  >
                    Kiểm tra tương tác thuốc
                  </Button>
                )}
                <Button variant="ghost" icon="refresh" onClick={() => void refreshCabinet()}>
                  Làm mới
                </Button>
              </div>
              {!canCheckInteractions ? (
                <p className="text-xs text-[var(--text-muted)]">Cần thêm ít nhất 2 thuốc để kiểm tra tương tác.</p>
              ) : null}
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-4 text-xs uppercase tracking-wider text-[var(--text-muted)]">
            <span className="inline-flex items-center gap-1"><i className="fa fa-lock" aria-hidden="true" /> Kiểm tra an toàn qua nguồn được xác minh</span>
            <span className="inline-flex items-center gap-1"><i className="fa fa-database" aria-hidden="true" /> Dữ liệu lưu trên tài khoản</span>
            <span className="inline-flex items-center gap-1"><i className="fa fa-clock-o" aria-hidden="true" /> Có thể cập nhật bất cứ lúc nào</span>
          </div>
        </SurfaceCard>

        <section className="grid grid-cols-12 gap-6">
          <div className="col-span-12 lg:col-span-8 space-y-6">
            <SurfaceCard className="p-6">
              <div className="mb-6 flex items-center justify-between">
                <h3 className="text-sm uppercase tracking-widest text-[var(--text-secondary)]">Mức sẵn sàng của dữ liệu</h3>
                <Badge tone={stats.total === 0 || stats.missingDosage > 0 ? "warn" : "ok"}>
                  {stats.total === 0 ? "CHƯA CÓ THUỐC" : stats.missingDosage > 0 ? "CẦN BỔ SUNG" : "ĐỦ DỮ LIỆU CƠ BẢN"}
                </Badge>
              </div>

              <p className="mb-5 text-xs leading-5 text-[var(--text-secondary)]">
                Đây là kiểm tra độ đầy đủ và hạn dùng của dữ liệu, không phải điểm rủi ro y khoa.
                Cảnh báo tương tác chỉ xuất hiện sau khi bạn chủ động kiểm tra qua nguồn DrugBank được xác minh.
              </p>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                    <p className="mb-1 text-[10px] uppercase tracking-widest text-[var(--text-muted)]">Dữ liệu để kiểm tra tương tác</p>
                    <p className="text-sm font-medium text-[var(--text-primary)]">
                      {(stats.total ?? 0) < 2 ? "Cần ít nhất 2 thuốc" : `${stats.total} hoạt chất trong tủ`}
                    </p>
                  </div>
                  <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                    <p className="mb-1 text-[10px] uppercase tracking-widest text-[var(--text-muted)]">Độ đầy đủ dữ liệu</p>
                    <p className="text-sm font-medium text-[var(--text-primary)]">
                      {stats.missingDosage > 0 ? `${stats.missingDosage} thuốc thiếu liều` : "Đã đủ dữ liệu cơ bản"}
                    </p>
                  </div>
                  <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                    <p className="mb-1 text-[10px] uppercase tracking-widest text-[var(--text-muted)]">Hạn dùng</p>
                    <p className="text-sm font-medium text-[var(--text-primary)]">
                      {stats.expired > 0 ? `${stats.expired} mục đã hết hạn` : stats.expiringSoon > 0 ? `${stats.expiringSoon} mục sắp hết hạn` : "Chưa có mục quá hạn"}
                    </p>
                  </div>
                  <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                    <p className="mb-1 text-[10px] uppercase tracking-widest text-[var(--text-muted)]">Nguồn nhập</p>
                    <p className="text-sm font-medium text-[var(--text-primary)]">
                      {stats.fromOcr} OCR · {stats.manual} thủ công
                    </p>
                  </div>
              </div>
            </SurfaceCard>

            <article className="space-y-4">
              <div className="flex items-center justify-between px-1">
                <h3 className="text-lg font-bold text-[var(--text-primary)]">Danh Sách Thuốc Hiện Tại</h3>
                <span className="text-xs text-[var(--text-muted)]">{stats.total} hoạt chất đang sử dụng</span>
              </div>

              {isLoading ? <p className="text-sm text-[var(--text-secondary)]">Đang tải tủ thuốc...</p> : null}
              {error ? <InlineError message={error} onRetry={() => void refreshCabinet()} /> : null}
              {notice ? <p className="text-sm font-medium text-[var(--status-ok-text)]">{notice}</p> : null}

              {!isLoading && topItems.length === 0 ? (
                <EmptyState
                  icon="medication"
                  title="Tủ thuốc đang trống."
                  description='Bắt đầu bằng "Thêm Thuốc Mới" để nhập tay hoặc quét OCR.'
                />
              ) : null}

              {topItems.map((item) => (
                <SurfaceCard key={item.id} className="group overflow-hidden" interactive>
                  <div className="flex flex-col gap-4 p-5 md:flex-row md:items-center md:gap-6">
                    <div className="flex h-16 w-16 items-center justify-center rounded-lg bg-[var(--surface-brand-soft)]">
                      <span className="material-symbols-outlined text-[var(--text-brand)] text-3xl">medication_liquid</span>
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="mb-1 flex flex-wrap items-center gap-2">
                        <h4 className="truncate text-lg font-bold text-[var(--text-primary)]">{item.drug_name}</h4>
                        <Badge tone={sourceTone(item.source)}>{sourceLabel(item.source)}</Badge>
                        {(item.normalization_status ?? item.normalization_source) ? (
                          <Badge tone={normalizationTone(item.normalization_status ?? item.normalization_source)}>
                            {normalizationLabel(item.normalization_status ?? item.normalization_source)}
                          </Badge>
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
                          <span className="inline-flex items-center gap-1 font-semibold text-[var(--status-ok-text)]">
                            <i className="fa fa-check-circle" aria-hidden="true" /> OCR {Math.round(item.ocr_confidence * 100)}%
                          </span>
                        ) : null}
                      </div>
                    </div>

                    <div className="text-right">
                      <p className="mb-1 text-[10px] uppercase tracking-widest text-[var(--text-muted)]">Số lượng</p>
                      <p className="text-xl font-extrabold text-[var(--text-primary)]">{item.quantity}</p>
                      <Button
                        variant="danger"
                        size="sm"
                        className="mt-3"
                        onClick={() => void onDelete(item.id)}
                      >
                        Xóa
                      </Button>
                    </div>
                  </div>

                  <div className="border-t border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-5 py-3">
                    <div className="flex flex-wrap items-center gap-4 text-[10px] text-[var(--text-muted)]">
                      <span className="inline-flex items-center gap-1"><i className="fa fa-shield" aria-hidden="true" /> Đã lưu vào tủ thuốc</span>
                      <span className="inline-flex items-center gap-1"><i className="fa fa-history" aria-hidden="true" /> Cập nhật: {formatDate(item.updated_at)}</span>
                    </div>
                  </div>
                </SurfaceCard>
              ))}
            </article>
          </div>

          <div className="col-span-12 lg:col-span-4 space-y-6">
            <SurfaceCard className="p-6">
              <h3 className="mb-6 text-sm uppercase tracking-widest text-[var(--text-secondary)]">Lịch Trình Dùng Thuốc</h3>
              {timelineItems.length > 0 ? (
                <div className="relative space-y-6 before:absolute before:left-[11px] before:top-2 before:bottom-2 before:w-[1px] before:bg-[color:var(--shell-border)]">
                  {timelineItems.map((entry, idx) => (
                    <div className="relative pl-8" key={entry.id}>
                      <div
                        className={[
                          "absolute top-1 z-10 rounded-full border-2 border-[var(--bg-canvas)]",
                          idx === 0 ? "left-0 w-6 h-6 bg-[var(--brand-500)]" : "left-[5px] w-[14px] h-[14px] bg-[var(--surface-muted)]",
                        ].join(" ")}
                      />
                      <p className={`mb-1 text-[10px] font-bold uppercase ${idx === 0 ? "text-[var(--text-brand)]" : "text-[var(--text-muted)]"}`}>{entry.time}</p>
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
            </SurfaceCard>

            <section className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-6">
              <div className="mb-4 flex items-center gap-3">
                <span className="material-symbols-outlined text-[var(--text-brand)]">verified_user</span>
                <h3 className="text-sm font-bold uppercase tracking-widest text-[var(--text-primary)]">Kiểm Tra An Toàn Được Xác Minh</h3>
              </div>
              <p className="text-xs leading-5 text-[var(--text-secondary)]">
                CLARA không suy luận cảnh báo từ tên thuốc trong tủ. Hãy mở kiểm tra tương tác để gửi các thuốc đã chọn
                tới luồng DrugBank/FIDES; nếu nguồn xác minh không sẵn sàng, kết quả sẽ bị chặn an toàn.
              </p>
              {stats.expired > 0 || stats.expiringSoon > 0 || stats.missingDosage > 0 ? (
                <ul className="mt-4 space-y-2 text-xs text-[var(--text-secondary)]">
                  {stats.expired > 0 ? <li>• {stats.expired} mục đã hết hạn trong dữ liệu tủ.</li> : null}
                  {stats.expiringSoon > 0 ? <li>• {stats.expiringSoon} mục sẽ hết hạn trong 30 ngày.</li> : null}
                  {stats.missingDosage > 0 ? <li>• {stats.missingDosage} mục chưa có thông tin liều.</li> : null}
                </ul>
              ) : null}
              <Button as="link" href="/medicines?tab=safety" variant="secondary" block className="mt-4 text-[10px] uppercase tracking-widest">
                Mở kiểm tra tương tác
              </Button>
            </section>

          </div>
        </section>
      </div>
    </SelfMedConsentGate>
  );
}
