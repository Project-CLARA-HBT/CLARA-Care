import type { IconName } from "@/components/ui/icon";

export type AdminCategoryKey = "platform" | "knowledge" | "ai_systems" | "governance";

export interface AdminCategoryMeta {
  id: AdminCategoryKey;
  label: string;
  shortLabel: string;
  description: string;
  icon: IconName;
}

export const ADMIN_CATEGORIES: Record<AdminCategoryKey, AdminCategoryMeta> = {
  platform: {
    id: "platform",
    label: "Nền tảng & Điều hành",
    shortLabel: "Nền tảng",
    description: "Cấu hình tổng thể, tháp điều phối và trạng thái mạng lưới liên kết",
    icon: "settings",
  },
  knowledge: {
    id: "knowledge",
    label: "Tri thức & Dữ liệu RAG",
    shortLabel: "Tri thức",
    description: "Kho tài liệu, luồng nạp embedding và cổng kết nối y văn",
    icon: "folder",
  },
  ai_systems: {
    id: "ai_systems",
    label: "Hệ thống AI & Giám sát",
    shortLabel: "Hệ thống AI",
    description: "Luồng suy luận, chất lượng RAG, chỉ số vận hành và an toàn lâm sàng",
    icon: "scan",
  },
  governance: {
    id: "governance",
    label: "Quản trị & Tuân thủ",
    shortLabel: "Quản trị",
    description: "Quyền dữ liệu DSAR, kiểm toán bảo mật và kiểm duyệt nội dung",
    icon: "clinical-notes",
  },
};

export const ADMIN_CATEGORY_ORDER: AdminCategoryKey[] = [
  "platform",
  "knowledge",
  "ai_systems",
  "governance",
];

export interface AdminToolItem {
  id: string;
  title: string;
  description: string;
  category: AdminCategoryKey;
  href: string;
  code: string;
  icon: IconName;
  badge?: string;
  badgeTone?: "primary" | "info" | "warning" | "success" | "muted";
  keywords: string[];
  isPrimaryTab?: boolean;
  hint?: string;
}

