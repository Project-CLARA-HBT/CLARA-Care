"use client";

import { useRef, useState } from "react";
import PhrModal from "@/components/phr/phr-modal";
import {
  confirmPhrOcr,
  scanPhrOcr,
  type PhrOcrCandidate,
} from "@/lib/phr";
import type { UILanguage } from "@/lib/ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";

/**
 * OCR review modal (personal-health-record Requirement 9.1–9.5). The user
 * uploads a document, the backend returns candidate medications WITHOUT
 * committing anything (Req 9.1), and the user edits / accepts / discards each
 * candidate before an explicit confirm commits them as `ocr`-sourced entries
 * (Req 9.2, 9.3). The server binds all displayed opaque IDs to a short-lived,
 * owner-bound review token; the user can discard rows without allowing a new
 * candidate to be injected after the scan.
 *
 * Rendered only when the `ocr_import` capability is effective (Requirement 18.1).
 */

type ReviewRow = PhrOcrCandidate & { _accepted: boolean };

const COPY = {
  vi: {
    open: "Quét đơn thuốc (OCR)",
    title: "Xem lại kết quả OCR",
    intro:
      "Tải lên ảnh hoặc tệp đơn thuốc. Không có mục nào được lưu cho đến khi bạn xác nhận.",
    disclosure:
      "Tôi đồng ý gửi tệp này để trích xuất các thuốc cần xem lại. CLARA không tự lưu thuốc từ kết quả OCR.",
    pick: "Chọn tệp",
    scanning: "Đang quét...",
    scanError: "Quét tài liệu thất bại.",
    noCandidates: "Không tìm thấy mục nào. Hãy thử tệp rõ hơn.",
    name: "Tên thuốc",
    dose: "Liều dùng",
    frequency: "Tần suất",
    needsReview: "Cần xem lại",
    accept: "Chấp nhận",
    accepted: "Đã chấp nhận",
    discard: "Bỏ qua",
    confirm: "Xác nhận & lưu",
    confirming: "Đang lưu...",
    confirmError: "Lưu các mục OCR thất bại.",
    confirmed: "Đã lưu các mục đã chọn.",
    nothingAccepted: "Hãy chấp nhận ít nhất một mục để lưu.",
    close: "Đóng",
  },
  en: {
    open: "Scan prescription (OCR)",
    title: "Review OCR results",
    intro:
      "Upload a prescription image or file. Nothing is saved until you confirm.",
    disclosure:
      "I agree to send this file for reviewable medication extraction. CLARA does not save medicines automatically from OCR.",
    pick: "Choose file",
    scanning: "Scanning...",
    scanError: "Failed to scan the document.",
    noCandidates: "No candidates found. Try a clearer file.",
    name: "Medication",
    dose: "Dose",
    frequency: "Frequency",
    needsReview: "Needs review",
    accept: "Accept",
    accepted: "Accepted",
    discard: "Discard",
    confirm: "Confirm & save",
    confirming: "Saving...",
    confirmError: "Failed to save OCR entries.",
    confirmed: "Saved the accepted entries.",
    nothingAccepted: "Accept at least one entry to save.",
    close: "Close",
  },
} as const;

