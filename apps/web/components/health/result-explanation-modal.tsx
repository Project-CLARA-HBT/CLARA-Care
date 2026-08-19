"use client";

import { useMemo } from "react";
import Link from "next/link";
import { Modal } from "@/components/ui/modal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { SourceBadge } from "@/components/health/source-badge";
import { formatLocaleDate } from "@/lib/i18n/catalog";
import type { HealthRecentResultDto } from "@/lib/api/v2-client";

export interface ResultExplanationModalProps {
  open: boolean;
  onClose: () => void;
  result: HealthRecentResultDto | null;
  locale?: "vi" | "en";
}

interface TestKnowledgeItem {
  purposeVi: string;
  purposeEn: string;
  explanationNormalVi: string;
  explanationNormalEn: string;
  explanationAbnormalVi: string;
  explanationAbnormalEn: string;
  questionsVi: string[];
  questionsEn: string[];
}

const TEST_KNOWLEDGE: Record<string, TestKnowledgeItem> = {
  glucose: {
    purposeVi: "Đo nồng độ đường trong máu tại thời điểm xét nghiệm nhằm sàng lọc, chẩn đoán và theo dõi bệnh Đái tháo đường hoặc hạ đường huyết.",
    purposeEn: "Measures blood sugar concentration to screen, diagnose, and monitor diabetes mellitus or hypoglycemia.",
    explanationNormalVi: "Chỉ số đường huyết của bạn nằm trong khoảng tham chiếu thông thường. Hãy duy trì chế độ ăn cân đối và lối sống năng động.",
    explanationNormalEn: "Your blood glucose level is within the standard reference range. Maintain a balanced diet and regular physical activity.",
    explanationAbnormalVi: "Chỉ số đường huyết nằm ngoài khoảng tham chiếu. Cần được bác sĩ xem xét cùng tình trạng nhịn ăn trước xét nghiệm và chỉ số HbA1c.",
    explanationAbnormalEn: "Your glucose level is outside the target range. A physician should review this alongside fasting status and HbA1c.",
    questionsVi: [
      "Chỉ số đường huyết này có cần làm lại lúc đói hay làm nghiệm pháp dung nạp glucose không?",
      "Tôi có cần điều chỉnh chế độ ăn uống, lượng tinh bột hoặc vận động không?",
      "Thuốc tôi đang dùng có ảnh hưởng gì đến đường huyết không?",
    ],
    questionsEn: [
      "Do I need a repeat fasting glucose or an oral glucose tolerance test?",
      "Should I make any dietary or exercise adjustments?",
      "Do any of my current medications impact my blood sugar?",
    ],
  },
  hba1c: {
    purposeVi: "Phản ánh mức đường huyết trung bình trong khoảng 2 - 3 tháng gần nhất, là tiêu chuẩn vàng để theo dõi kiểm soát bệnh đái tháo đường.",
    purposeEn: "Reflects your average blood sugar levels over the past 2–3 months, serving as the gold standard for long-term diabetes control.",
    explanationNormalVi: "Mức HbA1c dưới 5.7% cho thấy kiểm soát đường huyết tốt trong 3 tháng qua.",
    explanationNormalEn: "An HbA1c below 5.7% indicates healthy glycemic control over the past 3 months.",
    explanationAbnormalVi: "Mức HbA1c cao hơn bình thường cho thấy đường huyết trung bình trong 3 tháng qua đang tăng. Cần thảo luận với bác sĩ để tối ưu hóa phác đồ.",
    explanationAbnormalEn: "Elevated HbA1c indicates higher average blood glucose over the past 3 months. Discuss therapy optimization with your physician.",
    questionsVi: [
      "Mục tiêu HbA1c phù hợp nhất với độ tuổi và thể trạng của tôi là bao nhiêu?",
      "Tôi có cần bổ sung hoặc thay đổi liều thuốc hạ đường huyết không?",
      "Khi nào tôi nên làm lại xét nghiệm HbA1c (thường sau 3 tháng)?",
    ],
    questionsEn: [
      "What is my personalized HbA1c target given my age and health status?",
      "Do I need to adjust my medication dose or regimen?",
      "When is my next HbA1c retest recommended?",
    ],
  },
  cholesterol: {
    purposeVi: "Đánh giá bilan mỡ máu toàn phần nhằm ước tính nguy cơ xơ vữa động mạch và bệnh lý tim mạch.",
    purposeEn: "Evaluates total blood lipids to estimate cardiovascular and atherosclerotic disease risk.",
    explanationNormalVi: "Nồng độ cholesterol toàn phần trong giới hạn khuyến nghị, hỗ trợ bảo vệ thành mạch máu.",
    explanationNormalEn: "Total cholesterol is within the recommended interval, supporting vascular health.",
    explanationAbnormalVi: "Cholesterol toàn phần tăng cao có thể làm tăng nguy cơ lắng đọng mảng xơ vữa trong lòng mạch máu.",
    explanationAbnormalEn: "Elevated total cholesterol may increase the risk of plaque accumulation in blood vessels.",
    questionsVi: [
      "Tỷ lệ giữa các thành phần mỡ máu (LDL, HDL, Triglycerid) của tôi ra sao?",
      "Tôi có cần can thiệp bằng thuốc hạ mỡ máu (Statin) hay chỉ cần thay đổi lối sống?",
      "Tôi nên kiêng những loại thực phẩm cụ thể nào?",
    ],
    questionsEn: [
      "How do my specific lipid fractions (LDL, HDL, Triglycerides) balance out?",
      "Do I need lipid-lowering medication (e.g. statins) or lifestyle modifications?",
      "Which dietary modifications would benefit me most?",
    ],
  },
  alt: {
    purposeVi: "Đo nồng độ men Alanine Aminotransferase - một enzym chủ yếu ở tế bào gan, nhằm phát hiện tổn thương hoặc viêm gan.",
    purposeEn: "Measures Alanine Aminotransferase (ALT) enzyme levels, primarily found in liver cells, to detect hepatic inflammation or injury.",
    explanationNormalVi: "Men gan ALT ở mức bình thường, cho thấy tế bào gan không có dấu hiệu bị hoại tử hay viêm cấp.",
    explanationNormalEn: "ALT levels are within normal limits, suggesting no active acute liver cell injury.",
    explanationAbnormalVi: "Men gan ALT tăng cho thấy có tế bào gan đang bị tổn thương hoặc phóng thích enzym (do virus, rượu, thuốc, hoặc gan nhiễm mỡ).",
    explanationAbnormalEn: "Elevated ALT indicates liver cell stress or injury (e.g. viral infection, medications, alcohol, or fatty liver).",
    questionsVi: [
      "Men gan tăng có phải do các loại thuốc hoặc thực phẩm chức năng tôi đang dùng không?",
      "Tôi có cần làm thêm siêu âm ổ bụng hoặc xét nghiệm viêm gan B, C không?",
      "Tôi có cần dùng thuốc bổ trợ gan hoặc tái khám lại sau bao lâu?",
    ],
    questionsEn: [
      "Could any prescription drugs or supplements be causing this enzyme elevation?",
      "Should I undergo abdominal ultrasound or viral hepatitis serology?",
      "When should I repeat this liver panel?",
    ],
  },
  creatinine: {
    purposeVi: "Đo nồng độ chất thải creatinin trong máu do cơ bắp sinh ra để đánh giá chức năng lọc của cầu thận (eGFR).",
    purposeEn: "Measures serum creatinine waste to calculate estimated glomerular filtration rate (eGFR) and evaluate kidney function.",
    explanationNormalVi: "Chỉ số Creatinin bình thường phản ánh khả năng lọc và đào thải chất độc của hai thận hoạt động tốt.",
    explanationNormalEn: "Normal creatinine indicates adequate renal filtration and excretion capacity.",
    explanationAbnormalVi: "Creatinin tăng cao có thể là dấu hiệu suy giảm chức năng lọc của thận hoặc do mất nước, dùng thuốc độc cho thận, vận động gắng sức.",
    explanationAbnormalEn: "Elevated creatinine may indicate reduced renal filtration, dehydration, nephrotoxic medications, or strenuous exertion.",
    questionsVi: [
      "Mức lọc cầu thận ước tính (eGFR) của tôi hiện tại là bao nhiêu?",
      "Các loại thuốc tôi đang dùng có cần chỉnh liều theo chức năng thận không?",
      "Tôi có cần hạn chế đạm, muối hoặc uống thêm nước không?",
    ],
    questionsEn: [
      "What is my estimated glomerular filtration rate (eGFR)?",
      "Do any of my medications require renal dosage adjustment?",
      "Should I adjust dietary protein, salt, or fluid intake?",
    ],
  },
  cbc: {
    purposeVi: "Tổng phân tích tế bào máu ngoại vi: khảo sát dòng hồng cầu (thiếu máu), bạch cầu (nhiễm trùng/miễn dịch) và tiểu cầu (đông máu).",
    purposeEn: "Complete Blood Count (CBC): evaluates red blood cells (anemia), white blood cells (infection/immunity), and platelets (clotting).",
    explanationNormalVi: "Các dòng tế bào máu của bạn đều nằm trong khoảng tham chiếu cân bằng.",
    explanationNormalEn: "All blood cell lines are balanced and within standard physiological ranges.",
    explanationAbnormalVi: "Có sự biến động ở một hoặc nhiều dòng tế bào máu. Cần đối chiếu với triệu chứng lâm sàng như sốt, mệt mỏi, vết bầm tím.",
    explanationAbnormalEn: "One or more cell counts fall outside reference limits. Correlate with clinical symptoms such as fatigue, fever, or bruising.",
    questionsVi: [
      "Sự bất thường này có phải do tình trạng viêm nhiễm cấp tính hay thiếu vi chất (sắt, B12) không?",
      "Tôi có cần bổ sung vi chất hoặc làm xét nghiệm tủy đồ/huyết đồ chuyên sâu không?",
      "Bao lâu tôi nên kiểm tra lại công thức máu?",
    ],
    questionsEn: [
      "Does this abnormality reflect an acute infection or a nutritional deficiency (iron, B12)?",
      "Do I require targeted supplementation or further hematologic workup?",
      "When is a repeat CBC recommended?",
    ],
  },
};

