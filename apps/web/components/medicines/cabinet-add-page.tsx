"use client";

import { DragEvent, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Button from "@/components/ui/button";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Field, Textarea } from "@/components/ui/field";
import Icon from "@/components/ui/icon";
import MedicalConsentGate from "@/components/medicines/medical-consent-gate";
import {
  ErrorSummary,
  GuidedFlowShell,
  ReviewSection,
  StepActions,
  type GuidedFlowError,
  type GuidedFlowSaveState,
} from "@/components/guided-flow";
import { t } from "@/lib/i18n/catalog";
import {
  AddCabinetItemPayload,
  ScanDetection,
  addCabinetItem,
  importDetections,
  isLowConfidenceDetection,
  scanReceiptFile,
  scanReceiptText,
} from "@/lib/selfmed";
import { useUILanguage } from "@/lib/use-ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";

type Step = "scan" | "verify" | "review";
type InputMode = "file" | "text" | "manual";

function confidenceTone(value: number): BadgeTone {
  if (value >= 0.85) return "ok";
  if (value >= 0.6) return "warn";
  return "danger";
}

function getDetectionKey(item: ScanDetection, index: number): string {
  return `${item.normalized_name}-${item.evidence}-${index}`;
}

function normalizationLabel(
  source: string | null | undefined,
  language: ReturnType<typeof useUILanguage>,
): string {
  if (source === "db") return t(language, "medicines.cabinet.guided.normalization.matched");
  if (source === "candidate") return t(language, "medicines.cabinet.guided.normalization.candidate");
  if (source === "fallback") return t(language, "medicines.cabinet.guided.normalization.fallback");
  return t(language, "medicines.cabinet.guided.normalization.unknown");
}

function normalizationTone(source: string | null | undefined): BadgeTone {
  if (source === "db") return "ok";
  if (source === "candidate") return "warn";
  if (source === "fallback") return "danger";
  return "neutral";
}

