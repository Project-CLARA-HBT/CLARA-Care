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
    // The health-record hub and its focused editor routes share this page.
    // All static labels, safety clarification, empty/error state, and ARIA
    // labels must come from the typed catalog; record values remain user data.
    path: "app/phr/page.tsx",
    required: [
      "@/lib/i18n/catalog",
      "phr.title",
      "phr.disclaimer",
      "phr.hub.identity.title",
      "phr.completeness.class.patientDemographics",
      "phr.error.sectionNotFound.title",
    ],
    forbidden: [
      'title: "Hồ sơ sức khỏe cá nhân"',
      'title: "Personal Health Record"',
      '"Hồ sơ này do bạn tự khai báo, chỉ dùng để hỗ trợ ra quyết định',
      '"This record is self-declared and for decision support only',
      '"Danh tính cơ bản"',
      '"Identity"',
    ],
  },
  {
    // OCR is a medical-data processing surface: localized acknowledgement,
    // disclosure, errors and accessible labels must move as one catalog-backed
    // boundary rather than leaving a component-local bilingual map behind.
    path: "components/phr/ocr-review-modal.tsx",
    required: [
      "@/lib/i18n/catalog",
      "phr.ocr.disclosure",
      "phr.ocr.consentNotice",
      "phr.ocr.processingNotice",
      "phr.ocr.confirmError",
    ],
    forbidden: [
      "Quét đơn thuốc (OCR)",
      "Scan prescription (OCR)",
      "Tải lên ảnh hoặc tệp đơn thuốc.",
      "Upload a prescription image or file.",
    ],
  },
  {
    path: "components/phr/share-manager.tsx",
    required: [
      "@/lib/i18n/catalog",
      "phr.share.createError",
      "phr.share.scopeEmergency",
      "formatLocaleDate(uiLanguage",
    ],
    forbidden: ["Chia sẻ hồ sơ (chỉ đọc)", "Share record (read-only)"],
  },
  {
    path: "components/phr/export-button.tsx",
    required: ["@/lib/i18n/catalog", "phr.export.title", "phr.export.resource.all"],
    forbidden: ["Xuất hồ sơ (FHIR)", "Export record (FHIR)"],
  },
  {
    path: "components/phr/emergency-card-editor.tsx",
    required: [
      "@/lib/i18n/catalog",
      "phr.emergencyCard.title",
      "phr.emergencyCard.field.allergies",
    ],
    forbidden: ["Thẻ khẩn cấp", "Emergency card"],
  },
  {
    path: "components/phr/reminders-panel.tsx",
    required: ["@/lib/i18n/catalog", "phr.reminders.title", "phr.reminders.addError"],
    forbidden: ["Nhắc uống thuốc", "Medication reminders"],
  },
  {
    path: "app/account/data/delete/[step]/delete-data-flow-client.tsx",
    required: [
      "@/lib/i18n/catalog",
      "account.dataDelete.confirmation",
      "formatLocaleDate(uiLanguage",
    ],
    forbidden: [
      "Xóa dữ liệu cá nhân",
      "Delete personal data",
      "toLocaleString()",
      "toLocaleDateString()",
    ],
  },
  {
    path: "app/admin/dsar/page.tsx",
    required: [
      "@/lib/i18n/catalog",
      "admin.dsar.loadError",
      "admin.dsar.status.received",
      "formatLocaleDate(uiLanguage",
    ],
    forbidden: [
      "Hàng đợi DSAR (Quản trị)",
      "DSAR queue (Admin)",
      "err instanceof Error ? err.message",
      "toLocaleString()",
      "toLocaleDateString()",
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
    // Visit preparation is intentionally a two-step, review-only flow. The
    // generated draft and cited source records remain immutable; the only
    // editable field is client-memory notes that are neither persisted nor
    // submitted to LifeMap.
    path: "app/lifemap/visit-prep/page.tsx",
    required: [
      "@/lib/i18n/catalog",
      "StepProgress",
      "visitPrep.step.scope",
      "visitPrep.step.review",
      "visitPrep.localNotes.label",
      "setNotes",
      "onNotesChange",
    ],
    forbidden: [
      "Your notes or questions",
      "Ghi chú hoặc câu hỏi của bạn",
      "localStorage",
      "sessionStorage",
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
  {
    path: "app/chat/_v2/components/MedicalAnswerCanvas.tsx",
    required: [
      "@/lib/i18n/catalog",
      "chat.answerCanvas.aria",
      "chat.answerCanvas.evidence.inspectLedger",
      "chat.answerCanvas.medicineSafety.description",
    ],
    forbidden: [
      "Medical answer canvas",
      "Bảng câu trả lời y khoa",
      "Inspect evidence ledger",
      "Xem sổ bằng chứng",
      "No retrievable evidence; do not treat this as decision-ready.",
      "Không có bằng chứng truy xuất được; chưa thể dùng để ra quyết định.",
    ],
  },
  {
    path: "app/chat/_v2/components/AnswerRenderer.tsx",
    required: [
      "@/lib/i18n/catalog",
      "chat.answerRenderer.degraded",
      "chat.answerRenderer.integrity.title",
      "chat.answerRenderer.references",
    ],
    forbidden: [
      "Degraded · local fallback",
      "Suy giảm · dự phòng nội bộ",
      "(No answer text)",
      "(Chưa có nội dung trả lời)",
      "Citation Registry",
      "Danh mục trích dẫn",
      "References (",
      "Nguồn tham khảo (",
    ],
  },
  {
    path: "app/chat/_v2/components/FlowTimeline.tsx",
    required: ["@/lib/i18n/catalog", "chat.flowTimeline.heading"],
    forbidden: ["Reasoning flow", "Luồng suy luận"],
  },
  {
    path: "app/chat/_v2/components/MessageLog.tsx",
    required: ["@/lib/i18n/catalog", "chat.messageLog.aria"],
    forbidden: ['"Conversation"', '"Cuộc trò chuyện"'],
  },
  {
    path: "app/chat/_v2/components/TurnView.tsx",
    required: [
      "@/lib/i18n/catalog",
      "chat.turnView.aria",
      "chat.turnView.displayFailed",
      "chat.turnView.refineEvidence",
    ],
    forbidden: [
      '"Conversation turn"',
      '"Lượt trò chuyện"',
      '"This answer could not be displayed."',
      '"Không thể hiển thị câu trả lời này."',
      '"Refine with a new evidence run"',
      '"Tinh chỉnh bằng lượt nghiên cứu mới"',
      '"Investigate with Medical Research"',
      '"Nghiên cứu y khoa chuyên sâu"',
    ],
  },
  {
    path: "app/chat/_v2/components/TelemetryPanel.tsx",
    required: [
      "@/lib/i18n/catalog",
      "chat.telemetryPanel.aria",
      "chat.telemetryPanel.sourceIntel",
      "chat.telemetryPanel.empty",
    ],
    forbidden: [
      '"System telemetry"',
      '"Telemetry hệ thống"',
      '"Source intel"',
      '"Nguồn"',
      '"No source signal yet."',
      '"Chưa có tín hiệu nguồn."',
    ],
  },
  {
    path: "components/chat-workspace/chat-composer.tsx",
    required: [
      "@/lib/i18n/catalog",
      "chat.composer.questionLabel",
      "chat.legacyComposer.advanced",
      "chat.legacyComposer.liveStatusFallback",
    ],
    forbidden: [
      '"Chat composer input"',
      '"Nhập câu hỏi y tế của bạn..."',
      '"Enter your medical question..."',
      '"Cách trả lời"',
      '"Mode"',
      '"Tùy chọn"',
      '"Options"',
      '"CLARA đang phân tích câu hỏi..."',
      '"CLARA is analyzing your question..."',
    ],
  },
  {
    // Static starter questions are catalog-owned. Runtime answers, API data,
    // user-entered workspace content, and vi-VN/en-US date-format identifiers
    // are deliberately outside this literal-copy contract.
    path: "app/chat/_legacy/page-legacy.tsx",
    required: [
      "@/lib/i18n/catalog",
      "safeUserFacingError",
      "QUICK_PROMPT_KEYS",
      "chat.legacyWorkspace.quickPrompt.metformin",
      "chat.legacyWorkspace.quickPrompt.sideEffects",
      "chat.legacyWorkspace.error.submit",
      "chat.legacyWorkspace.notice.bulkUpdated",
      "chat.legacyWorkspace.confirm.bulkDelete",
      "chat.legacyWorkspace.notice.conversationExported",
    ],
    forbidden: [
      "Tôi đang uống metformin, cần lưu ý gì?",
      "Thuốc này có tương tác với thuốc nào?",
      "Giải thích kết quả xét nghiệm này giúp tôi.",
      "Khi nào tôi nên đi khám bác sĩ?",
      "Tác dụng phụ thường gặp của thuốc này là gì?",
      "I take metformin. What should I watch for?",
      "Which medicines can this interact with?",
      "Help me understand this lab result.",
      "When should I see a doctor?",
      "What common side effects can this medicine cause?",
      "Hãy chọn conversation trước khi chạy bulk action.",
      "Đã cập nhật ${result.updated_count} conversation.",
      "Xóa ${selectedConversationIds.length} conversation đã chọn?",
      "Đã export conversation #${conversationId} (${format}).",
      "Tiêu đề note không được để trống.",
    ],
  },
  {
    path: "app/chat/_v2/ChatShell.tsx",
    required: [
      "@/lib/i18n/catalog",
      "chat.shell.notice.researchReady",
      "chat.shell.command.newChat",
      "chat.shell.mode.fast",
      "chat.shell.skipToConversation",
      "chat.shell.disclaimer",
    ],
    forbidden: [
      '"Research mode is ready. Refine the question or run it now."',
      '"Đã sẵn sàng chế độ Nghiên cứu. Bạn có thể chỉnh câu hỏi hoặc chạy ngay."',
      '"Answer saved locally; backend sync will recover later."',
      '"Đã lưu local; backend sync sẽ khôi phục sau."',
      '"New chat"',
      '"Chat mới"',
      '"Skip to conversation"',
      '"Tới khung trò chuyện"',
      '"CLARA is an AI health information assistant, not a replacement for a clinician."',
      '"CLARA là AI hỗ trợ thông tin y tế, không thay thế bác sĩ hoặc nhân viên y tế."',
    ],
  },
  {
    path: "app/medicines/safety-tab.tsx",
    required: [
      "@/lib/i18n/catalog",
      "medicines.safety.clarification.title",
      "medicines.safety.clarification.selectRequired",
      "medicines.safety.clarification.continue",
    ],
    forbidden: [
      "Confirm medicines before checking",
      "Xác nhận thuốc trước khi kiểm tra",
      "Continue interaction check",
      "Tiếp tục kiểm tra tương tác",
    ],
  },
  {
    // The ecosystem center exposes operational data, but its shell and error
    // boundary must respect the selected locale without changing telemetry.
    path: "app/dashboard/ecosystem/page.tsx",
    required: [
      "@/lib/i18n/catalog",
      "@/lib/use-ui-language",
      "safeUserFacingError",
      "ecosystem.pageTitle",
      "ecosystem.error.load",
      "formatLocaleDate(language",
    ],
    forbidden: [
      'title="Technical Monitoring Hub"',
      "Ecosystem Control Plane",
      "Không thể tải trung tâm hệ sinh thái. Vui lòng thử lại.",
      'toLocaleString("vi-VN")',
    ],
  },
  {
    // Council overview presents safety-oriented chrome around structured,
    // dynamic specialist and clinical content. This gate covers only the
    // static chrome; it intentionally does not constrain clinical outputs.
    path: "app/council/page.tsx",
    required: [
      "@/lib/i18n/catalog",
      "council.overview.banner.safety.title",
      "council.overview.timeline.status.missing",
      "council.overview.rerun.action",
      "council.overview.summary.title",
    ],
    forbidden: [
      "Sơ đồ bất đồng chuyên khoa",
      "Hệ thống chưa đạt đồng thuận tự động",
      "Timeline hội chẩn",
      "Tiến trình trực tiếp",
      "Chạy lại hội chẩn",
    ],
  },
  {
    // The workflow diagram is End_User-visible chrome. Its labels must stay
    // catalog-backed, including the SVG accessibility name, while its actual
    // safety/routing state remains deterministic component data.
    path: "components/council/council-flow-canvas.tsx",
    required: [
      "@/lib/i18n/catalog",
      "useUILanguage",
      "council.flow.aria",
      "council.flow.node.input.title",
      "council.flow.node.emergency.subtitle",
      "council.flow.review.needsMoreInfo",
    ],
    forbidden: [
      "Council Flow Canvas",
      "Pipeline hội chẩn dạng futuristic, tối ưu dark/light",
      "Council consultation flow canvas",
      'title: "Case Intake"',
      'subtitle: "Immediate escalation"',
      '"cần bổ sung thông tin"',
      '"cần người có chuyên môn rà soát"',
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
  // Vietnamese keeps literal message values (`as const`) so it can define the
  // translation-key union. English is intentionally annotated as
  // `MessageCatalog`, which makes TypeScript reject missing or unexpected
  // keys. Accept both declarations here: this CI gate must not silently stop
  // checking parity just because the implementation uses that safer typing.
  const match = catalogSource.match(
    new RegExp(
      `const ${name}\\s*(?::[^=]+)?=\\s*\\{([\\s\\S]*?)^\\}\\s*(?:as const)?;$`,
      "m",
    ),
  );
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
