export type HeroMetric = {
  label: string;
  value: string;
  note?: string;
};

export type TrustBadge = {
  label: string;
  detail: string;
};

export type ProblemPoint = {
  title: string;
  description: string;
  consequence: string;
};

export type OutcomeCard = {
  title: string;
  description: string;
  bullets: string[];
};

export type WorkflowStep = {
  index: string;
  title: string;
  subtitle: string;
  points: string[];
  outcome: string;
};

export type ModuleCard = {
  tag: string;
  title: string;
  description: string;
  bullets: string[];
  cta: string;
  href: string;
};

export type RoiMetric = {
  label: string;
  target: string;
  note: string;
};

export type SafetyGuardrail = {
  title: string;
  description: string;
};

export type Integration = {
  name: string;
  category: string;
  description: string;
};

export type Testimonial = {
  name: string;
  role: string;
  channel: string;
  quote: string;
};

export type FaqItem = {
  question: string;
  answer: string;
};

export type Office = {
  city: string;
  detail: string;
};

export type Sponsor = {
  name: string;
  href: string;
  logo: string;
};

export type FinalCta = {
  heading: string;
  subheading: string;
  button: string;
  href: string;
  secondaryButton?: string;
  secondaryHref?: string;
};

export const HERO_METRICS = [
  {
    label: "Thời gian khởi tạo pilot",
    value: "7-14 ngày",
    note: "Khởi động từ 1 use-case có owner và KPI rõ ràng.",
  },
  {
    label: "Onboarding vận hành",
    value: "< 30 phút",
    note: "Thiết lập vai trò cơ bản cho đội nghiên cứu và lâm sàng.",
  },
  {
    label: "Tầng guardrail an toàn",
    value: "6 lớp",
    note: "Citation, policy, role, de-identification, DDI, audit trail.",
  },
  {
    label: "Nguồn tri thức tích hợp",
    value: "8+",
    note: "PubMed, ClinicalTrials, WHO ICD-11, openFDA, RxNorm và guideline nội địa.",
  },
] as const satisfies readonly HeroMetric[];

export const TRUST_BADGES = [
  {
    label: "Citation-first",
    detail: "Mọi câu trả lời ưu tiên kèm bằng chứng truy vết.",
  },
  {
    label: "Safety-first",
    detail: "Guardrail đa tầng cho workflow y khoa có kiểm soát.",
  },
  {
    label: "Pilot-first",
    detail: "Triển khai theo pha nhỏ để đo hiệu quả trước khi mở rộng.",
  },
] as const satisfies readonly TrustBadge[];

export const PROBLEM_POINTS = [
  {
    title: "Tri thức y khoa rải rác",
    description: "Nguồn guideline, trial và note nội bộ nằm rời rạc nên khó hợp nhất khi xử lý ca.",
    consequence: "Đội ngũ mất thời gian tìm nguồn thay vì tập trung quyết định.",
  },
  {
    title: "Hội chẩn thiếu cấu trúc",
    description: "Nhiều ca vẫn phụ thuộc vào ghi chú tự do, thiếu pipeline review và tóm tắt chuẩn.",
    consequence: "Chất lượng giữa các ca không đồng nhất, khó bàn giao.",
  },
  {
    title: "An toàn thuốc chưa được kiểm soát",
    description: "Bệnh nhân dùng đa thuốc dễ gặp tương tác nhưng thiếu điểm cảnh báo rõ ràng theo mức độ.",
    consequence: "Tăng rủi ro trùng hoạt chất và sai thời điểm dùng.",
  },
  {
    title: "AI dừng ở mức demo",
    description: "Nhiều dự án AI không đi tới vận hành vì thiếu KPI, owner và cơ chế kiểm toán.",
    consequence: "Khó chứng minh giá trị để mở rộng ngân sách.",
  },
] as const satisfies readonly ProblemPoint[];

