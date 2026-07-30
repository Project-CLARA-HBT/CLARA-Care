import type { UILanguage } from "@/lib/ui-language";

type LandingModule = {
  title: string;
  description: string;
  cta: string;
  audience: string;
};

type LandingUseCase = {
  role: string;
  scenario: string;
  benefit: string;
  tag: string;
};

type LandingFaq = { q: string; a: string };
type LandingStep = { layer: string; title: string; description: string; icon: string; tone: string; solid: boolean };
type LandingWorkflowStep = { number: string; title: string; description: string; outcome: string; icon: string };
type LandingPrinciple = { title: string; description: string; outcome: string; icon: string };

export type LandingCopy = {
  languageLabel: string;
  languageNames: { vi: string; en: string };
  nav: { engine: string; modules: string; workflow: string; faq: string; login: string; register: string };
  hero: {
    eyebrow: string;
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
  modules: LandingModule[];
  sponsors: { heading: string; description: string; network: string };
  engine: { title: string; description: string; steps: LandingStep[] };
  useCases: LandingUseCase[];
  moduleSection: { eyebrow: string; title: string; coreEngine: string; description: string; source: string; sourceDetail: string; limits: string; limitsDetail: string; cta: string };
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
    contact: string;
    privacy: string;
    terms: string;
    consent: string;
    madeFor: string;
    productLine: string;
  };
};

const ICONS = ["groups", "medication", "shield", "fa fa-pencil-square-o"] as const;
const HREFS = ["/council/new", "/medicines?tab=cabinet", "/medicines?tab=safety", "/scribe"] as const;

