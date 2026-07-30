import type { UILanguage } from "@/lib/ui-language";
import { CONSUMER_TERMINOLOGY_MESSAGES } from "./consumer-terminology.generated";

// Keep end-user shell language in one typed source. Product pages that still
// own domain-specific bilingual copy can migrate incrementally without
// changing persisted locale semantics.
const VI_MESSAGES = {
  ...CONSUMER_TERMINOLOGY_MESSAGES.vi,
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
  "today.description":
    "Một nhịp chăm sóc rõ ràng: chỉ những việc bạn đã chấp nhận mới xuất hiện ở đây.",
  "today.following": "Theo dõi cùng bạn",
  "today.notConclusion": "Chưa dùng làm kết luận",
  "today.next": "Việc nên làm tiếp theo",
  "today.control": "Bạn luôn có quyền bỏ qua hoặc điều chỉnh kế hoạch.",
  "today.viewTask": "Xem việc",
  "today.createEpisode": "Tạo hành trình",
  "today.connectionError": "Kiểm tra kết nối rồi thử lại.",
  "today.startHere": "Bạn muốn làm gì?",
  "today.startHereDescription":
    "Chọn một việc để bắt đầu. Bạn có thể quay lại bất cứ lúc nào.",
  "today.askTitle": "Hỏi về sức khỏe",
  "today.askDescription":
    "Nêu điều bạn đang lo; CLARA sẽ giúp xác định bước an toàn tiếp theo.",
  "today.medicineTitle": "Kiểm tra thuốc",
  "today.medicineDescription":
    "Xem thuốc đang dùng và kiểm tra tương tác có nguồn.",
  "today.recordTitle": "Lưu thông tin khám",
  "today.recordDescription":
    "Gom toa thuốc, kết quả và thông tin sức khỏe cá nhân.",
  "today.visitTitle": "Chuẩn bị đi khám",
  "today.visitDescription":
    "Chuẩn bị câu hỏi và thông tin quan trọng cho buổi khám.",
  "today.openAction": "Mở",
  "visitPrep.title": "Chuẩn bị cho buổi khám",
  "visitPrep.description": "Tạo một bản nháp riêng để bạn xem, chỉnh sửa và mang theo khi đi khám.",
  "visitPrep.goalLabel": "Bạn muốn trao đổi điều gì trong buổi khám?",
  "visitPrep.goalHint": "Không bắt buộc. CLARA chỉ dùng câu này để chọn các ghi nhận LifeMap liên quan.",
  "visitPrep.build": "Tạo bản nháp",
  "visitPrep.building": "Đang tạo bản nháp…",
  "visitPrep.unavailable": "Tính năng chuẩn bị buổi khám hiện chưa được bật cho hồ sơ này.",
  "visitPrep.reviewNotice": "Đây là bản nháp để bạn tự xem và sửa. Nó không thay đổi hồ sơ sức khỏe của bạn.",
  "visitPrep.importantNow": "Điều quan trọng lúc này",
  "visitPrep.basedOn": "CLARA dựa vào các ghi nhận này",
  "visitPrep.uncertainty": "Điều cần kiểm tra thêm",
  "visitPrep.nextStep": "Việc bạn có thể làm tiếp",
  "visitPrep.urgent": "Khi nào cần hỗ trợ khẩn cấp",
  "visitPrep.questions": "Câu hỏi bạn có thể mang theo",
  "visitPrep.copy": "Sao chép bản nháp",
  "visitPrep.copied": "Đã sao chép bản nháp",
  "visitPrep.noDraft": "Chưa có bản nháp. Hãy chọn tạo bản nháp khi bạn sẵn sàng.",
  "visitPrep.error": "Chưa thể tạo bản nháp. Kiểm tra kết nối rồi thử lại.",
  "visitPrep.back": "Quay lại lịch khám",
  "visitPrep.noQuestions": "Chưa có câu hỏi gợi ý từ các ghi nhận trong phạm vi này.",
  "medicines.title": "Thuốc & an toàn tương tác",
  "medicines.description":
    "Quản lý thuốc đã xác nhận, tủ thuốc cá nhân và kiểm tra tương tác an toàn trong một nơi.",
  "medicines.tabs": "Khu vực thuốc và an toàn tương tác",
  "medicines.tab.list": "Thuốc của tôi",
  "medicines.tab.cabinet": "Tủ thuốc",
  "medicines.tab.safety": "An toàn tương tác",
  "surface.loadFailed": "Chưa thể tải dữ liệu",
  "surface.retry": "Thử lại",
  "surface.loading": "Đang tải",
  "flow.saveFailed": "Chưa thể lưu thay đổi",
  "flow.savingDraft": "Đang lưu bản nháp…",
  "flow.savedDraft": "Đã lưu bản nháp",
  "flow.progress": "Tiến trình",
  "flow.stepOf": "Bước {current} / {total}",
  "flow.complete": "đã hoàn tất",
  "flow.current": "hiện tại",
  "flow.notStarted": "chưa bắt đầu",
  "flow.checkInformation": "Kiểm tra lại thông tin",
  "flow.fixBeforeContinue":
    "Có một vài mục cần được sửa trước khi bạn tiếp tục.",
} as const;