export const OUTCOME_CARDS = [
  {
    title: "Rút ngắn vòng xử lý ca",
    description: "Giảm thời gian tìm bằng chứng và chuẩn bị hội chẩn bằng cách gom nguồn vào một flow duy nhất.",
    bullets: [
      "Tìm tài liệu theo ngữ cảnh thay vì tra thủ công từng nguồn.",
      "Tách workspace research, review, citation rõ ràng.",
      "Giảm thời gian chuyển giao giữa các vai trò.",
    ],
  },
  {
    title: "Tăng độ nhất quán quyết định",
    description: "Chuẩn hóa cách tổng hợp thông tin và trình bày mức tin cậy theo từng ca.",
    bullets: [
      "Output có cấu trúc thay vì ghi chú rời rạc.",
      "Giữ cùng format kiểm tra trên mọi module.",
      "Dễ review lại khi cần audit hoặc escalation.",
    ],
  },
  {
    title: "Đưa AI vào vận hành an toàn",
    description: "Thiết kế guardrail ngay từ đầu để giảm overclaim và tăng khả năng triển khai dài hạn.",
    bullets: [
      "Policy gate theo ngữ cảnh thiếu dữ liệu.",
      "DDI alerts ưu tiên theo mức độ nguy cơ.",
      "Audit trail phục vụ kiểm toán nội bộ.",
    ],
  },
] as const satisfies readonly OutcomeCard[];

export const WORKFLOW_STEPS = [
  {
    index: "01",
    title: "Chốt use-case và baseline",
    subtitle: "BẮT ĐẦU TỪ VẤN ĐỀ CÓ THỂ ĐO",
    points: [
      "Chọn 1 luồng ưu tiên: Research, Council, SelfMed hoặc CareGuard.",
      "Đo baseline: thời gian xử lý, tỷ lệ hoàn tất, tỷ lệ ca cần escalation.",
      "Chỉ định owner rõ theo vai trò chuyên môn và vận hành.",
    ],
    outcome: "Có mục tiêu định lượng ngay từ tuần đầu.",
  },
  {
    index: "02",
    title: "Kết nối tri thức và chính sách",
    subtitle: "RAG ĐA NGUỒN + ROUTING THEO NGỮ CẢNH",
    points: [
      "Tích hợp PubMed, ClinicalTrials, WHO ICD-11, openFDA, RxNorm và nguồn nội bộ.",
      "Thiết lập citation hiển thị ngay tại output để verify nhanh.",
      "Bật policy gate để xử lý trường hợp thiếu ngữ cảnh quan trọng.",
    ],
    outcome: "Giảm nhiễu và tăng chất lượng truy xuất bằng chứng.",
  },
  {
    index: "03",
    title: "Vận hành workflow đa module",
    subtitle: "THỰC THI TRÊN CASE THẬT",
    points: [
      "Research cho truy xuất bằng chứng, Council cho hội chẩn, SelfMed/CareGuard cho an toàn thuốc.",
      "Scribe chuẩn hóa ghi chú để giảm tải hành chính sau ca.",
      "Control Tower theo dõi trạng thái flow và cấu hình tri thức tập trung.",
    ],
    outcome: "Workflow xuyên suốt thay cho các thao tác rời rạc.",
  },
  {
    index: "04",
    title: "Đánh giá và mở rộng",
    subtitle: "MỞ RỘNG KHI KPI ỔN ĐỊNH",
    points: [
      "Review KPI hàng tuần và so sánh với baseline.",
      "Chỉ mở thêm module khi use-case đầu đạt ngưỡng đã chốt.",
      "Lưu audit trail để hỗ trợ kiểm toán và cải tiến liên tục.",
    ],
    outcome: "Chuyển từ pilot sang vận hành dài hạn có kiểm soát.",
  },
] as const satisfies readonly WorkflowStep[];