function resolveKnowledge(testName: string, category?: string | null): TestKnowledgeItem {
  const normalized = (testName + " " + (category || "")).toLowerCase();

  if (normalized.includes("hba1c") || normalized.includes("a1c")) {
    return TEST_KNOWLEDGE.hba1c;
  }
  if (normalized.includes("glucose") || normalized.includes("đường") || normalized.includes("sugar")) {
    return TEST_KNOWLEDGE.glucose;
  }
  if (normalized.includes("cholesterol") || normalized.includes("lipid") || normalized.includes("triglycerid") || normalized.includes("ldl") || normalized.includes("hdl")) {
    return TEST_KNOWLEDGE.cholesterol;
  }
  if (normalized.includes("alt") || normalized.includes("ast") || normalized.includes("sgpt") || normalized.includes("sgot") || normalized.includes("men gan")) {
    return TEST_KNOWLEDGE.alt;
  }
  if (normalized.includes("creatinin") || normalized.includes("egfr") || normalized.includes("urê") || normalized.includes("ure") || normalized.includes("thận")) {
    return TEST_KNOWLEDGE.creatinine;
  }
  if (normalized.includes("cbc") || normalized.includes("huyết đồ") || normalized.includes("bạch cầu") || normalized.includes("hồng cầu") || normalized.includes("tiểu cầu") || normalized.includes("hemoglobin")) {
    return TEST_KNOWLEDGE.cbc;
  }

  return {
    purposeVi: `Xét nghiệm ${testName} được chỉ định để khảo sát và theo dõi các chỉ số sinh hóa, huyết học hoặc dấu ấn sinh học trong cơ thể.`,
    purposeEn: `The ${testName} diagnostic test evaluates biochemical, hematological, or biomarker parameters in your body.`,
    explanationNormalVi: `Chỉ số ${testName} của bạn đang nằm trong giới hạn tham chiếu thông thường của phòng xét nghiệm.`,
    explanationNormalEn: `Your ${testName} reading is within the standard laboratory reference range.`,
    explanationAbnormalVi: `Chỉ số ${testName} có sự chênh lệch so với khoảng tham chiếu tiêu chuẩn. Hãy trao đổi với bác sĩ để được giải thích chi tiết trong bối cảnh bệnh sử cá nhân.`,
    explanationAbnormalEn: `Your ${testName} reading deviates from standard reference limits. Consult your doctor for interpretation in your clinical context.`,
    questionsVi: [
      `Chỉ số ${testName} này có ý nghĩa gì đối với tình trạng sức khỏe hiện tại của tôi?`,
      "Tôi có cần làm thêm xét nghiệm chuyên sâu nào khác để xác định rõ hơn không?",
      "Khoảng bao lâu tôi nên xét nghiệm lại chỉ số này?",
    ],
    questionsEn: [
      `What does this ${testName} result mean for my overall health plan?`,
      "Are further confirmatory diagnostic tests recommended?",
      "When should I schedule a follow-up test?",
    ],
  };
}

