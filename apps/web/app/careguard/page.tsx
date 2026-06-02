"use client";

import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import PageShell from "@/components/ui/page-shell";
import { acceptConsent, getConsentStatus } from "@/lib/consent";
import {
  CareguardAnalyzeResult,
  analyzeCareguard,
  formatCareguardRiskLabel,
  normalizeCareguardResult,
  parseFreeTextList,
  parseLabsInput,
  toCareguardUserMessage
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

const RISK_GAUGE_CIRCUMFERENCE = 552.92;

function getRiskBadgeClass(riskTier: string | null): string {
  const value = riskTier?.toLowerCase() ?? "";
  if (value.includes("high") || value.includes("red") || value.includes("critical")) {
    return "border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300";
  }
  if (value.includes("medium") || value.includes("moderate") || value.includes("amber")) {
    return "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300";
  }
  if (value.includes("low") || value.includes("green")) {
    return "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300";
  }
  return "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]";
}

function getModeBadgeLabel(mode: string | null): string {
  const value = mode?.toLowerCase() ?? "";
  if (value.includes("external_plus_local") || value.includes("external")) return "Bên ngoài + cục bộ";
  if (value.includes("local_only") || value.includes("local")) return "Chỉ cục bộ";
  return "Chưa xác định";
}

function getModeBadgeClass(mode: string | null): string {
  const value = mode?.toLowerCase() ?? "";
  if (value.includes("external_plus_local") || value.includes("external")) {
    return "border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-800 dark:bg-sky-950/40 dark:text-sky-300";
  }
  if (value.includes("local_only") || value.includes("local")) {
    return "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300";
  }
  return "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]";
}

function getDetectionKey(item: ScanDetection, index: number): string {
  return `${item.normalized_name}-${item.evidence}-${index}`;
}

function getNormalizationLabel(source: string | null | undefined): string {
  if (source === "db") return "Khớp từ điển";
  if (source === "candidate") return "Khớp gợi ý";
  if (source === "fallback") return "Dự phòng";
  return "Chưa xác định";
}

function getNormalizationClass(source: string | null | undefined): string {
  if (source === "db") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300";
  }
  if (source === "candidate") {
    return "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300";
  }
  if (source === "fallback") {
    return "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-800 dark:bg-rose-950/40 dark:text-rose-300";
  }
  return "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]";
}

function getSeverityTone(severity: string | undefined, fallbackIndex: number): "major" | "moderate" {
  const normalized = severity?.toLowerCase() ?? "";
  if (["major", "high", "critical", "severe"].some((token) => normalized.includes(token))) {
    return "major";
  }
  if (["moderate", "medium", "amber"].some((token) => normalized.includes(token))) {
    return "moderate";
  }
  return fallbackIndex === 0 ? "major" : "moderate";
}

function getRiskScore(result: CareguardAnalyzeResult | null): number {
  if (!result) return 0;
  const tier = (result.riskTier ?? "").toLowerCase();
  let base = 46;
  if (["high", "critical", "red"].some((token) => tier.includes(token))) base = 72;
  if (["medium", "moderate", "amber"].some((token) => tier.includes(token))) base = 54;
  if (["low", "green"].some((token) => tier.includes(token))) base = 28;

  const severeAlerts = result.ddiAlerts.filter((alert) => getSeverityTone(alert.severity, 0) === "major").length;
  const moderateAlerts = Math.max(0, result.ddiAlerts.length - severeAlerts);
  const weighted = base + severeAlerts * 7 + moderateAlerts * 3;
  return Math.max(5, Math.min(95, weighted));
}

function getRiskScoreLabel(score: number): string {
  if (score >= 70) return "Rủi ro cao";
  if (score >= 45) return "Rủi ro trung bình";
  return "Rủi ro thấp";
}

