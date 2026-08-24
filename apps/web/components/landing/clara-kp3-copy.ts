import type { UILanguage } from "@/lib/ui-language";

export type LandingModule = {
  title: string;
  description: string;
  cta: string;
  audience: string;
  icon?: string;
  href?: string;
};

export type LandingUseCase = {
  role: string;
  scenario: string;
  benefit: string;
  tag: string;
};

export type LandingFaq = { q: string; a: string };
export type LandingStep = { layer: string; title: string; description: string; icon: string; tone: string; solid: boolean };
export type LandingWorkflowStep = { number: string; title: string; description: string; outcome: string; icon: string };
export type LandingPrinciple = { title: string; description: string; outcome: string; icon: string };

export type InteractivePreviewTab = {
  id: "ddi" | "council" | "scribe" | "phr";
  tabLabel: string;
  badge: string;
  title: string;
  query: string;
  responseHeadline: string;
  responseBody: string;
  safetyTag: string;
  citations: string[];
  zeroCotAssurance: string;
  ctaText: string;
  ctaHref: string;
  detailPoints?: { label: string; value: string }[];
};

export type PathwaySection = {
  id: "personal" | "clinical" | "evidence";
  tag: string;
  title: string;
  subtitle: string;
  description: string;
  features: { title: string; desc: string; href: string; icon: string; badge?: string }[];
  primaryCta: { label: string; href: string };
};

export type LandingCopy = {
  languageLabel: string;
  languageNames: { vi: string; en: string };
  nav: {
    engine: string;
    modules: string;
    pathways: string;
    workflow: string;
    safety: string;
    guide: string;
    faq: string;
    login: string;
    register: string;
  };
  hero: {
    eyebrow: string;
    safetyBadgeFides: string;
    safetyBadgeZeroCot: string;
    headingStart: string;
    headingAccent: string;
    headingEnd: string;
    audience: string;
    descriptionBefore: string;
    descriptionAfter: string;
    primaryCta: string;
    secondaryCta: string;
    sourceWhenAvailable: string;
    uncertainty: string;
    safetyGuard: string;
    fidesAssurance: string;
    zeroCotAssurance: string;
    doctorBoundary: string;
    preview: {
      systemCore: string;
      engineTitle: string;
      activeSession: string;
      clinicalContext: string;
      question: string;
      answer: string;
      reviewSource: string;
      analysing: string;
      sourceWhenAvailable: string;
    };
  };
  interactivePreview: {
    eyebrow: string;
    title: string;
    subtitle: string;
    tabs: InteractivePreviewTab[];
  };
  pathways: {
    eyebrow: string;
    title: string;
    subtitle: string;
    sections: PathwaySection[];
  };
  safetyStrip: {
    eyebrow: string;
    title: string;
    subtitle: string;
    invariants: {
      title: string;
      desc: string;
      badge: string;
      icon: string;
    }[];
  };
  modules: LandingModule[];
  sponsors: { heading: string; description: string; network: string };
  engine: { title: string; description: string; steps: LandingStep[] };
  useCases: LandingUseCase[];
  moduleSection: {
    eyebrow: string;
    title: string;
    coreEngine: string;
    description: string;
    source: string;
    sourceDetail: string;
    limits: string;
    limitsDetail: string;
    cta: string;
  };
  workflow: { titleStart: string; titleAccent: string; steps: LandingWorkflowStep[] };
  principles: { title: string; titleAccent: string; description: string; outcomeLabel: string; items: LandingPrinciple[] };
  useCaseSection: { title: string; description: string };
  primaryCta: { eyebrow: string; title: string; description: string; chat: string; workflow: string };
  faqTitle: string;
  faqs: LandingFaq[];
  footer: {
    ctaTitle: string;
    ctaDetail: string;
    register: string;
    description: string;
    product: string;
    legal: string;
    guide: string;
    contact: string;
    privacy: string;
    terms: string;
    consent: string;
    cookies: string;
    madeFor: string;
    productLine: string;
    disclaimer: string;
  };
};

const ICONS = ["groups", "medication", "shield", "clinical-notes"] as const;
const HREFS = ["/council", "/medicines?tab=cabinet", "/medicines?tab=safety", "/scribe"] as const;