function getStatusBadgeTone(flag?: string) {
  switch (flag?.toLowerCase()) {
    case "critical_high":
    case "critical_low":
    case "critical":
      return "danger";
    case "high":
    case "low":
    case "abnormal":
      return "warn";
    case "normal":
    default:
      return "ok";
  }
}

export function ResultExplanationModal({
  open,
  onClose,
  result,
  locale = "vi",
}: ResultExplanationModalProps) {
  const isEn = locale === "en";

  const knowledge = useMemo(() => {
    if (!result) return null;
    return resolveKnowledge(result.test_name, result.category);
  }, [result]);

  if (!result || !knowledge) return null;

  const isAbnormal =
    result.flag &&
    result.flag.toLowerCase() !== "normal" &&
    result.flag.toLowerCase() !== "ok";

  const formattedDate = result.effective_at
    ? formatLocaleDate(locale, result.effective_at, {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : "";

  const askUrl = `/ask?q=${encodeURIComponent(
    `Giải thích kết quả xét nghiệm ${result.test_name}: ${result.value} ${result.unit ?? ""}`,
  )}`;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEn ? `Lab Result: ${result.test_name}` : `Giải thích xét nghiệm: ${result.test_name}`}
      description={
        isEn
          ? "Plain-language explanation, reference intervals, clinical context, and doctor discussion questions."
          : "Giải thích ý nghĩa chỉ số, khoảng tham chiếu phòng lab, bối cảnh lâm sàng và câu hỏi gợi ý cho bác sĩ."
      }
      size="lg"
      closeLabel={isEn ? "Close" : "Đóng"}
    >
      <div className="space-y-5 text-sm" data-testid="result-explanation-content">
        {/* 1. Value & Status Banner */}
        <div className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 p-4 sm:p-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[color:var(--shell-border)]/60 pb-3">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-lg font-bold text-[var(--text-primary)]">
                  {result.test_name}
                </span>
                {result.category && (
                  <span className="rounded-[var(--radius-pill)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)] px-2.5 py-0.5 text-xs text-[var(--text-secondary)]">
                    {result.category}
                  </span>
                )}
                {result.flag && (
                  <Badge tone={getStatusBadgeTone(result.flag)}>
                    {result.flag.toUpperCase()}
                  </Badge>
                )}
              </div>
              {formattedDate && (
                <p className="mt-1 text-xs text-[var(--text-muted)]">
                  {isEn ? "Recorded at: " : "Thời gian thực hiện: "}{formattedDate}
                </p>
              )}
            </div>

            <div className="text-left sm:text-right">
              <div className="text-2xl font-extrabold text-[var(--text-primary)]">
                {result.value}{" "}
                <span className="text-sm font-normal text-[var(--text-secondary)]">
                  {result.unit ?? ""}
                </span>
              </div>
              {result.reference_range && (
                <span className="text-xs text-[var(--text-muted)] block mt-0.5">
                  {isEn ? "Reference interval: " : "Khoảng tham chiếu: "}{result.reference_range}
                </span>
              )}
            </div>
          </div>

          {result.source_name && (
            <div className="mt-2.5 flex items-center gap-2 text-xs text-[var(--text-secondary)]">
              <Icon name="scan" size="0.95rem" className="text-[var(--text-brand)]" />
              <span>
                {isEn ? "Testing Facility / Source: " : "Nguồn / Cơ sở thực hiện: "}
                <strong>{result.source_name}</strong>
              </span>
              {result.source_kind && (
                <SourceBadge sourceKind={result.source_kind} locale={locale} />
              )}
            </div>
          )}
        </div>

        {/* 2. Test Purpose */}
        <div className="space-y-1.5 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
          <div className="flex items-center gap-2 text-[var(--text-brand)]">
            <Icon name="clinical-notes" size="1.1rem" />
            <h3 className="font-semibold text-sm text-[var(--text-primary)]">
              {isEn ? "Why is this test done?" : "Tại sao làm xét nghiệm này?"}
            </h3>
          </div>
          <p className="text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed pt-1">
            {isEn ? knowledge.purposeEn : knowledge.purposeVi}
          </p>
        </div>

        {/* 3. Plain Language Explanation */}
        <div className="space-y-1.5 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
          <div className="flex items-center gap-2 text-[var(--brand-600)]">
            <Icon name="help" size="1.1rem" />
            <h3 className="font-semibold text-sm text-[var(--text-primary)]">
              {isEn ? "What does your result mean?" : "Ý nghĩa chỉ số của bạn"}
            </h3>
          </div>
          <p className="text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed pt-1">
            {isAbnormal
              ? isEn
                ? knowledge.explanationAbnormalEn
                : knowledge.explanationAbnormalVi
              : isEn
                ? knowledge.explanationNormalEn
                : knowledge.explanationNormalVi}
          </p>
        </div>

        {/* 4. Questions to Ask Doctor */}
        <div className="space-y-2 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
          <div className="flex items-center gap-2 text-[var(--text-brand)]">
            <Icon name="contact" size="1.1rem" />
            <h3 className="font-semibold text-sm text-[var(--text-primary)]">
              {isEn ? "Questions to Ask Your Doctor" : "Câu hỏi gợi ý khi trao đổi với bác sĩ"}
            </h3>
          </div>
          <ul className="mt-2 space-y-2 text-xs sm:text-sm text-[var(--text-secondary)]">
            {(isEn ? knowledge.questionsEn : knowledge.questionsVi).map((q, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="mt-1 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--brand-500)]" />
                <span>{q}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* 5. Historical Trend Table if history exists */}
        {result.history && result.history.length > 1 && (
          <div className="space-y-2 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
            <div className="flex items-center gap-2 text-[var(--text-brand)]">
              <Icon name="progress" size="1.1rem" />
              <h3 className="font-semibold text-sm text-[var(--text-primary)]">
                {isEn ? "Historical Test Measurements" : "Lịch sử các lần xét nghiệm"}
              </h3>
            </div>
            <div className="overflow-x-auto pt-1">
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="border-b border-[color:var(--shell-border)] text-[var(--text-muted)]">
                    <th className="py-1.5">{isEn ? "Date" : "Ngày"}</th>
                    <th className="py-1.5">{isEn ? "Value" : "Giá trị"}</th>
                    <th className="py-1.5">{isEn ? "Status" : "Trạng thái"}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[color:var(--shell-border)]/40">
                  {result.history.map((item, idx) => (
                    <tr key={idx} className="text-[var(--text-secondary)]">
                      <td className="py-1.5">{item.effective_at}</td>
                      <td className="py-1.5 font-semibold text-[var(--text-primary)]">
                        {item.value} {item.unit ?? result.unit}
                      </td>
                      <td className="py-1.5">
                        <Badge tone={getStatusBadgeTone(item.flag)}>
                          {item.flag ?? "normal"}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* 6. Medical Disclaimer */}
        <div className="rounded-[var(--radius-md)] bg-[var(--surface-muted)]/60 p-3 text-[11px] text-[var(--text-muted)] leading-relaxed">
          {isEn
            ? "Note: CLARA provides reference explanation only and does not replace clinical judgment. Diagnostic values must always be interpreted in combination with your medical history and clinical examination."
            : "Lưu ý: Thông tin giải thích chỉ mang tính tham khảo và hỗ trợ hiểu biết y khoa. Kết quả xét nghiệm cần được bác sĩ chuyên khoa phân tích trong tương quan lâm sàng tổng thể."}
        </div>

        {/* 7. Action Footer */}
        <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
          <Link
            href={askUrl}
            onClick={onClose}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--text-brand)] hover:underline"
          >
            <Icon name="chat" size="0.95rem" />
            <span>
              {isEn ? "Ask CLARA more about this result" : "Hỏi CLARA thêm về chỉ số này"}
            </span>
            <Icon name="arrow-right" size="0.8rem" />
          </Link>

          <Button variant="secondary" size="sm" onClick={onClose}>
            {isEn ? "Close" : "Đóng"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

export default ResultExplanationModal;
