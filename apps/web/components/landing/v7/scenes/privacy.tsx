"use client";

import React, { useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";
import { SpatialStage } from "../primitives/spatial-stage";
import { PermissionGate } from "../artwork/permission-gate";
import { EvidenceRibbon } from "../artwork/evidence-ribbon";
import { FloatingMetadata } from "../primitives/floating-metadata";

/**
 * PrivacyScene (Landing v7)
 *
 * Zero-CoT Data Privacy Boundary Scene:
 * - PermissionGate Motif: Spatial boundary illustrating explicit data filtering:
 *   allowed clinical fields pass through, while sensitive personal data is halted at the boundary.
 * - Live interactive Revocation test: Users can simulate instant single-tap permission termination.
 * - 3 Core Privacy Guarantees: Zero-CoT Enclave Isolation, Zero Model Training, AES-256/TLS 1.3 Sovereignty.
 * - Three-zone architecture: Source (PHR) ➔ Gate (Zero-CoT) ➔ Destination (Clinician).
 */
export function PrivacyScene() {
  const { language, isEnhanced } = useMotionTier();
  const lang = language === "en" ? "en" : "vi";
  const copy = LANDING_COPY_V7[lang]?.privacy ?? LANDING_COPY_V7.vi.privacy;

  const [isRevoked, setIsRevoked] = useState<boolean>(false);

  const privacyBadge =
    lang === "vi"
      ? "KIẾN TRÚC ZERO-COT • AES-256 GCM"
      : "ZERO-COT ENCLAVE • AES-256 GCM";

  const metaLabel1 = lang === "vi" ? "Cách ly suy luận" : "Reasoning Isolation";
  const metaValue1 =
    lang === "vi" ? "Zero-CoT Enclave Bảo vệ" : "Zero-CoT Enclave Protected";
  const metaTag1 = "Zero Leak";

  const metaLabel2 = lang === "vi" ? "Quyền dữ liệu" : "Data Sovereignty";
  const metaValue2 =
    lang === "vi" ? "Không dùng huấn luyện AI" : "Zero Model Training";
  const metaTag2 = "Decree 13 / GDPR";

  const guarantees = [
    {
      title: lang === "vi" ? "Cách ly suy luận Zero-CoT" : "Zero-CoT Reasoning Isolation",
      subtitle: lang === "vi" ? "Không rò rỉ vết suy luận nội bộ" : "Zero Internal Trace Leakage",
      description:
        lang === "vi"
          ? "Chuỗi suy luận thô (Chain-of-Thought) và các bước xử lý trung gian được giữ kín trong vùng an toàn nội bộ. Người nhận chỉ tiếp cận kết luận lâm sàng đã được kiểm chứng."
          : "Raw Chain-of-Thought reasoning steps are strictly isolated within our secure enclave. External consumers only receive verified, finalized clinical syntheses.",
      tag: "Zero-CoT Enclave",
      tone: "text-[#0B6FD8] bg-[#EFF7FF] border-[#0B6FD8]/20",
    },
    {
      title: lang === "vi" ? "Tuyệt đối không huấn luyện" : "Zero Model Training",
      subtitle: lang === "vi" ? "Dữ liệu người dùng là bất khả xâm phạm" : "User Records Are Strictly Private",
      description:
        lang === "vi"
          ? "Toàn bộ hồ sơ bệnh án, lịch sử hội thoại và đơn thuốc cá nhân không bao giờ bị sử dụng để huấn luyện (train/fine-tune) bất kỳ mô hình AI nào khi chưa có văn bản đồng thuận."
          : "Your medical records, conversation history, and uploaded prescriptions are never used to train or fine-tune AI models without explicit, affirmative consent.",
      tag: "No Model Training",
      tone: "text-[#14A88D] bg-[#ECFDF8] border-[#14A88D]/20",
    },
    {
      title: lang === "vi" ? "Chủ quyền & Thu hồi tức thì" : "Sovereignty & Instant Revocation",
      subtitle: lang === "vi" ? "Toàn quyền cấp và hủy bỏ trong 1 chạm" : "Instant 1-Click Access Termination",
      description:
        lang === "vi"
          ? "Mọi chia sẻ hồ sơ sức khỏe đều có thời hạn xác định và có thể bị thu hồi ngay lập tức. Hệ thống áp dụng chuẩn mã hóa ngân hàng AES-256 ở trạng thái nghỉ và TLS 1.3 khi truyền tải."
          : "Every health record share operates on time-bounded tokens that can be revoked in real time. Backed by banking-grade AES-256 at rest and TLS 1.3 in transit.",
      tag: "AES-256 / TLS 1.3",
      tone: "text-[#8B7CF6] bg-[#F5F3FF] border-[#8B7CF6]/20",
    },
  ];

  return (
    <LandingScene
      id="privacy"
      scale="standard"
      tone="canvas"
      className="relative overflow-hidden pt-20 pb-24 md:pt-28 md:pb-36"
    >
      {/* Background Top Transition Ribbon (Handoff from Safety scene) */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-16 opacity-30 flex items-center justify-center overflow-hidden"
      >
        <EvidenceRibbon variant="horizontal" tone="azure" active={true} className="w-full max-w-6xl" />
      </div>

      {/* Scene Editorial Header */}
      <div className="relative z-10 max-w-4xl mx-auto mb-10 md:mb-14 px-2 sm:px-4">
        <SceneHeader
          eyebrow={copy.eyebrow}
          badge={privacyBadge}
          title={copy.title}
          description={copy.description}
          align="center"
          tone="azure"
          className="mb-0"
        />
      </div>

      {/* Main Spatial Stage wrapping PermissionGate & Sovereignty Controls */}
      <div className="relative mx-auto max-w-5xl w-full px-2 sm:px-4 space-y-8">
        <SpatialStage enablePointerTilt={isEnhanced}>
          <div className="relative">
            {/* Interactive Revocation Controller Bar */}
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-white p-4 border border-[#E3E8EF] shadow-xs">
              <div className="flex items-center gap-3">
                <span
                  className={`h-3 w-3 rounded-full transition-colors ${
                    isRevoked ? "bg-rose-600 animate-pulse" : "bg-emerald-500"
                  }`}
                />
                <div>
                  <span className="text-xs font-bold text-[#162033] block">
                    {isRevoked
                      ? lang === "vi"
                        ? "Trạng thái: Đã thu hồi toàn bộ quyền truy cập (Khóa cổng)"
                        : "Status: All Access Permissions Terminated (Gate Locked)"
                      : lang === "vi"
                      ? "Trạng thái: Đang truyền dữ liệu có giới hạn (3 trường được duyệt)"
                      : "Status: Active Bounded Stream (3 Fields Permitted)"}
                  </span>
                  <span className="text-[11px] text-[#6D7A8E]">
                    {lang === "vi"
                      ? "Nhấn nút bên phải để kiểm tra cơ chế ngắt luồng tức thời"
                      : "Click button on right to test real-time instant stream revocation"}
                  </span>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setIsRevoked((prev) => !prev)}
                className={`rounded-xl px-4 py-2 text-xs font-bold transition-all clara-focus-ring ${
                  isRevoked
                    ? "bg-emerald-600 text-white hover:bg-emerald-700 shadow-xs"
                    : "bg-rose-600 text-white hover:bg-rose-700 shadow-xs"
                }`}
              >
                {isRevoked
                  ? lang === "vi"
                    ? "Kích hoạt lại chia sẻ"
                    : "Re-enable Access"
                  : lang === "vi"
                  ? "Thu hồi quyền tức thì"
                  : "Instant Revoke"}
              </button>
            </div>

            {/* PermissionGate Artwork Motif */}
            <PermissionGate
              isRevoked={isRevoked}
              allowedCount={3}
              blockedCount={2}
              expiryText={lang === "vi" ? "24 giờ" : "24 hours"}
              className="shadow-2xl"
            />

            {/* Floating Metadata 1 (Top Left / Overflow) */}
            <FloatingMetadata
              label={metaLabel1}
              value={metaValue1}
              tag={metaTag1}
              tone="azure"
              className="absolute -top-4 -left-4 hidden lg:inline-flex"
            />

            {/* Floating Metadata 2 (Bottom Right / Overflow) */}
            <FloatingMetadata
              label={metaLabel2}
              value={metaValue2}
              tag={metaTag2}
              tone="mint"
              className="absolute -bottom-4 -right-4 hidden lg:inline-flex"
            />
          </div>
        </SpatialStage>

        {/* 3 Core Privacy Guarantees */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 pt-2">
          {guarantees.map((g) => (
            <div
              key={g.title}
              className="rounded-2xl bg-white p-5 sm:p-6 border border-[#E3E8EF] shadow-xs flex flex-col justify-between text-left space-y-3 transition-all hover:border-[#0B6FD8]/30 hover:shadow-sm"
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className="font-bold text-sm text-[#162033]">{g.title}</span>
                  <span
                    className={`rounded px-2 py-0.5 text-[10px] font-bold border ${g.tone}`}
                  >
                    {g.tag}
                  </span>
                </div>
                <span className="text-xs font-semibold text-[#0B6FD8] block mb-1.5">
                  {g.subtitle}
                </span>
                <p className="text-xs text-[#48566A] leading-relaxed">{g.description}</p>
              </div>
            </div>
          ))}
        </div>

        {/* 3-Zone Architecture Telemetry Footer */}
        <div className="rounded-2xl bg-[#F8FAFD] p-4 border border-[#E3E8EF] flex flex-wrap items-center justify-between gap-3 text-xs text-[#6D7A8E]">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-bold text-[#162033]">
              {copy.diagram.source}
            </span>
            <span>➔</span>
            <span className="font-bold text-[#0B6FD8]">
              {copy.diagram.gate}
            </span>
            <span>➔</span>
            <span className="font-bold text-[#14A88D]">
              {copy.diagram.destination}
            </span>
          </div>

          <span className="text-[11px] font-semibold text-[#48566A]">
            {copy.diagram.allowedNote} • {copy.diagram.revokeNote}
          </span>
        </div>
      </div>

      {/* Transition Ribbon Flowing toward Scenarios Scene */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-10 left-1/2 -translate-x-1/2 w-full max-w-2xl opacity-50 hidden md:block"
      >
        <EvidenceRibbon variant="curved" tone="mint" active={true} className="h-20 w-full" />
      </div>
    </LandingScene>
  );
}

export default PrivacyScene;