export const ADMIN_TOOLS: AdminToolItem[] = [
  // 1. Platform
  {
    id: "overview",
    title: "Tổng quan hệ thống",
    description: "Toàn cảnh cấu hình RAG, trạng thái dịch vụ và chỉ số điều hành",
    hint: "Toàn cảnh cấu hình và trạng thái",
    category: "platform",
    href: "/admin/overview",
    code: "A01",
    icon: "calendar",
    badge: "Core",
    badgeTone: "primary",
    keywords: ["overview", "tong quan", "dashboard", "trang thai", "he thong", "dieu hanh", "a01"],
    isPrimaryTab: true,
  },
  {
    id: "control-tower",
    title: "Tháp Điều phối (Control Tower)",
    description: "Điều phối nguồn RAG, router, reranker và cờ tính năng runtime",
    hint: "Điều phối nguồn RAG và cờ tính năng",
    category: "platform",
    href: "/dashboard/control-tower",
    code: "PLT-02",
    icon: "settings",
    badge: "Runtime",
    badgeTone: "info",
    keywords: ["control tower", "thap dieu phoi", "orchestration", "router", "flags", "runtime", "co tinh nang", "plt-02"],
    isPrimaryTab: false,
  },
  {
    id: "ecosystem",
    title: "Hệ sinh thái Đối tác & Liên kết",
    description: "Theo dõi sức khỏe đối tác, độ tin cậy dữ liệu và cảnh báo liên kết",
    hint: "Sức khỏe đối tác và độ tin cậy dữ liệu",
    category: "platform",
    href: "/dashboard/ecosystem",
    code: "PLT-03",
    icon: "progress",
    badge: "Network",
    badgeTone: "muted",
    keywords: ["ecosystem", "he sinh thai", "doi tac", "partners", "trust score", "canh bao", "federation", "plt-03"],
    isPrimaryTab: false,
  },

  // 2. Knowledge
  {
    id: "knowledge-sources",
    title: "Nguồn tri thức",
    description: "Kho tài liệu, connector truy xuất và cấu hình tri thức y khoa",
    hint: "Kho tri thức và connector truy xuất",
    category: "knowledge",
    href: "/admin/knowledge-sources",
    code: "A02",
    icon: "folder",
    badge: "RAG",
    badgeTone: "primary",
    keywords: ["knowledge", "tri thuc", "nguon", "sources", "documents", "tai lieu", "connector", "a02"],
    isPrimaryTab: true,
  },
  {
    id: "rag-ingestion",
    title: "Nạp dữ liệu RAG (Ingestion Plane)",
    description: "Quy trình trích xuất, watermark, embedding và lập chỉ mục kho y văn",
    hint: "Trích xuất, embedding và chỉ mục y văn",
    category: "knowledge",
    href: "/admin/rag-ingestion",
    code: "KNW-02",
    icon: "upload",
    badge: "Pipeline",
    badgeTone: "info",
    keywords: ["ingestion", "nap du lieu", "embedding", "pipeline", "watermark", "indexing", "vector", "knw-02"],
    isPrimaryTab: false,
  },
  {
    id: "source-hub",
    title: "Cổng nguồn Y văn (Source Hub)",
    description: "Trung tâm kết nối các nguồn y văn PubMed, EuropePMC, Dược thư QG",
    hint: "Kết nối PubMed, EuropePMC và Dược thư",
    category: "knowledge",
    href: "/research/source-hub",
    code: "KNW-03",
    icon: "search",
    badge: "Live Sync",
    badgeTone: "muted",
    keywords: ["source hub", "cong nguon", "pubmed", "y van", "literature", "europepmc", "duoc thu", "knw-03"],
    isPrimaryTab: false,
  },

  // 3. AI Systems
  {
    id: "answer-flow",
    title: "Luồng trả lời & Suy luận",
    description: "Cấu hình flow flags, kiểm chứng quy tắc, mô hình NLI và reranker",
    hint: "Flow flags và runtime debug",
    category: "ai_systems",
    href: "/admin/answer-flow",
    code: "A03",
    icon: "scan",
    badge: "Flow",
    badgeTone: "primary",
    keywords: ["answer flow", "luong tra loi", "flow flags", "nli", "reranker", "suy luan", "verification", "a03"],
    isPrimaryTab: true,
  },
  {
    id: "observability",
    title: "Giám sát AI & Hệ thống",
    description: "Theo dõi sức khỏe service, độ trễ p50/p90/p99, throughput và signal board",
    hint: "Health, metrics và signal board",
    category: "ai_systems",
    href: "/admin/observability",
    code: "A04",
    icon: "progress",
    badge: "Monitor",
    badgeTone: "primary",
    keywords: ["observability", "giam sat", "monitor", "latency", "do tre", "health", "metrics", "throughput", "a04"],
    isPrimaryTab: true,
  },
  {
    id: "analytics",
    title: "Phân tích sản phẩm",
    description: "Thống kê người dùng, surface tương tác, tỷ lệ giữ chân và phiên hội thoại",
    hint: "Người dùng, Surface và giữ chân",
    category: "ai_systems",
    href: "/admin/analytics",
    code: "A05",
    icon: "calendar",
    badge: "Usage",
    badgeTone: "primary",
    keywords: ["analytics", "phan tich", "san pham", "users", "retention", "sessions", "product", "a05"],
    isPrimaryTab: true,
  },
  {
    id: "rag-eval",
    title: "Đánh giá chất lượng RAG",
    description: "Kiểm thử tự động recall@k, nDCG@k, độ trung thực faithfulness & trích dẫn",
    hint: "Đánh giá recall@k, faithfulness & trích dẫn",
    category: "ai_systems",
    href: "/admin/rag-eval",
    code: "AI-04",
    icon: "check",
    badge: "Benchmark",
    badgeTone: "info",
    keywords: ["rag eval", "danh gia", "recall", "ndcg", "faithfulness", "accuracy", "trich dan", "benchmark", "ai-04"],
    isPrimaryTab: false,
  },
  {
    id: "clinical-analytics",
    title: "Phân tích lâm sàng & An toàn",
    description: "Kiểm chứng FIDES, tương tác thuốc DDI, độ trễ và độ an toàn khuyến cáo",
    hint: "Kiểm chứng, DDI và độ trễ lâm sàng",
    category: "ai_systems",
    href: "/admin/analytics/clinical",
    code: "A06",
    icon: "clinical-notes",
    badge: "Safety",
    badgeTone: "warning",
    keywords: ["clinical analytics", "lam sang", "fides", "ddi", "safety", "an toan", "kiem chung", "a06"],
    isPrimaryTab: false,
  },

  // 4. Governance
  {
    id: "dsar",
    title: "Hàng đợi DSAR & Quyền dữ liệu",
    description: "Xử lý yêu cầu xuất, chỉnh sửa và xóa dữ liệu cá nhân theo quy định",
    hint: "Yêu cầu quyền dữ liệu và quyền riêng tư",
    category: "governance",
    href: "/admin/dsar",
    code: "GOV-01",
    icon: "user-card",
    badge: "Compliance",
    badgeTone: "warning",
    keywords: ["dsar", "quyen du lieu", "privacy", "gdpr", "xoa du lieu", "xuat du lieu", "gov-01"],
    isPrimaryTab: false,
  },
  {
    id: "audit-log",
    title: "Nhật ký kiểm toán quản trị",
    description: "Lịch sử hành động quản trị hệ thống append-only, loại trừ PII hoàn toàn",
    hint: "Lịch sử hành động quản trị không định danh",
    category: "governance",
    href: "/admin/audit-log",
    code: "GOV-02",
    icon: "eye",
    badge: "Audit",
    badgeTone: "muted",
    keywords: ["audit log", "nhat ky", "kiem toan", "security", "zero-pii", "lich su", "gov-02"],
    isPrimaryTab: false,
  },
  {
    id: "community-moderation",
    title: "Kiểm duyệt cộng đồng",
    description: "Hàng đợi xem xét báo cáo vi phạm, gỡ nội dung và bảo vệ người dùng",
    hint: "Hàng đợi báo cáo và xử lý nội dung",
    category: "governance",
    href: "/admin/community-moderation",
    code: "GOV-03",
    icon: "warning",
    badge: "Social",
    badgeTone: "muted",
    keywords: ["moderation", "kiem duyet", "cong dong", "social", "bao cao", "vi pham", "gov-03"],
    isPrimaryTab: false,
  },
  {
    id: "security",
    title: "Bảo mật & Khóa API",
    description: "Giới hạn tốc độ (Rate Limit), kiểm tra CSRF token, xoay vòng API key nội bộ và cấu hình IP allowlist",
    hint: "Rate limit, CSRF, key rotation & IP allowlist",
    category: "governance",
    href: "/admin/security",
    code: "GOV-04",
    icon: "settings",
    badge: "Security",
    badgeTone: "warning",
    keywords: ["security", "bao mat", "api keys", "rate limit", "csrf", "rotation", "ip allowlist", "gov-04"],
    isPrimaryTab: false,
  },
  {
    id: "users",
    title: "Quản trị người dùng (User Administration)",
    description: "Quản lý danh sách tài khoản, phân quyền vai trò, kiểm soát khóa và thu hồi phiên đăng nhập",
    hint: "Phân quyền vai trò, khóa & thu hồi phiên",
    category: "governance",
    href: "/admin/users",
    code: "GOV-05",
    icon: "user-card",
    badge: "Users",
    badgeTone: "primary",
    keywords: ["users", "nguoi dung", "tai khoan", "phan quyen", "roles", "lock", "sessions", "gov-05", "admin/users"],
    isPrimaryTab: false,
  },
];

