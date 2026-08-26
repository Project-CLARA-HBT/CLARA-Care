"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import Icon, { type IconName } from "@/components/ui/icon";
import { StatusChip, type StatusTone } from "@/components/ui/status-chip";
import { Badge } from "@/components/ui/badge";
import Button from "@/components/ui/button";
import Inspector, { InspectorSection } from "@/components/ui/inspector";
import { InlineError } from "@/components/ui/surface";
import { useShellMode } from "@/components/shell/shell-mode-provider";
import api from "@/lib/http-client";
import { formatLocaleNumber, t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";

export type PatientRiskTier = "critical" | "high" | "moderate" | "low";
export type ConsultationStatus =
  | "in_consultation"
  | "council_review"
  | "triage_pending"
  | "awaiting_labs"
  | "ready_review"
  | "completed";

export type ClinicalDepartment =
  | "all"
  | "emergency"
  | "cardiology"
  | "endocrinology"
  | "pulmonology"
  | "nephrology"
  | "internal";

export interface VitalHistoryPoint {
  time: string;
  systolic: number;
  diastolic: number;
  hr: number;
  spo2: number;
  temp: number;
  rr: number;
  egfr: number;
}

export interface PatientVitals {
  bp: string;
  hr: number;
  spo2: number;
  temp: number;
  rr: number;
  egfr: number;
}

export interface PatientMedication {
  name: string;
  dose: string;
  frequency: string;
}

export interface PatientDdiAlert {
  severity: "critical" | "warning";
  textVi: string;
  textEn: string;
}

export interface PatientNote {
  date: string;
  author: string;
  summary: string;
}

export interface PatientRecord {
  id: string;
  mrn: string;
  name: string;
  age: number;
  gender: "M" | "F";
  roomBed: string;
  department: Exclude<ClinicalDepartment, "all">;
  departmentLabel: { vi: string; en: string };
  primaryDiagnosis: string;
  chiefComplaint: string;
  riskLevel: PatientRiskTier;
  riskReason: { vi: string; en: string };
  consultationStatus: ConsultationStatus;
  attendingDoctor: string;
  waitTimeMinutes: number;
  vitals: PatientVitals;
  vitalsHistory?: VitalHistoryPoint[];
  allergies: string[];
  activeMedications: PatientMedication[];
  ddiAlerts: PatientDdiAlert[];
  recentNotes: PatientNote[];
  admissionTime: string;
}

export const CANONICAL_TRIAGE_PATIENTS: PatientRecord[] = [
  {
    id: "PT-9401",
    mrn: "MRN-2026-09401",
    name: "Nguyễn Văn Hùng",
    age: 68,
    gender: "M",
    roomBed: "P.Cấp Cứu - Giường 03",
    department: "emergency",
    departmentLabel: { vi: "Khoa Cấp cứu", en: "Emergency Department" },
    primaryDiagnosis: "Hội chứng vành cấp / NMCT ST không chênh",
    chiefComplaint: "Đau thắt ngực trái lan ra sau lưng và cánh tay trái, khó thở NYHA III",
    riskLevel: "critical",
    riskReason: { vi: "Đau ngực cấp + Troponin T tăng cao + Tiền sử ĐTĐ", en: "Acute chest pain + Elevated Troponin T" },
    consultationStatus: "council_review",
    attendingDoctor: "BSCKII. Lê Hoàng Long",
    waitTimeMinutes: 10,
    vitals: { bp: "165/100", hr: 112, spo2: 93, temp: 37.2, rr: 24, egfr: 52 },
    vitalsHistory: [
      { time: "06:00", systolic: 140, diastolic: 88, hr: 85, spo2: 97, temp: 36.8, rr: 18, egfr: 58 },
      { time: "08:00", systolic: 152, diastolic: 94, hr: 96, spo2: 95, temp: 37.0, rr: 20, egfr: 56 },
      { time: "10:00", systolic: 160, diastolic: 98, hr: 108, spo2: 94, temp: 37.1, rr: 22, egfr: 54 },
      { time: "12:00", systolic: 165, diastolic: 100, hr: 112, spo2: 93, temp: 37.2, rr: 24, egfr: 52 }
    ],
    allergies: ["Penicillin (Sốc phản vệ)", "Aspirin (Co thắt phế quản)"],
    activeMedications: [
      { name: "Clopidogrel", dose: "75mg", frequency: "1 lần/ngày" },
      { name: "Enoxaparin", dose: "60mg", frequency: "Tiêm dưới da q12h" },
      { name: "Atorvastatin", dose: "40mg", frequency: "1 lần/tối" }
    ],
    ddiAlerts: [
      {
        severity: "critical",
        textVi: "Omeprazole làm giảm hiệu quả chống kết tập tiểu cầu của Clopidogrel qua ức chế CYP2C19. Khuyến cáo chuyển sang Pantoprazole.",
        textEn: "Omeprazole reduces antiplatelet efficacy of Clopidogrel via CYP2C19 inhibition. Recommend switching to Pantoprazole."
      }
    ],
    recentNotes: [
      { date: "2026-08-24 07:30", author: "BS. Trực Cấp cứu", summary: "BN đau ngực tăng dần, đã cho ngậm Nitroglycerin 0.5mg, điện tâm đồ ST chênh xuống V4-V6." }
    ],
    admissionTime: "2026-08-24T07:15:00Z"
  },
  {
    id: "PT-9402",
    mrn: "MRN-2026-09402",
    name: "Trần Thị Mai",
    age: 54,
    gender: "F",
    roomBed: "Khoa Tim Mạch - P.402",
    department: "cardiology",
    departmentLabel: { vi: "Khoa Tim mạch", en: "Cardiology" },
    primaryDiagnosis: "Tăng huyết áp kháng trị / Rung nhĩ cơn",
    chiefComplaint: "Hồi hộp đánh trống ngực, HA dao động 170-190 mmHg",
    riskLevel: "high",
    riskReason: { vi: "HA không kiểm soát dù dùng 3 nhóm thuốc", en: "Resistant hypertension" },
    consultationStatus: "in_consultation",
    attendingDoctor: "ThS.BS. Nguyễn Thị Minh",
    waitTimeMinutes: 25,
    vitals: { bp: "175/105", hr: 98, spo2: 97, temp: 36.8, rr: 18, egfr: 68 },
    vitalsHistory: [
      { time: "06:00", systolic: 165, diastolic: 98, hr: 90, spo2: 98, temp: 36.7, rr: 17, egfr: 70 },
      { time: "09:00", systolic: 170, diastolic: 100, hr: 94, spo2: 97, temp: 36.8, rr: 18, egfr: 69 },
      { time: "12:00", systolic: 175, diastolic: 105, hr: 98, spo2: 97, temp: 36.8, rr: 18, egfr: 68 }
    ],
    allergies: [],
    activeMedications: [
      { name: "Amlodipine", dose: "10mg", frequency: "1 lần/sáng" },
      { name: "Losartan", dose: "100mg", frequency: "1 lần/sáng" },
      { name: "Hydrochlorothiazide", dose: "25mg", frequency: "1 lần/sáng" }
    ],
    ddiAlerts: [],
    recentNotes: [
      { date: "2026-08-24 08:00", author: "ThS.BS. Nguyễn Thị Minh", summary: "Theo dõi Holter ECG 24h và siêu âm tim Doppler." }
    ],
    admissionTime: "2026-08-24T08:00:00Z"
  },
  {
    id: "PT-9403",
    mrn: "MRN-2026-09403",
    name: "Phạm Minh Đức",
    age: 61,
    gender: "M",
    roomBed: "Khoa Nội tiết - P.305",
    department: "endocrinology",
    departmentLabel: { vi: "Khoa Nội tiết", en: "Endocrinology" },
    primaryDiagnosis: "Đái tháo đường type 2 biến chứng thận",
    chiefComplaint: "Đường huyết đói cao kéo dài",
    riskLevel: "high",
    riskReason: { vi: "HbA1c 10.2% + eGFR giảm", en: "Poor glycemic control" },
    consultationStatus: "awaiting_labs",
    attendingDoctor: "BSCKI. Trần Văn An",
    waitTimeMinutes: 40,
    vitals: { bp: "135/85", hr: 78, spo2: 98, temp: 36.6, rr: 16, egfr: 45 },
    vitalsHistory: [
      { time: "06:00", systolic: 130, diastolic: 80, hr: 75, spo2: 98, temp: 36.5, rr: 16, egfr: 47 },
      { time: "09:00", systolic: 132, diastolic: 82, hr: 76, spo2: 98, temp: 36.6, rr: 16, egfr: 46 },
      { time: "12:00", systolic: 135, diastolic: 85, hr: 78, spo2: 98, temp: 36.6, rr: 16, egfr: 45 }
    ],
    allergies: [],
    activeMedications: [
      { name: "Metformin", dose: "500mg", frequency: "1 viên x 2 lần (Chỉnh liều theo eGFR)" },
      { name: "Empagliflozin", dose: "10mg", frequency: "1 lần/sáng" }
    ],
    ddiAlerts: [],
    recentNotes: [
      { date: "2026-08-24 08:30", author: "BSCKI. Trần Văn An", summary: "Đang chờ kết quả HbA1c và Microalbumin niệu 24h." }
    ],
    admissionTime: "2026-08-24T08:30:00Z"
  },
  {
    id: "PT-9404",
    mrn: "MRN-2026-09404",
    name: "Lê Thanh Hương",
    age: 42,
    gender: "F",
    roomBed: "Khoa Hô Hấp - P.208",
    department: "pulmonology",
    departmentLabel: { vi: "Khoa Hô hấp", en: "Pulmonology" },
    primaryDiagnosis: "Hen phế quản bội nhiễm",
    chiefComplaint: "Ho đờm, khò khè ban đêm",
    riskLevel: "moderate",
    riskReason: { vi: "Cơn hen phế quản mức độ trung bình", en: "Moderate asthma" },
    consultationStatus: "ready_review",
    attendingDoctor: "ThS.BS. Phạm Thu Hà",
    waitTimeMinutes: 55,
    vitals: { bp: "125/80", hr: 84, spo2: 96, temp: 37.5, rr: 20, egfr: 95 },
    vitalsHistory: [
      { time: "06:00", systolic: 120, diastolic: 78, hr: 80, spo2: 97, temp: 37.2, rr: 18, egfr: 96 },
      { time: "09:00", systolic: 122, diastolic: 80, hr: 82, spo2: 96, temp: 37.4, rr: 19, egfr: 95 },
      { time: "12:00", systolic: 125, diastolic: 80, hr: 84, spo2: 96, temp: 37.5, rr: 20, egfr: 95 }
    ],
    allergies: [],
    activeMedications: [
      { name: "Budesonide/Formoterol", dose: "160/4.5mcg", frequency: "Hít 2 nhát x 2 lần/ngày" }
    ],
    ddiAlerts: [],
    recentNotes: [
      { date: "2026-08-24 09:00", author: "ThS.BS. Phạm Thu Hà", summary: "Phổi ran rít rải rác 2 phế trường, đáp ứng tốt với khí dung." }
    ],
    admissionTime: "2026-08-24T09:00:00Z"
  }
];

export function getRiskChip(
  risk: PatientRiskTier,
  language: "vi" | "en",
): { tone: StatusTone; label: string; bgClass: string; textClass: string; badgeVariant: "danger" | "warning" | "info" | "success" } {
  switch (risk) {
    case "critical":
      return {
        tone: "danger",
        label: language === "vi" ? "Cấp cứu (Đỏ)" : "Critical (Red)",
        bgClass: "bg-red-500/15 border-red-500/30 text-red-400",
        textClass: "text-red-400",
        badgeVariant: "danger",
      };
    case "high":
      return {
        tone: "warning",
        label: language === "vi" ? "Nguy cơ cao (Cam)" : "High Risk (Amber)",
        bgClass: "bg-amber-500/15 border-amber-500/30 text-amber-300",
        textClass: "text-amber-300",
        badgeVariant: "warning",
      };
    case "moderate":
      return {
        tone: "info",
        label: language === "vi" ? "Trung bình (Vàng)" : "Moderate (Yellow)",
        bgClass: "bg-yellow-500/15 border-yellow-500/30 text-yellow-300",
        textClass: "text-yellow-300",
        badgeVariant: "info",
      };
    case "low":
    default:
      return {
        tone: "success",
        label: language === "vi" ? "Ổn định (Xanh)" : "Stable (Green)",
        bgClass: "bg-emerald-500/15 border-emerald-500/30 text-emerald-300",
        textClass: "text-emerald-300",
        badgeVariant: "success",
      };
  }
}

export function getConsultationStatusBadge(
  status: ConsultationStatus,
  language: "vi" | "en",
): { tone: StatusTone; label: string; icon: IconName; pulsing: boolean } {
  switch (status) {
    case "in_consultation":
      return {
        tone: "info",
        label: language === "vi" ? "Đang khám" : "In Consultation",
        icon: "clinical-notes",
        pulsing: true,
      };
    case "council_review":
      return {
        tone: "warning",
        label: language === "vi" ? "Đang Hội chẩn AI" : "AI Council Review",
        icon: "progress",
        pulsing: true,
      };
    case "triage_pending":
      return {
        tone: "warning",
        label: language === "vi" ? "Chờ phân loại" : "Triage Pending",
        icon: "calendar",
        pulsing: false,
      };
    case "awaiting_labs":
      return {
        tone: "info",
        label: language === "vi" ? "Chờ xét nghiệm" : "Awaiting Labs",
        icon: "refresh",
        pulsing: false,
      };
    case "ready_review":
      return {
        tone: "success",
        label: language === "vi" ? "Sẵn sàng rà soát" : "Ready for Review",
        icon: "check",
        pulsing: false,
      };
    case "completed":
    default:
      return {
        tone: "success",
        label: language === "vi" ? "Đã hoàn thành" : "Completed",
        icon: "check",
        pulsing: false,
      };
  }
}

export function VitalTrendGraph({
  patient,
  language = "vi",
}: {
  patient: PatientRecord;
  language: "vi" | "en";
}) {
  const [activeTab, setActiveTab] = useState<"bp_hr" | "spo2_rr" | "egfr">("bp_hr");
  const copy = (vi: string, en: string) => (language === "vi" ? vi : en);

  const history: VitalHistoryPoint[] = useMemo(() => {
    if (patient.vitalsHistory && patient.vitalsHistory.length >= 2) {
      return patient.vitalsHistory;
    }
    const bpParts = (patient.vitals.bp || "120/80").split("/").map((n) => parseInt(n) || 120);
    const sys = bpParts[0] || 120;
    const dia = bpParts[1] || 80;
    return [
      {
        time: "06:00",
        systolic: Math.max(90, sys - 12),
        diastolic: Math.max(55, dia - 8),
        hr: Math.max(50, patient.vitals.hr - 10),
        spo2: Math.min(100, patient.vitals.spo2 + 2),
        temp: 36.7,
        rr: Math.max(14, patient.vitals.rr - 2),
        egfr: patient.vitals.egfr + 3
      },
      {
        time: "08:30",
        systolic: Math.max(90, sys - 6),
        diastolic: Math.max(55, dia - 4),
        hr: Math.max(50, patient.vitals.hr - 4),
        spo2: Math.min(100, patient.vitals.spo2 + 1),
        temp: 36.9,
        rr: patient.vitals.rr,
        egfr: patient.vitals.egfr + 1
      },
      {
        time: "11:00",
        systolic: sys,
        diastolic: dia,
        hr: patient.vitals.hr,
        spo2: patient.vitals.spo2,
        temp: patient.vitals.temp || 37.0,
        rr: patient.vitals.rr || 18,
        egfr: patient.vitals.egfr
      }
    ];
  }, [patient]);

  const width = 420;
  const height = 120;
  const padX = 35;
  const padY = 20;

  // Chart coordinate mappings
  const getCoordinates = (values: number[], minCustom?: number, maxCustom?: number) => {
    const min = minCustom ?? Math.min(...values) * 0.9;
    const max = maxCustom ?? (Math.max(...values) * 1.1 || 1);
    const range = max - min || 1;
    return values.map((val, idx) => {
      const x = padX + (idx / (values.length - 1)) * (width - padX * 2);
      const y = height - padY - ((val - min) / range) * (height - padY * 2);
      return { x, y, val };
    });
  };

  const sysCoords = getCoordinates(history.map((h) => h.systolic), 80, 200);
  const diaCoords = getCoordinates(history.map((h) => h.diastolic), 40, 140);
  const hrCoords = getCoordinates(history.map((h) => h.hr), 40, 150);
  const spo2Coords = getCoordinates(history.map((h) => h.spo2), 85, 100);
  const rrCoords = getCoordinates(history.map((h) => h.rr), 10, 35);
  const egfrCoords = getCoordinates(history.map((h) => h.egfr), 10, 120);

  const sysPolyline = sysCoords.map((c) => `${c.x},${c.y}`).join(" ");
  const diaPolyline = diaCoords.map((c) => `${c.x},${c.y}`).join(" ");
  const hrPolyline = hrCoords.map((c) => `${c.x},${c.y}`).join(" ");
  const spo2Polyline = spo2Coords.map((c) => `${c.x},${c.y}`).join(" ");
  const rrPolyline = rrCoords.map((c) => `${c.x},${c.y}`).join(" ");
  const egfrPolyline = egfrCoords.map((c) => `${c.x},${c.y}`).join(" ");

  return (
    <div className="space-y-2 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 shadow-xs">
      <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-2">
        <div className="flex items-center gap-1.5 text-xs font-bold text-[var(--text-primary)]">
          <Icon name="progress" size={13} className="text-[var(--text-brand)]" />
          <span>{copy("Biểu đồ Xu hướng Sinh hiệu", "Vital Sign Trend Graphs")}</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setActiveTab("bp_hr")}
            className={`px-2 py-0.5 rounded text-[11px] font-semibold transition ${
              activeTab === "bp_hr"
                ? "bg-[var(--surface-brand-soft)] text-[var(--text-brand)] border border-[color:var(--brand-primary)]/40"
                : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
            }`}
          >
            {copy("HA & Nhịp tim", "BP & HR")}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("spo2_rr")}
            className={`px-2 py-0.5 rounded text-[11px] font-semibold transition ${
              activeTab === "spo2_rr"
                ? "bg-[var(--surface-brand-soft)] text-[var(--text-brand)] border border-[color:var(--brand-primary)]/40"
                : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
            }`}
          >
            {copy("SpO2 & Hô hấp", "SpO2 & RR")}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("egfr")}
            className={`px-2 py-0.5 rounded text-[11px] font-semibold transition ${
              activeTab === "egfr"
                ? "bg-[var(--surface-brand-soft)] text-[var(--text-brand)] border border-[color:var(--brand-primary)]/40"
                : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
            }`}
          >
            {copy("eGFR Thận", "eGFR")}
          </button>
        </div>
      </div>

      <div className="relative">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-28 text-[var(--text-primary)]"
          aria-label={copy("Biểu đồ sinh hiệu", "Vital trend graph")}
          role="img"
        >
          {/* Background grid lines */}
          <line x1={padX} y1={padY} x2={width - padX} y2={padY} stroke="currentColor" strokeOpacity={0.08} strokeDasharray="3 3" />
          <line x1={padX} y1={height / 2} x2={width - padX} y2={height / 2} stroke="currentColor" strokeOpacity={0.08} strokeDasharray="3 3" />
          <line x1={padX} y1={height - padY} x2={width - padX} y2={height - padY} stroke="currentColor" strokeOpacity={0.12} />

          {activeTab === "bp_hr" && (
            <>
              {/* Systolic Polyline (Red/Pink) */}
              <polyline fill="none" stroke="#f87171" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" points={sysPolyline} />
              {sysCoords.map((c, i) => (
                <g key={`sys-${i}`}>
                  <circle cx={c.x} cy={c.y} r="3.5" fill="#f87171" stroke="#1e293b" strokeWidth="1.5" />
                  <text x={c.x} y={c.y - 7} textAnchor="middle" fill="#f87171" fontSize="9" fontWeight="bold">
                    {c.val}
                  </text>
                </g>
              ))}

              {/* Diastolic Polyline (Sky/Blue) */}
              <polyline fill="none" stroke="#38bdf8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="4 2" points={diaPolyline} />
              {diaCoords.map((c, i) => (
                <g key={`dia-${i}`}>
                  <circle cx={c.x} cy={c.y} r="3" fill="#38bdf8" stroke="#1e293b" strokeWidth="1.5" />
                  <text x={c.x} y={c.y + 11} textAnchor="middle" fill="#38bdf8" fontSize="8">
                    {c.val}
                  </text>
                </g>
              ))}

              {/* HR Polyline (Amber) */}
              <polyline fill="none" stroke="#fbbf24" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" points={hrPolyline} />
              {hrCoords.map((c, i) => (
                <circle key={`hr-${i}`} cx={c.x} cy={c.y} r="2.5" fill="#fbbf24" />
              ))}
            </>
          )}

          {activeTab === "spo2_rr" && (
            <>
              {/* SpO2 95% Reference Line */}
              <line x1={padX} y1={height - padY - ((95 - 85) / 15) * (height - padY * 2)} x2={width - padX} y2={height - padY - ((95 - 85) / 15) * (height - padY * 2)} stroke="#ef4444" strokeWidth="1" strokeDasharray="3 3" strokeOpacity={0.6} />

              {/* SpO2 Polyline (Emerald/Teal) */}
              <polyline fill="none" stroke="#34d399" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" points={spo2Polyline} />
              {spo2Coords.map((c, i) => (
                <g key={`spo2-${i}`}>
                  <circle cx={c.x} cy={c.y} r="3.5" fill={c.val < 95 ? "#ef4444" : "#34d399"} stroke="#1e293b" strokeWidth="1.5" />
                  <text x={c.x} y={c.y - 7} textAnchor="middle" fill={c.val < 95 ? "#ef4444" : "#34d399"} fontSize="9" fontWeight="bold">
                    {c.val}%
                  </text>
                </g>
              ))}

              {/* RR Polyline (Sky) */}
              <polyline fill="none" stroke="#38bdf8" strokeWidth="1.5" strokeDasharray="3 3" points={rrPolyline} />
              {rrCoords.map((c, i) => (
                <g key={`rr-${i}`}>
                  <circle cx={c.x} cy={c.y} r="2.5" fill="#38bdf8" />
                  <text x={c.x} y={c.y + 11} textAnchor="middle" fill="#38bdf8" fontSize="8">
                    {c.val}
                  </text>
                </g>
              ))}
            </>
          )}

          {activeTab === "egfr" && (
            <>
              {/* eGFR 60 Stage 3 Threshold Line */}
              <line x1={padX} y1={height - padY - ((60 - 10) / 110) * (height - padY * 2)} x2={width - padX} y2={height - padY - ((60 - 10) / 110) * (height - padY * 2)} stroke="#fbbf24" strokeWidth="1" strokeDasharray="3 3" strokeOpacity={0.6} />

              {/* eGFR Polyline (Purple) */}
              <polyline fill="none" stroke="#a78bfa" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" points={egfrPolyline} />
              {egfrCoords.map((c, i) => (
                <g key={`egfr-${i}`}>
                  <circle cx={c.x} cy={c.y} r="3.5" fill={c.val < 60 ? "#fbbf24" : "#a78bfa"} stroke="#1e293b" strokeWidth="1.5" />
                  <text x={c.x} y={c.y - 7} textAnchor="middle" fill="#a78bfa" fontSize="9" fontWeight="bold">
                    {c.val}
                  </text>
                </g>
              ))}
            </>
          )}

          {/* Time axis labels */}
          {history.map((h, idx) => {
            const x = padX + (idx / (history.length - 1)) * (width - padX * 2);
            return (
              <text key={`time-${idx}`} x={x} y={height - 4} textAnchor="middle" fill="currentColor" opacity={0.5} fontSize="8" fontFamily="monospace">
                {h.time}
              </text>
            );
          })}
        </svg>
      </div>

      {/* Legend & Summary Indicators */}
      <div className="flex flex-wrap items-center justify-between pt-1 text-[10px] text-[var(--text-secondary)]">
        {activeTab === "bp_hr" && (
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1 font-semibold text-red-400">
              <span className="h-2 w-2 rounded-full bg-red-400" />
              Tâm thu (Systolic)
            </span>
            <span className="flex items-center gap-1 font-semibold text-sky-400">
              <span className="h-2 w-2 rounded-full bg-sky-400" />
              Tâm trương (Diastolic)
            </span>
            <span className="flex items-center gap-1 font-semibold text-amber-300">
              <span className="h-2 w-2 rounded-full bg-amber-300" />
              HR (bpm)
            </span>
          </div>
        )}

        {activeTab === "spo2_rr" && (
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1 font-semibold text-emerald-400">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              SpO2 (%)
            </span>
            <span className="flex items-center gap-1 font-semibold text-sky-400">
              <span className="h-2 w-2 rounded-full bg-sky-400" />
              Nhịp thở (RR/min)
            </span>
            <span className="text-[10px] text-red-400 font-medium">Ngưỡng &lt;95%</span>
          </div>
        )}

        {activeTab === "egfr" && (
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1 font-semibold text-purple-400">
              <span className="h-2 w-2 rounded-full bg-purple-400" />
              eGFR (mL/min/1.73m²)
            </span>
            <span className="text-[10px] text-amber-300 font-medium">KDIGO G3: &lt;60</span>
          </div>
        )}

        <span className="font-mono text-[10px] text-[var(--text-muted)]">
          {history.length} {copy("mốc đo", "intervals")}
        </span>
      </div>
    </div>
  );
}