function getRiskScoreMeaning(result: CareguardAnalyzeResult | null, score: number): string {
  if (!result) return "Chưa kiểm tra tương tác thuốc.";
  const alertCount = result.ddiAlerts.length;
  if (alertCount > 0) {
    return `${alertCount} cảnh báo tương tác cần đọc trước khi dùng thuốc cùng nhau.`;
  }
  if (score >= 45) return "Có yếu tố cần rà soát thêm dù chưa thấy cặp tương tác rõ ràng.";
  return "Chưa thấy cảnh báo tương tác rõ trong tủ thuốc hiện tại.";
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
  const [ageInput, setAgeInput] = useState("");

  const [includeAgeRisk, setIncludeAgeRisk] = useState(true);
  const [includeLabs, setIncludeLabs] = useState(false);
  const [includeSymptoms, setIncludeSymptoms] = useState(false);
  const [includeHerbalOverlay, setIncludeHerbalOverlay] = useState(true);

  const [autoResult, setAutoResult] = useState<CareguardAnalyzeResult | null>(null);
  const [manualResult, setManualResult] = useState<CareguardAnalyzeResult | null>(null);
  const [autoChecking, setAutoChecking] = useState(false);
  const [manualChecking, setManualChecking] = useState(false);
  const [autoError, setAutoError] = useState("");
  const [manualError, setManualError] = useState("");

  const hiddenFileInputRef = useRef<HTMLInputElement | null>(null);
  const cameraInputRef = useRef<HTMLInputElement | null>(null);

  const cabinetStats = useMemo(() => {
    const fromOcr = cabinet.filter((item) => item.source === "ocr").length;
    return { total: cabinet.length, fromOcr };
  }, [cabinet]);

  const medicationNames = useMemo(
    () => Array.from(new Set(cabinet.map((item) => item.normalized_name))).filter(Boolean),
    [cabinet]
  );

  const pendingLowConfidenceDetections = useMemo(() => {
    return receiptDetections.filter((item, index) => {
      if (!isLowConfidenceDetection(item)) return false;
      return !confirmedDetectionKeys[getDetectionKey(item, index)];
    });
  }, [confirmedDetectionKeys, receiptDetections]);

  const lowConfidenceDetectionCount = useMemo(
    () => receiptDetections.filter((item) => isLowConfidenceDetection(item)).length,
    [receiptDetections]
  );

  const displayedResult = manualResult ?? autoResult;
  const aggregateRiskScore = useMemo(() => getRiskScore(displayedResult), [displayedResult]);
  const aggregateRiskLabel = useMemo(() => getRiskScoreLabel(aggregateRiskScore), [aggregateRiskScore]);

  const gaugeOffset = useMemo(() => {
    if (!displayedResult) return RISK_GAUGE_CIRCUMFERENCE;
    return RISK_GAUGE_CIRCUMFERENCE - (aggregateRiskScore / 100) * RISK_GAUGE_CIRCUMFERENCE;
  }, [aggregateRiskScore, displayedResult]);

  const visibleAlerts = useMemo(() => {
    if (!displayedResult) return [] as Array<{ title: string; details: string; tone: "major" | "moderate" }>;

    return displayedResult.ddiAlerts.slice(0, 2).map((alert, index) => ({
      title: alert.title,
      details:
        alert.details ??
        (index === 0
          ? "Dùng đồng thời có thể làm tăng nguy cơ tác dụng bất lợi có ý nghĩa lâm sàng."
          : "Cần theo dõi sát hơn và đánh giá lợi ích - nguy cơ trong lần tái khám."),
      tone: getSeverityTone(alert.severity, index)
    }));
  }, [displayedResult]);

  const aiInsight = useMemo(() => {
    if (!displayedResult) {
      return "Hãy thêm thuốc vào tủ, sau đó bấm kiểm tra tương tác để xem cặp thuốc nào cần lưu ý.";
    }
    if (displayedResult.recommendations.length > 0) {
      return displayedResult.recommendations[0];
    }
    if (displayedResult.ddiAlerts.length > 0) {
      return "Mẫu tương tác phát hiện được cần đối chiếu thêm theo tuổi, chức năng thận và diễn tiến triệu chứng hiện tại.";
    }
    return "Chưa ghi nhận tương tác nghiêm trọng trong bộ thuốc hiện tại. Tiếp tục rà soát định kỳ khi thay đổi đơn thuốc.";
  }, [displayedResult]);

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
      setReceiptNotice("Vui lòng nhập nội dung OCR/text trước khi phân tích.");
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
          ? `Nhận diện được ${detections.length} thuốc từ nội dung.`
          : "Chưa nhận diện được thuốc từ nội dung này."
      );
    } catch (error) {
      setReceiptNotice(error instanceof Error ? error.message : "Không thể nhận diện nội dung.");
    } finally {
      setIsScanning(false);
    }
  };

  const onScanReceiptFile = async () => {
    if (!receiptFile) {
      setReceiptNotice("Vui lòng chọn file đơn thuốc/hóa đơn trước khi quét.");
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
        detections.length ? `Nhận diện được ${detections.length} thuốc từ file.` : "Không nhận diện được thuốc trong file."
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

  const onConfirmAllLowConfidence = (confirmed: boolean) => {
    if (!receiptDetections.length) return;
    const nextConfirmed = { ...confirmedDetectionKeys };
    receiptDetections.forEach((item, index) => {
      if (!isLowConfidenceDetection(item)) return;
      const key = getDetectionKey(item, index);
      nextConfirmed[key] = confirmed;
    });
    setConfirmedDetectionKeys(nextConfirmed);
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
        // ignore duplicate
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
        allergies: includeHerbalOverlay ? parseFreeTextList(allergiesInput) : []
      });
      setAutoResult(result);
    } catch (error) {
      setAutoError(toCareguardUserMessage(error, "Không thể kiểm tra tương tác thuốc lúc này. Vui lòng thử lại."));
    } finally {
      setAutoChecking(false);
    }
  };

  const onRunAdvancedAnalyze = async () => {
    if (!medicationNames.length) {
      setManualError("Cần ít nhất 1 thuốc trong tủ để chạy phân tích nâng cao.");
      return;
    }

    const labsPayload = includeLabs ? parseLabsInput(labsInput) : {};
    if (includeAgeRisk && ageInput.trim()) {
      const parsedAge = Number(ageInput.trim());
      if (Number.isFinite(parsedAge) && parsedAge > 0) {
        labsPayload.age = parsedAge;
      }
    }

    setManualError("");
    setManualChecking(true);
    try {
      const response = await analyzeCareguard({
        symptoms: includeSymptoms ? parseFreeTextList(symptomsInput) : [],
        labs: labsPayload,
        medications: medicationNames,
        allergies: includeHerbalOverlay ? parseFreeTextList(allergiesInput) : []
      });
      setManualResult(normalizeCareguardResult(response));
    } catch (error) {
      setManualError(
        toCareguardUserMessage(error, "Không thể chạy phân tích nâng cao lúc này. Vui lòng thử lại.")
      );
    } finally {
      setManualChecking(false);
    }
  };

  if (consentLoading) {
    return (
      <PageShell title="CLARA CareGuard" variant="plain">
        <section className="rounded-3xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm">
          <p className="text-base font-semibold text-[var(--text-primary)]">Đang kiểm tra điều khoản sử dụng y tế...</p>
        </section>
      </PageShell>
    );
  }

  if (!consentAccepted) {
    return (
      <PageShell title="CLARA CareGuard" variant="plain">
        <section className="rounded-3xl border border-amber-300 bg-amber-50 p-6 shadow-sm dark:border-amber-800 dark:bg-amber-950/25">
          <p className="text-xs font-semibold uppercase tracking-widest text-amber-800 dark:text-amber-200">Yêu cầu xác nhận điều khoản y tế</p>
          <h2 className="mt-2 text-2xl font-bold text-[var(--text-primary)]">Tuyên bố miễn trừ trách nhiệm y tế</h2>
          <p className="mt-3 text-sm leading-7 text-[var(--text-secondary)]">
            CLARA hỗ trợ cảnh báo tương tác thuốc và phân tích an toàn, không thay thế bác sĩ kê đơn/chẩn đoán.
            Vui lòng đọc và xác nhận điều khoản trước khi dùng Trung tâm Phân tích An toàn.
          </p>
          <p className="mt-3 text-sm text-[var(--text-secondary)]">
            Xem đầy đủ tại{" "}
            <Link className="font-semibold text-blue-700 underline dark:text-blue-300" href="/legal/consent">
              Đồng thuận sử dụng y tế
            </Link>
            {" "}và{" "}
            <Link className="font-semibold text-blue-700 underline dark:text-blue-300" href="/legal/privacy">
              Chính sách quyền riêng tư
            </Link>
            . Phiên bản: <span className="font-semibold">{consentRequiredVersion || "-"}</span>
          </p>

          <label className="mt-4 flex cursor-pointer items-start gap-3 rounded-2xl border border-amber-200 bg-white p-4 dark:border-amber-800 dark:bg-slate-900">
            <input
              type="checkbox"
              className="mt-1 h-5 w-5"
              checked={consentChecked}
              onChange={(event) => setConsentChecked(event.target.checked)}
            />
            <span className="text-sm font-medium leading-6 text-[var(--text-primary)]">
              Tôi đã đọc, hiểu và đồng ý với tuyên bố miễn trừ trách nhiệm y tế của CLARA.
            </span>
          </label>

          <button
            type="button"
            onClick={onAcceptConsent}
            disabled={!consentChecked || acceptingConsent}
            className="mt-5 min-h-11 rounded-xl bg-[#003461] px-6 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          >
            {acceptingConsent ? "Đang lưu xác nhận..." : "Đồng ý và tiếp tục"}
          </button>

          {consentError ? <p className="mt-3 text-sm text-red-700 dark:text-red-300">{consentError}</p> : null}
        </section>
      </PageShell>
    );
  }

  return (
    <PageShell title="" description="" variant="plain">
      <div className="space-y-6 pb-8">
        <section className="rounded-3xl border border-[#c2c6d1]/20 bg-[#f7f9fb] p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="text-3xl font-extrabold tracking-tight text-[#003461] dark:text-[#93efee]">Trung tâm Phân tích An toàn</h1>
              <p className="mt-1 text-sm text-[#424750] dark:text-slate-300">Không gian phân tích tương tác thuốc chuẩn lâm sàng, dùng dữ liệu backend thật.</p>
            </div>
            <div className="inline-flex items-center gap-2 rounded-full bg-[#93efee] px-4 py-2 text-xs font-bold uppercase tracking-wide text-[#006e6e] ring-1 ring-[#93efee]/40 dark:bg-[#1f4876]/40 dark:text-[#93efee]">
              <span className="material-symbols-outlined text-[14px]" style={{ fontVariationSettings: "'FILL' 1" }}>verified_user</span>
              Chế độ an toàn độc lập: Dữ liệu nhập không tự lưu vào tủ thuốc cá nhân
            </div>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <article className="rounded-2xl border-2 border-dashed border-[#93efee]/60 bg-white p-8 shadow-sm transition-all hover:shadow-md dark:border-[#1f4876] dark:bg-slate-900">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-[#93efee]/40 text-[#003461]">
              <span className="material-symbols-outlined text-3xl">cloud_upload</span>
            </div>
            <h3 className="text-center text-lg font-bold text-[#003461] dark:text-[#93efee]">Tải lên hoặc quét OCR</h3>
            <p className="mx-auto mt-2 max-w-sm text-center text-sm text-[#424750] dark:text-slate-300">
              Thả đơn thuốc, tóm tắt ra viện hoặc nhãn thuốc để trích xuất dữ liệu thuốc từ OCR backend thật.
            </p>

            <input
              ref={hiddenFileInputRef}
              type="file"
              accept="image/*,.pdf"
              className="hidden"
              onChange={(event: ChangeEvent<HTMLInputElement>) => setReceiptFile(event.target.files?.[0] ?? null)}
            />
            <input
              ref={cameraInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              className="hidden"
              onChange={(event: ChangeEvent<HTMLInputElement>) => setReceiptFile(event.target.files?.[0] ?? null)}
            />

            <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
              <button
                type="button"
                onClick={() => hiddenFileInputRef.current?.click()}
                className="rounded-lg bg-[#003461] px-6 py-2 text-sm font-bold text-white transition hover:opacity-90"
              >
                Chọn tệp
              </button>
              <button
                type="button"
                onClick={() => cameraInputRef.current?.click()}
                className="rounded-lg border border-[#003461] px-6 py-2 text-sm font-bold text-[#003461] transition hover:bg-[#eceef0] dark:border-[#93efee] dark:text-[#93efee] dark:hover:bg-slate-800"
              >
                Mở camera
              </button>
              <button
                type="button"
                onClick={onScanReceiptFile}
                disabled={isScanning || !receiptFile}
                className="rounded-lg bg-[#004b87] px-6 py-2 text-sm font-bold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isScanning ? "Đang quét..." : "Phân tích tệp OCR"}
              </button>
            </div>
            {receiptFile ? (
              <p className="mt-3 text-center text-xs text-[#424750] dark:text-slate-300">Đã chọn tệp: {receiptFile.name}</p>
            ) : null}
          </article>

          <article className="flex flex-col rounded-2xl border border-[#c2c6d1]/30 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="flex items-center gap-2 text-lg font-bold text-[#003461] dark:text-[#93efee]">
                <span className="material-symbols-outlined">edit_note</span>
                Ghi chú lâm sàng
              </h3>
              <span className="text-[10px] font-bold uppercase tracking-widest text-[#727781]">Nhập liệu ngôn ngữ tự nhiên</span>
            </div>
            <textarea
              value={receiptTextInput}
              onChange={(event) => setReceiptTextInput(event.target.value)}
              className="min-h-[220px] w-full flex-1 rounded-lg border border-[#c2c6d1]/30 bg-[#f2f4f6] p-4 text-sm text-[#191c1e] focus:ring-2 focus:ring-[#003461]/20 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
              placeholder="Dán danh sách thuốc thô hoặc ghi chú lâm sàng ngắn (ví dụ: Warfarin 5mg mỗi ngày + Ibuprofen trị đau lưng)"
            />
            <div className="mt-4 flex justify-end">
              <button
                type="button"
                onClick={onRecognizeReceiptText}
                disabled={isScanning}
                className="inline-flex items-center gap-2 rounded-lg bg-[#93efee] px-6 py-2 text-sm font-bold text-[#006e6e] transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <span className="material-symbols-outlined text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>bolt</span>
                {isScanning ? "Đang phân tích..." : "Phân tích văn bản"}
              </button>
            </div>
          </article>
        </section>

        {receiptNotice ? (
          <p className="rounded-xl border border-[#c2c6d1]/20 bg-white px-4 py-3 text-sm text-[#424750] shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300" aria-live="polite">
            {receiptNotice}
          </p>
        ) : null}

        {receiptDetections.length > 0 ? (
          <section className="rounded-2xl border border-[#c2c6d1]/20 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <h4 className="text-sm font-bold uppercase tracking-widest text-[#003461] dark:text-[#93efee]">Thuốc đã nhận diện</h4>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => onConfirmAllLowConfidence(true)}
                  disabled={lowConfidenceDetectionCount === 0}
                  className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-700 transition hover:bg-amber-100 disabled:opacity-60 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-200"
                >
                  Xác nhận mục độ tin cậy thấp
                </button>
                <button
                  type="button"
                  onClick={onImportDetections}
                  disabled={pendingLowConfidenceDetections.length > 0}
                  className="rounded-lg bg-[#003461] px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Nhập vào {cabinetLabel}
                </button>
              </div>
            </div>

            {pendingLowConfidenceDetections.length > 0 ? (
              <p className="mb-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-700 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-200">
                Còn {pendingLowConfidenceDetections.length}/{lowConfidenceDetectionCount} mục low-confidence cần xác nhận trước khi import.
              </p>
            ) : null}

            <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {receiptDetections.map((item, index) => {
                const key = getDetectionKey(item, index);
                const isLowConfidence = isLowConfidenceDetection(item);
                const isConfirmed = Boolean(confirmedDetectionKeys[key]);
                return (
                  <li key={key} className="rounded-xl border border-[#c2c6d1]/20 bg-[#f7f9fb] p-3 dark:border-slate-700 dark:bg-slate-950">
                    <p className="text-sm font-bold text-[#003461] dark:text-[#93efee]">{item.drug_name}</p>
                    <p className="mt-1 text-xs text-[#424750] dark:text-slate-300">
                      {item.dosage ? `Liều: ${item.dosage}` : "Liều: Chưa có"}
                    </p>
                    <p className="mt-1 text-xs text-[#424750] dark:text-slate-300">Độ tin cậy: {Math.round(item.confidence * 100)}%</p>
                    <span
                      className={`mt-2 inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold ${getNormalizationClass(item.mapping_source)}`}
                    >
                      {getNormalizationLabel(item.mapping_source)}
                    </span>
                    {isLowConfidence ? (
                      <label className="mt-2 flex items-center gap-2 text-xs font-medium text-[#424750] dark:text-slate-300">
                        <input
                          type="checkbox"
                          checked={isConfirmed}
                          onChange={() => onConfirmDetection(key)}
                          className="h-4 w-4"
                        />
                        Xác nhận thủ công
                      </label>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </section>
        ) : null}

        <section className="rounded-2xl border border-[#c2c6d1]/20 bg-[#eceef0] p-4 dark:border-slate-800 dark:bg-slate-900">
          <div className="flex flex-wrap items-center gap-6">
            <span className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-[#424750] dark:text-slate-300">
              <span className="material-symbols-outlined text-[16px]">tune</span>
              Tham số nâng cao
            </span>

            <label className="inline-flex items-center gap-2 text-sm text-[#191c1e] dark:text-slate-200">
              <input
                type="checkbox"
                checked={includeAgeRisk}
                onChange={(event) => setIncludeAgeRisk(event.target.checked)}
                className="h-4 w-4"
              />
              Rủi ro theo tuổi
            </label>
            <label className="inline-flex items-center gap-2 text-sm text-[#191c1e] dark:text-slate-200">
              <input
                type="checkbox"
                checked={includeLabs}
                onChange={(event) => setIncludeLabs(event.target.checked)}
                className="h-4 w-4"
              />
              Kết quả xét nghiệm
            </label>
            <label className="inline-flex items-center gap-2 text-sm text-[#191c1e] dark:text-slate-200">
              <input
                type="checkbox"
                checked={includeSymptoms}
                onChange={(event) => setIncludeSymptoms(event.target.checked)}
                className="h-4 w-4"
              />
              Triệu chứng hiện tại
            </label>
            <label className="inline-flex items-center gap-2 text-sm text-[#191c1e] dark:text-slate-200">
              <input
                type="checkbox"
                checked={includeHerbalOverlay}
                onChange={(event) => setIncludeHerbalOverlay(event.target.checked)}
                className="h-4 w-4"
              />
              Thuốc không kê đơn / thảo dược
            </label>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <input
              value={ageInput}
              onChange={(event) => setAgeInput(event.target.value)}
              placeholder="Tuổi (không bắt buộc)"
              className="rounded-lg border border-[#c2c6d1]/30 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
            />
            <input
              value={allergiesInput}
              onChange={(event) => setAllergiesInput(event.target.value)}
              placeholder="Dị ứng / OTC / thảo dược"
              className="rounded-lg border border-[#c2c6d1]/30 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
            />
            <input
              value={symptomsInput}
              onChange={(event) => setSymptomsInput(event.target.value)}
              placeholder="Triệu chứng (ngăn cách bằng dấu phẩy)"
              className="rounded-lg border border-[#c2c6d1]/30 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
            />
            <input
              value={labsInput}
              onChange={(event) => setLabsInput(event.target.value)}
              placeholder="Xét nghiệm: egfr=28, creatinine=2.1"
              className="rounded-lg border border-[#c2c6d1]/30 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
            />
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={onRunAutoDdi}
              disabled={autoChecking || cabinet.length === 0}
              className="rounded-lg bg-[#003461] px-5 py-2 text-sm font-bold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {autoChecking ? "Đang kiểm tra tương tác..." : "Kiểm tra tương tác thuốc"}
            </button>
            <button
              type="button"
              onClick={onRunAdvancedAnalyze}
              disabled={manualChecking || cabinet.length === 0}
              className="rounded-lg border border-[#003461] px-5 py-2 text-sm font-bold text-[#003461] transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-60 dark:border-[#93efee] dark:text-[#93efee] dark:hover:bg-slate-800"
            >
              {manualChecking ? "Đang phân tích kỹ hơn..." : "Phân tích kỹ hơn"}
            </button>
            <span className="text-xs text-[#727781] dark:text-slate-400">Số thuốc trong tủ: {cabinetStats.total}</span>
          </div>

          {autoError ? <p className="mt-3 text-sm text-red-700 dark:text-red-300">{autoError}</p> : null}
          {manualError ? <p className="mt-2 text-sm text-red-700 dark:text-red-300">{manualError}</p> : null}
        </section>

        <section className="grid grid-cols-1 gap-6 md:grid-cols-12">
          <article className="md:col-span-4 flex flex-col items-center rounded-2xl border border-white bg-white/80 p-8 text-center shadow-xl backdrop-blur-xl dark:border-slate-700 dark:bg-slate-900/80">
            <h4 className="mb-6 text-sm font-bold uppercase tracking-widest text-[#424750] dark:text-slate-300">Mức rủi ro tương tác</h4>
            <div className="relative mb-4 flex h-48 w-48 items-center justify-center">
              <svg className="h-full w-full -rotate-90" viewBox="0 0 192 192">
                <circle cx="96" cy="96" r="88" fill="transparent" stroke="currentColor" strokeWidth="8" className="text-[#e0e3e5] dark:text-slate-700" />
                <circle
                  cx="96"
                  cy="96"
                  r="88"
                  fill="transparent"
                  stroke="currentColor"
                  strokeWidth="12"
                  strokeLinecap="round"
                  strokeDasharray={RISK_GAUGE_CIRCUMFERENCE}
                  strokeDashoffset={gaugeOffset}
                  className={aggregateRiskScore >= 70 ? "text-[#ba1a1a]" : aggregateRiskScore >= 45 ? "text-amber-500" : "text-emerald-500"}
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-5xl font-extrabold text-[#ba1a1a] dark:text-red-300">{displayedResult ? aggregateRiskScore : "--"}</span>
                <span className="text-[10px] font-bold uppercase text-[#727781] dark:text-slate-400">{displayedResult ? aggregateRiskLabel : "Chưa có kết quả"}</span>
              </div>
            </div>
            <p className="text-sm leading-6 text-[#424750] dark:text-slate-300">
              {getRiskScoreMeaning(displayedResult, aggregateRiskScore)}
            </p>
            <div className="mt-6 flex h-1.5 w-full overflow-hidden rounded-full bg-[#eceef0] dark:bg-slate-700">
              <div className="h-full w-1/4 bg-emerald-400" />
              <div className="h-full w-1/4 bg-yellow-400" />
              <div className="h-full w-1/4 bg-orange-500" />
              <div className="h-full w-1/4 bg-[#ba1a1a]" />
            </div>
          </article>

          <article className="md:col-span-8 flex flex-col gap-4">
            {visibleAlerts.length > 0 ? (
              visibleAlerts.map((alert, index) => {
                const major = alert.tone === "major";
                return (
                  <div
                    key={`${alert.title}-${index}`}
                    className={`rounded-xl border-l-4 p-6 shadow-sm transition-shadow hover:shadow-md ${
                      major
                        ? "border-[#ba1a1a] bg-white dark:bg-slate-900"
                        : "border-yellow-500 bg-white dark:bg-slate-900"
                    } border border-[#c2c6d1]/20 dark:border-slate-800`}
                  >
                    <div className="mb-2 flex items-start justify-between gap-3">
                      <h5 className="text-lg font-bold text-[#003461] dark:text-[#93efee]">{alert.title}</h5>
                      <span
                        className={`rounded px-2 py-1 text-[10px] font-bold uppercase tracking-widest ${
                          major ? "bg-[#ba1a1a] text-white" : "bg-yellow-500 text-white"
                        }`}
                      >
                        {major ? "Nặng" : "Trung bình"}
                      </span>
                    </div>
                    <p className="text-sm leading-relaxed text-[#424750] dark:text-slate-300">{alert.details}</p>
                    <div className="mt-4 flex items-center justify-between rounded-lg bg-[#f2f4f6] p-3 dark:bg-slate-800">
                      <div className="flex items-center gap-2 text-xs font-semibold text-[#006e6e] dark:text-[#93efee]">
                        <span className="material-symbols-outlined text-sm">lightbulb</span>
                        Khuyến nghị: Rà soát với bác sĩ điều trị
                      </div>
                      <button
                        type="button"
                        className="text-xs font-bold text-[#003461] hover:underline dark:text-[#93efee]"
                      >
                        Xem bằng chứng
                      </button>
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="rounded-xl border border-[#c2c6d1]/20 bg-white p-6 text-sm text-[#424750] shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
                Chưa có cảnh báo tương tác. Hãy thêm ít nhất 2 thuốc vào tủ rồi bấm Kiểm tra tương tác thuốc.
              </div>
            )}

            <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-[#003461] to-[#004b87] p-6 text-white shadow-xl">
              <div className="absolute -bottom-12 -right-12 opacity-10">
                <span className="material-symbols-outlined text-[160px]">psychology</span>
              </div>
              <div className="relative z-10 flex gap-4">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-white/20">
                  <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>smart_toy</span>
                </div>
                <div className="flex-1">
                  <div className="mb-2 flex items-start justify-between gap-2">
                    <h5 className="text-lg font-bold">CLARA giải thích kết quả</h5>
                    <span className="rounded bg-[#93efee] px-2 py-1 text-[10px] font-bold uppercase tracking-widest text-[#003461]">Gợi ý an toàn</span>
                  </div>
                  <p className="text-sm leading-relaxed text-[#d3e4ff]">{aiInsight}</p>
                  <div className="mt-4 flex flex-wrap gap-3">
                    <button
                      type="button"
                      className="rounded-lg bg-white px-4 py-2 text-xs font-extrabold uppercase tracking-tight text-[#003461] transition hover:bg-[#eceef0]"
                    >
                      Đọc khuyến nghị
                    </button>
                    <button type="button" className="inline-flex items-center gap-1 text-xs font-bold text-white/80 hover:text-white">
                      <span className="material-symbols-outlined text-sm">visibility</span>
                      Xem chi tiết
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </article>
        </section>

        <section className="grid grid-cols-1 gap-6 xl:grid-cols-12">
          <article className="rounded-2xl border border-[#c2c6d1]/20 bg-white p-5 shadow-sm xl:col-span-7 dark:border-slate-800 dark:bg-slate-900">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <h4 className="text-sm font-bold uppercase tracking-widest text-[#003461] dark:text-[#93efee]">Tủ thuốc</h4>
              <div className="flex flex-wrap gap-2">
                <span className="rounded-full bg-[#eceef0] px-2.5 py-1 text-xs font-semibold text-[#424750] dark:bg-slate-800 dark:text-slate-300">
                  Tổng: {cabinetStats.total}
                </span>
                <span className="rounded-full bg-[#93efee]/30 px-2.5 py-1 text-xs font-semibold text-[#006e6e] dark:bg-[#1f4876]/40 dark:text-[#93efee]">
                  OCR: {cabinetStats.fromOcr}
                </span>
              </div>
            </div>

            <div className="mb-3 flex flex-wrap items-center gap-2">
              <input
                value={manualMedicationInput}
                onChange={(event) => setManualMedicationInput(event.target.value)}
                placeholder="Thêm nhanh thuốc (ngăn cách bằng dấu phẩy)"
                className="min-w-[260px] flex-1 rounded-lg border border-[#c2c6d1]/30 bg-[#f7f9fb] px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
              />
              <button
                type="button"
                onClick={onAddManualMedication}
                className="rounded-lg border border-[#003461] px-4 py-2 text-xs font-bold text-[#003461] hover:bg-[#eceef0] dark:border-[#93efee] dark:text-[#93efee] dark:hover:bg-slate-800"
              >
                Thêm
              </button>
              <button
                type="button"
                onClick={refreshCabinet}
                className="rounded-lg border border-[#c2c6d1] px-4 py-2 text-xs font-bold text-[#424750] hover:bg-[#eceef0] dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                Làm mới
              </button>
            </div>

            {cabinetLoading ? <p className="text-sm text-[#424750] dark:text-slate-300">Đang tải tủ thuốc...</p> : null}
            {cabinetError ? <p className="text-sm text-red-700 dark:text-red-300">{cabinetError}</p> : null}
            {cabinetNotice ? <p className="text-sm text-[#424750] dark:text-slate-300">{cabinetNotice}</p> : null}

            {cabinet.length > 0 ? (
              <ul className="mt-2 grid gap-2 md:grid-cols-2">
                {cabinet.map((item) => (
                  <li key={item.id} className="rounded-lg border border-[#c2c6d1]/20 bg-[#f7f9fb] p-3 dark:border-slate-700 dark:bg-slate-950">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="text-sm font-semibold text-[#003461] dark:text-[#93efee]">{item.drug_name}</p>
                        <p className="mt-1 text-xs text-[#424750] dark:text-slate-300">{item.dosage || "Liều: Chưa có"}</p>
                        <span
                          className={`mt-2 inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold ${getNormalizationClass(item.normalization_source)}`}
                        >
                          {getNormalizationLabel(item.normalization_source)}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => onRemoveCabinetItem(item.id)}
                        className="rounded border border-red-200 px-2 py-1 text-[11px] font-semibold text-red-700 hover:bg-red-50 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-950/40"
                      >
                        Xóa
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              !cabinetLoading && <p className="text-sm text-[#424750] dark:text-slate-300">Tủ thuốc đang trống.</p>
            )}
          </article>

          <article className="rounded-2xl border border-[#c2c6d1]/20 bg-white p-5 shadow-sm xl:col-span-5 dark:border-slate-800 dark:bg-slate-900">
            <h4 className="mb-3 text-sm font-bold uppercase tracking-widest text-[#003461] dark:text-[#93efee]">Tín hiệu vận hành</h4>

            <div className="space-y-3">
              <div className="rounded-lg border border-[#c2c6d1]/20 bg-[#f7f9fb] p-3 dark:border-slate-700 dark:bg-slate-950">
                <p className="text-[11px] font-bold uppercase tracking-wide text-[#727781]">Cách đối chiếu</p>
                <div className={`mt-2 inline-flex rounded-full border px-2 py-1 text-xs font-semibold ${getModeBadgeClass(displayedResult?.mode ?? null)}`}>
                  {getModeBadgeLabel(displayedResult?.mode ?? null)}
                </div>
              </div>

              <div className="rounded-lg border border-[#c2c6d1]/20 bg-[#f7f9fb] p-3 dark:border-slate-700 dark:bg-slate-950">
                <p className="text-[11px] font-bold uppercase tracking-wide text-[#727781]">Mức rủi ro</p>
                <div className={`mt-2 inline-flex rounded-full border px-2 py-1 text-xs font-semibold ${getRiskBadgeClass(displayedResult?.riskTier ?? null)}`}>
                  {formatCareguardRiskLabel(displayedResult?.riskTier ?? null)}
                </div>
              </div>

              <div className="rounded-lg border border-[#c2c6d1]/20 bg-[#f7f9fb] p-3 dark:border-slate-700 dark:bg-slate-950">
                <p className="text-[11px] font-bold uppercase tracking-wide text-[#727781]">Độ phủ bằng chứng</p>
                <p className="mt-2 text-sm text-[#424750] dark:text-slate-300">
                  Nguồn: {displayedResult?.attribution?.sourceCount ?? 0} • Trích dẫn: {displayedResult?.attribution?.citationCount ?? 0}
                </p>
                {displayedResult?.attribution?.sources?.length ? (
                  <p className="mt-1 text-xs text-[#424750] dark:text-slate-400">
                    {displayedResult.attribution.sources.map((source) => source.name).join(", ")}
                  </p>
                ) : null}
              </div>

            </div>
          </article>
        </section>
      </div>
    </PageShell>
  );
}
