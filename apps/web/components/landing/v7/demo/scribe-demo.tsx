"use client";

import React, { useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { CaptureWave } from "../artwork/capture-wave";

export type ScribeStep = 1 | 2 | 3 | 4 | 5;

export function ScribeDemo() {
  const { language, isReducedMotion } = useMotionTier();
  const copy = LANDING_COPY_V7[language].scribe;
  const [currentStep, setCurrentStep] = useState<ScribeStep>(4); // Default to SOAP draft for richest initial view

  const stepLabels: Record<ScribeStep, { number: string; title: string; subtitle: string }> = {
    1: {
      number: "01",
      title: copy.states.consent.title,
      subtitle: language === "vi" ? "Đồng thuận Y tế" : "Patient Consent",
    },
    2: {
      number: "02",
      title: copy.states.recording.title,
      subtitle: language === "vi" ? "Thu âm Hội thoại" : "Ambient Recording",
    },
    3: {
      number: "03",
      title: copy.states.transcript.title,
      subtitle: language === "vi" ? "Biên dịch Y khoa" : "Clinical NLP",
    },
    4: {
      number: "04",
      title: copy.states.soap.title,
      subtitle: language === "vi" ? "Dự thảo SOAP" : "SOAP Draft",
    },
    5: {
      number: "05",
      title: copy.states.review.title,
      subtitle: language === "vi" ? "Ký duyệt Bác sĩ" : "Physician Review",
    },
  };

  return (
    <div
      data-testid="scribe-demo"
      className="clara-product-surface relative w-full overflow-hidden p-6 sm:p-8 lg:p-10 transition-all duration-300"
    >
      {/* Scribe Header & 5-Step Transformation Stepper */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#E3E8EF] pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-bold text-[#162033]">
              {language === "vi" ? "CLARA Ambient Clinical Scribe" : "CLARA Ambient Clinical Scribe"}
            </h3>
            <span className="rounded-full bg-[#ECFDF8] px-2.5 py-0.5 text-xs font-semibold text-[#14A88D] border border-[#14A88D]/20">
              Bilingual VN/EN • Zero-CoT
            </span>
          </div>
          <p className="text-xs text-[#6D7A8E] mt-0.5">
            {language === "vi"
              ? "Quy trình chuyển đổi 5 bước từ hội thoại trực tiếp đến bệnh án SOAP đã xác nhận"
              : "5-step pipeline transforming raw doctor-patient dialogue into structured SOAP clinical notes"}
          </p>
        </div>

        {/* 5-Step Progress Indicators */}
        <div
          className="flex items-center gap-1.5 rounded-2xl bg-[#F1F5F9] p-1 border border-[#E3E8EF]"
          role="tablist"
          aria-label={language === "vi" ? "Các bước tiến trình Scribe" : "Scribe pipeline steps"}
        >
          {([1, 2, 3, 4, 5] as const).map((stepNum) => {
            const isCurrent = currentStep === stepNum;
            const isPassed = currentStep > stepNum;
            return (
              <button
                key={stepNum}
                type="button"
                role="tab"
                id={`scribe-step-tab-${stepNum}`}
                aria-selected={isCurrent}
                aria-controls={`scribe-step-panel-${stepNum}`}
                onClick={() => setCurrentStep(stepNum)}
                className={`flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-bold transition-all clara-focus-ring ${
                  isCurrent
                    ? "bg-[#14A88D] text-white shadow-sm scale-[1.02]"
                    : isPassed
                    ? "bg-white text-[#14A88D] border border-[#14A88D]/30"
                    : "bg-transparent text-[#6D7A8E] hover:text-[#162033] hover:bg-white/60"
                }`}
              >
                <span>0{stepNum}</span>
                <span className="hidden sm:inline text-[11px] font-medium">
                  {stepLabels[stepNum].subtitle}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Transforming Workspace Body */}
      <div className="mt-6">
        {/* Step 1: Consent */}
        {currentStep === 1 && (
          <div
            id="scribe-step-panel-1"
            role="tabpanel"
            aria-labelledby="scribe-step-tab-1"
            className="rounded-2xl bg-white p-6 border border-[#E3E8EF] space-y-4 animate-fadeIn"
          >
            <div className="flex items-center justify-between border-b border-[#E3E8EF]/80 pb-3">
              <span className="text-xs font-bold uppercase tracking-wider text-[#14A88D]">
                Bước 01 • {copy.states.consent.title}
              </span>
              <span className="rounded-full bg-[#ECFDF8] px-2.5 py-0.5 text-xs font-bold text-[#14A88D] border border-[#14A88D]/20">
                {language === "vi" ? "Đã cấp phép" : "Consent Verified"}
              </span>
            </div>

            <p className="text-sm font-semibold text-[#162033]">{copy.states.consent.desc}</p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 text-xs">
              <div className="rounded-xl bg-[#ECFDF8] p-4 border border-[#14A88D]/20 space-y-1">
                <div className="flex items-center gap-2 font-bold text-[#14A88D]">
                  <span>✓</span>
                  <span>{language === "vi" ? "Đồng thuận Ghi âm Bệnh nhân" : "Patient Audio Consent"}</span>
                </div>
                <p className="text-[#48566A] text-[11px]">
                  {language === "vi"
                    ? "Bệnh nhân đã ký xác nhận qua biểu mẫu điện tử trước khi bắt đầu buổi khám."
                    : "Patient authenticated consent via electronic tablet signature prior to intake."}
                </p>
              </div>

              <div className="rounded-xl bg-[#EFF7FF] p-4 border border-[#0B6FD8]/20 space-y-1">
                <div className="flex items-center gap-2 font-bold text-[#0B6FD8]">
                  <span>🔒</span>
                  <span>{language === "vi" ? "Mã hóa Đầu cuối Zero-CoT" : "Zero-CoT Security Guard"}</span>
                </div>
                <p className="text-[#48566A] text-[11px]">
                  {language === "vi"
                    ? "Dữ liệu âm thanh được bảo vệ, không sử dụng để huấn luyện mô hình khi chưa được phép."
                    : "Audio stream is encrypted in transit and at rest with strict no-training guarantees."}
                </p>
              </div>
            </div>

            <div className="pt-2 flex justify-end">
              <button
                type="button"
                onClick={() => setCurrentStep(2)}
                className="rounded-xl bg-[#14A88D] px-4 py-2 text-xs font-bold text-white hover:bg-[#0E856F] transition-all clara-focus-ring"
              >
                {language === "vi" ? "Bắt đầu Ghi âm →" : "Start Recording →"}
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Recording with CaptureWave Artwork */}
        {currentStep === 2 && (
          <div
            id="scribe-step-panel-2"
            role="tabpanel"
            aria-labelledby="scribe-step-tab-2"
            className="rounded-2xl bg-white p-6 border border-[#E3E8EF] space-y-4 animate-fadeIn"
          >
            <div className="flex items-center justify-between border-b border-[#E3E8EF]/80 pb-3">
              <span className="text-xs font-bold uppercase tracking-wider text-rose-600">
                Bước 02 • {copy.states.recording.title}
              </span>
              <span className="inline-flex items-center gap-2 rounded-full bg-rose-50 px-3 py-1 text-xs font-bold text-rose-700 border border-rose-200">
                <span
                  className={`h-2 w-2 rounded-full bg-rose-600 ${
                    isReducedMotion ? "" : "animate-ping"
                  }`}
                />
                {copy.states.recording.timer}
              </span>
            </div>

            <p className="text-sm text-[#48566A]">{copy.states.recording.desc}</p>

            {/* Integrated Vector CaptureWave Artwork */}
            <CaptureWave
              state="recording"
              isRecording={!isReducedMotion}
              className="my-2"
            />

            <div className="flex items-center justify-between pt-2">
              <span className="text-xs text-[#6D7A8E]">
                {language === "vi"
                  ? "Đang khử ồn môi trường phòng khám & tách giọng bác sĩ/bệnh nhân..."
                  : "Active background noise filtering and speaker diarization in progress..."}
              </span>
              <button
                type="button"
                onClick={() => setCurrentStep(3)}
                className="rounded-xl bg-[#0B6FD8] px-4 py-2 text-xs font-bold text-white hover:bg-[#084C99] transition-all clara-focus-ring"
              >
                {language === "vi" ? "Chuyển thành Văn bản →" : "Generate Transcript →"}
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Bilingual Medical NLP Transcript */}
        {currentStep === 3 && (
          <div
            id="scribe-step-panel-3"
            role="tabpanel"
            aria-labelledby="scribe-step-tab-3"
            className="rounded-2xl bg-white p-6 border border-[#E3E8EF] space-y-4 animate-fadeIn"
          >
            <div className="flex items-center justify-between border-b border-[#E3E8EF]/80 pb-3">
              <span className="text-xs font-bold uppercase tracking-wider text-[#0B6FD8]">
                Bước 03 • {copy.states.transcript.title}
              </span>
              <span className="rounded-full bg-[#EFF7FF] px-2.5 py-0.5 text-xs font-bold text-[#0B6FD8] border border-[#0B6FD8]/20">
                {language === "vi" ? "Nhận diện Thực thể Y khoa" : "Medical NER Extraction"}
              </span>
            </div>

            <p className="text-xs text-[#6D7A8E]">{copy.states.transcript.desc}</p>

            {/* Formatted Transcript Dialogue */}
            <div className="rounded-xl bg-[#F8FAFD] p-4 sm:p-5 border border-[#E3E8EF] space-y-3 font-sans text-xs text-[#162033] leading-relaxed">
              <div className="flex items-start gap-2.5">
                <span className="rounded-md bg-[#EFF7FF] px-2 py-0.5 font-bold text-[#0B6FD8] shrink-0 text-[11px]">
                  {language === "vi" ? "Bác sĩ" : "Doctor"}
                </span>
                <p className="text-[#162033]">
                  {language === "vi"
                    ? "Bác thấy cơn đau tức ngực xuất hiện lúc nào và kéo dài bao lâu?"
                    : "When do you notice the chest tightness, and how long does each episode last?"}
                </p>
              </div>

              <div className="flex items-start gap-2.5">
                <span className="rounded-md bg-[#ECFDF8] px-2 py-0.5 font-bold text-[#14A88D] shrink-0 text-[11px]">
                  {language === "vi" ? "Bệnh nhân" : "Patient"}
                </span>
                <p className="text-[#48566A]">
                  {language === "vi"
                    ? "Dạ thường là lúc tôi leo cầu thang lên tầng 2 hoặc xách đồ nặng. Cảm giác đau thắt đè nặng vùng ngực trái khoảng 3 phút, khi ngồi nghỉ thì dịu bớt."
                    : "Usually when climbing stairs to the second floor or lifting groceries. It feels like a heavy squeezing pressure over my left chest for about 3 minutes, which eases after resting."}
                </p>
              </div>

              <div className="flex items-start gap-2.5">
                <span className="rounded-md bg-[#EFF7FF] px-2 py-0.5 font-bold text-[#0B6FD8] shrink-0 text-[11px]">
                  {language === "vi" ? "Bác sĩ" : "Doctor"}
                </span>
                <p className="text-[#162033]">
                  {language === "vi"
                    ? "Huyết áp đo tại phòng khám hiện tại là 135/85 mmHg, tim đều. Tôi sẽ chỉ định điện tâm đồ và siêu âm tim để tầm soát mạch vành."
                    : "In-clinic blood pressure is 135/85 mmHg with regular heart sounds. I will order an ECG and Doppler echocardiogram to evaluate coronary perfusion."}
                </p>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2">
              <span className="text-xs text-[#6D7A8E]">
                {language === "vi" ? "Chuẩn hóa thuật ngữ SNOMED CT / ICD-10" : "Normalized against SNOMED CT & ICD-10"}
              </span>
              <button
                type="button"
                onClick={() => setCurrentStep(4)}
                className="rounded-xl bg-[#14A88D] px-4 py-2 text-xs font-bold text-white hover:bg-[#0E856F] transition-all clara-focus-ring"
              >
                {language === "vi" ? "Trích xuất Dự thảo SOAP →" : "Synthesize SOAP Draft →"}
              </button>
            </div>
          </div>
        )}

        {/* Step 4: Structured SOAP Draft */}
        {currentStep === 4 && (
          <div
            id="scribe-step-panel-4"
            role="tabpanel"
            aria-labelledby="scribe-step-tab-4"
            className="rounded-2xl bg-white p-6 border border-[#E3E8EF] space-y-4 animate-fadeIn"
          >
            <div className="flex items-center justify-between border-b border-[#E3E8EF] pb-3">
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-[#14A88D]">
                  Bước 04 • {copy.states.soap.title}
                </span>
                <p className="text-xs text-[#6D7A8E] mt-0.5">{copy.states.soap.desc}</p>
              </div>
              <span className="rounded-md bg-[#EFF7FF] px-2.5 py-1 text-xs font-bold text-[#0B6FD8] border border-[#0B6FD8]/20">
                {language === "vi" ? "Bệnh án cấu trúc SOAP" : "Structured SOAP Protocol"}
              </span>
            </div>

            {/* 4-Quadrant SOAP Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 text-xs">
              {/* S: Subjective */}
              <div className="rounded-xl bg-[#F8FAFD] p-4 border border-[#E3E8EF] space-y-1.5 shadow-xs">
                <div className="flex items-center justify-between">
                  <strong className="text-[#0B6FD8] font-bold text-xs uppercase tracking-wide">
                    S — Subjective ({language === "vi" ? "Chủ quan" : "History of Present Illness"})
                  </strong>
                  <span className="text-[10px] font-semibold text-[#0B6FD8] bg-[#EFF7FF] px-2 py-0.5 rounded-full">
                    Triệu chứng cơ năng
                  </span>
                </div>
                <p className="text-[#162033] font-medium leading-relaxed">{copy.states.soap.s}</p>
              </div>

              {/* O: Objective */}
              <div className="rounded-xl bg-[#F8FAFD] p-4 border border-[#E3E8EF] space-y-1.5 shadow-xs">
                <div className="flex items-center justify-between">
                  <strong className="text-[#14A88D] font-bold text-xs uppercase tracking-wide">
                    O — Objective ({language === "vi" ? "Khách quan" : "Clinical Examination"})
                  </strong>
                  <span className="text-[10px] font-semibold text-[#14A88D] bg-[#ECFDF8] px-2 py-0.5 rounded-full">
                    Thực thể & Sinh hiệu
                  </span>
                </div>
                <p className="text-[#162033] font-medium leading-relaxed">{copy.states.soap.o}</p>
              </div>

              {/* A: Assessment */}
              <div className="rounded-xl bg-[#F8FAFD] p-4 border border-[#E3E8EF] space-y-1.5 shadow-xs">
                <div className="flex items-center justify-between">
                  <strong className="text-[#8B7CF6] font-bold text-xs uppercase tracking-wide">
                    A — Assessment ({language === "vi" ? "Đánh giá sơ bộ" : "Clinical Impression"})
                  </strong>
                  <span className="text-[10px] font-semibold text-[#8B7CF6] bg-[#F5F3FF] px-2 py-0.5 rounded-full">
                    Chẩn đoán sơ bộ
                  </span>
                </div>
                <p className="text-[#162033] font-medium leading-relaxed">{copy.states.soap.a}</p>
              </div>

              {/* P: Plan */}
              <div className="rounded-xl bg-[#F8FAFD] p-4 border border-[#E3E8EF] space-y-1.5 shadow-xs">
                <div className="flex items-center justify-between">
                  <strong className="text-amber-700 font-bold text-xs uppercase tracking-wide">
                    P — Plan ({language === "vi" ? "Kế hoạch xử trí" : "Diagnostic & Care Plan"})
                  </strong>
                  <span className="text-[10px] font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full">
                    Chỉ định & Đơn thuốc
                  </span>
                </div>
                <p className="text-[#162033] font-medium leading-relaxed">{copy.states.soap.p}</p>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2">
              <span className="text-xs text-[#6D7A8E]">
                {language === "vi"
                  ? "Bản nháp tự động — Chờ Bác sĩ điều trị kiểm tra & ký duyệt"
                  : "Automated draft — Pending Attending Physician review & signature"}
              </span>
              <button
                type="button"
                onClick={() => setCurrentStep(5)}
                className="rounded-xl bg-[#14A88D] px-4 py-2 text-xs font-bold text-white hover:bg-[#0E856F] transition-all clara-focus-ring"
              >
                {language === "vi" ? "Tiến hành Ký duyệt →" : "Proceed to Sign-Off →"}
              </button>
            </div>
          </div>
        )}

        {/* Step 5: Review & Sign-Off by Attending Physician */}
        {currentStep === 5 && (
          <div
            id="scribe-step-panel-5"
            role="tabpanel"
            aria-labelledby="scribe-step-tab-5"
            className="rounded-2xl bg-white p-6 border border-[#E3E8EF] space-y-4 animate-fadeIn"
          >
            <div className="flex items-center justify-between border-b border-[#E3E8EF] pb-3">
              <span className="text-xs font-bold uppercase tracking-wider text-[#162033]">
                Bước 05 • {copy.states.review.title}
              </span>
              <span className="rounded-full bg-[#ECFDF8] px-3 py-1 text-xs font-bold text-[#14A88D] border border-[#14A88D]/20">
                {copy.states.review.status}
              </span>
            </div>

            <p className="text-xs sm:text-sm text-[#48566A]">{copy.states.review.desc}</p>

            <div className="rounded-xl bg-[#F8FAFD] p-4 border border-[#E3E8EF] space-y-2 text-xs">
              <div className="flex items-center justify-between text-[#6D7A8E] text-[11px]">
                <span>{language === "vi" ? "Bác sĩ phụ trách:" : "Attending Clinician:"} <strong className="text-[#162033]">BS. CKI Nguyễn Minh Tuấn</strong></span>
                <span>{language === "vi" ? "Mã chứng thư số:" : "Digital Key ID:"} <strong className="font-mono text-[#0B6FD8]">CA-MED-9948-VN</strong></span>
              </div>
              <p className="text-[#48566A] italic">
                {language === "vi"
                  ? "«Tôi xác nhận đã kiểm tra nội dung bệnh án SOAP, đối chiếu triệu chứng thực tế của bệnh nhân và đồng ý lưu trữ vào hồ sơ bệnh án điện tử (EMR).»"
                  : "«I certify that I have reviewed this SOAP clinical note against direct patient examination and authorize its synchronization into the electronic medical record (EMR).»"}
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3 pt-2">
              <button
                type="button"
                className="rounded-xl bg-[#14A88D] px-5 py-2.5 text-xs font-bold text-white hover:bg-[#0E856F] transition-all clara-focus-ring shadow-sm"
              >
                {language === "vi" ? "Ký số & Đồng bộ EMR" : "Sign Digitally & Commit to EMR"}
              </button>
              <button
                type="button"
                onClick={() => setCurrentStep(4)}
                className="rounded-xl bg-[#F1F5F9] px-4 py-2.5 text-xs font-bold text-[#48566A] hover:bg-[#E3E8EF] transition-all clara-focus-ring"
              >
                {language === "vi" ? "Chỉnh sửa bản nháp" : "Edit SOAP Draft"}
              </button>
              <button
                type="button"
                onClick={() => setCurrentStep(1)}
                className="rounded-xl bg-transparent px-3 py-2.5 text-xs font-medium text-[#6D7A8E] hover:text-[#162033] transition-all"
              >
                {language === "vi" ? "Khởi tạo ca mới" : "Start New Encounter"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ScribeDemo;
