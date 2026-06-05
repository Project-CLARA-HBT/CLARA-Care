"use client";

import Link from "next/link";
import { DragEvent, FormEvent, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import SelfMedConsentGate from "@/components/selfmed/selfmed-consent-gate";
import {
  AddCabinetItemPayload,
  ScanDetection,
  addCabinetItem,
  importDetections,
  isLowConfidenceDetection,
  scanReceiptFile,
  scanReceiptText
} from "@/lib/selfmed";

function confidenceClass(value: number): string {
  if (value >= 0.85) return "border-emerald-300 bg-emerald-50 text-emerald-800";
  if (value >= 0.6) return "border-amber-300 bg-amber-50 text-amber-800";
  return "border-red-300 bg-red-50 text-red-800";
}

function getDetectionKey(item: ScanDetection, index: number): string {
  return `${item.normalized_name}-${item.evidence}-${index}`;
}

function normalizationLabel(source: string | null | undefined): string {
  if (source === "db") return "Khớp chuẩn";
  if (source === "candidate") return "Cần kiểm tra lại";
  if (source === "fallback") return "Độ khớp tay: thấp";
  return "Chưa rõ";
}

function normalizationClass(source: string | null | undefined): string {
  if (source === "db") return "border-emerald-300 bg-emerald-50 text-emerald-800";
  if (source === "candidate") return "border-amber-300 bg-amber-50 text-amber-800";
  if (source === "fallback") return "border-rose-300 bg-rose-50 text-rose-800";
  return "border-slate-300 bg-slate-50 text-slate-700";
}

const cardClass = "rounded-[1.35rem] border border-[#B6D4FE] bg-white p-5 shadow-sm sm:p-6";
const fieldLabelClass = "text-sm font-semibold text-[#1F2937]";
const fieldOptionalLabelClass = "text-sm font-semibold text-[#4B5563]";
const inputClass =
  "h-14 w-full rounded-2xl border border-[#93C5FD] bg-[#F8FBFF] px-4 text-base text-[#1F2937] placeholder:text-[#6B7280] placeholder:font-medium outline-none transition focus:border-[#2563EB] focus:bg-white focus:ring-4 focus:ring-blue-100";
const textareaClass =
  "min-h-[220px] w-full rounded-2xl border border-[#93C5FD] bg-[#F8FBFF] px-4 py-4 text-base leading-7 text-[#1F2937] placeholder:text-[#6B7280] placeholder:font-medium outline-none transition focus:border-[#2563EB] focus:bg-white focus:ring-4 focus:ring-blue-100";
const primaryButtonClass =
  "inline-flex min-h-12 items-center justify-center rounded-xl border border-[#2563EB] bg-[#2563EB] px-5 py-2 text-sm font-bold text-white shadow-sm transition hover:bg-[#1D4ED8] disabled:cursor-not-allowed disabled:border-[#93C5FD] disabled:bg-[#DBEAFE] disabled:text-[#1F2937] disabled:shadow-none";
const secondaryButtonClass =
  "inline-flex min-h-12 items-center justify-center rounded-xl border border-[#93C5FD] bg-white px-5 py-2 text-sm font-bold text-[#1F2937] transition hover:bg-[#EEF6FF]";
const warningButtonClass =
  "inline-flex min-h-12 items-center justify-center rounded-xl border border-amber-300 bg-amber-50 px-5 py-2 text-sm font-bold text-amber-800 transition hover:bg-amber-100 disabled:cursor-not-allowed disabled:bg-amber-50 disabled:text-amber-700";
const helperTextClass = "mt-2 text-sm font-medium text-[#4B5563]";

export default function SelfMedAddPage() {
  const [scanFile, setScanFile] = useState<File | null>(null);
  const [scanText, setScanText] = useState("");
  const [detections, setDetections] = useState<ScanDetection[]>([]);
  const [selectedKeys, setSelectedKeys] = useState<Record<string, boolean>>({});
  const [confirmedLowConfidenceKeys, setConfirmedLowConfidenceKeys] = useState<Record<string, boolean>>({});
  const [scanNotice, setScanNotice] = useState("");
  const [isScanningFile, setIsScanningFile] = useState(false);
  const [isScanningText, setIsScanningText] = useState(false);
  const [isImporting, setIsImporting] = useState(false);

  const [manualDrugName, setManualDrugName] = useState("");
  const [manualBrandName, setManualBrandName] = useState("");
  const [manualManufacturer, setManualManufacturer] = useState("");
  const [manualDosage, setManualDosage] = useState("");
  const [manualQuantity, setManualQuantity] = useState("1");
  const [manualNotice, setManualNotice] = useState("");
  const [isAddingManual, setIsAddingManual] = useState(false);

  const selectedDetections = useMemo(
    () => detections.filter((item, index) => selectedKeys[getDetectionKey(item, index)]),
    [detections, selectedKeys]
  );

  const pendingLowConfidenceSelections = useMemo(() => {
    return detections.filter((item, index) => {
      if (!isLowConfidenceDetection(item)) return false;
      const key = getDetectionKey(item, index);
      return Boolean(selectedKeys[key]) && !confirmedLowConfidenceKeys[key];
    });
  }, [confirmedLowConfidenceKeys, detections, selectedKeys]);

  const lowConfidenceTotal = useMemo(
    () => detections.filter((item) => isLowConfidenceDetection(item)).length,
    [detections]
  );
  const selectedLowConfidenceTotal = useMemo(
    () => selectedDetections.filter((item) => isLowConfidenceDetection(item)).length,
    [selectedDetections]
  );
  const canScanFile = Boolean(scanFile) && !isScanningFile;
  const canScanText = Boolean(scanText.trim()) && !isScanningText;
  const canImportSelected =
    selectedDetections.length > 0 && pendingLowConfidenceSelections.length === 0 && !isImporting;
  const canAddManual =
    Boolean(manualDrugName.trim()) && Boolean(manualDosage.trim()) && !isAddingManual;
  const parsedQuantity = Math.max(1, Number.isFinite(Number(manualQuantity)) ? Math.floor(Number(manualQuantity)) : 1);
  const stepItems = [
    {
      title: "Upload đơn thuốc",
      status: scanFile ? "Đã chọn file" : "Chưa hoàn thành",
      completed: Boolean(scanFile),
      active: !scanFile,
      optional: false
    },
    {
      title: "Dán nội dung OCR",
      status: detections.length ? "Đã có dữ liệu OCR" : scanText.trim() ? "Đang nhập nội dung" : "Chưa có dữ liệu",
      completed: detections.length > 0,
      active: Boolean(scanFile || scanText.trim()) && detections.length === 0,
      optional: false
    },
    {
      title: "Thêm thủ công",
      status: "Dùng nếu OCR chưa đúng",
      completed: false,
      active: Boolean(manualDrugName.trim() || manualDosage.trim()),
      optional: true
    }
  ];

  const resetSelection = (items: ScanDetection[]) => {
    const nextSelected: Record<string, boolean> = {};
    const nextConfirmed: Record<string, boolean> = {};
    items.forEach((item, index) => {
      const key = getDetectionKey(item, index);
      if (isLowConfidenceDetection(item)) {
        nextSelected[key] = false;
        nextConfirmed[key] = false;
      } else {
        nextSelected[key] = true;
        nextConfirmed[key] = true;
      }
    });
    setSelectedKeys(nextSelected);
    setConfirmedLowConfidenceKeys(nextConfirmed);
  };

  const onScanFile = async () => {
    if (!scanFile) {
      setScanNotice("Vui lòng chọn file ảnh/PDF đơn thuốc trước khi quét.");
      return;
    }

    setIsScanningFile(true);
    setScanNotice("");
    try {
      const found = await scanReceiptFile(scanFile);
      setDetections(found);
      resetSelection(found);
      setScanNotice(found.length ? `Nhận diện được ${found.length} thuốc từ file.` : "Không nhận diện được thuốc từ file.");
    } catch (cause) {
      setScanNotice(cause instanceof Error ? cause.message : "Không thể nhận diện thuốc từ file.");
    } finally {
      setIsScanningFile(false);
    }
  };

  const onDropScanFile = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const file = event.dataTransfer.files?.[0] ?? null;
    if (file) {
      setScanFile(file);
    }
  };

  const onScanText = async () => {
    const text = scanText.trim();
    if (!text) {
      setScanNotice("Vui lòng dán hoặc nhập nội dung thuốc trước khi nhận diện.");
      return;
    }

    setIsScanningText(true);
    setScanNotice("");
    try {
      const found = await scanReceiptText(text);
      setDetections(found);
      resetSelection(found);
      setScanNotice(found.length ? `Nhận diện được ${found.length} thuốc từ nội dung đã dán.` : "Không nhận diện được thuốc từ nội dung đã dán.");
    } catch (cause) {
      setScanNotice(cause instanceof Error ? cause.message : "Không thể nhận diện thuốc từ nội dung đã dán.");
    } finally {
      setIsScanningText(false);
    }
  };

  const onImportSelected = async () => {
    if (!selectedDetections.length) return;
    if (pendingLowConfidenceSelections.length) {
      setScanNotice("Cần xác nhận các thuốc nhận diện chưa chắc chắn trước khi nhập.");
      return;
    }
    setIsImporting(true);
    setScanNotice("");
    try {
      const inserted = await importDetections(selectedDetections);
      setScanNotice(`Đã thêm ${inserted} thuốc vào tủ thuốc.`);
    } catch (cause) {
      setScanNotice(cause instanceof Error ? cause.message : "Không thể nhập dữ liệu vào tủ thuốc.");
    } finally {
      setIsImporting(false);
    }
  };

  const onToggleDetection = (key: string) => {
    setSelectedKeys((current) => ({ ...current, [key]: !current[key] }));
  };

  const onToggleLowConfidenceConfirm = (key: string) => {
    setConfirmedLowConfidenceKeys((current) => ({ ...current, [key]: !current[key] }));
  };

  const onSelectAllDetections = (selected: boolean) => {
    if (!detections.length) return;
    const nextSelected: Record<string, boolean> = {};
    detections.forEach((item, index) => {
      const key = getDetectionKey(item, index);
      nextSelected[key] = selected;
    });
    setSelectedKeys(nextSelected);
  };

  const onConfirmAllLowConfidence = (confirmed: boolean) => {
    if (!detections.length) return;
    const nextConfirmed = { ...confirmedLowConfidenceKeys };
    detections.forEach((item, index) => {
      if (!isLowConfidenceDetection(item)) return;
      const key = getDetectionKey(item, index);
      if (selectedKeys[key]) {
        nextConfirmed[key] = confirmed;
      }
    });
    setConfirmedLowConfidenceKeys(nextConfirmed);
  };

  const onAddManual = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setManualNotice("");
    if (!manualDrugName.trim() || !manualDosage.trim()) {
      setManualNotice("Nhập ít nhất tên thuốc và liều dùng để thêm vào tủ.");
      return;
    }
    setIsAddingManual(true);

    const payload: AddCabinetItemPayload = {
      drug_name: manualDrugName.trim(),
      brand_name: manualBrandName.trim(),
      manufacturer: manualManufacturer.trim(),
      dosage: manualDosage.trim(),
      quantity: parsedQuantity,
      source: "manual"
    };

    try {
      await addCabinetItem(payload);
      setManualDrugName("");
      setManualBrandName("");
      setManualManufacturer("");
      setManualDosage("");
      setManualQuantity("1");
      setManualNotice("Đã thêm thuốc thủ công vào tủ thuốc.");
    } catch (cause) {
      setManualNotice(cause instanceof Error ? cause.message : "Không thể thêm thuốc thủ công.");
    } finally {
      setIsAddingManual(false);
    }
  };

  const adjustManualQuantity = (delta: number) => {
    setManualQuantity((current) => String(Math.max(1, Math.floor(Number(current) || 1) + delta)));
  };

  return (
    <PageShell
      title="Thêm Thuốc"
      description="Tải ảnh đơn thuốc, dán nội dung thuốc hoặc nhập thủ công từng thuốc vào tủ thuốc cá nhân."
    >
      <SelfMedConsentGate>
        <div className="space-y-5">
          <section className="grid gap-3 md:grid-cols-3">
            {stepItems.map((step, index) => (
              <article
                key={step.title}
                className={[
                  "rounded-2xl border p-4 transition",
                  step.active
                    ? "border-[#2563EB] bg-[#EEF6FF] shadow-sm"
                    : step.completed
                      ? "border-emerald-300 bg-emerald-50"
                      : "border-[#B6D4FE] bg-white",
                ].join(" ")}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[0.12em] text-[#4B5563]">Bước {index + 1}</p>
                    <h2 className="mt-1 text-base font-bold text-[#1F2937]">{step.title}</h2>
                  </div>
                  <span
                    className={[
                      "inline-flex h-7 min-w-7 items-center justify-center rounded-full border px-2 text-xs font-bold",
                      step.completed
                        ? "border-emerald-300 bg-emerald-100 text-emerald-800"
                        : step.active
                          ? "border-[#2563EB] bg-white text-[#2563EB]"
                          : "border-[#B6D4FE] bg-[#F8FBFF] text-[#4B5563]",
                    ].join(" ")}
                  >
                    {step.completed ? <span className="material-symbols-outlined text-[16px]">check</span> : step.optional ? "Tùy chọn" : index + 1}
                  </span>
                </div>
                <p className="mt-2 text-sm font-medium text-[#4B5563]">{step.status}</p>
              </article>
            ))}
          </section>

          <section className={cardClass}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#4B5563]">Bước 1</p>
                <h2 className="mt-2 text-2xl font-bold text-[#1F2937]">Tải ảnh đơn thuốc / hóa đơn</h2>
                <p className="mt-2 text-base font-medium text-[#4B5563]">Kéo thả ảnh/PDF đơn thuốc vào đây hoặc bấm Chọn file.</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link
                  href="/selfmed"
                  className={secondaryButtonClass}
                >
                  Quay lại tủ thuốc
                </Link>
                <Link
                  href="/selfmed/ddi"
                  className={secondaryButtonClass}
                >
                  Sang kiểm tra tương tác
                </Link>
              </div>
            </div>

            <div
              onDrop={onDropScanFile}
              onDragOver={(event) => event.preventDefault()}
              className="mt-5 rounded-[1.4rem] border-2 border-dashed border-[#93C5FD] bg-[#EEF6FF] p-6 sm:p-8"
            >
              <input
                id="scan-file-input"
                type="file"
                accept="image/*,.pdf"
                onChange={(event) => setScanFile(event.target.files?.[0] ?? null)}
                className="sr-only"
              />
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-lg font-bold text-[#1F2937]">Kéo thả ảnh/PDF đơn thuốc vào đây</p>
                  <p className="mt-2 text-sm font-medium text-[#4B5563]">Hỗ trợ ảnh đơn thuốc, hóa đơn thuốc hoặc file PDF.</p>
                  {scanFile ? (
                    <p className="mt-3 rounded-xl border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-800">
                      Đã chọn: {scanFile.name}
                    </p>
                  ) : (
                    <p className={helperTextClass}>Chọn file ảnh/PDF trước để quét OCR.</p>
                  )}
                </div>
                <label htmlFor="scan-file-input" className={`${primaryButtonClass} cursor-pointer`}>
                  Chọn file
                </label>
              </div>

              <div className="mt-5 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={() => void onScanFile()}
                  disabled={!canScanFile}
                  className={primaryButtonClass}
                >
                  {isScanningFile ? "Đang nhận diện..." : "Nhận diện thuốc từ file"}
                </button>
                {!scanFile ? <span className="text-sm font-medium text-[#4B5563]">Chọn file ảnh/PDF trước để quét OCR.</span> : null}
              </div>
            </div>
          </section>

          <section className={cardClass}>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#4B5563]">Bước 2</p>
            <h3 className="mt-2 text-2xl font-bold text-[#1F2937]">Nhập hoặc dán nội dung thuốc</h3>
            <p className="mt-2 text-base font-medium text-[#4B5563]">
              Nếu OCR ngoài đã có sẵn nội dung, bạn có thể dán vào đây để nhận diện nhanh hơn.
            </p>

            <textarea
              value={scanText}
              onChange={(event) => setScanText(event.target.value)}
              placeholder={"Ví dụ:\naspirin 81mg\nmetformin 500mg\namlodipine 5mg"}
              className={`mt-4 ${textareaClass}`}
            />

            <button
              type="button"
              onClick={() => void onScanText()}
              disabled={!canScanText}
              className={`mt-4 ${primaryButtonClass}`}
            >
              {isScanningText ? "Đang nhận diện..." : "Nhận diện từ nội dung đã dán"}
            </button>
            {!scanText.trim() ? <p className={helperTextClass}>Dán hoặc nhập nội dung trước để tiếp tục.</p> : null}

            {scanNotice ? (
              <p className="mt-4 rounded-xl border border-[#B6D4FE] bg-[#F8FBFF] px-4 py-3 text-sm font-semibold text-[#4B5563]">
                {scanNotice}
              </p>
            ) : null}

            {detections.length ? (
              <div className="mt-4 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-base font-bold text-[#1F2937]">Danh sách thuốc nhận diện</p>
                  <span className="rounded-full border border-[#B6D4FE] bg-[#F8FBFF] px-3 py-1 text-xs font-semibold text-[#4B5563]">
                    Đã chọn {selectedDetections.length}/{detections.length}
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => onSelectAllDetections(true)}
                    className={secondaryButtonClass}
                  >
                    Chọn tất cả
                  </button>
                  <button
                    type="button"
                    onClick={() => onSelectAllDetections(false)}
                    className={secondaryButtonClass}
                  >
                    Bỏ chọn tất cả
                  </button>
                  <button
                    type="button"
                    onClick={() => onConfirmAllLowConfidence(true)}
                    disabled={!lowConfidenceTotal}
                    className={warningButtonClass}
                  >
                    Xác nhận các thuốc cần kiểm tra lại
                  </button>
                </div>
                {!lowConfidenceTotal ? (
                  <p className={helperTextClass}>Không có thuốc nhận diện chưa chắc chắn cần duyệt thêm.</p>
                ) : null}
                {pendingLowConfidenceSelections.length ? (
                  <p className="rounded-xl border-2 border-amber-300 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-800">
                    Còn {pendingLowConfidenceSelections.length}/{selectedLowConfidenceTotal} thuốc cần kiểm tra lại trước khi nhập.
                  </p>
                ) : null}

                <ul className="grid gap-2 lg:grid-cols-2">
                  {detections.map((item, index) => {
                    const key = getDetectionKey(item, index);
                    const checked = Boolean(selectedKeys[key]);
                    const isLowConfidence = isLowConfidenceDetection(item);
                    const isLowConfidenceConfirmed = Boolean(confirmedLowConfidenceKeys[key]);
                    return (
                      <li
                        key={key}
                        className={`rounded-2xl border p-4 transition ${
                          checked
                            ? isLowConfidence
                              ? "border-amber-400 bg-amber-50 shadow-sm"
                              : "border-[#2563EB] bg-[#EEF6FF] shadow-sm"
                            : "border-[#B6D4FE] bg-white"
                        }`}
                      >
                        <label className="flex min-h-11 cursor-pointer items-start gap-3">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => onToggleDetection(key)}
                            className="mt-1 h-6 w-6 rounded border-[#2563EB] text-[#2563EB] focus:ring-[#93C5FD]"
                          />
                          <div>
                            <p className="text-lg font-bold text-[#1F2937]">{item.drug_name}</p>
                            {(item.dosage || item.brand_name || item.manufacturer) ? (
                              <p className="mt-1 text-sm font-medium text-[#4B5563]">
                                {item.dosage ? `Liều: ${item.dosage}` : "Liều: N/A"}
                                {" · "}
                                {item.brand_name ? `Brand: ${item.brand_name}` : "Brand: N/A"}
                                {" · "}
                                {item.manufacturer ? `Hãng: ${item.manufacturer}` : "Hãng: N/A"}
                              </p>
                            ) : null}
                            <p className="mt-1 text-sm font-medium text-[#4B5563]">Bằng chứng: {item.evidence}</p>
                            <span className={`mt-2 inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${confidenceClass(item.confidence)}`}>
                              OCR {Math.round(item.confidence * 100)}%
                            </span>
                            {item.mapping_source ? (
                              <span
                                className={`ml-2 mt-2 inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${normalizationClass(item.mapping_source)}`}
                              >
                                {normalizationLabel(item.mapping_source)}
                              </span>
                            ) : null}
                          </div>
                        </label>
                        {isLowConfidence && checked ? (
                          <label className="mt-3 flex min-h-11 cursor-pointer items-center gap-3 rounded-xl border border-amber-300 bg-amber-50 px-3 py-2">
                            <input
                              type="checkbox"
                              checked={isLowConfidenceConfirmed}
                              onChange={() => onToggleLowConfidenceConfirm(key)}
                              className="h-6 w-6 rounded border-amber-500 text-amber-600 focus:ring-amber-300"
                            />
                            <span className="text-sm font-semibold text-amber-800">
                              Tôi xác nhận thuốc OCR này đúng trước khi nhập.
                            </span>
                          </label>
                        ) : null}
                      </li>
                    );
                  })}
                </ul>

                <button
                  type="button"
                  onClick={() => void onImportSelected()}
                  disabled={!canImportSelected}
                  className={primaryButtonClass}
                >
                  {isImporting ? "Đang thêm vào tủ..." : `Thêm ${selectedDetections.length} thuốc vào tủ`}
                </button>
                {!canImportSelected ? (
                  <p className={helperTextClass}>
                    {selectedDetections.length === 0
                      ? "Chọn ít nhất 1 thuốc nhận diện để thêm vào tủ."
                      : pendingLowConfidenceSelections.length > 0
                        ? "Xác nhận các thuốc cần kiểm tra lại trước khi thêm vào tủ."
                        : "Đang xử lý, vui lòng chờ."}
                  </p>
                ) : null}
              </div>
            ) : null}
          </section>

          <section className={cardClass}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#4B5563]">Bước 3</p>
                <h3 className="mt-2 text-2xl font-bold text-[#1F2937]">Nhập thuốc thủ công</h3>
                <p className="mt-2 text-base font-medium text-[#4B5563]">
                  Dùng khi đơn thuốc khó OCR hoặc bạn muốn thêm từng thuốc một.
                </p>
              </div>
              <span className="rounded-full border border-[#B6D4FE] bg-[#F8FBFF] px-3 py-1 text-xs font-bold text-[#4B5563]">
                Tùy chọn
              </span>
            </div>

            <form onSubmit={onAddManual} className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              <label className="space-y-2">
                <span className={fieldLabelClass}>Tên thuốc <span className="text-red-600">*</span></span>
                <input
                  value={manualDrugName}
                  onChange={(event) => setManualDrugName(event.target.value)}
                  required
                  placeholder="Ví dụ: Metformin"
                  className={inputClass}
                />
              </label>

              <label className="space-y-2">
                <span className={fieldOptionalLabelClass}>Brand (không bắt buộc)</span>
                <input
                  value={manualBrandName}
                  onChange={(event) => setManualBrandName(event.target.value)}
                  placeholder="Ví dụ: Panadol Extra"
                  className={inputClass}
                />
              </label>

              <label className="space-y-2">
                <span className={fieldOptionalLabelClass}>Hãng (không bắt buộc)</span>
                <input
                  value={manualManufacturer}
                  onChange={(event) => setManualManufacturer(event.target.value)}
                  placeholder="Ví dụ: STADA"
                  className={inputClass}
                />
              </label>

              <label className="space-y-2">
                <span className={fieldLabelClass}>Liều dùng <span className="text-red-600">*</span></span>
                <input
                  value={manualDosage}
                  onChange={(event) => setManualDosage(event.target.value)}
                  placeholder="Ví dụ: 500mg"
                  required
                  className={inputClass}
                />
              </label>

              <div className="space-y-2">
                <span className={fieldLabelClass}>Số lượng</span>
                <div className="flex h-14 overflow-hidden rounded-2xl border border-[#93C5FD] bg-[#F8FBFF] focus-within:border-[#2563EB] focus-within:ring-4 focus-within:ring-blue-100">
                  <button
                    type="button"
                    onClick={() => adjustManualQuantity(-1)}
                    className="flex w-14 items-center justify-center border-r border-[#B6D4FE] text-xl font-bold text-[#1F2937] hover:bg-[#EEF6FF]"
                    aria-label="Giảm số lượng"
                  >
                    -
                  </button>
                  <input
                    value={manualQuantity}
                    onChange={(event) => setManualQuantity(event.target.value)}
                    inputMode="numeric"
                    aria-label="Số lượng thuốc"
                    className="min-w-0 flex-1 bg-transparent px-4 text-center text-base font-semibold text-[#1F2937] outline-none placeholder:text-[#6B7280]"
                  />
                  <button
                    type="button"
                    onClick={() => adjustManualQuantity(1)}
                    className="flex w-14 items-center justify-center border-l border-[#B6D4FE] text-xl font-bold text-[#1F2937] hover:bg-[#EEF6FF]"
                    aria-label="Tăng số lượng"
                  >
                    +
                  </button>
                </div>
              </div>

              <div className="md:col-span-3">
                <button
                  type="submit"
                  disabled={!canAddManual}
                  className={primaryButtonClass}
                >
                  {isAddingManual ? "Đang thêm..." : "Thêm 1 thuốc vào tủ"}
                </button>
                {!canAddManual ? <p className={helperTextClass}>Nhập ít nhất tên thuốc và liều dùng để thêm vào tủ.</p> : null}
              </div>
            </form>

            {manualNotice ? (
              <p className="mt-4 rounded-xl border border-[#B6D4FE] bg-[#F8FBFF] px-4 py-3 text-sm font-semibold text-[#4B5563]">
                {manualNotice}
              </p>
            ) : null}
          </section>
        </div>
      </SelfMedConsentGate>
    </PageShell>
  );
}
