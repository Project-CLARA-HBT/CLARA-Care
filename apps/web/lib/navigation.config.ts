export type UserRole = "normal" | "researcher" | "doctor" | "admin";
export type NavGroupKey = "core" | "clinical" | "medication" | "admin" | "support";

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
  "/verify-email"
]);

export const DEFAULT_POST_LOGIN_PATH = "/chat";

const AUTH_ENTRY_ROUTES = new Set(["/login", "/register"]);

const ROLE_HOME_PATHS: Record<UserRole, string> = {
  normal: "/chat",
  researcher: "/chat",
  doctor: "/chat",
  admin: "/chat",
};

const NAV_ITEMS: NavigationItem[] = [
  {
    href: "/chat",
    label: "Chat",
    icon: "chat_paste_go",
    desc: "Trải nghiệm chat thuần",
    group: "core",
    roles: ["normal", "researcher", "doctor", "admin"],
    mobilePrimary: true,
    page: {
      title: "CLARA Chat",
      subtitle: "Không gian chat tập trung với 3 mode Clara Research: Fast, Deep, Deep Beta."
    }
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
      subtitle: "Theo dõi nhanh các tác vụ chăm sóc và vận hành trong ngày."
    }
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
      subtitle: "Quản lý thuốc đang dùng và quét toa thuốc từ ảnh."
    }
  },
  {
    href: "/careguard",
    label: "Kiểm tra tương tác",
    icon: "security",
    desc: "DDI và cảnh báo an toàn",
    group: "medication",
    roles: ["normal", "doctor", "admin"],
    mobilePrimary: true,
    page: {
      title: "Kiểm tra tương tác thuốc",
      subtitle: "Đối chiếu thuốc, dị ứng và triệu chứng để phát hiện rủi ro sớm."
    }
  },
  {
    href: "/council",
    label: "Hội chẩn AI",
    icon: "groups",
    desc: "Nhiều góc nhìn chuyên khoa",
    group: "clinical",
    roles: ["doctor", "admin"],
    page: {
      title: "Hội chẩn ca bệnh",
      subtitle: "Tập hợp ý kiến đa chuyên khoa để xử lý ca khó."
    }
  },
  {
    href: "/scribe",
    label: "Medical Scribe",
    icon: "clinical_notes",
    desc: "Ghi chép khám bệnh",
    group: "clinical",
    roles: ["doctor", "admin"],
    page: {
      title: "Ghi chép khám bệnh",
      subtitle: "Soạn ghi chú khám nhanh theo định dạng rõ ràng, nhất quán."
    }
  },
  {
    href: "/admin/overview",
    label: "Admin Control Tower",
    icon: "settings_input_component",
    desc: "Điều phối cấu hình và vận hành",
    group: "admin",
    roles: ["researcher", "doctor", "admin"],
    page: {
      title: "Quản trị hệ thống",
      subtitle: "Bảng điều phối trung tâm cho cấu hình, chất lượng phản hồi và vận hành."
    }
  },
  {
    href: "/admin/knowledge-sources",
    label: "Nguồn tri thức",
    icon: "database",
    desc: "Knowledge Hub hợp nhất",
    group: "admin",
    roles: ["researcher", "doctor", "admin"],
    page: {
      title: "Knowledge Hub",
      subtitle: "Trung tâm hợp nhất retrieval connectors, tài liệu và đồng bộ nguồn y khoa."
    }
  },
  {
    href: "/admin/answer-flow",
    label: "Luồng trả lời",
    icon: "alt_route",
    desc: "Điều phối phân tích và phản hồi",
    group: "admin",
    roles: ["researcher", "doctor", "admin"],
    page: {
      title: "Luồng trả lời",
      subtitle: "Điều phối các bước phân tích, xác minh và phản hồi cuối."
    }
  },
  {
    href: "/admin/observability",
    label: "Giám sát vận hành",
    icon: "monitoring",
    desc: "Theo dõi cảnh báo runtime",
    group: "admin",
    roles: ["researcher", "doctor", "admin"],
    page: {
      title: "Giám sát vận hành",
      subtitle: "Theo dõi tình trạng hệ thống, cảnh báo và tín hiệu runtime."
    }
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
      subtitle: "Các bước sử dụng nhanh cho người mới."
    }
  }
];