export default function OcrReviewModal({
  uiLanguage,
  onConfirmed,
}: {
  uiLanguage: UILanguage;
  onConfirmed?: () => void;
}) {
  const text = COPY[uiLanguage];
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<ReviewRow[]>([]);
  const [scanning, setScanning] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [reviewToken, setReviewToken] = useState("");
  const [reviewCandidateIds, setReviewCandidateIds] = useState<string[]>([]);
  const [processingNotice, setProcessingNotice] = useState("");
  const [processingAcknowledged, setProcessingAcknowledged] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const fileRef = useRef<HTMLInputElement | null>(null);

  const reset = () => {
    setRows([]);
    setReviewToken("");
    setReviewCandidateIds([]);
    setProcessingNotice("");
    setProcessingAcknowledged(false);
    setError("");
    setMessage("");
  };

  const onOpen = () => {
    reset();
    setOpen(true);
  };

  const onClose = () => {
    setOpen(false);
    if (fileRef.current) fileRef.current.value = "";
  };

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    setScanning(true);
    setError("");
    setMessage("");
    try {
      const result = await scanPhrOcr(file);
      // Every OCR row is proposal-only. A person must explicitly accept each
      // one before it can be written, regardless of a provider confidence.
      setRows(result.candidates.map((c) => ({ ...c, _accepted: false })));
      setReviewToken(result.reviewToken);
      setReviewCandidateIds(result.candidates.map((candidate) => candidate.candidate_id));
      if (result.processingDisclosure?.humanConfirmationRequired) {
        setProcessingNotice(
          uiLanguage === "vi"
            ? "CLARA không lưu tệp tải lên; hãy kiểm tra từng mục trước khi lưu vào hồ sơ."
            : "CLARA does not persist the uploaded file; review every item before saving it to your record.",
        );
      }
      if (result.candidates.length === 0) setMessage(text.noCandidates);
    } catch (err) {
      setError(safeUserFacingError(err, text.scanError));
    } finally {
      setScanning(false);
    }
  };

  const patchRow = (idx: number, patch: Partial<ReviewRow>) => {
    setRows((prev) =>
      prev.map((row, i) => (i === idx ? { ...row, ...patch } : row)),
    );
  };

  const onConfirm = async () => {
    const accepted = rows.filter((r) => r._accepted);
    if (accepted.length === 0 || !reviewToken || reviewCandidateIds.length === 0) {
      setError(text.nothingAccepted);
      return;
    }
    setConfirming(true);
    setError("");
    setMessage("");
    try {
      await confirmPhrOcr(
        accepted.map(({ _accepted, ...c }) => ({
          ...c,
          requires_manual_confirm: false,
          confirmed: true,
        })),
        reviewToken,
        reviewCandidateIds,
      );
      setMessage(text.confirmed);
      setRows([]);
      onConfirmed?.();
      onClose();
    } catch (err) {
      setError(safeUserFacingError(err, text.confirmError));
    } finally {
      setConfirming(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={onOpen}
        className="inline-flex min-h-[38px] items-center rounded-lg border border-[#93C5FD] bg-[#EFF6FF] px-3 text-sm font-semibold text-[#1D4ED8] transition hover:bg-[#DBEAFE] dark:border-sky-500/70 dark:bg-sky-500/18 dark:text-sky-100"
      >
        {text.open}
      </button>

      <PhrModal open={open} title={text.title} onClose={onClose} closeLabel={text.close}>
        <p className="text-[13px] leading-6 text-[var(--text-secondary)]">
          {text.intro}
        </p>
        <p className="mt-2 text-xs leading-5 text-[var(--text-muted)]">
          {uiLanguage === "vi"
            ? "Bạn cần có đồng ý y tế phù hợp trước khi CLARA gửi tệp đến dịch vụ OCR đã cấu hình."
            : "Appropriate medical consent is required before CLARA sends a file to the configured OCR service."}
        </p>

        <div className="mt-3">
          <label className="mb-3 flex items-start gap-2 text-[13px] leading-5 text-[var(--text-secondary)]">
            <input
              type="checkbox"
              checked={processingAcknowledged}
              onChange={(event) => setProcessingAcknowledged(event.target.checked)}
              disabled={scanning || confirming}
            />
            <span>{text.disclosure}</span>
          </label>
          <input
            ref={fileRef}
            type="file"
            accept="image/*,application/pdf"
            aria-label={text.pick}
            onChange={(e) => onFile(e.target.files?.[0])}
            disabled={scanning || confirming || !processingAcknowledged}
            className="block w-full text-sm text-[var(--text-secondary)] file:mr-3 file:rounded-lg file:border file:border-[#93C5FD] file:bg-[#EFF6FF] file:px-3 file:py-1.5 file:text-sm file:font-semibold file:text-[#1D4ED8]"
          />
        </div>

        {scanning ? (
          <p className="mt-3 text-sm text-[var(--text-secondary)]">{text.scanning}</p>
        ) : null}
        {error ? <p className="mt-3 text-sm text-rose-500">{error}</p> : null}
        {message ? (
          <p className="mt-3 text-sm text-emerald-600 dark:text-emerald-300">{message}</p>
        ) : null}
        {processingNotice ? (
          <p className="mt-3 text-xs leading-5 text-[var(--text-muted)]">{processingNotice}</p>
        ) : null}

        {rows.length > 0 ? (
          <div className="mt-4 space-y-3">
            {rows.map((row, idx) => (
              <div
                key={idx}
                className={`rounded-2xl border p-3 ${
                  row._accepted
                    ? "border-emerald-300 bg-emerald-50/60 dark:border-emerald-500/50 dark:bg-emerald-500/10"
                    : "border-[#93C5FD] bg-[#EEF6FF] dark:border-sky-700/70 dark:bg-slate-800/80"
                }`}
              >
                <div className="grid gap-2 sm:grid-cols-3">
                  <input
                    className="input"
                    aria-label={text.name}
                    placeholder={text.name}
                    value={row.name}
                    onChange={(e) => patchRow(idx, { name: e.target.value })}
                  />
                  <input
                    className="input"
                    aria-label={text.dose}
                    placeholder={text.dose}
                    value={row.dose}
                    onChange={(e) => patchRow(idx, { dose: e.target.value })}
                  />
                  <input
                    className="input"
                    aria-label={text.frequency}
                    placeholder={text.frequency}
                    value={row.frequency}
                    onChange={(e) => patchRow(idx, { frequency: e.target.value })}
                  />
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  {row.requires_manual_confirm && !row._accepted ? (
                    <span className="inline-flex items-center rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-800 dark:border-amber-500/50 dark:bg-amber-500/10 dark:text-amber-200">
                      {text.needsReview}
                    </span>
                  ) : null}
                  <div className="ml-auto flex gap-2">
                    <button
                      type="button"
                      onClick={() => patchRow(idx, { _accepted: !row._accepted })}
                      className="rounded-full border border-emerald-300 bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700 transition hover:bg-emerald-100 dark:border-emerald-500/60 dark:bg-emerald-500/15 dark:text-emerald-100"
                    >
                      {row._accepted ? text.accepted : text.accept}
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        setRows((prev) => prev.filter((_, i) => i !== idx))
                      }
                      className="rounded-full border border-rose-300 bg-rose-50 px-3 py-1 text-xs font-bold text-rose-700 transition hover:bg-rose-100 dark:border-rose-500/70 dark:bg-rose-500/15 dark:text-rose-100"
                    >
                      {text.discard}
                    </button>
                  </div>
                </div>
              </div>
            ))}

            <div className="flex justify-end pt-1">
              <button
                type="button"
                onClick={onConfirm}
                disabled={confirming}
                className="inline-flex min-h-[38px] items-center rounded-lg border border-cyan-300/65 bg-gradient-to-r from-sky-600 to-cyan-500 px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
              >
                {confirming ? text.confirming : text.confirm}
              </button>
            </div>
          </div>
        ) : null}
      </PhrModal>
    </>
  );
}
