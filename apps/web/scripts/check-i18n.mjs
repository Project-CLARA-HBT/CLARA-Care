#!/usr/bin/env node

/**
 * Catalog contract for migrated, end-user-facing web surfaces.
 *
 * This intentionally has no test-runner dependency, so it is a required CI
 * gate before lint/build. A surface may only be added after all listed visible
 * strings have been moved to `t(locale, key)`. The contract is checked on
 * every web change; it is not an opt-in developer command.
 */
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const WEB_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const CATALOG_PATH = resolve(WEB_ROOT, "lib/i18n/catalog.ts");

const MIGRATED_SURFACES = [
  {
    path: "app/layout.tsx",
    required: ["UI_LANGUAGE_COOKIE_NAME", "await cookies()"],
    forbidden: ['<html lang="vi"'],
  },
  {
    path: "components/app-shell.tsx",
    required: ["@/lib/i18n/catalog", "action.askClara", "language.preference"],
    forbidden: ["Hỏi CLARA", "Ask CLARA", "Tùy chọn ngôn ngữ", "Language preferences"],
  },
  {
    path: "components/navigation/app-topbar.tsx",
    required: ["@/lib/i18n/catalog", "action.askClara", "language.change"],
    forbidden: ["Hỏi CLARA", "Ask CLARA", "Đổi ngôn ngữ", "Change language"],
  },
  {
    path: "components/sidebar-nav.tsx",
    required: ["@/lib/i18n/catalog", "navigation.primary", "action.signOut"],
    forbidden: ["Hỏi CLARA", "Ask CLARA", "Đăng xuất", "Sign out", "Điều hướng chính", "Primary navigation"],
  },
  {
    path: "components/ui/surface.tsx",
    required: ["@/lib/i18n/catalog", "surface.loadFailed", "surface.retry", "surface.loading"],
    forbidden: ["Chưa thể tải dữ liệu", "We couldn't load the data", "Thử lại", "Try again"],
  },
  {
    path: "app/today/page.tsx",
    required: ["@/lib/i18n/catalog", "today.title", "today.startHere", "today.emptyDescription"],
    forbidden: ["Việc nên làm tiếp theo", "Hôm nay chưa có việc nào", "Mở LifeMap"],
  },
  {
    path: "app/today/tasks/[taskId]/page.tsx",
    required: [
      "@/lib/i18n/catalog",
      "@/lib/use-ui-language",
      "today.taskDetail.pageTitle",
      "today.taskDetail.completeAction",
      "formatLocaleDate(language",
    ],
    forbidden: [
      "Chi tiết việc hôm nay",
      "Xác nhận hoàn tất",
      "Việc này không còn trong danh sách hôm nay",
      'toLocaleString("vi-VN")',
    ],
  },
  {
    path: "app/role-select/page.tsx",
    required: ["@/lib/i18n/catalog", "@/lib/use-ui-language", "roleRedirect.title"],
    forbidden: ["Đang mở không gian của bạn", "Vai trò được xác nhận từ tài khoản"],
  },
  {
    path: "app/chat/shares/page.tsx",
    required: [
      "@/lib/i18n/catalog",
      "@/lib/use-ui-language",
      "chatShares.title",
      "chatShares.revoke",
      "formatLocaleDate(language",
    ],
    forbidden: [
      "Share Management",
      "Quản lý toàn bộ public links",
      "Đã copy public URL.",
      'toLocaleString("vi-VN")',
    ],
  },
  {
    path: "app/medicines/page.tsx",
    required: [
      "@/lib/i18n/catalog",
      "@/lib/use-ui-language",
      "medicines.title",
      "medicines.description",
      "medicines.tabs",
      "medicines.tab.list",
      "medicines.tab.cabinet",
      "medicines.tab.safety",
    ],
    forbidden: [
      "Thuốc & an toàn tương tác",
      "Medication & interaction safety",
      "Khu vực thuốc và an toàn tương tác",
      "Medication and interaction safety area",
      "Thuốc của tôi",
      "My medication",
      "Tủ thuốc",
      "Medicine cabinet",
      "An toàn tương tác",
      "Interaction safety",
    ],
  },
  {
    path: "app/lifemap/new/start-client.tsx",
    required: [
      "@/lib/i18n/catalog",
      "@/lib/use-ui-language",
      "lifemap.guided.start.title",
      "guidedFlowSteps(\"lifemapEpisode\", language)",
    ],
    forbidden: [
      "Tạo hành trình sức khoẻ",
      "Create a health journey",
      "Đang mở bản nháp an toàn của bạn",
      "Opening your safe draft",
    ],
  },
  {
    path: "app/lifemap/new/[draftId]/[step]/step-client.tsx",
    required: [
      "@/lib/i18n/catalog",
      "@/lib/use-ui-language",
      "lifemap.guided.title.label",
      "lifemap.guided.review.create",
      "guidedFlowSteps(\"lifemapEpisode\", language)",
    ],
    forbidden: [
      "Bạn muốn gọi hành trình này là gì?",
      "What would you like to call this journey?",
      "Mức ưu tiên giúp sắp xếp kế hoạch",
      "Priority helps order your plan",
    ],
  },
  {
    path: "app/chat/_v2/components/ChatWelcome.tsx",
    required: [
      "@/lib/i18n/catalog",
      "chat.welcome.researcher.eyebrow",
      "chat.welcome.doctor.eyebrow",
      "specialistWelcomeContent",
    ],
    forbidden: [
      "Tìm hiểu có dẫn nguồn",
      "Evidence with traceable sources",
      "Hỗ trợ quyết định lâm sàng",
      "Clinical decision support",
    ],
  },
  {
    path: "app/chat/_v2/components/WorkspaceDrawer.tsx",
    required: [
      "@/lib/i18n/catalog",
      "chat.workspace.title",
      "chat.workspace.notice.shareCreated",
      "formatLocaleDate(uiLanguage, item.expires_at)",
    ],
    forbidden: [
      "Không gian làm việc",
      "Workspace sections",
      "Đã tạo liên kết chia sẻ.",
      "Share link created.",
      "toLocaleDateString()",
    ],
  },
  {
    path: "app/chat/_v2/components/CommandPalette.tsx",
    required: [
      "@/lib/i18n/catalog",
      "chat.commandPalette.title",
      "chat.commandPalette.searchPlaceholder",
      "chat.commandPalette.noMatches",
    ],
    forbidden: [
      "Đóng command palette",
      "Close command palette",
      "Tìm hành động...",
      "Find an action... (new chat, export, share...)",
      "Không có hành động phù hợp.",
      "No matching action.",
    ],
  },
];