export const MODULE_CARDS = [
  {
    tag: "CLARA RESEARCH",
    title: "Truy xuất bằng chứng y khoa đa nguồn",
    description: "Tổng hợp câu trả lời có citation để đội chuyên môn kiểm tra nhanh và tái sử dụng.",
    bullets: [
      "Evidence panel có truy vết PMID/DOI.",
      "Reranking theo bối cảnh truy vấn.",
      "Phù hợp bác sĩ trẻ, sinh viên y, nhóm nghiên cứu.",
    ],
    cta: "Mở CLARA Research",
    href: "/research",
  },
  {
    tag: "CLARA COUNCIL",
    title: "Hội chẩn AI theo wizard đa trang",
    description: "Chuẩn hóa intake, review và tổng hợp đồng thuận bằng flow đơn giản, ít thao tác hơn.",
    bullets: [
      "Wizard từng bước để tránh rối workspace.",
      "Tách research, details, citations rõ ràng.",
      "Nêu conflict và điểm cần escalation.",
    ],
    cta: "Mở Hội chẩn AI",
    href: "/council/new",
  },
  {
    tag: "CLARA SELF-MED",
    title: "An toàn dùng thuốc tại nhà",
    description: "Số hóa tủ thuốc cá nhân, nhắc lịch và giảm sai sót do tương tác hoặc trùng hoạt chất.",
    bullets: [
      "Nhận diện thuốc từ ảnh/OCR.",
      "Nhắc liều theo hồ sơ cá nhân.",
      "Giảm nhầm lẫn khi dùng đa thuốc.",
    ],
    cta: "Mở CLARA Self-Med",
    href: "/selfmed",
  },
  {
    tag: "CLARA CAREGUARD",
    title: "DDI guardrail cho quyết định thuốc",
    description: "Phân tầng cảnh báo để đội điều trị ưu tiên xử lý theo mức nguy cơ.",
    bullets: [
      "Cảnh báo tương tác đa mức.",
      "Hỗ trợ review trong bối cảnh ngoại trú.",
      "Dễ gắn vào checklist an toàn.",
    ],
    cta: "Mở CareGuard",
    href: "/careguard",
  },
  {
    tag: "CLARA SCRIBE",
    title: "Medical Scribe cho ghi chép lâm sàng",
    description: "Chuẩn hóa ghi chú sau ca để giảm tải nhập liệu và tăng chất lượng bàn giao.",
    bullets: [
      "Sinh bản ghi theo mẫu thống nhất.",
      "Giảm thao tác hành chính lặp lại.",
      "Hỗ trợ bàn giao ca trực mạch lạc.",
    ],
    cta: "Mở Medical Scribe",
    href: "/scribe",
  },
  {
    tag: "CLARA CONTROL TOWER",
    title: "Quản trị flow và tri thức tập trung",
    description: "Theo dõi runtime, policy, source và quality gate trong một không gian quản trị duy nhất.",
    bullets: [
      "Quan sát trạng thái hệ thống theo thời gian thực.",
      "Quản lý knowledge source theo nghiệp vụ.",
      "Hỗ trợ kiểm toán và tối ưu liên tục.",
    ],
    cta: "Mở Control Tower",
    href: "/admin/overview",
  },
] as const satisfies readonly ModuleCard[];

export const ROI_METRICS = [
  {
    label: "Thời gian tổng hợp tài liệu cho 1 ca",
    target: "Mục tiêu giảm 20-30%",
    note: "Đo theo baseline trước pilot và review theo tuần.",
  },
  {
    label: "Thời gian chuẩn bị trước hội chẩn",
    target: "Mục tiêu giảm 15-25%",
    note: "Phù hợp đơn vị có lịch hội chẩn định kỳ.",
  },
  {
    label: "Tỷ lệ ca có citation kiểm chứng",
    target: "Mục tiêu > 90%",
    note: "Áp dụng cho luồng yêu cầu bằng chứng bắt buộc.",
  },
  {
    label: "Tỷ lệ checklist an toàn thuốc hoàn tất",
    target: "Mục tiêu > 95%",
    note: "Áp dụng cho ca bật DDI guardrail đầy đủ.",
  },
] as const satisfies readonly RoiMetric[];

export const SAFETY_GUARDRAILS = [
  {
    title: "Citation-first response",
    description: "Ưu tiên phản hồi kèm nguồn để đội chuyên môn kiểm tra nhanh.",
  },
  {
    title: "DDI cảnh báo đa tầng",
    description: "Phân loại cảnh báo theo mức độ để tối ưu ưu tiên xử lý.",
  },
  {
    title: "Policy gate theo ngữ cảnh",
    description: "Hạ mức hoặc chặn output khi thiếu dữ liệu quan trọng.",
  },
  {
    title: "Role-based access control",
    description: "Giới hạn quyền theo vai trò bệnh nhân, chăm sóc, chuyên môn và quản trị.",
  },
  {
    title: "De-identification",
    description: "Ẩn danh PII/PHI trước khi xử lý mở rộng hoặc xuất dữ liệu.",
  },
  {
    title: "Audit trail",
    description: "Lưu vết quyết định để phục vụ review chất lượng và kiểm toán.",
  },
] as const satisfies readonly SafetyGuardrail[];

