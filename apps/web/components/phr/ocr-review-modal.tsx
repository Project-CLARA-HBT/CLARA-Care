"use client";

import { useRef, useState } from "react";
import PhrModal from "@/components/phr/phr-modal";
import {
  confirmPhrOcr,
  scanPhrOcr,
  type PhrOcrCandidate,
} from "@/lib/phr";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
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

export default function OcrReviewModal({
  uiLanguage,
  onConfirmed,
}: {
  uiLanguage: UILanguage;
  onConfirmed?: () => void;
}) {
  const copy = (key: UITranslationKey) => t(uiLanguage, key);
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
        setProcessingNotice(copy("phr.ocr.processingNotice"));
      }
      if (result.candidates.length === 0) setMessage(copy("phr.ocr.noCandidates"));
    } catch (err) {
      setError(safeUserFacingError(err, copy("phr.ocr.scanError")));
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
      setError(copy("phr.ocr.nothingAccepted"));
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
      setMessage(copy("phr.ocr.confirmed"));
      setRows([]);
      onConfirmed?.();
      // Keep the modal open long enough for the explicit success state to be
      // perceived. The caller has already refreshed owner-scoped record data;
      // closing remains an intentional user action, not an implicit write-side
      // navigation change.
    } catch (err) {
      setError(safeUserFacingError(err, copy("phr.ocr.confirmError")));
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
        {copy("phr.ocr.open")}
      </button>

      <PhrModal
        open={open}
        title={copy("phr.ocr.title")}
        onClose={onClose}
        closeLabel={copy("phr.ocr.close")}
      >
        <p className="text-[13px] leading-6 text-[var(--text-secondary)]">
          {copy("phr.ocr.intro")}
        </p>
        <p className="mt-2 text-xs leading-5 text-[var(--text-muted)]">
          {copy("phr.ocr.consentNotice")}
        </p>

        <div className="mt-3">
          <label className="mb-3 flex items-start gap-2 text-[13px] leading-5 text-[var(--text-secondary)]">
            <input
              type="checkbox"
              checked={processingAcknowledged}
              onChange={(event) => setProcessingAcknowledged(event.target.checked)}
              disabled={scanning || confirming}
            />
            <span>{copy("phr.ocr.disclosure")}</span>
          </label>
          <input
            ref={fileRef}
            type="file"
            accept="image/*,application/pdf"
            aria-label={copy("phr.ocr.pick")}
            onChange={(e) => onFile(e.target.files?.[0])}
            disabled={scanning || confirming || !processingAcknowledged}
            className="block w-full text-sm text-[var(--text-secondary)] file:mr-3 file:rounded-lg file:border file:border-[#93C5FD] file:bg-[#EFF6FF] file:px-3 file:py-1.5 file:text-sm file:font-semibold file:text-[#1D4ED8]"
          />
        </div>

        {scanning ? (
          <p className="mt-3 text-sm text-[var(--text-secondary)]">{copy("phr.ocr.scanning")}</p>
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
                    aria-label={copy("phr.ocr.name")}
                    placeholder={copy("phr.ocr.name")}
                    value={row.name}
                    onChange={(e) => patchRow(idx, { name: e.target.value })}
                  />
                  <input
                    className="input"
                    aria-label={copy("phr.ocr.dose")}
                    placeholder={copy("phr.ocr.dose")}
                    value={row.dose}
                    onChange={(e) => patchRow(idx, { dose: e.target.value })}
                  />
                  <input
                    className="input"
                    aria-label={copy("phr.ocr.frequency")}
                    placeholder={copy("phr.ocr.frequency")}
                    value={row.frequency}
                    onChange={(e) => patchRow(idx, { frequency: e.target.value })}
                  />
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  {row.requires_manual_confirm && !row._accepted ? (
                    <span className="inline-flex items-center rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-800 dark:border-amber-500/50 dark:bg-amber-500/10 dark:text-amber-200">
                      {copy("phr.ocr.needsReview")}
                    </span>
                  ) : null}
                  <div className="ml-auto flex gap-2">
                    <button
                      type="button"
                      onClick={() => patchRow(idx, { _accepted: !row._accepted })}
                      className="rounded-full border border-emerald-300 bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700 transition hover:bg-emerald-100 dark:border-emerald-500/60 dark:bg-emerald-500/15 dark:text-emerald-100"
                    >
                      {row._accepted ? copy("phr.ocr.accepted") : copy("phr.ocr.accept")}
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        setRows((prev) => prev.filter((_, i) => i !== idx))
                      }
                      className="rounded-full border border-rose-300 bg-rose-50 px-3 py-1 text-xs font-bold text-rose-700 transition hover:bg-rose-100 dark:border-rose-500/70 dark:bg-rose-500/15 dark:text-rose-100"
                    >
                      {copy("phr.ocr.discard")}
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
                {confirming ? copy("phr.ocr.confirming") : copy("phr.ocr.confirm")}
              </button>
            </div>
          </div>
        ) : null}
      </PhrModal>
    </>
  );
}
