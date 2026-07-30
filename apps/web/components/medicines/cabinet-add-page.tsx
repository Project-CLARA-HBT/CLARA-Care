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

function confidenceTone(value: number): BadgeTone {
  if (value >= 0.85) return "ok";
  if (value >= 0.6) return "warn";
  return "danger";
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
                    <p className="text-xs font-bold uppercase tracking-[0.12em] text-[color:var(--text-muted)]">Bước {index + 1}</p>
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
                    {step.completed ? <span className="material-symbols-outlined text-[16px]">check</span> : step.optional ? "Tùy chọn" : index + 1}
                  </span>
                </div>
                <p className="mt-2 text-sm font-medium text-[color:var(--text-muted)]">{step.status}</p>
              </article>
            ))}
          </section>

          <section className={cardClass}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-[color:var(--text-muted)]">Bước 1</p>
                <h2 className="mt-2 text-2xl font-bold text-[color:var(--text-primary)]">Tải ảnh đơn thuốc / hóa đơn</h2>
                <p className="mt-2 text-base font-medium text-[color:var(--text-muted)]">Kéo thả ảnh/PDF đơn thuốc vào đây hoặc bấm Chọn file.</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button as="link" href="/medicines?tab=cabinet" variant="secondary">
                  Quay lại tủ thuốc
                </Button>
                <Button as="link" href="/medicines?tab=safety" variant="secondary">
                  Sang kiểm tra tương tác
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
                  <p className="text-lg font-bold text-[color:var(--text-primary)]">Kéo thả ảnh/PDF đơn thuốc vào đây</p>
                  <p className="mt-2 text-sm font-medium text-[color:var(--text-muted)]">Hỗ trợ ảnh đơn thuốc, hóa đơn thuốc hoặc file PDF.</p>
                  {scanFile ? (
                    <p className="mt-3 rounded-[var(--radius-md)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-3 py-2 text-sm font-semibold text-[var(--status-ok-text)]">
                      Đã chọn: {scanFile.name}
                    </p>
                  ) : (
                    <p className={helperTextClass}>Chọn file ảnh/PDF trước để quét OCR.</p>
                  )}
                </div>
                <label
                  htmlFor="scan-file-input"
                  className="inline-flex min-h-[var(--touch-target-min)] cursor-pointer items-center justify-center gap-2 rounded-[var(--radius-md)] border border-[color:var(--brand-700)] bg-[var(--brand-600)] px-4 py-2.5 text-sm font-semibold text-white shadow-[var(--shadow-sm)] transition hover:bg-[var(--brand-700)]"
                >
                  Chọn file
                </label>
              </div>

              <div className="mt-5 flex flex-wrap items-center gap-3">
                <Button
                  onClick={() => void onScanFile()}
                  disabled={!canScanFile}
                  loading={isScanningFile}
                  loadingLabel="Đang nhận diện..."
                >
                  Nhận diện thuốc từ file
                </Button>
                {!scanFile ? <span className="text-sm font-medium text-[color:var(--text-muted)]">Chọn file ảnh/PDF trước để quét OCR.</span> : null}
              </div>
            </div>
          </section>

          <section className={cardClass}>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-[color:var(--text-muted)]">Bước 2</p>
            <h3 className="mt-2 text-2xl font-bold text-[color:var(--text-primary)]">Nhập hoặc dán nội dung thuốc</h3>
            <p className="mt-2 text-base font-medium text-[color:var(--text-muted)]">
              Nếu OCR ngoài đã có sẵn nội dung, bạn có thể dán vào đây để nhận diện nhanh hơn.
            </p>

            <Textarea
              value={scanText}
              onChange={(event) => setScanText(event.target.value)}
              placeholder={"Ví dụ:\naspirin 81mg\nmetformin 500mg\namlodipine 5mg"}
              wrapperClassName="mt-4"
              className="min-h-[220px]"
            />

            <Button
              onClick={() => void onScanText()}
              disabled={!canScanText}
              loading={isScanningText}
              loadingLabel="Đang nhận diện..."
              className="mt-4"
            >
              Nhận diện từ nội dung đã dán
            </Button>
            {!scanText.trim() ? <p className={helperTextClass}>Dán hoặc nhập nội dung trước để tiếp tục.</p> : null}

            {scanNotice ? (
              <p className="mt-4 rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-3 text-sm font-semibold text-[color:var(--text-muted)]">
                {scanNotice}
              </p>
            ) : null}

            {detections.length ? (
              <div className="mt-4 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-base font-bold text-[color:var(--text-primary)]">Danh sách thuốc nhận diện</p>
                  <Badge tone="neutral">
                    Đã chọn {selectedDetections.length}/{detections.length}
                  </Badge>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Button variant="secondary" onClick={() => onSelectAllDetections(true)}>
                    Chọn tất cả
                  </Button>
                  <Button variant="secondary" onClick={() => onSelectAllDetections(false)}>
                    Bỏ chọn tất cả
                  </Button>
                  <Button
                    onClick={() => onConfirmAllLowConfidence(true)}
                    disabled={!lowConfidenceTotal}
                    className="border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)] hover:bg-[var(--status-warn-bg)]"
                  >
                    Xác nhận các thuốc cần kiểm tra lại
                  </Button>
                </div>
                {!lowConfidenceTotal ? (
                  <p className={helperTextClass}>Không có thuốc nhận diện chưa chắc chắn cần duyệt thêm.</p>
                ) : null}
                {pendingLowConfidenceSelections.length ? (
                  <p className="rounded-[var(--radius-md)] border-2 border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-3 py-2 text-sm font-semibold text-[var(--status-warn-text)]">
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
                                {item.dosage ? `Liều: ${item.dosage}` : "Liều: N/A"}
                                {" · "}
                                {item.brand_name ? `Brand: ${item.brand_name}` : "Brand: N/A"}
                                {" · "}
                                {item.manufacturer ? `Hãng: ${item.manufacturer}` : "Hãng: N/A"}
                              </p>
                            ) : null}
                            <p className="mt-1 text-sm font-medium text-[color:var(--text-muted)]">Bằng chứng: {item.evidence}</p>
                            <div className="mt-2 flex flex-wrap gap-2">
                              <Badge tone={confidenceTone(item.confidence)}>
                                OCR {Math.round(item.confidence * 100)}%
                              </Badge>
                              {item.mapping_source ? (
                                <Badge tone={normalizationTone(item.mapping_source)}>
                                  {normalizationLabel(item.mapping_source)}
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
                              Tôi xác nhận thuốc OCR này đúng trước khi nhập.
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
                  loadingLabel="Đang thêm vào tủ..."
                >
                  {`Thêm ${selectedDetections.length} thuốc vào tủ`}
                </Button>
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
