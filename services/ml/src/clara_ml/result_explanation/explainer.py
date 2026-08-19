"""Lab Result Plain-Language Explanation Task.

Provides patient-friendly explanations of clinical laboratory results while
strictly enforcing safety and numeric fidelity invariants:
- Never invents reference ranges if not provided by the lab.
- Clearly states what the test measures in plain language.
- Clarifies that an abnormal flag/value is NEVER a medical diagnosis on its own.
- Generates targeted questions for the user to discuss with their clinician.
- Enforces strict numeric fidelity: cannot alter the observed value or unit.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field


class NumericFidelityError(ValueError):
    """Raised when numeric value or unit has been altered during explanation generation."""


class LabResultInput(BaseModel):
    """Input parameters for lab result explanation."""

    model_config = ConfigDict(extra="ignore")

    analyte_name: str = Field(
        ..., min_length=1, description="Analyte / test name (e.g. 'HbA1c', 'Glucose', 'Creatinine')"
    )
    observed_value: str | float | int = Field(
        ..., description="Observed quantitative or qualitative result value"
    )
    unit: str = Field(
        default="", description="Measurement unit (e.g. 'mmol/L', '%', 'mg/dL', 'U/L')"
    )
    reference_range: str | None = Field(
        default=None, description="Exact lab-provided reference interval if present"
    )
    specimen_date: str | date | datetime | None = Field(
        default=None, description="Date specimen was collected"
    )
    locale: Literal["vi", "en"] = Field(default="vi", description="Output language")


class LabResultExplanation(BaseModel):
    """Structured, fidelity-verified explanation of a laboratory test result."""

    model_config = ConfigDict(extra="ignore")

    analyte_name: str = Field(..., description="Analyte name from input")
    observed_value: str = Field(..., description="Preserved observed value string")
    unit: str = Field(..., description="Preserved measurement unit")
    reference_range: str | None = Field(
        default=None, description="Lab-provided reference range or None"
    )
    reference_range_source: Literal["provided_by_lab", "not_provided"] = Field(
        ..., description="Whether reference range was provided by the lab"
    )
    specimen_date: str | None = Field(default=None, description="Specimen collection date")
    test_purpose: str = Field(
        ..., description="Plain-language description of what this test measures"
    )
    interpretation_summary: str = Field(
        ..., description="Explanation of what this specific value indicates"
    )
    status_flag: Literal["normal", "abnormal_high", "abnormal_low", "unspecified"] = Field(
        ..., description="Evaluation status based solely on lab-provided reference range"
    )
    non_diagnostic_disclaimer: str = Field(
        ..., description="Safety clarification that abnormal flags are not a medical diagnosis"
    )
    questions_for_clinician: list[str] = Field(
        default_factory=list, description="Targeted questions to discuss with a healthcare provider"
    )
    fidelity_verified: bool = Field(
        default=True,
        description="Whether numeric value and unit were strictly verified against input",
    )


class LabResultExplainer:
    """Explains laboratory results with zero hallucination of reference ranges and strict numeric fidelity."""

    _ANALYTE_KNOWLEDGE: ClassVar[dict[str, dict[str, Any]]] = {
        "glucose": {
            "aliases": (
                "glucose",
                "duong huyet",
                "duong mau",
                "blood sugar",
                "glu",
                "fasting glucose",
            ),
            "purpose_vi": "Xét nghiệm Glucose đo nồng độ đường trong máu tại thời điểm lấy mẫu, thường dùng để sàng lọc và theo dõi bệnh đái tháo đường.",
            "purpose_en": "The Glucose test measures blood sugar concentration at the time of sampling, commonly used to screen and monitor diabetes.",
            "high_hint_vi": "Nồng độ glucose máu cao hơn khoảng tham chiếu có thể liên quan đến tăng đường huyết, đái tháo đường hoặc sau bữa ăn.",
            "high_hint_en": "A glucose level above the reference range may indicate hyperglycemia, diabetes, or post-prandial state.",
            "low_hint_vi": "Nồng độ glucose máu thấp hơn khoảng tham chiếu có thể là dấu hiệu của hạ đường huyết, nhịn ăn kéo dài hoặc do thuốc hạ đường huyết.",
            "low_hint_en": "A glucose level below the reference range may indicate hypoglycemia, prolonged fasting, or medication effects.",
            "default_questions_vi": [
                "Chỉ số đường huyết này có cần kiểm tra lại sau khi nhịn ăn hoặc làm thêm xét nghiệm HbA1c không?",
                "Tôi có cần điều chỉnh chế độ dinh dưỡng, tập luyện hoặc liều thuốc hiện tại không?",
                "Khi nào tôi nên kiểm tra lại đường huyết?",
            ],
            "default_questions_en": [
                "Does this blood glucose result require a fasting re-test or an HbA1c check?",
                "Should I adjust my diet, physical activity, or current medications?",
                "When should I schedule a follow-up test?",
            ],
        },
        "hba1c": {
            "aliases": ("hba1c", "hemoglobin a1c", "glycated hemoglobin", "a1c"),
            "purpose_vi": "Xét nghiệm HbA1c đo tỷ lệ hemoglobin gắn đường trong hồng cầu, phản ánh mức đường huyết trung bình trong 2 đến 3 tháng vừa qua.",
            "purpose_en": "The HbA1c test measures the percentage of glycated hemoglobin in red blood cells, reflecting average blood sugar control over the past 2-3 months.",
            "high_hint_vi": "Chỉ số HbA1c cao hơn khoảng tham chiếu cho thấy mức đường huyết trung bình trong 2-3 tháng qua chưa được kiểm soát tối ưu hoặc có nguy cơ tiền đái tháo đường / đái tháo đường.",
            "high_hint_en": "An elevated HbA1c level indicates suboptimal average glucose control over the past 2-3 months or increased risk of pre-diabetes / diabetes.",
            "low_hint_vi": "Chỉ số HbA1c thấp có thể gặp ở người có các bệnh lý về hồng cầu (như thiếu máu huyết tán) hoặc hạ đường huyết thường xuyên.",
            "low_hint_en": "A lower HbA1c may be associated with red blood cell disorders (such as hemolytic anemia) or frequent hypoglycemia.",
            "default_questions_vi": [
                "Mục tiêu HbA1c phù hợp nhất với độ tuổi và thể trạng của tôi là bao nhiêu %?",
                "Tôi có cần thay đổi phác đồ thuốc điều trị đái tháo đường hoặc lối sống không?",
                "Bao lâu sau tôi nên xét nghiệm lại HbA1c (3 tháng hay 6 tháng)?",
            ],
            "default_questions_en": [
                "What is my personalized target HbA1c percentage given my age and health profile?",
                "Do I need adjustments in my diabetes medication regimen or lifestyle?",
                "How often should I repeat the HbA1c test (every 3 or 6 months)?",
            ],
        },
        "creatinine": {
            "aliases": ("creatinine", "cre", "creatinin mau", "serum creatinine"),
            "purpose_vi": "Xét nghiệm Creatinine huyết thanh đo nồng độ sản phẩm chuyển hóa từ cơ bắp, là chỉ số cơ bản để đánh giá chức năng lọc của thận.",
            "purpose_en": "Serum Creatinine measures a byproduct of muscle metabolism and is a primary biomarker for evaluating kidney filtration function.",
            "high_hint_vi": "Nồng độ Creatinine tăng cao hơn khoảng tham chiếu có thể là dấu hiệu suy giảm khả năng lọc của thận hoặc do mất nước, vận động cơ bắp cường độ cao.",
            "high_hint_en": "Elevated Creatinine above reference range may suggest decreased kidney filtration function, dehydration, or heavy muscle exertion.",
            "low_hint_vi": "Nồng độ Creatinine thấp có thể liên quan đến khối lượng cơ bắp ít, suy dinh dưỡng hoặc chế độ ăn rất ít đạm.",
            "low_hint_en": "Low Creatinine may be associated with reduced muscle mass, malnutrition, or low-protein diets.",
            "default_questions_vi": [
                "Chỉ số Creatinine này quy đổi ra mức độ lọc cầu thận (eGFR) là bao nhiêu?",
                "Các loại thuốc tôi đang dùng có ảnh hưởng gì tới chức năng thận không?",
                "Tôi cần lưu ý gì về lượng nước uống và chế độ ăn đạm hàng ngày?",
            ],
            "default_questions_en": [
                "What is my calculated estimated glomerular filtration rate (eGFR) based on this Creatinine?",
                "Do any of my current medications pose a risk to kidney function?",
                "What daily fluid and dietary protein guidelines should I follow?",
            ],
        },
        "alt": {
            "aliases": ("alt", "sgpt", "alanine aminotransferase", "men gan alt"),
            "purpose_vi": "Xét nghiệm ALT (SGPT) là một loại enzym tập trung chủ yếu ở tế bào gan, dùng để phát hiện tổn thương hoặc viêm ở gan.",
            "purpose_en": "ALT (SGPT) is an enzyme primarily concentrated in liver cells, used to detect liver inflammation or cellular injury.",
            "high_hint_vi": "Chỉ số ALT tăng cao cho thấy tế bào gan có thể đang bị kích ứng hoặc tổn thương do viêm gan virus, gan nhiễm mỡ, rượu bia hoặc tác dụng phụ của thuốc.",
            "high_hint_en": "Elevated ALT suggests liver cellular irritation or injury due to viral hepatitis, steatosis, alcohol, or medication side effects.",
            "low_hint_vi": "Chỉ số ALT thấp thường là bình thường và không có ý nghĩa bệnh lý đặc biệt.",
            "low_hint_en": "Low ALT is generally normal and typically has no pathological significance.",
            "default_questions_vi": [
                "Men gan tăng như vậy có cần làm thêm xét nghiệm siêu âm gan hoặc kiểm tra viêm gan siêu vi B/C không?",
                "Có loại thuốc, thực phẩm chức năng hoặc rượu bia nào tôi đang dùng gây tăng men gan không?",
                "Khi nào tôi nên kiểm tra lại men gan?",
            ],
            "default_questions_en": [
                "Does this elevated ALT require further liver ultrasound or viral hepatitis screening?",
                "Could any of my current prescriptions, supplements, or alcohol intake be affecting my liver?",
                "When should I repeat the liver enzyme test?",
            ],
        },
        "ast": {
            "aliases": ("ast", "sgot", "aspartate aminotransferase", "men gan ast"),
            "purpose_vi": "Xét nghiệm AST (SGOT) đo nồng độ enzym có trong gan, tim và cơ bắp, hỗ trợ đánh giá tình trạng tổn thương mô gan và cơ.",
            "purpose_en": "AST (SGOT) measures an enzyme found in liver, heart, and muscle tissues, helping evaluate liver and muscle cellular status.",
            "high_hint_vi": "AST tăng cao có thể do tổn thương tế bào gan, tập luyện thể lực nặng, hoặc các vấn đề về cơ/tim.",
            "high_hint_en": "Elevated AST can be caused by liver cell injury, intense physical exercise, or muscle/cardiac conditions.",
            "low_hint_vi": "AST thấp thường nằm trong giới hạn sinh lý bình thường.",
            "low_hint_en": "Low AST is usually within normal physiological variation.",
            "default_questions_vi": [
                "Tỷ lệ giữa AST và ALT của tôi có ý nghĩa gì về nguyên nhân gây tổn thương gan?",
                "Tôi có cần kiêng khem hay làm thêm xét nghiệm chuyên sâu nào không?",
            ],
            "default_questions_en": [
                "What does my AST/ALT ratio suggest regarding the underlying cause?",
                "Are there specific dietary restrictions or further diagnostic tests recommended?",
            ],
        },
        "cholesterol_ldl": {
            "aliases": ("ldl", "ldl-c", "ldl cholesterol", "cholesterol ldl", "cholesterol xau"),
            "purpose_vi": "Xét nghiệm LDL-Cholesterol đo lượng mỡ 'xấu' trong máu, là yếu tố nguy cơ chính hình thành mảng xơ vữa động mạch.",
            "purpose_en": "LDL-Cholesterol measures 'bad' cholesterol in the blood, a major risk factor for atherosclerotic plaque formation.",
            "high_hint_vi": "LDL-C tăng cao làm gia tăng nguy cơ xơ vữa mạch máu và các bệnh lý tim mạch (như bệnh mạch vành, nhồi máu cơ tim, đột quỵ).",
            "high_hint_en": "Elevated LDL-C increases the risk of vascular atherosclerosis and cardiovascular events (coronary artery disease, myocardial infarction, stroke).",
            "low_hint_vi": "LDL-C thấp thường có lợi cho tim mạch, tuy nhiên mức cực thấp cần đánh giá tổng thể dinh dưỡng và hấp thu.",
            "low_hint_en": "Low LDL-C is generally protective against cardiovascular disease, though very low levels may warrant nutritional review.",
            "default_questions_vi": [
                "Mức LDL-C mục tiêu của tôi là bao nhiêu dựa trên nguy cơ tim mạch tổng thể?",
                "Tôi nên bắt đầu thay đổi chế độ ăn giảm mỡ hay cần dùng thuốc nhóm Statin?",
                "Khi nào tôi nên xét nghiệm lại bộ mỡ máu (Lipid panel)?",
            ],
            "default_questions_en": [
                "What is my personalized target LDL-C level based on my overall cardiovascular risk?",
                "Should I start with lifestyle/dietary modifications or do I need a statin medication?",
                "When should I follow up with a full lipid panel?",
            ],
        },
        "tsh": {
            "aliases": ("tsh", "thyroid stimulating hormone", "hormone tuyen giap"),
            "purpose_vi": "Xét nghiệm TSH đo hormone kích thích tuyến giáp do tuyến yên tiết ra, là chỉ số quan trọng hàng đầu để đánh giá chức năng tuyến giáp.",
            "purpose_en": "TSH measures thyroid-stimulating hormone produced by the pituitary gland, serving as the primary screening tool for thyroid function.",
            "high_hint_vi": "TSH tăng cao thường gợi ý tình trạng suy giáp (tuyến giáp hoạt động kém không sản xuất đủ hormone giáp).",
            "high_hint_en": "High TSH typically indicates hypothyroidism (underactive thyroid gland producing insufficient thyroid hormones).",
            "low_hint_vi": "TSH giảm thấp thường gợi ý tình trạng cường giáp (tuyến giáp sản xuất quá mức hormone giáp).",
            "low_hint_en": "Low TSH typically indicates hyperthyroidism (overactive thyroid gland producing excessive thyroid hormones).",
            "default_questions_vi": [
                "Tôi có cần làm thêm xét nghiệm hormone giáp tự do (FT4, FT3) hoặc kháng thể tuyến giáp không?",
                "Các triệu chứng mệt mỏi, thay đổi cân nặng hay nhịp tim của tôi có liên quan đến chỉ số TSH này không?",
            ],
            "default_questions_en": [
                "Do I need additional free thyroid hormone tests (Free T4, Free T3) or thyroid antibodies?",
                "Could my symptoms (fatigue, weight changes, heart rate) be related to this TSH level?",
            ],
        },
        "uric_acid": {
            "aliases": ("uric acid", "acid uric", "axit uric", "urate"),
            "purpose_vi": "Xét nghiệm Axit Uric đo lượng axit uric trong máu, hỗ trợ chẩn đoán và theo dõi bệnh Gút (Gout) cũng như nguy cơ sỏi thận urat.",
            "purpose_en": "Uric Acid measures the concentration of uric acid in blood, used to evaluate gout, hyperuricemia, and uric acid kidney stones.",
            "high_hint_vi": "Axit Uric tăng cao (tăng axit uric máu) có thể dẫn đến lắng đọng tinh thể urat tại các khớp gây viêm khớp gút cấp hoặc sỏi đường tiết niệu.",
            "high_hint_en": "Elevated Uric Acid can lead to urate crystal deposition in joints causing acute gout attacks or urinary tract stones.",
            "low_hint_vi": "Axit Uric thấp hiếm gặp và thường ít có ý nghĩa bệnh lý nghiêm trọng.",
            "low_hint_en": "Low Uric Acid is uncommon and rarely of clinical concern.",
            "default_questions_vi": [
                "Với mức axit uric này, tôi có cần dùng thuốc hạ axit uric hay chỉ cần kiêng đạm, hải sản, rượu bia?",
                "Tôi nên uống bao nhiêu lít nước mỗi ngày để hỗ trợ đào thải axit uric qua thận?",
            ],
            "default_questions_en": [
                "Given this uric acid level, do I need urate-lowering medication or lifestyle modifications alone?",
                "How much daily hydration is recommended to support renal uric acid excretion?",
            ],
        },
        "wbc": {
            "aliases": ("wbc", "bach cau", "white blood cell", "leukocyte", "so luong bach cau"),
            "purpose_vi": "Xét nghiệm WBC đo tổng số lượng bạch cầu trong máu, là thành phần quan trọng của hệ miễn dịch giúp chống lại nhiễm trùng và viêm.",
            "purpose_en": "WBC test measures total white blood cell count in blood, a critical component of the immune system fighting infections and inflammation.",
            "high_hint_vi": "Bạch cầu tăng cao thường là phản ứng tự nhiên của cơ thể khi có nhiễm trùng (vi khuẩn, virus), phản ứng viêm hoặc stress thể chất.",
            "high_hint_en": "Elevated WBC is commonly a physiological response to bacterial/viral infections, systemic inflammation, or physical stress.",
            "low_hint_vi": "Bạch cầu giảm thấp có thể làm giảm khả năng đề kháng, gặp trong nhiễm virus cấp, suy tủy hoặc tác dụng phụ của một số thuốc.",
            "low_hint_en": "Decreased WBC can lower immune defense, seen in acute viral infections, bone marrow suppression, or drug reactions.",
            "default_questions_vi": [
                "Sự thay đổi số lượng bạch cầu này có phù hợp với các triệu chứng lâm sàng hiện tại của tôi không?",
                "Có cần làm thêm công thức bạch cầu chi tiết (Neutrophil, Lymphocyte) hoặc xét nghiệm viêm (CRP) không?",
            ],
            "default_questions_en": [
                "Does this WBC change correlate with my current clinical symptoms?",
                "Do I need a differential count (Neutrophils, Lymphocytes) or inflammatory markers (CRP)?",
            ],
        },
    }

    @staticmethod
    def fold_text(text: str) -> str:
        """Normalize text to unaccented lowercase for robust matching."""
        normalized = unicodedata.normalize("NFD", text.lower())
        plain = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        plain = plain.replace("đ", "d").replace("Đ", "d")
        return re.sub(r"\s+", " ", plain).strip()

    @classmethod
    def _find_analyte_info(cls, analyte_name: str) -> dict[str, Any] | None:
        """Find analyte knowledge base entry by alias."""
        folded = cls.fold_text(analyte_name)
        for data in cls._ANALYTE_KNOWLEDGE.values():
            for alias in data["aliases"]:
                if alias in folded or folded in alias:
                    return data
        return None

    @classmethod
    def _parse_reference_range(
        cls, observed_value: str | float, ref_range: str | None
    ) -> tuple[Literal["normal", "abnormal_high", "abnormal_low", "unspecified"], str | None]:
        """Parse lab reference range and evaluate against observed value without inventing values.

        Returns (status_flag, parsed_range_text).
        """
        if not ref_range or not ref_range.strip():
            return "unspecified", None

        clean_range = ref_range.strip()

        # Try to parse observed value as float
        obs_num: float | None = None
        if isinstance(observed_value, (int, float)):
            obs_num = float(observed_value)
        else:
            # Extract first float pattern in observed_value
            match = re.search(r"[-+]?\d*\.?\d+", str(observed_value).replace(",", "."))
            if match:
                try:
                    obs_num = float(match.group(0))
                except ValueError:
                    obs_num = None

        if obs_num is None:
            return "unspecified", clean_range

        # Pattern 1: Lower - Upper (e.g. "4.0 - 5.6", "0.7-1.3", "4.0 to 5.6", "4.0 – 5.6")
        bound_match = re.search(
            r"([0-9]+(?:\.[0-9]+)?)\s*(?:-|–|—|to|\.\.)\s*([0-9]+(?:\.[0-9]+)?)",
            clean_range.replace(",", "."),
        )
        if bound_match:
            try:
                low = float(bound_match.group(1))
                high = float(bound_match.group(2))
                if obs_num < low:
                    return "abnormal_low", clean_range
                if obs_num > high:
                    return "abnormal_high", clean_range
                return "normal", clean_range
            except ValueError:
                pass

        # Pattern 2: Upper bound only (e.g. "< 5.7", "<= 100", "<130")
        less_match = re.search(r"(?:<|<=|≤)\s*([0-9]+(?:\.[0-9]+)?)", clean_range.replace(",", "."))
        if less_match:
            try:
                high = float(less_match.group(1))
                if obs_num > high:
                    return "abnormal_high", clean_range
                return "normal", clean_range
            except ValueError:
                pass

        # Pattern 3: Lower bound only (e.g. "> 60", ">= 90", "≥ 50")
        greater_match = re.search(
            r"(?:>|>=|≥)\s*([0-9]+(?:\.[0-9]+)?)", clean_range.replace(",", ".")
        )
        if greater_match:
            try:
                low = float(greater_match.group(1))
                if obs_num < low:
                    return "abnormal_low", clean_range
                return "normal", clean_range
            except ValueError:
                pass

        return "unspecified", clean_range

    @classmethod
    def explain(cls, result_input: LabResultInput) -> LabResultExplanation:
        """Generate patient-accessible, non-diagnostic explanation adhering to safety and fidelity invariants."""
        locale = result_input.locale
        is_vi = locale == "vi"

        # Ensure exact input string preservation for numeric fidelity
        obs_val_str = str(result_input.observed_value).strip()
        unit_str = result_input.unit.strip()
        analyte_name = result_input.analyte_name.strip()

        # Date formatting
        specimen_date_str: str | None = None
        if isinstance(result_input.specimen_date, (datetime, date)):
            specimen_date_str = result_input.specimen_date.strftime("%d/%m/%Y")
        elif result_input.specimen_date:
            specimen_date_str = str(result_input.specimen_date).strip()

        # 1. Reference range evaluation
        status_flag, parsed_range = cls._parse_reference_range(
            result_input.observed_value, result_input.reference_range
        )
        range_provided = parsed_range is not None and bool(parsed_range.strip())
        range_source: Literal["provided_by_lab", "not_provided"] = (
            "provided_by_lab" if range_provided else "not_provided"
        )

        # 2. Knowledge retrieval
        analyte_info = cls._find_analyte_info(analyte_name)

        if analyte_info:
            purpose = analyte_info["purpose_vi"] if is_vi else analyte_info["purpose_en"]
        else:
            purpose = (
                f"Xét nghiệm {analyte_name} là chỉ số xét nghiệm cận lâm sàng dùng để theo dõi tình trạng sức khỏe và hỗ trợ bác sĩ đánh giá chức năng các cơ quan trong cơ thể."
                if is_vi
                else f"The {analyte_name} test is a clinical biomarker used to monitor health status and evaluate organ functions."
            )

        # 3. Plain language interpretation
        val_with_unit = f"{obs_val_str} {unit_str}".strip()

        if not range_provided:
            # INVARIANT: NEVER invent a reference range if not provided by lab!
            if is_vi:
                interp = (
                    f"Kết quả xét nghiệm ghi nhận giá trị là {val_with_unit}. "
                    f"Phiếu kết quả từ phòng xét nghiệm KHÔNG kèm khoảng tham chiếu. "
                    f"Khoảng giá trị bình thường có thể thay đổi tùy thuộc vào phương pháp đo, hóa chất "
                    f"và thiết bị của từng phòng xét nghiệm cụ thể. Bạn nên trao đổi trực tiếp với bác sĩ điều trị để được diễn giải chính xác."
                )
            else:
                interp = (
                    f"The observed test value is {val_with_unit}. "
                    f"A reference range was NOT provided on the lab report. "
                    f"Standard reference intervals vary by laboratory methodology, reagents, and instruments. "
                    f"Please consult your healthcare provider for clinical correlation."
                )
        else:
            if status_flag == "normal":
                if is_vi:
                    interp = (
                        f"Kết quả xét nghiệm là {val_with_unit}, nằm trong khoảng tham chiếu ({parsed_range}) "
                        f"do phòng xét nghiệm cung cấp. Đây là chỉ số bình thường tại thời điểm lấy mẫu."
                    )
                else:
                    interp = (
                        f"The observed result is {val_with_unit}, which falls within the lab's reference range ({parsed_range}). "
                        f"This is within expected parameters at the time of sampling."
                    )
            elif status_flag == "abnormal_high":
                hint = (
                    analyte_info.get("high_hint_vi" if is_vi else "high_hint_en", "")
                    if analyte_info
                    else ""
                )
                if is_vi:
                    interp = (
                        f"Kết quả xét nghiệm là {val_with_unit}, CAO HƠN khoảng tham chiếu ({parsed_range}) "
                        f"của phòng xét nghiệm. {hint} "
                        f"Chỉ số cao có thể do nhiều yếu tố sinh lý, chế độ ăn, thuốc hoặc tình trạng sức khỏe tạm thời."
                    )
                else:
                    interp = (
                        f"The observed result is {val_with_unit}, which is HIGHER than the lab's reference range ({parsed_range}). {hint} "
                        f"An elevated level can be influenced by physiological factors, diet, medications, or health conditions."
                    )
            elif status_flag == "abnormal_low":
                hint = (
                    analyte_info.get("low_hint_vi" if is_vi else "low_hint_en", "")
                    if analyte_info
                    else ""
                )
                if is_vi:
                    interp = (
                        f"Kết quả xét nghiệm là {val_with_unit}, THẤP HƠN khoảng tham chiếu ({parsed_range}) "
                        f"của phòng xét nghiệm. {hint} "
                        f"Chỉ số thấp cần được bác sĩ đánh giá kết hợp với triệu chứng thực tế."
                    )
                else:
                    interp = (
                        f"The observed result is {val_with_unit}, which is LOWER than the lab's reference range ({parsed_range}). {hint} "
                        f"A low value should be evaluated in context with your clinical presentation."
                    )
            else:
                if is_vi:
                    interp = (
                        f"Kết quả xét nghiệm là {val_with_unit} (khoảng tham chiếu phòng xét nghiệm: {parsed_range}). "
                        f"Bác sĩ điều trị sẽ đánh giá chỉ số này cùng với bệnh cảnh lâm sàng tổng thể."
                    )
                else:
                    interp = (
                        f"The observed result is {val_with_unit} (lab reference interval: {parsed_range}). "
                        f"Your clinician will evaluate this parameter alongside your overall medical context."
                    )

        # 4. Mandatory non-diagnostic safety disclaimer
        disclaimer_vi = (
            "LƯU Ý QUAN TRỌNG: Kết quả xét nghiệm và chỉ số bất thường (nếu có) KHÔNG phải là một chẩn đoán bệnh lý. "
            "Một chỉ số đơn lẻ không thể khẳng định bạn mắc bệnh hay không. Bác sĩ cần kết hợp thăm khám lâm sàng, "
            "tiền sử bệnh và các triệu chứng hiện tại để đưa ra kết luận y khoa chính xác."
        )
        disclaimer_en = (
            "IMPORTANT NOTICE: A laboratory result or abnormal flag alone is NOT a medical diagnosis. "
            "A single biomarker cannot establish the presence or absence of disease. Your doctor must correlate "
            "this value with a physical examination, clinical history, and symptoms to make a clinical judgment."
        )
        disclaimer = disclaimer_vi if is_vi else disclaimer_en

        # 5. Targeted questions for clinician
        if analyte_info:
            questions = list(
                analyte_info["default_questions_vi" if is_vi else "default_questions_en"]
            )
        else:
            if is_vi:
                questions = [
                    f"Chỉ số {analyte_name} ({val_with_unit}) có ý nghĩa như thế nào đối với tình trạng sức khỏe hiện tại của tôi?",
                    "Tôi có cần làm lại xét nghiệm này hoặc làm thêm xét nghiệm bổ sung nào khác không?",
                    "Có cần điều chỉnh thuốc, chế độ ăn uống hoặc lối sống dựa trên kết quả này không?",
                ]
            else:
                questions = [
                    f"What does this {analyte_name} result ({val_with_unit}) indicate regarding my current health condition?",
                    "Do I need a repeat test or any additional diagnostic investigations?",
                    "Should I modify any medications, diet, or lifestyle habits based on this result?",
                ]

        explanation = LabResultExplanation(
            analyte_name=analyte_name,
            observed_value=obs_val_str,
            unit=unit_str,
            reference_range=parsed_range,
            reference_range_source=range_source,
            specimen_date=specimen_date_str,
            test_purpose=purpose,
            interpretation_summary=interp,
            status_flag=status_flag,
            non_diagnostic_disclaimer=disclaimer,
            questions_for_clinician=questions,
            fidelity_verified=True,
        )

        # Enforce numeric fidelity verification before returning
        cls.verify_fidelity(result_input, explanation)
        return explanation

    @classmethod
    def verify_fidelity(
        cls, result_input: LabResultInput, explanation: LabResultExplanation
    ) -> bool:
        """Strictly verify that observed numeric value and unit were preserved with 100% fidelity."""
        expected_val = str(result_input.observed_value).strip()
        expected_unit = result_input.unit.strip()

        if explanation.observed_value != expected_val:
            raise NumericFidelityError(
                f"Numeric fidelity violation: expected observed_value '{expected_val}', got '{explanation.observed_value}'"
            )
        if explanation.unit != expected_unit:
            raise NumericFidelityError(
                f"Numeric fidelity violation: expected unit '{expected_unit}', got '{explanation.unit}'"
            )

        # Verify that expected_val is present in interpretation summary
        if expected_val not in explanation.interpretation_summary:
            raise NumericFidelityError(
                f"Numeric fidelity violation: observed value '{expected_val}' is missing from interpretation summary text"
            )

        return True
