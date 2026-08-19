"""Care Navigation and Triage Engine.

Provides deterministic triage rules and structured questions classifying user
symptoms into care setting urgency levels (EMERGENCY, URGENT, ROUTINE,
PHARMACIST, SELF_CARE) with clear rationale citing user facts without
returning ranked disease probability lists to consumers.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from clara_api.core.care_navigation.detector import EmergencyRedFlagDetector, RedFlagFinding

CareUrgency = Literal["EMERGENCY", "URGENT", "ROUTINE", "PHARMACIST", "SELF_CARE"]


class TriageQuestion(BaseModel):
    """Structured question for symptom triage intake."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Unique question identifier")
    category: str = Field(
        description="Clinical category (e.g. onset, severity, red_flags, history)"
    )
    prompt_vi: str = Field(description="Question text in Vietnamese")
    prompt_en: str = Field(description="Question text in English")
    input_type: Literal["text", "single_choice", "multiple_choice", "scale", "boolean"] = Field(
        default="text", description="UI input type"
    )
    options: list[dict[str, str]] | None = Field(
        default=None, description="Predefined choices if single_choice / multiple_choice"
    )
    required: bool = Field(default=False, description="Whether question is mandatory")


class TriageInput(BaseModel):
    """Input payload for symptom triage evaluation."""

    model_config = ConfigDict(extra="ignore")

    symptoms: str = Field(..., description="Free-text description of current symptoms")
    onset: str | None = Field(
        default=None, description="When symptoms started (e.g. '2 giờ trước', '3 ngày')"
    )
    duration: str | None = Field(default=None, description="How long symptoms lasted")
    severity_score: int | None = Field(
        default=None, ge=1, le=10, description="Self-reported pain/discomfort score (1-10)"
    )
    answers: dict[str, Any] = Field(
        default_factory=dict, description="Structured answers to triage questions"
    )
    current_medications: list[str] = Field(
        default_factory=list, description="Currently taken medications"
    )
    known_conditions: list[str] = Field(
        default_factory=list, description="Known chronic medical conditions"
    )
    locale: Literal["vi", "en"] = Field(default="vi", description="Target language")


class CareNavigationResult(BaseModel):
    """Comprehensive recommendation result from Care Navigation Engine."""

    model_config = ConfigDict(extra="ignore")

    urgency: CareUrgency = Field(
        ...,
        description="Care setting urgency: EMERGENCY, URGENT, ROUTINE, PHARMACIST, SELF_CARE",
    )
    care_setting: str = Field(
        ...,
        description="Recommended clinical facility or action setting in target locale",
    )
    care_setting_code: str = Field(
        ...,
        description="Machine-readable code: '115_er', 'same_day_clinic', 'scheduled_visit', 'pharmacy_otc', 'home_monitoring'",
    )
    recommendation: str = Field(
        ...,
        description="Clear plain-language recommendation for the user",
    )
    rationale: str = Field(
        ...,
        description="Explanation strictly citing key user-provided facts (never ranked disease lists)",
    )
    cited_facts: list[str] = Field(
        default_factory=list,
        description="Explicit user-provided facts and symptoms cited in the decision",
    )
    clinician_handoff_summary: str = Field(
        ...,
        description="Structured clinical summary formatted for handover to doctor or nurse",
    )
    actionable_steps: list[str] = Field(
        default_factory=list,
        description="Actionable guidance for next steps (what to do right now)",
    )
    red_flags_detected: list[str] = Field(
        default_factory=list,
        description="Identified red-flag triggers if any",
    )
    disclaimer: str = Field(
        ...,
        description="Safety notice that CLARA is a navigation assistant, not a diagnostic doctor",
    )


