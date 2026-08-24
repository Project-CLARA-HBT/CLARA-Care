"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import Button from "@/components/ui/button";
import { Icon, resolveIconName, type IconName } from "@/components/ui/icon";
import { Badge } from "@/components/ui/badge";
import { SurfaceCard } from "@/components/ui/surface";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import { PRIMARY_ACTIONS, type PrimarySurface } from "@/lib/primary-actions";
import {
  getStoredUILanguage,
  onUILanguageChange,
  type UILanguage,
} from "@/lib/ui-language";

export type RoleCategory = "all" | "consumer" | "clinical" | "research" | "admin";

export type GuideIllustration = {
  stepBadge: string;
  titleVi: string;
  titleEn: string;
  descVi: string;
  descEn: string;
  snippetType: "input" | "guardrail" | "output" | "system";
  snippetHeader: string;
  snippetBody: string;
  snippetTag?: string;
};

export type GuideTask = {
  id: string;
  titleKey?: UITranslationKey;
  titleVi?: string;
  titleEn?: string;
  detailKey?: UITranslationKey;
  detailVi?: string;
  detailEn?: string;
  surface?: PrimarySurface;
  href?: string;
  icon: IconName;
  recommendedToolVi: string;
  recommendedToolEn: string;
  roleScope: "consumer" | "clinical" | "research" | "admin";
  keywords: string[];
  readTime: string;
  steps: [UITranslationKey, UITranslationKey, UITranslationKey] | [string, string, string];
  actionKey?: UITranslationKey;
  actionVi?: string;
  actionEn?: string;
  illustrations: [GuideIllustration, GuideIllustration, GuideIllustration];
  bestPracticesVi: string[];
  bestPracticesEn: string[];
  safetyNoteVi: string;
  safetyNoteEn: string;
};

