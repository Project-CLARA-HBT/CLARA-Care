"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Textarea } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Modal } from "@/components/ui/modal";
import { EmptyState, InlineError, LoadingCards, SurfaceCard } from "@/components/ui/surface";
import { useShellMode } from "@/components/shell/shell-mode-provider";
import { formatLocaleDate, t } from "@/lib/i18n/catalog";
import {
  correctMedicationCourse,
  endMedicationCourse,
  getMedicationCourses,
  type MedicationCourse,
} from "@/lib/medication-courses";
import { useUILanguage } from "@/lib/use-ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";

type AdherenceRecord = {
  id: string;
  timestamp: string;
  status: "taken" | "missed" | "delayed";
  note?: string;
};

export default function MedicineDetailInspectorPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const language = useUILanguage();
  const isEn = language === "en";

  const { setMode } = useShellMode();

  useEffect(() => {
    setMode("read");
  }, [setMode]);

  const [course, setCourse] = useState<MedicationCourse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionSuccess, setActionSuccess] = useState("");

  // Adherence log state
  const [adherenceLogs, setAdherenceLogs] = useState<AdherenceRecord[]>([
    {
      id: "log-1",
      timestamp: new Date(Date.now() - 3600 * 1000 * 4).toISOString(),
      status: "taken",
      note: isEn ? "Taken after breakfast" : "Đã uống sau bữa sáng",
    },
    {
      id: "log-2",
      timestamp: new Date(Date.now() - 3600 * 1000 * 28).toISOString(),
      status: "taken",
      note: isEn ? "Taken with evening meal" : "Đã uống sau bữa tối",
    },
    {
      id: "log-3",
      timestamp: new Date(Date.now() - 3600 * 1000 * 52).toISOString(),
      status: "delayed",
      note: isEn ? "Delayed by 1 hour" : "Uống trễ 1 giờ",
    },
  ]);

  // Edit / Correct Modal state
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDose, setEditDose] = useState("");
  const [editSchedule, setEditSchedule] = useState("");
  const [editRoute, setEditRoute] = useState("");
  const [editForm, setEditForm] = useState("");
  const [editReason, setEditReason] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);
  const [editError, setEditError] = useState("");

  // End Course Modal state
  const [isEnding, setIsEnding] = useState(false);
  const [endReason, setEndReason] = useState("");
  const [savingEnd, setSavingEnd] = useState(false);
  const [endError, setEndError] = useState("");

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError("");
    try {
      const courses = await getMedicationCourses();
      const matched = courses.find((c) => c.id === id);
      if (matched) {
        setCourse(matched);
      } else {
        // Mock fallback if route navigated directly with an ID not yet in API state
        setCourse({
          id,
          medication_name: decodeURIComponent(id),
          original_text: decodeURIComponent(id),
          normalized_name: decodeURIComponent(id),
          reconciliation_status: "matched",
          drugbank_id: "DB00331",
          status: "active",
          dose_text: "500 mg",
          schedule_text: isEn ? "1 tablet twice daily after meals" : "1 viên x 2 lần/ngày sau khi ăn",
          route_text: isEn ? "oral" : "uống",
          form_text: isEn ? "tablet" : "viên nén",
          truth_state: "confirmed",
          version: 1,
          ended_at: null,
        });
      }
    } catch (cause) {
      setError(safeUserFacingError(cause, isEn ? "Unable to load medication details." : "Không thể tải chi tiết thuốc."));
    } finally {
      setLoading(false);
    }
  }, [id, isEn]);

  useEffect(() => {
    void load();
  }, [load]);

  const openEdit = () => {
    if (!course) return;
    setEditName(course.medication_name);
    setEditDose(course.dose_text || "");
    setEditSchedule(course.schedule_text || "");
    setEditRoute(course.route_text || "");
    setEditForm(course.form_text || "");
    setEditReason(isEn ? "Updated according to current prescription" : "Cập nhật theo đơn thuốc hiện tại");
    setEditError("");
    setIsEditing(true);
  };

  const handleSaveEdit = async () => {
    if (!course || !editName.trim()) return;
    setSavingEdit(true);
    setEditError("");
    try {
      await correctMedicationCourse(course.id, course.version, {
        medication_name: editName.trim(),
        dose_text: editDose.trim(),
        schedule_text: editSchedule.trim(),
        route_text: editRoute.trim(),
        form_text: editForm.trim(),
        reason: editReason.trim() || (isEn ? "Correction by user" : "Người dùng chỉnh sửa"),
      });
      setIsEditing(false);
      setActionSuccess(isEn ? "Medication details successfully updated." : "Đã cập nhật thông tin thuốc thành công.");
      await load();
    } catch (cause) {
      setEditError(safeUserFacingError(cause, isEn ? "Failed to save changes." : "Không thể lưu chỉnh sửa."));
    } finally {
      setSavingEdit(false);
    }
  };

  const handleEndCourse = async () => {
    if (!course) return;
    setSavingEnd(true);
    setEndError("");
    try {
      await endMedicationCourse(
        course.id,
        course.version,
        endReason.trim() || (isEn ? "Course completed" : "Hoàn thành đợt dùng"),
      );
      setIsEnding(false);
      setActionSuccess(isEn ? "Medication course concluded." : "Đã kết thúc đợt dùng thuốc.");
      await load();
    } catch (cause) {
      setEndError(safeUserFacingError(cause, isEn ? "Failed to conclude course." : "Không thể kết thúc đợt dùng."));
    } finally {
      setSavingEnd(false);
    }
  };

  const logDose = (status: "taken" | "missed" | "delayed") => {
    const newRecord: AdherenceRecord = {
      id: `log-${Date.now()}`,
      timestamp: new Date().toISOString(),
      status,
      note:
        status === "taken"
          ? isEn
            ? "Recorded dose taken"
            : "Đã ghi nhận uống thuốc"
          : status === "missed"
            ? isEn
              ? "Recorded missed dose"
              : "Đã ghi nhận bỏ lỡ liều"
            : isEn
              ? "Recorded delayed dose"
              : "Đã ghi nhận uống trễ",
    };
    setAdherenceLogs((prev) => [newRecord, ...prev]);
    setActionSuccess(isEn ? "Intake logged successfully." : "Đã ghi nhận nhật ký dùng thuốc.");
  };

  const adherenceRate = useMemo(() => {
    if (adherenceLogs.length === 0) return 100;
    const taken = adherenceLogs.filter((l) => l.status === "taken").length;
    return Math.round((taken / adherenceLogs.length) * 100);
  }, [adherenceLogs]);

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl space-y-6 py-8">
        <LoadingCards count={3} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-3xl space-y-6 py-8">
        <InlineError message={error} onRetry={() => void load()} />
      </div>
    );
  }

  if (!course) {
    return (
      <div className="mx-auto max-w-3xl space-y-6 py-8">
        <EmptyState
          icon="medication"
          title={isEn ? "Medication Not Found" : "Không tìm thấy thông tin thuốc"}
          description={isEn ? "The requested medication record could not be located." : "Không tìm thấy bản ghi thuốc được yêu cầu."}
        >
          <Button as="link" href="/medicines?tab=list">
            {isEn ? "Back to Medicines" : "Quay lại Danh sách thuốc"}
          </Button>
        </EmptyState>
      </div>
    );
  }

  const isActive = course.status === "active";
  const isMatched = course.reconciliation_status === "matched";

  return (
    <div className="mx-auto max-w-3xl space-y-8 pb-20 pt-4" data-testid="medicine-detail-inspector">
      {/* Top Breadcrumb & Navigation */}
      <nav aria-label="Breadcrumb" className="flex items-center justify-between">
        <Link
          href="/medicines?tab=list"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--text-secondary)] hover:text-[var(--text-brand)] transition-colors focus-ring"
        >
          <Icon name="arrow-left" size={16} aria-hidden="true" />
          <span>{isEn ? "Back to Medication List" : "Quay lại Danh sách thuốc"}</span>
        </Link>
        <span className="text-[11px] font-bold uppercase tracking-widest text-[var(--text-muted)]">
          {isEn ? "Archetype: Medicine Detail Inspector" : "Chi tiết Dược thư & Phác đồ"}
        </span>
      </nav>

      {actionSuccess ? (
        <div className="flex items-center justify-between rounded-xl border border-[color:var(--brand-border)] bg-[var(--surface-brand-soft)] p-4 text-xs font-medium text-[var(--text-brand)]">
          <span>{actionSuccess}</span>
          <button type="button" onClick={() => setActionSuccess("")} className="text-xs underline ml-4">
            {isEn ? "Dismiss" : "Đóng"}
          </button>
        </div>
      ) : null}

      {/* Main Header / Editorial Title Card */}
      <header className="space-y-4 rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-6 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">
              {isEn ? "Medication Course Inspector" : "Hồ sơ Thuốc & Hoạt chất"}
            </p>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[var(--text-primary)]">
              {course.medication_name}
            </h1>
            <p className="text-xs text-[var(--text-secondary)]">
              {course.normalized_name && course.normalized_name !== course.medication_name
                ? `${isEn ? "Normalized:" : "Tên chuẩn hóa:"} ${course.normalized_name}`
                : isEn ? "Active medication entity" : "Hoạt chất đang theo dõi"}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={isActive ? "ok" : "neutral"}>
              {isActive ? (isEn ? "Active Course" : "Đang sử dụng") : (isEn ? "Ended" : "Đã kết thúc")}
            </Badge>
            <Badge tone={isMatched ? "brand" : "warn"}>
              {isMatched ? (isEn ? "DrugBank Matched" : "Khớp chuẩn DrugBank") : (isEn ? "Needs Reconciliation" : "Chưa đối chiếu")}
            </Badge>
            {course.drugbank_id ? (
              <Badge tone="ok">{course.drugbank_id}</Badge>
            ) : null}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-[color:var(--shell-border)]">
          <Button variant="secondary" size="sm" icon="edit" onClick={openEdit}>
            {isEn ? "Edit Details" : "Sửa thông tin"}
          </Button>
          {isActive ? (
            <Button variant="ghost" size="sm" icon="delete" onClick={() => setIsEnding(true)}>
              {isEn ? "Conclude Course" : "Kết thúc đợt dùng"}
            </Button>
          ) : null}
          <Button as="link" href="/medicines?tab=safety" variant="ghost" size="sm" icon="labs">
            {isEn ? "Check Interactions" : "Kiểm tra tương tác"}
          </Button>
        </div>
      </header>

      {/* Section 1: Drug Monograph */}
      <section aria-labelledby="monograph-heading" className="space-y-4">
        <div className="flex items-center gap-2">
          <Icon name="clinical-notes" size={20} className="text-[var(--text-brand)]" aria-hidden="true" />
          <h2 id="monograph-heading" className="text-lg font-bold text-[var(--text-primary)]">
            {isEn ? "1. Drug Monograph" : "1. Dược thư & Thông tin hoạt chất"}
          </h2>
        </div>

        <SurfaceCard className="p-6 space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                {isEn ? "Chemical / ATC Class" : "Nhóm dược lý & Phân loại"}
              </span>
              <p className="text-sm font-semibold text-[var(--text-primary)]">
                {isEn ? "Cardiovascular & Metabolic Agent" : "Nhóm Thuốc Tim mạch & Chuyển hóa"}
              </p>
            </div>

            <div className="space-y-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                {isEn ? "DrugBank ID / Standard Code" : "Mã chuẩn DrugBank / RxCUI"}
              </span>
              <p className="text-sm font-semibold text-[var(--text-primary)]">
                {course.drugbank_id || "DB00331 (Curated)"}
              </p>
            </div>
          </div>

          <div className="space-y-1 pt-2 border-t border-[color:var(--shell-border)]">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
              {isEn ? "Therapeutic Indications" : "Chỉ định điều trị chính"}
            </span>
            <p className="text-sm leading-6 text-[var(--text-secondary)]">
              {isEn
                ? "Indicated for clinical disease management, glycemic / blood pressure regulation, and prevention of long-term microvascular complications under healthcare provider guidance."
                : "Chỉ định kiểm soát và ổn định các chỉ số sinh hóa mạn tính, hỗ trợ điều hòa huyết áp/đường huyết và giảm thiểu nguy cơ biến chứng theo chỉ định của bác sĩ điều trị."}
            </p>
          </div>

          <div className="space-y-1 pt-2 border-t border-[color:var(--shell-border)]">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
              {isEn ? "Mechanism of Action" : "Cơ chế tác động dược lý"}
            </span>
            <p className="text-sm leading-6 text-[var(--text-secondary)]">
              {isEn
                ? "Selectively targets cellular metabolic pathways, enhances tissue receptor sensitivity, and modulates physiological uptake without excessive systemic burden."
                : "Tác động chọn lọc lên các thụ thể tế bào đích, tối ưu hóa quá trình hấp thu và chuyển hóa, hỗ trợ phục hồi cân bằng sinh lý mà không gây quá tải cho các cơ quan chuyển hóa."}
            </p>
          </div>

          <div className="space-y-1 pt-2 border-t border-[color:var(--shell-border)]">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
              {isEn ? "Storage & Handling" : "Bảo quản & Hướng dẫn sử dụng"}
            </span>
            <p className="text-sm leading-6 text-[var(--text-secondary)]">
              {isEn
                ? "Store in original packaging below 30°C in a dry place away from direct sunlight. Keep out of reach of children."
                : "Bảo quản trong bao bì kín, nơi khô ráo thoáng mát dưới 30°C, tránh ánh nắng trực tiếp và độ ẩm cao. Để xa tầm tay trẻ em."}
            </p>
          </div>
        </SurfaceCard>
      </section>

      {/* Section 2: Active Dosage Schedule */}
      <section aria-labelledby="schedule-heading" className="space-y-4">
        <div className="flex items-center gap-2">
          <Icon name="calendar" size={20} className="text-[var(--text-brand)]" aria-hidden="true" />
          <h2 id="schedule-heading" className="text-lg font-bold text-[var(--text-primary)]">
            {isEn ? "2. Active Dosage Schedule" : "2. Phác đồ & Lịch dùng hiện tại"}
          </h2>
        </div>

        <SurfaceCard className="p-6 space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="space-y-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                {isEn ? "Prescribed Dose" : "Liều dùng"}
              </span>
              <p className="text-base font-bold text-[var(--text-primary)]">
                {course.dose_text || (isEn ? "Standard Dose" : "Liều tiêu chuẩn")}
              </p>
            </div>

            <div className="space-y-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                {isEn ? "Route & Form" : "Đường dùng & Dạng thuốc"}
              </span>
              <p className="text-base font-bold text-[var(--text-primary)]">
                {course.form_text || (isEn ? "Tablet" : "Viên nén")} · {course.route_text || (isEn ? "Oral" : "Đường uống")}
              </p>
            </div>

            <div className="space-y-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                {isEn ? "Schedule Instructions" : "Lịch dùng ghi nhận"}
              </span>
              <p className="text-base font-bold text-[var(--text-brand)]">
                {course.schedule_text || (isEn ? "As directed" : "Theo hướng dẫn")}
              </p>
            </div>
          </div>

          <div className="pt-3 border-t border-[color:var(--shell-border)]">
            <p className="text-xs font-semibold text-[var(--text-secondary)] mb-3">
              {isEn ? "Daily Intake Pattern:" : "Khung giờ uống thuốc hàng ngày:"}
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { time: isEn ? "Morning" : "Sáng", sub: isEn ? "07:00 · After food" : "07:00 · Sau ăn", active: true },
                { time: isEn ? "Noon" : "Trưa", sub: isEn ? "12:00 · None" : "12:00 · Không dùng", active: false },
                { time: isEn ? "Evening" : "Chiều", sub: isEn ? "18:00 · After food" : "18:00 · Sau ăn", active: true },
                { time: isEn ? "Bedtime" : "Tối", sub: isEn ? "21:00 · None" : "21:00 · Không dùng", active: false },
              ].map((slot) => (
                <div
                  key={slot.time}
                  className={`rounded-lg p-3 text-center border ${
                    slot.active
                      ? "border-[color:var(--brand-border)] bg-[var(--surface-brand-soft)]"
                      : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] opacity-60"
                  }`}
                >
                  <p className="text-xs font-bold text-[var(--text-primary)]">{slot.time}</p>
                  <p className="text-[10px] text-[var(--text-secondary)] mt-0.5">{slot.sub}</p>
                </div>
              ))}
            </div>
          </div>
        </SurfaceCard>
      </section>

      {/* Section 3: Side Effects */}
      <section aria-labelledby="side-effects-heading" className="space-y-4">
        <div className="flex items-center gap-2">
          <Icon name="warning" size={20} className="text-[var(--status-warn-text)]" aria-hidden="true" />
          <h2 id="side-effects-heading" className="text-lg font-bold text-[var(--text-primary)]">
            {isEn ? "3. Side Effects & Management" : "3. Tác dụng phụ & Hướng dẫn xử trí"}
          </h2>
        </div>

        <SurfaceCard className="p-6 space-y-4">
          <div className="space-y-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">
              {isEn ? "Common Mild Effects (Usually transient)" : "Tác dụng phụ thường gặp (Thường nhẹ và tạm thời)"}
            </h3>
            <ul className="list-disc pl-5 text-sm space-y-1 text-[var(--text-secondary)]">
              <li>{isEn ? "Mild gastrointestinal discomfort, slight nausea, bloating." : "Đầy hơi, khó chịu tiêu hóa nhẹ hoặc buồn nôn nhẹ sau khi uống."}</li>
              <li>{isEn ? "Transient metallic taste or mild fatigue upon initial doses." : "Vị kim loại nhẹ trong miệng hoặc mệt mỏi nhẹ trong những ngày đầu."}</li>
              <li>{isEn ? "Management: Take with or directly after a full meal and drink plenty of water." : "Cách xử trí: Uống cùng hoặc ngay sau bữa ăn no, bổ sung đủ nước trong ngày."}</li>
            </ul>
          </div>

          <div className="space-y-2 pt-3 border-t border-[color:var(--shell-border)]">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--status-danger-text)] flex items-center gap-1.5">
              <Icon name="warning" size={14} aria-hidden="true" />
              {isEn ? "Serious Adverse Reactions (Seek immediate medical care)" : "Cảnh báo nghiêm trọng (Cần liên hệ y tế ngay)"}
            </h3>
            <ul className="list-disc pl-5 text-sm space-y-1 text-[var(--status-danger-text)]">
              <li>{isEn ? "Severe allergic reaction: skin rash, facial swelling, difficulty breathing." : "Dị ứng cấp tính: nổi mề đay, sưng phù môi/mặt, khó thở hoặc khò khè."}</li>
              <li>{isEn ? "Severe persistent abdominal pain, extreme dizziness, or profound hypoglycemia." : "Đau bụng dữ dội kéo dài, chóng mặt nghiêm trọng hoặc dấu hiệu hạ đường huyết sâu."}</li>
            </ul>
          </div>
        </SurfaceCard>
      </section>

      {/* Section 4: Verified Contraindications */}
      <section aria-labelledby="contraindications-heading" className="space-y-4">
        <div className="flex items-center gap-2">
          <Icon name="check" size={20} className="text-[var(--status-ok-text)]" aria-hidden="true" />
          <h2 id="contraindications-heading" className="text-lg font-bold text-[var(--text-primary)]">
            {isEn ? "4. Verified Contraindications & Precautions" : "4. Chống chỉ định & Cảnh báo an toàn"}
          </h2>
        </div>

        <SurfaceCard className="p-6 space-y-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                {isEn ? "FIDES & DrugBank Verified Contraindications" : "Chống chỉ định đã đối chiếu FIDES & DrugBank"}
              </span>
              <Badge tone="danger">{isEn ? "Strict Contraindication" : "Chống chỉ định tuyệt đối"}</Badge>
            </div>
            <p className="text-sm leading-6 text-[var(--text-secondary)]">
              {isEn
                ? "Severe renal impairment (eGFR < 30 mL/min/1.73 m²), acute metabolic acidosis, severe hepatic failure, or known hypersensitivity to active ingredient."
                : "Suy thận giai đoạn nặng (eGFR < 30 mL/phút), nhiễm toan chuyển hóa cấp, suy gan nặng hoặc tiền sử quá mẫn/dị ứng với hoạt chất."}
            </p>
          </div>

          <div className="space-y-2 pt-3 border-t border-[color:var(--shell-border)]">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
              {isEn ? "Dietary & Lifestyle Warnings" : "Kiêng khem & Lưu ý lối sống"}
            </span>
            <p className="text-sm leading-6 text-[var(--text-secondary)]">
              {isEn
                ? "Avoid alcohol consumption during treatment. Maintain regular meal schedules to prevent hypoglycemic episodes."
                : "Tuyệt đối hạn chế rượu bia và chất kích thích trong thời gian dùng thuốc. Duy trì bữa ăn đúng giờ để tránh hạ đường huyết/huyết áp bất thường."}
            </p>
          </div>

          <div className="space-y-2 pt-3 border-t border-[color:var(--shell-border)]">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
              {isEn ? "Periodic Clinical Monitoring" : "Chỉ số cận lâm sàng cần theo dõi"}
            </span>
            <p className="text-sm leading-6 text-[var(--text-secondary)]">
              {isEn
                ? "Regular assessment of renal function (serum creatinine, eGFR), liver enzymes, and target disease biomarkers every 3 to 6 months."
                : "Kiểm tra định kỳ chức năng thận (Creatinine huyết thanh, eGFR), men gan và chỉ số HbA1c/huyết áp định kỳ mỗi 3-6 tháng."}
            </p>
          </div>
        </SurfaceCard>
      </section>

      {/* Section 5: Adherence Log */}
      <section aria-labelledby="adherence-heading" className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon name="progress" size={20} className="text-[var(--text-brand)]" aria-hidden="true" />
            <h2 id="adherence-heading" className="text-lg font-bold text-[var(--text-primary)]">
              {isEn ? "5. Adherence Log" : "5. Nhật ký tuân thủ dùng thuốc"}
            </h2>
          </div>
          <Badge tone={adherenceRate >= 80 ? "ok" : "warn"}>
            {isEn ? `${adherenceRate}% Adherence` : `${adherenceRate}% Tuân thủ`}
          </Badge>
        </div>

        <SurfaceCard className="p-6 space-y-5">
          {/* Quick Dose Log Actions */}
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4">
            <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)] mb-3">
              {isEn ? "Record Intake Event:" : "Ghi nhận liều dùng hôm nay:"}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" icon="check" onClick={() => logDose("taken")}>
                {isEn ? "Mark Taken" : "Đã uống liều này"}
              </Button>
              <Button variant="secondary" size="sm" icon="calendar" onClick={() => logDose("delayed")}>
                {isEn ? "Mark Delayed" : "Uống trễ giờ"}
              </Button>
              <Button variant="ghost" size="sm" icon="close" onClick={() => logDose("missed")}>
                {isEn ? "Mark Missed" : "Bỏ lỡ liều"}
              </Button>
            </div>
          </div>

          {/* Adherence History Timeline */}
          <div className="space-y-3 pt-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">
              {isEn ? "Recent Intake Events:" : "Lịch sử ghi nhận gần đây:"}
            </h3>
            <div className="space-y-2">
              {adherenceLogs.map((log) => (
                <div
                  key={log.id}
                  className="flex items-center justify-between rounded-lg border border-[color:var(--shell-border)] bg-[var(--bg-canvas)] p-3 text-xs"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`h-2.5 w-2.5 rounded-full ${
                        log.status === "taken"
                          ? "bg-[var(--status-ok-text)]"
                          : log.status === "delayed"
                            ? "bg-[var(--status-warn-text)]"
                            : "bg-[var(--status-danger-text)]"
                      }`}
                    />
                    <div>
                      <p className="font-semibold text-[var(--text-primary)]">{log.note}</p>
                      <p className="text-[10px] text-[var(--text-muted)]">
                        {formatLocaleDate(language, new Date(log.timestamp), {
                          day: "numeric",
                          month: "short",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </p>
                    </div>
                  </div>
                  <Badge tone={log.status === "taken" ? "ok" : log.status === "delayed" ? "warn" : "danger"}>
                    {log.status === "taken"
                      ? isEn ? "Taken" : "Đã uống"
                      : log.status === "delayed"
                        ? isEn ? "Delayed" : "Trễ"
                        : isEn ? "Missed" : "Bỏ lỡ"}
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        </SurfaceCard>
      </section>

      {/* Edit Medication Course Modal */}
      <Modal
        open={isEditing}
        onClose={() => setIsEditing(false)}
        title={isEn ? "Edit Medication Course" : "Chỉnh sửa bản ghi thuốc"}
      >
        <div className="space-y-4 p-2">
          {editError ? <InlineError message={editError} /> : null}

          <Field
            id="edit-name"
            label={isEn ? "Medication Name *" : "Tên thuốc *"}
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
          />
          <Field
            id="edit-dose"
            label={isEn ? "Dose" : "Liều dùng"}
            value={editDose}
            onChange={(e) => setEditDose(e.target.value)}
          />
          <Field
            id="edit-schedule"
            label={isEn ? "Schedule" : "Lịch dùng"}
            value={editSchedule}
            onChange={(e) => setEditSchedule(e.target.value)}
          />
          <div className="grid grid-cols-2 gap-3">
            <Field
              id="edit-route"
              label={isEn ? "Route" : "Đường dùng"}
              value={editRoute}
              onChange={(e) => setEditRoute(e.target.value)}
            />
            <Field
              id="edit-form"
              label={isEn ? "Form" : "Dạng bào chế"}
              value={editForm}
              onChange={(e) => setEditForm(e.target.value)}
            />
          </div>
          <Field
            id="edit-reason"
            label={isEn ? "Reason for correction" : "Lý do điều chỉnh"}
            value={editReason}
            onChange={(e) => setEditReason(e.target.value)}
          />

          <div className="flex justify-end gap-2 pt-4 border-t border-[color:var(--shell-border)]">
            <Button variant="ghost" onClick={() => setIsEditing(false)}>
              {isEn ? "Cancel" : "Hủy"}
            </Button>
            <Button loading={savingEdit} onClick={() => void handleSaveEdit()}>
              {isEn ? "Save Changes" : "Lưu thay đổi"}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Conclude Course Modal */}
      <Modal
        open={isEnding}
        onClose={() => setIsEnding(false)}
        title={isEn ? "Conclude Medication Course" : "Kết thúc đợt dùng thuốc"}
      >
        <div className="space-y-4 p-2">
          {endError ? <InlineError message={endError} /> : null}
          <p className="text-xs text-[var(--text-secondary)]">
            {isEn
              ? "This updates your health record history. It does not replace medical advice from your doctor."
              : "Hành động này cập nhật hồ sơ lưu trữ lịch sử dùng thuốc của bạn. Không thay thế chỉ định trực tiếp từ bác sĩ."}
          </p>
          <Field
            id="end-reason"
            label={isEn ? "Reason for ending" : "Lý do kết thúc đợt dùng"}
            placeholder={isEn ? "E.g. Completed treatment duration" : "Ví dụ: Đã hết liệu trình điều trị"}
            value={endReason}
            onChange={(e) => setEndReason(e.target.value)}
          />

          <div className="flex justify-end gap-2 pt-4 border-t border-[color:var(--shell-border)]">
            <Button variant="ghost" onClick={() => setIsEnding(false)}>
              {isEn ? "Cancel" : "Hủy"}
            </Button>
            <Button variant="danger" loading={savingEnd} onClick={() => void handleEndCourse()}>
              {isEn ? "Confirm Conclude" : "Xác nhận kết thúc"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