export default function CabinetAddPage() {
  const router = useRouter();
  const language = useUILanguage();

  const [step, setStep] = useState<Step>("scan");
  const [inputMode, setInputMode] = useState<InputMode>("file");

  // Step 1: Inputs
  const [scanFile, setScanFile] = useState<File | null>(null);
  const [scanText, setScanText] = useState("");
  const [manualDrugName, setManualDrugName] = useState("");
  const [manualBrandName, setManualBrandName] = useState("");
  const [manualManufacturer, setManualManufacturer] = useState("");
  const [manualDosage, setManualDosage] = useState("");
  const [manualQuantity, setManualQuantity] = useState("1");

  // Detections & selections
  const [detections, setDetections] = useState<ScanDetection[]>([]);
  const [selectedKeys, setSelectedKeys] = useState<Record<string, boolean>>({});
  const [confirmedLowConfidenceKeys, setConfirmedLowConfidenceKeys] = useState<Record<string, boolean>>({});

  // Loading & statuses
  const [isScanningFile, setIsScanningFile] = useState(false);
  const [isScanningText, setIsScanningText] = useState(false);
  const [scanNotice, setScanNotice] = useState("");
  const [validationErrors, setValidationErrors] = useState<GuidedFlowError[]>([]);
  const [saveState, setSaveState] = useState<GuidedFlowSaveState>({ kind: "idle" });

  const fileInputRef = useRef<HTMLInputElement>(null);
  const textInputRef = useRef<HTMLTextAreaElement>(null);
  const manualNameRef = useRef<HTMLInputElement>(null);

  const steps = [
    { id: "scan" as const, label: t(language, "medicines.cabinet.wizard.step.scan") },
    { id: "verify" as const, label: t(language, "medicines.cabinet.wizard.step.verify") },
    { id: "review" as const, label: t(language, "medicines.cabinet.wizard.step.review") },
  ];

  const titleByStep: Record<Step, string> = {
    scan: t(language, "medicines.cabinet.guided.file.title"),
    verify: t(language, "medicines.cabinet.wizard.step.verify"),
    review: t(language, "medicines.cabinet.wizard.step.review"),
  };

  const descriptionByStep: Record<Step, string> = {
    scan: t(language, "medicines.cabinet.guided.page.description"),
    verify: t(language, "medicines.cabinet.guided.detections.title"),
    review: t(language, "medicines.cabinet.wizard.safetyNote"),
  };

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

  const selectedDetections = useMemo(
    () =>
      detections.flatMap((item, index) => {
        const key = getDetectionKey(item, index);
        if (!selectedKeys[key]) return [];
        return [
          {
            ...item,
            confirmed: Boolean(confirmedLowConfidenceKeys[key]),
          },
        ];
      }),
    [confirmedLowConfidenceKeys, detections, selectedKeys]
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

  // Trigger file scan
  const onScanFile = async () => {
    if (!scanFile) {
      setValidationErrors([
        {
          id: "scan-file-required",
          fieldLabel: t(language, "medicines.cabinet.guided.file.title"),
          message: t(language, "medicines.cabinet.guided.notice.fileRequired"),
        },
      ]);
      return;
    }

    setIsScanningFile(true);
    setScanNotice("");
    setValidationErrors([]);
    try {
      const found = await scanReceiptFile(scanFile);
      if (found.length === 0) {
        setScanNotice(t(language, "medicines.cabinet.guided.notice.fileNotDetected"));
      } else {
        setDetections(found);
        resetSelection(found);
        setStep("verify");
      }
    } catch (cause) {
      setScanNotice(safeUserFacingError(cause, t(language, "medicines.cabinet.guided.notice.fileScanError")));
    } finally {
      setIsScanningFile(false);
    }
  };

  // Trigger text scan
  const onScanText = async () => {
    const text = scanText.trim();
    if (!text) {
      setValidationErrors([
        {
          id: "scan-text-required",
          fieldLabel: t(language, "medicines.cabinet.guided.paste.title"),
          message: t(language, "medicines.cabinet.guided.notice.textRequired"),
        },
      ]);
      return;
    }

    setIsScanningText(true);
    setScanNotice("");
    setValidationErrors([]);
    try {
      const found = await scanReceiptText(text);
      if (found.length === 0) {
        setScanNotice(t(language, "medicines.cabinet.guided.notice.textNotDetected"));
      } else {
        setDetections(found);
        resetSelection(found);
        setStep("verify");
      }
    } catch (cause) {
      setScanNotice(safeUserFacingError(cause, t(language, "medicines.cabinet.guided.notice.textScanError")));
    } finally {
      setIsScanningText(false);
    }
  };

  // Prepare manual entry
  const onProceedManual = () => {
    if (!manualDrugName.trim()) {
      setValidationErrors([
        {
          id: "manual-name-required",
          fieldId: "manual-drug-name",
          fieldLabel: t(language, "medicines.cabinet.addManual.name"),
          message: t(language, "medicines.cabinet.addManual.requirements"),
        },
      ]);
      manualNameRef.current?.focus();
      return;
    }

    const singleDetection: ScanDetection = {
      drug_name: manualDrugName.trim(),
      normalized_name: manualDrugName.trim(),
      dosage: manualDosage.trim() || null,
      brand_name: manualBrandName.trim() || null,
      manufacturer: manualManufacturer.trim() || null,
      confidence: 1.0,
      evidence: "Manual entry",
      mapping_source: "fallback",
    };

    setDetections([singleDetection]);
    resetSelection([singleDetection]);
    setValidationErrors([]);
    setStep("verify");
  };

  const onDropScanFile = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const file = event.dataTransfer.files?.[0] ?? null;
    if (file) {
      setScanFile(file);
      setValidationErrors([]);
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

  const validateAndProceedToReview = () => {
    if (selectedDetections.length === 0) {
      setValidationErrors([
        {
          id: "no-detections-selected",
          message: t(language, "medicines.cabinet.guided.detections.selectRequired"),
        },
      ]);
      return;
    }
    if (pendingLowConfidenceSelections.length > 0) {
      setValidationErrors([
        {
          id: "unconfirmed-low-confidence",
          message: t(language, "medicines.cabinet.guided.detections.confirmRequired"),
        },
      ]);
      return;
    }
    setValidationErrors([]);
    setStep("review");
  };

  const commitToCabinet = async () => {
    setValidationErrors([]);
    setSaveState({
      kind: "saving",
      message: t(language, "medicines.cabinet.guided.detections.importing"),
    });

    try {
      if (inputMode === "manual" && detections.length === 1 && detections[0].evidence === "Manual entry") {
        const parsedQuantity = Math.max(1, Math.floor(Number(manualQuantity)) || 1);
        const payload: AddCabinetItemPayload = {
          drug_name: manualDrugName.trim(),
          brand_name: manualBrandName.trim() || undefined,
          manufacturer: manualManufacturer.trim() || undefined,
          dosage: manualDosage.trim() || undefined,
          quantity: parsedQuantity,
          source: "manual",
        };
        await addCabinetItem(payload);
      } else {
        await importDetections(selectedDetections);
      }

      setSaveState({ kind: "saved" });
      router.replace("/medicines?tab=cabinet");
      router.refresh();
    } catch (cause) {
      setSaveState({
        kind: "error",
        message: safeUserFacingError(cause, t(language, "medicines.cabinet.guided.notice.importError")),
      });
    }
  };

  const stepIndex = steps.findIndex((candidate) => candidate.id === step);

  let content;

  if (step === "scan") {
    content = (
      <div className="space-y-6">
        <ErrorSummary errors={validationErrors} />

        {/* Input Mode Selector */}
        <div className="grid grid-cols-3 gap-2 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-1">
          <button
            type="button"
            onClick={() => {
              setInputMode("file");
              setValidationErrors([]);
            }}
            className={`flex items-center justify-center gap-2 rounded-md px-3 py-2 text-xs font-semibold transition ${
              inputMode === "file"
                ? "bg-[var(--surface-panel)] text-[var(--text-primary)] shadow-sm"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            <Icon name="scan" size={16} />
            <span>{t(language, "medicines.cabinet.guided.step.upload.title")}</span>
          </button>
          <button
            type="button"
            onClick={() => {
              setInputMode("text");
              setValidationErrors([]);
            }}
            className={`flex items-center justify-center gap-2 rounded-md px-3 py-2 text-xs font-semibold transition ${
              inputMode === "text"
                ? "bg-[var(--surface-panel)] text-[var(--text-primary)] shadow-sm"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            <Icon name="clinical-notes" size={16} />
            <span>{t(language, "medicines.cabinet.guided.step.paste.title")}</span>
          </button>
          <button
            type="button"
            onClick={() => {
              setInputMode("manual");
              setValidationErrors([]);
            }}
            className={`flex items-center justify-center gap-2 rounded-md px-3 py-2 text-xs font-semibold transition ${
              inputMode === "manual"
                ? "bg-[var(--surface-panel)] text-[var(--text-primary)] shadow-sm"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            <Icon name="edit" size={16} />
            <span>{t(language, "medicines.cabinet.guided.step.manual.title")}</span>
          </button>
        </div>

        {/* Option A: File Upload */}
        {inputMode === "file" && (
          <div
            onDrop={onDropScanFile}
            onDragOver={(event) => event.preventDefault()}
            className="rounded-[var(--radius-xl)] border-2 border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)]/60 p-6 text-center sm:p-8"
          >
            <input
              ref={fileInputRef}
              id="cabinet-scan-file-input"
              type="file"
              accept="image/*,.pdf"
              onChange={(event) => {
                setScanFile(event.target.files?.[0] ?? null);
                setValidationErrors([]);
              }}
              className="sr-only"
            />
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
              <Icon name="scan" size={24} />
            </div>
            <h3 className="mt-3 text-base font-semibold text-[var(--text-primary)]">
              {t(language, "medicines.cabinet.guided.file.dropTitle")}
            </h3>
            <p className="mt-1 text-xs text-[var(--text-secondary)]">
              {t(language, "medicines.cabinet.guided.file.fileTypes")}
            </p>

            {scanFile ? (
              <div className="mt-4 inline-flex items-center gap-2 rounded-lg border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-3 py-2 text-sm font-semibold text-[var(--status-ok-text)]">
                <Icon name="check" size={16} />
                <span>{t(language, "medicines.cabinet.guided.file.selected", { filename: scanFile.name })}</span>
              </div>
            ) : null}

            <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
              <label
                htmlFor="cabinet-scan-file-input"
                className="cursor-pointer rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-2.5 text-xs font-semibold text-[var(--text-primary)] shadow-sm hover:bg-[var(--surface-muted)]"
              >
                {t(language, "medicines.cabinet.guided.file.choose")}
              </label>
              <Button
                onClick={() => void onScanFile()}
                disabled={!scanFile || isScanningFile}
                loading={isScanningFile}
                loadingLabel={t(language, "medicines.cabinet.guided.scanning")}
                icon="scan"
              >
                {t(language, "medicines.cabinet.guided.file.scan")}
              </Button>
            </div>
          </div>
        )}

        {/* Option B: Paste text */}
        {inputMode === "text" && (
          <div className="space-y-4">
            <Textarea
              ref={textInputRef}
              value={scanText}
              onChange={(event) => {
                setScanText(event.target.value);
                setValidationErrors([]);
              }}
              label={t(language, "medicines.cabinet.guided.paste.title")}
              hint={t(language, "medicines.cabinet.guided.paste.description")}
              placeholder={t(language, "medicines.cabinet.guided.paste.placeholder")}
              className="min-h-[160px]"
            />
            <Button
              onClick={() => void onScanText()}
              disabled={!scanText.trim() || isScanningText}
              loading={isScanningText}
              loadingLabel={t(language, "medicines.cabinet.guided.scanning")}
              icon="scan"
            >
              {t(language, "medicines.cabinet.guided.paste.scan")}
            </Button>
          </div>
        )}

        {/* Option C: Manual Entry */}
        {inputMode === "manual" && (
          <div className="space-y-4">
            <Field
              ref={manualNameRef}
              id="manual-drug-name"
              label={t(language, "medicines.cabinet.addManual.name")}
              value={manualDrugName}
              onChange={(event) => {
                setManualDrugName(event.target.value);
                setValidationErrors([]);
              }}
              required
              placeholder={t(language, "medicines.cabinet.addManual.namePlaceholder")}
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <Field
                id="manual-dosage"
                label={t(language, "medicines.cabinet.addManual.dose")}
                value={manualDosage}
                onChange={(event) => setManualDosage(event.target.value)}
                placeholder={t(language, "medicines.cabinet.addManual.dosePlaceholder")}
              />
              <Field
                id="manual-quantity"
                label={t(language, "medicines.cabinet.addManual.quantity")}
                value={manualQuantity}
                onChange={(event) => setManualQuantity(event.target.value)}
                inputMode="numeric"
                placeholder="1"
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field
                id="manual-brand"
                label={t(language, "medicines.cabinet.addManual.brand")}
                optional
                value={manualBrandName}
                onChange={(event) => setManualBrandName(event.target.value)}
                placeholder={t(language, "medicines.cabinet.addManual.brandPlaceholder")}
              />
              <Field
                id="manual-manufacturer"
                label={t(language, "medicines.cabinet.addManual.manufacturer")}
                optional
                value={manualManufacturer}
                onChange={(event) => setManualManufacturer(event.target.value)}
                placeholder={t(language, "medicines.cabinet.addManual.manufacturerPlaceholder")}
              />
            </div>
            <Button onClick={onProceedManual} icon="arrow-right">
              {t(language, "medicines.cabinet.wizard.step.verify")}
            </Button>
          </div>
        )}

        {scanNotice ? (
          <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 text-xs text-[var(--text-secondary)]">
            {scanNotice}
          </div>
        ) : null}

        <StepActions
          back={{
            label: t(language, "medicines.cabinet.guided.file.back"),
            href: "/medicines?tab=cabinet",
          }}
        />
      </div>
    );
  } else if (step === "verify") {
    content = (
      <div className="space-y-6">
        <ErrorSummary errors={validationErrors} />

        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[color:var(--shell-border)] pb-4">
          <div>
            <h3 className="text-base font-semibold text-[var(--text-primary)]">
              {t(language, "medicines.cabinet.guided.detections.title")}
            </h3>
            <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
              {t(language, "medicines.cabinet.guided.detections.selected", {
                selected: selectedDetections.length,
                total: detections.length,
              })}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="secondary" onClick={() => onSelectAllDetections(true)}>
              {t(language, "medicines.cabinet.guided.detections.selectAll")}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => onSelectAllDetections(false)}>
              {t(language, "medicines.cabinet.guided.detections.clearAll")}
            </Button>
            {lowConfidenceTotal > 0 ? (
              <Button
                size="sm"
                variant="secondary"
                onClick={() => onConfirmAllLowConfidence(true)}
              >
                {t(language, "medicines.cabinet.guided.detections.confirmAll")}
              </Button>
            ) : null}
          </div>
        </div>

        {pendingLowConfidenceSelections.length > 0 ? (
          <div className="rounded-xl border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] p-3.5 text-xs font-semibold text-[var(--status-warn-text)]">
            {t(language, "medicines.cabinet.guided.detections.reviewRemaining", {
              pending: pendingLowConfidenceSelections.length,
              total: lowConfidenceTotal,
            })}
          </div>
        ) : null}

        <ul className="space-y-3">
          {detections.map((item, index) => {
            const key = getDetectionKey(item, index);
            const checked = Boolean(selectedKeys[key]);
            const isLow = isLowConfidenceDetection(item);
            const isConfirmed = Boolean(confirmedLowConfidenceKeys[key]);

            return (
              <li
                key={key}
                className={`rounded-[var(--radius-lg)] border p-4 transition ${
                  checked
                    ? isLow
                      ? "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)]/40"
                      : "border-[color:var(--brand-500)] bg-[var(--surface-brand-soft)]/40"
                    : "border-[color:var(--shell-border)] bg-[var(--surface-panel)]"
                }`}
              >
                <label className="flex cursor-pointer items-start gap-3">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => onToggleDetection(key)}
                    className="mt-1 h-5 w-5 rounded border-[color:var(--shell-border)] text-[var(--text-brand)] focus:ring-[var(--focus-ring-color)]"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold text-[var(--text-primary)]">{item.drug_name}</span>
                      <Badge tone={confidenceTone(item.confidence)}>
                        {t(language, "medicines.cabinet.guided.detections.ocr")}
                      </Badge>
                      {item.mapping_source ? (
                        <Badge tone={normalizationTone(item.mapping_source)}>
                          {normalizationLabel(item.mapping_source, language)}
                        </Badge>
                      ) : null}
                    </div>

                    {(item.dosage || item.brand_name || item.manufacturer) && (
                      <p className="mt-1 text-xs text-[var(--text-secondary)]">
                        {[
                          item.dosage ? t(language, "medicines.cabinet.guided.detections.dose", { dose: item.dosage }) : null,
                          item.brand_name ? t(language, "medicines.cabinet.guided.detections.brand", { brand: item.brand_name }) : null,
                          item.manufacturer ? t(language, "medicines.cabinet.guided.detections.manufacturer", { manufacturer: item.manufacturer }) : null,
                        ]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                    )}

                    {item.evidence && (
                      <p className="mt-1 text-xs italic text-[var(--text-muted)]">
                        {t(language, "medicines.cabinet.guided.detections.evidence", { evidence: item.evidence })}
                      </p>
                    )}
                  </div>
                </label>

                {isLow && checked ? (
                  <label className="mt-3 flex cursor-pointer items-center gap-2.5 rounded-lg border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-3 py-2">
                    <input
                      type="checkbox"
                      checked={isConfirmed}
                      onChange={() => onToggleLowConfidenceConfirm(key)}
                      className="h-4 w-4 rounded border-[color:var(--status-warn-border)] text-[var(--warn-500)] focus:ring-[var(--status-warn-border)]"
                    />
                    <span className="text-xs font-semibold text-[var(--status-warn-text)]">
                      {t(language, "medicines.cabinet.guided.detections.confirmOne")}
                    </span>
                  </label>
                ) : null}
              </li>
            );
          })}
        </ul>

        <StepActions
          nextType="button"
          nextLabel={t(language, "medicines.cabinet.wizard.step.review")}
          onNext={validateAndProceedToReview}
          back={{
            label: t(language, "medicines.cabinet.wizard.step.scan"),
            onClick: () => setStep("scan"),
          }}
        />
      </div>
    );
  } else {
    content = (
      <div className="space-y-6">
        <ErrorSummary errors={validationErrors} />

        {/* Safety Disclaimer Callout */}
        <div className="rounded-[var(--radius-xl)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] p-4 sm:p-5">
          <div className="flex items-start gap-3">
            <span className="shrink-0 text-[var(--status-warn-text)]">
              <Icon name="warning" size={20} />
            </span>
            <div className="text-xs leading-relaxed text-[var(--status-warn-text)]">
              <p className="font-bold">{t(language, "medicines.workspace.cabinet.title")}</p>
              <p className="mt-1">{t(language, "medicines.cabinet.wizard.safetyNote")}</p>
            </div>
          </div>
        </div>

        {/* Review list */}
        <ReviewSection
          title={t(language, "medicines.cabinet.wizard.step.review")}
          description={t(language, "medicines.workspace.cabinet.desc")}
          edit={{
            label: t(language, "medicines.cabinet.wizard.step.verify"),
            onClick: () => setStep("verify"),
          }}
          items={selectedDetections.map((item) => ({
            label: item.drug_name,
            value: (
              <div className="text-xs text-[var(--text-secondary)]">
                <span>{item.dosage || t(language, "medicines.cabinet.notAvailable")}</span>
                {item.brand_name ? <span> · {item.brand_name}</span> : null}
                {item.manufacturer ? <span> ({item.manufacturer})</span> : null}
              </div>
            ),
          }))}
        />

        <StepActions
          nextLabel={t(language, "medicines.cabinet.guided.detections.import", {
            count: selectedDetections.length,
          })}
          nextType="button"
          onNext={() => void commitToCabinet()}
          saving={saveState.kind === "saving"}
          savingLabel={t(language, "medicines.cabinet.guided.detections.importing")}
          back={{
            label: t(language, "medicines.cabinet.wizard.step.verify"),
            onClick: () => setStep("verify"),
          }}
        />
      </div>
    );
  }

  return (
    <MedicalConsentGate>
      <GuidedFlowShell
        eyebrow={t(language, "medicines.cabinet.defaultLabel")}
        title={titleByStep[step]}
        description={descriptionByStep[step]}
        steps={steps}
        currentStep={stepIndex}
        saveState={saveState}
        aside={t(language, "medicines.cabinet.wizard.aside")}
      >
        {content}
      </GuidedFlowShell>
    </MedicalConsentGate>
  );
}