const TASKS: GuideTask[] = [
  // 1. Personal: Hỏi CLARA (Chat)
  {
    id: "chat",
    titleKey: "guide.tasks.chat.title",
    detailKey: "guide.tasks.chat.detail",
    surface: "chat",
    href: "/chat",
    icon: "chat",
    recommendedToolVi: "CÔNG CỤ KHUYÊN DÙNG: HỎI CLARA",
    recommendedToolEn: "RECOMMENDED: CLARA ASK",
    roleScope: "consumer",
    keywords: ["hỏi", "triệu chứng", "dùng thuốc", "chat", "ask", "cơ bản", "an toàn"],
    readTime: "2 phút",
    steps: ["guide.tasks.chat.step1", "guide.tasks.chat.step2", "guide.tasks.chat.step3"],
    actionKey: "guide.tasks.chat.action",
    illustrations: [
      {
        stepBadge: "Bước 1",
        titleVi: "Nhập câu hỏi bằng ngôn ngữ tự nhiên",
        titleEn: "Ask your question in natural language",
        descVi: "Mô tả triệu chứng, độ tuổi hoặc tên thuốc bạn đang băn khoăn.",
        descEn: "Describe symptoms, age or medicine questions in plain language.",
        snippetType: "input",
        snippetHeader: "Ô nhập câu hỏi · Chế độ Nhanh",
        snippetBody: "\"Tôi bị đau đầu kèm sốt nhẹ 38°C từ chiều qua, có thể dùng thuốc gì để hạ sốt an toàn?\"",
        snippetTag: "Độ tuổi: 32 · Không dị ứng đã biết",
      },
      {
        stepBadge: "Bước 2",
        titleVi: "Rà soát an toàn & Phác đồ điều trị",
        titleEn: "Safety screening & Guideline matching",
        descVi: "Hệ thống FIDES kiểm tra chống chỉ định, liều lượng và cảnh báo cấp cứu khẩn cấp.",
        descEn: "FIDES safety engine screens for contraindications, dosage and red-flag alerts.",
        snippetType: "guardrail",
        snippetHeader: "FIDES Clinical Guardrail · Trực tuyến",
        snippetBody: "Trạng thái: An toàn cơ bản · Rà soát phác đồ BYT Sốt/Đau đầu · Loại trừ dấu hiệu cảnh báo khẩn",
        snippetTag: "FIDES PASS",
      },
      {
        stepBadge: "Bước 3",
        titleVi: "Đọc phần lưu ý an toàn trước khi áp dụng",
        titleEn: "Read safety guidance before taking action",
        descVi: "Xem cấu trúc giải đáp, hướng xử trí ban đầu và khi nào cần đến cơ sở y tế.",
        descEn: "Review structured recommendations, initial home care and when to seek urgent medical care.",
        snippetType: "output",
        snippetHeader: "Giải đáp có cấu trúc từ CLARA",
        snippetBody: "Paracetamol 500mg (1 viên mỗi 4-6 giờ, tối đa 2g/ngày). Cần đi khám ngay nếu sốt > 39°C hoặc kèm cứng cổ.",
        snippetTag: "Có trích dẫn nguồn",
      },
    ],
    bestPracticesVi: [
      "Luôn cung cấp thêm thông tin về bệnh nền hoặc tình trạng mang thai/cho con bú nếu có.",
      "Không tự ý tăng liều thuốc vượt quá khuyến cáo ghi trên nhãn phụ.",
    ],
    bestPracticesEn: [
      "Always mention underlying conditions, pregnancy or breastfeeding status if applicable.",
      "Never exceed recommended maximum daily dosages without a physician's advice.",
    ],
    safetyNoteVi: "CLARA chỉ hỗ trợ thông tin tham khảo ban đầu, không thay thế chẩn đoán hay đơn thuốc từ bác sĩ chuyên khoa.",
    safetyNoteEn: "CLARA provides decision-support information only and is not a substitute for a licensed doctor's diagnosis or prescription.",
  },

  // 2. Personal: Tủ thuốc (Medicine Cabinet)
  {
    id: "cabinet",
    titleKey: "guide.tasks.cabinet.title",
    detailKey: "guide.tasks.cabinet.detail",
    surface: "selfmed",
    href: "/medicines?tab=cabinet",
    icon: "medication",
    recommendedToolVi: "CÔNG CỤ KHUYÊN DÙNG: TỦ THUỐC",
    recommendedToolEn: "RECOMMENDED: MED CABINET",
    roleScope: "consumer",
    keywords: ["tủ thuốc", "lưu thuốc", "uống thuốc", "đơn thuốc", "cabinet", "thuốc đang dùng"],
    readTime: "3 phút",
    steps: ["guide.tasks.cabinet.step1", "guide.tasks.cabinet.step2", "guide.tasks.cabinet.step3"],
    actionKey: "guide.tasks.cabinet.action",
    illustrations: [
      {
        stepBadge: "Bước 1",
        titleVi: "Thêm thuốc hoặc quét ảnh đơn thuốc (OCR)",
        titleEn: "Add medicines or scan prescription photo (OCR)",
        descVi: "Chụp ảnh nhãn thuốc hoặc nhập tên hoạt chất vào tủ thuốc cá nhân.",
        descEn: "Capture a photo of the medicine box or type active ingredients into your cabinet.",
        snippetType: "input",
        snippetHeader: "Thêm thuốc vào tủ · Nhận diện tự động",
        snippetBody: "Hoạt chất: Amlodipine 5mg · Dạng: Viên nén · Chỉ định: Huyết áp",
        snippetTag: "OCR Đã trích xuất",
      },
      {
        stepBadge: "Bước 2",
        titleVi: "Bổ sung liều lượng & Giờ uống",
        titleEn: "Enter dosage & Schedule reminders",
        descVi: "Ghi nhận liều dùng mỗi ngày (sáng/tối) để CLARA theo dõi và cảnh báo tương tác.",
        descEn: "Set daily dosage schedule so CLARA can track compliance and detect conflicts.",
        snippetType: "guardrail",
        snippetHeader: "Hồ sơ thuốc đang dùng",
        snippetBody: "1. Amlodipine 5mg (1 viên/sáng)\n2. Atorvastatin 20mg (1 viên/tối)",
        snippetTag: "Đã lưu 2 loại thuốc",
      },
      {
        stepBadge: "Bước 3",
        titleVi: "Kích hoạt kiểm tra an toàn tương tác thuốc",
        titleEn: "Run interaction and allergy safety check",
        descVi: "Hệ thống tự động phát hiện các cặp thuốc tương kỵ hoặc trùng lặp hoạt chất.",
        descEn: "The system automatically evaluates drug pairs for adverse interactions or duplications.",
        snippetType: "output",
        snippetHeader: "Báo cáo an toàn tủ thuốc",
        snippetBody: "Không ghi nhận tương tác nguy hiểm giữa Amlodipine và Atorvastatin. Đơn thuốc phù hợp.",
        snippetTag: "Tủ thuốc An Toàn",
      },
    ],
    bestPracticesVi: [
      "Cập nhật lại tủ thuốc ngay khi bác sĩ thay đổi đơn hoặc bạn ngừng dùng một loại thuốc.",
      "Ghi chú rõ thực phẩm chức năng và thảo dược đang dùng song song.",
    ],
    bestPracticesEn: [
      "Update your cabinet whenever your prescription changes or you stop a medication.",
      "Include dietary supplements and herbal remedies for a complete safety check.",
    ],
    safetyNoteVi: "Hãy kiểm tra lại nhãn gốc của thuốc trước khi uống, không lưu trữ thuốc đã hết hạn sử dụng.",
    safetyNoteEn: "Always verify physical pill bottles before taking medicine. Discard expired drugs safely.",
  },

  // 3. Personal: Kiểm tra tương tác thuốc (DDI)
  {
    id: "interactions",
    titleKey: "guide.tasks.interactions.title",
    detailKey: "guide.tasks.interactions.detail",
    surface: "ddi",
    href: "/medicines?tab=safety",
    icon: "warning",
    recommendedToolVi: "CÔNG CỤ KHUYÊN DÙNG: KIỂM TRA TƯƠNG TÁC (DDI)",
    recommendedToolEn: "RECOMMENDED: DDI SAFETY ENGINE",
    roleScope: "consumer",
    keywords: ["kiểm tra tương tác", "tương tác thuốc", "chống chỉ định", "ddi", "thuốc", "an toàn"],
    readTime: "3 phút",
    steps: ["guide.tasks.interactions.step1", "guide.tasks.interactions.step2", "guide.tasks.interactions.step3"],
    actionKey: "guide.tasks.interactions.action",
    illustrations: [
      {
        stepBadge: "Bước 1",
        titleVi: "Chọn ít nhất 2 loại thuốc cần phối hợp",
        titleEn: "Select at least 2 medications to check",
        descVi: "Chọn từ danh sách tủ thuốc hoặc thêm nhanh 2 tên thuốc bạn chuẩn bị uống.",
        descEn: "Select from your cabinet or enter two medications you intend to take concurrently.",
        snippetType: "input",
        snippetHeader: "Cặp thuốc kiểm tra tương tác",
        snippetBody: "Thuốc A: Clopidogrel 75mg (Kháng kết tập tiểu cầu)\nThuốc B: Omeprazole 20mg (Ức chế bơm proton)",
        snippetTag: "2 Thuốc",
      },
      {
        stepBadge: "Bước 2",
        titleVi: "Đối chiếu cơ sở dữ liệu DrugBank & BYT",
        titleEn: "Cross-reference DrugBank & Ministry of Health databases",
        descVi: "Công cụ DDI phân tích cơ chế chuyển hóa gan qua enzym CYP2C19.",
        descEn: "The DDI engine checks hepatic metabolic pathways via CYP2C19 isoenzymes.",
        snippetType: "guardrail",
        snippetHeader: "DDI Safety Analysis Engine",
        snippetBody: "Phát hiện tương tác mức độ: TRUNG BÌNH (Omeprazole làm giảm hoạt tính chống đông của Clopidogrel)",
        snippetTag: "Cảnh báo DDI",
      },
      {
        stepBadge: "Bước 3",
        titleVi: "Đọc khuyến nghị xử trí lâm sàng",
        titleEn: "Review clinical management recommendation",
        descVi: "Xem giải pháp thay thế an toàn hơn (ví dụ: Pantoprazole) và thảo luận cùng bác sĩ.",
        descEn: "Explore safer alternative options (e.g. Pantoprazole) to discuss with your doctor.",
        snippetType: "output",
        snippetHeader: "Khuyến nghị từ DDI Engine",
        snippetBody: "Nên cân nhắc đổi Omeprazole sang Pantoprazole hoặc dùng cách nhau ít nhất 12 giờ.",
        snippetTag: "Đã xác thực",
      },
    ],
    bestPracticesVi: [
      "Không tự ý ngừng thuốc chống đông đột ngột mà không hỏi ý kiến bác sĩ điều trị.",
      "Thông báo cho bác sĩ tất cả các loại thuốc dạ dày, giảm đau không kê đơn bạn đang dùng.",
    ],
    bestPracticesEn: [
      "Never discontinue antithrombotic medications abruptly without physician guidance.",
      "Inform your healthcare provider about all OTC antacids and NSAIDs you take.",
    ],
    safetyNoteVi: "Các cảnh báo tương tác thuốc mang tính hỗ trợ phòng ngừa, bác sĩ là người đưa ra quyết định phối hợp sau cùng.",
    safetyNoteEn: "DDI alerts provide precautionary guidance. Your prescribing doctor makes the final clinical decision.",
  },

  // 4. Clinical: Hội chẩn đa chuyên khoa (Council AI)
  {
    id: "council",
    titleKey: "guide.tasks.council.title",
    detailKey: "guide.tasks.council.detail",
    surface: "council",
    href: "/council",
    icon: "contact",
    recommendedToolVi: "CÔNG CỤ KHUYÊN DÙNG: HỘI CHẨN (COUNCIL)",
    recommendedToolEn: "RECOMMENDED: COUNCIL AI",
    roleScope: "clinical",
    keywords: ["hội chẩn", "đa chuyên khoa", "ca khó", "council", "bác sĩ", "chuyên khoa"],
    readTime: "4 phút",
    steps: ["guide.tasks.council.step1", "guide.tasks.council.step2", "guide.tasks.council.step3"],
    actionKey: "guide.tasks.council.action",
    illustrations: [
      {
        stepBadge: "Bước 1",
        titleVi: "Nhập bối cảnh ca bệnh & Chỉ số cận lâm sàng",
        titleEn: "Enter clinical context & Diagnostic lab values",
        descVi: "Cung cấp tiền sử bệnh, triệu chứng hiện tại, kết quả xét nghiệm máu, hình ảnh học.",
        descEn: "Provide patient history, current presentation, blood work, and imaging findings.",
        snippetType: "input",
        snippetHeader: "Council Case Intake · Nam 68t",
        snippetBody: "Tiền sử: ĐTĐ type 2, THA, CKD gđ 3b (eGFR 38). Nhập viện vì suy tim mất bù cấp kèm phù chi dưới.",
        snippetTag: "Cận lâm sàng: NT-proBNP 4200, K+ 5.2",
      },
      {
        stepBadge: "Bước 2",
        titleVi: "Kích hoạt phiên thảo luận đa chuyên khoa (Council Consensus)",
        titleEn: "Run multi-specialist debate (Council Consensus)",
        descVi: "Các chuyên gia Tim mạch, Thận học và Nội tiết cùng phân tích và phản biện phác đồ.",
        descEn: "Cardiology, Nephrology, and Endocrinology agents evaluate options and resolve trade-offs.",
        snippetType: "guardrail",
        snippetHeader: "Council Specialist Panel Consensus",
        snippetBody: "Tim mạch: Khuyến nghị SGLT2i + Lợi tiểu quai.\nThận học: Cảnh báo theo dõi sát eGFR và Kali máu trong 7 ngày đầu.",
        snippetTag: "Đồng thuận 3 chuyên khoa",
      },
      {
        stepBadge: "Bước 3",
        titleVi: "Xem bản tổng hợp & Trích dẫn hướng dẫn điều trị",
        titleEn: "Inspect synthesis & Evidence citations",
        descVi: "Nhận báo cáo tổng hợp có phân tích lợi ích/nguy cơ kèm trích dẫn phác đồ ESC/KDIGO.",
        descEn: "Receive a structured synthesis report with benefit/risk analysis and ESC/KDIGO citations.",
        snippetType: "output",
        snippetHeader: "Tổng hợp đề xuất lâm sàng",
        snippetBody: "Phác đồ ưu tiên: Bắt đầu Dapagliflozin 10mg + Furosemide 40mg IV ngắt quãng. Tái đánh giá ion đồ sau 48h.",
        snippetTag: "Tham khảo chuyên môn",
      },
    ],
    bestPracticesVi: [
      "Cung cấp đầy đủ chỉ số chức năng thận (Creatinine, eGFR) và điện giải đồ để chuyên gia thận đánh giá chính xác.",
      "Đối chiếu kết quả hội chẩn AI với hướng dẫn chẩn đoán và điều trị của Bộ Y tế Việt Nam.",
    ],
    bestPracticesEn: [
      "Always supply complete renal function indices (Creatinine, eGFR) and electrolytes for accurate nephrology review.",
      "Cross-check Council AI recommendations with current institutional guidelines.",
    ],
    safetyNoteVi: "Council AI là hệ thống hỗ trợ ra quyết định lâm sàng (CDSS), không thay thế trách nhiệm pháp lý của bác sĩ điều trị.",
    safetyNoteEn: "Council AI is a clinical decision-support system (CDSS) and does not replace the attending physician's clinical responsibility.",
  },

  // 5. Clinical: Ghi chép y khoa (Clinical Scribe)
  {
    id: "scribe",
    titleKey: "guide.tasks.scribe.title",
    detailKey: "guide.tasks.scribe.detail",
    surface: "scribe",
    href: "/scribe",
    icon: "mic",
    recommendedToolVi: "CÔNG CỤ KHUYÊN DÙNG: GHI CHÉP (SCRIBE)",
    recommendedToolEn: "RECOMMENDED: CLINICAL SCRIBE",
    roleScope: "clinical",
    keywords: ["ghi âm", "buổi khám", "ghi chép", "scribe", "bệnh án", "soap", "âm thanh", "ghi lại"],
    readTime: "3 phút",
    steps: ["guide.tasks.scribe.step1", "guide.tasks.scribe.step2", "guide.tasks.scribe.step3"],
    actionKey: "guide.tasks.scribe.action",
    illustrations: [
      {
        stepBadge: "Bước 1",
        titleVi: "Ghi âm hoặc dán nội dung đối thoại buổi khám",
        titleEn: "Record or paste consultation audio/transcript",
        descVi: "Ghi âm trực tiếp cuộc trao đổi giữa bác sĩ và bệnh nhân hoặc dán biên bản thoại thô.",
        descEn: "Record the clinical conversation live or paste raw consultation speech transcripts.",
        snippetType: "input",
        snippetHeader: "Clinical Audio Stream · Ghi âm trực tiếp",
        snippetBody: "\"Bác sĩ: Bác thấy tức ngực khi leo cầu thang lâu chưa? Bệnh nhân: Dạ khoảng 2 tuần nay, nghỉ thì đỡ đau...\"",
        snippetTag: "ASR Faster-Whisper",
      },
      {
        stepBadge: "Bước 2",
        titleVi: "Trích xuất & Cấu trúc hóa theo chuẩn SOAP",
        titleEn: "Extract & Structure into SOAP format",
        descVi: "CLARA tự động phân loại thông tin vào 4 phần: Subjective, Objective, Assessment, Plan.",
        descEn: "CLARA parses clinical dialogues into Subjective, Objective, Assessment, and Plan sections.",
        snippetType: "guardrail",
        snippetHeader: "SOAP Structuring Engine",
        snippetBody: "S: Đau thắt ngực khi gắng sức 2 tuần.\nO: HA 135/85 mmHg, T1 T2 đều.\nA: Cơn đau thắt ngực ổn định nghi do bệnh mạch vành.\nP: Chỉ định ECG gắng sức, Siêu âm tim.",
        snippetTag: "Chuẩn SOAP Y Khoa",
      },
      {
        stepBadge: "Bước 3",
        titleVi: "Kiểm tra, chỉnh sửa & Xuất hồ sơ bệnh án",
        titleEn: "Review, edit & Export medical record",
        descVi: "Bác sĩ rà soát lại thông tin trước khi ký duyệt hoặc sao chép vào hệ thống EMR/HIS.",
        descEn: "Clinicians review and finalize the structured record before committing to EMR/HIS.",
        snippetType: "output",
        snippetHeader: "Bản tóm tắt bệnh án sẵn sàng xuất",
        snippetBody: "Đã hoàn tất kiểm tra lâm sàng · Không chứa PII ngoài ý muốn · Sẵn sàng đồng bộ.",
        snippetTag: "Đã ký duyệt",
      },
    ],
    bestPracticesVi: [
      "Luôn thông báo và nhận được sự đồng ý của bệnh nhân trước khi bật tính năng ghi âm buổi khám.",
      "Rà soát kỹ tên thuốc và liều dùng trong phần Kế hoạch (Plan) trước khi xác nhận lưu bệnh án.",
    ],
    bestPracticesEn: [
      "Obtain informed patient consent before initiating ambient recording in examination rooms.",
      "Carefully verify all medication dosages in the Plan section before exporting to EMR.",
    ],
    safetyNoteVi: "Hệ thống ASR/Scribe xử lý âm thanh trong môi trường an toàn, không lưu trữ tệp âm thanh nhạy cảm sau phiên làm việc.",
    safetyNoteEn: "ASR/Scribe processes audio ephemerally in a secure sandbox and discards raw voice files post-transcription.",
  },

  // 6. Clinical: Tư duy y khoa sâu (Thinking Mode)
  {
    id: "thinking",
    titleKey: "guide.tasks.thinking.title",
    detailKey: "guide.tasks.thinking.detail",
    surface: "chat_thinking",
    href: "/chat",
    icon: "clinical-notes",
    recommendedToolVi: "CÔNG CỤ KHUYÊN DÙNG: TƯ DUY Y KHOA",
    recommendedToolEn: "RECOMMENDED: DEEP THINKING",
    roleScope: "clinical",
    keywords: ["tư duy", "sâu", "chi tiết", "phân tích", "thinking", "kỹ hơn"],
    readTime: "3 phút",
    steps: ["guide.tasks.thinking.step1", "guide.tasks.thinking.step2", "guide.tasks.thinking.step3"],
    actionKey: "guide.tasks.thinking.action",
    illustrations: [
      {
        stepBadge: "Bước 1",
        titleVi: "Bật chế độ Tư duy (Thinking) hoặc Pro",
        titleEn: "Switch to Thinking or Pro mode",
        descVi: "Mở menu chế độ bên cạnh ô nhập để kích hoạt mô hình suy luận chuỗi tư duy y khoa.",
        descEn: "Toggle mode selector beside chat composer to activate deep clinical chain-of-thought reasoning.",
        snippetType: "input",
        snippetHeader: "Bộ chọn chế độ AI · Chế độ Tư duy",
        snippetBody: "Chế độ: Tư duy (Deep Reasoning) · Nguồn: Đầy đủ nguồn y văn",
        snippetTag: "Tư duy sâu",
      },
      {
        stepBadge: "Bước 2",
        titleVi: "Phân tích chuỗi suy luận từng bước (Zero-CoT)",
        titleEn: "Step-by-step clinical chain-of-thought (Zero-CoT)",
        descVi: "CLARA phân tích sâu các cơ chế sinh lý bệnh, chẩn đoán phân biệt và các nghiên cứu lâm sàng.",
        descEn: "CLARA explores pathophysiology mechanisms, differential diagnoses, and trial evidence.",
        snippetType: "guardrail",
        snippetHeader: "Suy luận chuỗi tư duy y khoa",
        snippetBody: "1. Đánh giá khả năng viêm mạch máu so với xơ vữa động mạch.\n2. Phân tích tác động của các thuốc ức chế miễn dịch.\n3. Rà soát tương tác trên enzym CYP3A4.",
        snippetTag: "Lập luận đa chiều",
      },
      {
        stepBadge: "Bước 3",
        titleVi: "Nhận báo cáo tổng hợp chuyên sâu kèm tài liệu tham khảo",
        titleEn: "Receive in-depth synthesis with peer-reviewed citations",
        descVi: "Xem báo cáo y khoa chi tiết với danh mục tài liệu từ PubMed, BMJ và Bộ Y tế.",
        descEn: "View comprehensive clinical reports with citations from PubMed, BMJ, and VN-MOH guidelines.",
        snippetType: "output",
        snippetHeader: "Báo cáo tư duy lâm sàng chuyên sâu",
        snippetBody: "Kết luận: Cần thực hiện sinh thiết da có tổn thương để khẳng định chẩn đoán viêm mạch trước khi dùng Corticoid liều cao.",
        snippetTag: "Trích dẫn PubMed",
      },
    ],
    bestPracticesVi: [
      "Dùng chế độ Tư duy khi đối mặt với các ca bệnh hiếm gặp, triệu chứng phức tạp hoặc khó lý giải bằng phác đồ thông thường.",
      "Kiểm tra kỹ các trích dẫn bằng chứng và liên kết DOI đính kèm trong câu trả lời.",
    ],
    bestPracticesEn: [
      "Use Thinking mode for atypical presentations, rare conditions or complex differential diagnoses.",
      "Inspect linked DOI references and guideline citations provided alongside the response.",
    ],
    safetyNoteVi: "Mọi chuỗi lập luận tư duy đều tuân thủ nguyên tắc bảo mật Zero-CoT, không lưu vết thông tin nhận diện người bệnh.",
    safetyNoteEn: "All chain-of-thought reasoning adheres to Zero-CoT privacy standards without logging patient identifiers.",
  },

  // 7. Research: Truy xuất y văn & Bằng chứng lâm sàng (Evidence & PubMed)
  {
    id: "evidence",
    titleVi: "Truy xuất y văn & Tổng hợp bằng chứng lâm sàng",
    titleEn: "Retrieve clinical evidence & Synthesize medical literature",
    detailVi: "Tra cứu các nghiên cứu thử nghiệm lâm sàng ngẫu nhiên (RCT), meta-analysis và guideline Bộ Y tế.",
    detailEn: "Search randomized clinical trials (RCT), meta-analyses, and Ministry of Health clinical guidelines.",
    href: "/evidence",
    icon: "search",
    recommendedToolVi: "CÔNG CỤ KHUYÊN DÙNG: TỔNG HỢP BẰNG CHỨNG",
    recommendedToolEn: "RECOMMENDED: EVIDENCE SYNTHESIS",
    roleScope: "research",
    keywords: ["nghiên cứu", "y văn", "bằng chứng", "evidence", "pubmed", "rct", "thử nghiệm", "meta-analysis"],
    readTime: "4 phút",
    steps: [
      "Nhập chủ đề nghiên cứu hoặc câu hỏi can thiệp PICO.",
      "Hệ thống RAG truy xuất kho dữ liệu PubMed, Cochrane và BYT.",
      "Đọc báo cáo tổng hợp bằng chứng với đánh giá mức độ tin cậy."
    ],
    actionVi: "Mở tổng hợp bằng chứng",
    actionEn: "Open Evidence Synthesis",
    illustrations: [
      {
        stepBadge: "Bước 1",
        titleVi: "Nhập câu hỏi nghiên cứu PICO",
        titleEn: "Formulate a PICO clinical research question",
        descVi: "Xác định Quần thể (P), Can thiệp (I), Đối chứng (C) và Kết cục (O).",
        descEn: "Specify Population, Intervention, Comparison, and Outcome parameters.",
        snippetType: "input",
        snippetHeader: "PICO Evidence Search",
        snippetBody: "P: Bệnh nhân suy tim EF bảo tồn (HFpEF)\nI: Thuốc ức chế SGLT2 (Empagliflozin)\nC: Placebo\nO: Tỷ lệ tái nhập viện và tử vong do tim mạch",
        snippetTag: "PICO Protocol",
      },
      {
        stepBadge: "Bước 2",
        titleVi: "Truy xuất RAG & Đánh giá mức độ bằng chứng (GRADE)",
        titleEn: "RAG Retrieval & GRADE Evidence Quality Assessment",
        descVi: "Hệ thống tổng hợp dữ liệu từ thử nghiệm EMPEROR-Preserved và phân loại chất lượng bằng chứng.",
        descEn: "The pipeline retrieves trials like EMPEROR-Preserved and assigns GRADE trust tiers.",
        snippetType: "guardrail",
        snippetHeader: "Evidence Pipeline · Trust Tier A1",
        snippetBody: "Nguồn: NEJM (2021) · Mẫu: 5,988 BN · HR: 0.79 (95% CI 0.69-0.90, p<0.001)",
        snippetTag: "GRADE High Quality",
      },
      {
        stepBadge: "Bước 3",
        titleVi: "Xem báo cáo tổng hợp & Trích dẫn học thuật",
        titleEn: "Examine systematic synthesis & DOI citations",
        descVi: "Xuất dữ liệu tham khảo cho đề tài nghiên cứu hoặc cập nhật phác đồ điều trị bệnh viện.",
        descEn: "Export structured literature summaries for clinical research or formulary reviews.",
        snippetType: "output",
        snippetHeader: "Báo cáo tổng hợp bằng chứng y văn",
        snippetBody: "Khẳng định: Empagliflozin giảm 21% nguy cơ kết cục gộp (tử vong tim mạch hoặc nhập viện vì suy tim) ở BN HFpEF.",
        snippetTag: "Đã kiểm chứng RAG",
      },
    ],
    bestPracticesVi: [
      "Sử dụng từ khóa hoạt chất quốc tế (INN) và thuật ngữ MeSH chuẩn để tăng độ chính xác truy xuất.",
      "Ưu tiên các nguồn tài liệu thuộc cấp độ bằng chứng A1 (Meta-analysis, RCTs đa trung tâm).",
    ],
    bestPracticesEn: [
      "Use International Nonproprietary Names (INN) and MeSH terms for optimal retrieval precision.",
      "Prioritize Tier-A1 evidence sources (Systematic reviews, multi-center RCTs).",
    ],
    safetyNoteVi: "Kết quả tổng hợp bằng chứng phục vụ nghiên cứu và tham khảo chuyên môn y khoa, không sử dụng cho mục đích thương mại.",
    safetyNoteEn: "Synthesized evidence supports academic research and clinical education, not commercial promotion.",
  },

  // 8. Admin: Giám sát hệ thống & SLOs (Observability)
  {
    id: "observability",
    titleVi: "Giám sát hệ thống, độ trễ & Độ an toàn FIDES",
    titleEn: "Monitor system observability, latency SLOs & FIDES safety",
    detailVi: "Theo dõi chỉ số hiệu năng runtime, phân vị độ trễ p50/p90/p99 và tỷ lệ chặn cảnh báo an toàn.",
    detailEn: "Track runtime metrics, p50/p90/p99 latency percentiles, and FIDES safety enforcement rates.",
    href: "/admin/observability",
    icon: "progress",
    recommendedToolVi: "CÔNG CỤ QUẢN TRỊ: GIÁM SÁT HỆ THỐNG",
    recommendedToolEn: "ADMIN TOOL: OBSERVABILITY PANEL",
    roleScope: "admin",
    keywords: ["quản trị", "admin", "giám sát", "observability", "slo", "độ trễ", "p99", "fides", "hệ thống"],
    readTime: "3 phút",
    steps: [
      "Mở Bảng điều khiển Quản trị (Admin Observability).",
      "Rà soát các chỉ số SLOs thời gian thực theo từng luồng dịch vụ API/ML.",
      "Kiểm tra nhật ký cảnh báo và trạng thái hoạt động của các sidecar."
    ],
    actionVi: "Mở giám sát hệ thống",
    actionEn: "Open Observability Panel",
    illustrations: [
      {
        stepBadge: "Bước 1",
        titleVi: "Kiểm tra phân vị độ trễ runtime theo từng endpoint",
        titleEn: "Inspect latency distributions across endpoints",
        descVi: "Theo dõi thời gian phản hồi của API Gateway, ML Pipeline và RAG Retriever.",
        descEn: "Monitor response times across API Gateway, ML Synthesis, and RAG search tiers.",
        snippetType: "input",
        snippetHeader: "Runtime Metrics Stream · Live",
        snippetBody: "Chat Fast: p50 1.2s | p90 2.4s | p99 3.8s\nCouncil Consensus: p50 8.4s | p90 14.1s\nOCR Ingestion: p50 0.8s",
        snippetTag: "SLO 99.4% Pass",
      },
      {
        stepBadge: "Bước 2",
        titleVi: "Rà soát tỷ lệ kiểm duyệt an toàn FIDES",
        titleEn: "Review FIDES guardrail intercept rates",
        descVi: "Đảm bảo 100% các yêu cầu vi phạm chỉ định hoặc xung đột thuốc nghiêm trọng đều bị chặn fail-closed.",
        descEn: "Ensure 100% of contraindicated claims and illegal prescribing attempts fail closed.",
        snippetType: "guardrail",
        snippetHeader: "FIDES Safety Enforcement",
        snippetBody: "24h Intercepts: 142 Safety Blocks\n- Prescribing Hard-block: 89\n- DDI Critical Alert: 53\n- False Positive Rate: <0.2%",
        snippetTag: "FIDES Fail-Closed",
      },
      {
        stepBadge: "Bước 3",
        titleVi: "Xử lý sự cố & Điều chỉnh phân bổ tải",
        titleEn: "Incident response & Resource scaling",
        descVi: "Kích hoạt chế độ dự phòng hoặc điều chỉnh bộ đệm kết nối khi có biến động tải.",
        descEn: "Trigger failover circuits or optimize worker pools during traffic surges.",
        snippetType: "output",
        snippetHeader: "Hạ tầng sidecar & Cơ sở dữ liệu",
        snippetBody: "ASR Whisper: HEALTHY · OCR Vision: HEALTHY · Vector Store: HEALTHY",
        snippetTag: "Tất cả hệ thống OK",
      },
    ],
    bestPracticesVi: [
      "Kiểm tra bảng điều khiển observability định kỳ hàng ngày để phát hiện sớm các bất thường về độ trễ.",
      "Đảm bảo không ghi nhật ký chứa thông tin PII của người dùng vào hệ thống telemetry.",
    ],
    bestPracticesEn: [
      "Review observability dashboards daily to catch latency degradation trends early.",
      "Enforce zero-PII telemetry logging across all production monitoring channels.",
    ],
    safetyNoteVi: "Mọi số liệu giám sát quản trị đều là số liệu tổng hợp không định danh (counts, percentiles), tuân thủ GDPR và HIPAA.",
    safetyNoteEn: "All telemetry metrics are de-identified aggregations (counts, percentiles) compliant with GDPR standards.",
  },
];