const GROUP_ORDER: NavGroupKey[] = ["core", "clinical", "medication", "admin", "support"];

export const GROUP_LABELS: Record<NavGroupKey, string> = {
  core: "Workspace",
  clinical: "Lâm sàng",
  medication: "Thuốc và an toàn",
  admin: "Quản trị hệ thống",
  support: "Hỗ trợ"
};

const GROUP_META: Record<NavGroupKey, NavGroupMeta> = {
  core: { label: "Workspace", shortLabel: "Workspace", icon: "workspaces" },
  clinical: { label: "Lâm sàng", shortLabel: "Lâm sàng", icon: "stethoscope" },
  medication: { label: "Thuốc và an toàn", shortLabel: "An toàn", icon: "shield" },
  admin: { label: "Quản trị hệ thống", shortLabel: "Quản trị", icon: "settings_input_component" },
  support: { label: "Hỗ trợ", shortLabel: "Hỗ trợ", icon: "help" }
};

const DEFAULT_PAGE_META: PageMeta = {
  title: "Không gian làm việc",
  subtitle: "Nền tảng trợ lý y tế giúp bạn xử lý công việc nhanh và rõ ràng hơn."
};

export function isPublicRoute(pathname: string): boolean {
  return PUBLIC_ROUTES.has(pathname);
}

export function getRoleHomePath(role: UserRole = "normal"): string {
  return ROLE_HOME_PATHS[role] ?? DEFAULT_POST_LOGIN_PATH;
}

export function sanitizeNextPath(nextPath: string | null | undefined): string | null {
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

export function resolvePostLoginPath(options: { nextPath?: string | null; role?: UserRole }): string {
  return sanitizeNextPath(options.nextPath) ?? getRoleHomePath(options.role ?? "normal");
}

export function getNavItemsByRole(role: UserRole): NavigationItem[] {
  return NAV_ITEMS.filter((item) => item.roles.includes(role));
}

export function getGroupedNavItems(role: UserRole): Array<{ key: NavGroupKey; label: string; items: NavigationItem[] }> {
  const items = getNavItemsByRole(role);
  return GROUP_ORDER.map((groupKey) => {
    const groupItems = items.filter((item) => item.group === groupKey);
    return {
      key: groupKey,
      label: GROUP_META[groupKey].label,
      items: groupItems
    };
  }).filter((group) => group.items.length > 0);
}

export function getMobilePrimaryNav(role: UserRole): NavigationItem[] {
  return getNavItemsByRole(role).filter((item) => item.mobilePrimary).slice(0, 4);
}

export function getGroupMeta(group: NavGroupKey): NavGroupMeta {
  return GROUP_META[group];
}

export function getTopNavLinks(role: UserRole): Array<{ href: string; label: string; icon: string }> {
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
        icon: meta.icon
      };
    })
    .filter((item): item is { href: string; label: string; icon: string } => Boolean(item));
}

export function getPageMeta(pathname: string): PageMeta {
  const exact = NAV_ITEMS.find((item) => item.href === pathname);
  if (exact) return exact.page;

  if (pathname === "/research" || pathname.startsWith("/research/")) {
    return {
      title: "Hỏi đáp chuyên môn",
      subtitle: "Tra cứu câu trả lời có dẫn nguồn để hỗ trợ quyết định lâm sàng."
    };
  }

  const prefixSorted = [...NAV_ITEMS].sort((a, b) => b.href.length - a.href.length);
  const prefixMatch = prefixSorted.find((item) => pathname.startsWith(`${item.href}/`));
  if (prefixMatch) return prefixMatch.page;

  if (pathname.startsWith("/dashboard/control-tower")) {
    return {
      title: "Điều phối tri thức",
      subtitle: "Thiết lập nguồn dữ liệu và luồng phản hồi cho hệ thống hỏi đáp."
    };
  }

  if (pathname.startsWith("/dashboard/ecosystem")) {
    return {
      title: "Hệ sinh thái đối tác",
      subtitle: "Theo dõi trạng thái kết nối và độ tin cậy dữ liệu liên thông."
    };
  }

  return DEFAULT_PAGE_META;
}

export function isActiveRoute(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}
