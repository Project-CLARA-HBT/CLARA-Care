"use client";

import { Suspense, useMemo, useState } from "react";
import Link from "next/link";
import { HealthPageHeader } from "@/components/consumer/health-page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Select, Textarea } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Modal } from "@/components/ui/modal";
import { useUILanguage } from "@/lib/use-ui-language";
import { getActiveProfileId } from "@/lib/profile-context";
import {
  v2Client,
  type SymptomCheckResultDto,
  type SymptomUrgencyLevel,
} from "@/lib/api/v2-client";

type Step = 1 | 2 | 3 | 4;

interface RedFlagItem {
  id: string;
  labelVi: string;
  labelEn: string;
  descriptionVi: string;
  descriptionEn: string;
}

const RED_FLAGS: RedFlagItem[] = [
  {
    id: "chest_pain",
    labelVi: "Đau ngực dữ dội hoặc tức ngực lan lên hàm, vai, tay trái",
    labelEn: "Severe crushing chest pain spreading to jaw, neck, or left arm",
    descriptionVi: "Dấu hiệu nghi ngờ Nhồi máu cơ tim cấp hoặc hội chứng mạch vành.",
    descriptionEn: "Possible acute myocardial infarction or coronary syndrome.",
  },
  {
    id: "stroke_fast",
    labelVi: "Đột ngột yếu liệt một bên người, méo miệng, nói ngọng / khó nói",
    labelEn: "Sudden facial drooping, arm weakness, or slurred speech (FAST)",
    descriptionVi: "Dấu hiệu cảnh báo Đột quỵ não cấp (thời gian vàng cấp cứu).",
    descriptionEn: "Critical acute stroke warning sign (FAST protocol).",
  },
  {
    id: "severe_sob",
    labelVi: "Khó thở dữ dội, tím tái môi đầu chi, không nói được cả câu",
    labelEn: "Severe shortness of breath, cyanosis, unable to speak full sentences",
    descriptionVi: "Dấu hiệu suy hô hấp cấp hoặc co thắt phế quản nặng.",
    descriptionEn: "Acute respiratory distress or severe bronchospasm.",
  },
  {
    id: "cough_vomit_blood",
    labelVi: "Ho ra máu tươi hoặc nôn ra máu lượng nhiều, phân đen như bã cà phê",
    labelEn: "Coughing up fresh blood, vomiting blood, or black tarry stools",
    descriptionVi: "Dấu hiệu xuất huyết tiêu hóa hoặc xuất huyết đường hô hấp trên/dưới.",
    descriptionEn: "Severe gastrointestinal or respiratory tract bleeding.",
  },
  {
    id: "anaphylaxis",
    labelVi: "Sưng nề mắt, môi, nghẹn cổ họng sau khi dùng thuốc, tiêm hoặc ăn",
    labelEn: "Swollen lips, throat constriction, or severe hives after food/drugs",
    descriptionVi: "Dấu hiệu phản vệ đe dọa tắc nghẽn đường thở.",
    descriptionEn: "Severe anaphylactic reaction threatening airway obstruction.",
  },
  {
    id: "unconscious",
    labelVi: "Bất tỉnh, lơ mơ, co giật hoặc thay đổi tri giác đột ngột",
    labelEn: "Loss of consciousness, seizure, or sudden altered mental status",
    descriptionVi: "Dấu hiệu suy tuần hoàn, hôn mê hoặc rối loạn thần kinh trung ương.",
    descriptionEn: "Loss of consciousness or acute neurologic emergency.",
  },
  {
    id: "acute_abdomen",
    labelVi: "Đau bụng dữ dội đột ngột, bụng cứng như gỗ, sốt cao",
    labelEn: "Sudden acute severe abdominal pain, rigid abdomen, high fever",
    descriptionVi: "Dấu hiệu viêm phúc mạc hoặc thủng tạng rỗng cấp cứu ngoại khoa.",
    descriptionEn: "Possible surgical acute abdomen or peritonitis.",
  },
];

const COMMON_SYMPTOMS_VI = [
  { category: "Toàn thân", items: ["Sốt", "Mệt mỏi suy nhược", "Ớn lạnh", "Sụt cân không rõ nguyên nhân"] },
  { category: "Đầu & Thần kinh", items: ["Đau đầu", "Chóng mặt quay cuồng", "Mất ngủ", "Căng thẳng lo âu"] },
  { category: "Hô hấp & Tai mũi họng", items: ["Ho có đờm", "Ho khan kéo dài", "Đau rát họng", "Nghẹt mũi chảy mũi", "Sổ mũi"] },
  { category: "Tiêu hóa", items: ["Đau bụng âm ỉ", "Buồn nôn hoặc nôn", "Tiêu chảy", "Ợ chua nóng rát thượng vị", "Táo bón"] },
  { category: "Tim mạch & Tuần hoàn", items: ["Hồi hộp đánh trống ngực", "Phù mắt cá chân", "Mệt khi gắng sức"] },
  { category: "Cơ xương khớp", items: ["Đau nhức khớp gối", "Đau thắt lưng", "Mỏi cơ toàn thân"] },
  { category: "Da liễu", items: ["Phát ban ngứa", "Mày đay", "Khô da tróc vảy"] },
];

