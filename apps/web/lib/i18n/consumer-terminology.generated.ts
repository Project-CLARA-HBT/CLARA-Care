import type { UILanguage } from "@/lib/ui-language";

// GENERATED FROM contracts/consumer-terminology/consumer-terminology.v1.json.
// Static product wording only. This is not a clinical-language translation
// layer and must not receive medical free text, PII, state, or safety data.
export const CONSUMER_TERMINOLOGY_VERSION = "2026-07-30.v1" as const;

export const CONSUMER_TERMINOLOGY_MESSAGES = {
  vi: {
    "action.askClara": "Hỏi CLARA",
    "action.complete": "Hoàn tất",
    "action.open": "Mở",
    "action.retry": "Thử lại",
    "navigation.today": "Hôm nay",
    "navigation.lifeMap": "Hành trình sức khỏe",
    "navigation.medicines": "Thuốc",
    "navigation.profile": "Hồ sơ",
    "today.title": "Hôm nay",
    "today.openLifeMap": "Mở hành trình sức khỏe",
    "today.pending": "Việc đang chờ",
    "today.accepted": "Đã đồng ý thực hiện",
    "today.episodes": "Hành trình đang mở",
    "today.confirmation": "Cần xác nhận",
    "today.noDueDate": "Không có hạn cụ thể",
    "today.dueDate": "Hạn: {date}",
    "today.emptyTitle": "Hôm nay chưa có việc nào",
    "today.emptyDescription": "Khi bạn chấp nhận một việc trong hành trình sức khỏe, nó sẽ xuất hiện ở đây. CLARA không tự thêm việc thay bạn.",
  },
  en: {
    "action.askClara": "Ask CLARA",
    "action.complete": "Complete",
    "action.open": "Open",
    "action.retry": "Try again",
    "navigation.today": "Today",
    "navigation.lifeMap": "Health journey",
    "navigation.medicines": "Medicines",
    "navigation.profile": "Profile",
    "today.title": "Today",
    "today.openLifeMap": "Open health journey",
    "today.pending": "Pending tasks",
    "today.accepted": "Accepted by you",
    "today.episodes": "Open journeys",
    "today.confirmation": "Needs confirmation",
    "today.noDueDate": "No specific due date",
    "today.dueDate": "Due: {date}",
    "today.emptyTitle": "No tasks for today",
    "today.emptyDescription": "A task appears here after you accept it in your health journey. CLARA never adds one for you.",
  },
} as const satisfies Record<UILanguage, Record<string, string>>;

export type ConsumerTerminologyKey = keyof typeof CONSUMER_TERMINOLOGY_MESSAGES.vi;