const LABELS = [
  { term: "guide.labels.quick.term", meaning: "guide.labels.quick.meaning" },
  { term: "guide.labels.thinking.term", meaning: "guide.labels.thinking.meaning" },
  { term: "guide.labels.pro.term", meaning: "guide.labels.pro.meaning" },
  { term: "guide.labels.autoSources.term", meaning: "guide.labels.autoSources.meaning" },
  { term: "guide.labels.fullSources.term", meaning: "guide.labels.fullSources.meaning" },
] as const satisfies ReadonlyArray<{
  term: UITranslationKey;
  meaning: UITranslationKey;
}>;

const QUICK_SEARCH_SUGGESTIONS = [
  "Kiểm tra tương tác thuốc",
  "Ghi âm buổi khám",
  "Phân tích ca bệnh khó",
  "Hỏi triệu chứng & dùng thuốc",
  "Tủ thuốc gia đình",
  "Truy xuất y văn & PubMed",
  "Giám sát hệ thống & SLOs",
];

export default function GuidePage() {
  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");
  const isEn = uiLanguage === "en";

  // Search & Role Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState<RoleCategory>("all");

  // Currently Selected Guide ID for the Guide Reader
  const [selectedGuideId, setSelectedGuideId] = useState<string>("chat");

  useEffect(() => {
    setUiLanguage(getStoredUILanguage());
    return onUILanguageChange(setUiLanguage);
  }, []);

  // Filter tasks based on role category and omni-search query
  const filteredTasks = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    const tokens = q.split(/\s+/).filter(Boolean);

    return TASKS.filter((task) => {
      // Role scope filter
      if (roleFilter !== "all" && task.roleScope !== roleFilter) {
        return false;
      }
      // Query match
      if (!q) return true;

      const title = task.titleKey ? t(uiLanguage, task.titleKey) : isEn ? task.titleEn : task.titleVi;
      const detail = task.detailKey ? t(uiLanguage, task.detailKey) : isEn ? task.detailEn : task.detailVi;
      const tool = isEn ? task.recommendedToolEn : task.recommendedToolVi;

      const searchableCorpus = [
        title,
        detail,
        tool,
        ...(task.keywords || []),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return (
        searchableCorpus.includes(q) ||
        tokens.every((token) => searchableCorpus.includes(token))
      );
    });
  }, [searchQuery, roleFilter, uiLanguage, isEn]);

  // Active guide task displayed in the Guide Reader
  const activeGuide = useMemo(() => {
    const found = filteredTasks.find((t) => t.id === selectedGuideId);
    return found ?? filteredTasks[0] ?? TASKS[0];
  }, [filteredTasks, selectedGuideId]);

  // Synchronize selection if current selection is filtered out
  useEffect(() => {
    if (filteredTasks.length > 0 && !filteredTasks.some((t) => t.id === selectedGuideId)) {
      setSelectedGuideId(filteredTasks[0].id);
    }
  }, [filteredTasks, selectedGuideId]);

  const getTaskTitle = (task: GuideTask) => {
    if (task.titleKey) return t(uiLanguage, task.titleKey);
    return isEn ? task.titleEn || "" : task.titleVi || "";
  };

  const getTaskDetail = (task: GuideTask) => {
    if (task.detailKey) return t(uiLanguage, task.detailKey);
    return isEn ? task.detailEn || "" : task.detailVi || "";
  };

  const getTaskActionLabel = (task: GuideTask) => {
    if (task.surface && PRIMARY_ACTIONS[task.surface]) {
      return PRIMARY_ACTIONS[task.surface].label;
    }
    if (task.actionKey) return t(uiLanguage, task.actionKey);
    return isEn ? task.actionEn || "Open Tool" : task.actionVi || "Mở công cụ";
  };

  const getTaskDestination = (task: GuideTask) => {
    if (task.surface && PRIMARY_ACTIONS[task.surface]) {
      return PRIMARY_ACTIONS[task.surface].href;
    }
    return task.href || "/chat";
  };

  const roleLabelMap: Record<RoleCategory, { vi: string; en: string }> = {
    all: { vi: "Tất cả", en: "All" },
    consumer: { vi: "Người dùng", en: "Personal" },
    clinical: { vi: "Lâm sàng", en: "Clinical" },
    research: { vi: "Nghiên cứu", en: "Research" },
    admin: { vi: "Quản trị", en: "Admin" },
  };

  return (
    <main className="mx-auto max-w-7xl space-y-8 px-4 py-8 sm:px-6 lg:px-8">
      {/* 1. Search First: Omni-Search Hero (Spec v5 6.73 Item 1) */}
      <section
        aria-labelledby="guide-hero-heading"
        className="relative overflow-hidden rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 sm:p-8 shadow-sm space-y-6"
      >
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <span className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-brand)]">
              {t(uiLanguage, "guide.eyebrow")}
            </span>
            <h1
              id="guide-hero-heading"
              className="text-2xl sm:text-3xl font-bold tracking-tight text-[var(--text-primary)]"
            >
              {isEn ? "Help & Guide Center" : "Trung tâm hướng dẫn"}
            </h1>
            <p className="text-xs sm:text-sm text-[var(--text-secondary)] max-w-2xl">
              {isEn
                ? "Role-aware interactive library with step-by-step illustrations. No manual required."
                : "Thư viện hướng dẫn phân theo vai trò kèm minh họa từng bước. Dễ hiểu, không cần tài liệu dài dòng."}
            </p>
          </div>

          {/* Role Filter Selector */}
          <div className="flex flex-wrap items-center rounded-xl bg-[var(--surface-muted)] p-1 border border-[color:var(--shell-border)] text-xs">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)] px-2.5">
              {isEn ? "Role:" : "Vai trò:"}
            </span>
            {(["all", "consumer", "clinical", "research", "admin"] as RoleCategory[]).map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setRoleFilter(r)}
                className={`px-3 py-1.5 rounded-lg font-semibold transition ${
                  roleFilter === r
                    ? "bg-[var(--surface-panel)] text-[var(--text-primary)] shadow-sm border border-[color:var(--shell-border)]"
                    : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                }`}
              >
                {isEn ? roleLabelMap[r].en : roleLabelMap[r].vi}
              </button>
            ))}
          </div>
        </div>

        {/* Omni Search Bar */}
        <div className="space-y-2">
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-[var(--text-muted)]">
              <Icon name="search" size="1.2rem" />
            </div>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={
                isEn
                  ? "What would you like to accomplish? (e.g. check interactions, ambient scribe, council AI...)"
                  : "Bạn muốn làm gì với CLARA? (ví dụ: kiểm tra tương tác thuốc, ghi âm buổi khám, hội chẩn...)"
              }
              className="block w-full pl-11 pr-4 py-3 sm:py-3.5 bg-[var(--surface-muted)] border border-[color:var(--shell-border)] rounded-xl text-sm font-medium text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:ring-2 focus:ring-[var(--brand-500)]/40 focus:border-[var(--brand-500)] outline-none shadow-sm transition"
              data-testid="omni-guide-search-input"
            />
            {searchQuery ? (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-[var(--text-muted)] hover:text-[var(--text-primary)]"
              >
                <Icon name="close" size="1rem" />
              </button>
            ) : null}
          </div>

          {/* Quick Suggestion Pills */}
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            <span className="text-[11px] font-semibold text-[var(--text-muted)] mr-1">
              {isEn ? "Suggestions:" : "Gợi ý:"}
            </span>
            {QUICK_SEARCH_SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => setSearchQuery(suggestion)}
                className="rounded-full bg-[var(--surface-muted)] border border-[color:var(--shell-border)] px-2.5 py-1 text-[11px] font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)] transition"
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* 2 & 3 & 4. Wide Screen Split: Guide Reader + Local Contents (Spec v5 6.73 Items 2, 3, 4) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Selected Guide Reader (READ Shell Archetype) */}
        <section
          aria-labelledby="selected-guide-heading"
          className="lg:col-span-8 space-y-6"
        >
          {activeGuide ? (
            <SurfaceCard className="p-6 sm:p-8 space-y-6 rounded-[var(--radius-2xl)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-sm">
              {/* Guide Header */}
              <div className="space-y-3 border-b border-[color:var(--shell-border)]/60 pb-6">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge
                      tone={
                        activeGuide.roleScope === "clinical"
                          ? "brand"
                          : activeGuide.roleScope === "consumer"
                          ? "ok"
                          : activeGuide.roleScope === "research"
                          ? "warn"
                          : "danger"
                      }
                      className="text-xs font-bold"
                    >
                      {isEn ? roleLabelMap[activeGuide.roleScope].en : roleLabelMap[activeGuide.roleScope].vi}
                    </Badge>
                    <span className="rounded-md bg-[var(--brand-50)] text-[var(--brand-700)] border border-[color:var(--brand-200)] px-2.5 py-0.5 text-[11px] font-bold">
                      {isEn ? activeGuide.recommendedToolEn : activeGuide.recommendedToolVi}
                    </span>
                  </div>

                  <span className="text-xs text-[var(--text-muted)] flex items-center gap-1">
                    <Icon name="calendar" size="0.85rem" />
                    <span>{activeGuide.readTime}</span>
                  </span>
                </div>

                <div className="space-y-1">
                  <h2
                    id="selected-guide-heading"
                    className="text-xl sm:text-2xl font-bold tracking-tight text-[var(--text-primary)]"
                  >
                    {getTaskTitle(activeGuide)}
                  </h2>
                  <p className="text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed">
                    {getTaskDetail(activeGuide)}
                  </p>
                </div>
              </div>

              {/* Step-by-Step Illustrated Workflow */}
              <div className="space-y-4">
                <div className="flex items-center gap-2 text-[var(--text-brand)]">
                  <Icon name="progress" size="1.1rem" />
                  <h3 className="text-sm font-bold uppercase tracking-wider text-[var(--text-primary)]">
                    {isEn ? "Step-by-Step Execution Workflow" : "Quy trình thực hiện từng bước (Minh họa)"}
                  </h3>
                </div>

                <div className="space-y-4">
                  {activeGuide.illustrations.map((step, idx) => (
                    <div
                      key={idx}
                      className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-4 sm:p-5 space-y-3"
                    >
                      {/* Step Header */}
                      <div className="flex items-center gap-2.5">
                        <span className="rounded-full bg-[var(--brand-600)] text-[var(--button-primary-text)] text-xs font-bold w-6 h-6 flex items-center justify-center shrink-0">
                          {idx + 1}
                        </span>
                        <h4 className="font-bold text-sm text-[var(--text-primary)]">
                          {isEn ? step.titleEn : step.titleVi}
                        </h4>
                      </div>

                      <p className="text-xs leading-relaxed text-[var(--text-secondary)] pl-8">
                        {isEn ? step.descEn : step.descVi}
                      </p>

                      {/* Illustrated Mock Snippet Box */}
                      <div className="ml-8 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 text-xs space-y-2">
                        <div className="flex items-center justify-between text-[11px] border-b border-[color:var(--shell-border)]/50 pb-1 text-[var(--text-muted)] font-medium">
                          <span>{step.snippetHeader}</span>
                          {step.snippetTag ? (
                            <span className="rounded bg-[var(--surface-muted)] px-1.5 py-0.5 text-[10px] text-[var(--text-brand)] font-bold">
                              {step.snippetTag}
                            </span>
                          ) : null}
                        </div>
                        <div className="font-mono text-[11px] leading-relaxed text-[var(--text-primary)] whitespace-pre-wrap">
                          {step.snippetBody}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Best Practices & Advice */}
              <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4 sm:p-5 space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] flex items-center gap-1.5">
                  <Icon name="check" size="1rem" className="text-[var(--brand-500)]" />
                  <span>{isEn ? "Best Practices & Clinical Tips:" : "Lời khuyên khi sử dụng:"}</span>
                </h4>
                <ul className="list-disc pl-5 space-y-1 text-xs text-[var(--text-secondary)]">
                  {(isEn ? activeGuide.bestPracticesEn : activeGuide.bestPracticesVi).map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              </div>

              {/* Safety & Zero-CoT Disclaimer */}
              <div className="rounded-lg border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)]/40 p-3.5 text-xs text-[var(--status-warn-text)] flex items-start gap-2.5">
                <Icon name="warning" size="1.1rem" className="shrink-0 mt-0.5" />
                <p className="leading-relaxed">
                  {isEn ? activeGuide.safetyNoteEn : activeGuide.safetyNoteVi}
                </p>
              </div>

              {/* Direct Primary Action Button */}
              <div className="pt-2 flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-t border-[color:var(--shell-border)]/60">
                <span className="text-xs text-[var(--text-muted)] italic">
                  {isEn
                    ? `Direct destination: ${getTaskDestination(activeGuide)}`
                    : `Điều hướng trực tiếp: ${getTaskDestination(activeGuide)}`}
                </span>
                <Button
                  as="link"
                  href={getTaskDestination(activeGuide)}
                  variant="primary"
                  size="md"
                  className="rounded-xl font-bold px-6 py-2.5 shadow-sm text-sm"
                >
                  <Icon name="arrow-right" size="1rem" className="mr-1.5" />
                  {getTaskActionLabel(activeGuide)}
                </Button>
              </div>
            </SurfaceCard>
          ) : (
            <div className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-8 text-center space-y-3">
              <Icon name="search" size="2rem" className="text-[var(--text-muted)] mx-auto" />
              <p className="text-sm font-bold text-[var(--text-primary)]">
                {isEn ? "No matching guides found" : "Không tìm thấy hướng dẫn phù hợp"}
              </p>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => {
                  setSearchQuery("");
                  setRoleFilter("all");
                }}
              >
                {isEn ? "Reset Filter" : "Đặt lại bộ lọc"}
              </Button>
            </div>
          )}
        </section>

        {/* Right Column: Local Contents / Topic Navigator (Spec v5 6.73 Item 2 & 4) */}
        <aside className="lg:col-span-4 space-y-4 sticky top-6">
          <div className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5 space-y-3 shadow-sm">
            <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                {isEn ? "Topic Navigator" : "Danh mục hướng dẫn"}
              </h3>
              <span className="text-xs text-[var(--text-muted)]">
                {filteredTasks.length} {isEn ? "topics" : "mục"}
              </span>
            </div>

            <div className="space-y-1.5 max-h-[600px] overflow-y-auto pr-1">
              {filteredTasks.map((task) => {
                const isSelected = activeGuide?.id === task.id;
                return (
                  <button
                    key={task.id}
                    type="button"
                    onClick={() => setSelectedGuideId(task.id)}
                    className={`w-full text-left p-3 rounded-xl transition flex items-start gap-3 border ${
                      isSelected
                        ? "bg-[var(--surface-brand-soft)] border-[color:var(--brand-500)]/50 shadow-sm"
                        : "bg-[var(--surface-panel)] border-[color:var(--shell-border)]/50 hover:bg-[var(--surface-muted)] text-[var(--text-secondary)]"
                    }`}
                  >
                    <div
                      className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 border ${
                        isSelected
                          ? "bg-[var(--brand-600)] text-[var(--button-primary-text)] border-transparent"
                          : "bg-[var(--surface-muted)] text-[var(--text-brand)] border-[color:var(--shell-border)]"
                      }`}
                    >
                      <Icon name={resolveIconName(task.icon)} size="1.1rem" />
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1">
                        <span
                          className={`text-xs font-bold truncate ${
                            isSelected ? "text-[var(--text-brand)]" : "text-[var(--text-primary)]"
                          }`}
                        >
                          {getTaskTitle(task)}
                        </span>
                      </div>
                      <p className="text-[11px] line-clamp-1 text-[var(--text-secondary)] mt-0.5">
                        {getTaskDetail(task)}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </aside>
      </div>

      {/* 5. Mode Glossary & Terminology (Spec v5 6.73 Bottom Section) */}
      <SurfaceCard className="p-6 sm:p-8 space-y-4 rounded-[var(--radius-2xl)] border-[color:var(--shell-border)] bg-[var(--surface-panel)]">
        <div className="flex items-center gap-2 text-[var(--text-brand)]">
          <Icon name="clinical-notes" size="1.2rem" />
          <h2 className="text-base font-bold text-[var(--text-primary)]">
            {t(uiLanguage, "guide.labels.title")}
          </h2>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {LABELS.map((item) => (
            <div
              key={item.term}
              className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4 space-y-1.5"
            >
              <p className="text-xs font-bold text-[var(--text-primary)] flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-[var(--brand-500)]" />
                <span>{t(uiLanguage, item.term)}</span>
              </p>
              <p className="text-[11px] leading-relaxed text-[var(--text-secondary)]">
                {t(uiLanguage, item.meaning)}
              </p>
            </div>
          ))}
        </div>
      </SurfaceCard>
    </main>
  );
}