function getUrgencyBadgeTone(urgency?: string) {
  switch (urgency) {
    case "emergency":
      return "danger";
    case "urgent":
      return "warn";
    case "routine":
      return "brand";
    case "pharmacist":
      return "neutral";
    case "self_care":
    default:
      return "ok";
  }
}

function getUrgencyTitle(urgency?: string, locale: "vi" | "en" = "vi") {
  const isEn = locale === "en";
  switch (urgency) {
    case "emergency":
      return isEn ? "Emergency Care (Call 115 / Go to ER)" : "Cấp cứu khẩn cấp (Gọi 115 / Tới phòng cấp cứu)";
    case "urgent":
      return isEn ? "Urgent Same-Day Medical Evaluation" : "Cần khám trong ngày tại cơ sở y tế";
    case "routine":
      return isEn ? "Routine Outpatient Consultation" : "Khám thông thường / Hẹn khám chuyên khoa";
    case "pharmacist":
      return isEn ? "Pharmacist Consultation & OTC Relief" : "Tham vấn Dược sĩ & Thuốc không kê đơn";
    case "self_care":
    default:
      return isEn ? "Home Self-Care & Active Monitoring" : "Tự chăm sóc & Theo dõi tại nhà";
  }
}

function SymptomCheckerContent() {
  const uiLanguage = useUILanguage();
  const isEn = uiLanguage === "en";

  const [currentStep, setCurrentStep] = useState<Step>(1);
  const [selectedRedFlags, setSelectedRedFlags] = useState<string[]>([]);
  const [selectedSymptoms, setSelectedSymptoms] = useState<string[]>([]);
  const [searchSymptom, setSearchSymptom] = useState("");
  const [customSymptomInput, setCustomSymptomInput] = useState("");

  // Step 2: Duration & Severity
  const [duration, setDuration] = useState("1_3_days");
  const [severity, setSeverity] = useState<"mild" | "moderate" | "severe">("moderate");
  const [onset, setOnset] = useState("gradual");

  // Step 3: Context & Safety
  const [hasHighFever, setHasHighFever] = useState(false);
  const [knownConditions, setKnownConditions] = useState<string>("");
  const [currentMeds, setCurrentMeds] = useState<string>("");
  const [userNotes, setUserNotes] = useState("");

  // Emergency Modal override
  const [showEmergencyModal, setShowEmergencyModal] = useState(false);
  const [acknowledgedEmergency, setAcknowledgedEmergency] = useState(false);

  // Result state
  const [result, setResult] = useState<SymptomCheckResultDto | null>(null);
  const [isEvaluating, setIsEvaluating] = useState(false);

  const toggleRedFlag = (flagId: string) => {
    setSelectedRedFlags((prev) => {
      const exists = prev.includes(flagId);
      const next = exists ? prev.filter((id) => id !== flagId) : [...prev, flagId];
      if (!exists) {
        // Immediate deterministic override: trigger emergency modal
        setShowEmergencyModal(true);
      }
      return next;
    });
  };

  const toggleSymptom = (symptomName: string) => {
    setSelectedSymptoms((prev) =>
      prev.includes(symptomName)
        ? prev.filter((s) => s !== symptomName)
        : [...prev, symptomName],
    );
  };

  const handleAddCustomSymptom = () => {
    if (!customSymptomInput.trim()) return;
    if (!selectedSymptoms.includes(customSymptomInput.trim())) {
      setSelectedSymptoms((prev) => [...prev, customSymptomInput.trim()]);
    }
    setCustomSymptomInput("");
  };

  const handleCalculateResult = async () => {
    setIsEvaluating(true);
    setCurrentStep(4);

    // If red flags were selected, urgency is deterministic Emergency
    if (selectedRedFlags.length > 0) {
      setResult({
        urgency: "emergency",
        is_red_flag_emergency: true,
        title: isEn ? "Immediate Emergency Medical Care Required" : "Cần cấp cứu y tế ngay lập tức",
        explanation: isEn
          ? "You reported critical red-flag warning signs that require emergency room evaluation. Do not wait for standard outpatient hours."
          : "Hệ thống phát hiện dấu hiệu cảnh báo đỏ nguy hiểm tính mạng. Cần được bác sĩ cấp cứu thăm khám ngay lập tức, không nên tự điều trị tại nhà.",
        care_navigation_guidance: isEn
          ? "Call emergency services (115 in Vietnam) or go immediately to the nearest hospital Emergency Room."
          : "Gọi ngay cấp cứu 115 hoặc nhờ người thân đưa ngay tới khoa Cấp cứu bệnh viện gần nhất.",
        recommended_actions: [
          isEn ? "Call 115 or emergency dispatch immediately" : "Gọi cấp cứu 115 ngay lập tức",
          isEn ? "Do not drive yourself — have someone accompany you" : "Không tự lái xe, nhờ người thân trợ giúp",
          isEn ? "Keep all current medications accessible for the ER team" : "Mang theo đơn thuốc và giấy tờ tùy thân",
        ],
        clinician_handoff_summary: `TRIỆU CHỨNG KHẨN CẤP: ${selectedRedFlags.map((rf) => RED_FLAGS.find((f) => f.id === rf)?.labelVi).join(", ")}. Triệu chứng kèm theo: ${selectedSymptoms.join(", ")}.`,
        questions_for_doctor: [
          "Tình trạng này có nguy hiểm đến tính mạng không?",
          "Tôi có cần can thiệp cấp cứu chuyên khoa ngay không?",
        ],
        when_to_seek_immediate_care: [
          "Bất kỳ dấu hiệu khó thở tăng dần",
          "Đau ngực dữ dội không giảm sau 5 phút nghỉ ngơi",
          "Ngất xỉu hoặc mất ý thức",
        ],
      });
      setIsEvaluating(false);
      return;
    }

    try {
      const res = await v2Client.checkSymptoms({
        symptoms: selectedSymptoms,
        duration,
        severity,
        red_flags: selectedRedFlags,
        answers: {
          has_high_fever: hasHighFever,
          known_conditions: knownConditions,
          current_medications: currentMeds,
          onset_pattern: onset,
        },
        notes: userNotes,
      });
      setResult(res);
    } catch {
      // Deterministic triage fallback logic
      let calculatedUrgency: SymptomUrgencyLevel = "self_care";
      if (severity === "severe" || hasHighFever) {
        calculatedUrgency = "urgent";
      } else if (severity === "moderate" || duration === "more_than_week") {
        calculatedUrgency = "routine";
      } else if (selectedSymptoms.some((s) => s.includes("họng") || s.includes("Nghẹt") || s.includes("Sổ mũi"))) {
        calculatedUrgency = "pharmacist";
      }

      setResult({
        urgency: calculatedUrgency,
        is_red_flag_emergency: false,
        title: getUrgencyTitle(calculatedUrgency, uiLanguage),
        explanation:
          calculatedUrgency === "urgent"
            ? isEn
              ? "Your symptoms indicate a significant acute condition with high severity or fever. A medical consultation within 24 hours is advised."
              : "Triệu chứng có mức độ nặng hoặc kèm sốt cao. Bạn nên đến phòng khám hoặc bệnh viện trong ngày để bác sĩ kiểm tra."
            : calculatedUrgency === "routine"
              ? isEn
                ? "Your symptoms warrant clinical evaluation, but do not show acute red flags. Schedule a routine doctor visit."
                : "Triệu chứng cần được bác sĩ đánh giá nhưng không có dấu hiệu khẩn cấp. Bạn có thể đặt lịch hẹn khám chuyên khoa trong 1-3 ngày tới."
              : calculatedUrgency === "pharmacist"
                ? isEn
                  ? "Mild symptoms may be alleviated by over-the-counter remedies. Discuss with a qualified pharmacist."
                  : "Các triệu chứng nhẹ có thể cải thiện bằng thuốc không kê đơn. Hãy tham vấn ý kiến dược sĩ tại nhà thuốc."
                : isEn
                  ? "Your symptoms appear mild and suitable for home rest and hydration. Monitor for any worsening signs."
                  : "Các triệu chứng nhẹ, có thể theo dõi tại nhà kết hợp nghỉ ngơi, uống đủ nước và ăn uống thanh đạm.",
        care_navigation_guidance:
          calculatedUrgency === "urgent"
            ? isEn ? "Visit an outpatient clinic or hospital today." : "Đến phòng khám hoặc bệnh viện trong ngày hôm nay."
            : calculatedUrgency === "routine"
              ? isEn ? "Book a consultation with a specialist." : "Đặt lịch hẹn tái khám hoặc khám chuyên khoa phù hợp."
              : isEn ? "Consult a pharmacist and rest at home." : "Tham vấn dược sĩ hoặc nghỉ ngơi, theo dõi tại nhà.",
        recommended_actions: [
          isEn ? "Keep a log of symptoms and temperature" : "Theo dõi nhiệt độ cơ thể và ghi chép triệu chứng",
          isEn ? "Stay well-hydrated and rest adequately" : "Uống đủ nước (2 lít/ngày) và nghỉ ngơi hợp lý",
          isEn ? "Bring previous medical history to consultation" : "Mang theo hồ sơ khám cũ nếu có",
        ],
        clinician_handoff_summary: `Bệnh nhân ghi nhận: ${selectedSymptoms.join(", ")}. Thời gian: ${duration}, Mức độ: ${severity}. Tiền sử: ${knownConditions || "Không có"}, Thuốc đang dùng: ${currentMeds || "Không có"}.`,
        questions_for_doctor: [
          "Triệu chứng này có phải là do bệnh lý nhiễm trùng hoặc viêm không?",
          "Tôi có cần dùng kháng sinh hay chỉ cần thuốc điều trị triệu chứng?",
          "Nếu sau bao lâu không đỡ thì tôi cần tái khám?",
        ],
        when_to_seek_immediate_care: [
          "Sốt cao liên tục > 39°C không hạ với Paracetamol",
          "Khó thở, thở nhanh nông hoặc đau ngực",
          "Nôn ói liên tục không uống được nước",
        ],
      });
    } finally {
      setIsEvaluating(false);
    }
  };

  const handleReset = () => {
    setSelectedRedFlags([]);
    setSelectedSymptoms([]);
    setDuration("1_3_days");
    setSeverity("moderate");
    setHasHighFever(false);
    setResult(null);
    setCurrentStep(1);
    setShowEmergencyModal(false);
    setAcknowledgedEmergency(false);
  };

  return (
    <div
      className="symptom-checker-flow mx-auto max-w-4xl space-y-6 pb-12"
      data-testid="care-symptom-checker-page"
    >
      {/* 1. Header */}
      <HealthPageHeader
        title={isEn ? "Symptom Check & Care Navigation" : "Kiểm tra triệu chứng & Định hướng chăm sóc"}
        subtitle={
          isEn
            ? "Stepwise clinical guidance, deterministic emergency safety floor (115 / ER), and clinician handoff summary."
            : "Đánh giá mức độ khẩn cấp, phát hiện dấu hiệu nguy hiểm (Cấp cứu 115) và tóm tắt thông tin bàn giao cho bác sĩ."
        }
        backHref="/care"
        backLabel={isEn ? "Back to Care" : "Quay lại Chăm sóc"}
        locale={uiLanguage}
      />

      {/* 2. Step Progress Indicator */}
      <div
        className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4"
        data-testid="symptom-check-progress"
      >
        <div className="grid grid-cols-4 gap-2 text-center text-xs font-bold">
          {[
            { step: 1, labelVi: "1. Triệu chứng", labelEn: "1. Symptoms" },
            { step: 2, labelVi: "2. Mức độ", labelEn: "2. Severity" },
            { step: 3, labelVi: "3. Yếu tố an toàn", labelEn: "3. Safety" },
            { step: 4, labelVi: "4. Kết luận", labelEn: "4. Result" },
          ].map(({ step, labelVi, labelEn }) => (
            <div
              key={step}
              className={`rounded-[var(--radius-md)] py-2 transition ${
                currentStep === step
                  ? "bg-[var(--brand-600)] text-[var(--button-primary-text)] font-extrabold"
                  : currentStep > step
                    ? "bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                    : "bg-[var(--surface-muted)] text-[var(--text-muted)]"
              }`}
            >
              <span>{isEn ? labelEn : labelVi}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 3. Red-Flag Emergency Override Section (Visible on Step 1) */}
      {currentStep === 1 && (
        <section
          className="rounded-[var(--radius-xl)] border-2 border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-4 sm:p-5 text-[var(--status-danger-text)] space-y-3 shadow-xs"
          data-testid="red-flag-section"
        >
          <div className="flex items-start gap-3">
            <Icon name="warning" size="1.35rem" className="mt-0.5 shrink-0 text-[var(--danger-500)]" />
            <div>
              <h2 className="text-sm sm:text-base font-extrabold leading-tight">
                {isEn ? "CRITICAL RED-FLAG WARNING SIGNS (EMERGENCY 115)" : "DẤU HIỆU CẢNH BÁO ĐỎ NGUY HIỂM (CẤP CỨU 115)"}
              </h2>
              <p className="mt-1 text-xs opacity-95 leading-relaxed">
                {isEn
                  ? "If you or someone nearby is experiencing any of these emergency signs, call 115 or go to the ER immediately:"
                  : "Nếu bạn hoặc người thân có bất kỳ dấu hiệu nguy kịch nào dưới đây, hãy gọi Cấp cứu 115 ngay:"}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
            {RED_FLAGS.map((flag) => {
              const isChecked = selectedRedFlags.includes(flag.id);
              return (
                <label
                  key={flag.id}
                  className={`flex items-start gap-2.5 rounded-[var(--radius-lg)] border p-2.5 cursor-pointer text-xs transition ${
                    isChecked
                      ? "border-[color:var(--danger-500)] bg-[var(--surface-panel)] text-[var(--status-danger-text)] ring-1 ring-[var(--danger-500)] font-bold"
                      : "border-[color:var(--status-danger-border)]/60 bg-[var(--surface-panel)]/80 text-[var(--text-primary)] hover:bg-[var(--surface-panel)]"
                  }`}
                  data-testid={`redflag-checkbox-${flag.id}`}
                >
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => toggleRedFlag(flag.id)}
                    className="mt-0.5 h-4 w-4 accent-[var(--danger-500)] cursor-pointer"
                  />
                  <div className="min-w-0 flex-1 leading-snug">
                    <span>{isEn ? flag.labelEn : flag.labelVi}</span>
                  </div>
                </label>
              );
            })}
          </div>
        </section>
      )}

      {/* STEP 1: Primary Symptoms Selection */}
      {currentStep === 1 && (
        <section
          className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 sm:p-6 space-y-5"
          data-testid="symptom-step-1"
        >
          <div>
            <h2 className="text-base font-bold text-[var(--text-primary)]">
              {isEn ? "Select Primary Symptoms" : "Chọn các triệu chứng bạn đang gặp phải"}
            </h2>
            <p className="text-xs text-[var(--text-secondary)] mt-1">
              {isEn
                ? "Choose common symptoms below or type a specific symptom description."
                : "Chọn các triệu chứng phổ biến dưới đây hoặc tự nhập triệu chứng cụ thể."}
            </p>
          </div>

          {/* Search or Custom input */}
          <div className="flex gap-2">
            <Field
              value={customSymptomInput}
              onChange={(e) => setCustomSymptomInput(e.target.value)}
              placeholder={isEn ? "Type another symptom (e.g. Earache, Numbness)..." : "Nhập triệu chứng khác (VD: Đau tai, Tê bì chân tay)..."}
              wrapperClassName="flex-1"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleAddCustomSymptom();
                }
              }}
            />
            <Button type="button" variant="secondary" onClick={handleAddCustomSymptom} icon="plus">
              {isEn ? "Add" : "Thêm"}
            </Button>
          </div>

          {/* Selected Symptoms Chips */}
          {selectedSymptoms.length > 0 && (
            <div className="space-y-1.5 rounded-[var(--radius-lg)] bg-[var(--surface-muted)]/50 p-3">
              <span className="text-xs font-bold text-[var(--text-brand)] block">
                {isEn ? "Selected Symptoms:" : "Triệu chứng đã chọn:"}
              </span>
              <div className="flex flex-wrap gap-1.5">
                {selectedSymptoms.map((s) => (
                  <span
                    key={s}
                    className="inline-flex items-center gap-1 rounded-[var(--radius-pill)] bg-[var(--brand-600)] px-3 py-1 text-xs font-semibold text-[var(--button-primary-text)] shadow-xs"
                  >
                    <span>{s}</span>
                    <button
                      type="button"
                      onClick={() => toggleSymptom(s)}
                      className="hover:opacity-80"
                      aria-label={`Remove ${s}`}
                    >
                      <Icon name="close" size="0.8rem" />
                    </button>
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Common Symptoms Categories */}
          <div className="space-y-4 pt-1">
            {COMMON_SYMPTOMS_VI.map((cat, idx) => (
              <div key={idx} className="space-y-1.5">
                <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                  {cat.category}
                </span>
                <div className="flex flex-wrap gap-2">
                  {cat.items.map((item) => {
                    const isSelected = selectedSymptoms.includes(item);
                    return (
                      <button
                        key={item}
                        type="button"
                        onClick={() => toggleSymptom(item)}
                        className={`rounded-[var(--radius-lg)] border px-3 py-1.5 text-xs font-medium transition ${
                          isSelected
                            ? "border-[color:var(--brand-600)] bg-[var(--brand-600)] text-[var(--button-primary-text)] font-bold shadow-xs"
                            : "border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 text-[var(--text-primary)] hover:border-[color:var(--brand-500)]"
                        }`}
                        data-testid={`symptom-chip-${item}`}
                      >
                        {isSelected ? "✓ " : "+ "}{item}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          <div className="flex justify-end pt-4 border-t border-[color:var(--shell-border)]/50">
            <Button
              onClick={() => setCurrentStep(2)}
              disabled={selectedSymptoms.length === 0 && selectedRedFlags.length === 0}
              icon="arrow-right"
            >
              {isEn ? "Next: Severity & Duration" : "Tiếp theo: Mức độ & Thời gian"}
            </Button>
          </div>
        </section>
      )}

      {/* STEP 2: Duration, Severity & Onset */}
      {currentStep === 2 && (
        <section
          className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 sm:p-6 space-y-5"
          data-testid="symptom-step-2"
        >
          <div>
            <h2 className="text-base font-bold text-[var(--text-primary)]">
              {isEn ? "Duration & Severity Level" : "Thời gian kéo dài & Mức độ khó chịu"}
            </h2>
            <p className="text-xs text-[var(--text-secondary)] mt-1">
              {isEn
                ? "Help us assess whether this represents an acute change or chronic course."
                : "Giúp xác định diễn tiến cấp tính hay mạn tính để điều hướng chăm sóc chính xác."}
            </p>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-[var(--text-primary)] mb-1.5">
                {isEn ? "How long have you had these symptoms?" : "Triệu chứng bắt đầu xuất hiện từ khi nào?"}
              </label>
              <Select value={duration} onChange={(e) => setDuration(e.target.value)}>
                <option value="under_24h">{isEn ? "Less than 24 hours" : "Dưới 24 giờ (Vừa mới xuất hiện)"}</option>
                <option value="1_3_days">{isEn ? "1 to 3 days" : "1 đến 3 ngày"}</option>
                <option value="4_7_days">{isEn ? "4 to 7 days" : "4 đến 7 ngày (Gần 1 tuần)"}</option>
                <option value="more_than_week">{isEn ? "1 to 4 weeks" : "Trên 1 tuần đến 1 tháng"}</option>
                <option value="chronic">{isEn ? "Chronic (Over 1 month)" : "Mạn tính (Kéo dài trên 1 tháng)"}</option>
              </Select>
            </div>

            <div>
              <label className="block text-xs font-bold text-[var(--text-primary)] mb-1.5">
                {isEn ? "Symptom Severity Level" : "Mức độ đau / khó chịu"}
              </label>
              <div className="grid grid-cols-3 gap-2.5">
                {[
                  { key: "mild", labelVi: "Nhẹ (1-3)", labelEn: "Mild", descVi: "Không ảnh hưởng sinh hoạt", descEn: "Minor discomfort" },
                  { key: "moderate", labelVi: "Vừa (4-6)", labelEn: "Moderate", descVi: "Khó chịu, gián đoạn công việc", descEn: "Disrupts normal tasks" },
                  { key: "severe", labelVi: "Nặng (7-10)", labelEn: "Severe", descVi: "Đau dữ dội, không thể làm việc", descEn: "Intense, debilitating" },
                ].map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => setSeverity(item.key as any)}
                    className={`rounded-[var(--radius-lg)] border p-3 text-left transition ${
                      severity === item.key
                        ? "border-[color:var(--brand-600)] bg-[var(--surface-brand-soft)] ring-1 ring-[var(--brand-500)]"
                        : "border-[color:var(--shell-border)] bg-[var(--surface-muted)]/30 hover:bg-[var(--surface-muted)]"
                    }`}
                  >
                    <span className="font-bold text-xs sm:text-sm block text-[var(--text-primary)]">
                      {isEn ? item.labelEn : item.labelVi}
                    </span>
                    <span className="text-[11px] text-[var(--text-muted)] mt-0.5 block">
                      {isEn ? item.descEn : item.descVi}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-[var(--text-primary)] mb-1.5">
                {isEn ? "Onset Pattern" : "Kiểu khởi phát triệu chứng"}
              </label>
              <Select value={onset} onChange={(e) => setOnset(e.target.value)}>
                <option value="gradual">{isEn ? "Gradual onset (worsening over days)" : "Từ từ tăng dần qua nhiều ngày"}</option>
                <option value="sudden">{isEn ? "Sudden sudden onset (within minutes/hours)" : "Đột ngột xuất hiện trong vòng vài phút / vài giờ"}</option>
                <option value="intermittent">{isEn ? "Intermittent / recurrent episodes" : "Từng đợt ngắt quãng (lúc bị lúc không)"}</option>
              </Select>
            </div>
          </div>

          <div className="flex justify-between pt-4 border-t border-[color:var(--shell-border)]/50">
            <Button variant="secondary" onClick={() => setCurrentStep(1)} icon="arrow-left">
              {isEn ? "Back" : "Quay lại"}
            </Button>
            <Button onClick={() => setCurrentStep(3)} icon="arrow-right">
              {isEn ? "Next: Safety & Context" : "Tiếp theo: Tiền sử & An toàn"}
            </Button>
          </div>
        </section>
      )}

      {/* STEP 3: Context, Medications & Safety Check */}
      {currentStep === 3 && (
        <section
          className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 sm:p-6 space-y-4"
          data-testid="symptom-step-3"
        >
          <div>
            <h2 className="text-base font-bold text-[var(--text-primary)]">
              {isEn ? "Health Context & Safety Factors" : "Bối cảnh sức khỏe & Yếu tố an toàn"}
            </h2>
            <p className="text-xs text-[var(--text-secondary)] mt-1">
              {isEn
                ? "Underlying chronic conditions or concurrent medications can change clinical urgency."
                : "Bệnh nền mạn tính hoặc thuốc đang sử dụng có thể ảnh hưởng đến mức độ ưu tiên xử trí."}
            </p>
          </div>

          <div className="space-y-4">
            <label className="flex items-center gap-3 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-3.5 cursor-pointer">
              <input
                type="checkbox"
                checked={hasHighFever}
                onChange={(e) => setHasHighFever(e.target.checked)}
                className="h-4 w-4 accent-[var(--brand-600)]"
              />
              <div>
                <span className="font-bold text-xs sm:text-sm text-[var(--text-primary)] block">
                  {isEn ? "Currently have high fever (≥ 38.5°C / 101.3°F)?" : "Đang bị sốt cao (≥ 38.5°C)?"}
                </span>
                <span className="text-[11px] text-[var(--text-muted)]">
                  {isEn ? "High fever requires closer medical monitoring" : "Sốt cao cần được theo dõi sát nguy cơ nhiễm trùng"}
                </span>
              </div>
            </label>

            <Field
              label={isEn ? "Known Chronic Conditions" : "Bệnh nền đang điều trị"}
              value={knownConditions}
              onChange={(e) => setKnownConditions(e.target.value)}
              placeholder="VD: Tăng huyết áp, Đái tháo đường, Hen suyễn, Dạ dày..."
            />

            <Field
              label={isEn ? "Current Medications & Supplements" : "Thuốc và thực phẩm chức năng đang dùng"}
              value={currentMeds}
              onChange={(e) => setCurrentMeds(e.target.value)}
              placeholder="VD: Amlodipine 5mg, Metformin, Thuốc giảm đau..."
            />

            <Textarea
              label={isEn ? "Additional Notes / Symptoms Details" : "Ghi chú thêm về triệu chứng"}
              value={userNotes}
              onChange={(e) => setUserNotes(e.target.value)}
              placeholder="Mô tả cụ thể thời điểm đau tăng, yếu tố làm dịu hoặc lo lắng của bạn..."
              className="min-h-20"
            />
          </div>

          <div className="flex justify-between pt-4 border-t border-[color:var(--shell-border)]/50">
            <Button variant="secondary" onClick={() => setCurrentStep(2)} icon="arrow-left">
              {isEn ? "Back" : "Quay lại"}
            </Button>
            <Button onClick={handleCalculateResult} icon="check">
              {isEn ? "Get Triage Assessment" : "Xem kết quả đánh giá"}
            </Button>
          </div>
        </section>
      )}

      {/* STEP 4: Urgency Result Card & Clinician Handoff */}
      {currentStep === 4 && result && (
        <section
          className="space-y-6"
          data-testid="symptom-check-result"
        >
          {/* Main Urgency Result Card */}
          <div
            className={`rounded-[var(--radius-xl)] border-2 p-5 sm:p-6 shadow-sm space-y-4 ${
              result.is_red_flag_emergency
                ? "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]"
                : result.urgency === "urgent"
                  ? "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]"
                  : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-primary)]"
            }`}
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-current/20 pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <Badge tone={getUrgencyBadgeTone(result.urgency)}>
                    {result.urgency.toUpperCase()}
                  </Badge>
                  {result.is_red_flag_emergency && (
                    <span className="font-extrabold text-xs text-[var(--danger-500)] flex items-center gap-1">
                      <Icon name="warning" size="0.9rem" />
                      <span>{isEn ? "RED-FLAG OVERRIDE" : "CẢNH BÁO ĐỎ KHẨN CẤP"}</span>
                    </span>
                  )}
                </div>
                <h2 className="mt-2 text-lg sm:text-xl font-extrabold">
                  {result.title}
                </h2>
              </div>

              {result.is_red_flag_emergency && (
                <a
                  href="tel:115"
                  className="inline-flex min-h-[var(--touch-target-min)] items-center justify-center gap-2 rounded-[var(--radius-lg)] bg-[var(--danger-500)] px-5 py-2.5 text-sm font-extrabold text-white shadow-md hover:opacity-90 transition self-start sm:self-center"
                >
                  <Icon name="emergency" size="1.2rem" />
                  <span>{isEn ? "Call 115 Emergency" : "GỌI CẤP CỨU 115 NGAY"}</span>
                </a>
              )}
            </div>

            <p className="text-xs sm:text-sm leading-relaxed opacity-95">
              {result.explanation}
            </p>

            <div className="rounded-[var(--radius-lg)] bg-black/5 dark:bg-white/5 p-3.5 space-y-1">
              <span className="text-xs font-bold uppercase tracking-wider block">
                {isEn ? "Care Navigation Guidance:" : "Hướng dẫn hành động:"}
              </span>
              <p className="text-xs sm:text-sm font-semibold">
                {result.care_navigation_guidance}
              </p>
            </div>

            {/* Recommended Actions */}
            {result.recommended_actions.length > 0 && (
              <div className="space-y-1.5 pt-1">
                <span className="text-xs font-bold uppercase tracking-wider">
                  {isEn ? "Recommended Steps:" : "Các bước nên thực hiện:"}
                </span>
                <ul className="space-y-1 text-xs sm:text-sm list-disc pl-4">
                  {result.recommended_actions.map((act, i) => (
                    <li key={i}>{act}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Clinician Handoff Summary Card */}
          <div className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 space-y-4 shadow-sm">
            <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-3">
              <div className="flex items-center gap-2 text-[var(--text-brand)]">
                <Icon name="clinical-notes" size="1.15rem" />
                <h3 className="font-bold text-sm text-[var(--text-primary)]">
                  {isEn ? "Clinician Handoff Summary" : "Tóm tắt bàn giao cho Bác sĩ"}
                </h3>
              </div>
              <Badge tone="neutral">{isEn ? "Ready for Doctor" : "Sẵn sàng mang đi khám"}</Badge>
            </div>

            <p className="text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed bg-[var(--surface-muted)]/40 rounded-[var(--radius-lg)] p-3 border border-[color:var(--shell-border)]/50 font-mono">
              {result.clinician_handoff_summary}
            </p>

            {/* Doctor questions */}
            {result.questions_for_doctor.length > 0 && (
              <div className="space-y-2 pt-2">
                <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                  {isEn ? "Questions to Ask Doctor / Pharmacist:" : "Câu hỏi gợi ý khi trao đổi với Bác sĩ / Dược sĩ:"}
                </span>
                <ul className="space-y-1 text-xs text-[var(--text-secondary)]">
                  {result.questions_for_doctor.map((q, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="mt-1 h-1.5 w-1.5 rounded-full bg-[var(--brand-500)]" />
                      <span>{q}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Red flags warning signs to watch out */}
            {result.when_to_seek_immediate_care && result.when_to_seek_immediate_care.length > 0 && (
              <div className="space-y-1.5 rounded-[var(--radius-lg)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] p-3 text-[var(--status-warn-text)] text-xs">
                <span className="font-bold flex items-center gap-1.5">
                  <Icon name="warning" size="0.95rem" />
                  <span>{isEn ? "When to seek immediate emergency care:" : "Đến bệnh viện ngay nếu xuất hiện thêm:"}</span>
                </span>
                <ul className="space-y-0.5 list-disc pl-4 opacity-95">
                  {result.when_to_seek_immediate_care.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Action Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
            <Button variant="secondary" onClick={handleReset} icon="refresh">
              {isEn ? "Start New Symptom Check" : "Kiểm tra triệu chứng khác"}
            </Button>

            <div className="flex flex-wrap gap-2">
              <Button as="link" href="/care/prepare" icon="clinical-notes">
                {isEn ? "Prepare for Consultation" : "Chuẩn bị đi khám"}
              </Button>
              <Button as="link" href="/ask" variant="secondary" icon="chat">
                {isEn ? "Ask CLARA More" : "Hỏi thêm CLARA"}
              </Button>
            </div>
          </div>
        </section>
      )}

      {/* Deterministic Emergency Alert Modal */}
      {showEmergencyModal && (
        <Modal
          open={showEmergencyModal}
          onClose={() => setShowEmergencyModal(false)}
          title={isEn ? "CRITICAL EMERGENCY ALERT" : "CẢNH BÁO CẤP CỨU KHẨN CẤP"}
          description={
            isEn
              ? "A life-threatening red-flag symptom was selected. Emergency evaluation is required."
              : "Phát hiện dấu hiệu cảnh báo đỏ nguy hiểm tính mạng. Cần cấp cứu y tế ngay lập tức."
          }
          role="alertdialog"
          size="md"
        >
          <div className="space-y-4 py-2" data-testid="emergency-modal-content">
            <div className="rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-4 text-[var(--status-danger-text)] text-xs sm:text-sm space-y-2">
              <p className="font-extrabold text-base flex items-center gap-1.5">
                <Icon name="emergency" size="1.3rem" className="text-[var(--danger-500)]" />
                <span>{isEn ? "Call 115 or Go to ER Now" : "Gọi cấp cứu 115 hoặc tới phòng Cấp cứu ngay"}</span>
              </p>
              <p className="leading-relaxed opacity-95">
                {isEn
                  ? "Symptoms like crushing chest pain, stroke signs (FAST), severe difficulty breathing, or coughing blood require immediate hospital care."
                  : "Các triệu chứng đau ngực dữ dội, dấu hiệu đột quỵ, khó thở nặng hoặc ho ra máu cần can thiệp y tế khẩn cấp tại phòng cấp cứu bệnh viện."}
              </p>
            </div>

            <div className="space-y-2 text-xs text-[var(--text-secondary)]">
              <p className="font-semibold text-[var(--text-primary)]">
                {isEn ? "Key emergency instructions:" : "Hướng dẫn quan trọng:"}
              </p>
              <ul className="space-y-1 list-disc pl-4">
                <li>{isEn ? "Call 115 (Emergency Services in Vietnam)" : "Gọi số 115 (Cấp cứu tại Việt Nam)"}</li>
                <li>{isEn ? "Do NOT drive yourself — ask family or ambulance" : "KHÔNG tự lái xe — nhờ người thân hoặc chờ xe cứu thương"}</li>
                <li>{isEn ? "Stay calm, sit or lie down in a comfortable position" : "Giữ bình tĩnh, ngồi hoặc nằm ở tư thế thoải mái"}</li>
              </ul>
            </div>

            <div className="pt-3 flex flex-col sm:flex-row gap-2 justify-end">
              <a
                href="tel:115"
                className="inline-flex min-h-[var(--touch-target-min)] items-center justify-center gap-2 rounded-[var(--radius-md)] bg-[var(--danger-500)] px-4 py-2 text-xs sm:text-sm font-extrabold text-white shadow-sm hover:opacity-90 transition text-center"
              >
                <Icon name="emergency" size="1.1rem" />
                <span>{isEn ? "Call 115 Immediately" : "Gọi 115 ngay"}</span>
              </a>

              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setAcknowledgedEmergency(true);
                  setShowEmergencyModal(false);
                }}
              >
                {isEn ? "I Acknowledge, Continue" : "Tôi đã hiểu, Tiếp tục xem"}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

export default function SymptomCheckerPage() {
  return (
    <Suspense fallback={null}>
      <SymptomCheckerContent />
    </Suspense>
  );
}
