import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import type { UILanguage } from "@/lib/ui-language";

export type UserRole = "normal" | "researcher" | "doctor" | "admin";
export type NavGroupKey =
  | "care"
  | "medicines"
  | "explore"
  | "clinical"
  | "admin"
  | "support";

export type PageMeta = {
  title: string;
  subtitle: string;
};

export type NavigationItem = {
  href: string;
  label: string;
  /** Short label for tight surfaces (mobile bottom bar). Falls back to `label`. */
  shortLabel?: string;
  icon: string;
  desc: string;
  group: NavGroupKey;
  roles: UserRole[];
  hiddenForRoles?: UserRole[];
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
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
]);

export const DEFAULT_POST_LOGIN_PATH = "/today";

const AUTH_ENTRY_ROUTES = new Set(["/login", "/register"]);
const AUTHENTICATED_UTILITY_ROUTES = new Set(["/welcome", "/role-select"]);
const AUTHENTICATED_UTILITY_PREFIXES = ["/welcome/"];

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
    shortLabel: "Hỏi",
    icon: "chat_paste_go",
    desc: "Hỏi đáp y tế hợp nhất",
    group: "care",
    roles: ["normal", "researcher", "doctor", "admin"],
    page: {
      title: "CLARA Chat",
      subtitle:
        "Hỏi đáp y tế rõ ràng, có bằng chứng và phù hợp với vai trò của bạn.",
    },
  },
  {
    href: "/dashboard",
    label: "Tổng quan",
    shortLabel: "Tổng quan",
    icon: "dashboard",
    desc: "Bức tranh nhanh hôm nay",
    group: "care",
    roles: ["normal", "researcher", "doctor", "admin"],
    hiddenForRoles: ["normal"],
    mobilePrimary: true,
    page: {
      title: "Tổng quan công việc",
      subtitle: "Theo dõi nhanh các tác vụ chăm sóc và vận hành trong ngày.",
    },
  },
  {
    href: "/today",
    label: "Hôm nay",
    shortLabel: "Hôm nay",
    icon: "today",
    desc: "Việc chăm sóc bạn đã chấp nhận",
    group: "care",
    roles: ["normal", "researcher", "doctor", "admin"],
    mobilePrimary: true,
    page: {
      title: "Hôm nay",
      subtitle: "Các việc chăm sóc đã được bạn chấp nhận.",
    },
  },
  {
    href: "/lifemap",
    label: "Hành trình sức khỏe",
    shortLabel: "Hành trình",
    icon: "route",
    desc: "Hành trình chăm sóc của bạn",
    group: "care",
    roles: ["normal", "researcher", "doctor", "admin"],
    mobilePrimary: true,
    page: {
      title: "Hành trình sức khỏe",
      subtitle: "Tổ chức điều bạn muốn theo dõi thành hành trình nhỏ.",
    },
  },
  {
    href: "/visits",
    label: "Chuẩn bị đi khám",
    icon: "event_available",
    desc: "Câu hỏi và Visit Pack của bạn",
    group: "care",
    roles: ["normal", "researcher", "doctor", "admin"],
    page: {
      title: "Chuẩn bị buổi khám",
      subtitle: "Gom đúng thông tin bạn muốn mang đến buổi khám.",
    },
  },
  {
    href: "/family",
    label: "Người thân hỗ trợ",
    icon: "family_restroom",
    desc: "Chia sẻ tối thiểu với người hỗ trợ",
    group: "care",
    roles: ["normal", "researcher", "doctor", "admin"],
    page: {
      title: "Người thân hỗ trợ",
      subtitle: "Kiểm soát ai được xem hoặc hỗ trợ đúng một việc.",
    },
  },
  {
    href: "/research",
    label: "Tra cứu y khoa",
    shortLabel: "Tra cứu",
    icon: "science",
    desc: "Tổng hợp và kiểm chứng bằng chứng",
    group: "explore",
    roles: ["normal", "researcher", "doctor", "admin"],
    hiddenForRoles: ["normal"],
    page: {
      title: "Tra cứu y khoa",
      subtitle:
        "Phân tích chuyên sâu với nguồn, độ chắc chắn và dấu vết luận điểm.",
    },
  },
  {
    href: "/evidence",
    label: "Bằng chứng cập nhật",
    icon: "fact_check",
    desc: "Câu hỏi LifeMap với nguồn kiểm chứng",
    group: "explore",
    roles: ["normal", "researcher", "doctor", "admin"],
    hiddenForRoles: ["normal"],
    page: {
      title: "Bằng chứng đang cập nhật",
      subtitle: "Gắn câu hỏi với hành trình, xem nguồn và phần chưa chắc chắn.",
    },
  },
  {
    href: "/phr",
    label: "Hồ sơ sức khỏe cá nhân",
    shortLabel: "Hồ sơ",
    icon: "description",
    desc: "Hồ sơ sức khỏe cá nhân",
    group: "care",
    roles: ["normal", "researcher", "doctor", "admin"],
    mobilePrimary: true,
    page: {
      title: "Hồ sơ sức khỏe cá nhân",
      subtitle: "Lưu trữ và tổng hợp hồ sơ sức khỏe cá nhân.",
    },
  },
  {
    href: "/medicines",
    label: "Thuốc & an toàn",
    shortLabel: "Thuốc",
    icon: "medication",
    desc: "Thuốc, tủ thuốc và kiểm tra tương tác",
    group: "medicines",
    roles: ["normal", "researcher", "doctor", "admin"],
    mobilePrimary: true,
    page: {
      title: "Thuốc & an toàn",
      subtitle:
        "Thuốc đã xác nhận, tủ thuốc và kiểm tra tương tác — tất cả ở một nơi.",
    },
  },
  {
    // Consolidated into the /medicines hub. Kept as route-allowed (hidden for
    // every role) so the AppShell guard permits the redirect stubs to load and
    // forward into the correct hub tab instead of bouncing to the role home.
    href: "/selfmed",
    label: "Tủ thuốc",
    icon: "pill",
    desc: "Đã hợp nhất vào Thuốc & an toàn",
    group: "medicines",
    roles: ["normal", "researcher", "doctor", "admin"],
    hiddenForRoles: ["normal", "researcher", "doctor", "admin"],
    page: {
      title: "Tủ thuốc của tôi",
      subtitle: "Quản lý thuốc đang dùng và quét toa thuốc từ ảnh.",
    },
  },
  {
    href: "/careguard",
    label: "Kiểm tra tương tác",
    icon: "security",
    desc: "Đã hợp nhất vào Thuốc & an toàn",
    group: "medicines",
    roles: ["normal", "researcher", "doctor", "admin"],
    hiddenForRoles: ["normal", "researcher", "doctor", "admin"],
    page: {
      title: "Kiểm tra tương tác thuốc",
      subtitle:
        "Đối chiếu thuốc, dị ứng và triệu chứng để phát hiện rủi ro sớm.",
    },
  },
  {
    href: "/research/source-hub",
    label: "Nguồn nghiên cứu",
    icon: "database_search",
    desc: "PubMed, thuốc và nguồn y khoa",
    group: "explore",
    roles: ["researcher", "doctor", "admin"],
    page: {
      title: "Nguồn nghiên cứu",
      subtitle:
        "Đồng bộ và tra cứu các nguồn y khoa phục vụ phân tích bằng chứng.",
    },
  },

  {
    href: "/council",
    label: "Tham khảo nhiều chuyên khoa",
    icon: "groups",
    desc: "Nhiều góc nhìn chuyên khoa",
    group: "clinical",
    roles: ["doctor", "admin"],
    page: {
      title: "Tham khảo nhiều chuyên khoa",
      subtitle: "Tập hợp ý kiến đa chuyên khoa để xử lý ca khó.",
    },
  },
  {
    href: "/scribe",
    label: "Ghi chép buổi khám",
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

type LocalizedNavigationKeys = {
  label: UITranslationKey;
  desc: UITranslationKey;
  title: UITranslationKey;
  subtitle: UITranslationKey;
};

// Every navigation destination is catalog-backed. The Vietnamese source copy
// in the static route definitions remains a compatibility fallback for callers
// that do not pass a locale; all shell-facing routes use this map so English
// switches labels, descriptions and page metadata together.
const NAVIGATION_KEYS: Partial<Record<string, LocalizedNavigationKeys>> = {
  "/chat": {
    label: "navigation.item.chat.label",
    desc: "navigation.item.chat.desc",
    title: "navigation.item.chat.title",
    subtitle: "navigation.item.chat.subtitle",
  },
  "/today": {
    label: "navigation.item.today.label",
    desc: "navigation.item.today.desc",
    title: "navigation.item.today.title",
    subtitle: "navigation.item.today.subtitle",
  },
  "/lifemap": {
    label: "navigation.item.lifemap.label",
    desc: "navigation.item.lifemap.desc",
    title: "navigation.item.lifemap.title",
    subtitle: "navigation.item.lifemap.subtitle",
  },
  "/visits": {
    label: "navigation.item.visits.label",
    desc: "navigation.item.visits.desc",
    title: "navigation.item.visits.title",
    subtitle: "navigation.item.visits.subtitle",
  },
  "/family": {
    label: "navigation.item.family.label",
    desc: "navigation.item.family.desc",
    title: "navigation.item.family.title",
    subtitle: "navigation.item.family.subtitle",
  },
  "/phr": {
    label: "navigation.item.phr.label",
    desc: "navigation.item.phr.desc",
    title: "navigation.item.phr.title",
    subtitle: "navigation.item.phr.subtitle",
  },
  "/medicines": {
    label: "navigation.item.medicines.label",
    desc: "navigation.item.medicines.desc",
    title: "navigation.item.medicines.title",
    subtitle: "navigation.item.medicines.subtitle",
  },
  "/dashboard": {
    label: "navigation.item.dashboard.label",
    desc: "navigation.item.dashboard.desc",
    title: "navigation.item.dashboard.title",
    subtitle: "navigation.item.dashboard.subtitle",
  },
  "/research": {
    label: "navigation.item.research.label",
    desc: "navigation.item.research.desc",
    title: "navigation.item.research.title",
    subtitle: "navigation.item.research.subtitle",
  },
  "/evidence": {
    label: "navigation.item.evidence.label",
    desc: "navigation.item.evidence.desc",
    title: "navigation.item.evidence.title",
    subtitle: "navigation.item.evidence.subtitle",
  },
  "/selfmed": {
    label: "navigation.item.selfmed.label",
    desc: "navigation.item.selfmed.desc",
    title: "navigation.item.selfmed.title",
    subtitle: "navigation.item.selfmed.subtitle",
  },
  "/careguard": {
    label: "navigation.item.careguard.label",
    desc: "navigation.item.careguard.desc",
    title: "navigation.item.careguard.title",
    subtitle: "navigation.item.careguard.subtitle",
  },
  "/research/source-hub": {
    label: "navigation.item.sourceHub.label",
    desc: "navigation.item.sourceHub.desc",
    title: "navigation.item.sourceHub.title",
    subtitle: "navigation.item.sourceHub.subtitle",
  },
  "/council": {
    label: "navigation.item.council.label",
    desc: "navigation.item.council.desc",
    title: "navigation.item.council.title",
    subtitle: "navigation.item.council.subtitle",
  },
  "/scribe": {
    label: "navigation.item.scribe.label",
    desc: "navigation.item.scribe.desc",
    title: "navigation.item.scribe.title",
    subtitle: "navigation.item.scribe.subtitle",
  },
  "/admin/overview": {
    label: "navigation.item.adminOverview.label",
    desc: "navigation.item.adminOverview.desc",
    title: "navigation.item.adminOverview.title",
    subtitle: "navigation.item.adminOverview.subtitle",
  },
  "/admin/knowledge-sources": {
    label: "navigation.item.adminKnowledgeSources.label",
    desc: "navigation.item.adminKnowledgeSources.desc",
    title: "navigation.item.adminKnowledgeSources.title",
    subtitle: "navigation.item.adminKnowledgeSources.subtitle",
  },
  "/admin/answer-flow": {
    label: "navigation.item.adminAnswerFlow.label",
    desc: "navigation.item.adminAnswerFlow.desc",
    title: "navigation.item.adminAnswerFlow.title",
    subtitle: "navigation.item.adminAnswerFlow.subtitle",
  },
  "/admin/observability": {
    label: "navigation.item.adminObservability.label",
    desc: "navigation.item.adminObservability.desc",
    title: "navigation.item.adminObservability.title",
    subtitle: "navigation.item.adminObservability.subtitle",
  },
  "/admin/community-moderation": {
    label: "navigation.item.adminModeration.label",
    desc: "navigation.item.adminModeration.desc",
    title: "navigation.item.adminModeration.title",
    subtitle: "navigation.item.adminModeration.subtitle",
  },
  "/admin/analytics": {
    label: "navigation.item.adminAnalytics.label",
    desc: "navigation.item.adminAnalytics.desc",
    title: "navigation.item.adminAnalytics.title",
    subtitle: "navigation.item.adminAnalytics.subtitle",
  },
  "/admin/analytics/clinical": {
    label: "navigation.item.adminClinicalAnalytics.label",
    desc: "navigation.item.adminClinicalAnalytics.desc",
    title: "navigation.item.adminClinicalAnalytics.title",
    subtitle: "navigation.item.adminClinicalAnalytics.subtitle",
  },
  "/huong-dan": {
    label: "navigation.item.help.label",
    desc: "navigation.item.help.desc",
    title: "navigation.item.help.title",
    subtitle: "navigation.item.help.subtitle",
  },
  "/account/consent": {
    label: "navigation.item.consent.label",
    desc: "navigation.item.consent.desc",
    title: "navigation.item.consent.title",
    subtitle: "navigation.item.consent.subtitle",
  },
  "/account/data": {
    label: "navigation.item.dataRights.label",
    desc: "navigation.item.dataRights.desc",
    title: "navigation.item.dataRights.title",
    subtitle: "navigation.item.dataRights.subtitle",
  },
  "/admin/dsar": {
    label: "navigation.item.dsar.label",
    desc: "navigation.item.dsar.desc",
    title: "navigation.item.dsar.title",
    subtitle: "navigation.item.dsar.subtitle",
  },
  "/community": {
    label: "navigation.item.community.label",
    desc: "navigation.item.community.desc",
    title: "navigation.item.community.title",
    subtitle: "navigation.item.community.subtitle",
  },
};

function localizeNavigationItem(
  item: NavigationItem,
  language: UILanguage,
): NavigationItem {
  const keys = NAVIGATION_KEYS[item.href];
  if (!keys) return item;
  return {
    ...item,
    label: t(language, keys.label),
    shortLabel: t(language, keys.label),
    desc: t(language, keys.desc),
    page: {
      title: t(language, keys.title),
      subtitle: t(language, keys.subtitle),
    },
  };
}

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

// CLARA_Social community surface. The backend fails closed (routes 404 when
// `SOCIAL_PLATFORM_ENABLED` is off), so the nav entry is shown only when the
// matching public flag is explicitly enabled — no permanently-hidden dead item.
if (isComplianceFlagOn(process.env.NEXT_PUBLIC_SOCIAL_PLATFORM_ENABLED)) {
  NAV_ITEMS.push({
    href: "/community",
    label: "Cộng đồng",
    icon: "forum",
    desc: "Cộng đồng sức khỏe CLARA",
    group: "care",
    roles: ["normal", "researcher", "doctor", "admin"],
    page: {
      title: "Cộng đồng sức khỏe",
      subtitle:
        "Chia sẻ kinh nghiệm và hỗ trợ nhau. Không phải tư vấn y tế — nội dung được kiểm duyệt.",
    },
  });
}

const GROUP_ORDER: NavGroupKey[] = [
  "care",
  "medicines",
  "explore",
  "clinical",
  "admin",
  "support",
];

const GROUP_META: Record<NavGroupKey, NavGroupMeta> = {
  care: {
    label: "Chăm sóc của bạn",
    shortLabel: "Chăm sóc",
    icon: "favorite",
  },
  medicines: {
    label: "Thuốc & an toàn",
    shortLabel: "Thuốc",
    icon: "medication",
  },
  explore: { label: "Tìm hiểu", shortLabel: "Tìm hiểu", icon: "science" },
  clinical: { label: "Lâm sàng", shortLabel: "Lâm sàng", icon: "stethoscope" },
  admin: {
    label: "Quản trị hệ thống",
    shortLabel: "Quản trị",
    icon: "settings_input_component",
  },
  support: { label: "Hỗ trợ", shortLabel: "Hỗ trợ", icon: "help" },
};

const GROUP_KEYS: Record<
  NavGroupKey,
  { label: UITranslationKey; shortLabel: UITranslationKey }
> = {
  care: { label: "navigation.care", shortLabel: "navigation.care" },
  medicines: {
    label: "navigation.medicines",
    shortLabel: "navigation.medicines",
  },
  explore: { label: "navigation.explore", shortLabel: "navigation.explore" },
  clinical: { label: "navigation.clinical", shortLabel: "navigation.clinical" },
  admin: { label: "navigation.admin", shortLabel: "navigation.admin" },
  support: { label: "navigation.support", shortLabel: "navigation.support" },
};

export function isPublicRoute(pathname: string): boolean {
  return (
    PUBLIC_ROUTES.has(pathname) ||
    pathname.startsWith("/share/") ||
    pathname.startsWith("/phr/shared/")
  );
}

/**
 * Signed-in flows that should be route-guarded but not shown as permanent
 * navigation destinations. Onboarding is intentionally transient: once the
 * user has completed or skipped it, the everyday sidebar stays uncluttered.
 */
export function isAuthenticatedUtilityRoute(pathname: string): boolean {
  return (
    AUTHENTICATED_UTILITY_ROUTES.has(pathname) ||
    AUTHENTICATED_UTILITY_PREFIXES.some((prefix) => pathname.startsWith(prefix))
  );
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

export function getNavItemsByRole(
  role: UserRole,
  language: UILanguage = "vi",
): NavigationItem[] {
  return NAV_ITEMS.filter(
    (item) => item.roles.includes(role) && !item.hiddenForRoles?.includes(role),
  ).map((item) => localizeNavigationItem(item, language));
}

export function isRouteAllowedForRole(
  pathname: string,
  role: UserRole,
): boolean {
  return NAV_ITEMS.some(
    (item) => item.roles.includes(role) && isActiveRoute(pathname, item.href),
  );
}

export function getGroupedNavItems(
  role: UserRole,
  language: UILanguage = "vi",
): Array<{ key: NavGroupKey; label: string; items: NavigationItem[] }> {
  const items = getNavItemsByRole(role, language);
  return GROUP_ORDER.map((groupKey) => {
    const groupItems = items.filter((item) => item.group === groupKey);
    return {
      key: groupKey,
      label: t(language, GROUP_KEYS[groupKey].label),
      items: groupItems,
    };
  }).filter((group) => group.items.length > 0);
}

export function getMobilePrimaryNav(
  role: UserRole,
  language: UILanguage = "vi",
): NavigationItem[] {
  return getNavItemsByRole(role, language)
    .filter((item) => item.mobilePrimary)
    .slice(0, 4);
}

export function getGroupMeta(
  group: NavGroupKey,
  language: UILanguage = "vi",
): NavGroupMeta {
  const meta = GROUP_META[group];
  const keys = GROUP_KEYS[group];
  return {
    ...meta,
    label: t(language, keys.label),
    shortLabel: t(language, keys.shortLabel),
  };
}

export function getPageMeta(
  pathname: string,
  language: UILanguage = "vi",
): PageMeta {
  const exact = NAV_ITEMS.find((item) => item.href === pathname);
  if (exact) return localizeNavigationItem(exact, language).page;

  if (pathname === "/research" || pathname.startsWith("/research/")) {
    return {
      title: t(language, "navigation.page.researchRedirect.title"),
      subtitle: t(language, "navigation.page.researchRedirect.subtitle"),
    };
  }

  // These dashboard sub-pages have their own metadata. Resolve them before
  // the generic `/dashboard` prefix route below.
  if (pathname.startsWith("/dashboard/control-tower")) {
    return {
      title: t(language, "navigation.page.controlTower.title"),
      subtitle: t(language, "navigation.page.controlTower.subtitle"),
    };
  }

  if (pathname.startsWith("/dashboard/ecosystem")) {
    return {
      title: t(language, "navigation.page.ecosystem.title"),
      subtitle: t(language, "navigation.page.ecosystem.subtitle"),
    };
  }

  const prefixSorted = [...NAV_ITEMS].sort(
    (a, b) => b.href.length - a.href.length,
  );
  const prefixMatch = prefixSorted.find((item) =>
    pathname.startsWith(`${item.href}/`),
  );
  if (prefixMatch) return localizeNavigationItem(prefixMatch, language).page;

  return {
    title: t(language, "navigation.page.default.title"),
    subtitle: t(language, "navigation.page.default.subtitle"),
  };
}

export function isActiveRoute(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}
