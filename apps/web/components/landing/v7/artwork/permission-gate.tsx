"use client";

import React, { useId } from "react";

export interface PermissionGateProps {
  /** Whether the sharing permission has been revoked by the patient */
  isRevoked?: boolean;
  /** Number of allowed clinical fields passing through the gate */
  allowedCount?: number;
  /** Number of sensitive fields halted at the boundary */
  blockedCount?: number;
  /** Human-readable expiration text (e.g., "24 giờ", "24h", "Valid for 24h") */
  expiryText?: string;
  /** Additional CSS class names */
  className?: string;
}

/**
 * PermissionGate Artwork Component (Landing v7)
 *
 * Renders the spatial data-boundary artwork demonstrating bounded sharing:
 * - Allowed data lines (Green / #14A88D) pass cleanly through the gate aperture into the clinical enclave.
 * - Blocked sensitive fields (Red / #F43F5E) halt strictly at the boundary perimeter with deflection ripples.
 * - Dynamic revocation state toggles the gate into lockdown mode, terminating all active flows.
 */
export function PermissionGate({
  isRevoked = false,
  allowedCount = 3,
  blockedCount = 2,
  expiryText = "24 giờ",
  className = "",
}: PermissionGateProps) {
  const rawId = useId();
  const uid = rawId.replace(/[^a-zA-Z0-9-_]/g, "");

  // Gradients and filter IDs
  const gradAllowedId = `perm-gate-grad-allowed-${uid}`;
  const gradBlockedId = `perm-gate-grad-blocked-${uid}`;
  const gradRevokedId = `perm-gate-grad-revoked-${uid}`;
  const gradGateBeamId = `perm-gate-grad-beam-${uid}`;
  const gradGateBlockedBeamId = `perm-gate-grad-blocked-beam-${uid}`;
  const filterGlowGreenId = `perm-gate-glow-green-${uid}`;
  const filterGlowRedId = `perm-gate-glow-red-${uid}`;
  const patternVoidId = `perm-gate-pattern-void-${uid}`;

  return (
    <div
      data-testid="permission-gate"
      data-artwork="permission-gate"
      data-revoked={String(isRevoked)}
      data-allowed-count={allowedCount}
      data-blocked-count={blockedCount}
      className={`relative w-full overflow-hidden rounded-3xl border border-[#E3E8EF] bg-gradient-to-b from-[#FFFFFF] via-[#F8FAFD] to-[#F1F5F9] p-4 sm:p-6 lg:p-7 shadow-xl transition-all duration-300 ${className}`}
    >
      {/* Visual Header / Telemetry Bar */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-[#E3E8EF]/80 pb-3.5">
        <div className="flex items-center gap-2.5">
          <div
            className={`flex h-7 w-7 items-center justify-center rounded-xl font-black text-xs shadow-xs transition-colors duration-300 ${
              isRevoked
                ? "bg-rose-600 text-white"
                : "bg-[#0B6FD8] text-white"
            }`}
          >
            {isRevoked ? "✕" : "✦"}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-[#162033]">
                Zero-CoT Permission Gate
              </span>
              <span className="rounded-full bg-[#EFF7FF] px-2 py-0.5 text-[10px] font-bold text-[#0B6FD8] border border-[#0B6FD8]/20">
                AES-256 GCM
              </span>
            </div>
            <p className="text-[11px] text-[#6D7A8E]">
              {isRevoked
                ? "Ranh giới đã kích hoạt chế độ thu hồi tức thời"
                : "Minh họa không gian luồng truyền dữ liệu qua ranh giới bảo mật"}
            </p>
          </div>
        </div>

        {/* Live Status Badge */}
        <div className="flex items-center gap-2.5">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold border transition-all duration-300 ${
              isRevoked
                ? "bg-rose-50 text-rose-700 border-rose-200"
                : "bg-[#ECFDF8] text-[#14A88D] border-[#14A88D]/25"
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                isRevoked ? "bg-rose-600" : "bg-[#14A88D] animate-pulse"
              }`}
            />
            {isRevoked ? "Đã ngắt quyền truy cập" : `Thời hạn token: ${expiryText}`}
          </span>
        </div>
      </div>

      {/* Main SVG Spatial Boundary Canvas */}
      <div className="relative w-full overflow-hidden rounded-2xl bg-white/80 p-2 sm:p-3 border border-[#E3E8EF]/60 shadow-inner">
        <svg
          viewBox="0 0 800 370"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="w-full h-auto select-none"
          preserveAspectRatio="xMidYMid meet"
          role="img"
          aria-label="Minh họa Cổng phân quyền dữ liệu có ranh giới: Dữ liệu cho phép đi qua cổng, dữ liệu nhạy cảm bị chặn tại ranh giới"
        >
          <defs>
            {/* Green Allowed Flow Gradient */}
            <linearGradient id={gradAllowedId} x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#14A88D" stopOpacity="0.85" />
              <stop offset="50%" stopColor="#10B981" stopOpacity="1" />
              <stop offset="100%" stopColor="#14A88D" stopOpacity="0.9" />
            </linearGradient>

            {/* Red Blocked Flow Gradient */}
            <linearGradient id={gradBlockedId} x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#F43F5E" stopOpacity="0.8" />
              <stop offset="70%" stopColor="#E11D48" stopOpacity="0.95" />
              <stop offset="100%" stopColor="#BE123C" stopOpacity="1" />
            </linearGradient>

            {/* Revoked Truncated Gradient */}
            <linearGradient id={gradRevokedId} x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#94A3B8" stopOpacity="0.7" />
              <stop offset="50%" stopColor="#F43F5E" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#E11D48" stopOpacity="0.2" />
            </linearGradient>

            {/* Gate Vertical Beam Gradient (Allowed Active) */}
            <linearGradient id={gradGateBeamId} x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#14A88D" stopOpacity="0.05" />
              <stop offset="25%" stopColor="#14A88D" stopOpacity="0.8" />
              <stop offset="60%" stopColor="#0B6FD8" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#14A88D" stopOpacity="0.1" />
            </linearGradient>

            {/* Gate Vertical Beam Gradient (Blocked Area) */}
            <linearGradient id={gradGateBlockedBeamId} x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#F43F5E" stopOpacity="0.2" />
              <stop offset="40%" stopColor="#E11D48" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#9F1239" stopOpacity="0.15" />
            </linearGradient>

            {/* Glow Filter Green */}
            <filter id={filterGlowGreenId} x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>

            {/* Glow Filter Red */}
            <filter id={filterGlowRedId} x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3.5" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>

            {/* Void / Isolated Enclave Hatch Pattern */}
            <pattern
              id={patternVoidId}
              width="12"
              height="12"
              patternUnits="userSpaceOnUse"
              patternTransform="rotate(45)"
            >
              <line x1="0" y1="0" x2="0" y2="12" stroke="#FEE2E2" strokeWidth="1.5" />
            </pattern>
          </defs>

          {/* Background Micro Grid */}
          <g opacity="0.4">
            <line x1="40" y1="60" x2="760" y2="60" stroke="#E3E8EF" strokeDasharray="3 3" />
            <line x1="40" y1="120" x2="760" y2="120" stroke="#E3E8EF" strokeDasharray="3 3" />
            <line x1="40" y1="180" x2="760" y2="180" stroke="#E3E8EF" strokeDasharray="3 3" />
            <line x1="40" y1="240" x2="760" y2="240" stroke="#E3E8EF" strokeDasharray="3 3" />
            <line x1="40" y1="300" x2="760" y2="300" stroke="#E3E8EF" strokeDasharray="3 3" />
          </g>

          {/* ============================================================ */}
          {/* ZONE 1: ORIGIN / PATIENT SOVEREIGN VAULT (Left: x=30 to 220) */}
          {/* ============================================================ */}
          <g id="origin-vault-compartment">
            <rect
              x="30"
              y="25"
              width="190"
              height="320"
              rx="16"
              fill="#F8FAFD"
              stroke="#E3E8EF"
              strokeWidth="1.5"
            />
            {/* Compartment Header */}
            <rect x="42" y="37" width="22" height="22" rx="6" fill="#EFF7FF" />
            <text x="53" y="52" fill="#0B6FD8" fontSize="11" fontWeight="bold" textAnchor="middle">
              ☤
            </text>
            <text x="72" y="47" fill="#6D7A8E" fontSize="9" fontWeight="bold" letterSpacing="0.05em">
              ORIGIN VAULT
            </text>
            <text x="72" y="58" fill="#162033" fontSize="11" fontWeight="bold">
              Hồ sơ Gốc (PHR)
            </text>
            <rect x="165" y="40" width="44" height="16" rx="4" fill="#EFF7FF" />
            <text x="187" y="51" fill="#0B6FD8" fontSize="8.5" fontWeight="bold" textAnchor="middle">
              AES-256
            </text>
            <line x1="42" y1="67" x2="208" y2="67" stroke="#E3E8EF" strokeWidth="1" />

            {/* Allowed Data Items in Vault */}
            {/* Item 1: Allergies */}
            <g id="vault-item-allergies">
              <rect x="42" y="78" width="166" height="34" rx="8" fill="#FFFFFF" stroke="#14A88D" strokeWidth="1" strokeOpacity="0.4" />
              <circle cx="54" cy="95" r="4" fill="#14A88D" />
              <text x="64" y="92" fill="#162033" fontSize="10" fontWeight="bold">
                Tiền sử dị ứng
              </text>
              <text x="64" y="103" fill="#6D7A8E" fontSize="8">
                Penicillin (Urticaria)
              </text>
              <rect x="162" y="85" width="40" height="15" rx="3.5" fill="#ECFDF8" />
              <text x="182" y="96" fill="#14A88D" fontSize="8" fontWeight="bold" textAnchor="middle">
                Cấp phép
              </text>
            </g>

            {/* Item 2: Active Meds */}
            <g id="vault-item-meds">
              <rect x="42" y="120" width="166" height="34" rx="8" fill="#FFFFFF" stroke="#14A88D" strokeWidth="1" strokeOpacity="0.4" />
              <circle cx="54" cy="137" r="4" fill="#14A88D" />
              <text x="64" y="134" fill="#162033" fontSize="10" fontWeight="bold">
                Đơn thuốc hiện tại
              </text>
              <text x="64" y="145" fill="#6D7A8E" fontSize="8">
                Metformin, Amlodipine
              </text>
              <rect x="162" y="127" width="40" height="15" rx="3.5" fill="#ECFDF8" />
              <text x="182" y="138" fill="#14A88D" fontSize="8" fontWeight="bold" textAnchor="middle">
                Cấp phép
              </text>
            </g>

            {/* Item 3: Vitals */}
            <g id="vault-item-vitals">
              <rect x="42" y="162" width="166" height="34" rx="8" fill="#FFFFFF" stroke="#14A88D" strokeWidth="1" strokeOpacity="0.4" />
              <circle cx="54" cy="179" r="4" fill="#14A88D" />
              <text x="64" y="176" fill="#162033" fontSize="10" fontWeight="bold">
                Nhật ký Huyết áp
              </text>
              <text x="64" y="187" fill="#6D7A8E" fontSize="8">
                60 ngày gần nhất
              </text>
              <rect x="162" y="169" width="40" height="15" rx="3.5" fill="#ECFDF8" />
              <text x="182" y="180" fill="#14A88D" fontSize="8" fontWeight="bold" textAnchor="middle">
                Cấp phép
              </text>
            </g>

            {/* Divider between Allowed and Blocked in Vault */}
            <line x1="42" y1="206" x2="208" y2="206" stroke="#E2E8F0" strokeDasharray="3 2" />

            {/* Blocked Data Items in Vault */}
            {/* Item 4: Sensitive Notes */}
            <g id="vault-item-notes">
              <rect x="42" y="216" width="166" height="34" rx="8" fill="#FFF1F2" stroke="#F43F5E" strokeWidth="1" strokeOpacity="0.35" />
              <circle cx="54" cy="233" r="4" fill="#F43F5E" />
              <text x="64" y="230" fill="#48566A" fontSize="10" fontWeight="bold">
                Ghi chú riêng tư
              </text>
              <text x="64" y="241" fill="#94A3B8" fontSize="8">
                Nhật ký tâm lý cá nhân
              </text>
              <rect x="162" y="223" width="40" height="15" rx="3.5" fill="#FFE4E6" />
              <text x="182" y="234" fill="#E11D48" fontSize="8" fontWeight="bold" textAnchor="middle">
                Khóa kín
              </text>
            </g>

            {/* Item 5: Financial / Billing */}
            <g id="vault-item-billing">
              <rect x="42" y="258" width="166" height="34" rx="8" fill="#FFF1F2" stroke="#F43F5E" strokeWidth="1" strokeOpacity="0.35" />
              <circle cx="54" cy="275" r="4" fill="#F43F5E" />
              <text x="64" y="272" fill="#48566A" fontSize="10" fontWeight="bold">
                BHYT & Viện phí
              </text>
              <text x="64" y="283" fill="#94A3B8" fontSize="8">
                Lịch sử thanh toán
              </text>
              <rect x="162" y="265" width="40" height="15" rx="3.5" fill="#FFE4E6" />
              <text x="182" y="276" fill="#E11D48" fontSize="8" fontWeight="bold" textAnchor="middle">
                Khóa kín
              </text>
            </g>

            {/* Vault Footer Sovereignty Note */}
            <text x="125" y="322" fill="#6D7A8E" fontSize="8.5" textAnchor="middle">
              🔒 Chủ quyền thuộc bệnh nhân
            </text>
          </g>

          {/* ============================================================ */}
          {/* ZONE 2: THE PERMISSION GATE BARRIER (Center: x=360 to 440)   */}
          {/* ============================================================ */}
          <g id="permission-boundary-gate">
            {/* Gate Column Background Capsule */}
            <rect
              x="368"
              y="20"
              width="64"
              height="330"
              rx="18"
              fill={isRevoked ? "#FFF1F2" : "#FFFFFF"}
              stroke={isRevoked ? "#F43F5E" : "#0B6FD8"}
              strokeWidth="2"
              className="transition-colors duration-300"
            />

            {/* Gate Glow Beams */}
            {/* Top Beam: Allowed Aperture Region */}
            <rect
              x="396"
              y="25"
              width="8"
              height="180"
              rx="4"
              fill={isRevoked ? `url(#${gradGateBlockedBeamId})` : `url(#${gradGateBeamId})`}
              filter={isRevoked ? `url(#${filterGlowRedId})` : `url(#${filterGlowGreenId})`}
            />

            {/* Bottom Beam: Blocked Containment Region */}
            <rect
              x="396"
              y="215"
              width="8"
              height="130"
              rx="4"
              fill={`url(#${gradGateBlockedBeamId})`}
              filter={`url(#${filterGlowRedId})`}
            />

            {/* Upper Gate Aperture (Allowed Pass-Through Area) */}
            <g id="gate-aperture-upper">
              {!isRevoked ? (
                <>
                  {/* Active Laser Rings / Optical Aperture */}
                  <ellipse cx="400" cy="95" rx="14" ry="7" fill="#ECFDF8" stroke="#14A88D" strokeWidth="1.5" />
                  <ellipse cx="400" cy="137" rx="14" ry="7" fill="#ECFDF8" stroke="#14A88D" strokeWidth="1.5" />
                  <ellipse cx="400" cy="179" rx="14" ry="7" fill="#ECFDF8" stroke="#14A88D" strokeWidth="1.5" />
                </>
              ) : (
                <>
                  {/* Revoked Lockdown Barriers */}
                  <line x1="384" y1="87" x2="416" y2="103" stroke="#E11D48" strokeWidth="2.5" strokeLinecap="round" />
                  <line x1="384" y1="103" x2="416" y2="87" stroke="#E11D48" strokeWidth="2.5" strokeLinecap="round" />
                  <line x1="384" y1="129" x2="416" y2="145" stroke="#E11D48" strokeWidth="2.5" strokeLinecap="round" />
                  <line x1="384" y1="145" x2="416" y2="129" stroke="#E11D48" strokeWidth="2.5" strokeLinecap="round" />
                  <line x1="384" y1="171" x2="416" y2="187" stroke="#E11D48" strokeWidth="2.5" strokeLinecap="round" />
                  <line x1="384" y1="187" x2="416" y2="171" stroke="#E11D48" strokeWidth="2.5" strokeLinecap="round" />
                </>
              )}
            </g>

            {/* Lower Gate Barrier: Deflection Shield Arcs (Sensitive Block Area) */}
            <g id="gate-deflector-lower">
              {/* Deflection Impact Arcs where blocked lines hit */}
              <path
                d="M 390 220 Q 375 233 390 246"
                fill="none"
                stroke="#E11D48"
                strokeWidth="2.5"
                strokeLinecap="round"
                filter={`url(#${filterGlowRedId})`}
              />
              <circle cx="380" cy="233" r="3.5" fill="#E11D48" />

              <path
                d="M 390 262 Q 375 275 390 288"
                fill="none"
                stroke="#E11D48"
                strokeWidth="2.5"
                strokeLinecap="round"
                filter={`url(#${filterGlowRedId})`}
              />
              <circle cx="380" cy="275" r="3.5" fill="#E11D48" />

              {/* Deflection Burst Ripples */}
              <path d="M 374 228 L 368 224" stroke="#F43F5E" strokeWidth="1.5" strokeLinecap="round" />
              <path d="M 374 238 L 368 242" stroke="#F43F5E" strokeWidth="1.5" strokeLinecap="round" />
              <path d="M 374 270 L 368 266" stroke="#F43F5E" strokeWidth="1.5" strokeLinecap="round" />
              <path d="M 374 280 L 368 284" stroke="#F43F5E" strokeWidth="1.5" strokeLinecap="round" />
            </g>

            {/* Central Monolith Core Badge */}
            <g id="gate-central-core">
              <circle
                cx="400"
                cy="204"
                r="18"
                fill={isRevoked ? "#FFF1F2" : "#FFFFFF"}
                stroke={isRevoked ? "#E11D48" : "#0B6FD8"}
                strokeWidth="2"
                shadow-md="true"
              />
              <circle
                cx="400"
                cy="204"
                r="13"
                fill={isRevoked ? "#E11D48" : "#0B6FD8"}
              />
              <text
                x="400"
                y="208"
                fill="#FFFFFF"
                fontSize="11"
                fontWeight="900"
                textAnchor="middle"
              >
                {isRevoked ? "✕" : "🛡"}
              </text>
            </g>

            {/* Gate Top Label */}
            <text
              x="400"
              y="38"
              fill={isRevoked ? "#E11D48" : "#0B6FD8"}
              fontSize="8"
              fontWeight="900"
              letterSpacing="0.08em"
              textAnchor="middle"
            >
              {isRevoked ? "LOCKED" : "GATEWAY"}
            </text>

            {/* Gate Bottom Barrier Marker */}
            <rect
              x="376"
              y="320"
              width="48"
              height="15"
              rx="4"
              fill={isRevoked ? "#FFE4E6" : "#EFF7FF"}
              stroke={isRevoked ? "#FDA4AF" : "#BFDBFE"}
              strokeWidth="1"
            />
            <text
              x="400"
              y="330.5"
              fill={isRevoked ? "#E11D48" : "#0B6FD8"}
              fontSize="7.5"
              fontWeight="bold"
              textAnchor="middle"
            >
              {isRevoked ? "ĐÃ KHÓA" : "CHẶN 100%"}
            </text>
          </g>

          {/* ============================================================ */}
          {/* ZONE 3: DESTINATION / CLINICAL ENCLAVE (Right: x=580 to 770) */}
          {/* ============================================================ */}
          <g id="destination-enclave-compartment">
            <rect
              x="580"
              y="25"
              width="190"
              height="320"
              rx="16"
              fill={isRevoked ? "#FFF1F2" : "#F8FAFD"}
              stroke={isRevoked ? "#FDA4AF" : "#E3E8EF"}
              strokeWidth="1.5"
              className="transition-colors duration-300"
            />
            {/* Compartment Header */}
            <rect
              x="592"
              y="37"
              width="22"
              height="22"
              rx="6"
              fill={isRevoked ? "#FFE4E6" : "#EFF7FF"}
            />
            <text
              x="603"
              y="52"
              fill={isRevoked ? "#E11D48" : "#0B6FD8"}
              fontSize="11"
              fontWeight="bold"
              textAnchor="middle"
            >
              ✚
            </text>
            <text x="622" y="47" fill="#6D7A8E" fontSize="9" fontWeight="bold" letterSpacing="0.05em">
              AUTHORIZED DESTINATION
            </text>
            <text x="622" y="58" fill="#162033" fontSize="11" fontWeight="bold">
              Bác sĩ Tim mạch
            </text>
            <rect
              x="716"
              y="40"
              width="44"
              height="16"
              rx="4"
              fill={isRevoked ? "#FFE4E6" : "#ECFDF8"}
            />
            <text
              x="738"
              y="51"
              fill={isRevoked ? "#E11D48" : "#14A88D"}
              fontSize="8.5"
              fontWeight="bold"
              textAnchor="middle"
            >
              {isRevoked ? "REVOKED" : "VERIFIED"}
            </text>
            <line x1="592" y1="67" x2="758" y2="67" stroke="#E3E8EF" strokeWidth="1" />

            {/* Receiving Intake Channels */}
            {!isRevoked ? (
              <>
                {/* Port 1: Received Allergies */}
                <g id="dest-item-allergies">
                  <rect x="592" y="78" width="166" height="34" rx="8" fill="#FFFFFF" stroke="#14A88D" strokeWidth="1" strokeOpacity="0.4" />
                  <circle cx="604" cy="95" r="4" fill="#14A88D" />
                  <text x="614" y="92" fill="#162033" fontSize="10" fontWeight="bold">
                    Tiền sử dị ứng
                  </text>
                  <text x="614" y="103" fill="#14A88D" fontSize="8" fontWeight="medium">
                    ✓ Đã nhận an toàn
                  </text>
                  <rect x="712" y="85" width="40" height="15" rx="3.5" fill="#ECFDF8" />
                  <text x="732" y="96" fill="#14A88D" fontSize="8" fontWeight="bold" textAnchor="middle">
                    Đã nhận
                  </text>
                </g>

                {/* Port 2: Received Active Meds */}
                <g id="dest-item-meds">
                  <rect x="592" y="120" width="166" height="34" rx="8" fill="#FFFFFF" stroke="#14A88D" strokeWidth="1" strokeOpacity="0.4" />
                  <circle cx="604" cy="137" r="4" fill="#14A88D" />
                  <text x="614" y="134" fill="#162033" fontSize="10" fontWeight="bold">
                    Đơn thuốc hiện tại
                  </text>
                  <text x="614" y="145" fill="#14A88D" fontSize="8" fontWeight="medium">
                    ✓ Đã nhận an toàn
                  </text>
                  <rect x="712" y="127" width="40" height="15" rx="3.5" fill="#ECFDF8" />
                  <text x="732" y="138" fill="#14A88D" fontSize="8" fontWeight="bold" textAnchor="middle">
                    Đã nhận
                  </text>
                </g>

                {/* Port 3: Received Vitals */}
                <g id="dest-item-vitals">
                  <rect x="592" y="162" width="166" height="34" rx="8" fill="#FFFFFF" stroke="#14A88D" strokeWidth="1" strokeOpacity="0.4" />
                  <circle cx="604" cy="179" r="4" fill="#14A88D" />
                  <text x="614" y="176" fill="#162033" fontSize="10" fontWeight="bold">
                    Nhật ký Huyết áp
                  </text>
                  <text x="614" y="187" fill="#14A88D" fontSize="8" fontWeight="medium">
                    ✓ Đã nhận an toàn
                  </text>
                  <rect x="712" y="169" width="40" height="15" rx="3.5" fill="#ECFDF8" />
                  <text x="732" y="180" fill="#14A88D" fontSize="8" fontWeight="bold" textAnchor="middle">
                    Đã nhận
                  </text>
                </g>
              </>
            ) : (
              /* When Revoked: Destination Locked Out */
              <g id="dest-revoked-state">
                <rect x="592" y="78" width="166" height="118" rx="8" fill="#FFFFFF" stroke="#FDA4AF" strokeWidth="1" />
                <circle cx="675" cy="115" r="14" fill="#FFE4E6" />
                <text x="675" y="120" fill="#E11D48" fontSize="14" textAnchor="middle">
                  🔒
                </text>
                <text x="675" y="145" fill="#E11D48" fontSize="11" fontWeight="bold" textAnchor="middle">
                  Phiên chia sẻ đã ngắt
                </text>
                <text x="675" y="160" fill="#6D7A8E" fontSize="9" textAnchor="middle">
                  Bên nhận mất toàn bộ quyền đọc
                </text>
                <text x="675" y="174" fill="#94A3B8" fontSize="8" textAnchor="middle">
                  Zero CoT & Zero Record Retention
                </text>
              </g>
            )}

            {/* Blocked Isolation Zone (Crosshatched Void Area) */}
            <g id="dest-void-zone">
              <rect
                x="592"
                y="216"
                width="166"
                height="76"
                rx="8"
                fill={`url(#${patternVoidId})`}
                stroke="#FECDD3"
                strokeWidth="1"
              />
              <rect x="612" y="235" width="126" height="38" rx="6" fill="#FFFFFF" stroke="#FDA4AF" strokeWidth="1" opacity="0.95" />
              <text x="675" y="250" fill="#E11D48" fontSize="9" fontWeight="bold" textAnchor="middle">
                🚫 VÙNG CÁCH LY TUYỆT ĐỐI
              </text>
              <text x="675" y="262" fill="#6D7A8E" fontSize="8" textAnchor="middle">
                0 trường nhạy cảm lọt qua
              </text>
            </g>

            {/* Destination Footer Audit Note */}
            <text x="675" y="322" fill="#6D7A8E" fontSize="8.5" textAnchor="middle">
              {isRevoked ? "Đã vô hiệu hóa token" : "Phiên kiểm chứng an toàn"}
            </text>
          </g>

          {/* ============================================================ */}
          {/* DATA FLOW STREAMS (Connecting Lines)                         */}
          {/* ============================================================ */}
          {/* 1. ALLOWED FLOW STREAMS (Green / #14A88D) */}
          <g id="allowed-flow-streams">
            {!isRevoked ? (
              <>
                {/* Stream 1: Allergies (y=95) */}
                <path
                  d="M 208 95 L 368 95 M 432 95 L 580 95"
                  fill="none"
                  stroke={`url(#${gradAllowedId})`}
                  strokeWidth="3"
                  strokeLinecap="round"
                  filter={`url(#${filterGlowGreenId})`}
                />
                {/* Through-gate continuous beam */}
                <line x1="368" y1="95" x2="432" y2="95" stroke="#10B981" strokeWidth="3" strokeDasharray="3 3" />
                {/* Animated data pulses */}
                <circle cx="280" cy="95" r="3.5" fill="#FFFFFF" stroke="#14A88D" strokeWidth="1.5" className="motion-safe:animate-pulse" />
                <circle cx="505" cy="95" r="3.5" fill="#FFFFFF" stroke="#14A88D" strokeWidth="1.5" className="motion-safe:animate-pulse" />

                {/* Stream 2: Meds (y=137) */}
                <path
                  d="M 208 137 L 368 137 M 432 137 L 580 137"
                  fill="none"
                  stroke={`url(#${gradAllowedId})`}
                  strokeWidth="3"
                  strokeLinecap="round"
                  filter={`url(#${filterGlowGreenId})`}
                />
                <line x1="368" y1="137" x2="432" y2="137" stroke="#10B981" strokeWidth="3" strokeDasharray="3 3" />
                <circle cx="310" cy="137" r="3.5" fill="#FFFFFF" stroke="#14A88D" strokeWidth="1.5" className="motion-safe:animate-pulse" />
                <circle cx="480" cy="137" r="3.5" fill="#FFFFFF" stroke="#14A88D" strokeWidth="1.5" className="motion-safe:animate-pulse" />

                {/* Stream 3: Vitals (y=179) */}
                <path
                  d="M 208 179 L 368 179 M 432 179 L 580 179"
                  fill="none"
                  stroke={`url(#${gradAllowedId})`}
                  strokeWidth="3"
                  strokeLinecap="round"
                  filter={`url(#${filterGlowGreenId})`}
                />
                <line x1="368" y1="179" x2="432" y2="179" stroke="#10B981" strokeWidth="3" strokeDasharray="3 3" />
                <circle cx="260" cy="179" r="3.5" fill="#FFFFFF" stroke="#14A88D" strokeWidth="1.5" className="motion-safe:animate-pulse" />
                <circle cx="530" cy="179" r="3.5" fill="#FFFFFF" stroke="#14A88D" strokeWidth="1.5" className="motion-safe:animate-pulse" />
              </>
            ) : (
              /* When Revoked: Allowed lines are truncated and severed before the gate */
              <>
                <path
                  d="M 208 95 L 368 95"
                  fill="none"
                  stroke={`url(#${gradRevokedId})`}
                  strokeWidth="2.5"
                  strokeDasharray="6 4"
                />
                <circle cx="368" cy="95" r="4" fill="#E11D48" />

                <path
                  d="M 208 137 L 368 137"
                  fill="none"
                  stroke={`url(#${gradRevokedId})`}
                  strokeWidth="2.5"
                  strokeDasharray="6 4"
                />
                <circle cx="368" cy="137" r="4" fill="#E11D48" />

                <path
                  d="M 208 179 L 368 179"
                  fill="none"
                  stroke={`url(#${gradRevokedId})`}
                  strokeWidth="2.5"
                  strokeDasharray="6 4"
                />
                <circle cx="368" cy="179" r="4" fill="#E11D48" />
              </>
            )}
          </g>

          {/* 2. BLOCKED FLOW STREAMS (Red / #F43F5E - Halts at boundary x=380!) */}
          <g id="blocked-flow-streams">
            {/* Stream 4: Notes (y=233) */}
            <path
              d="M 208 233 L 380 233"
              fill="none"
              stroke={`url(#${gradBlockedId})`}
              strokeWidth="3"
              strokeDasharray="4 2"
              strokeLinecap="round"
              filter={`url(#${filterGlowRedId})`}
            />
            {/* Stop Marker at Gate */}
            <circle cx="380" cy="233" r="5" fill="#E11D48" />
            <text x="380" y="236.5" fill="#FFFFFF" fontSize="8" fontWeight="bold" textAnchor="middle">
              ✕
            </text>

            {/* Stream 5: Billing (y=275) */}
            <path
              d="M 208 275 L 380 275"
              fill="none"
              stroke={`url(#${gradBlockedId})`}
              strokeWidth="3"
              strokeDasharray="4 2"
              strokeLinecap="round"
              filter={`url(#${filterGlowRedId})`}
            />
            {/* Stop Marker at Gate */}
            <circle cx="380" cy="275" r="5" fill="#E11D48" />
            <text x="380" y="278.5" fill="#FFFFFF" fontSize="8" fontWeight="bold" textAnchor="middle">
              ✕
            </text>

            {/* Flow Warning Badges */}
            <rect x="250" y="223" width="94" height="18" rx="4" fill="#FFF1F2" stroke="#FDA4AF" strokeWidth="1" />
            <text x="297" y="235.5" fill="#E11D48" fontSize="8" fontWeight="bold" textAnchor="middle">
              CHẶN TẠI RANH GIỚI
            </text>

            <rect x="250" y="265" width="94" height="18" rx="4" fill="#FFF1F2" stroke="#FDA4AF" strokeWidth="1" />
            <text x="297" y="277.5" fill="#E11D48" fontSize="8" fontWeight="bold" textAnchor="middle">
              CHẶN TẠI RANH GIỚI
            </text>
          </g>
        </svg>
      </div>

      {/* Bottom Summary HUD / Counters */}
      <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
        {/* Allowed Stream Counter */}
        <div
          className={`flex items-start gap-3 rounded-2xl p-3.5 border transition-all ${
            isRevoked
              ? "bg-[#F8FAFD] border-[#E3E8EF] opacity-60"
              : "bg-[#ECFDF8]/70 border-[#14A88D]/25 shadow-2xs"
          }`}
        >
          <span
            className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-lg text-xs font-bold text-white ${
              isRevoked ? "bg-slate-400" : "bg-[#14A88D]"
            }`}
          >
            {isRevoked ? "—" : "✓"}
          </span>
          <div>
            <div className="flex items-center gap-2">
              <h4 className="text-xs font-bold text-[#162033]">
                {allowedCount} Luồng Cấp phép đi qua
              </h4>
              <span className="rounded bg-white px-1.5 py-0.5 text-[10px] font-bold text-[#14A88D] border border-[#14A88D]/20">
                {isRevoked ? "Đã ngắt" : "Được phép"}
              </span>
            </div>
            <p className="mt-0.5 text-[11px] text-[#48566A]">
              Chỉ các trường bệnh nhân xác nhận (Dị ứng, Đơn thuốc, HA) mới vượt qua cổng.
            </p>
          </div>
        </div>

        {/* Blocked Stream Counter */}
        <div className="flex items-start gap-3 rounded-2xl bg-[#FFF1F2]/70 p-3.5 border border-rose-200/80 shadow-2xs">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-rose-600 text-xs font-bold text-white">
            ✕
          </span>
          <div>
            <div className="flex items-center gap-2">
              <h4 className="text-xs font-bold text-[#162033]">
                {blockedCount} Trường Nhạy cảm Bị chặn
              </h4>
              <span className="rounded bg-white px-1.5 py-0.5 text-[10px] font-bold text-rose-700 border border-rose-200">
                Dừng 100%
              </span>
            </div>
            <p className="mt-0.5 text-[11px] text-[#48566A]">
              Nhật ký cá nhân và viện phí dừng tuyệt đối tại ranh giới, không tới người nhận.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default PermissionGate;
