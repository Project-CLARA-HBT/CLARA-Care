export type UserRole = "normal" | "researcher" | "doctor" | "admin";
export type NavGroupKey =
  "core" | "research" | "clinical" | "medication" | "admin" | "support";

export type PageMeta = {
  title: string;
  subtitle: string;
};

export type NavigationItem = {
  href: string;
  label: string;
  icon: string;
  desc: string;
  group: NavGroupKey;
  roles: UserRole[];
  mobilePrimary?: boolean;
  page: PageMeta;
};

export type NavGroupMeta = {
  label: string;
  shortLabel: string;
  icon: string;
};

export const PUBLIC_ROUTES = new Set([
  "/",
  "/legal",
  "/legal/privacy",
  "/legal/terms",
  "/legal/consent",
  "/legal/cookies",
  "/huong-dan",
  "/login",
  "/register",
  "/role-select",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
]);

export const DEFAULT_POST_LOGIN_PATH = "/today";

const AUTH_ENTRY_ROUTES = new Set(["/login", "/register"]);

const ROLE_HOME_PATHS: Record<UserRole, string> = {
  normal: "/today",
  researcher: "/dashboard",
  doctor: "/dashboard",
  admin: "/dashboard",
};

const NAV_ITEMS: NavigationItem[] = [
  {
    href: "/chat",
    label: "Hỏi CLARA",
    icon: "chat_paste_go",
    desc: "Hỏi đáp y tế hợp nhất",
    group: "core",
    roles: ["normal", "researcher", "doctor", "admin"],
    mobilePrimary: true,
    page: {
      title: "CLARA Chat",
      subtitle:
        "Hỏi đáp y tế rõ ràng, có bằng chứng và phù hợp với vai trò của bạn.",
    },
  },
  {
    href: "/dashboard",
    label: "Tổng quan",
    icon: "dashboard",
    desc: "Bức tranh nhanh hôm nay",
    group: "core",
    roles: ["normal", "researcher", "doctor", "admin"],
    mobilePrimary: true,
    page: {
      title: "Tổng quan công việc",
      subtitle: "Theo dõi nhanh các tác vụ chăm sóc và vận hành trong ngày.",
    },
  },
  {
    href: "/today",
    label: "Hôm nay",
    icon: "today",
    desc: "Việc chăm sóc bạn đã chấp nhận",
    group: "core",
    roles: ["normal", "researcher", "doctor", "admin"],
    mobilePrimary: true,
    page: {
      title: "Hôm nay",
      subtitle: "Các việc chăm sóc đã được bạn chấp nhận.",
    },
  },
  {
    href: "/lifemap",
    label: "LifeMap",
    icon: "route",
    desc: "Hành trình chăm sóc của bạn",
    group: "core",
    roles: ["normal", "researcher", "doctor", "admin"],
    page: {
      title: "LifeMap",
      subtitle: "Tổ chức điều bạn muốn theo dõi thành hành trình nhỏ.",
    },
  },
  {
    href: "/visits",
    label: "Chuẩn bị đi khám",
    icon: "event_available",
    desc: "Câu hỏi và Visit Pack của bạn",
    group: "core",
    roles: ["normal", "researcher", "doctor", "admin"],
    page: {
      title: "Chuẩn bị buổi khám",
      subtitle: "Gom đúng thông tin bạn muốn mang đến buổi khám.",
    },
  },
  {
    href: "/family",
    label: "Family Circle",
    icon: "family_restroom",
    desc: "Chia sẻ tối thiểu với người hỗ trợ",
    group: "core",
    roles: ["normal", "researcher", "doctor", "admin"],
    page: {
      title: "Family Circle",
      subtitle: "Kiểm soát ai được xem hoặc hỗ trợ đúng một việc.",
    },
  },
  {
    href: "/research",
    label: "Nghiên cứu",
    icon: "science",
    desc: "Tổng hợp và kiểm chứng bằng chứng",
    group: "research",
    roles: ["normal", "researcher", "doctor", "admin"],
    mobilePrimary: true,
    page: {
      title: "CLARA Research",
      subtitle: "Phân tích chuyên sâu với nguồn, độ chắc chắn và dấu vết luận điểm.",
    },
  },
  {
    href: "/evidence",
    label: "Bằng chứng cập nhật",
    icon: "fact_check",
    desc: "Câu hỏi LifeMap với nguồn kiểm chứng",
    group: "research",
    roles: ["normal", "researcher", "doctor", "admin"],
    page: {
      title: "Bằng chứng đang cập nhật",
      subtitle: "Gắn câu hỏi với hành trình, xem nguồn và phần chưa chắc chắn.",
    },
  },
  {
    href: "/phr",
    label: "Hồ sơ sức khỏe cá nhân",
    icon: "description",
    desc: "Hồ sơ sức khỏe cá nhân",
    group: "core",
    roles: ["normal", "researcher", "doctor", "admin"],
    mobilePrimary: true,
    page: {
      title: "Hồ sơ sức khỏe cá nhân",
      subtitle: "Lưu trữ và tổng hợp hồ sơ sức khỏe cá nhân.",
    },
  },
  {
    href: "/community",
    label: "Cộng đồng",
    icon: "forum",
    desc: "Cộng đồng sức khỏe CLARA",
    group: "core",
    roles: ["normal", "researcher", "doctor", "admin"],
    page: {
      title: "Cộng đồng sức khỏe",
      subtitle:
        "Chia sẻ kinh nghiệm và hỗ trợ nhau. Không phải tư vấn y tế — nội dung được kiểm duyệt.",
    },
  },
  {
    href: "/selfmed",
    label: "Tủ thuốc",
    icon: "pill",
    desc: "Quản lý thuốc cá nhân",
    group: "medication",
    roles: ["normal", "researcher", "doctor", "admin"],
    mobilePrimary: true,
    page: {
      title: "Tủ thuốc của tôi",
      subtitle: "Quản lý thuốc đang dùng và quét toa thuốc từ ảnh.",
    },
  },
  {
    href: "/medicines",
    label: "Thuốc của tôi",
    icon: "medication",
    desc: "Thuốc đã xác nhận và DrugBank DDI",
    group: "medication",
    roles: ["normal", "researcher", "doctor", "admin"],
    page: {
      title: "Thuốc của tôi",
      subtitle: "Theo dõi thuốc đã xác nhận và kiểm tra DrugBank.",
    },
  },
  {
    href: "/research/source-hub",
    label: "Nguồn nghiên cứu",
    icon: "database_search",
    desc: "PubMed, thuốc và nguồn y khoa",
    group: "research",
    roles: ["researcher", "doctor", "admin"],
    page: {
      title: "Nguồn nghiên cứu",
      subtitle:
        "Đồng bộ và tra cứu các nguồn y khoa phục vụ phân tích bằng chứng.",
    },
  },
  {
    href: "/careguard",
    label: "Kiểm tra tương tác",
    icon: "security",
    desc: "DDI và cảnh báo an toàn",
    group: "medication",
    roles: ["normal", "researcher", "doctor", "admin"],
    mobilePrimary: true,
    page: {
      title: "Kiểm tra tương tác thuốc",
      subtitle:
        "Đối chiếu thuốc, dị ứng và triệu chứng để phát hiện rủi ro sớm.",
    },
  },
  {
    href: "/council",
    label: "Ca lâm sàng",
    icon: "groups",
    desc: "Nhiều góc nhìn chuyên khoa",
    group: "clinical",
    roles: ["doctor", "admin"],
    page: {
      title: "Hội chẩn ca bệnh",
      subtitle: "Tập hợp ý kiến đa chuyên khoa để xử lý ca khó.",
    },
  },
  {
    href: "/scribe",
    label: "Ghi chú khám",
    icon: "clinical_notes",
    desc: "Ghi chép khám bệnh",
    group: "clinical",
    roles: ["doctor", "admin"],
    page: {
      title: "Ghi chép khám bệnh",
      subtitle: "Soạn ghi chú khám nhanh theo định dạng rõ ràng, nhất quán.",
    },
  },
  {
    href: "/admin/overview",
    label: "Quản trị hệ thống",
    icon: "settings_input_component",
    desc: "Điều phối cấu hình và vận hành",
    group: "admin",
    roles: ["admin"],
    page: {
      title: "Quản trị hệ thống",
      subtitle:
        "Bảng điều phối trung tâm cho cấu hình, chất lượng phản hồi và vận hành.",
    },
  },
  {
    href: "/admin/knowledge-sources",
    label: "Nguồn tri thức",
    icon: "database",
    desc: "Nguồn dữ liệu hợp nhất",
    group: "admin",
    roles: ["admin"],
    page: {
      title: "Nguồn tri thức",
      subtitle:
        "Trung tâm hợp nhất connector truy xuất, tài liệu và đồng bộ nguồn y khoa.",
    },
  },
  {
    href: "/admin/answer-flow",
    label: "Luồng trả lời",
    icon: "alt_route",
    desc: "Điều phối phân tích và phản hồi",
    group: "admin",
    roles: ["admin"],
    page: {
      title: "Luồng trả lời",
      subtitle: "Điều phối các bước phân tích, xác minh và phản hồi cuối.",
    },
  },
  {
    href: "/admin/observability",
    label: "Giám sát vận hành",
    icon: "monitoring",
    desc: "Theo dõi cảnh báo runtime",
    group: "admin",
    roles: ["admin"],
    page: {
      title: "Giám sát vận hành",
      subtitle: "Theo dõi tình trạng hệ thống, cảnh báo và tín hiệu runtime.",
    },
  },
  {
    href: "/admin/community-moderation",
    label: "Kiểm duyệt cộng đồng",
    icon: "gavel",
    desc: "Xử lý báo cáo nội dung cộng đồng",
    group: "admin",
    roles: ["admin"],
    page: {
      title: "Kiểm duyệt cộng đồng",
      subtitle: "Xem xét và xử lý các báo cáo nội dung từ cộng đồng.",
    },
  },
  {
    href: "/admin/analytics",
    label: "Phân tích sản phẩm",
    icon: "insights",
    desc: "Người dùng, Surface và giữ chân",
    group: "admin",
    roles: ["admin"],
    page: {
      title: "Phân tích sản phẩm",
      subtitle:
        "Xu hướng người dùng, mức độ sử dụng theo Surface, phễu chuyển đổi và giữ chân.",
    },
  },
  {
    href: "/admin/analytics/clinical",
    label: "Phân tích lâm sàng",
    icon: "vital_signs",
    desc: "Kiểm chứng, DDI và độ trễ",
    group: "admin",
    roles: ["admin"],
    page: {
      title: "Phân tích lâm sàng",
      subtitle:
        "Phán quyết kiểm chứng FIDES, phân bố tương tác thuốc và độ trễ theo tier.",
    },
  },
  {
    href: "/huong-dan",
    label: "Hướng dẫn",
    icon: "widgets",
    desc: "Bắt đầu trong 5 phút",
    group: "support",
    roles: ["normal", "researcher", "doctor", "admin"],
    page: {
      title: "Trung tâm hướng dẫn",
      subtitle: "Các bước sử dụng nhanh cho người mới.",
    },
  },
];

