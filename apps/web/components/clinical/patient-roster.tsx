"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import Icon, { type IconName } from "@/components/ui/icon";
import { StatusChip, type StatusTone } from "@/components/ui/status-chip";
import { Badge } from "@/components/ui/badge";
import Button from "@/components/ui/button";
import Inspector, { InspectorSection } from "@/components/ui/inspector";
import { useShellMode } from "@/components/shell/shell-mode-provider";
import { formatLocaleNumber, t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

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
  allergies: string[];
  activeMedications: PatientMedication[];
  ddiAlerts: PatientDdiAlert[];
  recentNotes: PatientNote[];
  admissionTime: string;
}

export const INITIAL_PATIENT_QUEUE: PatientRecord[] = [
  {
    id: "PT-9401",
    mrn: "MRN-2026-09401",
    name: "Nguyễn Văn Hùng",
    age: 64,
    gender: "M",
    roomBed: "Phòng Cấp cứu - Giường 02",
    department: "emergency",
    departmentLabel: { vi: "Cấp cứu", en: "Emergency" },
    primaryDiagnosis: "Hội chứng vành cấp / Nhồi máu cơ tim NSTEMI",
    chiefComplaint: "Đau thắt ngực kiểu đè nặng sau xương ức lan vai trái kèm vã mồ hôi 2 giờ",
    riskLevel: "critical",
    riskReason: {
      vi: "Nguy cơ biến cố mạch vành cấp tính, SpO2 93%, Troponin T tăng cao",
      en: "Acute coronary syndrome risk, SpO2 93%, elevated Troponin T",
    },
    consultationStatus: "in_consultation",
    attendingDoctor: "BS.CKII Trần Quốc Tuấn",
    waitTimeMinutes: 5,
    vitals: { bp: "165/100", hr: 104, spo2: 93, temp: 37.0, rr: 24, egfr: 52 },
    allergies: ["Aspirin (co thắt phế quản)"],
    activeMedications: [
      { name: "Clopidogrel", dose: "75mg", frequency: "1v/ngày" },
      { name: "Atorvastatin", dose: "40mg", frequency: "1v tối" },
    ],
    ddiAlerts: [
      {
        severity: "critical",
        textVi: "Chống chỉ định Aspirin do tiền sử dị ứng co thắt phế quản nặng.",
        textEn: "Aspirin contraindicated due to history of severe bronchospasm.",
      },
    ],
    recentNotes: [
      {
        date: "2026-08-24 08:30",
        author: "BS.CKII Trần Quốc Tuấn",
        summary: "Bệnh nhân vào viện vì đau ngực cấp giờ thứ 2, ECG ST chênh xuống V4-V6. Đang chuyển hội chẩn can thiệp.",
      },
    ],
    admissionTime: "08:15",
  },
  {
    id: "PT-9402",
    mrn: "MRN-2026-09402",
    name: "Trần Thị Mai Lan",
    age: 58,
    gender: "F",
    roomBed: "Phòng 405 - Giường 03",
    department: "endocrinology",
    departmentLabel: { vi: "Nội tiết", en: "Endocrinology" },
    primaryDiagnosis: "Đái tháo đường Type 2 kháng trị / Suy thận mạn G3a",
    chiefComplaint: "Mệt mỏi nhiều, khát nước, đường huyết dao động 14-18 mmol/L",
    riskLevel: "high",
    riskReason: {
      vi: "eGFR giảm 38 mL/min, cần hiệu chỉnh liều Metformin và rà soát DDI",
      en: "eGFR decreased to 38 mL/min, requires Metformin dose adjustment and DDI review",
    },
    consultationStatus: "council_review",
    attendingDoctor: "ThS.BS Lê Hoàng Anh",
    waitTimeMinutes: 20,
    vitals: { bp: "145/90", hr: 82, spo2: 97, temp: 36.8, rr: 18, egfr: 38 },
    allergies: ["Sulfonamides"],
    activeMedications: [
      { name: "Metformin", dose: "1000mg", frequency: "2v/ngày" },
      { name: "Gliclazide MR", dose: "60mg", frequency: "1v sáng" },
      { name: "Enalapril", dose: "10mg", frequency: "1v sáng" },
    ],
    ddiAlerts: [
      {
        severity: "warning",
        textVi: "Metformin liều cao (2000mg) trên bệnh nhân eGFR 38 mL/min - Cần giảm liều tối đa 1000mg/ngày.",
        textEn: "High-dose Metformin on eGFR 38 mL/min - Reduce max dose to 1000mg/day.",
      },
    ],
    recentNotes: [
      {
        date: "2026-08-24 08:00",
        author: "ThS.BS Lê Hoàng Anh",
        summary: "Bệnh nhân có biến chứng thận do ĐTĐ, kích hoạt Hội đồng chuyên khoa AI để phối hợp SGLT2i + Insulin.",
      },
    ],
    admissionTime: "07:45",
  },
  {
    id: "PT-9403",
    mrn: "MRN-2026-09403",
    name: "Phạm Minh Đức",
    age: 71,
    gender: "M",
    roomBed: "Phòng 308 - Giường 01",
    department: "pulmonology",
    departmentLabel: { vi: "Hô hấp", en: "Pulmonology" },
    primaryDiagnosis: "Đợt cấp COPD nhóm E / Suy hô hấp độ 1",
    chiefComplaint: "Khó thở tăng dần, ho đờm đục nhiều, thở khò khè",
    riskLevel: "high",
    riskReason: {
      vi: "SpO2 91% khí phòng, tiền sử thở máy, nguy cơ suy hô hấp tăng CO2",
      en: "SpO2 91% room air, prior mechanical ventilation, hypercapnic failure risk",
    },
    consultationStatus: "triage_pending",
    attendingDoctor: "BS.CKI Vũ Đình Trọng",
    waitTimeMinutes: 35,
    vitals: { bp: "135/85", hr: 98, spo2: 91, temp: 37.8, rr: 26, egfr: 65 },
    allergies: [],
    activeMedications: [
      { name: "Tiotropium Respimat", dose: "2.5mcg", frequency: "2 nhát sáng" },
      { name: "Seretide Evohaler", dose: "25/250", frequency: "2 nhát x 2" },
    ],
    ddiAlerts: [],
    recentNotes: [
      {
        date: "2026-08-24 07:30",
        author: "BS.CKI Vũ Đình Trọng",
        summary: "Thở oxy gọng kính 2L/phút, khí dung Berodual + Pulmicort, đang chờ kết quả khí máu động mạch.",
      },
    ],
    admissionTime: "07:15",
  },
  {
    id: "PT-9404",
    mrn: "MRN-2026-09404",
    name: "Lê Thanh Hương",
    age: 45,
    gender: "F",
    roomBed: "Phòng Khám 12 - Ngoại trú",
    department: "cardiology",
    departmentLabel: { vi: "Tim mạch", en: "Cardiology" },
    primaryDiagnosis: "Tăng huyết áp nguyên phát độ 2 / Rối loạn lipid máu",
    chiefComplaint: "Đau đầu âm ỉ vùng chẩm gáy vào buổi sáng, chóng mặt nhẹ",
    riskLevel: "moderate",
    riskReason: {
      vi: "Huyết áp chưa kiểm soát mục tiêu, cần tối ưu hóa phối hợp thuốc đôi",
      en: "Blood pressure above target, optimize dual antihypertensive regimen",
    },
    consultationStatus: "awaiting_labs",
    attendingDoctor: "BS. Nguyễn Thùy Linh",
    waitTimeMinutes: 45,
    vitals: { bp: "155/95", hr: 76, spo2: 98, temp: 36.6, rr: 16, egfr: 88 },
    allergies: ["Penicillin"],
    activeMedications: [
      { name: "Amlodipine", dose: "5mg", frequency: "1v sáng" },
    ],
    ddiAlerts: [],
    recentNotes: [
      {
        date: "2026-08-24 07:10",
        author: "BS. Nguyễn Thùy Linh",
        summary: "Chỉ định siêu âm tim Doppler và bilan lipid máu. Đang chờ kết quả xét nghiệm sinh hóa.",
      },
    ],
    admissionTime: "06:50",
  },
  {
    id: "PT-9405",
    mrn: "MRN-2026-09405",
    name: "Vũ Hoàng Nam",
    age: 32,
    gender: "M",
    roomBed: "Phòng Khám 08 - Ngoại trú",
    department: "internal",
    departmentLabel: { vi: "Nội tổng quát", en: "Internal Medicine" },
    primaryDiagnosis: "Viêm dạ dày trào ngược GERD độ B / Viêm họng mạn",
    chiefComplaint: "Nóng rát sau xương ức, ợ chua sau ăn, nuốt vướng 1 tuần",
    riskLevel: "low",
    riskReason: {
      vi: "Sinh hiệu ổn định, không có dấu hiệu báo động (Red Flags)",
      en: "Stable vitals, zero alarm symptoms or red flags present",
    },
    consultationStatus: "ready_review",
    attendingDoctor: "BS. Phạm Quang Hải",
    waitTimeMinutes: 15,
    vitals: { bp: "120/75", hr: 70, spo2: 99, temp: 36.5, rr: 16, egfr: 102 },
    allergies: [],
    activeMedications: [
      { name: "Esomeprazole", dose: "40mg", frequency: "1v trước ăn sáng" },
    ],
    ddiAlerts: [],
    recentNotes: [
      {
        date: "2026-08-24 08:15",
        author: "BS. Phạm Quang Hải",
        summary: "Đã hoàn thành nội soi thực quản dạ dày tuần trước, chỉ định phác đồ PPI liều chuẩn 8 tuần.",
      },
    ],
    admissionTime: "08:00",
  },
  {
    id: "PT-9406",
    mrn: "MRN-2026-09406",
    name: "Đặng Thu Thảo",
    age: 52,
    gender: "F",
    roomBed: "Phòng 204 - Giường 02",
    department: "nephrology",
    departmentLabel: { vi: "Thận học", en: "Nephrology" },
    primaryDiagnosis: "Hội chứng thận hư tái phát / Tăng lipid máu thứ phát",
    chiefComplaint: "Phù 2 chi dưới mức độ vừa, tăng 3kg trong 1 tuần, tiểu bọt nhiều",
    riskLevel: "moderate",
    riskReason: {
      vi: "Protein niệu 24h tăng cao, Albumin máu giảm, cần kiểm tra đông máu",
      en: "Elevated 24h proteinuria, hypoalbuminemia, evaluate thrombosis risk",
    },
    consultationStatus: "in_consultation",
    attendingDoctor: "TS.BS Bùi Đình Thi",
    waitTimeMinutes: 10,
    vitals: { bp: "130/80", hr: 74, spo2: 98, temp: 36.7, rr: 18, egfr: 72 },
    allergies: [],
    activeMedications: [
      { name: "Prednisolone", dose: "5mg", frequency: "8v sáng" },
      { name: "Furosemide", dose: "40mg", frequency: "1v sáng" },
    ],
    ddiAlerts: [],
    recentNotes: [
      {
        date: "2026-08-24 08:20",
        author: "TS.BS Bùi Đình Thi",
        summary: "Đánh giá đáp ứng corticoid, bổ sung canxi và PPI bảo vệ niêm mạc dạ dày.",
      },
    ],
    admissionTime: "08:10",
  },
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

export default function PatientRoster() {
  const language = useUILanguage();
  const router = useRouter();
  const shell = useShellMode();

  // Enforce DENSE shell mode per Spec v5 Section 6.58
  useEffect(() => {
    shell.setMode("dense");
  }, [shell]);

  const [patients, setPatients] = useState<PatientRecord[]>(INITIAL_PATIENT_QUEUE);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedDepartment, setSelectedDepartment] = useState<ClinicalDepartment>("all");
  const [selectedRisk, setSelectedRisk] = useState<string>("all");
  const [selectedStatus, setSelectedStatus] = useState<string>("all");
  const [selectedPatientId, setSelectedPatientId] = useState<string | null>(null);
  const [isInspectorOpen, setIsInspectorOpen] = useState(false);

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

            {/* Vital Signs Grid */}
            <InspectorSection
              title={copy("Sinh hiệu & Chỉ số Lâm sàng", "Vital Signs & Biometrics")}
              defaultExpanded
            >
              <div className="grid grid-cols-3 gap-2.5 pt-2 font-mono">
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
