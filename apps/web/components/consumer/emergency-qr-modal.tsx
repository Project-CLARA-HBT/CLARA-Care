"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { InlineError } from "@/components/shared/inline-error";
import api from "@/lib/http-client";

export interface EmergencyCardEligibility {
  eligible: boolean;
  reasons?: string[];
  required_fields?: string[];
  consent_version?: string;
  subject_binding?: string;
  generated_at?: string;
  expires_at?: string | null;
}

export interface EmergencyCardTokenResponse {
  success?: boolean;
  token?: string;
  qr_payload?: string;
  expires_at?: string;
  scope?: string;
  emergency_card?: Record<string, unknown>;
}

export interface EmergencyQrModalProps {
  open: boolean;
  onClose: () => void;
  patientName: string;
  bloodType?: string;
  emergencyContact?: {
    name: string;
    phone: string;
    relationship?: string;
  } | null;
  medicalAlerts?: string[];
  isEn?: boolean;
}

export function EmergencyQrModal({
  open,
  onClose,
  patientName,
  bloodType = "O+",
  emergencyContact,
  medicalAlerts = [],
  isEn = false,
}: EmergencyQrModalProps) {
  const [eligibility, setEligibility] = useState<EmergencyCardEligibility | null>(null);
  const [cardToken, setCardToken] = useState<EmergencyCardTokenResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const fetchEmergencyData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // 1. Query eligibility from /api/v1/phr/emergency-card/eligibility
      const eligRes = await api.get<EmergencyCardEligibility>(
        "/api/v1/phr/emergency-card/eligibility"
      );
      const elig = eligRes?.data ?? { eligible: false, reasons: ["MISSING_PHR_PROFILE"] };
      setEligibility(elig);

      // 2. Query emergency card / issue signed token only if eligible
      if (elig.eligible) {
        let tokenData: EmergencyCardTokenResponse | null = null;
        try {
          const postRes = await api.post<EmergencyCardTokenResponse>(
            "/api/v1/phr/emergency-card"
          );
          tokenData = postRes?.data;
        } catch {
          const getRes = await api.get<EmergencyCardTokenResponse>(
            "/api/v1/phr/emergency-card"
          );
          tokenData = getRes?.data;
        }
        setCardToken(tokenData);
      } else {
        setCardToken(null);
      }
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : isEn
            ? "Failed to check emergency card eligibility."
            : "Không thể kiểm tra điều kiện cấp thẻ cấp cứu."
      );
    } finally {
      setLoading(false);
    }
  }, [isEn]);

  useEffect(() => {
    if (open) {
      void fetchEmergencyData();
    } else {
      setEligibility(null);
      setCardToken(null);
      setError(null);
      setLoading(false);
      setCopied(false);
    }
  }, [open, fetchEmergencyData]);

  if (!open) return null;

  const token = cardToken?.token;
  const qrPayload =
    cardToken?.qr_payload ||
    (token
      ? typeof window !== "undefined"
        ? `${window.location.origin}/share/emergency?token=${token}`
        : `https://theclaracare.com/share/emergency?token=${token}`
      : "");

  const handleCopyLink = () => {
    if (typeof navigator !== "undefined" && navigator.clipboard && qrPayload) {
      navigator.clipboard.writeText(qrPayload);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    }
  };

  const isEligible = Boolean(eligibility?.eligible);
  const hasValidToken = Boolean(token);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-md"
      data-testid="emergency-qr-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="emergency-qr-title"
    >
      <div className="relative w-full max-w-md rounded-[var(--radius-2xl)] border-2 border-[color:var(--status-danger-border)] bg-[var(--surface-panel)] p-6 shadow-2xl space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-3">
          <div className="flex items-center gap-2.5 text-[var(--status-danger-text)]">
            <Icon name="emergency" size="1.4rem" />
            <div>
              <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--status-danger-text)]">
                {isEn ? "Emergency QR Access" : "Mã QR Cấp Cứu Y Tế"}
              </span>
              <h3 id="emergency-qr-title" className="text-base font-bold text-[var(--text-primary)]">
                {patientName || (isEn ? "Medical ID Card" : "Thẻ Cấp Cứu")}
              </h3>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-[var(--text-muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] transition"
            aria-label={isEn ? "Close dialog" : "Đóng hộp thoại"}
          >
            <Icon name="close" size="1.25rem" />
          </button>
        </div>

        {/* Loading State */}
        {loading ? (
          <div
            className="flex flex-col items-center justify-center py-10 space-y-3"
            data-testid="emergency-qr-loading"
          >
            <div className="h-10 w-10 animate-spin rounded-full border-4 border-[color:var(--brand-200)] border-t-[color:var(--brand-600)]" />
            <p className="text-xs font-semibold text-[var(--text-secondary)]">
              {isEn
                ? "Verifying emergency eligibility and signature..."
                : "Đang kiểm tra tính hợp lệ và chữ ký số thẻ cấp cứu..."}
            </p>
          </div>
        ) : error ? (
          /* Error State */
          <div className="space-y-4">
            <InlineError message={error} onRetry={() => void fetchEmergencyData()} />
            <div className="flex justify-end">
              <Button type="button" variant="secondary" size="sm" onClick={onClose}>
                {isEn ? "Close" : "Đóng"}
              </Button>
            </div>
          </div>
        ) : !isEligible ? (
          /* Ineligible State: Missing profile data */
          <div className="space-y-4" data-testid="emergency-qr-ineligible">
            <div className="rounded-xl border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] p-4 space-y-2">
              <div className="flex items-center gap-2 text-[var(--status-warn-text)] font-bold text-sm">
                <Icon name="warning" size="1.25rem" />
                <span>
                  {isEn
                    ? "Incomplete Profile for Emergency QR"
                    : "Hồ sơ chưa đủ điều kiện tạo Mã QR Cấp cứu"}
                </span>
              </div>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                {isEn
                  ? "For patient safety, a signed emergency card requires complete personal identification and at least one emergency contact phone number."
                  : "Để đảm bảo an toàn y tế, thẻ cấp cứu có chữ ký số yêu cầu có đầy đủ họ tên cá nhân và số điện thoại liên hệ khẩn cấp."}
              </p>
            </div>

            {/* Reasons checklist */}
            <div className="space-y-1.5 text-xs">
              <span className="font-bold text-[var(--text-primary)] block">
                {isEn ? "Missing required information:" : "Các thông tin còn thiếu:"}
              </span>
              <ul className="space-y-1 list-disc pl-4 text-[var(--text-secondary)]">
                {eligibility?.reasons?.includes("MISSING_FULL_NAME") ||
                eligibility?.required_fields?.includes("full_name") ? (
                  <li>{isEn ? "Full Name (Họ và tên)" : "Họ và tên"}</li>
                ) : null}
                {eligibility?.reasons?.includes("MISSING_EMERGENCY_CONTACT") ||
                eligibility?.required_fields?.includes("emergency_contact_phone") ? (
                  <li>
                    {isEn
                      ? "Emergency contact phone number (Số điện thoại liên hệ khẩn cấp)"
                      : "Số điện thoại liên hệ khẩn cấp"}
                  </li>
                ) : null}
                {eligibility?.reasons?.includes("MISSING_PHR_PROFILE") ? (
                  <li>
                    {isEn
                      ? "Personal health record profile initialization"
                      : "Khởi tạo hồ sơ sức khỏe cá nhân (PHR)"}
                  </li>
                ) : null}
              </ul>
            </div>

            <div className="pt-2 flex flex-col gap-2">
              <Link
                href="/you/profile"
                onClick={onClose}
                className="fluent-button-primary inline-flex w-full items-center justify-center gap-2 rounded-xl py-2.5 px-4 text-xs font-bold"
                data-testid="complete-profile-btn"
              >
                <Icon name="edit" size="0.9rem" />
                <span>{isEn ? "Update Profile & Emergency Contact" : "Cập nhật Hồ sơ & Thẻ Cấp cứu"}</span>
              </Link>
              <Button type="button" variant="secondary" size="sm" onClick={onClose} className="w-full justify-center">
                {isEn ? "Cancel" : "Hủy"}
              </Button>
            </div>
          </div>
        ) : hasValidToken ? (
          /* Eligible State: Only render QR code when valid server signed token is present */
          <div className="space-y-5" data-testid="emergency-qr-eligible">
            {/* QR Code Container */}
            <div
              className="flex flex-col items-center justify-center rounded-2xl bg-white p-6 shadow-inner text-slate-900 border border-slate-200"
              data-testid="emergency-qr-code-container"
            >
              {/* Stylized Emergency ID QR SVG */}
              <svg
                viewBox="0 0 200 200"
                className="h-44 w-44"
                fill="currentColor"
                role="img"
                aria-label={isEn ? "Emergency medical QR code" : "Mã QR y tế khẩn cấp"}
                data-testid="emergency-qr-svg"
              >
                {/* Top-Left Finder */}
                <rect x="10" y="10" width="50" height="50" rx="6" fill="#0f172a" />
                <rect x="18" y="18" width="34" height="34" rx="4" fill="#ffffff" />
                <rect x="26" y="26" width="18" height="18" rx="2" fill="#e11d48" />

                {/* Top-Right Finder */}
                <rect x="140" y="10" width="50" height="50" rx="6" fill="#0f172a" />
                <rect x="148" y="18" width="34" height="34" rx="4" fill="#ffffff" />
                <rect x="156" y="26" width="18" height="18" rx="2" fill="#e11d48" />

                {/* Bottom-Left Finder */}
                <rect x="10" y="140" width="50" height="50" rx="6" fill="#0f172a" />
                <rect x="18" y="148" width="34" height="34" rx="4" fill="#ffffff" />
                <rect x="26" y="156" width="18" height="18" rx="2" fill="#e11d48" />

                {/* Alignment / Data Pattern Grid */}
                <rect x="70" y="15" width="12" height="12" rx="2" fill="#0f172a" />
                <rect x="90" y="15" width="8" height="8" rx="1" fill="#0f172a" />
                <rect x="110" y="15" width="16" height="10" rx="2" fill="#0f172a" />

                <rect x="70" y="35" width="18" height="10" rx="2" fill="#0f172a" />
                <rect x="100" y="32" width="10" height="18" rx="2" fill="#e11d48" />
                <rect x="120" y="35" width="12" height="12" rx="2" fill="#0f172a" />

                <rect x="15" y="70" width="14" height="14" rx="2" fill="#0f172a" />
                <rect x="38" y="75" width="16" height="10" rx="2" fill="#0f172a" />
                <rect x="65" y="65" width="70" height="70" rx="8" fill="#f1f5f9" />

                {/* Center Caduceus / Medical Cross */}
                <rect x="92" y="78" width="16" height="44" rx="3" fill="#e11d48" />
                <rect x="78" y="92" width="44" height="16" rx="3" fill="#e11d48" />
                <rect x="95" y="81" width="10" height="38" rx="2" fill="#ffffff" />
                <rect x="81" y="95" width="38" height="10" rx="2" fill="#ffffff" />
                <rect x="96" y="96" width="8" height="8" rx="1" fill="#e11d48" />

                <rect x="145" y="72" width="15" height="15" rx="2" fill="#0f172a" />
                <rect x="170" y="75" width="18" height="12" rx="2" fill="#0f172a" />

                <rect x="70" y="145" width="14" height="14" rx="2" fill="#0f172a" />
                <rect x="92" y="145" width="12" height="18" rx="2" fill="#0f172a" />
                <rect x="115" y="150" width="20" height="12" rx="2" fill="#0f172a" />
                <rect x="145" y="145" width="14" height="14" rx="2" fill="#0f172a" />
                <rect x="168" y="145" width="18" height="18" rx="2" fill="#0f172a" />

                <rect x="70" y="170" width="25" height="15" rx="2" fill="#0f172a" />
                <rect x="105" y="172" width="18" height="12" rx="2" fill="#0f172a" />
                <rect x="135" y="168" width="16" height="18" rx="2" fill="#0f172a" />
                <rect x="160" y="172" width="25" height="12" rx="2" fill="#0f172a" />
              </svg>

              <p className="mt-2 text-center text-xs font-bold text-slate-800 tracking-wide uppercase">
                CLARA EMERGENCY MEDICAL ID
              </p>
              <div className="flex items-center gap-1.5 text-[11px] text-slate-500 font-medium">
                <span>{bloodType} · {patientName}</span>
                <span className="inline-block w-1 h-1 rounded-full bg-emerald-500" />
                <span className="text-emerald-700 text-[10px] font-bold">
                  {isEn ? "Signed" : "Đã ký số"}
                </span>
              </div>
            </div>

            {/* Quick Snapshot Details */}
            <div className="rounded-xl bg-[var(--surface-muted)] p-3.5 border border-[color:var(--shell-border)] space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-[var(--text-secondary)]">
                  {isEn ? "Blood Group:" : "Nhóm máu:"}
                </span>
                <span className="font-extrabold text-[var(--status-danger-text)] bg-[var(--status-danger-bg)] px-2 py-0.5 rounded border border-[color:var(--status-danger-border)]">
                  {bloodType}
                </span>
              </div>

              {medicalAlerts.length > 0 ? (
                <div>
                  <span className="font-semibold text-[var(--text-secondary)] block mb-1">
                    {isEn ? "Critical Medical Alerts:" : "Cảnh báo y tế khẩn cấp:"}
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {medicalAlerts.map((alert, i) => (
                      <span
                        key={i}
                        className="inline-flex items-center gap-1 rounded bg-[var(--status-danger-bg)] text-[var(--status-danger-text)] px-2 py-0.5 text-[10px] font-bold border border-[color:var(--status-danger-border)]"
                      >
                        <Icon name="warning" size="0.75rem" />
                        {alert}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}

              {emergencyContact ? (
                <div className="border-t border-[color:var(--shell-border)]/60 pt-2 flex items-center justify-between text-[11px]">
                  <div>
                    <span className="text-[var(--text-muted)]">
                      {isEn ? "First Contact: " : "Liên hệ đầu tiên: "}
                    </span>
                    <span className="font-semibold text-[var(--text-primary)]">
                      {emergencyContact.name} ({emergencyContact.relationship})
                    </span>
                  </div>
                  <a
                    href={`tel:${emergencyContact.phone}`}
                    className="font-mono font-bold text-[var(--text-brand)] hover:underline inline-flex items-center gap-1"
                  >
                    {emergencyContact.phone}
                  </a>
                </div>
              ) : null}
            </div>

            {/* Guidance Tip */}
            <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed italic">
              {isEn
                ? "Responders and emergency personnel can scan this QR code to view life-saving allergies, conditions, and contacts without unlocking your phone."
                : "Nhân viên y tế hoặc người sơ cứu có thể quét mã này để tra cứu ngay lập tức dị ứng nguy hiểm, bệnh nền và người liên hệ khẩn cấp."}
            </p>

            {/* Action Buttons */}
            <div className="flex items-center gap-2 pt-2 border-t border-[color:var(--shell-border)]/60">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={handleCopyLink}
                className="flex-1 justify-center"
                data-testid="copy-emergency-link-btn"
              >
                <Icon name="share" size="0.9rem" />
                <span>
                  {copied
                    ? isEn
                      ? "Link Copied!"
                      : "Đã sao chép!"
                    : isEn
                      ? "Copy Emergency Link"
                      : "Sao chép liên kết"}
                </span>
              </Button>

              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={onClose}
                className="justify-center px-5"
              >
                {isEn ? "Done" : "Đóng"}
              </Button>
            </div>
          </div>
        ) : (
          /* Eligible but token issuance pending/failed */
          <div className="space-y-4">
            <InlineError
              message={
                isEn
                  ? "Failed to generate signed emergency card token."
                  : "Không thể khởi tạo mã thẻ cấp cứu có chữ ký số."
              }
              onRetry={() => void fetchEmergencyData()}
            />
            <div className="flex justify-end">
              <Button type="button" variant="secondary" size="sm" onClick={onClose}>
                {isEn ? "Close" : "Đóng"}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