export const PRIMARY_ADMIN_TABS: Array<{
  key: string;
  href: string;
  label: string;
  hint: string;
  code: string;
  icon: IconName;
}> = [
  {
    key: "overview",
    href: "/admin/overview",
    label: "Tổng quan",
    hint: "Toàn cảnh cấu hình và trạng thái",
    code: "A01",
    icon: "calendar",
  },
  {
    key: "knowledge-sources",
    href: "/admin/knowledge-sources",
    label: "Nguồn tri thức",
    hint: "Kho tri thức và connector truy xuất",
    code: "A02",
    icon: "folder",
  },
  {
    key: "answer-flow",
    href: "/admin/answer-flow",
    label: "Luồng trả lời",
    hint: "Flow flags và runtime debug",
    code: "A03",
    icon: "scan",
  },
  {
    key: "observability",
    href: "/admin/observability",
    label: "Giám sát",
    hint: "Health, metrics và signal board",
    code: "A04",
    icon: "progress",
  },
  {
    key: "product-analytics",
    href: "/admin/analytics",
    label: "Phân tích",
    hint: "Người dùng, Surface và giữ chân",
    code: "A05",
    icon: "calendar",
  },
];

export function getAdminToolById(id: string): AdminToolItem | undefined {
  return ADMIN_TOOLS.find((tool) => tool.id === id);
}

export function getAdminToolByHref(href: string): AdminToolItem | undefined {
  return ADMIN_TOOLS.find((tool) => tool.href === href);
}

export function getAdminToolsByCategory(
  category: AdminCategoryKey | "all" = "all",
): AdminToolItem[] {
  if (category === "all") return ADMIN_TOOLS;
  return ADMIN_TOOLS.filter((tool) => tool.category === category);
}

export function searchAdminTools(
  query: string,
  category: AdminCategoryKey | "all" = "all",
): AdminToolItem[] {
  const tools = getAdminToolsByCategory(category);
  const trimmed = query.trim().toLowerCase();
  if (!trimmed) return tools;

  return tools.filter((tool) => {
    const matchTitle = tool.title.toLowerCase().includes(trimmed);
    const matchDesc = tool.description.toLowerCase().includes(trimmed);
    const matchCode = tool.code.toLowerCase().includes(trimmed);
    const matchCategory = ADMIN_CATEGORIES[tool.category].label.toLowerCase().includes(trimmed);
    const matchKeywords = tool.keywords.some((kw) => kw.toLowerCase().includes(trimmed));

    return matchTitle || matchDesc || matchCode || matchCategory || matchKeywords;
  });
}
