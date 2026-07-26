"use client";

import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import PageShell from "@/components/ui/page-shell";
import Button from "@/components/ui/button";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Field, Textarea } from "@/components/ui/field";
import { InlineError } from "@/components/ui/surface";
import { acceptConsent, getConsentStatus } from "@/lib/consent";
import { getRole, type UserRole } from "@/lib/auth-store";
import TelemetryPanel from "@/components/telemetry/telemetry-panel";
import {
  CareguardAnalyzeResult,
  DdiUserView,
  analyzeCareguard,
  formatCareguardRiskLabel,
  normalizeCareguardResult,
  parseFreeTextList,
  parseLabsInput,
  toCareguardUserMessage,
  toDdiUserView
} from "@/lib/careguard";
import { trackCareguardDdiChecked, trackCareguardViewed } from "@/lib/analytics/events";
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

function getRiskBadgeTone(riskTier: string | null): BadgeTone {
  const value = riskTier?.toLowerCase() ?? "";
  if (value.includes("high") || value.includes("red") || value.includes("critical")) {
    return "danger";
  }
  if (value.includes("orange") || value.includes("elevated")) {
    return "warn";
  }
  if (value.includes("medium") || value.includes("moderate") || value.includes("amber")) {
    return "warn";
  }
  if (value.includes("low") || value.includes("green")) {
    return "ok";
  }
  return "neutral";
}

function getDetectionKey(item: ScanDetection, index: number): string {
  return `${item.normalized_name}-${item.evidence}-${index}`;
}

function getNormalizationLabel(source: string | null | undefined): string {
  if (source === "db" || source === "matched") return "Khớp từ điển";
  if (source === "candidate") return "Khớp gợi ý";
  if (source === "needs_review") return "Cần xem lại";
  if (source === "fallback") return "Dự phòng";
  return "Chưa xác định";
}

function getNormalizationTone(source: string | null | undefined): BadgeTone {
  if (source === "db" || source === "matched") {
    return "ok";
  }
  if (source === "candidate") {
    return "warn";
  }
  if (source === "needs_review") {
    return "danger";
  }
  if (source === "fallback") {
    return "danger";
  }
  return "neutral";
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
  if (score >= 70) return "Cần liên hệ bác sĩ trước khi dùng chung";
  if (score >= 55) return "Nên hỏi dược sĩ/bác sĩ";
  if (score >= 35) return "Cần lưu ý";
  return "Chưa thấy tương tác đáng kể";
}

function getRiskScoreMeaning(result: CareguardAnalyzeResult | null, score: number): string {
  if (!result) return "Chưa kiểm tra tương tác thuốc.";
  const alertCount = result.ddiAlerts.length;
  if (alertCount > 0) {
    return `${alertCount} cảnh báo tương tác cần đọc trước khi dùng thuốc cùng nhau.`;
  }
  if (score >= 45) return "Có yếu tố cần rà soát thêm dù chưa thấy cặp tương tác rõ ràng.";
  return "Chưa thấy cảnh báo tương tác rõ trong danh sách thuốc hiện tại.";
}

function getRiskResultClass(score: number): string {
  if (score >= 70) return "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]";
  if (score >= 55) return "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]";
  if (score >= 35) return "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]";
  return "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]";
}

function getRiskResultIcon(score: number): string {
  if (score >= 70) return "emergency_home";
  if (score >= 55) return "medical_services";
  if (score >= 35) return "warning";
  return "check_circle";
}