export const INTEGRATIONS = [
  {
    name: "PubMed",
    category: "Evidence",
    description: "Nguồn bài báo y sinh cho truy vấn bằng chứng.",
  },
  {
    name: "ClinicalTrials.gov",
    category: "Evidence",
    description: "Đối chiếu thử nghiệm lâm sàng liên quan theo chủ đề.",
  },
  {
    name: "WHO ICD-11",
    category: "Terminology",
    description: "Chuẩn hóa mã bệnh theo ngữ cảnh quốc tế.",
  },
  {
    name: "openFDA",
    category: "Drug Safety",
    description: "Tham chiếu tín hiệu an toàn thuốc.",
  },
  {
    name: "RxNorm",
    category: "Terminology",
    description: "Chuẩn hóa tên thuốc và hoạt chất.",
  },
  {
    name: "Dược thư VN",
    category: "Local Guideline",
    description: "Bổ sung bối cảnh sử dụng thuốc tại Việt Nam.",
  },
  {
    name: "Bộ Y tế",
    category: "Local Guideline",
    description: "Liên kết văn bản và hướng dẫn chuyên môn.",
  },
  {
    name: "DI & ADR",
    category: "Drug Safety",
    description: "Hỗ trợ rà soát tương tác và phản ứng có hại.",
  },
] as const satisfies readonly Integration[];

export const TESTIMONIALS = [
  {
    name: "Lê Minh Anh",
    role: "Người chăm sóc tại nhà",
    channel: "Hà Nội",
    quote: "CLARA cho mình cảnh báo tương tác thuốc rõ ràng và dễ hành động hơn.",
  },
  {
    name: "Trần Đức Phúc",
    role: "Sinh viên Y6",
    channel: "TP.HCM",
    quote: "Phần citation giúp mình rút ngắn thời gian chuẩn bị seminar rất nhiều.",
  },
  {
    name: "BS. Nguyễn Hoài Nam",
    role: "Bác sĩ Nội tổng quát",
    channel: "Huế",
    quote: "Điểm tốt nhất là hệ thống luôn nêu rõ mức tin cậy và giới hạn phản hồi.",
  },
  {
    name: "Phạm Thảo Vy",
    role: "Bệnh nhân tăng huyết áp",
    channel: "Đà Nẵng",
    quote: "Nhắc lịch đều và quản lý tủ thuốc theo tài khoản giúp mình đỡ quên thuốc hơn.",
  },
  {
    name: "Dương Quốc Bảo",
    role: "Research Assistant",
    channel: "Cần Thơ",
    quote: "Luồng Research phù hợp cho tổng hợp y văn nhanh khi cần đối chiếu nhiều guideline.",
  },
  {
    name: "Ngô Hạnh Sương",
    role: "Điều dưỡng",
    channel: "Gia Lâm",
    quote: "Medical Scribe giúp ghi chú gọn hơn trong các ca trực dày.",
  },
] as const satisfies readonly Testimonial[];

export const SPONSORS = [
  {
    name: "HiTechCloud",
    href: "https://hitechcloud.vn",
    logo: "/partners/hitechcloud.svg",
  },
  {
    name: "BNIX",
    href: "https://bnix.vn",
    logo: "/partners/bnix-local.png",
  },
] as const satisfies readonly Sponsor[];

export const OFFICES = [
  {
    city: "HÀ NỘI (VN)",
    detail: "Toà P3 Pavilion, Vinhomes Ocean Park 1, Gia Lâm, HN",
  },
  {
    city: "HÀ NỘI (VN)",
    detail: "Toà S2.18, phân khu Sapphire, Vinhomes Ocean Park 1, quận Gia Lâm, TP Hà Nội",
  },
  {
    city: "HÀ NỘI (VN)",
    detail: "Toà E5, Khu đô thị Ciputra, Phú Thượng, Hà Nội",
  },
  {
    city: "HUẾ (VN)",
    detail: "Toà CT3, Chung cư Aranya, đường Dương Khuê, TP Huế",
  },
  {
    city: "EMAIL",
    detail: "clara@thiennn.icu",
  },
  {
    city: "HOTLINE",
    detail: "0853374247",
  },
] as const satisfies readonly Office[];

