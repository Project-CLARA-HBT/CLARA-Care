"use client";

import React, { useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";
import { V6_DEMO_PHR_FIELDS } from "../landing-data-v6";

export function PhrSharingDemo() {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V6[language].phr;
  const [isRevoked, setIsRevoked] = useState(false);

  return (
    <div className="w-full space-y-6">
      {/* Prominent Editorial Statement Anchor */}
      <div className="text-center max-w-3xl mx-auto py-2">
        <p className="text-xl sm:text-2xl font-bold text-[#162033] tracking-tight">
          “{copy.statement}”
        </p>
      </div>

      {/* Main Spatial Permission Stage */}
      <div className="clara-product-surface relative overflow-hidden p-6 sm:p-8 lg:p-10">
        {/* Packet Header */}
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#E3E8EF] pb-5">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-[#0B6FD8]">
              CLARA PHR PERMISSION GATEWAY
            </span>
            <h3 className="text-lg font-bold text-[#162033]">{copy.sharingTitle}</h3>
            <p className="text-xs text-[#6D7A8E] mt-0.5">
              Bệnh nhân: <strong className="text-[#162033]">{copy.patientName}</strong> • {copy.patientMrn}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="text-right">
              <span className="text-[11px] uppercase tracking-wider text-[#6D7A8E] block">
                {copy.expiryLabel}
              </span>
              <span className={`text-xs font-bold ${isRevoked ? "text-rose-600" : "text-[#14A88D]"}`}>
                {isRevoked ? "Đã thu hồi quyền" : copy.expiryValue}
              </span>
            </div>

            <button
              type="button"
              onClick={() => setIsRevoked(!isRevoked)}
              className={`rounded-xl px-4 py-2 text-xs font-bold transition-all clara-focus-ring ${
                isRevoked
                  ? "bg-[#0B6FD8] text-white hover:bg-[#0855A8]"
                  : "bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100"
              }`}
            >
              {isRevoked ? "Khôi phục gói chia sẻ" : copy.revokeAction}
            </button>
          </div>
        </div>

        {/* Spatial Sharing Split: Allowed vs Blocked */}
        <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Allowed Column (Visibly Permitted Across Gate) */}
          <div className="rounded-2xl bg-[#ECFDF8]/60 p-5 border border-[#14A88D]/30 space-y-3">
            <div className="flex items-center justify-between border-b border-[#14A88D]/20 pb-2">
              <div className="flex items-center gap-2">
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[#14A88D] text-white text-xs font-bold">
                  ✓
                </span>
                <h4 className="text-xs font-bold uppercase tracking-wider text-[#14A88D]">
                  {copy.allowedSection}
                </h4>
              </div>
              <span className="text-[11px] font-semibold text-[#14A88D]">Truyền qua an toàn</span>
            </div>

            <div className="space-y-2.5">
              {V6_DEMO_PHR_FIELDS.filter((f) => f.status === "allowed").map((field) => (
                <div
                  key={field.id}
                  className={`rounded-xl bg-white p-3.5 border border-[#14A88D]/20 shadow-xs transition-opacity ${
                    isRevoked ? "opacity-40" : "opacity-100"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-[#162033]">
                      {language === "vi" ? field.labelVi : field.labelEn}
                    </span>
                    <span className="rounded bg-[#ECFDF8] px-1.5 py-0.5 text-[10px] font-bold text-[#14A88D]">
                      Được phép
                    </span>
                  </div>
                  <p className="mt-1 text-xs font-medium text-[#48566A]">
                    {language === "vi" ? field.valueVi : field.valueEn}
                  </p>
                  <p className="mt-1 text-[11px] text-[#6D7A8E] italic">
                    {language === "vi" ? field.reasonVi : field.reasonEn}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Blocked Column (Halted At Gate) */}
          <div className="rounded-2xl bg-[#FFF1F2]/60 p-5 border border-rose-200/80 space-y-3">
            <div className="flex items-center justify-between border-b border-rose-200 pb-2">
              <div className="flex items-center gap-2">
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-rose-600 text-white text-xs font-bold">
                  ✕
                </span>
                <h4 className="text-xs font-bold uppercase tracking-wider text-rose-800">
                  {copy.blockedSection}
                </h4>
              </div>
              <span className="text-[11px] font-semibold text-rose-700">Chặn tại cổng</span>
            </div>

            <div className="space-y-2.5">
              {V6_DEMO_PHR_FIELDS.filter((f) => f.status === "blocked").map((field) => (
                <div
                  key={field.id}
                  className="rounded-xl bg-white p-3.5 border border-rose-200/60 shadow-xs opacity-90"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-[#162033]">
                      {language === "vi" ? field.labelVi : field.labelEn}
                    </span>
                    <span className="rounded bg-rose-50 px-1.5 py-0.5 text-[10px] font-bold text-rose-700">
                      Đã chặn
                    </span>
                  </div>
                  <p className="mt-1 text-xs font-medium text-[#48566A]">
                    {language === "vi" ? field.valueVi : field.valueEn}
                  </p>
                  <p className="mt-1 text-[11px] text-rose-600/80 italic">
                    {language === "vi" ? field.reasonVi : field.reasonEn}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
