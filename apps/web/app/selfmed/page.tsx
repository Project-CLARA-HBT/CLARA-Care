"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import { CareguardAnalyzeResult } from "@/lib/careguard";
import {
  addCabinetItem,
  deleteCabinetItem,
  getCabinet,
  importDetections,
  runCabinetAutoDdi,
  scanReceiptFile,
  scanReceiptText,
  ScanDetection,
  CabinetItem
} from "@/lib/selfmed";

function parseLineList(value: string): string[] {
  return value
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

type RiskLevel = "high" | "medium" | "low" | "unknown";

function riskLevel(value: string | null | undefined): RiskLevel {
  const normalized = (value ?? "").toLowerCase();
  if (/critical|severe|contra|major|high|red|danger/.test(normalized)) return "high";
  if (/moderate|medium|amber|intermediate/.test(normalized)) return "medium";
  if (/minor|low|green|safe|none/.test(normalized)) return "low";
  return "unknown";
}

function riskPillClass(value: string | null | undefined): string {
  const level = riskLevel(value);
  if (level === "high") return "border-red-200 bg-red-50 text-red-700";
  if (level === "medium") return "border-amber-200 bg-amber-50 text-amber-700";
  if (level === "low") return "border-emerald-200 bg-emerald-50 text-emerald-700";
  return "border-slate-200 bg-slate-50 text-slate-700";
}

function riskPanelClass(value: string | null | undefined): string {
  const level = riskLevel(value);
  if (level === "high") return "border-red-200 bg-red-50 text-red-900";
  if (level === "medium") return "border-amber-200 bg-amber-50 text-amber-900";
  if (level === "low") return "border-emerald-200 bg-emerald-50 text-emerald-900";
  return "border-slate-200 bg-slate-50 text-slate-900";
}

function confidencePillClass(confidence: number): string {
  if (confidence >= 0.85) return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (confidence >= 0.6) return "border-amber-200 bg-amber-50 text-amber-700";
  return "border-red-200 bg-red-50 text-red-700";
}

function sourceLabel(source: string): string {
  if (source === "ocr") return "OCR";
  if (source === "manual") return "Nhập tay";
  if (source === "barcode") return "Barcode";
  if (source === "imported") return "Import";
  return source;
}

function sourceClass(source: string): string {
  if (source === "ocr") return "border-sky-200 bg-sky-50 text-sky-700";
  if (source === "manual") return "border-slate-200 bg-slate-100 text-slate-700";
  if (source === "barcode") return "border-violet-200 bg-violet-50 text-violet-700";
  if (source === "imported") return "border-indigo-200 bg-indigo-50 text-indigo-700";
  return "border-slate-200 bg-slate-50 text-slate-700";
}

function noticeClass(message: string): string {
  const value = message.toLowerCase();
  if (value.includes("không thể") || value.includes("lỗi")) return "text-red-700";
  if (value.includes("vui lòng")) return "text-amber-700";
  return "text-slate-700";
}

export default function SelfMedPage() {
  const [cabinetLabel, setCabinetLabel] = useState("Tủ thuốc cá nhân");
  const [items, setItems] = useState<CabinetItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadingError, setLoadingError] = useState("");
  const [cabinetNotice, setCabinetNotice] = useState("");

  const [manualDrugName, setManualDrugName] = useState("");
  const [manualDosage, setManualDosage] = useState("");
  const [manualQuantity, setManualQuantity] = useState("1");
  const [manualNotice, setManualNotice] = useState("");

  const [scanInput, setScanInput] = useState("");
  const [scanDetections, setScanDetections] = useState<ScanDetection[]>([]);
  const [scanNotice, setScanNotice] = useState("");
  const [scanFile, setScanFile] = useState<File | null>(null);
  const [isScanningFile, setIsScanningFile] = useState(false);

  const [allergiesInput, setAllergiesInput] = useState("");
  const [ddiResult, setDdiResult] = useState<CareguardAnalyzeResult | null>(null);
  const [ddiError, setDdiError] = useState("");
  const [isCheckingDdi, setIsCheckingDdi] = useState(false);

  const cabinetStats = useMemo(() => {
    const fromOcr = items.filter((item) => item.source === "ocr").length;
    return { total: items.length, fromOcr };
  }, [items]);

  const stepStatus = useMemo(
    () => [
      {
        id: 1,
        title: "Scan đơn thuốc",
        detail: scanDetections.length ? `${scanDetections.length} thuốc đã nhận diện` : "Chưa quét dữ liệu"
      },
      {
        id: 2,
        title: "Thêm vào tủ thuốc",
        detail: items.length ? `${items.length} thuốc trong tủ` : "Chưa có thuốc trong tủ"
      },
      {
        id: 3,
        title: "Auto DDI",
        detail: ddiResult ? "Đã có kết quả phân tích" : "Chưa chạy DDI"
      }
    ],
    [ddiResult, items.length, scanDetections.length]
  );

  const refreshCabinet = async () => {
    setIsLoading(true);
    setLoadingError("");
    try {
      const response = await getCabinet();
      setCabinetLabel(response.label);
      setItems(response.items);
    } catch (error) {
      setLoadingError(error instanceof Error ? error.message : "Không thể tải tủ thuốc.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void refreshCabinet();
  }, []);

  const onAddManual = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setManualNotice("");
    setCabinetNotice("");
    try {
      const quantity = Number(manualQuantity);
      await addCabinetItem({
        drug_name: manualDrugName.trim(),
        dosage: manualDosage.trim(),
        quantity: Number.isFinite(quantity) ? quantity : 1,
        source: "manual"
      });
      setManualDrugName("");
      setManualDosage("");
      setManualQuantity("1");
      setManualNotice("Đã thêm thuốc vào tủ thuốc.");
      await refreshCabinet();
    } catch (error) {
      setManualNotice(error instanceof Error ? error.message : "Không thể thêm thuốc.");
    }
  };

  const onScanText = async () => {
    setScanNotice("");
    setScanDetections([]);
    try {
      const detections = await scanReceiptText(scanInput.trim());
      setScanDetections(detections);
      if (!detections.length) {
        setScanNotice("Không nhận diện được thuốc từ nội dung OCR.");
      } else {
        setScanNotice(`Nhận diện được ${detections.length} thuốc từ nội dung dán.`);
      }
    } catch (error) {
      setScanNotice(error instanceof Error ? error.message : "Không thể quét nội dung.");
    }
  };

  const onScanFile = async () => {
    if (!scanFile) {
      setScanNotice("Vui lòng chọn file hóa đơn/đơn thuốc trước khi quét.");
      return;
    }
    setScanNotice("");
    setScanDetections([]);
    setIsScanningFile(true);
    try {
      const detections = await scanReceiptFile(scanFile);
      setScanDetections(detections);
      if (!detections.length) {
        setScanNotice("Không nhận diện được thuốc từ file OCR.");
      } else {
        setScanNotice(`Nhận diện được ${detections.length} thuốc từ file OCR.`);
      }
    } catch (error) {
      setScanNotice(error instanceof Error ? error.message : "Không thể quét file OCR.");
    } finally {
      setIsScanningFile(false);
    }
  };

  const onImportDetections = async () => {
    if (!scanDetections.length) return;
    setScanNotice("");
    setCabinetNotice("");
    try {
      const inserted = await importDetections(scanDetections);
      setCabinetNotice(`Đã thêm ${inserted} thuốc vào tủ thuốc từ kết quả scan.`);
      await refreshCabinet();
    } catch (error) {
      setCabinetNotice(error instanceof Error ? error.message : "Không thể nhập dữ liệu OCR.");
    }
  };

  const onDeleteItem = async (itemId: number) => {
    setCabinetNotice("");
    try {
      await deleteCabinetItem(itemId);
      setCabinetNotice("Đã xóa thuốc khỏi tủ.");
      await refreshCabinet();
    } catch (error) {
      setCabinetNotice(error instanceof Error ? error.message : "Không thể xóa thuốc.");
    }
  };

  const onAutoDdiCheck = async () => {
    setIsCheckingDdi(true);
    setDdiError("");
    setDdiResult(null);
    try {
      const result = await runCabinetAutoDdi({
        allergies: parseLineList(allergiesInput)
      });
      setDdiResult(result);
    } catch (error) {
      setDdiError(error instanceof Error ? error.message : "Không thể kiểm tra DDI.");
    } finally {
      setIsCheckingDdi(false);
    }
  };

  return (
    <PageShell title="CLARA Self-Med">
      <div className="space-y-5">
        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Module Self-Med</p>
              <h2 className="text-xl font-semibold text-slate-900">Quản lý thuốc cá nhân theo 3 bước</h2>
              <p className="mt-1 text-sm text-slate-600">Luồng chuẩn: Scan đơn thuốc, thêm vào tủ, sau đó auto kiểm tra tương tác DDI.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <span className="rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-medium text-sky-700">
                Tổng thuốc: {cabinetStats.total}
              </span>
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                Từ OCR: {cabinetStats.fromOcr}
              </span>
            </div>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-3">
            {stepStatus.map((step) => {
              const done = !step.detail.startsWith("Chưa");
              return (
                <article
                  key={step.id}
                  className={`rounded-2xl border px-4 py-3 ${done ? "border-emerald-200 bg-emerald-50" : "border-slate-200 bg-slate-50"}`}
                >
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Bước {step.id}</p>
                  <p className="mt-1 text-sm font-semibold text-slate-900">{step.title}</p>
                  <p className="mt-1 text-xs text-slate-600">{step.detail}</p>
                </article>
              );
            })}
          </div>
        </section>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
          <div className="space-y-5">
            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Bước 1</p>
                  <h3 className="text-lg font-semibold text-slate-900">Scan đơn thuốc hoặc hóa đơn</h3>
                  <p className="text-sm text-slate-600">Quét file ảnh/PDF hoặc dán text OCR để nhận diện tên thuốc.</p>
                </div>
                <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700">
                  Thuốc nhận diện: {scanDetections.length}
                </span>
              </div>

              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                <div className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <label className="text-sm font-medium text-slate-800" htmlFor="scan-file">
                    Tải file đơn thuốc/hóa đơn
                  </label>
                  <input
                    id="scan-file"
                    className="block w-full text-sm text-slate-700 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-200 file:px-3 file:py-2 file:text-sm file:font-medium file:text-slate-700"
                    type="file"
                    accept="image/*,.pdf"
                    onChange={(event) => setScanFile(event.target.files?.[0] ?? null)}
                  />
                  <button
                    className="rounded-xl border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-60"
                    type="button"
                    onClick={onScanFile}
                    disabled={isScanningFile}
                  >
                    {isScanningFile ? "Đang quét file..." : "Quét file OCR"}
                  </button>
                </div>

                <div className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <label className="text-sm font-medium text-slate-800" htmlFor="scan-text">
                    Hoặc dán nội dung OCR
                  </label>
                  <textarea
                    id="scan-text"
                    className="min-h-[120px] w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                    placeholder="Dán nội dung OCR hóa đơn/đơn thuốc..."
                    value={scanInput}
                    onChange={(event) => setScanInput(event.target.value)}
                  />
                  <button
                    className="rounded-xl border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
                    type="button"
                    onClick={onScanText}
                  >
                    Quét nội dung dán tay
                  </button>
                </div>
              </div>

              {scanNotice ? <p className={`mt-3 text-sm ${noticeClass(scanNotice)}`}>{scanNotice}</p> : null}

              {scanDetections.length ? (
                <ul className="mt-3 grid gap-2 md:grid-cols-2">
                  {scanDetections.map((detection) => (
                    <li key={`${detection.normalized_name}-${detection.evidence}`} className="rounded-xl border border-slate-200 bg-white p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-semibold text-slate-900">{detection.drug_name}</p>
                        <span
                          className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${confidencePillClass(detection.confidence)}`}
                        >
                          {Math.round(detection.confidence * 100)}%
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-slate-600">Bằng chứng OCR: {detection.evidence}</p>
                    </li>
                  ))}
                </ul>
              ) : null}
            </section>

            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Bước 2</p>
                <h3 className="text-lg font-semibold text-slate-900">Thêm vào tủ thuốc {cabinetLabel}</h3>
                <p className="text-sm text-slate-600">
                  Nhập nhanh từ kết quả scan hoặc thêm thủ công trước khi chạy kiểm tra tương tác.
                </p>
              </div>

              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-sm font-semibold text-slate-900">Nhập từ kết quả scan</p>
                  <p className="mt-1 text-xs text-slate-600">Hệ thống sẽ thêm toàn bộ thuốc đã nhận diện ở Bước 1 vào tủ thuốc.</p>
                  <button
                    className="mt-3 rounded-xl bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-60"
                    type="button"
                    disabled={!scanDetections.length}
                    onClick={onImportDetections}
                  >
                    Thêm {scanDetections.length} thuốc từ scan
                  </button>
                </article>

                <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-sm font-semibold text-slate-900">Thêm thủ công</p>
                  <form className="mt-3 space-y-3" onSubmit={onAddManual}>
                    <div>
                      <label className="mb-1 block text-xs font-medium text-slate-700" htmlFor="manual-drug">
                        Tên thuốc
                      </label>
                      <input
                        id="manual-drug"
                        className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                        placeholder="Ví dụ: metformin"
                        value={manualDrugName}
                        onChange={(event) => setManualDrugName(event.target.value)}
                        required
                      />
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div>
                        <label className="mb-1 block text-xs font-medium text-slate-700" htmlFor="manual-dose">
                          Liều dùng
                        </label>
                        <input
                          id="manual-dose"
                          className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                          placeholder="Ví dụ: 500mg"
                          value={manualDosage}
                          onChange={(event) => setManualDosage(event.target.value)}
                        />
                      </div>
                      <div>
                        <label className="mb-1 block text-xs font-medium text-slate-700" htmlFor="manual-qty">
                          Số lượng
                        </label>
                        <input
                          id="manual-qty"
                          className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                          placeholder="1"
                          value={manualQuantity}
                          onChange={(event) => setManualQuantity(event.target.value)}
                        />
                      </div>
                    </div>
                    <button className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-700" type="submit">
                      Thêm thủ công vào tủ
                    </button>
                    {manualNotice ? <p className={`text-sm ${noticeClass(manualNotice)}`}>{manualNotice}</p> : null}
                  </form>
                </article>
              </div>
            </section>
          </div>

          <div className="space-y-5">
            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Tủ thuốc</p>
                  <h3 className="text-lg font-semibold text-slate-900">Danh mục thuốc hiện tại</h3>
                </div>
                <button
                  type="button"
                  className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100"
                  onClick={refreshCabinet}
                >
                  Làm mới
                </button>
              </div>

              {isLoading ? <p className="mt-3 text-sm text-slate-600">Đang tải tủ thuốc...</p> : null}
              {loadingError ? <p className="mt-3 text-sm text-red-700">{loadingError}</p> : null}
              {!isLoading && !items.length ? <p className="mt-3 text-sm text-slate-600">Chưa có thuốc nào trong tủ thuốc.</p> : null}

              {items.length ? (
                <ul className="mt-3 space-y-2">
                  {items.map((item) => (
                    <li key={item.id} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="text-sm font-semibold text-slate-900">{item.drug_name}</p>
                          <p className="text-xs text-slate-600">
                            {item.dosage || "Chưa có liều"} | Số lượng: {item.quantity}
                          </p>
                          <div className="mt-1 flex flex-wrap items-center gap-2">
                            <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${sourceClass(item.source)}`}>
                              {sourceLabel(item.source)}
                            </span>
                            {item.ocr_confidence !== null ? (
                              <span
                                className={`rounded-full border px-2 py-0.5 text-xs font-medium ${confidencePillClass(item.ocr_confidence)}`}
                              >
                                OCR {Math.round(item.ocr_confidence * 100)}%
                              </span>
                            ) : null}
                          </div>
                        </div>
                        <button
                          type="button"
                          className="rounded-lg border border-red-200 px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50"
                          onClick={() => onDeleteItem(item.id)}
                        >
                          Xóa
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : null}

              {cabinetNotice ? <p className={`mt-3 text-sm ${noticeClass(cabinetNotice)}`}>{cabinetNotice}</p> : null}
            </section>

            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Bước 3</p>
                <h3 className="text-lg font-semibold text-slate-900">Auto DDI theo toàn bộ tủ thuốc</h3>
                <p className="text-sm text-slate-600">
                  Tự động kiểm tra tương tác thuốc hiện có, hiển thị mức rủi ro theo màu để dễ quyết định.
                </p>
              </div>

              <div className="mt-3 flex flex-wrap gap-2">
                <span className="rounded-full border border-red-200 bg-red-50 px-3 py-1 text-xs font-semibold text-red-700">
                  Nguy cơ cao
                </span>
                <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">
                  Nguy cơ trung bình
                </span>
                <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
                  Nguy cơ thấp
                </span>
              </div>

              <div className="mt-4">
                <label className="mb-1 block text-sm font-medium text-slate-800" htmlFor="allergy-input">
                  Dị ứng (không bắt buộc)
                </label>
                <textarea
                  id="allergy-input"
                  className="min-h-[92px] w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                  placeholder="Mỗi dòng một dị ứng hoặc phân tách bằng dấu phẩy"
                  value={allergiesInput}
                  onChange={(event) => setAllergiesInput(event.target.value)}
                />
              </div>

              <button
                className="mt-3 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60"
                type="button"
                onClick={onAutoDdiCheck}
                disabled={isCheckingDdi || items.length === 0}
              >
                {isCheckingDdi ? "Đang phân tích..." : "Chạy auto DDI"}
              </button>

              {items.length === 0 ? <p className="mt-2 text-xs text-amber-700">Cần ít nhất 1 thuốc trong tủ để phân tích DDI.</p> : null}
              {ddiError ? <p className="mt-3 text-sm text-red-700">{ddiError}</p> : null}

              {ddiResult ? (
                <div className="mt-4 space-y-3">
                  <article className={`rounded-2xl border p-4 ${riskPanelClass(ddiResult.riskTier)}`}>
                    <p className="text-xs font-semibold uppercase tracking-wide">Kết quả tổng quan</p>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${riskPillClass(ddiResult.riskTier)}`}>
                        Mức rủi ro: {ddiResult.riskTier ?? "Chưa xác định"}
                      </span>
                    </div>
                    <p className="mt-2 text-sm">
                      {ddiResult.ddiAlerts.length
                        ? `Phát hiện ${ddiResult.ddiAlerts.length} cảnh báo tương tác cần lưu ý.`
                        : "Chưa ghi nhận cảnh báo tương tác rõ ràng."}
                    </p>
                  </article>

                  {ddiResult.ddiAlerts.length ? (
                    <ul className="space-y-2">
                      {ddiResult.ddiAlerts.map((alert, index) => (
                        <li key={`${alert.title}-${index}`} className={`rounded-xl border p-3 ${riskPanelClass(alert.severity ?? ddiResult.riskTier)}`}>
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <p className="text-sm font-semibold">{alert.title}</p>
                            {alert.severity ? (
                              <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${riskPillClass(alert.severity)}`}>
                                {alert.severity}
                              </span>
                            ) : null}
                          </div>
                          {alert.details ? <p className="mt-1 text-xs opacity-90">{alert.details}</p> : null}
                        </li>
                      ))}
                    </ul>
                  ) : null}

                  {ddiResult.recommendations.length ? (
                    <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                      <p className="text-sm font-semibold text-slate-900">Khuyến nghị</p>
                      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
                        {ddiResult.recommendations.map((item, index) => (
                          <li key={`${item}-${index}`}>{item}</li>
                        ))}
                      </ul>
                    </article>
                  ) : null}
                </div>
              ) : null}
            </section>
          </div>
        </div>
      </div>
    </PageShell>
  );
}