/**
 * Compliance Consent Center + DSAR self-service nav entries.
 *
 * These account/privacy surfaces are part of the additive, feature-flagged
 * regulatory-compliance layer. They are included in navigation ONLY when their
 * `NEXT_PUBLIC_COMPLIANCE_*` flag is explicitly enabled, so that with the flags
 * off (the default) navigation — and the AppShell route guard — behave exactly
 * as before (regulatory-compliance Requirement 8.1, 8.2). The flag is read from
 * the build-time-inlined public env var; anything other than an explicit opt-in
 * (`1`/`true`/`on`) resolves to OFF.
 */
const COMPLIANCE_FLAG_TRUTHY = new Set(["1", "true", "on"]);

function isComplianceFlagOn(value: string | undefined): boolean {
  if (typeof value !== "string") return false;
  return COMPLIANCE_FLAG_TRUTHY.has(value.trim().toLowerCase());
}

const ACCOUNT_NAV_ITEMS: NavigationItem[] = [
  {
    href: "/account/consent",
    label: "Trung tâm đồng thuận",
    icon: "privacy_tip",
    desc: "Quản lý đồng thuận theo mục đích",
    group: "support",
    roles: ["normal", "researcher", "doctor", "admin"],
    page: {
      title: "Trung tâm đồng thuận",
      subtitle:
        "Cấp hoặc rút đồng thuận cho từng mục đích xử lý dữ liệu cá nhân.",
    },
  },
  {
    href: "/account/data",
    label: "Dữ liệu của tôi",
    icon: "shield_person",
    desc: "Quyền truy cập, xuất và xóa dữ liệu",
    group: "support",
    roles: ["normal", "researcher", "doctor", "admin"],
    page: {
      title: "Dữ liệu của tôi",
      subtitle:
        "Thực hiện quyền của chủ thể dữ liệu: xuất, chỉnh sửa, xóa, hạn chế và rút đồng thuận.",
    },
  },
];