export const LANDING_COPY: Record<UILanguage, LandingCopy> = {
  vi: {
    languageLabel: "Ngôn ngữ",
    languageNames: { vi: "Tiếng Việt", en: "English" },
    nav: {
      engine: "Cách hoạt động",
      modules: "Tính năng",
      pathways: "Phân hệ",
      workflow: "Quy trình",
      safety: "An toàn & FIDES",
      guide: "Hướng dẫn",
      faq: "Hỏi đáp",
      login: "Đăng nhập",
      register: "Đăng ký",
    },
    hero: {
      eyebrow: "AI Y TẾ CÓ KIỂM CHỨNG & AN TOÀN TUYỆT ĐỐI",
      safetyBadgeFides: "FIDES Guardrail Verified",
      safetyBadgeZeroCot: "Zero-CoT Privacy Safe",
      headingStart: "Trợ lý AI lâm sàng",
      headingAccent: "hỗ trợ quyết định y khoa.",
      headingEnd: "Minh bạch nguồn, chuẩn an toàn FIDES & tôn trọng chuyên môn.",
      audience: "người dùng, bác sĩ, sinh viên y khoa và nhà nghiên cứu",
      descriptionBefore: "CLARA là trợ lý y tế cho ",
      descriptionAfter: ": giúp tra cứu y văn sống (Living Evidence), đối chiếu tương tác thuốc FIDES, bảo mật nghiêm ngặt Zero-CoT và không thay thế đánh giá chuyên môn của bác sĩ.",
      primaryCta: "Dùng thử CLARA Chat",
      secondaryCta: "Xem cách hoạt động",
      sourceWhenAvailable: "Trích dẫn nguồn y văn khi có",
      uncertainty: "Nêu rõ phần chưa chắc chắn",
      safetyGuard: "Có chặn an toàn cho tình huống rủi ro",
      fidesAssurance: "Kiểm chứng FIDES: Tự động khóa các cảnh báo tương tác thuốc DDI mức CRITICAL và liều dùng sai lệch.",
      zeroCotAssurance: "Chuẩn Zero-CoT: Tuyệt đối không lưu vết chuỗi suy luận nội bộ, bảo mật dữ liệu PHR theo Nghị định 13/2023.",
      doctorBoundary: "Ranh giới lâm sàng: Khuyến nghị mang tính hỗ trợ tham vấn, quyền quyết định điều trị luôn thuộc bác sĩ có giấy phép.",
      preview: {
        systemCore: "Lõi hệ thống FIDES",
        engineTitle: "CLARA Chat · Spatial Editorial",
        activeSession: "Phiên hoạt động an toàn",
        clinicalContext: "Ngữ cảnh lâm sàng & Dược thư BYT",
        question: "Tương tác thuốc giữa Amlodipine 5mg và Simvastatin 40mg trên người cao tuổi?",
        answer: "Simvastatin chuyển hóa qua CYP3A4; phối hợp Amlodipine ức chế nhẹ CYP3A4 làm tăng nồng độ Simvastatin trong máu, làm tăng nguy cơ tiêu cơ vân (Rhabdomyolysis). Khuyến cáo: Giới hạn liều Simvastatin tối đa 20mg/ngày khi dùng chung với Amlodipine hoặc xem xét chuyển sang Atorvastatin/Rosuvastatin.",
        reviewSource: "Nguồn: Dược thư Quốc gia Việt Nam & openFDA",
        analysing: "FIDES Safety Guardrail: PASS (CRITICAL Level Monitored)",
        sourceWhenAvailable: "Nguồn: Dược thư QG 2022 · openFDA",
      },
    },
    interactivePreview: {
      eyebrow: "TRẢI NGHIỆM TƯƠNG TÁC THỰC TẾ",
      title: "Xem trước năng lực xử lý lâm sàng của CLARA",
      subtitle: "Khám phá cách hệ thống xử lý từng tình huống y khoa với rào chắn an toàn FIDES và bảo mật Zero-CoT.",
      tabs: [
        {
          id: "ddi",
          tabLabel: "Tương tác thuốc & FIDES",
          badge: "FIDES PASS",
          title: "Kiểm tra tương tác đa thuốc (DDI Screening)",
          query: "Kiểm tra tương tác giữa Amlodipine 5mg và Simvastatin 40mg trên bệnh nhân 68 tuổi?",
          responseHeadline: "Cảnh báo tương tác DDI mức Đáng chú ý (Moderate / Critical Dose Cap)",
          responseBody:
            "Simvastatin được chuyển hóa chủ yếu qua enzym CYP3A4. Amlodipine là chất ức chế nhẹ CYP3A4, dẫn đến tăng nồng độ Simvastatin trong huyết tương và gia tăng nguy cơ bệnh cơ, tiêu cơ vân (Rhabdomyolysis).",
          safetyTag: "FIDES CRITICAL BOUND: Khóa liều Simvastatin > 20mg/ngày khi phối hợp",
          citations: ["Dược thư Quốc gia Việt Nam 2022", "openFDA Drug Interactions Database"],
          zeroCotAssurance: "Zero-CoT Invariant: Chuỗi suy luận DDI chỉ xử lý tại RAM và hủy ngay sau khi trả lời.",
          ctaText: "Thử tra cứu an toàn thuốc",
          ctaHref: "/medicines?tab=safety",
          detailPoints: [
            { label: "Cơ chế", value: "Ức chế CYP3A4 tại gan" },
            { label: "Khuyến nghị liều", value: "Simvastatin ≤ 20mg/ngày" },
            { label: "Lựa chọn thay thế", value: "Atorvastatin hoặc Rosuvastatin" },
          ],
        },
        {
          id: "council",
          tabLabel: "Hội chẩn đa chuyên khoa",
          badge: "Council AI",
          title: "Tổng hợp góc nhìn đa chuyên khoa (Council AI)",
          query: "Bệnh nhân 64 tuổi, Đái tháo đường T2 kèm Bệnh thận mạn (CKD G3b, eGFR 38), sốt kéo dài 10 ngày chưa rõ nguyên nhân.",
          responseHeadline: "Tổng hợp đồng thuận Hội đồng chuyên gia lâm sàng (Council Consensus)",
          responseBody:
            "Hội đồng AI phân tích ca bệnh theo 3 góc nhìn chuyên khoa độc lập: Nội tiết (tạm dừng SGLT2i để phòng toan ceton euglycemic), Thận học (điều chỉnh liều kháng sinh theo eGFR 38, tránh cản quang tĩnh mạch), Truyền nhiễm (cấy máu 3 mẫu trước khi dùng kháng sinh phổ rộng).",
          safetyTag: "Council Multi-Agent: Đạt đồng thuận 3/3 chuyên khoa",
          citations: ["KDIGO 2024 Clinical Guideline", "Hướng dẫn chẩn đoán ĐTĐ - Bộ Y tế VN 2020"],
          zeroCotAssurance: "Zero-CoT Protected: Toàn bộ phiên hội chẩn được bảo vệ trong ranh giới tạm thời.",
          ctaText: "Mở hội chẩn Council",
          ctaHref: "/council",
          detailPoints: [
            { label: "Nội tiết", value: "Theo dõi đường huyết mao mạch, dừng SGLT2i" },
            { label: "Thận học", value: "Chỉnh liều kháng sinh theo eGFR = 38 mL/phút" },
            { label: "Truyền nhiễm", value: "Cấy máu 3 mẫu, tầm soát sốt kéo dài (FUO)" },
          ],
        },
        {
          id: "scribe",
          tabLabel: "Ghi chép lâm sàng & SOAP",
          badge: "Scribe Note",
          title: "Chuẩn hóa ghi chú khám bệnh SOAP tự động",
          query: "Âm thanh buổi khám: \"Bệnh nhân 52 tuổi đến khám vì ho khan 4 ngày, rát họng nhẹ, sốt 37.8°C, phổi thông khí rõ, SpO2 98%...\"",
          responseHeadline: "Cấu trúc hồ sơ bệnh án SOAP chuẩn hóa",
          responseBody:
            "S (Subjective): Ho khan 4 ngày, đau rát họng, sốt nhẹ 37.8°C, không khó thở.\nO (Objective): Họng sung huyết nhẹ, amidan không xuất tiết, phổi thông khí đều 2 bên, SpO2 98%.\nA (Assessment): Viêm họng cấp nghi do virus (ICD-11: CA42 / J02.9).\nP (Plan): Điều trị triệu chứng (Paracetamol khi sốt, súc họng NaCl 0.9%), tái khám sau 3 ngày.",
          safetyTag: "Scribe Engine: Tự động tách bạch thông tin chủ quan & khách quan",
          citations: ["WHO ICD-11 Standard Coding", "Mẫu bệnh án điện tử Bộ Y tế"],
          zeroCotAssurance: "Zero-CoT Audio: Bản ghi âm xử lý cục bộ và xóa ngay sau khi bóc tách SOAP.",
          ctaText: "Dùng thử Scribe Y khoa",
          ctaHref: "/scribe",
          detailPoints: [
            { label: "Mã ICD", value: "ICD-11: CA42 (Acute pharyngitis)" },
            { label: "Độ chính xác bóc tách", value: "98.1% F1 Entity Extraction" },
            { label: "Trạng thái", value: "Sẵn sàng lưu vào EMR/PHR" },
          ],
        },
        {
          id: "phr",
          tabLabel: "Hồ sơ sức khỏe & LifeMap",
          badge: "PHR & LifeMap",
          title: "Hồ sơ sức khỏe cá nhân & Dòng thời gian LifeMap",
          query: "Xem tóm tắt tiến trình sức khỏe và lịch dùng thuốc định kỳ cá nhân",
          responseHeadline: "Dòng thời gian sức khỏe liên tục (Longitudinal LifeMap)",
          responseBody:
            "Hệ thống tổng hợp chuỗi sự kiện sức khỏe: Chỉ số huyết áp 122/78 mmHg (Mục tiêu đạt), Đơn thuốc tăng huyết áp đang duy trì (Amlodipine 5mg - Sáng 1 viên), Lịch tái khám định kỳ vào ngày 15/09/2026 kèm nhắc nhở xét nghiệm chức năng gan thận.",
          safetyTag: "Data Rights: Quyền tự chủ dữ liệu cá nhân theo Nghị định 13/2023",
          citations: ["Bộ tiêu chí hồ sơ sức khỏe điện tử cá nhân BYT", "Tiêu chuẩn HL7/FHIR R4"],
          zeroCotAssurance: "Zero-CoT Retention: Dữ liệu mã hóa đầu cuối, không chia sẻ với bên thứ ba.",
          ctaText: "Xem Hồ sơ sức khỏe",
          ctaHref: "/phr",
          detailPoints: [
            { label: "Sinh hiệu", value: "Huyết áp 122/78 mmHg, Mạch 72 bpm" },
            { label: "Tủ thuốc", value: "1 thuốc đang dùng, 0 xung đột" },
            { label: "Nhắc hẹn", value: "Tái khám 15/09/2026" },
          ],
        },
      ],
    },
    pathways: {
      eyebrow: "PHÂN HỆ CHUYÊN BIỆT",
      title: "Hai lộ trình trải nghiệm — Một chuẩn an toàn y tế",
      subtitle: "CLARA được thiết kế riêng biệt cho cả người dùng cá nhân/gia đình và đội ngũ chuyên môn y tế.",
      sections: [
        {
          id: "personal",
          tag: "Dành cho Cá nhân & Gia đình",
          title: "Phân hệ Cá nhân — Spatial Health Companion",
          subtitle: "Đồng hành chăm sóc sức khỏe chủ động, an tâm và bảo mật tuyệt đối.",
          description:
            "Quản lý tủ thuốc gia đình, quét nhãn thuốc bằng camera, theo dõi chỉ số sinh hiệu và chia sẻ dữ liệu sức khỏe an toàn với người thân.",
          features: [
            {
              title: "Tủ thuốc thông minh (Self-Med)",
              desc: "Quản lý toa thuốc, quét nhãn thuốc OCR tiếng Việt và cảnh báo tương tác tự động.",
              href: "/medicines?tab=cabinet",
              icon: "medication",
              badge: "Tiện ích hàng ngày",
            },
            {
              title: "Hồ sơ sức khỏe cá nhân (PHR)",
              desc: "Lưu trữ lịch sử bệnh nền, tiền sử dị ứng, kết quả xét nghiệm và chỉ số sinh hiệu.",
              href: "/phr",
              icon: "clinical-notes",
              badge: "Mã hóa riêng tư",
            },
            {
              title: "Bản đồ sức khỏe (LifeMap)",
              desc: "Theo dõi toàn diện hành trình điều trị và tiến trình hồi phục sau mỗi đợt khám.",
              href: "/lifemap",
              icon: "progress",
              badge: "Dòng thời gian",
            },
            {
              title: "Chia sẻ gia đình (Family Sharing)",
              desc: "Kết nối và chăm sóc sức khỏe cho cha mẹ, con cái với phân quyền truy cập minh bạch.",
              href: "/family",
              icon: "contact",
              badge: "An toàn gia đình",
            },
          ],
          primaryCta: { label: "Bắt đầu với tài khoản Cá nhân", href: "/register" },
        },
        {
          id: "clinical",
          tag: "Dành cho Bác sĩ & Cơ sở Y tế",
          title: "Phân hệ Lâm sàng — Spatial Clinical Instrument",
          subtitle: "Công cụ trợ lý hỗ trợ ra quyết định lâm sàng chuẩn xác, dựa trên bằng chứng.",
          description:
            "Tối ưu hóa thời gian khám chữa bệnh với trợ lý hội chẩn ca khó Council, tự động hóa ghi chép SOAP và hệ thống cảnh báo an toàn CareGuard.",
          features: [
            {
              title: "Hội chẩn đa chuyên khoa (Council AI)",
              desc: "Mô phỏng hội đồng chuyên gia đa ngành phân tích ca bệnh phức tạp theo guideline quốc tế.",
              href: "/council",
              icon: "contact",
              badge: "Bác sĩ lâm sàng",
            },
            {
              title: "Ghi chép lâm sàng tự động (Scribe)",
              desc: "Chuyển lời thoại bác sĩ - bệnh nhân thành cấu trúc bệnh án SOAP chuẩn hóa tức thì.",
              href: "/scribe",
              icon: "clinical-notes",
              badge: "Tiết kiệm 70% thời gian",
            },
            {
              title: "Giám sát an toàn điều trị (CareGuard)",
              desc: "Phát hiện sớm nguy cơ xung đột phác đồ, chống chỉ định và tương tác thuốc nguy hiểm.",
              href: "/careguard",
              icon: "warning",
              badge: "Rào chắn FIDES",
            },
            {
              title: "Tra cứu tương tác & Dược thư",
              desc: "Tra cứu cơ chế DDI, điều chỉnh liều theo chức năng gan thận dựa trên Dược thư Quốc gia.",
              href: "/medicines?tab=safety",
              icon: "medication",
              badge: "Chuẩn BYT & FDA",
            },
          ],
          primaryCta: { label: "Đăng nhập Cổng Bác sĩ", href: "/login" },
        },
        {
          id: "evidence",
          tag: "Dành cho Nghiên cứu & Học tập",
          title: "Phân hệ Bằng chứng — Editorial Evidence Workstation",
          subtitle: "Truy xuất y văn sống và tổng hợp bằng chứng y khoa minh bạch.",
          description:
            "Kết nối đa nguồn PubMed, ClinicalTrials.gov, WHO ICD-11 và Dược thư Việt Nam với khả năng truy nguyên nguồn gốc theo Luật AI 134/2025.",
          features: [
            {
              title: "Tra cứu y văn sống (Living Evidence)",
              desc: "Truy xuất bài báo khoa học, thử nghiệm lâm sàng và tổng hợp bằng chứng cập nhật liên tục.",
              href: "/chat",
              icon: "search",
              badge: "PubMed & WHO",
            },
            {
              title: "Minh bạch thuật toán & Zero-CoT",
              desc: "Công khai họ mô hình AI suy luận, không lưu trữ chuỗi tư duy nhạy cảm.",
              href: "/legal",
              icon: "check",
              badge: "Luật AI 134/2025",
            },
          ],
          primaryCta: { label: "Tra cứu bằng chứng y khoa", href: "/chat" },
        },
      ],
    },
    safetyStrip: {
      eyebrow: "TIÊU CHUẨN AN TOÀN BẤT BIẾN",
      title: "Bốn rào chắn bảo vệ y tế & quyền riêng tư",
      subtitle: "An toàn là điều kiện tiên quyết. Mọi phản hồi của CLARA đều tuân thủ các nguyên tắc bất biến.",
      invariants: [
        {
          title: "Kiểm chứng FIDES (FIDES Verification)",
          desc: "Tự động chặn các phản hồi có rủi ro dược lý, liều dùng sai lệch hoặc chống chỉ định mức CRITICAL.",
          badge: "FIDES Engine",
          icon: "check",
        },
        {
          title: "Bảo mật tuyệt đối Zero-CoT",
          desc: "Không lưu trữ chuỗi suy luận nội bộ (Chain-of-Thought), không dùng dữ liệu PHR để huấn luyện AI công cộng.",
          badge: "Zero-CoT Safe",
          icon: "warning",
        },
        {
          title: "Quyền tự chủ dữ liệu (Nghị định 13)",
          desc: "Tuân thủ chặt chẽ bảo vệ dữ liệu cá nhân; hỗ trợ trích xuất (DSAR), chỉnh sửa hoặc xóa hồ sơ hoàn toàn.",
          badge: "DSAR Compliant",
          icon: "user-card",
        },
        {
          title: "Chuyển tiếp cấp cứu tức thì",
          desc: "Tự động nhận diện dấu hiệu nguy hiểm tính mạng và hướng dẫn liên hệ y tế khẩn cấp 115 ngay lập tức.",
          badge: "Emergency Fast-Path",
          icon: "emergency",
        },
      ],
    },
    modules: [
      { title: "Council", description: "Hỗ trợ hội chẩn đa chuyên khoa bằng AI theo thời gian thực.", cta: "Vào Council", audience: "Dành cho bác sĩ" },
      { title: "Self-Med", description: "Quản lý lộ trình thuốc và phân tích tương tác phức hợp.", cta: "Vào Self-Med", audience: "Dành cho người dùng cá nhân" },
      { title: "CareGuard", description: "Giám sát an toàn bệnh nhân và cảnh báo theo mức độ rủi ro.", cta: "Vào CareGuard", audience: "Dành cho an toàn lâm sàng" },
      { title: "Scribe", description: "Tự động hóa ghi chép và chuẩn hóa bàn giao sau ca.", cta: "Vào Scribe", audience: "Dành cho ghi chú y khoa" },
    ],
    useCases: [
      { role: "Bác sĩ lâm sàng", scenario: "Trước khi kê đơn cho bệnh nhân đa thuốc, bác sĩ tra DDI giữa Amlodipine và Simvastatin ngay trong CLARA Chat.", benefit: "Kết quả nêu rõ nguồn đã dùng và phần còn chưa chắc chắn để bác sĩ tự đối chiếu trong workflow.", tag: "Kiểm tra DDI" },
      { role: "Sinh viên y khoa", scenario: "Ôn một chủ đề lâm sàng bằng cách hỏi CLARA về hướng tiếp cận, rồi đối chiếu từng nhận định với nguồn phù hợp.", benefit: "Học theo bằng chứng; CLARA nêu nguồn và giới hạn khi dữ liệu phù hợp có sẵn.", tag: "Ôn theo bằng chứng" },
      { role: "Nhà nghiên cứu", scenario: "Tổng hợp các nguồn đã truy xuất từ PubMed, ClinicalTrials và WHO ICD-11 về một chủ đề để tiếp tục đối chiếu.", benefit: "Có danh sách nguồn và trạng thái kiểm chứng khi pipeline trả về, phục vụ bước rà soát tiếp theo.", tag: "Tổng hợp đa nguồn" },
    ],
    sponsors: { heading: "Đối tác và mạng lưới y tế", description: "Hạ tầng công nghệ và hệ sinh thái lâm sàng đồng hành cùng The Clara Care.", network: "Đối tác hạ tầng AI và mạng lưới thử nghiệm lâm sàng tại Việt Nam." },
    engine: {
      title: "CLARA xử lý một câu hỏi y khoa như thế nào?",
      description: "Bốn bước nghiêm ngặt — từ tiếp nhận câu hỏi đến câu trả lời có rào chắn FIDES và trích dẫn nguồn y văn.",
      steps: [
        { layer: "Bước 01", title: "Tiếp nhận yêu cầu", description: "Người dùng nhập triệu chứng, thuốc hoặc câu hỏi lâm sàng.", icon: "clinical-notes", tone: "text-cyan-700 dark:text-cyan-300", solid: false },
        { layer: "Bước 02", title: "Truy xuất Living Evidence", description: "CLARA tìm nguồn y khoa liên quan (PubMed, Dược thư VN, openFDA, WHO).", icon: "search", tone: "text-cyan-200", solid: true },
        { layer: "Bước 03", title: "Kiểm chứng an toàn FIDES", description: "Rà soát chống chỉ định, liều lượng, loại trừ rủi ro kê đơn và áp dụng Zero-CoT.", icon: "warning", tone: "text-red-400", solid: false },
        { layer: "Bước 04", title: "Kết quả & Nguồn minh bạch", description: "Trình bày khuyến nghị tham vấn, nguồn đã dùng, giới hạn và hướng dẫn bước tiếp theo.", icon: "check", tone: "text-cyan-700 dark:text-cyan-300", solid: false },
      ],
    },
    moduleSection: {
      eyebrow: "PHÂN HỆ TRỌNG TÂM",
      title: "CLARA Chat",
      coreEngine: "Lõi hỗ trợ lâm sàng",
      description: "Công cụ hỗ trợ tra cứu và diễn giải thông tin y tế có rào chắn an toàn cho bác sĩ, sinh viên y khoa và người dùng cá nhân.",
      source: "Nguồn y văn",
      sourceDetail: "Trích dẫn Dược thư VN, PubMed, FDA khi có",
      limits: "Giới hạn",
      limitsDetail: "Nêu rõ ranh giới thay vì phỏng đoán",
      cta: "Dùng thử CLARA Chat",
    },
    workflow: {
      titleStart: "Quy trình 3 bước từ",
      titleAccent: "câu hỏi đến quyết định có căn cứ",
      steps: [
        { number: "01", title: "Nhập yêu cầu lâm sàng", description: "Dùng ngôn ngữ tự nhiên để hỏi về tương tác thuốc, triệu chứng hoặc tổng hợp y văn.", icon: "clinical-notes", outcome: "CLARA tiếp nhận và phân tích ý định" },
        { number: "02", title: "CLARA truy xuất và kiểm chứng FIDES", description: "Hệ thống tra nguồn phù hợp theo quyền và cấu hình; trạng thái kiểm chứng FIDES được kích hoạt.", icon: "check", outcome: "Kết quả nêu nguồn và giới hạn khi có" },
        { number: "03", title: "Bạn duyệt nguồn và quyết định", description: "Rà soát nguồn, dùng Council, CareGuard hoặc Scribe khi phù hợp — bạn và đội ngũ chuyên môn quyết định cuối cùng.", icon: "progress", outcome: "Quyết định có thể được rà soát trong workflow" },
      ],
    },
    principles: {
      title: "Nguyên tắc thiết kế hệ thống",
      titleAccent: "y tế có rào chắn",
      description: "Đây là workflow có kiểm soát để đội ngũ y tế rà soát và sử dụng mỗi ngày.",
      outcomeLabel: "Ý nghĩa",
      items: [
        { title: "Nguồn khi phù hợp", icon: "check", description: "CLARA chỉ hiển thị nguồn đã được pipeline trả về; không có nguồn không đồng nghĩa với thông tin đã được xác minh.", outcome: "Bạn có thể đối chiếu trước khi ra quyết định." },
        { title: "An toàn trước tiên", icon: "warning", description: "CLARA không thay thế bác sĩ và giới hạn ở vai trò hỗ trợ; các tình huống rủi ro cao đi theo rào chắn an toàn.", outcome: "Giảm nguy cơ diễn giải quá mức." },
        { title: "Triển khai thí điểm", icon: "progress", description: "Bắt đầu nhỏ với chỉ số rõ ràng, đo hiệu quả rồi mở rộng có kiểm soát.", outcome: "Có cơ sở thực tế trước khi mở rộng vận hành." },
      ],
    },
    useCaseSection: { title: "Kịch bản sử dụng thực tế", description: "CLARA phục vụ các vai trò khác nhau trong hệ sinh thái y tế Việt Nam." },
    primaryCta: { eyebrow: "THỬ NGHIỆM MIỄN PHÍ", title: "Sẵn sàng trải nghiệm trợ lý AI y tế an toàn?", description: "Đặt câu hỏi lâm sàng, tra cứu tương tác thuốc và trải nghiệm chuẩn bảo mật Zero-CoT cùng CLARA ngay hôm nay.", chat: "Dùng thử CLARA Chat", workflow: "Xem quy trình kiểm chứng" },
    faqTitle: "Hỏi đáp thường gặp",
    faqs: [
      { q: "CLARA có thay thế quyết định bác sĩ không?", a: "Không. CLARA là hệ thống hỗ trợ tham khảo lâm sàng; quyết định điều trị cuối cùng luôn thuộc đội ngũ chuyên môn y tế có giấy phép." },
      { q: "Dữ liệu bệnh nhân có được bảo mật không?", a: "Có. CLARA vận hành theo chuẩn Zero-CoT (không lưu chuỗi suy luận), mã hóa dữ liệu cá nhân theo Nghị định 13/2023/NĐ-CP và không dùng dữ liệu người dùng để huấn luyện AI công cộng." },
      { q: "Làm sao để kiểm chứng thông tin AI đưa ra?", a: "Khi pipeline có nguồn phù hợp, CLARA nêu nguồn và giới hạn để bạn đối chiếu trước khi áp dụng. Luôn tham khảo chuyên môn cho quyết định y tế." },
      { q: "Nguồn y khoa của CLARA đến từ đâu?", a: "Tùy cấu hình và quyền truy cập, CLARA có thể dùng các nguồn như PubMed, ClinicalTrials.gov, WHO ICD-11, openFDA, RxNorm và Dược thư Quốc gia Việt Nam. Nguồn được nêu khi có." },
      { q: "CLARA có hỗ trợ tiếng Việt không?", a: "Có. CLARA được tối ưu hóa đặc thù cho tiếng Việt y khoa và hỗ trợ song ngữ Tiếng Việt / Tiếng Anh linh hoạt." },
      { q: "Có thể triển khai cho phòng khám hoặc bệnh viện không?", a: "Có. CLARA được thiết kế để triển khai theo pilot — bắt đầu từ 1 use-case nhỏ có KPI rõ, mở rộng theo dữ liệu thật. Liên hệ để được tư vấn cụ thể." },
    ],
    footer: {
      ctaTitle: "Bắt đầu dùng CLARA cho học tập, tra cứu và kiểm chứng lâm sàng.",
      ctaDetail: "Miễn phí — không cần thẻ tín dụng.",
      register: "Đăng ký tài khoản",
      description: "Hệ thống trợ lý AI y tế chuyên sâu hỗ trợ quyết định lâm sàng có kiểm chứng FIDES, bảo mật dữ liệu Zero-CoT và quy trình minh bạch cho bác sĩ và người dùng cá nhân.",
      product: "Sản phẩm & Phân hệ",
      legal: "Trung tâm Pháp lý",
      guide: "Trung tâm Hướng dẫn",
      contact: "Liên hệ & Hỗ trợ",
      privacy: "Chính sách quyền riêng tư",
      terms: "Điều khoản dịch vụ",
      consent: "Đồng thuận y tế",
      cookies: "Chính sách cookie",
      madeFor: "Phát triển cho hệ thống chăm sóc sức khỏe & y tế Việt Nam.",
      productLine: "Chat • Council • CareGuard • Scribe • Self-Med • LifeMap",
      disclaimer: "Lưu ý quan trọng: CLARA là trợ lý AI hỗ trợ tham vấn y khoa và tổng hợp thông tin, không thay thế bác sĩ hoặc quyết định chuyên môn y tế có giấy phép. Trong trường hợp khẩn cấp, vui lòng đến ngay cơ sở y tế gần nhất hoặc gọi 115.",
    },
  },
  en: {
    languageLabel: "Language",
    languageNames: { vi: "Tiếng Việt", en: "English" },
    nav: {
      engine: "How it works",
      modules: "Features",
      pathways: "Pathways",
      workflow: "Workflow",
      safety: "Safety & FIDES",
      guide: "Guides",
      faq: "FAQ",
      login: "Log in",
      register: "Sign up",
    },
    hero: {
      eyebrow: "SAFETY-GOVERNED CLINICAL AI",
      safetyBadgeFides: "FIDES Guardrail Verified",
      safetyBadgeZeroCot: "Zero-CoT Privacy Safe",
      headingStart: "Clinical AI assistant for",
      headingAccent: "evidence-based medical decisions.",
      headingEnd: "Transparent sources, FIDES safety bounds & clinician respect.",
      audience: "people, clinicians, medical students, and researchers",
      descriptionBefore: "CLARA is a medical assistant for ",
      descriptionAfter: ": it helps you look things up, consults Living Evidence, verifies drug safety with FIDES, enforces strict Zero-CoT privacy, and does not replace professional judgement.",
      primaryCta: "Try CLARA Chat",
      secondaryCta: "See how it works",
      sourceWhenAvailable: "Shows evidence sources when available",
      uncertainty: "States what remains uncertain",
      safetyGuard: "Safety guardrails for higher-risk situations",
      fidesAssurance: "FIDES Verification: Automatically blocks CRITICAL-level drug interactions and dosing anomalies.",
      zeroCotAssurance: "Zero-CoT Privacy: Never retains internal chain-of-thought traces, strictly safeguarding PHR under privacy regulations.",
      doctorBoundary: "Clinical Boundary: Provides supportive consultation; licensed clinicians retain ultimate treatment authority.",
      preview: {
        systemCore: "FIDES System Core",
        engineTitle: "CLARA Chat · Spatial Editorial",
        activeSession: "Active secure session",
        clinicalContext: "Clinical context & National Formulary",
        question: "Is there an interaction between Amlodipine 5mg and Simvastatin 40mg?",
        answer: "Simvastatin is primarily metabolized by CYP3A4. Amlodipine mildly inhibits CYP3A4, elevating plasma Simvastatin levels and increasing rhabdomyolysis risk. Recommendation: Limit Simvastatin to max 20mg/day when co-administered or consider switching to Atorvastatin/Rosuvastatin.",
        reviewSource: "Source: VN National Drug Formulary & openFDA",
        analysing: "FIDES Safety Guardrail: PASS (CRITICAL Level Monitored)",
        sourceWhenAvailable: "Sources: VN Formulary 2022 · openFDA",
      },
    },
    interactivePreview: {
      eyebrow: "INTERACTIVE CLINICAL PREVIEW",
      title: "Preview CLARA's real-time clinical capabilities",
      subtitle: "Explore how the system safely processes medical tasks with FIDES verification and Zero-CoT privacy.",
      tabs: [
        {
          id: "ddi",
          tabLabel: "Drug Safety & FIDES",
          badge: "FIDES PASS",
          title: "Multi-drug Interaction Screening (DDI)",
          query: "Check interaction between Amlodipine 5mg and Simvastatin 40mg in a 68-year-old patient?",
          responseHeadline: "Clinically Significant DDI Warning (Critical Dose Cap)",
          responseBody:
            "Simvastatin is metabolized via hepatic CYP3A4. Amlodipine mildly inhibits CYP3A4, raising Simvastatin AUC and elevating risk of myopathy and rhabdomyolysis.",
          safetyTag: "FIDES CRITICAL BOUND: Restrict Simvastatin to ≤ 20mg/day when co-administered",
          citations: ["National Drug Formulary of Vietnam", "openFDA Drug Interactions Database"],
          zeroCotAssurance: "Zero-CoT Invariant: DDI reasoning traces are ephemeral and discarded immediately.",
          ctaText: "Try Drug Safety Check",
          ctaHref: "/medicines?tab=safety",
          detailPoints: [
            { label: "Mechanism", value: "Hepatic CYP3A4 inhibition" },
            { label: "Dose Limit", value: "Simvastatin ≤ 20mg/day" },
            { label: "Alternatives", value: "Atorvastatin or Rosuvastatin" },
          ],
        },
        {
          id: "council",
          tabLabel: "Multidisciplinary Council",
          badge: "Council AI",
          title: "Multidisciplinary Case Review (Council AI)",
          query: "64yo patient with T2DM, CKD G3b (eGFR 38), persistent fever for 10 days of unknown origin.",
          responseHeadline: "Synthesized Multidisciplinary Consensus",
          responseBody:
            "Independent multi-agent evaluation: Endocrinology (suspend SGLT2i to prevent euglycemic DKA), Nephrology (adjust antimicrobial dosing for eGFR 38, avoid IV contrast), Infectious Disease (obtain 3 sets of blood cultures prior to broad-spectrum antibiotics).",
          safetyTag: "Council Multi-Agent: 3/3 Specialty Consensus Achieved",
          citations: ["KDIGO 2024 Clinical Guidelines", "National Diabetes Guidelines 2020"],
          zeroCotAssurance: "Zero-CoT Protected: Entire consultation runs within ephemeral boundaries.",
          ctaText: "Open Council AI",
          ctaHref: "/council",
          detailPoints: [
            { label: "Endocrinology", value: "Monitor glucose, hold SGLT2i" },
            { label: "Nephrology", value: "Adjust dose for eGFR = 38 mL/min" },
            { label: "Infectious Disease", value: "Blood cultures x3, FUO workup" },
          ],
        },
        {
          id: "scribe",
          tabLabel: "Clinical Notes & SOAP",
          badge: "Scribe Note",
          title: "Automated SOAP Consultation Note Structuring",
          query: "Audio consultation intake: \"52yo patient presenting with dry cough for 4 days, mild sore throat, temp 37.8°C, clear lung sounds, SpO2 98%...\"",
          responseHeadline: "Standardized Structured SOAP Note",
          responseBody:
            "S (Subjective): 4-day dry cough, mild pharyngeal pain, low-grade fever 37.8°C, no dyspnea.\nO (Objective): Mild pharyngeal erythema, no tonsillar exudate, clear breath sounds bilaterally, SpO2 98%.\nA (Assessment): Acute viral pharyngitis (ICD-11: CA42 / J02.9).\nP (Plan): Symptomatic relief (Paracetamol prn fever, warm saline gargle), review in 3 days if not improved.",
          safetyTag: "Scribe Engine: Strict segregation of subjective & objective evidence",
          citations: ["WHO ICD-11 Standard Coding", "MoH Electronic Medical Record Standard"],
          zeroCotAssurance: "Zero-CoT Audio: Audio processed locally and purged immediately after SOAP extraction.",
          ctaText: "Try Clinical Scribe",
          ctaHref: "/scribe",
          detailPoints: [
            { label: "ICD Code", value: "ICD-11: CA42 (Acute pharyngitis)" },
            { label: "Extraction F1", value: "98.1% F1 Entity Precision" },
            { label: "Status", value: "Ready for EMR/PHR sync" },
          ],
        },
        {
          id: "phr",
          tabLabel: "PHR & LifeMap Timeline",
          badge: "PHR & LifeMap",
          title: "Personal Health Record & Longitudinal Timeline",
          query: "View longitudinal health overview, vital signs, and active medication schedule",
          responseHeadline: "Continuous Longitudinal LifeMap",
          responseBody:
            "Synthesized health timeline: Blood pressure 122/78 mmHg (On target), Active medication schedule (Amlodipine 5mg - 1 tab morning), Follow-up visit scheduled for 15/09/2026 with routine renal panel reminders.",
          safetyTag: "Data Rights: Complete user autonomy under privacy frameworks",
          citations: ["Personal Electronic Health Record Standards", "HL7/FHIR R4 Core"],
          zeroCotAssurance: "Zero-CoT Retention: Client-side encryption, zero third-party disclosure.",
          ctaText: "Explore Health Record",
          ctaHref: "/phr",
          detailPoints: [
            { label: "Vitals", value: "BP 122/78 mmHg, HR 72 bpm" },
            { label: "Cabinet", value: "1 active med, 0 conflicts" },
            { label: "Reminder", value: "Follow-up 15/09/2026" },
          ],
        },
      ],
    },
    pathways: {
      eyebrow: "ROLE-TAILORED PATHWAYS",
      title: "Two Dedicated Pathways — One Safety Standard",
      subtitle: "CLARA is purposefully crafted for individuals and healthcare professionals.",
      sections: [
        {
          id: "personal",
          tag: "For Individuals & Families",
          title: "Personal Pathway — Spatial Health Companion",
          subtitle: "Proactive, reliable, and completely private personal healthcare management.",
          description:
            "Manage medication schedules, scan labels via OCR, track vital sign trends, and share records safely with family members.",
          features: [
            {
              title: "Smart Medicine Cabinet (Self-Med)",
              desc: "Track prescriptions, scan medication labels, and receive automated interaction alerts.",
              href: "/medicines?tab=cabinet",
              icon: "medication",
              badge: "Daily Utility",
            },
            {
              title: "Personal Health Record (PHR)",
              desc: "Store condition history, allergy profiles, lab results, and biometric measurements.",
              href: "/phr",
              icon: "clinical-notes",
              badge: "Encrypted & Private",
            },
            {
              title: "Longitudinal LifeMap",
              desc: "Visualize your entire healthcare journey, recovery progress, and clinic visits.",
              href: "/lifemap",
              icon: "progress",
              badge: "Timeline View",
            },
            {
              title: "Family Sharing",
              desc: "Coordinate and care for family members with granular, revocable consent controls.",
              href: "/family",
              icon: "contact",
              badge: "Family Safety",
            },
          ],
          primaryCta: { label: "Get Started with Personal Account", href: "/register" },
        },
        {
          id: "clinical",
          tag: "For Clinicians & Healthcare Teams",
          title: "Clinical Pathway — Spatial Clinical Instrument",
          subtitle: "Evidence-grounded clinical decision-support instruments for modern practice.",
          description:
            "Accelerate diagnostic review with Council AI, automate SOAP documentation, and monitor patient safety via CareGuard in real time.",
          features: [
            {
              title: "Multidisciplinary Council AI",
              desc: "Simulate multi-specialty case reviews referencing international clinical guidelines.",
              href: "/council",
              icon: "contact",
              badge: "For Clinicians",
            },
            {
              title: "Clinical Scribe & SOAP Notes",
              desc: "Transform consultation dialogues into structured, ICD-11 coded clinical notes instantly.",
              href: "/scribe",
              icon: "clinical-notes",
              badge: "Save 70% Note Time",
            },
            {
              title: "Clinical Safety Guardrail (CareGuard)",
              desc: "Detect drug-drug interactions, contraindications, and protocol conflicts early.",
              href: "/careguard",
              icon: "warning",
              badge: "FIDES Engine",
            },
            {
              title: "Formulary & Interaction Screening",
              desc: "Review DDI pharmacodynamics and renal/hepatic dose adjustments in real time.",
              href: "/medicines?tab=safety",
              icon: "medication",
              badge: "MoH & FDA Guidelines",
            },
          ],
          primaryCta: { label: "Sign in to Clinician Portal", href: "/login" },
        },
        {
          id: "evidence",
          tag: "For Researchers & Educators",
          title: "Evidence Pathway — Editorial Evidence Workstation",
          subtitle: "Living evidence retrieval with transparent attribution.",
          description:
            "Query across PubMed, ClinicalTrials.gov, WHO ICD-11, and National Formularies with full algorithmic transparency under AI governance frameworks.",
          features: [
            {
              title: "Living Evidence Retrieval",
              desc: "Search peer-reviewed literature, clinical trials, and meta-analyses in real time.",
              href: "/chat",
              icon: "search",
              badge: "PubMed & WHO",
            },
            {
              title: "Algorithmic Transparency & Zero-CoT",
              desc: "Open model family attribution with zero retention of sensitive thinking traces.",
              href: "/legal",
              icon: "check",
              badge: "AI Law 134/2025",
            },
          ],
          primaryCta: { label: "Explore Living Evidence", href: "/chat" },
        },
      ],
    },
    safetyStrip: {
      eyebrow: "SAFETY INVARIANTS",
      title: "Four Pillars of Clinical Safety & Data Privacy",
      subtitle: "Safety is our core foundation. Every response strictly complies with invariant guardrails.",
      invariants: [
        {
          title: "FIDES Safety Verification",
          desc: "Automatically gates and prevents risky pharmacological claims, dosage anomalies, and critical contraindications.",
          badge: "FIDES Engine",
          icon: "check",
        },
        {
          title: "Zero-CoT Privacy Invariant",
          desc: "Never logs internal chain-of-thought traces; PHR data is never used to train public foundation models.",
          badge: "Zero-CoT Safe",
          icon: "warning",
        },
        {
          title: "Full Data Autonomy & DSAR",
          desc: "Rigorous personal data protection; full rights to export (DSAR), modify, or permanently delete records.",
          badge: "DSAR Compliant",
          icon: "user-card",
        },
        {
          title: "Emergency Fast-Path",
          desc: "Instantly recognizes life-threatening red flags and redirects to immediate emergency healthcare.",
          badge: "Emergency Fast-Path",
          icon: "emergency",
        },
      ],
    },
    modules: [
      { title: "Council", description: "Supports multidisciplinary case review with AI in real time.", cta: "Open Council", audience: "For clinicians" },
      { title: "Self-Med", description: "Helps manage medicines and review complex interactions.", cta: "Open Self-Med", audience: "For individuals" },
      { title: "CareGuard", description: "Supports patient safety review and risk-prioritized alerts.", cta: "Open CareGuard", audience: "For clinical safety" },
      { title: "Scribe", description: "Helps structure notes and handovers after a consultation.", cta: "Open Scribe", audience: "For clinical notes" },
    ],
    useCases: [
      { role: "Clinician", scenario: "Before prescribing for a person taking multiple medicines, a clinician checks the Amlodipine–Simvastatin interaction in CLARA Chat.", benefit: "The result identifies the sources used and what remains uncertain so the clinician can review it in their workflow.", tag: "Interaction check" },
      { role: "Medical student", scenario: "Study a clinical topic with CLARA, then compare each statement with an appropriate source.", benefit: "Learn from evidence; CLARA states sources and limits when suitable data are available.", tag: "Evidence-based study" },
      { role: "Researcher", scenario: "Bring together retrieved material from PubMed, ClinicalTrials, and WHO ICD-11 around one topic for further review.", benefit: "Receive a source list and verification status when the pipeline returns them, to support the next review step.", tag: "Multi-source synthesis" },
    ],
    sponsors: { heading: "Partners and ecosystem", description: "Technology infrastructure and clinical network partners alongside The Clara Care.", network: "Clinical pilot deployment network and health-tech infrastructure." },
    engine: {
      title: "How does CLARA handle a medical question?",
      description: "Four clear steps — from receiving a question to a guarded response with FIDES verification and evidence citations.",
      steps: [
        { layer: "Step 01", title: "Intake Request", description: "User enters symptoms, medications, or clinical questions.", icon: "clinical-notes", tone: "text-cyan-700 dark:text-cyan-300", solid: false },
        { layer: "Step 02", title: "Retrieve Living Evidence", description: "CLARA consults peer-reviewed databases (PubMed, National Formularies, FDA, WHO).", icon: "search", tone: "text-cyan-200", solid: true },
        { layer: "Step 03", title: "FIDES Safety Verification", description: "Screens for contraindications, dosage accuracy, and applies Zero-CoT privacy.", icon: "warning", tone: "text-red-400", solid: false },
        { layer: "Step 04", title: "Result & Citations", description: "Presents supportive guidance, cited sources, uncertainty bounds, and next steps.", icon: "check", tone: "text-cyan-700 dark:text-cyan-300", solid: false },
      ],
    },
    moduleSection: {
      eyebrow: "CORE ENGINE",
      title: "CLARA Chat",
      coreEngine: "Clinical Support Core",
      description: "A safety-governed assistant for exploring and interpreting medical knowledge for clinicians, medical students, and individuals.",
      source: "Evidence Sources",
      sourceDetail: "Cited from PubMed, openFDA, and VN Formulary",
      limits: "Limits",
      limitsDetail: "Explicitly bounded rather than guessed",
      cta: "Try CLARA Chat",
    },
    workflow: {
      titleStart: "A three-step path from",
      titleAccent: "question to reviewable decision",
      steps: [
        { number: "01", title: "Enter a clinical request", description: "Use natural language to ask about medicine interactions, symptoms, or literature review.", icon: "clinical-notes", outcome: "CLARA receives and classifies the request" },
        { number: "02", title: "CLARA retrieves and checks with FIDES", description: "The system consults suitable sources and verifies against FIDES safety guardrails.", icon: "check", outcome: "The result states sources and limits when available" },
        { number: "03", title: "You review sources and decide", description: "Review sources and use Council, CareGuard, or Scribe when appropriate — qualified people retain the final decision.", icon: "progress", outcome: "The workflow can support review and audit" },
      ],
    },
    principles: {
      title: "System design principles",
      titleAccent: "with clinical guardrails",
      description: "This is a controlled workflow designed for teams to review and use every day.",
      outcomeLabel: "Why it matters",
      items: [
        { title: "Sources when appropriate", icon: "check", description: "CLARA shows only sources returned by the pipeline; the absence of a source does not mean information has been verified.", outcome: "You can compare information before deciding." },
        { title: "Safety first", icon: "warning", description: "CLARA does not replace a clinician and remains a support tool; higher-risk situations follow safety guardrails.", outcome: "Reduces the risk of over-interpretation." },
        { title: "Pilot delivery", icon: "progress", description: "Start small with clear measures, assess outcomes, then expand with governance.", outcome: "Creates real-world evidence before broader rollout." },
      ],
    },
    useCaseSection: { title: "Practical use cases", description: "CLARA supports diverse roles across the healthcare ecosystem." },
    primaryCta: { eyebrow: "START EXPLORING", title: "Ready to experience safety-first clinical AI?", description: "Ask clinical questions, review drug safety, and experience Zero-CoT privacy with CLARA today.", chat: "Try CLARA Chat", workflow: "See the review workflow" },
    faqTitle: "Frequently asked questions",
    faqs: [
      { q: "Does CLARA replace a clinician's decision?", a: "No. CLARA is a clinical reference-support system; final treatment decisions always remain with qualified licensed professionals." },
      { q: "Is patient data protected?", a: "Yes. CLARA strictly enforces Zero-CoT privacy, encrypts personal data under privacy regulations, and never trains public foundation models on patient records." },
      { q: "How can I verify information from AI?", a: "When the pipeline has suitable sources, CLARA identifies the sources and limits so you can review them before acting. Seek professional advice for medical decisions." },
      { q: "Where do CLARA's medical sources come from?", a: "CLARA integrates PubMed, ClinicalTrials.gov, WHO ICD-11, openFDA, RxNorm, and Vietnamese Drug Formulary sources. Sources are identified in each answer when available." },
      { q: "Does CLARA support Vietnamese?", a: "Yes. CLARA is specially optimized for Vietnamese clinical terminology and provides full bilingual Vietnamese/English support." },
      { q: "Can a clinic or hospital adopt CLARA?", a: "Yes. CLARA is designed for a pilot approach: begin with one measurable use case, then expand according to real-world evidence and local governance." },
    ],
    footer: {
      ctaTitle: "Start using CLARA for learning, finding information, and clinical review.",
      ctaDetail: "Free to start — no credit card required.",
      register: "Create an account",
      description: "A specialized clinical AI assistant providing FIDES-verified clinical decision support, Zero-CoT privacy protection, and transparent workflows for clinicians and individuals.",
      product: "Products & Modules",
      legal: "Legal Index",
      guide: "Help Library",
      contact: "Contact & Support",
      privacy: "Privacy policy",
      terms: "Terms of service",
      consent: "Medical consent",
      cookies: "Cookie policy",
      madeFor: "Built for clinical workflows and healthcare systems.",
      productLine: "Chat • Council • CareGuard • Scribe • Self-Med • LifeMap",
      disclaimer: "Important note: CLARA is a clinical AI assistant for reference and information synthesis, and does not replace licensed medical practitioners or clinical judgment. In an emergency, please visit the nearest hospital or call 115 immediately.",
    },
  },
};

export const LANDING_MODULE_ICONS = ICONS;
export const LANDING_MODULE_HREFS = HREFS;