export const FAQ_ITEMS = [
  {
    question: "CLARA có thay thế bác sĩ trong chẩn đoán hoặc kê đơn không?",
    answer:
      "Không. Project CLARA là hệ thống hỗ trợ tham khảo và vận hành theo bằng chứng. Quyết định lâm sàng cuối cùng vẫn thuộc về bác sĩ và cơ sở y tế.",
  },
  {
    question: "Có thể bắt đầu từ module nào để dễ triển khai nhất?",
    answer:
      "Nên bắt đầu từ một use-case dễ đo trong 2-8 tuần, thường là Research hoặc Council. Khi KPI ổn định mới mở rộng sang SelfMed, CareGuard và Scribe.",
  },
  {
    question: "Các chỉ số ROI trên landing có phải cam kết tuyệt đối không?",
    answer:
      "Không. Đây là mục tiêu pilot thường dùng để tham chiếu. Kết quả thực tế phụ thuộc baseline, chất lượng dữ liệu và mức tuân thủ workflow của từng đơn vị.",
  },
  {
    question: "CLARA xử lý rủi ro tương tác thuốc như thế nào?",
    answer:
      "Hệ thống kết hợp hồ sơ tủ thuốc, kiểm tra tương tác bất lợi và hiển thị cảnh báo theo mức độ ưu tiên để đội chuyên môn review trước khi chốt quyết định.",
  },
  {
    question: "Dữ liệu nhạy cảm có được bảo vệ không?",
    answer:
      "Có. Hệ thống áp dụng phân quyền theo vai trò, de-identification theo ngữ cảnh và lưu audit trail cho kiểm tra nội bộ.",
  },
  {
    question: "Pilot thường mất bao lâu để thấy kết quả ban đầu?",
    answer:
      "Thông thường 7-14 ngày có thể chạy phiên pilot đầu tiên nếu dữ liệu và owner đã sẵn sàng. Sau đó cần review theo tuần để xác nhận tác động thực tế.",
  },
] as const satisfies readonly FaqItem[];

export const FINAL_CTA = {
  heading: "SẴN SÀNG CHUYỂN TỪ DEMO AI SANG WORKFLOW Y TẾ CÓ KPI?",
  subheading:
    "Bắt đầu từ một use-case trọng điểm, chạy pilot ngắn hạn, review theo tuần và mở rộng module dựa trên dữ liệu thật.",
  button: "ĐĂNG KÝ PILOT CÙNG CLARA",
  href: "/register",
  secondaryButton: "MỞ BẢN DEMO RESEARCH",
  secondaryHref: "/research",
} as const satisfies FinalCta;

export const CLARA_KP3_CONVERSION_DATA = {
  heroMetrics: HERO_METRICS,
  trustBadges: TRUST_BADGES,
  problemPoints: PROBLEM_POINTS,
  outcomeCards: OUTCOME_CARDS,
  workflowSteps: WORKFLOW_STEPS,
  moduleCards: MODULE_CARDS,
  roiMetrics: ROI_METRICS,
  safetyGuardrails: SAFETY_GUARDRAILS,
  integrations: INTEGRATIONS,
  testimonials: TESTIMONIALS,
  sponsors: SPONSORS,
  offices: OFFICES,
  faq: FAQ_ITEMS,
  finalCta: FINAL_CTA,
} as const;

// Backward-compat aliases trong giai đoạn chuyển giao landing cũ -> mới.
export type ServiceCard = ModuleCard;
export type ModelStep = WorkflowStep;
export const SERVICE_CARDS: readonly ServiceCard[] = MODULE_CARDS;
export const MODEL_STEPS: readonly ModelStep[] = WORKFLOW_STEPS;
export const OPEN_LETTER_PARAGRAPHS: readonly string[] = PROBLEM_POINTS.map(
  (item) => `${item.title}: ${item.description} ${item.consequence}`,
);
export const PARTNER_STRIP: readonly string[] = INTEGRATIONS.map((item) => item.name);