// Admin-only DSAR queue (regulatory-compliance Req 3.6, Property P7). Gated by
// the DSAR flag and the admin role; RBAC is enforced authoritatively by the
// backend (`/compliance/dsar/admin/*`).
const ADMIN_DSAR_NAV_ITEM: NavigationItem = {
  href: "/admin/dsar",
  label: "Hàng đợi DSAR",
  icon: "shield_person",
  desc: "Xử lý yêu cầu quyền dữ liệu",
  group: "admin",
  roles: ["admin"],
  page: {
    title: "Hàng đợi DSAR (Quản trị)",
    subtitle:
      "Theo dõi và xử lý các yêu cầu của chủ thể dữ liệu theo thời hạn luật định.",
  },
};

if (
  isComplianceFlagOn(
    process.env.NEXT_PUBLIC_COMPLIANCE_GRANULAR_CONSENT_ENABLED,
  )
) {
  NAV_ITEMS.push(ACCOUNT_NAV_ITEMS[0]);
}
if (isComplianceFlagOn(process.env.NEXT_PUBLIC_COMPLIANCE_DSAR_ENABLED)) {
  NAV_ITEMS.push(ACCOUNT_NAV_ITEMS[1]);
  NAV_ITEMS.push(ADMIN_DSAR_NAV_ITEM);
}