export const LANDING_COPY: Record<UILanguage, LandingCopy> = {
  vi: {
    languageLabel: "Ngôn ngữ",
    languageNames: { vi: "Tiếng Việt", en: "English" },
    nav: { engine: "Cách hoạt động", modules: "Tính năng", workflow: "Quy trình", faq: "Hỏi đáp", login: "Đăng nhập", register: "Đăng ký" },
    hero: {
      eyebrow: "AI y tế có kiểm soát an toàn",
      headingStart: "Hỏi điều bạn cần.",
      headingAccent: "Xem rõ nguồn và giới hạn.",
      headingEnd: "Tự quyết định cùng chuyên môn.",
      audience: "người dùng, bác sĩ, sinh viên y khoa và nhà nghiên cứu",
      descriptionBefore: "CLARA là trợ lý y tế cho ",
      descriptionAfter: ": giúp tra cứu, nêu nguồn khi có và tách bạch điều đã kiểm chứng với phần còn chưa chắc chắn. CLARA không thay thế đánh giá chuyên môn.",
      primaryCta: "Dùng thử CLARA Chat",
      secondaryCta: "Xem cách hoạt động",
      sourceWhenAvailable: "Hiển thị nguồn khi có",
      uncertainty: "Nêu rõ phần chưa chắc chắn",
      safetyGuard: "Có chặn an toàn cho tình huống rủi ro",
      preview: {
        systemCore: "Lõi hệ thống",
        engineTitle: "CLARA Chat",
        activeSession: "Phiên đang hoạt động",
        clinicalContext: "Ngữ cảnh lâm sàng đang bật",
        question: "Tương tác thuốc giữa Amlodipine và Simvastatin?",
        answer: "Đây là ví dụ minh họa: CLARA cần kiểm tra nguồn thuốc phù hợp trước khi đưa ra cảnh báo tương tác.",
        reviewSource: "Cần đối chiếu nguồn thuốc",
        analysing: "Đang phân tích dữ liệu lâm sàng...",
        sourceWhenAvailable: "Nguồn khi có",
      },
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
    sponsors: { heading: "Đối tác và nhà tài trợ", description: "Hạ tầng và hệ sinh thái đồng hành cùng The Clara Care.", network: "Đối tác hạ tầng và triển khai thử nghiệm — mạng lưới y khoa đang được xây dựng." },
    engine: { title: "CLARA xử lý một câu hỏi y khoa như thế nào?", description: "Bốn bước rõ ràng — từ câu hỏi đến câu trả lời có rào chắn an toàn và nguồn khi phù hợp.", steps: [
      { layer: "Bước 01", title: "Đầu vào", description: "Người dùng nhập triệu chứng, thuốc hoặc câu hỏi lâm sàng.", icon: "edit_note", tone: "text-cyan-700 dark:text-cyan-300", solid: false },
      { layer: "Bước 02", title: "Tìm nguồn liên quan", description: "CLARA tìm nguồn y khoa liên quan theo quyền truy cập và cấu hình hiện có.", icon: "neurology", tone: "text-cyan-200", solid: true },
      { layer: "Bước 03", title: "Kiểm tra an toàn", description: "Lọc cảnh báo, chống trả lời quá mức và yêu cầu kiểm chứng trước khi hiển thị.", icon: "security", tone: "text-red-400", solid: false },
      { layer: "Bước 04", title: "Kết quả", description: "Trình bày điều quan trọng, nguồn đã dùng, giới hạn và bước tiếp theo phù hợp.", icon: "task_alt", tone: "text-cyan-700 dark:text-cyan-300", solid: false },
    ] },
    moduleSection: { eyebrow: "Phân hệ hệ thống", title: "CLARA Chat", coreEngine: "Lõi hỗ trợ", description: "Công cụ hỗ trợ tra cứu và diễn giải thông tin y tế có rào chắn cho bác sĩ, sinh viên y khoa và người dùng.", source: "Nguồn", sourceDetail: "Hiển thị khi có và truy được", limits: "Giới hạn", limitsDetail: "Nêu rõ thay vì suy đoán", cta: "Dùng thử CLARA Chat" },
    workflow: { titleStart: "Quy trình 3 bước từ", titleAccent: "câu hỏi đến quyết định có căn cứ", steps: [
      { number: "01", title: "Nhập yêu cầu lâm sàng", description: "Dùng ngôn ngữ tự nhiên để hỏi về tương tác thuốc, triệu chứng hoặc tổng hợp y văn.", icon: "clinical_notes", outcome: "CLARA tiếp nhận và phân tích ý định" },
      { number: "02", title: "CLARA truy xuất và kiểm chứng", description: "Hệ thống tra nguồn phù hợp theo quyền và cấu hình; trạng thái kiểm chứng được nêu khi có.", icon: "fact_check", outcome: "Kết quả nêu nguồn và giới hạn khi có" },
      { number: "03", title: "Bạn duyệt nguồn và quyết định", description: "Rà soát nguồn, dùng Council, CareGuard hoặc Scribe khi phù hợp — bạn và đội ngũ chuyên môn quyết định cuối cùng.", icon: "monitoring", outcome: "Quyết định có thể được rà soát trong workflow" },
    ] },
    principles: { title: "Nguyên tắc thiết kế hệ thống", titleAccent: "y tế có rào chắn", description: "Đây là workflow có kiểm soát để đội ngũ rà soát và sử dụng mỗi ngày.", outcomeLabel: "Ý nghĩa", items: [
      { title: "Nguồn khi phù hợp", icon: "fact_check", description: "CLARA chỉ hiển thị nguồn đã được pipeline trả về; không có nguồn không đồng nghĩa với thông tin đã được xác minh.", outcome: "Bạn có thể đối chiếu trước khi ra quyết định." },
      { title: "An toàn trước tiên", icon: "health_and_safety", description: "CLARA không thay thế bác sĩ và giới hạn ở vai trò hỗ trợ; các tình huống rủi ro cao đi theo rào chắn an toàn.", outcome: "Giảm nguy cơ diễn giải quá mức." },
      { title: "Triển khai thí điểm", icon: "flight_takeoff", description: "Bắt đầu nhỏ với chỉ số rõ ràng, đo hiệu quả rồi mở rộng có kiểm soát.", outcome: "Có cơ sở thực tế trước khi mở rộng vận hành." },
    ] },
    useCaseSection: { title: "Kịch bản sử dụng thực tế", description: "CLARA phục vụ các vai trò khác nhau trong hệ sinh thái y tế." },
    primaryCta: { eyebrow: "Thử ngay", title: "Sẵn sàng thử CLARA với câu hỏi y khoa của bạn?", description: "Mở trình duyệt, đặt câu hỏi và xem rõ điều quan trọng, nguồn có sẵn cùng các giới hạn của câu trả lời.", chat: "Dùng thử CLARA Chat", workflow: "Xem quy trình kiểm chứng" },
    faqTitle: "Hỏi đáp",
    faqs: [
      { q: "CLARA có thay thế quyết định bác sĩ không?", a: "Không. CLARA là hệ thống hỗ trợ tham khảo lâm sàng; quyết định điều trị cuối cùng luôn thuộc đội ngũ chuyên môn." },
      { q: "Dữ liệu bệnh nhân có được bảo mật không?", a: "Có. Hệ thống áp dụng guardrail vận hành, kiểm soát truy cập theo vai trò và theo dõi audit để đảm bảo an toàn dữ liệu." },
      { q: "Làm sao để kiểm chứng thông tin AI đưa ra?", a: "Khi pipeline có nguồn phù hợp, CLARA nêu nguồn và giới hạn để bạn đối chiếu trước khi áp dụng. Luôn tham khảo chuyên môn cho quyết định y tế." },
      { q: "Nguồn y khoa của CLARA đến từ đâu?", a: "Tùy cấu hình và quyền truy cập, CLARA có thể dùng các nguồn như PubMed, ClinicalTrials.gov, WHO ICD-11, openFDA, RxNorm và Dược thư Việt Nam. Nguồn được nêu khi có." },
      { q: "CLARA có hỗ trợ tiếng Việt không?", a: "Có. CLARA hỗ trợ cả tiếng Việt và tiếng Anh. Bạn có thể đặt câu hỏi bằng tiếng Việt và nhận câu trả lời theo ngôn ngữ bạn chọn." },
      { q: "Có thể triển khai cho phòng khám hoặc bệnh viện không?", a: "Có. CLARA được thiết kế để triển khai theo pilot — bắt đầu từ 1 use-case nhỏ có KPI rõ, mở rộng theo dữ liệu thật. Liên hệ để được tư vấn cụ thể." },
    ],
    footer: { ctaTitle: "Bắt đầu dùng CLARA cho học tập, tra cứu và kiểm chứng lâm sàng.", ctaDetail: "Miễn phí — không cần thẻ tín dụng.", register: "Đăng ký dùng thử", description: "Trợ lý y tế có rào chắn, nêu nguồn khi có, dành cho bác sĩ, sinh viên y khoa và nhà nghiên cứu.", product: "Sản phẩm", legal: "Pháp lý", contact: "Liên hệ", privacy: "Chính sách quyền riêng tư", terms: "Điều khoản dịch vụ", consent: "Đồng ý y tế", madeFor: "Xây dựng cho quy trình lâm sàng Việt Nam.", productLine: "Chat • Council • An toàn • Scribe • Quản trị" },
  },
  en: {
    languageLabel: "Language",
    languageNames: { vi: "Tiếng Việt", en: "English" },
    nav: { engine: "How it works", modules: "Features", workflow: "Workflow", faq: "FAQ", login: "Log in", register: "Sign up" },
    hero: {
      eyebrow: "Safety-governed medical AI",
      headingStart: "Ask what matters.",
      headingAccent: "See sources and limits clearly.",
      headingEnd: "Make decisions with clinical expertise.",
      audience: "people, clinicians, medical students, and researchers",
      descriptionBefore: "CLARA is a medical assistant for ",
      descriptionAfter: ": it helps you look things up, shows sources when available, and separates verified information from what remains uncertain. CLARA does not replace professional judgement.",
      primaryCta: "Try CLARA Chat",
      secondaryCta: "See how it works",
      sourceWhenAvailable: "Shows sources when available",
      uncertainty: "States what remains uncertain",
      safetyGuard: "Safety guardrails for higher-risk situations",
      preview: {
        systemCore: "System core",
        engineTitle: "CLARA Chat",
        activeSession: "Session active",
        clinicalContext: "Clinical context enabled",
        question: "Is there an interaction between Amlodipine and Simvastatin?",
        answer: "This is an illustration: CLARA needs to check the appropriate medicine source before raising an interaction alert.",
        reviewSource: "Review the medicine source",
        analysing: "Reviewing clinical information...",
        sourceWhenAvailable: "Sources when available",
      },
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
    sponsors: { heading: "Partners and sponsors", description: "Infrastructure and ecosystem partners alongside The Clara Care.", network: "Infrastructure and pilot-delivery partners — the clinical network is being developed." },
    engine: { title: "How does CLARA handle a medical question?", description: "Four clear steps — from a question to a guarded answer with sources when appropriate.", steps: [
      { layer: "Step 01", title: "Input", description: "A person enters symptoms, medicines, or a clinical question.", icon: "edit_note", tone: "text-cyan-700 dark:text-cyan-300", solid: false },
      { layer: "Step 02", title: "Find relevant sources", description: "CLARA retrieves relevant medical sources according to the available access and configuration.", icon: "neurology", tone: "text-cyan-200", solid: true },
      { layer: "Step 03", title: "Check safety", description: "It applies guardrails and asks for verification before an answer is shown.", icon: "security", tone: "text-red-400", solid: false },
      { layer: "Step 04", title: "Result", description: "It presents what matters, sources used, limits, and an appropriate next step.", icon: "task_alt", tone: "text-cyan-700 dark:text-cyan-300", solid: false },
    ] },
    moduleSection: { eyebrow: "System modules", title: "CLARA Chat", coreEngine: "Support core", description: "A guarded tool for finding and explaining medical information for clinicians, medical students, and individuals.", source: "Sources", sourceDetail: "Shown when available and traceable", limits: "Limits", limitsDetail: "Stated instead of guessed", cta: "Try CLARA Chat" },
    workflow: { titleStart: "A three-step path from", titleAccent: "question to reviewable decision", steps: [
      { number: "01", title: "Enter a clinical request", description: "Use natural language to ask about medicine interactions, symptoms, or literature review.", icon: "clinical_notes", outcome: "CLARA receives and classifies the request" },
      { number: "02", title: "CLARA retrieves and checks", description: "The system consults suitable sources by access and configuration; it states verification status when available.", icon: "fact_check", outcome: "The result states sources and limits when available" },
      { number: "03", title: "You review sources and decide", description: "Review sources and use Council, CareGuard, or Scribe when appropriate — qualified people retain the final decision.", icon: "monitoring", outcome: "The workflow can support review and audit" },
    ] },
    principles: { title: "System design principles", titleAccent: "with clinical guardrails", description: "This is a controlled workflow designed for teams to review and use every day.", outcomeLabel: "Why it matters", items: [
      { title: "Sources when appropriate", icon: "fact_check", description: "CLARA shows only sources returned by the pipeline; the absence of a source does not mean information has been verified.", outcome: "You can compare information before deciding." },
      { title: "Safety first", icon: "health_and_safety", description: "CLARA does not replace a clinician and remains a support tool; higher-risk situations follow safety guardrails.", outcome: "Reduces the risk of over-interpretation." },
      { title: "Pilot delivery", icon: "flight_takeoff", description: "Start small with clear measures, assess outcomes, then expand with governance.", outcome: "Creates real-world evidence before broader rollout." },
    ] },
    useCaseSection: { title: "Practical use cases", description: "CLARA supports different roles across the health ecosystem." },
    primaryCta: { eyebrow: "Try it now", title: "Ready to try CLARA with your medical question?", description: "Open the chat, ask your question, and see what matters, available sources, and the limits of the answer.", chat: "Try CLARA Chat", workflow: "See the review workflow" },
    faqTitle: "Frequently asked questions",
    faqs: [
      { q: "Does CLARA replace a clinician's decision?", a: "No. CLARA is a clinical reference-support system; final treatment decisions always remain with qualified professionals." },
      { q: "Is patient data protected?", a: "CLARA applies operational guardrails, role-based access controls, and audit monitoring to help protect data." },
      { q: "How can I verify information from AI?", a: "When the pipeline has suitable sources, CLARA identifies the sources and limits so you can review them before acting. Seek professional advice for medical decisions." },
      { q: "Where do CLARA's medical sources come from?", a: "CLARA can integrate PubMed, ClinicalTrials.gov, WHO ICD-11, openFDA, RxNorm, and Vietnamese Drug Formulary sources. Sources are identified in each answer when available." },
      { q: "Does CLARA support Vietnamese?", a: "Yes. CLARA supports Vietnamese and English. You can ask in Vietnamese and choose your preferred interface language." },
      { q: "Can a clinic or hospital adopt CLARA?", a: "Yes. CLARA is designed for a pilot approach: begin with one measurable use case, then expand according to real-world evidence and local governance." },
    ],
    footer: { ctaTitle: "Start using CLARA for learning, finding information, and clinical review.", ctaDetail: "Free to start — no credit card required.", register: "Create an account", description: "A clinical AI system with source-aware answers for clinicians, medical students, and researchers.", product: "Product", legal: "Legal", contact: "Contact", privacy: "Privacy policy", terms: "Terms of service", consent: "Medical consent", madeFor: "Built for Vietnamese clinical workflows.", productLine: "Chat • Council • Safety • Scribe • Administration" },
  },
};

export const LANDING_MODULE_ICONS = ICONS;
export const LANDING_MODULE_HREFS = HREFS;