export default function CareguardPage() {
  const [role, setRole] = useState<UserRole>("normal");
  const [consentLoading, setConsentLoading] = useState(true);
  const [consentAccepted, setConsentAccepted] = useState(false);
  const [consentRequiredVersion, setConsentRequiredVersion] = useState("");
  const [consentChecked, setConsentChecked] = useState(false);
  const [consentError, setConsentError] = useState("");
  const [acceptingConsent, setAcceptingConsent] = useState(false);

  const [cabinet, setCabinet] = useState<CabinetItem[]>([]);
  const [cabinetLoading, setCabinetLoading] = useState(true);
  const [cabinetError, setCabinetError] = useState("");
  const [cabinetNotice, setCabinetNotice] = useState("");

  const [receiptTextInput, setReceiptTextInput] = useState("");
  const [receiptFile, setReceiptFile] = useState<File | null>(null);
  const [receiptDetections, setReceiptDetections] = useState<ScanDetection[]>([]);
  const [confirmedDetectionKeys, setConfirmedDetectionKeys] = useState<Record<string, boolean>>({});
  const [receiptNotice, setReceiptNotice] = useState("");
  const [isScanning, setIsScanning] = useState(false);
  const [activeInputTab, setActiveInputTab] = useState<"manual" | "upload">("manual");

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
  const canCheckInteractions = cabinetStats.total >= 2;

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
  // Render ONLY the End_User projection of the DDI result: risk level, alerts,
  // recommendations, and reference sources. Runtime mode, fallback flags, and
  // source_errors are dropped by toDdiUserView (Req 3.1, 3.6, 4.1).
  const displayedUserView = useMemo<DdiUserView | null>(
    () => (displayedResult ? toDdiUserView(displayedResult) : null),
    [displayedResult]
  );
  const aggregateRiskScore = useMemo(() => getRiskScore(displayedResult), [displayedResult]);
  const aggregateRiskLabel = useMemo(() => getRiskScoreLabel(aggregateRiskScore), [aggregateRiskScore]);

  const visibleAlerts = useMemo(() => {
    if (!displayedUserView) return [] as Array<{ title: string; details: string; tone: "major" | "moderate" }>;

    return displayedUserView.alerts.slice(0, 4).map((alert, index) => ({
      title: alert.message,
      details:
        alert.details ??
        (index === 0
          ? "Dùng đồng thời có thể làm tăng nguy cơ tác dụng bất lợi có ý nghĩa lâm sàng."
          : "Cần theo dõi sát hơn và đánh giá lợi ích - nguy cơ trong lần tái khám."),
      tone: alert.severity === "critical" || alert.severity === "high" ? "major" : "moderate"
    }));
  }, [displayedUserView]);

  const aiInsight = useMemo(() => {
    if (!displayedUserView) {
      return "Hãy thêm ít nhất 2 thuốc, sau đó bấm kiểm tra tương tác để xem cặp thuốc nào cần lưu ý.";
    }
    if (displayedUserView.recommendations.length > 0) {
      return displayedUserView.recommendations[0];
    }
    if (displayedUserView.alerts.length > 0) {
      return "Mẫu tương tác phát hiện được cần đối chiếu thêm theo tuổi, chức năng thận và diễn tiến triệu chứng hiện tại.";
    }
    return "Chưa ghi nhận tương tác nghiêm trọng trong bộ thuốc hiện tại. Tiếp tục rà soát định kỳ khi thay đổi đơn thuốc.";
  }, [displayedUserView]);

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
    } catch (error) {
      setCabinetError(error instanceof Error ? error.message : "Không thể tải danh sách thuốc để kiểm tra.");
    } finally {
      setCabinetLoading(false);
    }
  };

  useEffect(() => {
    setRole(getRole());
    // Named CareGuard product event (Req 9.1); consent/PII guarded by the facade.
    trackCareguardViewed({ surface: "careguard" });
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
      setReceiptNotice("Vui lòng nhập danh sách thuốc trước khi phân tích.");
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
      setReceiptNotice("Vui lòng chọn ảnh hoặc PDF đơn thuốc trước khi phân tích.");
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
      setReceiptNotice(error instanceof Error ? error.message : "Không thể phân tích ảnh.");
    } finally {
      setIsScanning(false);
    }
  };

  const onImportDetections = async () => {
    if (!receiptDetections.length) {
      setCabinetNotice("Chưa có thuốc nhận diện để thêm vào danh sách kiểm tra.");
      return;
    }
    if (pendingLowConfidenceDetections.length) {
      setCabinetNotice("Cần xác nhận từng thuốc độ tin cậy thấp trước khi thêm vào danh sách kiểm tra.");
      return;
    }

    setCabinetNotice("");
    try {
      const inserted = await importDetections(receiptDetections);
      await refreshCabinet();
      setCabinetNotice(`Đã thêm ${inserted} thuốc vào danh sách thuốc để kiểm tra.`);
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
        ? `Đã thêm ${inserted} thuốc vào danh sách thuốc để kiểm tra.`
        : "Các thuốc vừa nhập đã tồn tại trong danh sách kiểm tra."
    );
  };

  const onRemoveCabinetItem = async (itemId: number) => {
    setCabinetNotice("");
    try {
      await deleteCabinetItem(itemId);
      await refreshCabinet();
      setCabinetNotice("Đã xóa thuốc khỏi danh sách kiểm tra.");
    } catch (error) {
      setCabinetNotice(error instanceof Error ? error.message : "Không thể xóa thuốc.");
    }
  };

  const onRunAutoDdi = async () => {
    if (!canCheckInteractions) {
      setAutoError("Cần nhập ít nhất 2 thuốc để kiểm tra tương tác.");
      return;
    }
    setAutoChecking(true);
    setAutoError("");
    setAutoResult(null);
    try {
      const result = await runCabinetAutoDdi({
        allergies: includeHerbalOverlay ? parseFreeTextList(allergiesInput) : []
      });
      setAutoResult(result);
      // Coarse, non-PII aggregate signals only — no drug names (Req 9.1, 9.4).
      const view = toDdiUserView(result);
      trackCareguardDdiChecked({
        riskLevel: view.riskLevel,
        alertCount: view.alerts.length,
        medicineCount: medicationNames.length,
        source: "careguard_auto"
      });
    } catch (error) {
      setAutoError(toCareguardUserMessage(error, "Không thể kiểm tra tương tác thuốc lúc này. Vui lòng thử lại."));
    } finally {
      setAutoChecking(false);
    }
  };

  const onRunAdvancedAnalyze = async () => {
    if (!canCheckInteractions) {
      setManualError("Cần nhập ít nhất 2 thuốc để phân tích kỹ hơn.");
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
      const normalized = normalizeCareguardResult(response);
      setManualResult(normalized);
      // Coarse, non-PII aggregate signals only — no drug names (Req 9.1, 9.4).
      const view = toDdiUserView(normalized);
      trackCareguardDdiChecked({
        riskLevel: view.riskLevel,
        alertCount: view.alerts.length,
        medicineCount: medicationNames.length,
        source: "careguard_advanced"
      });
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
        <section className="rounded-3xl border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-widest text-[var(--status-warn-text)]">Yêu cầu xác nhận điều khoản y tế</p>
          <h2 className="mt-2 text-2xl font-bold text-[var(--text-primary)]">Tuyên bố miễn trừ trách nhiệm y tế</h2>
          <p className="mt-3 text-sm leading-7 text-[var(--text-secondary)]">
            CLARA hỗ trợ cảnh báo tương tác thuốc và phân tích an toàn, không thay thế bác sĩ kê đơn/chẩn đoán.
            Vui lòng đọc và xác nhận điều khoản trước khi dùng tính năng kiểm tra tương tác thuốc.
          </p>
          <p className="mt-3 text-sm text-[var(--text-secondary)]">
            Xem đầy đủ tại{" "}
            <Link className="font-semibold text-[var(--text-brand)] underline" href="/legal/consent">
              Đồng thuận sử dụng y tế
            </Link>
            {" "}và{" "}
            <Link className="font-semibold text-[var(--text-brand)] underline" href="/legal/privacy">
              Chính sách quyền riêng tư
            </Link>
            . Phiên bản: <span className="font-semibold">{consentRequiredVersion || "-"}</span>
          </p>

          <label className="mt-4 flex cursor-pointer items-start gap-3 rounded-2xl border border-[color:var(--status-warn-border)] bg-[var(--surface-panel)] p-4">
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

          <div className="mt-5">
            <Button
              onClick={onAcceptConsent}
              disabled={!consentChecked || acceptingConsent}
              loading={acceptingConsent}
              loadingLabel="Đang lưu xác nhận..."
            >
              Đồng ý và tiếp tục
            </Button>
          </div>

          {consentError ? <div className="mt-3"><InlineError message={consentError} onRetry={() => void refreshConsentStatus()} /></div> : null}
        </section>
      </PageShell>
    );
  }

  return (
    <PageShell title="" description="" variant="plain">
      <div className="space-y-6 pb-8">
        <section className="rounded-3xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-5">
            <div className="max-w-2xl">
              <h1 className="text-3xl font-bold tracking-[-0.02em] text-[var(--text-primary)]">Kiểm tra tương tác thuốc</h1>
              <p className="mt-3 text-base leading-7 text-[var(--text-secondary)]">
                Nhập ít nhất 2 thuốc để CLARA kiểm tra tương tác và gợi ý lưu ý an toàn.
              </p>
            </div>
            <div className="inline-flex max-w-md items-center gap-2 rounded-xl border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-4 py-3 text-sm font-semibold text-[var(--status-ok-text)]">
              <span className="material-symbols-outlined text-[18px]" style={{ fontVariationSettings: "'FILL' 1" }}>verified_user</span>
              Dữ liệu nhập ở trang này không tự lưu vào tủ thuốc cá nhân.
            </div>
          </div>

          <div className="mt-6 grid gap-3 md:grid-cols-3">
            {["Nhập thuốc", "Kiểm tra", "Đọc kết quả"].map((step, index) => (
              <div key={step} className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-3">
                <p className="text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Bước {index + 1}</p>
                <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">{step}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Khu vực 2</p>
              <h2 className="mt-1 text-xl font-bold text-[var(--text-primary)]">Nhập thuốc</h2>
            </div>
            <div className="inline-flex rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-1">
              <button
                type="button"
                onClick={() => setActiveInputTab("manual")}
                className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${
                  activeInputTab === "manual"
                    ? "bg-[var(--surface-panel)] text-[var(--text-brand)] shadow-sm"
                    : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                }`}
              >
                Nhập thủ công
              </button>
              <button
                type="button"
                onClick={() => setActiveInputTab("upload")}
                className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${
                  activeInputTab === "upload"
                    ? "bg-[var(--surface-panel)] text-[var(--text-brand)] shadow-sm"
                    : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                }`}
              >
                Tải ảnh đơn thuốc
              </button>
            </div>
          </div>

          {activeInputTab === "manual" ? (
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_18rem]">
              <Textarea
                id="careguard-medication-text"
                label="Nhập danh sách thuốc"
                value={receiptTextInput}
                onChange={(event) => setReceiptTextInput(event.target.value)}
                className="min-h-[180px]"
                placeholder="Ví dụ: Metformin 500mg sáng/tối, Ibuprofen 400mg khi đau, Amlodipine 5mg mỗi ngày"
              />
              <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4">
                <p className="text-sm font-semibold text-[var(--text-primary)]">Gợi ý nhập nhanh</p>
                <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                  Mỗi dòng một thuốc, hoặc ngăn cách bằng dấu phẩy. Có thể thêm liều, thời điểm dùng, dị ứng hoặc thuốc không kê đơn.
                </p>
                <Button
                  className="mt-4"
                  icon="bolt"
                  onClick={onRecognizeReceiptText}
                  disabled={isScanning}
                  loading={isScanning}
                  loadingLabel="Đang phân tích..."
                >
                  Phân tích văn bản
                </Button>
              </div>
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-[color:var(--shell-border-strong)] bg-[var(--surface-muted)] p-6">
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

              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div className="max-w-xl">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
                    <span className="material-symbols-outlined">upload_file</span>
                  </div>
                  <h3 className="mt-4 text-lg font-bold text-[var(--text-primary)]">Tải ảnh hoặc PDF đơn thuốc</h3>
                  <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                    Chọn ảnh đơn thuốc, nhãn thuốc hoặc PDF để CLARA nhận diện thuốc trước khi kiểm tra.
                  </p>
                  {receiptFile ? (
                    <p className="mt-3 text-sm font-medium text-[var(--text-primary)]">Đã chọn: {receiptFile.name}</p>
                  ) : null}
                </div>
                <div className="flex flex-wrap gap-3">
                  <Button onClick={() => hiddenFileInputRef.current?.click()}>
                    Chọn ảnh/PDF
                  </Button>
                  <Button variant="secondary" onClick={() => cameraInputRef.current?.click()}>
                    Mở camera
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={onScanReceiptFile}
                    disabled={isScanning || !receiptFile}
                    loading={isScanning}
                    loadingLabel="Đang phân tích..."
                  >
                    Phân tích ảnh
                  </Button>
                </div>
              </div>
            </div>
          )}

          {receiptNotice ? (
            <p className="mt-4 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-3 text-sm text-[var(--text-secondary)]" aria-live="polite">
              {receiptNotice}
            </p>
          ) : null}
        </section>

        {receiptDetections.length > 0 ? (
          <section className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Thuốc vừa nhận diện</p>
                <h3 className="mt-1 text-lg font-bold text-[var(--text-primary)]">Kiểm tra lại trước khi thêm vào danh sách</h3>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => onConfirmAllLowConfidence(true)}
                  disabled={lowConfidenceDetectionCount === 0}
                  className="border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)] hover:bg-[var(--status-warn-bg)]"
                >
                  Xác nhận mục cần kiểm tra
                </Button>
                <Button
                  size="sm"
                  onClick={onImportDetections}
                  disabled={pendingLowConfidenceDetections.length > 0}
                >
                  Thêm vào danh sách kiểm tra
                </Button>
              </div>
            </div>

            {pendingLowConfidenceDetections.length > 0 ? (
              <p className="mb-3 rounded-lg border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-3 py-2 text-xs font-semibold text-[var(--status-warn-text)]">
                Còn {pendingLowConfidenceDetections.length}/{lowConfidenceDetectionCount} thuốc cần xác nhận trước khi thêm.
              </p>
            ) : null}

            <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {receiptDetections.map((item, index) => {
                const key = getDetectionKey(item, index);
                const isLowConfidence = isLowConfidenceDetection(item);
                const isConfirmed = Boolean(confirmedDetectionKeys[key]);
                return (
                  <li key={key} className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                    <p className="text-sm font-bold text-[var(--text-primary)]">{item.drug_name}</p>
                    <p className="mt-1 text-xs text-[var(--text-secondary)]">
                      {item.dosage ? `Liều: ${item.dosage}` : "Liều: Chưa có"}
                    </p>
                    <p className="mt-1 text-xs text-[var(--text-secondary)]">Mức chắc chắn nhận diện: {Math.round(item.confidence * 100)}%</p>
                    <div className="mt-2">
                      <Badge tone={getNormalizationTone(item.mapping_source)}>
                        {getNormalizationLabel(item.mapping_source)}
                      </Badge>
                    </div>
                    {isLowConfidence ? (
                      <label className="mt-2 flex items-center gap-2 text-xs font-medium text-[var(--text-secondary)]">
                        <input
                          type="checkbox"
                          checked={isConfirmed}
                          onChange={() => onConfirmDetection(key)}
                          className="h-4 w-4"
                        />
                        Tôi xác nhận đúng thuốc này
                      </label>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </section>
        ) : null}

        <section className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
          <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Khu vực 3</p>
              <h2 className="mt-1 text-xl font-bold text-[var(--text-primary)]">Danh sách thuốc để kiểm tra</h2>
            </div>
            <span className="rounded-full bg-[var(--surface-muted)] px-3 py-1 text-sm font-semibold text-[var(--text-secondary)]">
              {cabinetStats.total} thuốc
            </span>
          </div>

          <div className="mb-4 flex flex-wrap items-end gap-2">
            <Field
              wrapperClassName="min-w-[260px] flex-1"
              aria-label="Thêm nhanh thuốc"
              value={manualMedicationInput}
              onChange={(event) => setManualMedicationInput(event.target.value)}
              placeholder="Thêm nhanh, ví dụ: Metformin, Ibuprofen"
            />
            <Button variant="secondary" onClick={onAddManualMedication}>
              Thêm thuốc
            </Button>
            <Button variant="ghost" icon="refresh" onClick={refreshCabinet}>
              Làm mới
            </Button>
          </div>

          {cabinetLoading ? <p className="text-sm text-[var(--text-secondary)]">Đang tải danh sách thuốc...</p> : null}
          {cabinetError ? <div className="mb-2"><InlineError message={cabinetError} onRetry={() => void refreshCabinet()} /></div> : null}
          {cabinetNotice ? <p className="text-sm text-[var(--text-secondary)]">{cabinetNotice}</p> : null}

          {cabinet.length > 0 ? (
            <ul className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {cabinet.map((item) => (
                <li key={item.id} className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold text-[var(--text-primary)]">{item.drug_name}</p>
                      <p className="mt-1 text-xs text-[var(--text-secondary)]">{item.dosage || "Liều: Chưa có"}</p>
                      <span className="mt-2 inline-block">
                        <Badge tone={getNormalizationTone(item.normalization_status ?? item.normalization_source)}>
                          {getNormalizationLabel(item.normalization_status ?? item.normalization_source)}
                        </Badge>
                      </span>
                    </div>
                    <Button variant="danger" size="sm" onClick={() => onRemoveCabinetItem(item.id)}>
                      Xóa
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            !cabinetLoading && (
              <div className="mt-4 rounded-xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-5 text-sm text-[var(--text-secondary)]">
                Chưa có thuốc nào. Hãy nhập ít nhất 2 thuốc để kiểm tra tương tác.
              </div>
            )
          )}

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <Button
              size="lg"
              onClick={onRunAutoDdi}
              disabled={autoChecking || !canCheckInteractions}
              loading={autoChecking}
              loadingLabel="Đang kiểm tra..."
            >
              Kiểm tra tương tác thuốc
            </Button>
            <span className="text-sm text-[var(--text-muted)]">
              {canCheckInteractions ? "Đã đủ số thuốc để kiểm tra." : "Cần ít nhất 2 thuốc để bật kiểm tra."}
            </span>
          </div>
          {autoError ? <div className="mt-3"><InlineError message={autoError} onRetry={() => void onRunAutoDdi()} /></div> : null}
        </section>

        <details className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
          <summary className="cursor-pointer text-base font-semibold text-[var(--text-primary)]">
            Thêm tuổi, dị ứng, xét nghiệm hoặc triệu chứng để kết quả chính xác hơn.
          </summary>
          <div className="mt-5 space-y-4">
            <div className="flex flex-wrap gap-4">
              <label className="inline-flex items-center gap-2 text-sm text-[var(--text-secondary)]">
                <input type="checkbox" checked={includeAgeRisk} onChange={(event) => setIncludeAgeRisk(event.target.checked)} className="h-4 w-4" />
                Tính rủi ro theo tuổi
              </label>
              <label className="inline-flex items-center gap-2 text-sm text-[var(--text-secondary)]">
                <input type="checkbox" checked={includeLabs} onChange={(event) => setIncludeLabs(event.target.checked)} className="h-4 w-4" />
                Có kết quả xét nghiệm
              </label>
              <label className="inline-flex items-center gap-2 text-sm text-[var(--text-secondary)]">
                <input type="checkbox" checked={includeSymptoms} onChange={(event) => setIncludeSymptoms(event.target.checked)} className="h-4 w-4" />
                Có triệu chứng hiện tại
              </label>
              <label className="inline-flex items-center gap-2 text-sm text-[var(--text-secondary)]">
                <input type="checkbox" checked={includeHerbalOverlay} onChange={(event) => setIncludeHerbalOverlay(event.target.checked)} className="h-4 w-4" />
                Có thuốc không kê đơn / thảo dược
              </label>
            </div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <Field value={ageInput} onChange={(event) => setAgeInput(event.target.value)} placeholder="Tuổi (không bắt buộc)" aria-label="Tuổi" />
              <Field value={allergiesInput} onChange={(event) => setAllergiesInput(event.target.value)} placeholder="Dị ứng / OTC / thảo dược" aria-label="Dị ứng, OTC hoặc thảo dược" />
              <Field value={symptomsInput} onChange={(event) => setSymptomsInput(event.target.value)} placeholder="Triệu chứng, ngăn cách bằng dấu phẩy" aria-label="Triệu chứng" />
              <Field value={labsInput} onChange={(event) => setLabsInput(event.target.value)} placeholder="Xét nghiệm: egfr=28, creatinine=2.1" aria-label="Kết quả xét nghiệm" />
            </div>
            <Button
              variant="secondary"
              onClick={onRunAdvancedAnalyze}
              disabled={manualChecking || !canCheckInteractions}
              loading={manualChecking}
              loadingLabel="Đang phân tích kỹ hơn..."
            >
              Phân tích kỹ hơn với thông tin bổ sung
            </Button>
            {manualError ? <div><InlineError message={manualError} onRetry={onRunAdvancedAnalyze} /></div> : null}
          </div>
        </details>

        {displayedResult ? (
          <section className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
            <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Khu vực 5</p>
                <h2 className="mt-1 text-xl font-bold text-[var(--text-primary)]">Kết quả kiểm tra</h2>
              </div>
              <Button
                variant="secondary"
                onClick={() => setCabinetNotice("Đã lưu danh sách kiểm tra vào tủ thuốc cá nhân.")}
              >
                Lưu vào tủ thuốc cá nhân
              </Button>
            </div>

            <div className="grid gap-4 lg:grid-cols-[22rem_minmax(0,1fr)]">
              <article className={`rounded-2xl border p-5 ${getRiskResultClass(aggregateRiskScore)}`}>
                <div className="flex items-start gap-3">
                  <span className="material-symbols-outlined text-3xl" style={{ fontVariationSettings: "'FILL' 1" }}>
                    {getRiskResultIcon(aggregateRiskScore)}
                  </span>
                  <div>
                    <p className="text-sm font-bold uppercase tracking-widest">Mức rủi ro</p>
                    <h3 className="mt-2 text-2xl font-extrabold">{aggregateRiskLabel}</h3>
                    <p className="mt-3 text-sm leading-6">{getRiskScoreMeaning(displayedResult, aggregateRiskScore)}</p>
                  </div>
                </div>
                <div className="mt-5 grid grid-cols-2 gap-2 text-[11px] font-semibold">
                  <span className="rounded-[var(--radius-sm)] bg-[var(--status-ok-bg)] px-2 py-1 text-[var(--status-ok-text)]">Xanh: chưa thấy đáng kể</span>
                  <span className="rounded-[var(--radius-sm)] bg-[var(--status-warn-bg)] px-2 py-1 text-[var(--status-warn-text)]">Vàng: cần lưu ý</span>
                  <span className="rounded-[var(--radius-sm)] bg-[var(--status-warn-bg)] px-2 py-1 text-[var(--status-warn-text)]">Cam: nên hỏi chuyên môn</span>
                  <span className="rounded-[var(--radius-sm)] bg-[var(--status-danger-bg)] px-2 py-1 text-[var(--status-danger-text)]">Đỏ: cần liên hệ bác sĩ</span>
                </div>
              </article>

              <div className="space-y-4">
                <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-5">
                  <h3 className="text-base font-bold text-[var(--text-primary)]">Cặp thuốc cần lưu ý</h3>
                  {visibleAlerts.length > 0 ? (
                    <ul className="mt-3 space-y-3">
                      {visibleAlerts.map((alert, index) => {
                        const major = alert.tone === "major";
                        return (
                          <li key={`${alert.title}-${index}`} className={`rounded-xl border-l-4 bg-[var(--surface-panel)] p-4 ${major ? "border-[color:var(--danger-500)]" : "border-[color:var(--warn-500)]"}`}>
                            <div className="flex flex-wrap items-start justify-between gap-2">
                              <p className="font-semibold text-[var(--text-primary)]">{alert.title}</p>
                              <Badge tone={major ? "danger" : "warn"}>
                                {major ? "Cần xử lý sớm" : "Cần lưu ý"}
                              </Badge>
                            </div>
                            <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{alert.details}</p>
                          </li>
                        );
                      })}
                    </ul>
                  ) : (
                    <p className="mt-2 text-sm text-[var(--text-secondary)]">Chưa thấy cặp thuốc có cảnh báo đáng kể trong danh sách hiện tại.</p>
                  )}
                </article>

                <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-5">
                  <h3 className="text-base font-bold text-[var(--text-primary)]">Giải thích dễ hiểu</h3>
                  <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{aiInsight}</p>
                </article>

                <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-5">
                  <h3 className="text-base font-bold text-[var(--text-primary)]">Khuyến nghị nên làm gì</h3>
                  {displayedUserView && displayedUserView.recommendations.length > 0 ? (
                    <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--text-secondary)]">
                      {displayedUserView.recommendations.slice(0, 4).map((item, index) => (
                        <li key={`${item}-${index}`} className="flex gap-2">
                          <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--brand-600)]" />
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-2 text-sm text-[var(--text-secondary)]">Tiếp tục theo dõi và hỏi bác sĩ/dược sĩ nếu có triệu chứng bất thường hoặc đang dùng thêm thuốc mới.</p>
                  )}
                </article>
              </div>
            </div>

            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-5">
                <h3 className="text-base font-bold text-[var(--text-primary)]">Nguồn tham khảo</h3>
                {displayedUserView && displayedUserView.sources.length ? (
                  <ul className="mt-2 flex flex-wrap gap-2">
                    {displayedUserView.sources.map((source, index) => (
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
                  <p className="mt-2 text-sm text-[var(--text-secondary)]">Chưa có nguồn tham khảo hiển thị cho kết quả này.</p>
                )}
              </article>

              {/* Detailed telemetry (raw source/citation counts) is admin-only
                  (Req 4.3, Property 11). End_Users see the sanitized risk label
                  summary instead. */}
              <TelemetryPanel
                role={role}
                summary={
                  <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-5">
                    <h3 className="text-base font-bold text-[var(--text-primary)]">Mức rủi ro tổng quan</h3>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Badge tone={getRiskBadgeTone(displayedResult.riskTier)}>
                        {formatCareguardRiskLabel(displayedUserView?.riskLevel ?? displayedResult.riskTier)}
                      </Badge>
                    </div>
                  </article>
                }
              >
                <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-5">
                  <h3 className="text-base font-bold text-[var(--text-primary)]">Độ tin cậy của kết quả</h3>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Badge tone={getRiskBadgeTone(displayedResult.riskTier)}>
                      {formatCareguardRiskLabel(displayedResult.riskTier)}
                    </Badge>
                    <Badge tone="neutral">
                      {displayedResult.attribution?.sourceCount ?? 0} nguồn
                    </Badge>
                    <Badge tone="neutral">
                      {displayedResult.attribution?.citationCount ?? 0} trích dẫn
                    </Badge>
                  </div>
                </article>
              </TelemetryPanel>
            </div>
          </section>
        ) : null}

        <p className="text-xs leading-5 text-[var(--text-muted)]">
          Thông tin tương tác thuốc chỉ mang tính tham khảo, không thay thế tư vấn của bác sĩ hoặc dược sĩ.
        </p>
      </div>
    </PageShell>
  );
}
