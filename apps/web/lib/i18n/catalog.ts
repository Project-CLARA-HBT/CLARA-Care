import type { UILanguage } from "@/lib/ui-language";

// Keep end-user shell language in one typed source. Product pages that still
// own domain-specific bilingual copy can migrate incrementally without
// changing persisted locale semantics.
const VI_MESSAGES = {
  "theme.light": "Sáng",
  "theme.dark": "Tối",
  "theme.system": "Theo hệ thống",
  "theme.switchToLight": "Chuyển sang giao diện sáng",
  "theme.switchToDark": "Chuyển sang giao diện tối",
  "language.preference": "Tùy chọn ngôn ngữ",
  "language.change": "Đổi ngôn ngữ",
  "language.vi": "Tiếng Việt",
  "language.en": "English",
  "navigation.primary": "Điều hướng chính",
  "navigation.care": "Chăm sóc của bạn",
  "navigation.medicines": "Thuốc & an toàn",
  "navigation.explore": "Tìm hiểu",
  "navigation.clinical": "Lâm sàng",
  "navigation.admin": "Vận hành",
  "navigation.support": "Hỗ trợ",
  "action.askClara": "Hỏi CLARA",
  "action.signOut": "Đăng xuất",
  "action.signingOut": "Đang đăng xuất…",
  "action.collapse": "Thu gọn",
  "action.expand": "Mở rộng",
  "help.open": "Mở trung tâm hướng dẫn",
  "help.title": "Hướng dẫn",
  "family.title": "Vòng tròn gia đình",
  "profile.active": "Hồ sơ đang dùng",
  "profile.account": "Tài khoản",
  "profile.yourAccount": "Tài khoản của bạn",
  "profile.shared": "Được chia sẻ · ",
  "profile.sharedAccess": "Quyền được chia sẻ",
  "profile.currentRole": "Vai trò hiện tại: {role}",
  "role.normal": "Cá nhân",
  "role.researcher": "Nhà nghiên cứu",
  "role.doctor": "Bác sĩ",
  "role.admin": "Quản trị viên",
  "family.pendingTasks": "{count} nhiệm vụ chăm sóc được chia sẻ đang chờ",
} as const;

type TranslationKey = keyof typeof VI_MESSAGES;
type MessageCatalog = Record<TranslationKey, string>;

const EN_MESSAGES: MessageCatalog = {
  "theme.light": "Light",
  "theme.dark": "Dark",
  "theme.system": "System",
  "theme.switchToLight": "Switch to light theme",
  "theme.switchToDark": "Switch to dark theme",
  "language.preference": "Language preferences",
  "language.change": "Change language",
  "language.vi": "Vietnamese",
  "language.en": "English",
  "navigation.primary": "Primary navigation",
  "navigation.care": "Your care",
  "navigation.medicines": "Medication & safety",
  "navigation.explore": "Explore",
  "navigation.clinical": "Clinical",
  "navigation.admin": "Operations",
  "navigation.support": "Support",
  "action.askClara": "Ask CLARA",
  "action.signOut": "Sign out",
  "action.signingOut": "Signing out…",
  "action.collapse": "Collapse",
  "action.expand": "Expand",
  "help.open": "Open help centre",
  "help.title": "Help",
  "family.title": "Family Circle",
  "profile.active": "Active profile",
  "profile.account": "Account",
  "profile.yourAccount": "Your account",
  "profile.shared": "Shared · ",
  "profile.sharedAccess": "Shared access",
  "profile.currentRole": "Current role: {role}",
  "role.normal": "Personal",
  "role.researcher": "Researcher",
  "role.doctor": "Doctor",
  "role.admin": "Administrator",
  "family.pendingTasks": "{count} shared care task(s) pending",
};

export const UI_MESSAGES: Record<UILanguage, MessageCatalog> = {
  vi: VI_MESSAGES,
  en: EN_MESSAGES,
};

export type UITranslationKey = TranslationKey;

export function t(
  locale: UILanguage,
  key: UITranslationKey,
  values: Record<string, string | number> = {},
): string {
  return UI_MESSAGES[locale][key].replace(/\{(\w+)\}/g, (_, name: string) =>
    String(values[name] ?? `{${name}}`),
  );
}

export function formatLocaleDate(
  locale: UILanguage,
  value: Date | number | string,
  options: Intl.DateTimeFormatOptions = { dateStyle: "medium" },
): string {
  return new Intl.DateTimeFormat(locale === "vi" ? "vi-VN" : "en-US", options).format(
    new Date(value),
  );
}

export function formatLocaleNumber(locale: UILanguage, value: number): string {
  return new Intl.NumberFormat(locale === "vi" ? "vi-VN" : "en-US").format(value);
}
