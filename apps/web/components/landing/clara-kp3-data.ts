export type ServiceCard = {
  tag: string;
  title: string;
  description: string;
  bullets: string[];
  cta: string;
  href: string;
};

export type ModelStep = {
  index: string;
  title: string;
  subtitle: string;
  points: string[];
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

export const HERO_METRICS = [
  { label: "Phân hệ sản phẩm đang hoạt động", value: "6" },
  { label: "Trang chức năng đã triển khai", value: "40+" },
  { label: "Flow đa trang Research + Council", value: "2" },
  { label: "Bảng quản trị Control Tower", value: "6" },
] as const;

export const OPEN_LETTER_PARAGRAPHS = [
  "Chào bạn, chúng tôi xây CLARA vì một thực tế đang diễn ra mỗi ngày: người dân có rất nhiều thông tin y tế, nhưng thiếu một hệ thống đủ tin cậy để ra quyết định an toàn.",
  "Ở nhà, một bệnh nhân mạn tính có thể dùng 4-5 thuốc cùng lúc. Chỉ cần một sai lệch nhỏ về liều, thời điểm, hoặc tương tác thuốc, rủi ro có thể tăng rất nhanh.",
  "Trong bệnh viện và môi trường học thuật, vấn đề lại là quá tải tri thức. Tìm được bằng chứng đúng đã khó; đối chiếu guideline quốc tế với bối cảnh Việt Nam còn khó hơn.",
  "CLARA không thay thế bác sĩ. CLARA được thiết kế để đóng vai trò co-pilot: truy xuất bằng chứng, hiển thị mức tin cậy, cảnh báo rủi ro và ghi rõ giới hạn hệ thống.",
  "Mục tiêu của chúng tôi rất rõ: giúp bạn ra quyết định y tế nhanh hơn, có căn cứ hơn và an toàn hơn.",
] as const;

export const SERVICE_CARDS: ServiceCard[] = [
  {
    tag: "CLARA RESEARCH",
    title: "Truy xuất bằng chứng y khoa đa nguồn",
    description:
      "Hỏi một lần, nhận câu trả lời có citation từ PubMed, ClinicalTrials, WHO ICD-11 và nguồn guideline nội địa được cấu hình trong hệ thống.",
    bullets: [
      "Agentic RAG + reranking để giảm nhiễu nguồn",
      "Evidence panel có truy vết PMID/DOI",
      "Phù hợp sinh viên y, bác sĩ trẻ, researcher"
    ],
    cta: "Mở CLARA Research",
    href: "/research",
  },
  {
    tag: "CLARA COUNCIL",
    title: "Hội chẩn AI đa chuyên khoa",
    description:
      "Đi từ intake đến review theo wizard nhiều bước, tổng hợp đồng thuận đa góc nhìn và tách workspace theo trang để giảm rối.",
    bullets: [
      "Wizard theo từng bước: intake, chọn chuyên khoa, review",
      "Workspace tách riêng: research, analyze, details, deepdive, citations",
      "Kết quả hội chẩn gọn, rõ conflict và escalation"
    ],
    cta: "Mở Hội chẩn AI",
    href: "/council/new",
  },
  {
    tag: "CLARA SELF-MED",
    title: "An toàn dùng thuốc tại gia đình",
    description:
      "Số hóa tủ thuốc, nhận diện thuốc từ ảnh/OCR, kiểm tra tương tác bất lợi và nhắc lịch dùng thuốc theo ngữ cảnh cá nhân.",
    bullets: [
      "DDI Safe phát hiện tương tác nguy cơ cao",
      "Nhắc liều theo thời gian thực",
      "Giảm sai sót do quên liều, trùng hoạt chất"
    ],
    cta: "Mở CLARA Self-Med",
    href: "/selfmed",
  },
  {
    tag: "CLARA CAREGUARD",
    title: "DDI guardrail cho quyết định thuốc",
    description:
      "Kiểm tra tương tác thuốc theo ca cụ thể, kết hợp dị ứng và triệu chứng để đưa cảnh báo sớm trước khi phát sinh rủi ro.",
    bullets: [
      "Kiểm tra tương tác trực tiếp từ danh mục thuốc",
      "Cảnh báo mức độ ưu tiên, dễ hành động",
      "Phù hợp phòng khám ngoại trú và theo dõi tại nhà"
    ],
    cta: "Mở CareGuard",
    href: "/careguard",
  },
  {
    tag: "CLARA SCRIBE",
    title: "Medical Scribe cho ghi chép lâm sàng",
    description:
      "Chuẩn hóa ghi chú khám bệnh theo cấu trúc rõ ràng để giảm tải hành chính và giữ nhất quán chất lượng hồ sơ.",
    bullets: [
      "Tạo bản ghi theo mẫu thống nhất",
      "Giảm thời gian soạn ghi chú sau khám",
      "Dễ kiểm tra lại trong quy trình điều trị liên tục"
    ],
    cta: "Mở Medical Scribe",
    href: "/scribe",
  },
  {
    tag: "CLARA CONTROL TOWER",
    title: "Quản trị Answer Flow và nguồn tri thức",
    description:
      "Điều phối runtime flow, theo dõi observability, quản lý knowledge sources và source hub trong cùng không gian vận hành.",
    bullets: [
      "Admin Overview, Answer Flow, Observability",
      "RAG Sources, Knowledge Sources, Source Hub",
      "Phù hợp đội triển khai AI y tế cần kiểm toán"
    ],
    cta: "Mở Control Tower",
    href: "/admin/overview",
  },
] as const;

export const MODEL_STEPS: ModelStep[] = [
  {
    index: "01",
    title: "INTAKE & ROUTING",
    subtitle: "ĐÚNG VAI TRÒ, ĐÚNG NGỮ CẢNH",
    points: [
      "Role-aware navigation cho normal/doctor/researcher/admin",
      "Council wizard tách bước để giảm lỗi nhập liệu",
      "Routing theo intent trước khi chạy deep flow"
    ],
  },
  {
    index: "02",
    title: "RETRIEVE & REASON",
    subtitle: "RAG ĐA NGUỒN, CÓ DEEP FLOW",
    points: [
      "Research canvas với analyze/details/deepdive/citations",
      "Deep + Deep Beta branch cho truy vấn khó",
      "Source hub và kho tri thức nội bộ có thể mở rộng"
    ],
  },
  {
    index: "03",
    title: "VERIFY & SAFETY",
    subtitle: "KIỂM CHỨNG CLAIM + DDI GUARD",
    points: [
      "Verification layer trước khi phản hồi cuối",
      "CareGuard + SelfMed DDI cảnh báo rủi ro thuốc",
      "Fallback path có ngưỡng low-context rõ ràng"
    ],
  },
  {
    index: "04",
    title: "OPERATE & SCALE",
    subtitle: "CONTROL TOWER CHO TRIỂN KHAI THẬT",
    points: [
      "Theo dõi flow flags, threshold, runtime health",
      "Quản trị nguồn tri thức theo từng kho dữ liệu",
      "Mở rộng pilot theo KPI thay vì cảm tính"
    ],
  },
] as const;

export const TESTIMONIALS: Testimonial[] = [
  {
    name: "Lê Minh Anh",
    role: "Người chăm sóc tại nhà",
    channel: "Hà Nội",
    quote:
      "Điều mình cần nhất là cảnh báo tương tác thuốc rõ ràng, không vòng vo. CLARA giúp mình tự tin hơn khi quản lý thuốc cho bố mẹ.",
  },
  {
    name: "Trần Đức Phúc",
    role: "Sinh viên Y6",
    channel: "TP.HCM",
    quote:
      "Điểm mạnh là citation rất rõ. Khi làm seminar, mình tiết kiệm nhiều giờ vì không phải lần mò nguồn từng đoạn nữa.",
  },
  {
    name: "BS. Nguyễn Hoài Nam",
    role: "Bác sĩ Nội tổng quát",
    channel: "Huế",
    quote:
      "Tôi dùng CLARA như một lớp hỗ trợ tra cứu nhanh trước hội chẩn. Hữu ích nhất là cơ chế nêu mức tin cậy và giới hạn.",
  },
  {
    name: "Phạm Thảo Vy",
    role: "Bệnh nhân tăng huyết áp",
    channel: "Đà Nẵng",
    quote:
      "Nhắc lịch đúng giờ và tủ thuốc lưu theo tài khoản giúp mình giảm hẳn tình trạng quên thuốc.",
  },
  {
    name: "Dương Quốc Bảo",
    role: "Research Assistant",
    channel: "Cần Thơ",
    quote:
      "Luồng Research của CLARA phù hợp cho công việc tổng hợp y văn nhanh, đặc biệt khi cần đối chiếu nhiều guideline.",
  },
  {
    name: "Ngô Hạnh Sương",
    role: "Điều dưỡng",
    channel: "Gia Lâm",
    quote:
      "Medical Scribe giúp chuẩn hóa ghi chú nhanh hơn, đỡ áp lực hành chính khi ca trực dày.",
  },
] as const;

export const FAQ_ITEMS: FaqItem[] = [
  {
    question: "CLARA có thay thế bác sĩ trong chẩn đoán và kê đơn không?",
    answer:
      "Không. CLARA là hệ thống hỗ trợ quyết định dựa trên bằng chứng, không thay thế khám chữa bệnh trực tiếp. Quyết định lâm sàng cuối cùng luôn thuộc về bác sĩ và cơ sở y tế.",
  },
  {
    question: "CLARA giảm rủi ro tương tác thuốc như thế nào?",
    answer:
      "Hệ thống duy trì hồ sơ thuốc đang dùng, đối chiếu tương tác bất lợi và hiển thị cảnh báo theo mức độ ưu tiên. Các khuyến nghị nhạy cảm đi qua policy gate trước khi trả lời.",
  },
  {
    question: "Dữ liệu cá nhân và dữ liệu sức khỏe có được bảo vệ không?",
    answer:
      "Có. CLARA áp dụng de-identification cho PII/PHI, kiểm soát phân quyền theo vai trò và lưu vết vận hành để phục vụ kiểm toán theo yêu cầu tuân thủ.",
  },
  {
    question: "Nguồn tri thức của CLARA đến từ đâu?",
    answer:
      "CLARA sử dụng kiến trúc RAG với các nguồn như PubMed, ClinicalTrials.gov, WHO ICD-11, openFDA cùng các nguồn nội địa đã được thiết lập trong control tower.",
  },
  {
    question: "Ai phù hợp để dùng CLARA ngay hôm nay?",
    answer:
      "Người bệnh mạn tính, người chăm sóc, sinh viên y khoa, bác sĩ trẻ và nhóm nghiên cứu cần truy xuất nhanh bằng chứng có trích dẫn minh bạch.",
  },
] as const;

export const OFFICES: Office[] = [
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
] as const;

export const PARTNER_STRIP = [
  "PubMed",
  "ClinicalTrials.gov",
  "WHO ICD-11",
  "openFDA",
  "Dược thư VN",
  "Bộ Y tế",
  "DI & ADR",
  "RxNorm",
] as const;

export const FINAL_CTA = {
  heading: "SẴN SÀNG CHUYỂN TỪ DEMO AI SANG WORKFLOW Y TẾ THẬT?",
  subheading:
    "Bắt đầu bằng một use-case cụ thể: Research, Council, SelfMed hoặc CareGuard. Khi KPI ổn định, mở rộng bằng Control Tower mà không phải xây lại từ đầu.",
  button: "BẮT ĐẦU PILOT VỚI CLARA",
  href: "/register",
} as const;