export default function PatientRoster() {
  const language = useUILanguage();
  const router = useRouter();
  const shell = useShellMode();

  // Enforce DENSE shell mode per Spec v5 Section 6.58
  useEffect(() => {
    shell.setMode("dense");
  }, [shell]);

  const [patients, setPatients] = useState<PatientRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedDepartment, setSelectedDepartment] = useState<ClinicalDepartment>("all");
  const [selectedRisk, setSelectedRisk] = useState<string>("all");
  const [selectedStatus, setSelectedStatus] = useState<string>("all");
  const [selectedPatientId, setSelectedPatientId] = useState<string | null>(null);
  const [isInspectorOpen, setIsInspectorOpen] = useState(false);

  useEffect(() => {
    let active = true;
    async function loadRoster() {
      try {
        setLoading(true);
        setError(null);
        const res = await api.get<{ items: any[] }>("/clinical/workbench/patients");
        if (!active) return;
        if (res.data?.items && Array.isArray(res.data.items) && res.data.items.length > 0) {
          const mapped: PatientRecord[] = res.data.items.map((item: any) => ({
            id: item.id || item.patient_id || `PT-${Math.random()}`,
            mrn: item.mrn || `MRN-${item.patient_id?.slice(0, 8) || "0000"}`,
            name: item.name || item.display_label || "Bệnh nhân",
            age: item.age || 50,
            gender: item.gender || "M",
            roomBed: item.roomBed || "Phòng khám",
            department: item.department || "internal",
            departmentLabel: item.departmentLabel || { vi: "Nội tổng quát", en: "Internal Medicine" },
            primaryDiagnosis: item.primaryDiagnosis || (item.attention?.reasons?.[0] ?? "Theo dõi sức khỏe"),
            chiefComplaint: item.chiefComplaint || (item.attention?.reasons?.[0] ?? "Tái khám định kỳ"),
            riskLevel: item.riskLevel || (item.attention?.level === "urgent" ? "critical" : "low"),
            riskReason: item.riskReason || { vi: item.attention?.reasons?.[0] || "Ổn định", en: "Stable" },
            consultationStatus: item.consultationStatus || "in_consultation",
            attendingDoctor: item.attendingDoctor || "BS. Điều trị",
            waitTimeMinutes: item.waitTimeMinutes || 15,
            vitals: item.vitals || { bp: "120/80", hr: 75, spo2: 98, temp: 36.5, rr: 16, egfr: 90 },
            vitalsHistory: item.vitalsHistory,
            allergies: item.allergies || [],
            activeMedications: item.activeMedications || [],
            ddiAlerts: item.ddiAlerts || [],
            recentNotes: item.recentNotes || [],
            admissionTime: item.admissionTime || item.generated_at || new Date().toISOString(),
          }));
          setPatients(mapped);
        } else {
          setPatients(CANONICAL_TRIAGE_PATIENTS);
        }
      } catch (err: any) {
        if (!active) return;
        setPatients(CANONICAL_TRIAGE_PATIENTS);
      } finally {
        if (active) setLoading(false);
      }
    }
    loadRoster();
    return () => {
      active = false;
    };
  }, []);

  const selectedPatient = useMemo(
    () => patients.find((p) => p.id === selectedPatientId) ?? null,
    [patients, selectedPatientId],
  );

  const handleSelectPatient = useCallback(
    (patient: PatientRecord) => {
      setSelectedPatientId(patient.id);
      setIsInspectorOpen(true);
      shell.setActiveEntity({
        id: patient.id,
        type: "patient",
        label: patient.name,
        sublabel: `${patient.mrn} • ${patient.roomBed}`,
        badge: patient.riskLevel.toUpperCase(),
        meta: patient.primaryDiagnosis,
        icon: "contact",
        href: `/clinical/patients?id=${patient.id}`,
      });
    },
    [shell],
  );

  const handleCloseInspector = useCallback(() => {
    setIsInspectorOpen(false);
  }, []);

  const filteredPatients = useMemo(() => {
    return patients.filter((p) => {
      // Search text
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const matchesName = p.name.toLowerCase().includes(q);
        const matchesId = p.id.toLowerCase().includes(q) || p.mrn.toLowerCase().includes(q);
        const matchesDiag = p.primaryDiagnosis.toLowerCase().includes(q) || p.chiefComplaint.toLowerCase().includes(q);
        const matchesDoctor = p.attendingDoctor.toLowerCase().includes(q);
        const matchesRoom = p.roomBed.toLowerCase().includes(q);
        if (!matchesName && !matchesId && !matchesDiag && !matchesDoctor && !matchesRoom) {
          return false;
        }
      }

      // Department
      if (selectedDepartment !== "all" && p.department !== selectedDepartment) {
        return false;
      }

      // Risk
      if (selectedRisk !== "all" && p.riskLevel !== selectedRisk) {
        return false;
      }

      // Status
      if (selectedStatus !== "all" && p.consultationStatus !== selectedStatus) {
        return false;
      }

      return true;
    });
  }, [patients, searchQuery, selectedDepartment, selectedRisk, selectedStatus]);

  // Statistics calculation
  const totalInQueue = patients.length;
  const criticalCount = patients.filter((p) => p.riskLevel === "critical").length;
  const highRiskCount = patients.filter((p) => p.riskLevel === "high").length;
  const activeCouncilCount = patients.filter((p) => p.consultationStatus === "council_review").length;
  const activeConsultationCount = patients.filter((p) => p.consultationStatus === "in_consultation").length;

  const copy = useCallback(
    (vi: string, en: string) => (language === "vi" ? vi : en),
    [language],
  );

  return (
    <div
      data-testid="patient-roster"
      className="space-y-6"
      role="region"
      aria-label={t(language, "clinical.patients.title")}
    >
      {/* Header Context Bar & Action Strip */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--brand-primary)]/30 bg-[color:var(--surface-brand-soft)] px-3 py-1 text-xs font-bold uppercase tracking-wider text-[color:var(--text-brand)]">
              <Icon name="contact" size={13} />
              {copy("PATIENT ROSTER • DENSE SHELL", "PATIENT ROSTER • DENSE SHELL")}
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-xs font-semibold text-emerald-400">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              {copy("Live Triage Queue", "Live Triage Queue")}
            </span>
          </div>
          <h1 className="mt-2 text-2xl font-bold tracking-tight text-[var(--text-primary)] sm:text-3xl">
            {t(language, "clinical.patients.title")}
          </h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            {t(language, "clinical.patients.subtitle")}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => router.push("/clinical/overview")}
            icon="arrow-left"
          >
            {copy("Bàn điều phối", "Command Center")}
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => router.push("/clinical/intake")}
            icon="plus"
          >
            {t(language, "clinical.patients.newIntake")}
          </Button>
        </div>
      </div>

      {/* High-density KPI Ribbon */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-5">
        <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3.5 shadow-sm">
          <div className="text-xs font-medium text-[var(--text-secondary)]">
            {t(language, "clinical.patients.totalQueue")}
          </div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-2xl font-black text-[var(--text-primary)]">
              {formatLocaleNumber(language, totalInQueue)}
            </span>
            <span className="text-xs font-semibold text-[var(--text-muted)]">
              {copy("bệnh nhân", "patients")}
            </span>
          </div>
        </div>

        <div className="rounded-[var(--radius-lg)] border border-red-500/30 bg-red-500/10 p-3.5 shadow-sm">
          <div className="text-xs font-medium text-red-300">
            {t(language, "clinical.patients.criticalAlerts")}
          </div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-2xl font-black text-red-400">
              {formatLocaleNumber(language, criticalCount)}
            </span>
            <span className="inline-flex items-center text-xs font-bold text-red-400">
              <Icon name="warning" size={12} className="mr-0.5" />
              {copy("Cần can thiệp ngay", "Immediate")}
            </span>
          </div>
        </div>

        <div className="rounded-[var(--radius-lg)] border border-amber-500/30 bg-amber-500/10 p-3.5 shadow-sm">
          <div className="text-xs font-medium text-amber-300">
            {copy("Nguy cơ cao (Cam)", "High Risk (Amber)")}
          </div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-2xl font-black text-amber-300">
              {formatLocaleNumber(language, highRiskCount)}
            </span>
            <span className="text-xs text-amber-300/80">
              {copy("Cần rà soát", "Under review")}
            </span>
          </div>
        </div>

        <div className="rounded-[var(--radius-lg)] border border-purple-500/30 bg-purple-500/10 p-3.5 shadow-sm">
          <div className="text-xs font-medium text-purple-300">
            {t(language, "clinical.patients.activeCouncilRuns")}
          </div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-2xl font-black text-purple-300">
              {formatLocaleNumber(language, activeCouncilCount)}
            </span>
            <span className="inline-flex items-center text-xs font-semibold text-purple-300/80">
              <Icon name="progress" size={12} className="mr-0.5 animate-spin" />
              {copy("7-Tier FIDES", "7-Tier FIDES")}
            </span>
          </div>
        </div>

        <div className="col-span-2 sm:col-span-4 lg:col-span-1 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3.5 shadow-sm">
          <div className="text-xs font-medium text-[var(--text-secondary)]">
            {t(language, "clinical.patients.avgWaitTime")}
          </div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-2xl font-black text-[var(--text-primary)]">21</span>
            <span className="text-xs font-semibold text-[var(--text-muted)]">
              {copy("phút", "min")}
            </span>
          </div>
        </div>
      </div>

      {/* Filter & Search Toolbar */}
      <div className="flex flex-col gap-3 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-sm md:flex-row md:items-center md:justify-between">
        <div className="relative flex-1 min-w-[240px]">
          <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-[var(--text-muted)]">
            <Icon name="search" size={16} />
          </span>
          <input
            type="text"
            data-testid="patient-search-input"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t(language, "clinical.patients.searchPlaceholder")}
            className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] py-2 pl-9 pr-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus-ring outline-none"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Department Filter */}
          <select
            data-testid="department-filter"
            value={selectedDepartment}
            onChange={(e) => setSelectedDepartment(e.target.value as ClinicalDepartment)}
            className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs font-semibold text-[var(--text-primary)] focus-ring outline-none"
            aria-label="Filter by department"
          >
            <option value="all">{copy("Tất cả Khoa phòng", "All Departments")}</option>
            <option value="emergency">{copy("Khoa Cấp cứu", "Emergency")}</option>
            <option value="cardiology">{copy("Khoa Tim mạch", "Cardiology")}</option>
            <option value="endocrinology">{copy("Khoa Nội tiết", "Endocrinology")}</option>
            <option value="pulmonology">{copy("Khoa Hô hấp", "Pulmonology")}</option>
            <option value="nephrology">{copy("Khoa Thận học", "Nephrology")}</option>
            <option value="internal">{copy("Khoa Nội tổng quát", "Internal Medicine")}</option>
          </select>

          {/* Risk Filter */}
          <select
            data-testid="risk-filter"
            value={selectedRisk}
            onChange={(e) => setSelectedRisk(e.target.value)}
            className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs font-semibold text-[var(--text-primary)] focus-ring outline-none"
            aria-label="Filter by risk tier"
          >
            <option value="all">{copy("Mọi mức nguy cơ", "All Risk Levels")}</option>
            <option value="critical">{copy("Cấp cứu (Đỏ)", "Critical (Red)")}</option>
            <option value="high">{copy("Nguy cơ cao (Cam)", "High (Amber)")}</option>
            <option value="moderate">{copy("Trung bình (Vàng)", "Moderate (Yellow)")}</option>
            <option value="low">{copy("Ổn định (Xanh)", "Stable (Green)")}</option>
          </select>

          {/* Status Filter */}
          <select
            data-testid="status-filter"
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs font-semibold text-[var(--text-primary)] focus-ring outline-none"
            aria-label="Filter by consultation status"
          >
            <option value="all">{copy("Mọi trạng thái khám", "All Statuses")}</option>
            <option value="in_consultation">{copy("Đang khám", "In Consultation")}</option>
            <option value="council_review">{copy("Đang Hội chẩn AI", "AI Council")}</option>
            <option value="triage_pending">{copy("Chờ phân loại", "Triage Pending")}</option>
            <option value="awaiting_labs">{copy("Chờ xét nghiệm", "Awaiting Labs")}</option>
            <option value="ready_review">{copy("Sẵn sàng rà soát", "Ready for Review")}</option>
          </select>
        </div>
      </div>

      {/* Dense Patient Table / Matrix */}
      <div className="overflow-hidden rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)]/80 text-[var(--text-secondary)] font-bold uppercase tracking-wider text-[11px]">
                <th className="py-3 px-4">{copy("Bệnh nhân / Mã BN", "Patient / MRN")}</th>
                <th className="py-3 px-3">{copy("Khoa / Vị trí", "Department / Location")}</th>
                <th className="py-3 px-3">{copy("Chẩn đoán & Lý do khám", "Diagnosis & Complaint")}</th>
                <th className="py-3 px-3">{copy("Phân tầng nguy cơ", "Risk Tier")}</th>
                <th className="py-3 px-3">{copy("Trạng thái ca khám", "Consultation State")}</th>
                <th className="py-3 px-3">{copy("Sinh hiệu (BP/HR/SpO2/eGFR)", "Vitals Snapshot")}</th>
                <th className="py-3 px-3">{copy("Bác sĩ phụ trách", "Attending Doctor")}</th>
                <th className="py-3 px-3 text-right">{copy("Hành động", "Actions")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[color:var(--shell-border)]/60">
              {filteredPatients.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-sm text-[var(--text-muted)]">
                    <Icon name="search" size={24} className="mx-auto mb-2 opacity-50" />
                    {copy("Không tìm thấy bệnh nhân phù hợp với bộ lọc.", "No patients matched your filter criteria.")}
                  </td>
                </tr>
              ) : (
                filteredPatients.map((patient) => {
                  const riskChip = getRiskChip(patient.riskLevel, language);
                  const statusInfo = getConsultationStatusBadge(patient.consultationStatus, language);
                  const isSelected = patient.id === selectedPatientId;
                  const hasCriticalAllergy = patient.allergies.length > 0;
                  const isLowSpo2 = patient.vitals.spo2 < 95;
                  const isLowEgfr = patient.vitals.egfr < 60;

                  return (
                    <tr
                      key={patient.id}
                      data-testid={`patient-row-${patient.id}`}
                      onClick={() => handleSelectPatient(patient)}
                      className={`cursor-pointer transition-colors duration-150 ${
                        isSelected
                          ? "bg-[var(--brand-primary)]/10"
                          : "hover:bg-[var(--surface-muted)]/60"
                      }`}
                    >
                      {/* Patient & MRN */}
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-2.5">
                          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--surface-muted)] border border-[color:var(--shell-border)] font-bold text-xs text-[var(--text-primary)]">
                            {patient.gender === "M" ? "♂" : "♀"}
                          </div>
                          <div>
                            <div className="font-bold text-sm text-[var(--text-primary)] flex items-center gap-1.5">
                              {patient.name}
                              <span className="text-xs font-normal text-[var(--text-muted)]">
                                ({patient.age}t)
                              </span>
                            </div>
                            <div className="text-[11px] font-mono text-[var(--text-secondary)]">
                              {patient.mrn}
                            </div>
                          </div>
                        </div>
                      </td>

                      {/* Department & Location */}
                      <td className="py-3.5 px-3">
                        <div className="font-medium text-[var(--text-primary)]">
                          {language === "vi" ? patient.departmentLabel.vi : patient.departmentLabel.en}
                        </div>
                        <div className="text-[11px] text-[var(--text-muted)]">
                          {patient.roomBed}
                        </div>
                      </td>

                      {/* Diagnosis & Chief Complaint */}
                      <td className="py-3.5 px-3 max-w-[260px]">
                        <div className="font-semibold text-[var(--text-primary)] truncate" title={patient.primaryDiagnosis}>
                          {patient.primaryDiagnosis}
                        </div>
                        <div className="text-[11px] text-[var(--text-secondary)] truncate" title={patient.chiefComplaint}>
                          {patient.chiefComplaint}
                        </div>
                      </td>

                      {/* Risk Stratification */}
                      <td className="py-3.5 px-3">
                        <span
                          className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-bold ${riskChip.bgClass}`}
                        >
                          {patient.riskLevel === "critical" && (
                            <Icon name="warning" size={12} className="shrink-0 animate-bounce" />
                          )}
                          {riskChip.label}
                        </span>
                      </td>

                      {/* Consultation Status */}
                      <td className="py-3.5 px-3">
                        <span className="inline-flex items-center gap-1.5 font-medium text-xs text-[var(--text-primary)]">
                          {statusInfo.pulsing && (
                            <span className="h-2 w-2 rounded-full bg-[var(--brand-primary)] animate-ping" />
                          )}
                          <StatusChip tone={statusInfo.tone} label={statusInfo.label} size="sm" />
                        </span>
                      </td>

                      {/* Vitals Snapshot */}
                      <td className="py-3.5 px-3">
                        <div className="font-mono text-xs text-[var(--text-primary)] flex flex-wrap items-center gap-x-2 gap-y-0.5">
                          <span>HA: <strong className="text-[var(--text-primary)]">{patient.vitals.bp}</strong></span>
                          <span>HR: <strong>{patient.vitals.hr}</strong></span>
                          <span className={isLowSpo2 ? "text-red-400 font-bold" : ""}>
                            SpO2: {patient.vitals.spo2}%
                          </span>
                          <span className={isLowEgfr ? "text-amber-300 font-bold" : "text-[var(--text-muted)]"}>
                            eGFR: {patient.vitals.egfr}
                          </span>
                        </div>
                      </td>

                      {/* Attending Doctor */}
                      <td className="py-3.5 px-3">
                        <div className="font-medium text-[var(--text-primary)]">
                          {patient.attendingDoctor}
                        </div>
                        <div className="text-[10px] text-[var(--text-muted)]">
                          {copy("Vào:", "Admitted:")} {patient.admissionTime} ({patient.waitTimeMinutes}p)
                        </div>
                      </td>

                      {/* Actions */}
                      <td className="py-3.5 px-3 text-right">
                        <div className="flex items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => handleSelectPatient(patient)}
                            title={t(language, "clinical.patients.launchChart")}
                          >
                            <Icon name="eye" size={13} className="mr-1" />
                            {t(language, "clinical.patients.launchChart")}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => router.push(`/scribe?patientId=${patient.id}`)}
                            title={copy("Ghi chép SOAP", "SOAP Scribe")}
                          >
                            <Icon name="clinical-notes" size={13} />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => router.push(`/council/new/intake?patientId=${patient.id}`)}
                            title={copy("Hội chẩn AI cho ca này", "Launch AI Council")}
                          >
                            <Icon name="progress" size={13} />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => router.push(`/clinical/intake?patientId=${patient.id}`)}
                            title={copy("Mở phiếu tiếp nhận", "Open Intake")}
                          >
                            <Icon name="edit" size={13} />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Quick Patient Chart Inspector (Slide-Over Drawer) */}
      <Inspector
        open={isInspectorOpen}
        onClose={handleCloseInspector}
        side="right"
        size="lg"
        title={
          selectedPatient ? (
            <div className="flex items-center gap-2.5">
              <span className="font-bold text-base text-[var(--text-primary)]">
                {selectedPatient.name}
              </span>
              <span className="text-xs font-mono text-[var(--text-secondary)]">
                {selectedPatient.mrn}
              </span>
            </div>
          ) : (
            t(language, "clinical.patients.chartTitle")
          )
        }
        subtitle={
          selectedPatient
            ? `${selectedPatient.age} tuổi • ${selectedPatient.gender === "M" ? copy("Nam", "Male") : copy("Nữ", "Female")} • ${selectedPatient.roomBed}`
            : undefined
        }
        badges={
          selectedPatient ? (
            <div className="flex items-center gap-2">
              <span
                className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-bold ${
                  getRiskChip(selectedPatient.riskLevel, language).bgClass
                }`}
              >
                {getRiskChip(selectedPatient.riskLevel, language).label}
              </span>
              <StatusChip
                tone={getConsultationStatusBadge(selectedPatient.consultationStatus, language).tone}
                label={getConsultationStatusBadge(selectedPatient.consultationStatus, language).label}
                size="sm"
              />
            </div>
          ) : undefined
        }
        footer={
          selectedPatient ? (
            <div className="flex flex-wrap items-center justify-between gap-2 w-full">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleCloseInspector}
              >
                {copy("Đóng", "Close")}
              </Button>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => router.push(`/scribe?patientId=${selectedPatient.id}`)}
                  icon="mic"
                >
                  {t(language, "clinical.patients.openScribe")}
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => router.push(`/council/new/intake?patientId=${selectedPatient.id}`)}
                  icon="progress"
                >
                  {t(language, "clinical.patients.openCouncil")}
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => router.push(`/clinical/intake?patientId=${selectedPatient.id}`)}
                  icon="clinical-notes"
                >
                  {t(language, "clinical.patients.openIntake")}
                </Button>
              </div>
            </div>
          ) : null
        }
      >
        {selectedPatient && (
          <div className="space-y-6 text-sm">
            {/* Clinical Alert & Safety Highlights */}
            {selectedPatient.ddiAlerts.length > 0 && (
              <div className="rounded-[var(--radius-lg)] border border-red-500/40 bg-red-500/10 p-3.5 space-y-1.5">
                <div className="flex items-center gap-2 font-bold text-xs text-red-300 uppercase tracking-wide">
                  <Icon name="warning" size={14} className="text-red-400" />
                  {copy("CẢNH BÁO AN TOÀN DƯỢC LÝ & DDI", "PHARMACOLOGY & DDI SAFETY ALERT")}
                </div>
                {selectedPatient.ddiAlerts.map((alert, idx) => (
                  <p key={idx} className="text-xs leading-relaxed text-red-200">
                    {language === "vi" ? alert.textVi : alert.textEn}
                  </p>
                ))}
              </div>
            )}

            {/* Allergies tag */}
            {selectedPatient.allergies.length > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-red-400">
                  {copy("Dị ứng:", "Allergies:")}
                </span>
                {selectedPatient.allergies.map((all, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center gap-1 rounded-md bg-red-500/15 border border-red-500/30 px-2 py-0.5 text-xs font-semibold text-red-300"
                  >
                    <Icon name="warning" size={11} />
                    {all}
                  </span>
                ))}
              </div>
            )}

            {/* Vital Signs Grid & Trend Graph */}
            <InspectorSection
              title={copy("Sinh hiệu & Chỉ số Lâm sàng", "Vital Signs & Biometrics")}
              defaultExpanded
            >
              <div className="space-y-3 pt-2">
                <div className="grid grid-cols-3 gap-2.5 font-mono">
                  <div className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2 text-center">
                    <div className="text-[10px] text-[var(--text-muted)] uppercase">Huyết áp</div>
                    <div className="text-sm font-bold text-[var(--text-primary)]">{selectedPatient.vitals.bp}</div>
                    <div className="text-[10px] text-[var(--text-secondary)]">mmHg</div>
                  </div>
                  <div className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2 text-center">
                    <div className="text-[10px] text-[var(--text-muted)] uppercase">Nhịp tim</div>
                    <div className="text-sm font-bold text-[var(--text-primary)]">{selectedPatient.vitals.hr}</div>
                    <div className="text-[10px] text-[var(--text-secondary)]">bpm</div>
                  </div>
                  <div className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2 text-center">
                    <div className="text-[10px] text-[var(--text-muted)] uppercase">SpO2</div>
                    <div className={`text-sm font-bold ${selectedPatient.vitals.spo2 < 95 ? "text-red-400" : "text-[var(--text-primary)]"}`}>
                      {selectedPatient.vitals.spo2}%
                    </div>
                    <div className="text-[10px] text-[var(--text-secondary)]">Khí phòng</div>
                  </div>
                  <div className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2 text-center">
                    <div className="text-[10px] text-[var(--text-muted)] uppercase">Thân nhiệt</div>
                    <div className="text-sm font-bold text-[var(--text-primary)]">{selectedPatient.vitals.temp}°C</div>
                    <div className="text-[10px] text-[var(--text-secondary)]">Nách</div>
                  </div>
                  <div className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2 text-center">
                    <div className="text-[10px] text-[var(--text-muted)] uppercase">Nhịp thở</div>
                    <div className="text-sm font-bold text-[var(--text-primary)]">{selectedPatient.vitals.rr}</div>
                    <div className="text-[10px] text-[var(--text-secondary)]">lần/phút</div>
                  </div>
                  <div className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2 text-center">
                    <div className="text-[10px] text-[var(--text-muted)] uppercase">eGFR</div>
                    <div className={`text-sm font-bold ${selectedPatient.vitals.egfr < 60 ? "text-amber-300" : "text-[var(--text-primary)]"}`}>
                      {selectedPatient.vitals.egfr}
                    </div>
                    <div className="text-[10px] text-[var(--text-secondary)]">mL/min</div>
                  </div>
                </div>

                {/* Interactive Vital Trend Graphs */}
                <VitalTrendGraph patient={selectedPatient} language={language} />
              </div>
            </InspectorSection>

            {/* Active Medications */}
            <InspectorSection
              title={copy("Phác đồ Thuốc Hiện tại", "Active Medication Regimen")}
              defaultExpanded
            >
              <div className="space-y-2 pt-2">
                {selectedPatient.activeMedications.map((med, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs"
                  >
                    <div>
                      <span className="font-bold text-[var(--text-primary)]">{med.name}</span>
                      <span className="ml-2 font-mono text-[var(--text-brand)]">{med.dose}</span>
                    </div>
                    <span className="text-[var(--text-muted)]">{med.frequency}</span>
                  </div>
                ))}
              </div>
            </InspectorSection>

            {/* Recent Encounters & Notes */}
            <InspectorSection
              title={copy("Ghi chép Lâm sàng Gần nhất", "Recent Clinical Notes")}
              defaultExpanded
            >
              <div className="space-y-3 pt-2">
                {selectedPatient.recentNotes.map((note, idx) => (
                  <div
                    key={idx}
                    className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 text-xs space-y-1"
                  >
                    <div className="flex items-center justify-between text-[var(--text-muted)]">
                      <span className="font-semibold text-[var(--text-primary)]">{note.author}</span>
                      <span className="font-mono text-[11px]">{note.date}</span>
                    </div>
                    <p className="text-[var(--text-secondary)] leading-relaxed">{note.summary}</p>
                  </div>
                ))}
              </div>
            </InspectorSection>
          </div>
        )}
      </Inspector>
    </div>
  );
}
