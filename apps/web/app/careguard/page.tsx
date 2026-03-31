"use client";

import { ChangeEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import PageShell from "@/components/ui/page-shell";
import { acceptConsent, getConsentStatus } from "@/lib/consent";
import {
  CareguardAnalyzeResult,
  analyzeCareguard,
  normalizeCareguardResult,
  parseFreeTextList,
  parseLabsInput
} from "@/lib/careguard";
import {
  addCabinetItem,
  CabinetItem,
  deleteCabinetItem,
  getCabinet,
  importDetections,
  isLowConfidenceDetection,
  runCabinetAutoDdi,
  scanReceiptFile,
  scanReceiptText,
  ScanDetection
} from "@/lib/selfmed";

function getRiskBadgeClass(riskTier: string | null): string {
  const value = riskTier?.toLowerCase() ?? "";
  if (value.includes("high") || value.includes("red") || value.includes("critical")) {
    return "border-red-200 bg-red-50 text-red-700";
  }
  if (value.includes("medium") || value.includes("moderate") || value.includes("amber")) {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  if (value.includes("low") || value.includes("green")) {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  return "border-slate-200 bg-slate-50 text-slate-700";
}

function getRiskLabelVi(riskTier: string | null): string {
  const value = riskTier?.toLowerCase() ?? "";
  if (value.includes("high") || value.includes("red") || value.includes("critical")) return "Cao";
  if (value.includes("medium") || value.includes("moderate") || value.includes("amber")) return "Trung bình";
  if (value.includes("low") || value.includes("green")) return "Thấp";
  return riskTier ?? "Chưa xác định";
}

function getModeBadgeLabel(mode: string | null): string {
  const value = mode?.toLowerCase() ?? "";
  if (value.includes("external_plus_local") || value.includes("external")) {
    return "Runtime: External + Local";
  }
  if (value.includes("local_only") || value.includes("local")) {
    return "Runtime: Local only";
  }
  return "Runtime: Chưa xác định";
}

function getModeBadgeClass(mode: string | null): string {
  const value = mode?.toLowerCase() ?? "";
  if (value.includes("external_plus_local") || value.includes("external")) {
    return "border-sky-200 bg-sky-50 text-sky-700";
  }
  if (value.includes("local_only") || value.includes("local")) {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  return "border-slate-200 bg-slate-50 text-slate-700";
}

function getDetectionKey(item: ScanDetection, index: number): string {
  return `${item.normalized_name}-${item.evidence}-${index}`;
}

export default function CareguardPage() {
  const [consentLoading, setConsentLoading] = useState(true);
  const [consentAccepted, setConsentAccepted] = useState(false);
  const [consentRequiredVersion, setConsentRequiredVersion] = useState("");
  const [consentChecked, setConsentChecked] = useState(false);
  const [consentError, setConsentError] = useState("");
  const [acceptingConsent, setAcceptingConsent] = useState(false);

  const [cabinet, setCabinet] = useState<CabinetItem[]>([]);
  const [cabinetLabel, setCabinetLabel] = useState("Tủ thuốc cá nhân");
  const [cabinetLoading, setCabinetLoading] = useState(true);
  const [cabinetError, setCabinetError] = useState("");
  const [cabinetNotice, setCabinetNotice] = useState("");

  const [receiptTextInput, setReceiptTextInput] = useState("");
  const [receiptFile, setReceiptFile] = useState<File | null>(null);
  const [receiptDetections, setReceiptDetections] = useState<ScanDetection[]>([]);
  const [confirmedDetectionKeys, setConfirmedDetectionKeys] = useState<Record<string, boolean>>({});
  const [receiptNotice, setReceiptNotice] = useState("");
  const [isScanning, setIsScanning] = useState(false);

  const [manualMedicationInput, setManualMedicationInput] = useState("");
  const [allergiesInput, setAllergiesInput] = useState("");
  const [symptomsInput, setSymptomsInput] = useState("");
  const [labsInput, setLabsInput] = useState("");

  const [autoResult, setAutoResult] = useState<CareguardAnalyzeResult | null>(null);
  const [manualResult, setManualResult] = useState<CareguardAnalyzeResult | null>(null);
  const [autoChecking, setAutoChecking] = useState(false);
  const [manualChecking, setManualChecking] = useState(false);
  const [autoError, setAutoError] = useState("");
  const [manualError, setManualError] = useState("");

  const cabinetStats = useMemo(() => {
    const fromOcr = cabinet.filter((item) => item.source === "ocr").length;
    return { total: cabinet.length, fromOcr };
  }, [cabinet]);

  const medicationNames = useMemo(() => {
    return Array.from(new Set(cabinet.map((item) => item.normalized_name))).filter(Boolean);
  }, [cabinet]);

  const pendingLowConfidenceDetections = useMemo(() => {
    return receiptDetections.filter((item, index) => {
      if (!isLowConfidenceDetection(item)) return false;
      return !confirmedDetectionKeys[getDetectionKey(item, index)];
    });
  }, [confirmedDetectionKeys, receiptDetections]);

  const refreshConsentStatus = async (): Promise<boolean> => {
    setConsentError("");
    try {
      const status = await getConsentStatus();
      setConsentAccepted(status.accepted);
      setConsentRequiredVersion(status.required_version);
      return status.accepted;
    } catch (error) {
      setConsentError(error instanceof Error ? error.message : "Không thể kiểm tra consent.");
      setConsentAccepted(false);
      return false;
    }
  };

  const refreshCabinet = async () => {
    setCabinetLoading(true);
    setCabinetError("");
    try {
      const response = await getCabinet();
      setCabinet(response.items);
      setCabinetLabel(response.label);
    } catch (error) {
      setCabinetError(error instanceof Error ? error.message : "Không thể tải dữ liệu tủ thuốc.");
    } finally {
      setCabinetLoading(false);
    }
  };

  useEffect(() => {
    const initialize = async () => {
      setConsentLoading(true);
      const accepted = await refreshConsentStatus();
      if (accepted) {
        await refreshCabinet();
      } else {
        setCabinetLoading(false);
      }
      setConsentLoading(false);
    };
    void initialize();
  }, []);

  const onAcceptConsent = async () => {
    if (!consentRequiredVersion) return;
    if (!consentChecked) {
      setConsentError("Vui lòng tick xác nhận trước khi tiếp tục.");
      return;
    }

    setAcceptingConsent(true);
    setConsentError("");
    try {
      await acceptConsent({ consent_version: consentRequiredVersion, accepted: true });
      setConsentAccepted(true);
      await refreshCabinet();
    } catch (error) {
      setConsentError(error instanceof Error ? error.message : "Không thể lưu xác nhận consent.");
    } finally {
      setAcceptingConsent(false);
    }
  };

  const onRecognizeReceiptText = async () => {
    const text = receiptTextInput.trim();
    if (!text) {
      setReceiptNotice("Vui lòng nhập nội dung OCR trước khi nhận diện.");
      return;
    }

    setIsScanning(true);
    setReceiptNotice("");
    setReceiptDetections([]);
    setConfirmedDetectionKeys({});
    try {
      const detections = await scanReceiptText(text);
      setReceiptDetections(detections);
      const nextConfirmed: Record<string, boolean> = {};
      detections.forEach((item, index) => {
        if (!isLowConfidenceDetection(item)) {
          nextConfirmed[getDetectionKey(item, index)] = true;
        }
      });
      setConfirmedDetectionKeys(nextConfirmed);
      setReceiptNotice(
        detections.length
          ? `Nhận diện được ${detections.length} thuốc từ nội dung OCR.`
          : "Chưa nhận diện được thuốc từ nội dung này."
      );
    } catch (error) {
      setReceiptNotice(error instanceof Error ? error.message : "Không thể nhận diện nội dung OCR.");
    } finally {
      setIsScanning(false);
    }
  };

  const onScanReceiptFile = async () => {
    if (!receiptFile) {
      setReceiptNotice("Vui lòng chọn file hóa đơn/đơn thuốc trước khi quét.");
      return;
    }

    setIsScanning(true);
    setReceiptNotice("");
    setReceiptDetections([]);
    setConfirmedDetectionKeys({});
    try {
      const detections = await scanReceiptFile(receiptFile);
      setReceiptDetections(detections);
      const nextConfirmed: Record<string, boolean> = {};
      detections.forEach((item, index) => {
        if (!isLowConfidenceDetection(item)) {
          nextConfirmed[getDetectionKey(item, index)] = true;
        }
      });
      setConfirmedDetectionKeys(nextConfirmed);
      setReceiptNotice(
        detections.length
          ? `Nhận diện được ${detections.length} thuốc từ file OCR.`
          : "Đã quét file nhưng chưa nhận diện được thuốc."
      );
    } catch (error) {
      setReceiptNotice(error instanceof Error ? error.message : "Không thể quét file OCR.");
    } finally {
      setIsScanning(false);
    }
  };

  const onImportDetections = async () => {
    if (!receiptDetections.length) {
      setCabinetNotice("Chưa có dữ liệu nhận diện để thêm vào tủ thuốc.");
      return;
    }
    if (pendingLowConfidenceDetections.length) {
      setCabinetNotice("Cần xác nhận từng thuốc độ tin cậy thấp trước khi thêm vào tủ thuốc.");
      return;
    }

    setCabinetNotice("");
    try {
      const inserted = await importDetections(receiptDetections);
      await refreshCabinet();
      setCabinetNotice(`Đã thêm ${inserted} thuốc vào ${cabinetLabel}.`);
    } catch (error) {
      setCabinetNotice(error instanceof Error ? error.message : "Không thể nhập dữ liệu nhận diện.");
    }
  };

  const onConfirmDetection = (key: string) => {
    setConfirmedDetectionKeys((current) => ({ ...current, [key]: !current[key] }));
  };

  const onAddManualMedication = async () => {
    const names = parseFreeTextList(manualMedicationInput);
    if (!names.length) {
      setCabinetNotice("Vui lòng nhập ít nhất 1 tên thuốc.");
      return;
    }

    let inserted = 0;
    for (const name of names) {
      try {
        await addCabinetItem({ drug_name: name, source: "manual" });
        inserted += 1;
      } catch {
        // Ignore duplicates to keep quick-add flow smooth.
      }
    }

    await refreshCabinet();
    setManualMedicationInput("");
    setCabinetNotice(
      inserted > 0
        ? `Đã thêm ${inserted} thuốc thủ công vào tủ thuốc.`
        : "Các thuốc vừa nhập đã tồn tại trong tủ thuốc."
    );
  };

  const onRemoveCabinetItem = async (itemId: number) => {
    setCabinetNotice("");
    try {
      await deleteCabinetItem(itemId);
      await refreshCabinet();
      setCabinetNotice("Đã xóa thuốc khỏi tủ thuốc.");
    } catch (error) {
      setCabinetNotice(error instanceof Error ? error.message : "Không thể xóa thuốc.");
    }
  };

  const onRunAutoDdi = async () => {
    setAutoChecking(true);
    setAutoError("");
    setAutoResult(null);
    try {
      const result = await runCabinetAutoDdi({
        allergies: parseFreeTextList(allergiesInput)
      });
      setAutoResult(result);
    } catch (error) {
      setAutoError(error instanceof Error ? error.message : "Không thể chạy auto DDI.");
    } finally {
      setAutoChecking(false);
    }
  };

  const onRunAdvancedAnalyze = async () => {
    if (!medicationNames.length) {
      setManualError("Cần ít nhất 1 thuốc trong tủ để chạy phân tích nâng cao.");
      return;
    }

    setManualError("");
    setManualChecking(true);
    try {
      const response = await analyzeCareguard({
        symptoms: parseFreeTextList(symptomsInput),
        labs: parseLabsInput(labsInput),
        medications: medicationNames,
        allergies: parseFreeTextList(allergiesInput)
      });
      setManualResult(normalizeCareguardResult(response));
    } catch (error) {
      setManualError(error instanceof Error ? error.message : "Không thể chạy phân tích nâng cao.");
    } finally {
      setManualChecking(false);
    }
  };

  if (consentLoading) {
    return (
      <PageShell title="CLARA CareGuard">
        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-base font-semibold text-slate-900">Đang kiểm tra điều khoản sử dụng y tế...</p>
        </section>
      </PageShell>
    );
  }

  if (!consentAccepted) {
    return (
      <PageShell title="CLARA CareGuard">
        <section className="rounded-3xl border-2 border-amber-300 bg-amber-50 p-6 shadow-sm">
          <p className="text-sm font-semibold uppercase tracking-wide text-amber-800">Bước bắt buộc trước khi dùng</p>
          <h2 className="mt-2 text-2xl font-bold text-slate-900">Tuyên bố miễn trừ trách nhiệm y tế</h2>
          <p className="mt-3 text-lg leading-8 text-slate-800">
            CLARA chỉ hỗ trợ cảnh báo tương tác thuốc và giải thích an toàn sử dụng. Ứng dụng không thay thế bác sĩ,
            không kê đơn, không chẩn đoán và không chỉ định liều dùng.
          </p>
          <p className="mt-3 text-base text-slate-700">
            Phiên bản điều khoản hiện tại: <span className="font-semibold">{consentRequiredVersion || "-"}</span>
          </p>

          <label className="mt-4 flex cursor-pointer items-start gap-3 rounded-2xl border border-slate-300 bg-white p-4">
            <input
              type="checkbox"
              className="mt-1 h-5 w-5"
              checked={consentChecked}
              onChange={(event) => setConsentChecked(event.target.checked)}
            />
            <span className="text-base font-medium leading-7 text-slate-900">
              Tôi đã đọc, hiểu và đồng ý với tuyên bố miễn trừ trách nhiệm y tế của CLARA.
            </span>
          </label>

          <button
            type="button"
            onClick={onAcceptConsent}
            disabled={!consentChecked || acceptingConsent}
            className="mt-5 min-h-12 rounded-xl bg-slate-900 px-6 py-3 text-base font-semibold text-white disabled:opacity-50"
          >
            {acceptingConsent ? "Đang lưu xác nhận..." : "Đồng ý và tiếp tục"}
          </button>

          {consentError ? <p className="mt-3 text-sm text-red-700">{consentError}</p> : null}
        </section>
      </PageShell>
    );
  }

  return (
    <PageShell title="CLARA CareGuard" variant="plain">
      <div className="space-y-4">
        <section className="rounded-3xl border border-slate-200 bg-gradient-to-br from-sky-50 via-white to-emerald-50 p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Flow backend thật</p>
          <h1 className="mt-1 text-xl font-semibold text-slate-900">Scan → xác nhận thủ công → lưu tủ thuốc → phân tích DDI</h1>
          <p className="mt-2 text-sm text-slate-700">
            Luồng CareGuard hiện dùng cùng dữ liệu persistent với <Link className="font-semibold underline" href="/selfmed">/selfmed</Link>.
            Dữ liệu không còn nằm ở localStorage.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-700">
              Tổng thuốc: {cabinetStats.total}
            </span>
            <span className="rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700">
              Nguồn OCR: {cabinetStats.fromOcr}
            </span>
          </div>
        </section>

        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Bước 1</p>
          <h2 className="mt-1 text-xl font-semibold text-slate-900">Nhận diện OCR và xác nhận thủ công</h2>
          <p className="mt-2 text-base leading-7 text-slate-700">
            Chế độ dành cho người lớn tuổi: chữ lớn hơn, tương phản cao, nút xác nhận rõ ràng.
          </p>

          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <div className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <label className="text-base font-semibold text-slate-900" htmlFor="careguard-scan-file">
                Tải file đơn thuốc/hóa đơn
              </label>
              <input
                id="careguard-scan-file"
                type="file"
                accept="image/*,.pdf"
                onChange={(event: ChangeEvent<HTMLInputElement>) => setReceiptFile(event.target.files?.[0] ?? null)}
                className="block w-full text-base text-slate-800 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-200 file:px-3 file:py-2 file:text-base file:font-semibold"
              />
              <button
                type="button"
                onClick={onScanReceiptFile}
                disabled={isScanning}
                className="min-h-14 rounded-xl border-2 border-slate-400 px-5 py-3 text-base font-semibold text-slate-900 transition hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-sky-200 disabled:opacity-60"
              >
                {isScanning ? "Đang quét file..." : "Quét file OCR"}
              </button>
            </div>

            <div className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <label className="text-base font-semibold text-slate-900" htmlFor="careguard-scan-text">
                Hoặc dán nội dung OCR
              </label>
              <textarea
                id="careguard-scan-text"
                value={receiptTextInput}
                onChange={(event) => setReceiptTextInput(event.target.value)}
                className="min-h-[140px] w-full rounded-xl border-2 border-slate-300 px-3 py-2 text-base leading-7 text-slate-900 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-sky-200"
                placeholder="Dán nội dung OCR hóa đơn/đơn thuốc..."
              />
              <button
                type="button"
                onClick={onRecognizeReceiptText}
                disabled={isScanning}
                className="min-h-14 rounded-xl border-2 border-slate-400 px-5 py-3 text-base font-semibold text-slate-900 transition hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-sky-200 disabled:opacity-60"
              >
                {isScanning ? "Đang quét nội dung..." : "Nhận diện từ text"}
              </button>
            </div>
          </div>

          {receiptNotice ? (
            <p className="mt-3 text-base font-medium text-slate-800" aria-live="polite">
              {receiptNotice}
            </p>
          ) : null}

          {receiptDetections.length ? (
            <div className="mt-3 rounded-2xl border-2 border-emerald-200 bg-emerald-50 p-4">
              <p className="text-xl font-semibold text-emerald-950">Xác nhận thủ công trước khi nhập tủ thuốc</p>
              <p className="mt-1 text-base leading-7 text-emerald-900">
                Vui lòng kiểm tra danh sách dưới đây. Thuốc có độ tin cậy thấp cần xác nhận riêng từng mục trước khi thêm.
              </p>
              {pendingLowConfidenceDetections.length ? (
                <p
                  className="mt-2 rounded-xl border-2 border-amber-400 bg-amber-100 px-3 py-2 text-base font-semibold text-amber-950"
                  aria-live="assertive"
                >
                  Còn {pendingLowConfidenceDetections.length} thuốc độ tin cậy thấp chưa được xác nhận thủ công.
                </p>
              ) : null}
              <ul className="mt-3 grid gap-2 md:grid-cols-2">
                {receiptDetections.map((item, index) => {
                  const key = getDetectionKey(item, index);
                  const isLowConfidence = isLowConfidenceDetection(item);
                  const isConfirmed = Boolean(confirmedDetectionKeys[key]);
                  return (
                    <li
                      key={key}
                      className={`rounded-xl border bg-white p-3 ${
                        isLowConfidence ? "border-amber-300" : "border-emerald-200"
                      }`}
                    >
                      <p className="text-xl font-semibold text-slate-950">{item.drug_name}</p>
                      <p className="mt-1 text-lg text-slate-800">Bằng chứng: {item.evidence}</p>
                      <p className="mt-1 text-lg font-semibold text-slate-900">
                        Độ tin cậy: {Math.round(item.confidence * 100)}%
                      </p>
                      {isLowConfidence ? (
                        <label className="mt-2 flex min-h-14 cursor-pointer items-center gap-3 rounded-xl border-2 border-amber-400 bg-amber-50 px-3 py-2">
                          <input
                            type="checkbox"
                            checked={isConfirmed}
                            onChange={() => onConfirmDetection(key)}
                            className="h-7 w-7 rounded border-2 border-amber-500 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-amber-300"
                          />
                          <span className="text-base font-semibold leading-7 text-amber-950">
                            Tôi xác nhận mục này đúng trước khi nhập vào {cabinetLabel}
                          </span>
                        </label>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
              <button
                type="button"
                onClick={onImportDetections}
                disabled={pendingLowConfidenceDetections.length > 0}
                className="mt-4 min-h-14 rounded-xl bg-emerald-700 px-6 py-3 text-lg font-semibold text-white transition hover:bg-emerald-800 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-emerald-300 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Tôi đã kiểm tra đúng, thêm vào {cabinetLabel}
              </button>
              <p className="mt-2 text-sm text-emerald-900">
                Ghi chú roadmap: sẽ bổ sung đọc kết quả bằng giọng nói (TTS) sau vòng 2.
              </p>
            </div>
          ) : null}
        </section>

        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Bước 2</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-900">Quản lý {cabinetLabel}</h2>

          <div className="mt-3 flex flex-col gap-2 md:flex-row md:items-center">
            <input
              className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
              placeholder="Ví dụ: Panadol Extra, Warfarin"
              value={manualMedicationInput}
              onChange={(event) => setManualMedicationInput(event.target.value)}
            />
            <button
              type="button"
              onClick={onAddManualMedication}
              className="min-h-11 rounded-xl border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700"
            >
              Thêm thủ công
            </button>
            <button
              type="button"
              onClick={refreshCabinet}
              className="min-h-11 rounded-xl border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700"
            >
              Làm mới
            </button>
          </div>

          {cabinetLoading ? <p className="mt-3 text-sm text-slate-600">Đang tải tủ thuốc...</p> : null}
          {cabinetError ? <p className="mt-3 text-sm text-red-700">{cabinetError}</p> : null}
          {cabinetNotice ? <p className="mt-3 text-sm text-slate-700">{cabinetNotice}</p> : null}

          {cabinet.length ? (
            <ul className="mt-3 space-y-2">
              {cabinet.map((item) => (
                <li key={item.id} className="flex items-start justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">{item.drug_name}</p>
                    <p className="mt-1 text-xs text-slate-600">
                      normalized: {item.normalized_name} | nguồn: {item.source}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => onRemoveCabinetItem(item.id)}
                    className="rounded-lg border border-red-200 px-2 py-1 text-xs font-medium text-red-700"
                  >
                    Xóa
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            !cabinetLoading && <p className="mt-3 text-sm text-slate-600">Tủ thuốc đang trống.</p>
          )}
        </section>

        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Bước 3</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-900">Auto DDI và phân tích nâng cao</h2>

          <label className="mt-3 block space-y-1">
            <span className="text-sm font-medium text-slate-700">Dị ứng (không bắt buộc)</span>
            <textarea
              className="min-h-[90px] w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
              value={allergiesInput}
              onChange={(event) => setAllergiesInput(event.target.value)}
              placeholder="Mỗi dòng 1 dị ứng hoặc phân tách bằng dấu phẩy"
            />
          </label>

          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={onRunAutoDdi}
              disabled={autoChecking || cabinet.length === 0}
              className="min-h-11 rounded-xl bg-indigo-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
            >
              {autoChecking ? "Đang chạy auto DDI..." : "Chạy auto DDI"}
            </button>

            <button
              type="button"
              onClick={onRunAdvancedAnalyze}
              disabled={manualChecking || cabinet.length === 0}
              className="min-h-11 rounded-xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-60"
            >
              {manualChecking ? "Đang phân tích nâng cao..." : "Chạy phân tích nâng cao"}
            </button>
          </div>

          <div className="mt-3 grid gap-3 lg:grid-cols-2">
            <label className="space-y-1">
              <span className="text-sm font-medium text-slate-700">Triệu chứng (nâng cao)</span>
              <textarea
                className="h-24 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                placeholder="Ví dụ: chóng mặt, khó thở"
                value={symptomsInput}
                onChange={(event) => setSymptomsInput(event.target.value)}
              />
            </label>
            <label className="space-y-1">
              <span className="text-sm font-medium text-slate-700">Xét nghiệm (nâng cao)</span>
              <textarea
                className="h-24 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                placeholder="Ví dụ: egfr=28, creatinine=2.1"
                value={labsInput}
                onChange={(event) => setLabsInput(event.target.value)}
              />
            </label>
          </div>

          {autoError ? <p className="mt-3 text-sm text-red-700">{autoError}</p> : null}
          {manualError ? <p className="mt-3 text-sm text-red-700">{manualError}</p> : null}

          {autoResult ? (
            <article className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-semibold text-slate-900">Kết quả Auto DDI:</p>
                <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${getRiskBadgeClass(autoResult.riskTier)}`}>
                  {getRiskLabelVi(autoResult.riskTier)}
                </span>
                <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${getModeBadgeClass(autoResult.mode)}`}>
                  {getModeBadgeLabel(autoResult.mode)}
                </span>
                <span
                  className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${
                    autoResult.fallbackUsed
                      ? "border-amber-200 bg-amber-50 text-amber-700"
                      : "border-emerald-200 bg-emerald-50 text-emerald-700"
                  }`}
                >
                  {autoResult.fallbackUsed ? "Fallback cục bộ: Có" : "Fallback cục bộ: Không"}
                </span>
              </div>
              {autoResult.ddiAlerts.length ? (
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
                  {autoResult.ddiAlerts.map((alert, index) => (
                    <li key={`${alert.title}-${index}`}>{alert.title}</li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-sm text-slate-700">Chưa phát hiện cảnh báo tương tác rõ ràng.</p>
              )}
              <article className="mt-3 rounded-xl border border-slate-200 bg-white p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Minh bạch nguồn dữ liệu</p>
                <p className="mt-1 text-sm text-slate-700">Mode trả về: {autoResult.mode ?? "N/A"}</p>
                {autoResult.attribution?.sources.length ? (
                  <p className="mt-1 text-sm text-slate-700">
                    Nguồn: {autoResult.attribution.sources.map((source) => source.name).join(", ")}
                  </p>
                ) : (
                  <p className="mt-1 text-sm text-slate-700">Nguồn: chưa có attribution.</p>
                )}
                {Object.keys(autoResult.sourceErrors).length ? (
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-amber-700">
                    {Object.entries(autoResult.sourceErrors).map(([source, issues]) => (
                      <li key={source}>
                        {source}: {issues.join(", ")}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-1 text-sm text-slate-700">source_errors: không ghi nhận.</p>
                )}
              </article>
            </article>
          ) : null}

          {manualResult ? (
            <article className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-semibold text-slate-900">Kết quả nâng cao:</p>
                <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${getRiskBadgeClass(manualResult.riskTier)}`}>
                  {getRiskLabelVi(manualResult.riskTier)}
                </span>
                <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${getModeBadgeClass(manualResult.mode)}`}>
                  {getModeBadgeLabel(manualResult.mode)}
                </span>
                <span
                  className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${
                    manualResult.fallbackUsed
                      ? "border-amber-200 bg-amber-50 text-amber-700"
                      : "border-emerald-200 bg-emerald-50 text-emerald-700"
                  }`}
                >
                  {manualResult.fallbackUsed ? "Fallback cục bộ: Có" : "Fallback cục bộ: Không"}
                </span>
              </div>
              {manualResult.recommendations.length ? (
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
                  {manualResult.recommendations.map((item, index) => (
                    <li key={`${item}-${index}`}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-sm text-slate-700">Chưa có khuyến nghị bổ sung.</p>
              )}
              <article className="mt-3 rounded-xl border border-slate-200 bg-white p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Minh bạch nguồn dữ liệu</p>
                <p className="mt-1 text-sm text-slate-700">Mode trả về: {manualResult.mode ?? "N/A"}</p>
                {manualResult.attribution?.sources.length ? (
                  <p className="mt-1 text-sm text-slate-700">
                    Nguồn: {manualResult.attribution.sources.map((source) => source.name).join(", ")}
                  </p>
                ) : (
                  <p className="mt-1 text-sm text-slate-700">Nguồn: chưa có attribution.</p>
                )}
                {Object.keys(manualResult.sourceErrors).length ? (
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-amber-700">
                    {Object.entries(manualResult.sourceErrors).map(([source, issues]) => (
                      <li key={source}>
                        {source}: {issues.join(", ")}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-1 text-sm text-slate-700">source_errors: không ghi nhận.</p>
                )}
              </article>
            </article>
          ) : null}
        </section>
      </div>
    </PageShell>
  );
}