class CareNavigationEngine:
    """Core triage and care navigation engine.

    Enforces deterministic safety floors:
    - Any acute red flag detected by `EmergencyRedFlagDetector` immediately triggers `EMERGENCY`
      and cannot be downgraded.
    - Classifies remaining queries into `URGENT`, `ROUTINE`, `PHARMACIST`, or `SELF_CARE`.
    - Never outputs ranked disease probabilities (e.g. '80% Flu, 20% COVID').
    """

    @staticmethod
    def get_structured_questions() -> list[TriageQuestion]:
        """Return canonical structured triage intake question set."""
        return [
            TriageQuestion(
                id="chief_complaint",
                category="onset",
                prompt_vi="Bạn đang cảm thấy khó chịu hoặc có triệu chứng gì bất thường nhất?",
                prompt_en="What is your primary symptom or main concern right now?",
                input_type="text",
                required=True,
            ),
            TriageQuestion(
                id="onset_time",
                category="onset",
                prompt_vi="Triệu chứng này bắt đầu từ khi nào (đột ngột hay từ từ)?",
                prompt_en="When did this symptom start (suddenly or gradually)?",
                input_type="single_choice",
                options=[
                    {
                        "value": "sudden_minutes",
                        "label_vi": "Đột ngột trong vài phút/giờ qua",
                        "label_en": "Suddenly within minutes/hours",
                    },
                    {
                        "value": "recent_days",
                        "label_vi": "Trong 1-3 ngày gần đây",
                        "label_en": "Within the last 1-3 days",
                    },
                    {
                        "value": "subacute_weeks",
                        "label_vi": "Kéo dài hơn 1 tuần",
                        "label_en": "Persisting for over 1 week",
                    },
                    {
                        "value": "chronic_months",
                        "label_vi": "Kéo dài nhiều tuần/tháng",
                        "label_en": "Chronic for weeks or months",
                    },
                ],
                required=True,
            ),
            TriageQuestion(
                id="severity_scale",
                category="severity",
                prompt_vi="Mức độ đau hoặc khó chịu của bạn theo thang điểm từ 1 (rất nhẹ) đến 10 (cực kỳ dữ dội)?",
                prompt_en="How severe is the pain or discomfort on a scale of 1 (very mild) to 10 (unbearable)?",
                input_type="scale",
                required=True,
            ),
            TriageQuestion(
                id="fever_status",
                category="symptoms",
                prompt_vi="Bạn có bị sốt không? Nếu có, nhiệt độ cao nhất là bao nhiêu?",
                prompt_en="Do you have a fever? If yes, what is the highest temperature?",
                input_type="single_choice",
                options=[
                    {
                        "value": "no_fever",
                        "label_vi": "Không sốt (< 37.5°C)",
                        "label_en": "No fever (< 37.5°C)",
                    },
                    {
                        "value": "mild_fever",
                        "label_vi": "Sốt nhẹ (37.5°C - 38.4°C)",
                        "label_en": "Mild fever (37.5°C - 38.4°C)",
                    },
                    {
                        "value": "high_fever",
                        "label_vi": "Sốt cao (>= 38.5°C - 39.5°C)",
                        "label_en": "High fever (>= 38.5°C - 39.5°C)",
                    },
                    {
                        "value": "very_high_fever",
                        "label_vi": "Sốt rất cao (> 39.5°C) hoặc co giật",
                        "label_en": "Very high fever (> 39.5°C) or chills/convulsions",
                    },
                ],
            ),
            TriageQuestion(
                id="red_flags_check",
                category="red_flags",
                prompt_vi="Bạn có xuất hiện bất kỳ dấu hiệu nào sau đây không: đau ngực, khó thở, méo miệng/yếu liệt nửa người, chảy máu nhiều, sốc dị ứng?",
                prompt_en="Do you have any of: chest pain, severe shortness of breath, facial droop/weakness, heavy bleeding, or severe allergic reaction?",
                input_type="multiple_choice",
                options=[
                    {
                        "value": "chest_pain",
                        "label_vi": "Đau / tức nặng ngực",
                        "label_en": "Chest pain / pressure",
                    },
                    {
                        "value": "shortness_of_breath",
                        "label_vi": "Khó thở / thở hụt hơi",
                        "label_en": "Shortness of breath",
                    },
                    {
                        "value": "facial_weakness",
                        "label_vi": "Méo miệng / tê yếu tay chân",
                        "label_en": "Facial droop / limb weakness",
                    },
                    {
                        "value": "heavy_bleeding",
                        "label_vi": "Chảy máu không cầm / nôn ra máu",
                        "label_en": "Uncontrolled bleeding / vomiting blood",
                    },
                    {
                        "value": "none",
                        "label_vi": "Không có dấu hiệu nào ở trên",
                        "label_en": "None of the above",
                    },
                ],
            ),
            TriageQuestion(
                id="chronic_conditions",
                category="history",
                prompt_vi="Bạn có tiền sử bệnh nền (tim mạch, đái tháo đường, hen suyễn, tăng huyết áp) không?",
                prompt_en="Do you have underlying conditions (cardiovascular, diabetes, asthma, hypertension)?",
                input_type="text",
            ),
        ]

    @classmethod
    def evaluate(cls, triage_input: TriageInput) -> CareNavigationResult:
        """Evaluate symptoms through deterministic rules and classify urgency."""
        locale = triage_input.locale
        is_vi = locale == "vi"

        # Aggregate all text input for full-scope analysis
        all_text_parts = [triage_input.symptoms]
        if triage_input.onset:
            all_text_parts.append(f"Khởi phát: {triage_input.onset}")
        if triage_input.duration:
            all_text_parts.append(f"Thời gian: {triage_input.duration}")
        for k, v in triage_input.answers.items():
            all_text_parts.append(f"{k}: {v}")
        full_text = " ".join(all_text_parts)

        # -------------------------------------------------------------------
        # STEP 1: DETERMINISTIC EMERGENCY FLOOR (Red-Flag Detector)
        # -------------------------------------------------------------------
        red_flags: list[RedFlagFinding] = EmergencyRedFlagDetector.detect(full_text)

        # Also check answers dictionary for explicit red flag selections
        rf_answer = triage_input.answers.get("red_flags_check") or triage_input.answers.get(
            "red_flags"
        )
        if isinstance(rf_answer, list):
            for item in rf_answer:
                if item in (
                    "chest_pain",
                    "shortness_of_breath",
                    "facial_weakness",
                    "heavy_bleeding",
                ) and not any(f.category in item for f in red_flags):
                    red_flags.append(
                        RedFlagFinding(
                            category=item,
                            matched_phrase=f"User selected: {item}",
                            severity="EMERGENCY",
                            description_vi=f"Dấu hiệu cảnh báo cấp cứu: {item}",
                            description_en=f"Emergency red flag: {item}",
                        )
                    )
        elif (
            isinstance(rf_answer, str)
            and rf_answer not in ("none", "khong", "no", "")
            and not red_flags
        ):
            red_flags.append(
                RedFlagFinding(
                    category="declared_emergency_flag",
                    matched_phrase=rf_answer,
                    severity="EMERGENCY",
                    description_vi="Người dùng báo cáo dấu hiệu nguy cấp",
                    description_en="User reported emergency sign",
                )
            )

        # Gather cited facts
        cited_facts: list[str] = [f"Triệu chứng chính: {triage_input.symptoms.strip()}"]
        if triage_input.onset:
            cited_facts.append(f"Khởi phát: {triage_input.onset}")
        if triage_input.duration:
            cited_facts.append(f"Thời gian kéo dài: {triage_input.duration}")
        if triage_input.severity_score is not None:
            cited_facts.append(f"Điểm mức độ khó chịu: {triage_input.severity_score}/10")
        if triage_input.known_conditions:
            cited_facts.append(f"Bệnh nền: {', '.join(triage_input.known_conditions)}")
        if triage_input.current_medications:
            cited_facts.append(f"Thuốc đang dùng: {', '.join(triage_input.current_medications)}")

        disclaimer_vi = (
            "LƯU Ý: CLARA là trợ lý điều hướng y tế và hỗ trợ thông tin, không thay thế chẩn đoán "
            "hoặc chỉ định của bác sĩ. Nếu gặp tình trạng nguy hiểm đến tính mạng, hãy gọi 115 ngay."
        )
        disclaimer_en = (
            "NOTICE: CLARA is a care navigation assistant and does not replace clinical diagnosis "
            "or medical advice from a physician. If experiencing a life-threatening emergency, call emergency services immediately."
        )
        disclaimer = disclaimer_vi if is_vi else disclaimer_en

        # If any emergency red flag is detected, output EMERGENCY immediately (cannot be downgraded!)
        if red_flags:
            rf_labels = [f.description_vi if is_vi else f.description_en for f in red_flags]
            rf_codes = [str(f.category) for f in red_flags]

            setting_vi = "Cấp cứu 115 hoặc Khoa Cấp cứu (ER) bệnh viện gần nhất"
            setting_en = "Emergency Services (115) / Nearest Emergency Department (ER)"

            rec_vi = (
                "BẠN CẦN ĐƯỢC XỬ TRÍ Y TẾ KHẨN CẤP NGAY LẬP TỨC. Vui lòng gọi 115 hoặc nhờ người thân "
                "đưa ngay tới khoa Cấp cứu bệnh viện gần nhất. Không tự lái xe."
            )
            rec_en = (
                "IMMEDIATE EMERGENCY MEDICAL CARE IS REQUIRED. Please call 115 / emergency services or "
                "have someone transport you to the nearest Emergency Department immediately. Do not drive yourself."
            )

            rationale_vi = (
                f"Đã phát hiện dấu hiệu cảnh báo nguy hiểm cấp tính ({'; '.join(rf_labels)}). "
                f"Dựa trên các dữ kiện bạn cung cấp: {triage_input.symptoms.strip()}, đây là các dấu hiệu "
                f"tiềm ẩn nguy cơ đe dọa tính mạng cần được bác sĩ cấp cứu can thiệp ngay."
            )
            rationale_en = (
                f"Acute emergency red-flags detected ({'; '.join(rf_labels)}). "
                f"Based on user-reported facts: {triage_input.symptoms.strip()}, these signs indicate "
                f"potential life-threatening risks requiring immediate clinical intervention."
            )

            handoff_vi = (
                f"TÓM TẮT BÀN GIAO CẤP CỨU:\n"
                f"- Dấu hiệu báo động: {', '.join(rf_labels)}\n"
                f"- Triệu chứng mô tả: {triage_input.symptoms}\n"
                f"- Khởi phát / Thời gian: {triage_input.onset or 'Không rõ'} | {triage_input.duration or 'Không rõ'}\n"
                f"- Mức độ đau/khó chịu: {triage_input.severity_score or 'N/A'}/10\n"
                f"- Tiền sử bệnh: {', '.join(triage_input.known_conditions) if triage_input.known_conditions else 'Không ghi nhận'}\n"
                f"- Thuốc đang dùng: {', '.join(triage_input.current_medications) if triage_input.current_medications else 'Không ghi nhận'}"
            )
            handoff_en = (
                f"EMERGENCY HANDOFF SUMMARY:\n"
                f"- Red Flags: {', '.join(rf_labels)}\n"
                f"- Chief Symptoms: {triage_input.symptoms}\n"
                f"- Onset / Duration: {triage_input.onset or 'Unknown'} | {triage_input.duration or 'Unknown'}\n"
                f"- Severity: {triage_input.severity_score or 'N/A'}/10\n"
                f"- Medical History: {', '.join(triage_input.known_conditions) if triage_input.known_conditions else 'None reported'}\n"
                f"- Current Medications: {', '.join(triage_input.current_medications) if triage_input.current_medications else 'None reported'}"
            )

            steps_vi = [
                "Gọi 115 hoặc tới khoa Cấp cứu bệnh viện gần nhất ngay lập tức.",
                "Ngồi hoặc nằm nghỉ ngơi ở tư thế thoải mái, nới lỏng quần áo, giữ bình tĩnh.",
                "Không tự lái xe; nhờ người thân hỗ trợ hoặc gọi xe cấp cứu.",
                "Mang theo danh sách thuốc đang dùng hoặc hồ sơ y tế nếu thuận tiện.",
            ]
            steps_en = [
                "Call 115 / emergency services or go to the nearest Emergency Department immediately.",
                "Sit or lie down in a comfortable position, loosen tight clothing, remain calm.",
                "Do not drive yourself; seek assistance from family or ambulance.",
                "Bring your current medication list or health records if accessible.",
            ]

            return CareNavigationResult(
                urgency="EMERGENCY",
                care_setting=setting_vi if is_vi else setting_en,
                care_setting_code="115_er",
                recommendation=rec_vi if is_vi else rec_en,
                rationale=rationale_vi if is_vi else rationale_en,
                cited_facts=cited_facts,
                clinician_handoff_summary=handoff_vi if is_vi else handoff_en,
                actionable_steps=steps_vi if is_vi else steps_en,
                red_flags_detected=rf_codes,
                disclaimer=disclaimer,
            )

        # -------------------------------------------------------------------
        # STEP 2: URGENT (Same-day clinic) EVALUATION
        # -------------------------------------------------------------------
        folded_full = EmergencyRedFlagDetector.fold_text(full_text)
        fever_status = str(triage_input.answers.get("fever_status") or "")
        severity = triage_input.severity_score or 0

        is_urgent = False
        urgent_reasons: list[str] = []

        # High pain score (>= 8)
        if severity >= 8:
            is_urgent = True
            urgent_reasons.append("Điểm khó chịu/đau ở mức rất cao (>= 8/10)")

        # High fever or prolonged fever
        if fever_status in ("very_high_fever", "high_fever") or any(
            p in folded_full
            for p in ("sot cao", "sot 39", "sot 40", "high fever", "sot 3 ngay", "sot tren 3 ngay")
        ):
            is_urgent = True
            urgent_reasons.append("Sốt cao hoặc sốt kéo dài cần thăm khám trong ngày")

        # Acute severe abdominal pain, persistent vomiting / dehydration
        if any(
            p in folded_full
            for p in (
                "dau bung du doi",
                "dau quan bung",
                "non lien tuc",
                "khong uong duoc nuoc",
                "mat nuoc",
                "severe abdominal pain",
                "persistent vomiting",
                "unable to keep fluids",
                "dehydration",
            )
        ):
            is_urgent = True
            urgent_reasons.append("Triệu chứng tiêu hóa / mất nước cấp tính cần bác sĩ đánh giá")

        # Spreading rash with fever or suspected fracture
        if any(
            p in folded_full
            for p in (
                "phat ban kem sot",
                "vet thuong sau",
                "nghi gay xuong",
                "bien dang khop",
                "spreading rash",
                "deep wound",
                "suspected fracture",
            )
        ):
            is_urgent = True
            urgent_reasons.append("Tổn thương cấp tính hoặc nhiễm trùng lan rộng")

        if is_urgent:
            setting_vi = "Phòng khám Đa khoa / Bác sĩ trong ngày (Same-day clinic)"
            setting_en = "Urgent Care Clinic / Same-Day Physician Consultation"

            rec_vi = (
                "Bạn nên đến phòng khám hoặc gặp bác sĩ trong ngày hôm nay để được thăm khám "
                "và đánh giá trực tiếp. Tình trạng này không nên trì hoãn sang các ngày sau."
            )
            rec_en = (
                "You should visit an urgent care clinic or consult a physician today for direct evaluation. "
                "This condition should not be delayed to subsequent days."
            )

            rationale_vi = (
                f"Dựa trên các triệu chứng bạn cung cấp ({', '.join(urgent_reasons)}), "
                f"tình trạng sức khỏe cần được nhân viên y tế chẩn đoán nguyên nhân và chỉ định xét nghiệm "
                f"hoặc điều trị thích hợp trong ngày."
            )
            rationale_en = (
                f"Based on user-provided facts ({', '.join(urgent_reasons)}), "
                f"your condition requires professional clinical assessment and same-day medical intervention."
            )

            handoff_vi = (
                f"TÓM TẮT BÀN GIAO PHÒNG KHÁM (TRONG NGÀY):\n"
                f"- Lý do khám: {triage_input.symptoms}\n"
                f"- Yếu tố cấp thiết: {'; '.join(urgent_reasons)}\n"
                f"- Thời gian khởi phát: {triage_input.onset or triage_input.duration or 'Không rõ'}\n"
                f"- Mức độ đau/khó chịu: {severity}/10\n"
                f"- Tiền sử & Thuốc: Bệnh nền ({', '.join(triage_input.known_conditions) or 'Không'}); Thuốc ({', '.join(triage_input.current_medications) or 'Không'})"
            )
            handoff_en = (
                f"SAME-DAY CLINIC HANDOFF SUMMARY:\n"
                f"- Chief complaint: {triage_input.symptoms}\n"
                f"- Urgent indicators: {'; '.join(urgent_reasons)}\n"
                f"- Onset / Duration: {triage_input.onset or triage_input.duration or 'Unknown'}\n"
                f"- Severity score: {severity}/10\n"
                f"- History & Meds: Conditions ({', '.join(triage_input.known_conditions) or 'None'}); Meds ({', '.join(triage_input.current_medications) or 'None'})"
            )

            steps_vi = [
                "Đặt hẹn hoặc đến trực tiếp phòng khám đa khoa / cơ sở y tế gần nhất trong ngày.",
                "Ghi chép diễn biến triệu chứng (nhiệt độ sốt, thời điểm đau) để báo với bác sĩ.",
                "Uống đủ nước (oresol nếu mất nước) và nghỉ ngơi.",
                "Nếu xuất hiện đau ngực, khó thở, ngất xỉu, hãy chuyển sang hướng xử trí cấp cứu 115 ngay.",
            ]
            steps_en = [
                "Schedule a same-day clinic visit or go to an urgent care center today.",
                "Track symptom timeline (temperature, pain patterns) for the doctor.",
                "Stay hydrated and rest.",
                "If chest pain, shortness of breath, or fainting develops, seek immediate emergency care (115).",
            ]

            return CareNavigationResult(
                urgency="URGENT",
                care_setting=setting_vi if is_vi else setting_en,
                care_setting_code="same_day_clinic",
                recommendation=rec_vi if is_vi else rec_en,
                rationale=rationale_vi if is_vi else rationale_en,
                cited_facts=cited_facts,
                clinician_handoff_summary=handoff_vi if is_vi else handoff_en,
                actionable_steps=steps_vi if is_vi else steps_en,
                red_flags_detected=[],
                disclaimer=disclaimer,
            )

        # -------------------------------------------------------------------
        # STEP 3: ROUTINE (Scheduled outpatient visit) EVALUATION
        # -------------------------------------------------------------------
        onset_val = str(triage_input.answers.get("onset_time") or "")
        is_routine = False
        routine_reasons: list[str] = []

        if onset_val in ("subacute_weeks", "chronic_months") or any(
            p in folded_full
            for p in (
                "keo dai 2 tuan",
                "keo dai hon 1 tuan",
                "man tinh",
                "kham dinh ky",
                "tai kham",
                "tai kham dinh ky",
                "giam can khong ro nguyen nhan",
                "met moi keo dai",
                "chronic",
                "over a week",
                "routine checkup",
                "scheduled visit",
            )
        ):
            is_routine = True
            routine_reasons.append(
                "Triệu chứng kéo dài nhiều ngày/tuần hoặc nhu cầu khám định kỳ/tái khám"
            )

        if severity in (5, 6, 7) and not is_routine:
            is_routine = True
            routine_reasons.append(
                f"Mức độ khó chịu trung bình ({severity}/10) không có dấu hiệu khẩn cấp"
            )

        if is_routine:
            setting_vi = "Đặt lịch hẹn khám Chuyên khoa / Bác sĩ gia đình"
            setting_en = "Scheduled Outpatient / Primary Care Specialist Appointment"

            rec_vi = (
                "Bạn nên đặt lịch hẹn khám định kỳ với bác sĩ chuyên khoa hoặc bác sĩ gia đình "
                "trong vài ngày tới để được chẩn đoán toàn diện và theo dõi phù hợp."
            )
            rec_en = (
                "You should schedule an outpatient appointment with your primary care provider or specialist "
                "in the coming days for comprehensive assessment and ongoing management."
            )

            rationale_vi = (
                f"Dựa trên các thông tin bạn cung cấp ({', '.join(routine_reasons)}), "
                f"triệu chứng hiện tại có tính chất bán cấp hoặc mạn tính, thích hợp thăm khám "
                f"có kế hoạch mà không cần can thiệp khẩn cấp."
            )
            rationale_en = (
                f"Based on user facts ({', '.join(routine_reasons)}), "
                f"the symptoms present a subacute or chronic pattern suitable for scheduled clinical consultation."
            )

            handoff_vi = (
                f"TÓM TẮT THĂM KHÁM THEO LỊCH:\n"
                f"- Lý do / Vấn đề cần trao đổi: {triage_input.symptoms}\n"
                f"- Thời gian diễn tiến: {triage_input.onset or triage_input.duration or 'Kéo dài'}\n"
                f"- Mức độ khó chịu: {severity}/10\n"
                f"- Tiền sử bệnh: {', '.join(triage_input.known_conditions) or 'Không có'}\n"
                f"- Thuốc hiện tại: {', '.join(triage_input.current_medications) or 'Không có'}"
            )
            handoff_en = (
                f"SCHEDULED VISIT SUMMARY:\n"
                f"- Discussion topic: {triage_input.symptoms}\n"
                f"- Progression timeline: {triage_input.onset or triage_input.duration or 'Extended'}\n"
                f"- Severity: {severity}/10\n"
                f"- Conditions: {', '.join(triage_input.known_conditions) or 'None'}\n"
                f"- Current meds: {', '.join(triage_input.current_medications) or 'None'}"
            )

            steps_vi = [
                "Đặt lịch hẹn khám tại cơ sở y tế phù hợp trong tuần.",
                "Chuẩn bị các câu hỏi cần trao đổi với bác sĩ và danh sách thuốc/xét nghiệm cũ.",
                "Tiếp tục theo dõi các thay đổi của triệu chứng.",
                "Nếu triệu chứng đột ngột xấu đi hoặc xuất hiện khó thở/đau ngực, hãy đi khám sớm hơn.",
            ]
            steps_en = [
                "Book an appointment with a suitable clinic or specialist this week.",
                "Prepare questions for the doctor along with previous lab records/medications.",
                "Monitor any symptom changes.",
                "If symptoms acutely worsen or red flags arise, seek medical attention earlier.",
            ]

            return CareNavigationResult(
                urgency="ROUTINE",
                care_setting=setting_vi if is_vi else setting_en,
                care_setting_code="scheduled_visit",
                recommendation=rec_vi if is_vi else rec_en,
                rationale=rationale_vi if is_vi else rationale_en,
                cited_facts=cited_facts,
                clinician_handoff_summary=handoff_vi if is_vi else handoff_en,
                actionable_steps=steps_vi if is_vi else steps_en,
                red_flags_detected=[],
                disclaimer=disclaimer,
            )

        # -------------------------------------------------------------------
        # STEP 4: PHARMACIST (OTC / Community pharmacy guidance) EVALUATION
        # -------------------------------------------------------------------
        is_pharmacist = False
        pharmacist_reasons: list[str] = []

        if any(
            p in folded_full
            for p in (
                "cam lanh",
                "so mui",
                "nghet mui",
                "chay nuoc mui",
                "viem mui di ung",
                "dau hong nhe",
                "nhiet mieng",
                "day bung",
                "o nong",
                "o chua",
                "bong nhe",
                "di ung thoi tiet",
                "mua thuoc",
                "hoi thuoc",
                "common cold",
                "runny nose",
                "mild sore throat",
                "allergic rhinitis",
                "mild heartburn",
                "indigestion",
                "otc medicine",
            )
        ) or (severity in (2, 3, 4)):
            is_pharmacist = True
            pharmacist_reasons.append(
                "Triệu chứng nhẹ, phù hợp tư vấn sử dụng thuốc không kê đơn (OTC)"
            )

        if is_pharmacist:
            setting_vi = "Nhà thuốc / Tham vấn Dược sĩ cộng đồng"
            setting_en = "Community Pharmacy / Pharmacist OTC Guidance"

            rec_vi = (
                "Bạn có thể đến nhà thuốc để được dược sĩ tư vấn sử dụng các loại thuốc không kê đơn "
                "(OTC) hoặc các biện pháp giảm nhẹ triệu chứng phù hợp."
            )
            rec_en = (
                "You can consult a community pharmacist for advice on over-the-counter (OTC) medications "
                "and appropriate symptomatic relief options."
            )

            rationale_vi = (
                f"Dựa trên các triệu chứng bạn mô tả ({triage_input.symptoms.strip()}), "
                f"tình trạng ở mức độ nhẹ ({severity}/10), chưa thấy dấu hiệu nhiễm trùng nghiêm trọng hay biến chứng, "
                f"thích hợp để dược sĩ hướng dẫn chăm sóc triệu chứng an toàn."
            )
            rationale_en = (
                f"Based on user-reported symptoms ({triage_input.symptoms.strip()}), "
                f"the condition is mild ({severity}/10) without red flags, suitable for pharmacist OTC guidance."
            )

            handoff_vi = (
                f"TÓM TẮT THAM VẤN DƯỢC SĨ:\n"
                f"- Triệu chứng cần hỗ trợ: {triage_input.symptoms}\n"
                f"- Mức độ khó chịu: {severity}/10\n"
                f"- Thuốc đang sử dụng: {', '.join(triage_input.current_medications) or 'Chưa có'}\n"
                f"- Tiền sử dị ứng / bệnh nền: {', '.join(triage_input.known_conditions) or 'Không ghi nhận'}"
            )
            handoff_en = (
                f"PHARMACIST CONSULTATION SUMMARY:\n"
                f"- Chief complaint: {triage_input.symptoms}\n"
                f"- Severity: {severity}/10\n"
                f"- Current medications: {', '.join(triage_input.current_medications) or 'None'}\n"
                f"- Conditions / Allergies: {', '.join(triage_input.known_conditions) or 'None'}"
            )

            steps_vi = [
                "Trao đổi với dược sĩ tại nhà thuốc về triệu chứng và các thuốc đang dùng để tránh tương tác.",
                "Đọc kỹ hướng dẫn sử dụng và tuân thủ liều lượng khuyến cáo.",
                "Nếu triệu chứng không cải thiện sau 3-5 ngày hoặc có chiều hướng tăng nặng, hãy đi khám bác sĩ.",
            ]
            steps_en = [
                "Consult the pharmacist about symptoms and your current medications to prevent interactions.",
                "Carefully follow packaging instructions and recommended dosages.",
                "If symptoms persist beyond 3-5 days or worsen, consult a doctor.",
            ]

            return CareNavigationResult(
                urgency="PHARMACIST",
                care_setting=setting_vi if is_vi else setting_en,
                care_setting_code="pharmacy_otc",
                recommendation=rec_vi if is_vi else rec_en,
                rationale=rationale_vi if is_vi else rationale_en,
                cited_facts=cited_facts,
                clinician_handoff_summary=handoff_vi if is_vi else handoff_en,
                actionable_steps=steps_vi if is_vi else steps_en,
                red_flags_detected=[],
                disclaimer=disclaimer,
            )

        # -------------------------------------------------------------------
        # STEP 5: SELF_CARE (Monitoring & home care)
        # -------------------------------------------------------------------
        setting_vi = "Tự theo dõi và chăm sóc tại nhà"
        setting_en = "Home Monitoring & Self-Care"

        rec_vi = (
            "Bạn có thể tiếp tục nghỉ ngơi, uống đủ nước và tự theo dõi sức khỏe tại nhà. "
            "Hiện tại chưa thấy dấu hiệu cần can thiệp y tế đặc biệt."
        )
        rec_en = (
            "You can rest, maintain hydration, and monitor your symptoms at home. "
            "No acute clinical intervention is currently indicated."
        )

        rationale_vi = (
            f"Dựa trên các thông tin bạn báo cáo ({triage_input.symptoms.strip()}), "
            f"triệu chứng rất nhẹ (mức {severity}/10) và không có dấu hiệu cảnh báo bất thường."
        )
        rationale_en = (
            f"Based on user-reported facts ({triage_input.symptoms.strip()}), "
            f"the symptom is very mild ({severity}/10) with no red flags identified."
        )

        handoff_vi = (
            f"TÓM TẮT TỰ THEO DÕI TẠI NHÀ:\n"
            f"- Triệu chứng ghi nhận: {triage_input.symptoms}\n"
            f"- Mức độ: {severity}/10\n"
            f"- Theo dõi diễn biến trong 24-48 giờ tới."
        )
        handoff_en = (
            f"HOME MONITORING SUMMARY:\n"
            f"- Reported symptom: {triage_input.symptoms}\n"
            f"- Severity: {severity}/10\n"
            f"- Monitor progression over the next 24-48 hours."
        )

        steps_vi = [
            "Nghỉ ngơi hợp lý và uống đủ nước.",
            "Ăn uống đủ chất, tránh căng thẳng hoặc vận động quá sức.",
            "Theo dõi nếu triệu chứng tiến triển hoặc kéo dài thì liên hệ nhân viên y tế.",
        ]
        steps_en = [
            "Get adequate rest and maintain hydration.",
            "Eat nutritious meals and avoid overexertion.",
            "Monitor symptoms and seek medical advice if they worsen or persist.",
        ]

        return CareNavigationResult(
            urgency="SELF_CARE",
            care_setting=setting_vi if is_vi else setting_en,
            care_setting_code="home_monitoring",
            recommendation=rec_vi if is_vi else rec_en,
            rationale=rationale_vi if is_vi else rationale_en,
            cited_facts=cited_facts,
            clinician_handoff_summary=handoff_vi if is_vi else handoff_en,
            actionable_steps=steps_vi if is_vi else steps_en,
            red_flags_detected=[],
            disclaimer=disclaimer,
        )
