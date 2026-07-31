"use client";

import { DragEvent, FormEvent, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import Button from "@/components/ui/button";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Field, Textarea } from "@/components/ui/field";
import MedicalConsentGate from "@/components/medicines/medical-consent-gate";
import { t } from "@/lib/i18n/catalog";
import {
  AddCabinetItemPayload,
  ScanDetection,
  addCabinetItem,
  importDetections,
  isLowConfidenceDetection,
  scanReceiptFile,
  scanReceiptText
} from "@/lib/selfmed";
import { useUILanguage } from "@/lib/use-ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";

function confidenceTone(value: number): BadgeTone {
  if (value >= 0.85) return "ok";
  if (value >= 0.6) return "warn";
  return "danger";
}

function getDetectionKey(item: ScanDetection, index: number): string {
  return `${item.normalized_name}-${item.evidence}-${index}`;
}

function normalizationLabel(source: string | null | undefined, language: ReturnType<typeof useUILanguage>): string {
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

const cardClass = "rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-[var(--shadow-sm)] sm:p-6";
const helperTextClass = "mt-2 text-sm font-medium text-[color:var(--text-muted)]";

export default function CabinetAddPage() {
  const language = useUILanguage();
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
      title: t(language, "medicines.cabinet.guided.step.upload.title"),
      status: scanFile ? t(language, "medicines.cabinet.guided.step.upload.selected") : t(language, "medicines.cabinet.guided.step.upload.pending"),
      completed: Boolean(scanFile),
      active: !scanFile,
      optional: false
    },
    {
      title: t(language, "medicines.cabinet.guided.step.paste.title"),
      status: detections.length
        ? t(language, "medicines.cabinet.guided.step.paste.ready")
        : scanText.trim()
          ? t(language, "medicines.cabinet.guided.step.paste.entering")
          : t(language, "medicines.cabinet.guided.step.paste.pending"),
      completed: detections.length > 0,
      active: Boolean(scanFile || scanText.trim()) && detections.length === 0,
      optional: false
    },
    {
      title: t(language, "medicines.cabinet.guided.step.manual.title"),
      status: t(language, "medicines.cabinet.guided.step.manual.status"),
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
      setScanNotice(t(language, "medicines.cabinet.guided.notice.fileRequired"));
      return;
    }

    setIsScanningFile(true);
    setScanNotice("");
    try {
      const found = await scanReceiptFile(scanFile);
      setDetections(found);
      resetSelection(found);
      setScanNotice(found.length
        ? t(language, "medicines.cabinet.guided.notice.fileDetected", { count: found.length })
        : t(language, "medicines.cabinet.guided.notice.fileNotDetected"));
    } catch (cause) {
      setScanNotice(safeUserFacingError(cause, t(language, "medicines.cabinet.guided.notice.fileScanError")));
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
      setScanNotice(t(language, "medicines.cabinet.guided.notice.textRequired"));
      return;
    }

    setIsScanningText(true);
    setScanNotice("");
    try {
      const found = await scanReceiptText(text);
      setDetections(found);
      resetSelection(found);
      setScanNotice(found.length
        ? t(language, "medicines.cabinet.guided.notice.textDetected", { count: found.length })
        : t(language, "medicines.cabinet.guided.notice.textNotDetected"));
    } catch (cause) {
      setScanNotice(safeUserFacingError(cause, t(language, "medicines.cabinet.guided.notice.textScanError")));
    } finally {
      setIsScanningText(false);
    }
  };

  const onImportSelected = async () => {
    if (!selectedDetections.length) return;
    if (pendingLowConfidenceSelections.length) {
      setScanNotice(t(language, "medicines.cabinet.guided.notice.confirmBeforeImport"));
      return;
    }
    setIsImporting(true);
    setScanNotice("");
    try {
      const inserted = await importDetections(selectedDetections);
      setScanNotice(t(language, "medicines.cabinet.guided.notice.imported", { count: inserted }));
    } catch (cause) {
      setScanNotice(safeUserFacingError(cause, t(language, "medicines.cabinet.guided.notice.importError")));
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
      setManualNotice(safeUserFacingError(cause, "Không thể thêm thuốc thủ công."));
    } finally {
      setIsAddingManual(false);
    }
  };

  const adjustManualQuantity = (delta: number) => {
    setManualQuantity((current) => String(Math.max(1, Math.floor(Number(current) || 1) + delta)));
  };

  return (
    <PageShell
      title={t(language, "medicines.cabinet.guided.page.title")}
      description={t(language, "medicines.cabinet.guided.page.description")}
    >
      <MedicalConsentGate>
        <div className="space-y-5">
          <section className="grid gap-3 md:grid-cols-3">
            {stepItems.map((step, index) => (
              <article
                key={step.title}
                className={[
                  "rounded-2xl border p-4 transition",
                  step.active
                    ? "border-[color:var(--brand-600)] bg-[color:var(--surface-muted)] shadow-[var(--shadow-sm)]"
                    : step.completed
                      ? "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)]"
                      : "border-[color:var(--shell-border)] bg-[var(--surface-panel)]",
                ].join(" ")}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[0.12em] text-[color:var(--text-muted)]">{t(language, "medicines.cabinet.guided.step.number", { number: index + 1 })}</p>
                    <h2 className="mt-1 text-base font-bold text-[color:var(--text-primary)]">{step.title}</h2>
                  </div>
                  <span
                    className={[
                      "inline-flex h-7 min-w-7 items-center justify-center rounded-full border px-2 text-xs font-bold",
                      step.completed
                        ? "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]"
                        : step.active
                          ? "border-[color:var(--brand-600)] bg-[var(--surface-panel)] text-[color:var(--brand-600)]"
                          : "border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] text-[color:var(--text-muted)]",
                    ].join(" ")}
                  >
                    {step.completed ? <span className="material-symbols-outlined text-[16px]">check</span> : step.optional ? t(language, "medicines.cabinet.guided.optional") : index + 1}
                  </span>
                </div>
                <p className="mt-2 text-sm font-medium text-[color:var(--text-muted)]">{step.status}</p>
              </article>
            ))}
          </section>

          <section className={cardClass}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-[color:var(--text-muted)]">{t(language, "medicines.cabinet.guided.step.number", { number: 1 })}</p>
                <h2 className="mt-2 text-2xl font-bold text-[color:var(--text-primary)]">{t(language, "medicines.cabinet.guided.file.title")}</h2>
                <p className="mt-2 text-base font-medium text-[color:var(--text-muted)]">{t(language, "medicines.cabinet.guided.file.description")}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button as="link" href="/medicines?tab=cabinet" variant="secondary">
                  {t(language, "medicines.cabinet.guided.file.back")}
                </Button>
                <Button as="link" href="/medicines?tab=safety" variant="secondary">
                  {t(language, "medicines.cabinet.guided.file.openSafety")}
                </Button>
              </div>
            </div>

            <div
              onDrop={onDropScanFile}
              onDragOver={(event) => event.preventDefault()}
              className="mt-5 rounded-[1.4rem] border-2 border-dashed border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] p-6 sm:p-8"
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
                  <p className="text-lg font-bold text-[color:var(--text-primary)]">{t(language, "medicines.cabinet.guided.file.dropTitle")}</p>
                  <p className="mt-2 text-sm font-medium text-[color:var(--text-muted)]">{t(language, "medicines.cabinet.guided.file.fileTypes")}</p>
                  {scanFile ? (
                    <p className="mt-3 rounded-[var(--radius-md)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-3 py-2 text-sm font-semibold text-[var(--status-ok-text)]">
                      {t(language, "medicines.cabinet.guided.file.selected", { filename: scanFile.name })}
                    </p>
                  ) : (
                    <p className={helperTextClass}>{t(language, "medicines.cabinet.guided.file.required")}</p>
                  )}
                </div>
                <label
                  htmlFor="scan-file-input"
                  className="inline-flex min-h-[var(--touch-target-min)] cursor-pointer items-center justify-center gap-2 rounded-[var(--radius-md)] border border-[color:var(--brand-700)] bg-[var(--brand-600)] px-4 py-2.5 text-sm font-semibold text-white shadow-[var(--shadow-sm)] transition hover:bg-[var(--brand-700)]"
                >
                  {t(language, "medicines.cabinet.guided.file.choose")}
                </label>
              </div>

              <div className="mt-5 flex flex-wrap items-center gap-3">
                <Button
                  onClick={() => void onScanFile()}
                  disabled={!canScanFile}
                  loading={isScanningFile}
                  loadingLabel={t(language, "medicines.cabinet.guided.scanning")}
                >
                  {t(language, "medicines.cabinet.guided.file.scan")}
                </Button>
                {!scanFile ? <span className="text-sm font-medium text-[color:var(--text-muted)]">{t(language, "medicines.cabinet.guided.file.required")}</span> : null}
              </div>
            </div>
          </section>

          <section className={cardClass}>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-[color:var(--text-muted)]">{t(language, "medicines.cabinet.guided.step.number", { number: 2 })}</p>
            <h3 className="mt-2 text-2xl font-bold text-[color:var(--text-primary)]">{t(language, "medicines.cabinet.guided.paste.title")}</h3>
            <p className="mt-2 text-base font-medium text-[color:var(--text-muted)]">
              {t(language, "medicines.cabinet.guided.paste.description")}
            </p>

            <Textarea
              value={scanText}
              onChange={(event) => setScanText(event.target.value)}
              placeholder={t(language, "medicines.cabinet.guided.paste.placeholder")}
              wrapperClassName="mt-4"
              className="min-h-[220px]"
            />

            <Button
              onClick={() => void onScanText()}
              disabled={!canScanText}
              loading={isScanningText}
              loadingLabel={t(language, "medicines.cabinet.guided.scanning")}
              className="mt-4"
            >
              {t(language, "medicines.cabinet.guided.paste.scan")}
            </Button>
            {!scanText.trim() ? <p className={helperTextClass}>{t(language, "medicines.cabinet.guided.paste.required")}</p> : null}

            {scanNotice ? (
              <p className="mt-4 rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-3 text-sm font-semibold text-[color:var(--text-muted)]">
                {scanNotice}
              </p>
            ) : null}

            {detections.length ? (
              <div className="mt-4 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-base font-bold text-[color:var(--text-primary)]">{t(language, "medicines.cabinet.guided.detections.title")}</p>
                  <Badge tone="neutral">
                    {t(language, "medicines.cabinet.guided.detections.selected", { selected: selectedDetections.length, total: detections.length })}
                  </Badge>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Button variant="secondary" onClick={() => onSelectAllDetections(true)}>
                    {t(language, "medicines.cabinet.guided.detections.selectAll")}
                  </Button>
                  <Button variant="secondary" onClick={() => onSelectAllDetections(false)}>
                    {t(language, "medicines.cabinet.guided.detections.clearAll")}
                  </Button>
                  <Button
                    onClick={() => onConfirmAllLowConfidence(true)}
                    disabled={!lowConfidenceTotal}
                    className="border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)] hover:bg-[var(--status-warn-bg)]"
                  >
                    {t(language, "medicines.cabinet.guided.detections.confirmAll")}
                  </Button>
                </div>
                {!lowConfidenceTotal ? (
                  <p className={helperTextClass}>{t(language, "medicines.cabinet.guided.detections.noReview")}</p>
                ) : null}
                {pendingLowConfidenceSelections.length ? (
                  <p className="rounded-[var(--radius-md)] border-2 border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-3 py-2 text-sm font-semibold text-[var(--status-warn-text)]">
                    {t(language, "medicines.cabinet.guided.detections.reviewRemaining", { pending: pendingLowConfidenceSelections.length, total: selectedLowConfidenceTotal })}
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
                              ? "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] shadow-sm"
                              : "border-[color:var(--brand-600)] bg-[color:var(--surface-muted)] shadow-sm"
                            : "border-[color:var(--shell-border)] bg-[var(--surface-panel)]"
                        }`}
                      >
                        <label className="flex min-h-11 cursor-pointer items-start gap-3">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => onToggleDetection(key)}
                            className="mt-1 h-6 w-6 rounded border-[color:var(--brand-600)] text-[color:var(--brand-600)] focus:ring-[color:var(--shell-border)]"
                          />
                          <div>
                            <p className="text-lg font-bold text-[color:var(--text-primary)]">{item.drug_name}</p>
                            {(item.dosage || item.brand_name || item.manufacturer) ? (
                              <p className="mt-1 text-sm font-medium text-[color:var(--text-muted)]">
                                {t(language, "medicines.cabinet.guided.detections.dose", { dose: item.dosage || t(language, "medicines.cabinet.guided.notAvailable") })}
                                {" · "}
                                {t(language, "medicines.cabinet.guided.detections.brand", { brand: item.brand_name || t(language, "medicines.cabinet.guided.notAvailable") })}
                                {" · "}
                                {t(language, "medicines.cabinet.guided.detections.manufacturer", { manufacturer: item.manufacturer || t(language, "medicines.cabinet.guided.notAvailable") })}
                              </p>
                            ) : null}
                            <p className="mt-1 text-sm font-medium text-[color:var(--text-muted)]">{t(language, "medicines.cabinet.guided.detections.evidence", { evidence: item.evidence })}</p>
                            <div className="mt-2 flex flex-wrap gap-2">
                              <Badge tone={confidenceTone(item.confidence)}>
                                {t(language, "medicines.cabinet.guided.detections.ocr")}
                              </Badge>
                              {item.mapping_source ? (
                                <Badge tone={normalizationTone(item.mapping_source)}>
                                  {normalizationLabel(item.mapping_source, language)}
                                </Badge>
                              ) : null}
                            </div>
                          </div>
                        </label>
                        {isLowConfidence && checked ? (
                          <label className="mt-3 flex min-h-11 cursor-pointer items-center gap-3 rounded-[var(--radius-md)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-3 py-2">
                            <input
                              type="checkbox"
                              checked={isLowConfidenceConfirmed}
                              onChange={() => onToggleLowConfidenceConfirm(key)}
                              className="h-6 w-6 rounded border-[color:var(--status-warn-border)] text-[var(--warn-500)] focus:ring-[color:var(--status-warn-border)]"
                            />
                            <span className="text-sm font-semibold text-[var(--status-warn-text)]">
                              {t(language, "medicines.cabinet.guided.detections.confirmOne")}
                            </span>
                          </label>
                        ) : null}
                      </li>
                    );
                  })}
                </ul>

                <Button
                  onClick={() => void onImportSelected()}
                  disabled={!canImportSelected}
                  loading={isImporting}
                  loadingLabel={t(language, "medicines.cabinet.guided.detections.importing")}
                >
                  {t(language, "medicines.cabinet.guided.detections.import", { count: selectedDetections.length })}
                </Button>
                {!canImportSelected ? (
                  <p className={helperTextClass}>
                    {selectedDetections.length === 0
                      ? t(language, "medicines.cabinet.guided.detections.selectRequired")
                      : pendingLowConfidenceSelections.length > 0
                        ? t(language, "medicines.cabinet.guided.detections.confirmRequired")
                        : t(language, "medicines.cabinet.guided.detections.processing")}
                  </p>
                ) : null}
              </div>
            ) : null}
          </section>

          <section className={cardClass}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-[color:var(--text-muted)]">{t(language, "medicines.cabinet.addManual.step")}</p>
                <h3 className="mt-2 text-2xl font-bold text-[color:var(--text-primary)]">{t(language, "medicines.cabinet.addManual.title")}</h3>
                <p className="mt-2 text-base font-medium text-[color:var(--text-muted)]">
                  {t(language, "medicines.cabinet.addManual.description")}
                </p>
              </div>
              <Badge tone="neutral">{t(language, "medicines.cabinet.addManual.optional")}</Badge>
            </div>

            <form onSubmit={onAddManual} className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              <Field
                label={t(language, "medicines.cabinet.addManual.name")}
                value={manualDrugName}
                onChange={(event) => setManualDrugName(event.target.value)}
                required
                placeholder={t(language, "medicines.cabinet.addManual.namePlaceholder")}
              />

              <Field
                label={t(language, "medicines.cabinet.addManual.brand")}
                optional
                value={manualBrandName}
                onChange={(event) => setManualBrandName(event.target.value)}
                placeholder={t(language, "medicines.cabinet.addManual.brandPlaceholder")}
              />

              <Field
                label={t(language, "medicines.cabinet.addManual.manufacturer")}
                optional
                value={manualManufacturer}
                onChange={(event) => setManualManufacturer(event.target.value)}
                placeholder={t(language, "medicines.cabinet.addManual.manufacturerPlaceholder")}
              />

              <Field
                label={t(language, "medicines.cabinet.addManual.dose")}
                value={manualDosage}
                onChange={(event) => setManualDosage(event.target.value)}
                placeholder={t(language, "medicines.cabinet.addManual.dosePlaceholder")}
                required
              />

              <div>
                <label
                  htmlFor="manual-quantity"
                  className="mb-1.5 block text-sm font-medium text-[var(--text-primary)]"
                >
                  {t(language, "medicines.cabinet.addManual.quantity")}
                </label>
                <div className="flex h-14 overflow-hidden rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] focus-within:border-[color:var(--brand-500)] focus-within:shadow-[var(--shadow-focus)]">
                  <button
                    type="button"
                    onClick={() => adjustManualQuantity(-1)}
                    className="flex w-14 items-center justify-center border-r border-[color:var(--shell-border)] text-xl font-bold text-[color:var(--text-primary)] hover:bg-[var(--surface-muted)]"
                    aria-label={t(language, "medicines.cabinet.addManual.decreaseQuantity")}
                  >
                    -
                  </button>
                  <input
                    id="manual-quantity"
                    value={manualQuantity}
                    onChange={(event) => setManualQuantity(event.target.value)}
                    inputMode="numeric"
                    aria-label={t(language, "medicines.cabinet.addManual.quantityInput")}
                    className="min-w-0 flex-1 bg-transparent px-4 text-center text-base font-semibold text-[color:var(--text-primary)] outline-none placeholder:text-[color:var(--text-muted)]"
                  />
                  <button
                    type="button"
                    onClick={() => adjustManualQuantity(1)}
                    className="flex w-14 items-center justify-center border-l border-[color:var(--shell-border)] text-xl font-bold text-[color:var(--text-primary)] hover:bg-[var(--surface-muted)]"
                    aria-label={t(language, "medicines.cabinet.addManual.increaseQuantity")}
                  >
                    +
                  </button>
                </div>
              </div>

              <div className="md:col-span-3">
                <Button
                  type="submit"
                  disabled={!canAddManual}
                  loading={isAddingManual}
                  loadingLabel={t(language, "medicines.cabinet.addManual.saving")}
                >
                  {t(language, "medicines.cabinet.addManual.submit")}
                </Button>
                {!canAddManual ? <p className={helperTextClass}>{t(language, "medicines.cabinet.addManual.requirements")}</p> : null}
              </div>
            </form>

            {manualNotice ? (
              <p className="mt-4 rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-3 text-sm font-semibold text-[color:var(--text-muted)]">
                {manualNotice}
              </p>
            ) : null}
          </section>
        </div>
      </MedicalConsentGate>
    </PageShell>
  );
}