const GROUP_ORDER: NavGroupKey[] = [
  "core",
  "research",
  "clinical",
  "medication",
  "admin",
  "support",
];

export const GROUP_LABELS: Record<NavGroupKey, string> = {
  core: "Không gian làm việc",
  research: "Nghiên cứu",
  clinical: "Lâm sàng",
  medication: "Thuốc và an toàn",
  admin: "Quản trị hệ thống",
  support: "Hỗ trợ",
};

const GROUP_META: Record<NavGroupKey, NavGroupMeta> = {
  core: {
    label: "Không gian làm việc",
    shortLabel: "Không gian",
    icon: "workspaces",
  },
  research: { label: "Nghiên cứu", shortLabel: "Nghiên cứu", icon: "science" },
  clinical: { label: "Lâm sàng", shortLabel: "Lâm sàng", icon: "stethoscope" },
  medication: {
    label: "Thuốc và an toàn",
    shortLabel: "An toàn",
    icon: "shield",
  },
  admin: {
    label: "Quản trị hệ thống",
    shortLabel: "Quản trị",
    icon: "settings_input_component",
  },
  support: { label: "Hỗ trợ", shortLabel: "Hỗ trợ", icon: "help" },
};

const DEFAULT_PAGE_META: PageMeta = {
  title: "Không gian làm việc",
  subtitle:
    "Nền tảng trợ lý y tế giúp bạn xử lý công việc nhanh và rõ ràng hơn.",
};