type TranslationKey = keyof typeof VI_MESSAGES;
type MessageCatalog = Record<TranslationKey, string>;

const EN_MESSAGES: MessageCatalog = {
  ...CONSUMER_TERMINOLOGY_MESSAGES.en,
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
  "today.description":
    "A clear care rhythm: only tasks you accepted appear here.",
  "today.following": "Tracking with you",
  "today.notConclusion": "Not used as a conclusion",
  "today.next": "Your next care step",
  "today.control": "You can always skip or adjust your plan.",
  "today.viewTask": "View task",
  "today.createEpisode": "Create journey",
  "today.connectionError": "Check your connection and try again.",
  "today.startHere": "What would you like to do?",
  "today.startHereDescription":
    "Choose one task to start. You can return at any time.",
  "today.askTitle": "Ask about your health",
  "today.askDescription":
    "Share what concerns you; CLARA will help identify a safe next step.",
  "today.medicineTitle": "Check medication",
  "today.medicineDescription":
    "Review current medication and source-backed interaction checks.",
  "today.recordTitle": "Save visit information",
  "today.recordDescription":
    "Gather prescriptions, results and personal health information.",
  "today.visitTitle": "Prepare for a visit",
  "today.visitDescription":
    "Prepare your questions and important information for a visit.",
  "today.openAction": "Open",
  "visitPrep.title": "Prepare for your visit",
  "visitPrep.description": "Create a private draft to review, edit and bring to your visit.",
  "visitPrep.goalLabel": "What would you like to discuss at your visit?",
  "visitPrep.goalHint": "Optional. CLARA only uses this to select relevant LifeMap records.",
  "visitPrep.build": "Create draft",
  "visitPrep.building": "Creating draft…",
  "visitPrep.unavailable": "Visit preparation is not enabled for this profile yet.",
  "visitPrep.reviewNotice": "This is a draft for you to review and edit. It does not change your health record.",
  "visitPrep.importantNow": "What matters now",
  "visitPrep.basedOn": "CLARA based this on these records",
  "visitPrep.uncertainty": "What needs checking",
  "visitPrep.nextStep": "What you can do next",
  "visitPrep.urgent": "When to seek emergency help",
  "visitPrep.questions": "Questions you can bring",
  "visitPrep.copy": "Copy draft",
  "visitPrep.copied": "Draft copied",
  "visitPrep.noDraft": "No draft yet. Create one when you are ready.",
  "visitPrep.error": "We could not create the draft. Check your connection and try again.",
  "visitPrep.back": "Back to visits",
  "visitPrep.noQuestions": "There are no suggested questions from records in this scope.",
  "medicines.title": "Medication & interaction safety",
  "medicines.description":
    "Manage confirmed medication, your personal medicine cabinet and safe interaction checks in one place.",
  "medicines.tabs": "Medication and interaction safety area",
  "medicines.tab.list": "My medication",
  "medicines.tab.cabinet": "Medicine cabinet",
  "medicines.tab.safety": "Interaction safety",
  "surface.loadFailed": "We couldn't load the data",
  "surface.retry": "Try again",
  "surface.loading": "Loading",
  "flow.saveFailed": "Could not save changes",
  "flow.savingDraft": "Saving draft…",
  "flow.savedDraft": "Draft saved",
  "flow.progress": "Progress",
  "flow.stepOf": "Step {current} / {total}",
  "flow.complete": "complete",
  "flow.current": "current",
  "flow.notStarted": "not started",
  "flow.checkInformation": "Check your information",
  "flow.fixBeforeContinue":
    "A few items need to be corrected before you continue.",
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
  return new Intl.DateTimeFormat(
    locale === "vi" ? "vi-VN" : "en-US",
    options,
  ).format(new Date(value));
}

export function formatLocaleNumber(locale: UILanguage, value: number): string {
  return new Intl.NumberFormat(locale === "vi" ? "vi-VN" : "en-US").format(
    value,
  );
}
