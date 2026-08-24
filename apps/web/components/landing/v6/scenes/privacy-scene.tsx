"use client";

import React, { useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";

export function PrivacyScene() {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V6[language];
  const privacyCopy = copy.privacy;
  const [isRevoked, setIsRevoked] = useState(false);

  const guarantees = [
    {
      icon: (
        <svg
          className="w-5 h-5 text-[#0B6FD8]"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
          />
        </svg>
      ),
      title: language === "vi" ? "Cách ly suy luận Zero-CoT" : "Zero-CoT Reasoning Isolation",
      subtitle: language === "vi" ? "Không rò rỉ vết suy luận nội bộ" : "Zero Internal Trace Leakage",
      description:
        language === "vi"
          ? "Chuỗi suy luận thô (Chain-of-Thought) và các bước xử lý trung gian được giữ kín trong vùng an toàn nội bộ. Người nhận và bên thứ ba chỉ tiếp cận kết luận lâm sàng đã được kiểm chứng."
          : "Raw Chain-of-Thought reasoning steps are strictly isolated within our secure enclave. External consumers only receive verified, finalized clinical syntheses without raw prompt leakage.",
      tag: "Zero-CoT Enclave",
      tagTone: "azure" as const,
    },
    {
      icon: (
        <svg
          className="w-5 h-5 text-[#14A88D]"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
          />
        </svg>
      ),
      title: language === "vi" ? "Tuyệt đối không huấn luyện" : "Zero Model Training",
      subtitle: language === "vi" ? "Dữ liệu người dùng là bất khả xâm phạm" : "User Records Are Strictly Private",
      description:
        language === "vi"
          ? "Toàn bộ hồ sơ bệnh án, lịch sử hội thoại và đơn thuốc cá nhân không bao giờ bị sử dụng để huấn luyện (train/fine-tune) bất kỳ mô hình AI nào khi chưa có văn bản đồng thuận rõ ràng."
          : "Your medical records, conversation history, and uploaded prescriptions are never used to train or fine-tune public or foundation AI models without explicit, affirmative consent.",
      tag: "No LLM Training",
      tagTone: "mint" as const,
    },
    {
      icon: (
        <svg
          className="w-5 h-5 text-[#8B7CF6]"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"
          />
        </svg>
      ),
      title: language === "vi" ? "Chủ quyền & Thu hồi tức thì" : "Sovereignty & Instant Revocation",
      subtitle: language === "vi" ? "Toàn quyền cấp và hủy bỏ trong 1 click" : "Instant 1-Click Access Termination",
      description:
        language === "vi"
          ? "Mọi chia sẻ hồ sơ sức khỏe đều có thời hạn xác định và có thể bị thu hồi ngay lập tức. Hệ thống áp dụng chuẩn mã hóa ngân hàng AES-256 ở trạng thái nghỉ và TLS 1.3 khi truyền tải."
          : "Every health record share operates on time-bounded tokens that can be revoked in real time. Backed by banking-grade AES-256 at rest and TLS 1.3 in transit.",
      tag: "AES-256 / TLS 1.3",
      tagTone: "iris" as const,
    },
  ];

  return (
    <LandingScene id="privacy" scale="standard" tone="canvas">
      <SceneHeader
        eyebrow={privacyCopy.eyebrow}
        title={privacyCopy.title}
        description={privacyCopy.description}
        align="center"
        tone="azure"
      />

      {/* Main Interactive Permission Boundary & Data Sovereignty Stage */}
      <div className="clara-product-surface bg-white border border-[#E3E8EF] rounded-3xl p-6 sm:p-8 lg:p-10 shadow-sm max-w-6xl mx-auto mb-12">
        {/* Workspace Sub-header & Live Revocation Simulator */}
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#E3E8EF] pb-5 mb-8">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-[#0B6FD8]">
                {language === "vi" ? "Kiến trúc Ranh giới Quyền" : "Permission Boundary Architecture"}
              </span>
              <span className="rounded-full bg-[#EFF7FF] px-2 py-0.5 text-[10px] font-bold text-[#0B6FD8] border border-[#0B6FD8]/20">
                Zero-CoT Security Gateway
              </span>
            </div>
            <h3 className="text-base sm:text-lg font-bold text-[#162033] mt-0.5">
              {language === "vi"
                ? "Minh họa luồng truyền dữ liệu qua Cổng kiểm soát phân quyền"
                : "Live Data Flow Across Policy-Enforced Security Perimeter"}
            </h3>
          </div>

          <div className="flex items-center gap-3">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold border ${
                isRevoked
                  ? "bg-rose-50 text-rose-700 border-rose-200"
                  : "bg-[#ECFDF8] text-[#14A88D] border-[#14A88D]/20"
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  isRevoked ? "bg-rose-600" : "bg-[#14A88D] animate-pulse"
                }`}
              />
              {isRevoked
                ? language === "vi"
                  ? "Đã ngắt quyền truy cập"
                  : "Access Revoked"
                : language === "vi"
                ? "Cổng bảo vệ đang hoạt động"
                : "Active Boundary Guard"}
            </span>

            <button
              type="button"
              onClick={() => setIsRevoked(!isRevoked)}
              className={`rounded-xl px-4 py-2 text-xs font-bold transition-all clara-focus-ring ${
                isRevoked
                  ? "bg-[#0B6FD8] text-white hover:bg-[#0855A8] shadow-xs"
                  : "bg-[#F1F5F9] text-[#48566A] hover:bg-[#E3E8EF] hover:text-[#162033]"
              }`}
            >
              {isRevoked
                ? language === "vi"
                  ? "Khôi phục gói chia sẻ"
                  : "Restore Access Packet"
                : language === "vi"
                ? "Thử nghiệm thu hồi"
                : "Simulate Revocation"}
            </button>
          </div>
        </div>

        {/* 3-Column Diagram Grid: Source -> Gate -> Destination */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
          {/* 1. Source: Personal Health Record (4 cols) */}
          <div className="lg:col-span-4 rounded-2xl bg-[#F8FAFD] p-5 border border-[#E3E8EF] flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between border-b border-[#E3E8EF] pb-3 mb-4">
                <div className="flex items-center gap-2">
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#EFF7FF] text-[#0B6FD8]">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                  </div>
                  <div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[#6D7A8E] block">
                      {language === "vi" ? "Điểm khởi nguồn" : "Origin Source"}
                    </span>
                    <h4 className="text-sm font-bold text-[#162033]">
                      {privacyCopy.diagram.source}
                    </h4>
                  </div>
                </div>
                <span className="rounded-md bg-[#EFF7FF] px-1.5 py-0.5 text-[10px] font-bold text-[#0B6FD8]">
                  AES-256
                </span>
              </div>

              {/* Data Items within Source Vault */}
              <div className="space-y-2" role="list">
                <div className="rounded-xl bg-white p-2.5 border border-[#14A88D]/30 shadow-2xs flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="h-1.5 w-1.5 rounded-full bg-[#14A88D]" />
                    <span className="text-xs font-semibold text-[#162033]">
                      {language === "vi" ? "Tiền sử dị ứng & Đơn thuốc" : "Allergies & Active Meds"}
                    </span>
                  </div>
                  <span className="text-[10px] font-bold text-[#14A88D] bg-[#ECFDF8] px-1.5 py-0.5 rounded">
                    {language === "vi" ? "Cho phép" : "Allowed"}
                  </span>
                </div>

                <div className="rounded-xl bg-white p-2.5 border border-[#14A88D]/30 shadow-2xs flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="h-1.5 w-1.5 rounded-full bg-[#14A88D]" />
                    <span className="text-xs font-semibold text-[#162033]">
                      {language === "vi" ? "Nhật ký huyết áp 60 ngày" : "60-Day BP Vitals"}
                    </span>
                  </div>
                  <span className="text-[10px] font-bold text-[#14A88D] bg-[#ECFDF8] px-1.5 py-0.5 rounded">
                    {language === "vi" ? "Cho phép" : "Allowed"}
                  </span>
                </div>

                <div className="rounded-xl bg-white p-2.5 border border-rose-200 shadow-2xs flex items-center justify-between opacity-75">
                  <div className="flex items-center gap-2">
                    <span className="h-1.5 w-1.5 rounded-full bg-rose-500" />
                    <span className="text-xs font-semibold text-[#48566A]">
                      {language === "vi" ? "Nhật ký riêng tư & Tâm lý" : "Private Personal Diary"}
                    </span>
                  </div>
                  <span className="text-[10px] font-bold text-rose-700 bg-rose-50 px-1.5 py-0.5 rounded">
                    {language === "vi" ? "Khóa kín" : "Locked"}
                  </span>
                </div>

                <div className="rounded-xl bg-white p-2.5 border border-rose-200 shadow-2xs flex items-center justify-between opacity-75">
                  <div className="flex items-center gap-2">
                    <span className="h-1.5 w-1.5 rounded-full bg-rose-500" />
                    <span className="text-xs font-semibold text-[#48566A]">
                      {language === "vi" ? "Dữ liệu viện phí & BHYT" : "Billing & Insurance"}
                    </span>
                  </div>
                  <span className="text-[10px] font-bold text-rose-700 bg-rose-50 px-1.5 py-0.5 rounded">
                    {language === "vi" ? "Khóa kín" : "Locked"}
                  </span>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-[#E3E8EF] text-[11px] text-[#6D7A8E] flex items-center gap-1.5">
              <svg className="w-3.5 h-3.5 text-[#14A88D] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
              <span>{language === "vi" ? "Chủ quyền 100% thuộc về bạn" : "100% Patient-Sovereign Data"}</span>
            </div>
          </div>

          {/* 2. Gate: Permission Boundary Policy Engine (4 cols) */}
          <div className="lg:col-span-4 rounded-2xl bg-white p-5 border-2 border-[#0B6FD8] shadow-md flex flex-col justify-between relative">
            <div className="space-y-4">
              <div className="flex items-center justify-between border-b border-[#E3E8EF] pb-3">
                <div className="flex items-center gap-2">
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#0B6FD8] text-white">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                    </svg>
                  </div>
                  <div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[#0B6FD8] block">
                      {language === "vi" ? "Ranh giới bảo mật" : "Security Perimeter"}
                    </span>
                    <h4 className="text-sm font-bold text-[#162033]">
                      {privacyCopy.diagram.gate}
                    </h4>
                  </div>
                </div>
                <span className="rounded-md bg-[#EFF7FF] px-1.5 py-0.5 text-[10px] font-bold text-[#0B6FD8] border border-[#0B6FD8]/20">
                  Zero-CoT
                </span>
              </div>

              {/* Gate Pass Channel (Allowed items) */}
              <div
                className={`rounded-xl p-3 border transition-all ${
                  isRevoked
                    ? "bg-[#F8FAFD] border-[#E3E8EF] opacity-40"
                    : "bg-[#ECFDF8] border-[#14A88D]/30"
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="flex h-4 w-4 items-center justify-center rounded-full bg-[#14A88D] text-white text-[10px] font-bold">
                    ✓
                  </span>
                  <span className="text-xs font-bold text-[#14A88D]">
                    {language === "vi" ? "Luồng cấp phép hợp lệ" : "Authorized Data Stream"}
                  </span>
                </div>
                <p className="text-[11px] text-[#48566A] leading-relaxed">
                  {privacyCopy.diagram.allowedNote}
                </p>
              </div>

              {/* Gate Block Channel (Blocked items) */}
              <div className="rounded-xl bg-[#FFF1F2] p-3 border border-rose-200">
                <div className="flex items-center gap-2 mb-1">
                  <span className="flex h-4 w-4 items-center justify-center rounded-full bg-rose-600 text-white text-[10px] font-bold">
                    ✕
                  </span>
                  <span className="text-xs font-bold text-rose-800">
                    {language === "vi" ? "Luồng chặn tự động" : "Blocked Data Boundary"}
                  </span>
                </div>
                <p className="text-[11px] text-[#48566A] leading-relaxed">
                  {privacyCopy.diagram.blockedNote}
                </p>
              </div>
            </div>

            {/* Revoke Note Pill at Bottom of Gate */}
            <div className="mt-4 pt-3 border-t border-[#E3E8EF]">
              <div className="rounded-xl bg-[#EFF7FF] p-2.5 border border-[#0B6FD8]/20 flex items-start gap-2">
                <span className="text-[#0B6FD8] text-xs font-bold mt-0.5">✦</span>
                <p className="text-[11px] text-[#0B6FD8] font-semibold leading-relaxed">
                  {privacyCopy.diagram.revokeNote}
                </p>
              </div>
            </div>
          </div>

          {/* 3. Destination: Designated Recipient (4 cols) */}
          <div className="lg:col-span-4 rounded-2xl bg-[#F8FAFD] p-5 border border-[#E3E8EF] flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between border-b border-[#E3E8EF] pb-3 mb-4">
                <div className="flex items-center gap-2">
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#EFF7FF] text-[#0B6FD8]">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                    </svg>
                  </div>
                  <div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[#6D7A8E] block">
                      {language === "vi" ? "Đích đến được chỉ định" : "Authorized Destination"}
                    </span>
                    <h4 className="text-sm font-bold text-[#162033]">
                      {privacyCopy.diagram.destination}
                    </h4>
                  </div>
                </div>
                <span
                  className={`rounded-md px-1.5 py-0.5 text-[10px] font-bold ${
                    isRevoked
                      ? "bg-rose-100 text-rose-700"
                      : "bg-[#ECFDF8] text-[#14A88D]"
                  }`}
                >
                  {isRevoked
                    ? language === "vi"
                      ? "Đã ngắt"
                      : "Revoked"
                    : language === "vi"
                    ? "Đã thẩm định"
                    : "Verified"}
                </span>
              </div>

              {/* Received Packet View */}
              {isRevoked ? (
                <div className="rounded-xl bg-rose-50/80 p-6 border border-rose-200 text-center space-y-2">
                  <span className="flex h-8 w-8 mx-auto items-center justify-center rounded-full bg-rose-100 text-rose-700 text-sm font-bold">
                    🔒
                  </span>
                  <h5 className="text-xs font-bold text-rose-900">
                    {language === "vi" ? "Gói chia sẻ đã bị thu hồi" : "Access Token Revoked"}
                  </h5>
                  <p className="text-[11px] text-rose-700 leading-relaxed">
                    {language === "vi"
                      ? "Toàn bộ phiên chia sẻ bị chấm dứt tức thời. Bên nhận không còn quyền đọc bất kỳ trường dữ liệu nào."
                      : "The session was terminated immediately. The recipient has zero access to any profile data."}
                  </p>
                </div>
              ) : (
                <div className="space-y-2.5">
                  <div className="rounded-xl bg-white p-3 border border-[#14A88D]/20 shadow-2xs">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-[#162033]">
                        {language === "vi" ? "Gói tóm tắt lâm sàng" : "Clinical Consultation Packet"}
                      </span>
                      <span className="text-[10px] font-bold text-[#14A88D] bg-[#ECFDF8] px-1.5 py-0.5 rounded">
                        Sanitized View
                      </span>
                    </div>
                    <ul className="mt-2 space-y-1 text-[11px] text-[#48566A]">
                      <li className="flex items-center gap-1.5">
                        <span className="text-[#14A88D] font-bold">✓</span>
                        {language === "vi" ? "Dị ứng: Penicillin (Nhẹ)" : "Allergy: Penicillin (Mild)"}
                      </li>
                      <li className="flex items-center gap-1.5">
                        <span className="text-[#14A88D] font-bold">✓</span>
                        {language === "vi" ? "Đơn thuốc: Metformin 500mg, Amlodipine 5mg" : "Meds: Metformin 500mg, Amlodipine 5mg"}
                      </li>
                      <li className="flex items-center gap-1.5">
                        <span className="text-[#14A88D] font-bold">✓</span>
                        {language === "vi" ? "Huyết áp trung bình: 126/82 mmHg" : "Mean BP: 126/82 mmHg"}
                      </li>
                    </ul>
                  </div>

                  <div className="rounded-xl bg-[#EFF7FF]/70 p-2.5 border border-[#0B6FD8]/15 text-[11px] text-[#0B6FD8]">
                    <span className="font-bold">Zero-CoT Guarantee:</span>{" "}
                    {language === "vi"
                      ? "Không rò rỉ vết suy luận nội bộ (Hidden Reasoning) ra bên ngoài."
                      : "Zero internal chain-of-thought traces exposed to external recipients."}
                  </div>
                </div>
              )}
            </div>

            <div className="mt-4 pt-3 border-t border-[#E3E8EF] text-[11px] text-[#6D7A8E] flex items-center justify-between">
              <span>{language === "vi" ? "Mã định danh phiên:" : "Session ID:"} 0x9F4C2A</span>
              <span className="font-mono text-[10px] text-[#14A88D] font-semibold">TLS 1.3 PASS</span>
            </div>
          </div>
        </div>
      </div>

      {/* 3 Core Sovereignty & Zero-CoT Guarantee Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-6xl mx-auto">
        {guarantees.map((item, idx) => {
          const pillColors = {
            azure: "bg-[#EFF7FF] text-[#0B6FD8] border-[#0B6FD8]/20",
            mint: "bg-[#ECFDF8] text-[#14A88D] border-[#14A88D]/20",
            iris: "bg-[#F5F3FF] text-[#8B7CF6] border-[#8B7CF6]/20",
          }[item.tagTone];

          return (
            <div
              key={idx}
              className="clara-product-surface bg-white border border-[#E3E8EF] rounded-3xl p-6 sm:p-7 shadow-xs hover:shadow-md transition-all duration-200 flex flex-col justify-between text-left"
            >
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#F8FAFD] border border-[#E3E8EF]">
                    {item.icon}
                  </div>
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-bold border ${pillColors}`}>
                    {item.tag}
                  </span>
                </div>

                <span className="text-[11px] font-bold uppercase tracking-wider text-[#6D7A8E]">
                  {item.subtitle}
                </span>
                <h3 className="text-base sm:text-lg font-bold text-[#162033] mt-1 mb-2.5">
                  {item.title}
                </h3>
                <p className="text-xs sm:text-sm text-[#48566A] leading-relaxed">
                  {item.description}
                </p>
              </div>

              <div className="mt-6 pt-4 border-t border-[#E3E8EF]/70 flex items-center gap-1.5 text-xs font-bold text-[#162033]">
                <span className="text-[#14A88D]">✓</span>
                <span>{language === "vi" ? "Cam kết chuẩn y tế số" : "Digital Health Standard"}</span>
              </div>
            </div>
          );
        })}
      </div>
    </LandingScene>
  );
}