export function isPublicRoute(pathname: string): boolean {
  return PUBLIC_ROUTES.has(pathname);
}

export function getRoleHomePath(role: UserRole = "normal"): string {
  return ROLE_HOME_PATHS[role] ?? DEFAULT_POST_LOGIN_PATH;
}

export function sanitizeNextPath(
  nextPath: string | null | undefined,
): string | null {
  if (!nextPath) return null;
  if (!nextPath.startsWith("/") || nextPath.startsWith("//")) return null;
  try {
    const parsed = new URL(nextPath, "http://localhost");
    if (AUTH_ENTRY_ROUTES.has(parsed.pathname)) return null;
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return null;
  }
}

export function resolvePostLoginPath(options: {
  nextPath?: string | null;
  role?: UserRole;
}): string {
  return (
    sanitizeNextPath(options.nextPath) ??
    getRoleHomePath(options.role ?? "normal")
  );
}

export function getNavItemsByRole(role: UserRole): NavigationItem[] {
  return NAV_ITEMS.filter((item) => item.roles.includes(role));
}

export function getGroupedNavItems(
  role: UserRole,
): Array<{ key: NavGroupKey; label: string; items: NavigationItem[] }> {
  const items = getNavItemsByRole(role);
  return GROUP_ORDER.map((groupKey) => {
    const groupItems = items.filter((item) => item.group === groupKey);
    return {
      key: groupKey,
      label: GROUP_META[groupKey].label,
      items: groupItems,
    };
  }).filter((group) => group.items.length > 0);
}

export function getMobilePrimaryNav(role: UserRole): NavigationItem[] {
  return getNavItemsByRole(role)
    .filter((item) => item.mobilePrimary)
    .slice(0, 4);
}

export function getGroupMeta(group: NavGroupKey): NavGroupMeta {
  return GROUP_META[group];
}

export function getTopNavLinks(
  role: UserRole,
): Array<{ href: string; label: string; icon: string }> {
  const grouped = getGroupedNavItems(role);
  const desiredOrder: NavGroupKey[] = ["clinical", "medication", "admin"];
  return desiredOrder
    .map((groupKey) => {
      const group = grouped.find((entry) => entry.key === groupKey);
      if (!group || group.items.length === 0) return null;
      const meta = GROUP_META[groupKey];
      return {
        href: group.items[0].href,
        label: meta.shortLabel,
        icon: meta.icon,
      };
    })
    .filter((item): item is { href: string; label: string; icon: string } =>
      Boolean(item),
    );
}

export function getPageMeta(pathname: string): PageMeta {
  const exact = NAV_ITEMS.find((item) => item.href === pathname);
  if (exact) return exact.page;

  if (pathname === "/research" || pathname.startsWith("/research/")) {
    return {
      title: "Hỏi đáp y tế",
      subtitle: "Luồng hỏi đáp đã hợp nhất về CLARA Chat.",
    };
  }

  const prefixSorted = [...NAV_ITEMS].sort(
    (a, b) => b.href.length - a.href.length,
  );
  const prefixMatch = prefixSorted.find((item) =>
    pathname.startsWith(`${item.href}/`),
  );
  if (prefixMatch) return prefixMatch.page;

  if (pathname.startsWith("/dashboard/control-tower")) {
    return {
      title: "Điều phối tri thức",
      subtitle:
        "Thiết lập nguồn dữ liệu và luồng phản hồi cho hệ thống hỏi đáp.",
    };
  }

  if (pathname.startsWith("/dashboard/ecosystem")) {
    return {
      title: "Hệ sinh thái đối tác",
      subtitle: "Theo dõi trạng thái kết nối và độ tin cậy dữ liệu liên thông.",
    };
  }

  return DEFAULT_PAGE_META;
}

export function isActiveRoute(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}
