"use client";

import React, { useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { V7_DEMO_PHR_FIELDS, type V7DemoPhrField } from "../landing-data-v7";
import PermissionGate from "../artwork/permission-gate";

export interface PhrDemoProps {
  className?: string;
}

/**
 * PhrDemo (Landing v7)
 *
 * Interactive Bounded PHR Sharing demonstration component:
 * 1. Prominent Editorial Statement Anchor: "Chia sẻ một phần không có nghĩa là chia sẻ toàn bộ hồ sơ."
 * 2. Two distinct spatial columns:
 *    - Permitted Fields: Allergies, Active Meds, Vitals crossing the gate into clinical enclave.
 *    - Blocked Fields: Sensitive private notes, Billing/Insurance halted strictly at the boundary.
 * 3. Interactive instant Revoke button toggling dynamic gate state and permissions.
 * 4. Embedded PermissionGate spatial boundary artwork with active Laser/Containment beams.
 */
export function PhrDemo({ className = "" }: PhrDemoProps) {
  const { language } = useMotionTier();
  const lang = language === "en" ? "en" : "vi";
  const copy = LANDING_COPY_V7[lang]?.phr ?? LANDING_COPY_V7.vi.phr;

  const [isRevoked, setIsRevoked] = useState(false);

  const allowedFields = V7_DEMO_PHR_FIELDS.filter((f) => f.status === "allowed");
  const blockedFields = V7_DEMO_PHR_FIELDS.filter((f) => f.status === "blocked");

  return (
    <div
      data-testid="phr-demo"
      className={`w-full space-y-6 sm:space-y-8 ${className}`}
    >
      {/* 1. Prominent Editorial Statement Anchor */}
      <div className="text-center max-w-3xl mx-auto py-2 px-4">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-[#EFF7FF] px-3 py-1 text-xs font-bold uppercase tracking-wider text-[#0B6FD8] border border-[#0B6FD8]/20 mb-3">
          ✦ {lang === "vi" ? "Chủ quyền Dữ liệu Cá nhân" : "Patient Data Sovereignty"}
        </span>
        <blockquote className="text-xl sm:text-2xl md:text-3xl font-extrabold text-[#162033] tracking-tight leading-snug">
          “{copy.statement}”
        </blockquote>
        <p className="mt-2 text-xs sm:text-sm text-[#6D7A8E] max-w-2xl mx-auto">
          {copy.description}
        </p>
      </div>

      {/* 2. Main Product Surface Container */}
      <div className="clara-product-surface relative overflow-hidden p-5 sm:p-7 lg:p-9 shadow-lg">
        {/* Packet Header & Interactive Revoke Controls */}
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#E3E8EF] pb-5">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-[#0B6FD8]">
                CLARA Bounded Sharing Protocol
              </span>
              <span className="rounded-full bg-[#ECFDF8] px-2 py-0.5 text-[10px] font-bold text-[#14A88D] border border-[#14A88D]/20">
                Zero-CoT Safe
              </span>
            </div>
            <h3 className="text-lg sm:text-xl font-bold text-[#162033]">
              {copy.sharingTitle}
            </h3>
            <p className="text-xs text-[#6D7A8E]">
              {lang === "vi" ? "Chủ hồ sơ:" : "Record Holder:"}{" "}
              <strong className="text-[#162033] font-semibold">{copy.patientName}</strong> •{" "}
              <span className="font-mono text-[#48566A]">{copy.patientMrn}</span>
            </p>
          </div>

          <div className="flex items-center gap-3.5">
            {/* Validity / Token Expiry Display */}
            <div className="text-right">
              <span className="text-[11px] uppercase tracking-wider text-[#6D7A8E] block font-semibold">
                {copy.expiryLabel}
              </span>
              <span
                className={`text-xs font-bold transition-colors duration-300 ${
                  isRevoked ? "text-rose-600" : "text-[#14A88D]"
                }`}
              >
                {isRevoked
                  ? lang === "vi"
                    ? "Đã thu hồi quyền"
                    : "Access Revoked"
                  : copy.expiryValue}
              </span>
            </div>

            {/* Instant Revocation Button */}
            <button
              type="button"
              data-testid="phr-revoke-btn"
              onClick={() => setIsRevoked((prev) => !prev)}
              className={`rounded-xl px-4 py-2 text-xs font-bold transition-all duration-200 clara-focus-ring cursor-pointer shadow-xs ${
                isRevoked
                  ? "bg-[#0B6FD8] text-white hover:bg-[#0855A8] active:scale-95"
                  : "bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100 active:scale-95"
              }`}
            >
              {isRevoked
                ? lang === "vi"
                  ? "Khôi phục gói chia sẻ"
                  : "Restore Share Access"
                : copy.revokeAction}
            </button>
          </div>
        </div>

        {/* 3. Spatial Artwork Stage: PermissionGate */}
        <div className="mt-6 mb-8">
          <PermissionGate
            isRevoked={isRevoked}
            allowedCount={allowedFields.length}
            blockedCount={blockedFields.length}
            expiryText={copy.expiryValue}
            className="w-full"
          />
        </div>

        {/* 4. Two Distinct Spatial Columns: Permitted vs Blocked */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Column A: Permitted Fields (Crossed the Gate) */}
          <div
            data-testid="phr-permitted-column"
            className={`rounded-2xl p-5 sm:p-6 border transition-all duration-300 space-y-4 ${
              isRevoked
                ? "bg-[#F8FAFD]/70 border-[#E3E8EF] opacity-60"
                : "bg-[#ECFDF8]/60 border-[#14A88D]/30 shadow-xs"
            }`}
          >
            {/* Column Header */}
            <div className="flex items-center justify-between border-b border-[#14A88D]/20 pb-3">
              <div className="flex items-center gap-2.5">
                <span
                  className={`flex h-6 w-6 items-center justify-center rounded-full text-white text-xs font-bold ${
                    isRevoked ? "bg-slate-400" : "bg-[#14A88D]"
                  }`}
                >
                  ✓
                </span>
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-[#14A88D]">
                    {copy.allowedSection}
                  </h4>
                  <span className="text-[11px] text-[#6D7A8E]">
                    {lang === "vi"
                      ? "3 trường thông tin thiết yếu cho hội đồng Tim mạch"
                      : "3 essential fields granted for Cardiology review"}
                  </span>
                </div>
              </div>
              <span
                className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold border ${
                  isRevoked
                    ? "bg-slate-100 text-slate-500 border-slate-200"
                    : "bg-white text-[#14A88D] border-[#14A88D]/25"
                }`}
              >
                {isRevoked
                  ? lang === "vi"
                    ? "Tạm ngắt"
                    : "Suspended"
                  : lang === "vi"
                  ? "Truyền qua an toàn"
                  : "Safely Transmitted"}
              </span>
            </div>

            {/* Allowed Field Cards */}
            <div className="space-y-3">
              {allowedFields.map((field: V7DemoPhrField) => {
                const label = lang === "vi" ? field.labelVi : field.labelEn;
                const value = lang === "vi" ? field.valueVi : field.valueEn;
                const reason = lang === "vi" ? field.reasonVi : field.reasonEn;

                return (
                  <div
                    key={field.id}
                    data-testid={`phr-field-${field.id}`}
                    className={`rounded-xl bg-white p-4 border transition-all duration-200 ${
                      isRevoked
                        ? "border-[#E3E8EF] opacity-75"
                        : "border-[#14A88D]/20 shadow-2xs hover:border-[#14A88D]/40"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="h-2 w-2 rounded-full bg-[#14A88D]" />
                        <span className="text-xs font-bold text-[#162033]">
                          {label}
                        </span>
                      </div>
                      <span
                        className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                          isRevoked
                            ? "bg-slate-100 text-slate-500"
                            : "bg-[#ECFDF8] text-[#14A88D]"
                        }`}
                      >
                        {isRevoked
                          ? lang === "vi"
                            ? "Đã ngắt"
                            : "Revoked"
                          : lang === "vi"
                          ? "Được phép"
                          : "Permitted"}
                      </span>
                    </div>

                    <p className="mt-1.5 text-xs font-semibold text-[#334155]">
                      {value}
                    </p>

                    <div className="mt-2 flex items-start gap-1.5 text-[11px] text-[#6D7A8E] bg-[#F8FAFD] p-2 rounded-lg border border-[#E3E8EF]/60">
                      <span className="text-[#0B6FD8] font-bold">ℹ</span>
                      <span>{reason}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Column B: Blocked Fields (Halted at Boundary) */}
          <div
            data-testid="phr-blocked-column"
            className="rounded-2xl bg-[#FFF1F2]/60 p-5 sm:p-6 border border-rose-200/80 shadow-xs space-y-4"
          >
            {/* Column Header */}
            <div className="flex items-center justify-between border-b border-rose-200 pb-3">
              <div className="flex items-center gap-2.5">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-rose-600 text-white text-xs font-bold">
                  ✕
                </span>
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-rose-800">
                    {copy.blockedSection}
                  </h4>
                  <span className="text-[11px] text-rose-600/80">
                    {lang === "vi"
                      ? "Dữ liệu nhạy cảm được bảo vệ tuyệt đối tại nguồn"
                      : "Sensitive records strictly protected at source"}
                  </span>
                </div>
              </div>
              <span className="rounded-full bg-white px-2.5 py-0.5 text-[10px] font-bold text-rose-700 border border-rose-200">
                {lang === "vi" ? "Chặn tại cổng" : "Halted at Gate"}
              </span>
            </div>

            {/* Blocked Field Cards */}
            <div className="space-y-3">
              {blockedFields.map((field: V7DemoPhrField) => {
                const label = lang === "vi" ? field.labelVi : field.labelEn;
                const value = lang === "vi" ? field.valueVi : field.valueEn;
                const reason = lang === "vi" ? field.reasonVi : field.reasonEn;

                return (
                  <div
                    key={field.id}
                    data-testid={`phr-field-${field.id}`}
                    className="rounded-xl bg-white p-4 border border-rose-200/60 shadow-2xs hover:border-rose-300 transition-all duration-200"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="h-2 w-2 rounded-full bg-rose-500" />
                        <span className="text-xs font-bold text-[#162033]">
                          {label}
                        </span>
                      </div>
                      <span className="rounded bg-rose-50 px-1.5 py-0.5 text-[10px] font-bold text-rose-700 border border-rose-200">
                        {lang === "vi" ? "Đã chặn" : "Blocked"}
                      </span>
                    </div>

                    <p className="mt-1.5 text-xs font-medium text-[#64748B]">
                      {value}
                    </p>

                    <div className="mt-2 flex items-start gap-1.5 text-[11px] text-rose-700/90 bg-[#FFF1F2]/80 p-2 rounded-lg border border-rose-100">
                      <span className="text-rose-600 font-bold">🚫</span>
                      <span>{reason}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* 5. Security Invariant Audit Footnote */}
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-[#F8FAFD] p-3.5 border border-[#E3E8EF] text-xs text-[#48566A]">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-[#14A88D]" />
            <span className="font-semibold text-[#162033]">
              {lang === "vi"
                ? "Bất biến An toàn CLARA:"
                : "CLARA Safety Invariant:"}
            </span>
            <span>
              {lang === "vi"
                ? "Chỉ truyền dữ liệu theo phạm vi chỉ định. Quyền thu hồi có hiệu lực ngay lập tức."
                : "Strict scope-bound transmission. Revocation takes effect instantly across all channels."}
            </span>
          </div>
          <span className="text-[11px] font-mono text-[#6D7A8E]">
            AUDIT-ID: PHR-GATE-2026-V7
          </span>
        </div>
      </div>
    </div>
  );
}

export default PhrDemo;