function fail(message) {
  process.stderr.write(`i18n contract: ${message}\n`);
  process.exitCode = 1;
}

function source(path) {
  return readFileSync(resolve(WEB_ROOT, path), "utf8");
}

function catalogKeys(catalogSource, name) {
  const match = catalogSource.match(new RegExp(`const ${name} = \\{([\\s\\S]*?)\\} as const;`));
  if (!match) {
    fail(`could not locate ${name} in lib/i18n/catalog.ts`);
    return [];
  }
  return [...match[1].matchAll(/^\s{2}"([^"]+)":/gm)].map((item) => item[1]);
}

function collectSourceFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const entryPath = resolve(directory, entry.name);
    if (entry.isDirectory()) return collectSourceFiles(entryPath);
    return /\.(?:ts|tsx)$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name)
      ? [entryPath]
      : [];
  });
}

const catalogSource = readFileSync(CATALOG_PATH, "utf8");
const viKeys = catalogKeys(catalogSource, "VI_MESSAGES");
const enKeys = catalogKeys(catalogSource, "EN_MESSAGES");
const viSet = new Set(viKeys);
const enSet = new Set(enKeys);

for (const key of viSet) {
  if (!enSet.has(key)) fail(`English catalog is missing key ${key}`);
}
for (const key of enSet) {
  if (!viSet.has(key)) fail(`Vietnamese catalog is missing key ${key}`);
}
if (viKeys.length !== viSet.size || enKeys.length !== enSet.size) {
  fail("catalog contains duplicate translation keys");
}

for (const surface of MIGRATED_SURFACES) {
  const content = source(surface.path);
  for (const token of surface.required) {
    if (!content.includes(token)) fail(`${surface.path} must reference ${token}`);
  }
  for (const literal of surface.forbidden) {
    if (content.includes(literal)) fail(`${surface.path} contains migrated literal: ${literal}`);
  }
}

// Detect accidental dead catalog entries in production source. Dynamic typed
// lookups (role/group/theme maps) are explicitly verified by the migrated
// surface contracts above, so a key is live if either a direct t() call or its
// contract declares it.
const sourceText = collectSourceFiles(resolve(WEB_ROOT, "app"))
  .concat(collectSourceFiles(resolve(WEB_ROOT, "components")))
  .concat(collectSourceFiles(resolve(WEB_ROOT, "lib")))
  .filter((path) => path !== CATALOG_PATH)
  .map((path) => readFileSync(path, "utf8"))
  .join("\n");
const contractKeys = new Set(MIGRATED_SURFACES.flatMap((surface) => surface.required));
for (const key of viSet) {
  const directUse = sourceText.includes(`"${key}"`) || sourceText.includes(`'${key}'`);
  if (!directUse && !contractKeys.has(key)) {
    fail(`catalog key is not referenced by production source: ${key}`);
  }
}

if (process.exitCode) process.exit(process.exitCode);
process.stdout.write(
  `i18n contract passed: ${viKeys.length} vi/en keys; ${MIGRATED_SURFACES.length} migrated surfaces checked.\n`,
);
