"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import Button from "@/components/ui/button";
import { Icon, resolveIconName } from "@/components/ui/icon";
import { Badge } from "@/components/ui/badge";
import { SurfaceCard } from "@/components/ui/surface";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import { PRIMARY_ACTIONS, type PrimarySurface } from "@/lib/primary-actions";
import {
  getStoredUILanguage,
  onUILanguageChange,
  type UILanguage,
} from "@/lib/ui-language";

type GuideTask = {
  title: UITranslationKey;
  detail: UITranslationKey;
  surface: PrimarySurface;
  icon: string;
  recommendedToolVi: string;
  recommendedToolEn: string;
  roleScope: "clinical" | "consumer" | "all";
  keywords: string[];
  steps: [UITranslationKey, UITranslationKey, UITranslationKey];
  action: UITranslationKey;
};

const TASKS: GuideTask[] = [
  {
    title: "guide.tasks.chat.title",
    detail: "guide.tasks.chat.detail",
    surface: "chat",
    icon: "chat",
    recommendedToolVi: "CÔNG CỤ KHUYÊN DÙNG: HỎI CLARA",
    recommendedToolEn: "RECOMMENDED: CLARA ASK",
    roleScope: "all",
    keywords: ["hỏi", "triệu chứng", "dùng thuốc", "chat", "ask", "cơ bản", "an toàn"],
    steps: ["guide.tasks.chat.step1", "guide.tasks.chat.step2", "guide.tasks.chat.step3"],
    action: "guide.tasks.chat.action",
  },
  {
    title: "guide.tasks.thinking.title",
    detail: "guide.tasks.thinking.detail",
    surface: "chat_thinking",
    icon: "psychology",
    recommendedToolVi: "CÔNG CỤ KHUYÊN DÙNG: TƯ DUY Y KHOA",
    recommendedToolEn: "RECOMMENDED: DEEP THINKING",
    roleScope: "clinical",
    keywords: ["tư duy", "sâu", "chi tiết", "phân tích", "thinking", "kỹ hơn"],
    steps: [
      "guide.tasks.thinking.step1",
      "guide.tasks.thinking.step2",
      "guide.tasks.thinking.step3",
    ],
    action: "guide.tasks.thinking.action",
  },
  {
    title: "guide.tasks.cabinet.title",
    detail: "guide.tasks.cabinet.detail",
    surface: "selfmed",
    icon: "medication",
    recommendedToolVi: "CÔNG CỤ KHUYÊN DÙNG: TỦ THUỐC",
    recommendedToolEn: "RECOMMENDED: MED CABINET",
    roleScope: "consumer",
    keywords: ["tủ thuốc", "lưu thuốc", "uống thuốc", "đơn thuốc", "cabinet", "thuốc đang dùng"],
    steps: [
      "guide.tasks.cabinet.step1",
      "guide.tasks.cabinet.step2",
      "guide.tasks.cabinet.step3",
    ],
    action: "guide.tasks.cabinet.action",
  },
  {
    title: "guide.tasks.interactions.title",
    detail: "guide.tasks.interactions.detail",
    surface: "ddi",
    icon: "health_and_safety",
    recommendedToolVi: "CÔNG CỤ KHUYÊN DÙNG: KIỂM TRA TƯƠNG TÁC (DDI)",
    recommendedToolEn: "RECOMMENDED: DDI SAFETY ENGINE",
    roleScope: "all",
    keywords: ["kiểm tra tương tác", "tương tác thuốc", "chống chỉ định", "ddi", "thuốc", "an toàn"],
    steps: [
      "guide.tasks.interactions.step1",
      "guide.tasks.interactions.step2",
      "guide.tasks.interactions.step3",
    ],
    action: "guide.tasks.interactions.action",
  },
  {
    title: "guide.tasks.council.title",
    detail: "guide.tasks.council.detail",
    surface: "council",
    icon: "groups",
    recommendedToolVi: "CÔNG CỤ KHUYÊN DÙNG: HỘI CHẨN (COUNCIL)",
    recommendedToolEn: "RECOMMENDED: COUNCIL AI",
    roleScope: "clinical",
    keywords: ["hội chẩn", "đa chuyên khoa", "ca khó", "council", "bác sĩ", "chuyên khoa"],
    steps: [
      "guide.tasks.council.step1",
      "guide.tasks.council.step2",
      "guide.tasks.council.step3",
    ],
    action: "guide.tasks.council.action",
  },
  {
    title: "guide.tasks.scribe.title",
    detail: "guide.tasks.scribe.detail",
    surface: "scribe",
    icon: "edit_note",
    recommendedToolVi: "CÔNG CỤ KHUYÊN DÙNG: GHI CHÉP (SCRIBE)",
    recommendedToolEn: "RECOMMENDED: CLINICAL SCRIBE",
    roleScope: "clinical",
    keywords: ["ghi âm", "buổi khám", "ghi chép", "scribe", "bệnh án", "soap", "âm thanh", "ghi lại"],
    steps: [
      "guide.tasks.scribe.step1",
      "guide.tasks.scribe.step2",
      "guide.tasks.scribe.step3",
    ],
    action: "guide.tasks.scribe.action",
  },
];

const LABELS = [
  { term: "guide.labels.quick.term", meaning: "guide.labels.quick.meaning" },
  { term: "guide.labels.thinking.term", meaning: "guide.labels.thinking.meaning" },
  { term: "guide.labels.pro.term", meaning: "guide.labels.pro.meaning" },
  { term: "guide.labels.autoSources.term", meaning: "guide.labels.autoSources.meaning" },
  { term: "guide.labels.fullSources.term", meaning: "guide.labels.fullSources.meaning" },
] as const satisfies ReadonlyArray<{
  term: UITranslationKey;
  meaning: UITranslationKey;
}>;

const QUICK_SEARCH_SUGGESTIONS = [
  "Kiểm tra tương tác thuốc",
  "Ghi âm buổi khám",
  "Phân tích ca bệnh khó",
  "Hỏi triệu chứng & dùng thuốc",
  "Tủ thuốc gia đình",
];

export default function GuidePage() {
  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");
  const isEn = uiLanguage === "en";

  // Search & Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState<"all" | "clinical" | "consumer">("all");

  // Expanded accordions state
  const [expandedTasks, setExpandedTasks] = useState<Record<string, boolean>>({
    "guide.tasks.chat.title": true,
    "guide.tasks.interactions.title": true,
    "guide.tasks.council.title": true,
  });

  useEffect(() => {
    setUiLanguage(getStoredUILanguage());
    return onUILanguageChange(setUiLanguage);
  }, []);

  const toggleAccordion = (taskTitle: string) => {
    setExpandedTasks((prev) => ({
      ...prev,
      [taskTitle]: !prev[taskTitle],
    }));
  };

  // Filter tasks by role and search query
  const filteredTasks = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    const tokens = q.split(/\s+/).filter(Boolean);

    return TASKS.filter((task) => {
      // Role filter match
      if (roleFilter !== "all" && task.roleScope !== "all" && task.roleScope !== roleFilter) {
        return false;
      }
      // Query match
      if (!q) return true;

      const searchableCorpus = [
        t(uiLanguage, task.title),
        t(uiLanguage, task.detail),
        t(uiLanguage, task.steps[0]),
        t(uiLanguage, task.steps[1]),
        t(uiLanguage, task.steps[2]),
        isEn ? task.recommendedToolEn : task.recommendedToolVi,
        ...(task.keywords || []),
      ]
        .join(" ")
        .toLowerCase();

      return (
        searchableCorpus.includes(q) ||
        tokens.every((token) => searchableCorpus.includes(token))
      );
    });
  }, [searchQuery, roleFilter, uiLanguage, isEn]);

  return (
    <main className="mx-auto max-w-6xl space-y-8 px-5 py-8 sm:px-6 lg:px-8">
      {/* Page Header & Omni Search Hero (Stitch Reference) */}
      <section className="relative overflow-hidden rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 sm:p-8 shadow-sm space-y-6">
        {/* Ambient Glow */}
        <div className="absolute top-0 right-1/4 w-96 h-96 bg-[var(--brand-500)]/5 rounded-full blur-[100px] pointer-events-none" />

        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <span className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-brand)]">
              {t(uiLanguage, "guide.eyebrow")}
            </span>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[var(--text-primary)]">
              {isEn ? "Help & Guide Center" : "Trung tâm hướng dẫn"}
            </h1>
            <p className="text-xs sm:text-sm text-[var(--text-secondary)] max-w-2xl">
              {isEn
                ? "Learn through experience with fast, task-oriented guides. No manual required."
                : "Học qua trải nghiệm, không cần đọc tài liệu hướng dẫn dài dòng."}
            </p>
          </div>

          {/* Role Filter Toggle */}
          <div className="flex items-center self-start md:self-center rounded-full bg-[var(--surface-muted)] p-1 border border-[color:var(--shell-border)] text-xs">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)] px-2.5">
              {isEn ? "For:" : "Dành cho:"}
            </span>
            <button
              type="button"
              onClick={() => setRoleFilter("all")}
              className={`px-3 py-1 rounded-full font-semibold transition ${
                roleFilter === "all"
                  ? "bg-[var(--surface-panel)] text-[var(--text-primary)] shadow-sm border border-[color:var(--shell-border)]"
                  : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              {isEn ? "All" : "Tất cả"}
            </button>
            <button
              type="button"
              onClick={() => setRoleFilter("clinical")}
              className={`px-3 py-1 rounded-full font-semibold transition ${
                roleFilter === "clinical"
                  ? "bg-[var(--surface-panel)] text-[var(--text-primary)] shadow-sm border border-[color:var(--shell-border)]"
                  : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              {isEn ? "Clinical" : "Lâm sàng"}
            </button>
            <button
              type="button"
              onClick={() => setRoleFilter("consumer")}
              className={`px-3 py-1 rounded-full font-semibold transition ${
                roleFilter === "consumer"
                  ? "bg-[var(--surface-panel)] text-[var(--text-primary)] shadow-sm border border-[color:var(--shell-border)]"
                  : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              {isEn ? "Personal" : "Người dùng"}
            </button>
          </div>
        </div>

        {/* Omni Search Bar */}
        <div className="relative z-10 space-y-2">
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-[var(--text-muted)]">
              <Icon name="search" size="1.25rem" />
            </div>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={
                isEn
                  ? "What would you like to accomplish with CLARA?"
                  : "Bạn muốn làm gì với CLARA? (ví dụ: kiểm tra thuốc, ghi âm, hội chẩn...)"
              }
              className="block w-full pl-11 pr-4 py-3 sm:py-3.5 bg-[var(--surface-muted)] border border-[color:var(--shell-border)] rounded-xl text-sm font-medium text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:ring-2 focus:ring-[var(--brand-500)]/40 focus:border-[var(--brand-500)] outline-none shadow-sm transition"
              data-testid="omni-guide-search-input"
            />
            {searchQuery ? (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-[var(--text-muted)] hover:text-[var(--text-primary)]"
              >
                <Icon name="close" size="1rem" />
              </button>
            ) : null}
          </div>

          {/* Quick Suggestion Pills */}
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            <span className="text-[11px] font-semibold text-[var(--text-muted)] mr-1">
              {isEn ? "Suggestions:" : "Gợi ý:"}
            </span>
            {QUICK_SEARCH_SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => setSearchQuery(suggestion)}
                className="rounded-full bg-[var(--surface-muted)] border border-[color:var(--shell-border)] px-2.5 py-0.5 text-[11px] font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)] transition"
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Bắt đầu nhanh (Quick Start Bento Cards) */}
      <section className="space-y-4">
        <div className="flex items-center gap-2 text-[var(--text-brand)]">
          <Icon name="progress" size="1.25rem" />
          <h2 className="text-base font-bold text-[var(--text-primary)]">
            {isEn ? "Quick Start Actions" : "Bắt đầu nhanh"}
          </h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Quick Start 1: Chat */}
          <Link
            href={PRIMARY_ACTIONS.chat.href}
            className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 hover:border-[color:var(--brand-400)]/60 hover:shadow-md transition group flex flex-col justify-between gap-3 relative overflow-hidden"
          >
            <div className="w-11 h-11 rounded-full bg-[var(--brand-50)] text-[var(--brand-700)] flex items-center justify-center group-hover:scale-110 transition shrink-0">
              <Icon name="chat" size="1.4rem" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-[var(--text-primary)] group-hover:text-[var(--text-brand)] transition">
                {isEn ? "Ask CLARA" : "Hỏi CLARA"}
              </h3>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed mt-1">
                {isEn ? "Instant clinical answers with cited evidence." : "Giải đáp nhanh thắc mắc lâm sàng cơ bản kèm trích dẫn."}
              </p>
            </div>
            <div className="flex items-center justify-end text-[var(--text-brand)] opacity-0 group-hover:opacity-100 transition transform translate-x-2 group-hover:translate-x-0">
              <Icon name="arrow-right" size="1rem" />
            </div>
          </Link>

          {/* Quick Start 2: Council */}
          <Link
            href={PRIMARY_ACTIONS.council.href}
            className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 hover:border-[color:var(--brand-400)]/60 hover:shadow-md transition group flex flex-col justify-between gap-3 relative overflow-hidden"
          >
            <div className="w-11 h-11 rounded-full bg-amber-500/10 text-amber-500 flex items-center justify-center group-hover:scale-110 transition shrink-0">
              <Icon name="contact" size="1.4rem" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-[var(--text-primary)] group-hover:text-amber-500 transition">
                {isEn ? "Council AI" : "Hội chẩn đa chuyên khoa"}
              </h3>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed mt-1">
                {isEn ? "Multi-specialist synthesis for complex clinical cases." : "Phân tích ca bệnh khó với nhiều góc nhìn chuyên khoa."}
              </p>
            </div>
            <div className="flex items-center justify-end text-amber-500 opacity-0 group-hover:opacity-100 transition transform translate-x-2 group-hover:translate-x-0">
              <Icon name="arrow-right" size="1rem" />
            </div>
          </Link>

          {/* Quick Start 3: Scribe */}
          <Link
            href={PRIMARY_ACTIONS.scribe.href}
            className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 hover:border-[color:var(--brand-400)]/60 hover:shadow-md transition group flex flex-col justify-between gap-3 relative overflow-hidden"
          >
            <div className="w-11 h-11 rounded-full bg-indigo-500/10 text-indigo-400 flex items-center justify-center group-hover:scale-110 transition shrink-0">
              <Icon name="mic" size="1.4rem" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-[var(--text-primary)] group-hover:text-indigo-400 transition">
                {isEn ? "Clinical Scribe" : "Ghi chép y khoa (Scribe)"}
              </h3>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed mt-1">
                {isEn ? "Voice-to-SOAP summary from visit audio." : "Tự động tóm tắt ghi chú và bệnh án SOAP từ âm thanh."}
              </p>
            </div>
            <div className="flex items-center justify-end text-indigo-400 opacity-0 group-hover:opacity-100 transition transform translate-x-2 group-hover:translate-x-0">
              <Icon name="arrow-right" size="1rem" />
            </div>
          </Link>

          {/* Quick Start 4: Meds & DDI */}
          <Link
            href={PRIMARY_ACTIONS.ddi.href}
            className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 hover:border-[color:var(--brand-400)]/60 hover:shadow-md transition group flex flex-col justify-between gap-3 relative overflow-hidden"
          >
            <div className="w-11 h-11 rounded-full bg-rose-500/10 text-rose-500 flex items-center justify-center group-hover:scale-110 transition shrink-0">
              <Icon name="medication" size="1.4rem" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-[var(--text-primary)] group-hover:text-rose-500 transition">
                {isEn ? "DDI & Medicine Cabinet" : "Kiểm tra tương tác thuốc"}
              </h3>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed mt-1">
                {isEn ? "Detect contraindications and severe drug-drug interactions." : "Phát hiện nhanh tương tác nguy hiểm và chất chống chỉ định."}
              </p>
            </div>
            <div className="flex items-center justify-end text-rose-500 opacity-0 group-hover:opacity-100 transition transform translate-x-2 group-hover:translate-x-0">
              <Icon name="arrow-right" size="1rem" />
            </div>
          </Link>
        </div>
      </section>

      {/* Task Rows / Searchable Accordion Guides */}
      <section className="space-y-4">
        <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-2">
          <div className="flex items-center gap-2 text-[var(--text-brand)]">
            <Icon name="clinical-notes" size="1.25rem" />
            <h2 className="text-base font-bold text-[var(--text-primary)]">
              {isEn ? "Clinical & Health Tasks (Step-by-Step)" : "Công việc lâm sàng & Hướng dẫn từng bước"}
            </h2>
          </div>
          <span className="text-xs text-[var(--text-muted)]">
            {filteredTasks.length} {isEn ? "guides available" : "hướng dẫn"}
          </span>
        </div>

        {filteredTasks.length > 0 ? (
          <div className="space-y-3">
            {filteredTasks.map((task) => {
              const action = PRIMARY_ACTIONS[task.surface];
              const isExpanded = expandedTasks[task.title] ?? false;

              return (
                <div
                  key={task.title}
                  className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] overflow-hidden shadow-sm transition"
                >
                  {/* Accordion Header Row */}
                  <div
                    onClick={() => toggleAccordion(task.title)}
                    className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 cursor-pointer hover:bg-[var(--surface-hover)] transition select-none"
                  >
                    <div className="flex items-start gap-4 flex-1 min-w-0">
                      <div className="w-10 h-10 rounded-xl bg-[var(--surface-muted)] flex items-center justify-center text-[var(--brand-600)] shrink-0 border border-[color:var(--shell-border)]">
                        <Icon name={resolveIconName(task.icon)} size="1.3rem" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <h3 className="text-sm font-bold text-[var(--text-primary)] flex items-center gap-2">
                          <span>{t(uiLanguage, task.title)}</span>
                        </h3>
                        <p className="text-xs text-[var(--text-secondary)] mt-0.5 leading-relaxed">
                          {t(uiLanguage, task.detail)}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 self-end sm:self-center shrink-0">
                      <span className="rounded-md bg-[var(--brand-50)] text-[var(--brand-700)] border border-[color:var(--brand-200)] px-2.5 py-1 text-[10px] font-bold">
                        {isEn ? task.recommendedToolEn : task.recommendedToolVi}
                      </span>
                      <div className="w-7 h-7 rounded-full bg-[var(--surface-muted)] flex items-center justify-center text-[var(--text-muted)]">
                        <Icon
                          name="chevron-down"
                          size="1rem"
                          className={`transition-transform duration-200 ${isExpanded ? "rotate-180" : ""}`}
                        />
                      </div>
                    </div>
                  </div>

                  {/* Accordion Body */}
                  {isExpanded ? (
                    <div className="px-6 pb-6 pt-2 border-t border-[color:var(--shell-border)]/40 bg-[var(--surface-muted)]/30 space-y-4">
                      <div>
                        <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)] block mb-2">
                          {isEn ? "Execution Steps:" : "Các bước thực hiện:"}
                        </span>
                        <ol className="list-decimal space-y-2 pl-5 text-xs leading-relaxed text-[var(--text-primary)]">
                          {task.steps.map((step) => (
                            <li key={step} className="pl-1">
                              {t(uiLanguage, step)}
                            </li>
                          ))}
                        </ol>
                      </div>

                      <div className="pt-2 flex items-center justify-between border-t border-[color:var(--shell-border)]/40">
                        <span className="text-[11px] text-[var(--text-muted)] italic">
                          {isEn ? `Destination: ${action.href}` : `Điều hướng: ${action.href}`}
                        </span>
                        <Button
                          as="link"
                          href={action.href}
                          variant="primary"
                          size="sm"
                          className="rounded-xl px-4 py-2 font-bold text-xs"
                        >
                          {t(uiLanguage, task.action)}
                        </Button>
                      </div>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-8 text-center space-y-3">
            <Icon name="search" size="2rem" className="text-[var(--text-muted)] mx-auto" />
            <p className="text-sm font-bold text-[var(--text-primary)]">
              {isEn ? "No matching guides found" : "Không tìm thấy hướng dẫn phù hợp"}
            </p>
            <p className="text-xs text-[var(--text-secondary)]">
              {isEn ? "Try adjusting your search terms or filter." : "Thử đổi từ khóa tìm kiếm hoặc bỏ lọc vai trò."}
            </p>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => {
                setSearchQuery("");
                setRoleFilter("all");
              }}
            >
              {isEn ? "Reset Filter" : "Đặt lại bộ lọc"}
            </Button>
          </div>
        )}
      </section>

      {/* Mode Glossary & Labels */}
      <SurfaceCard className="p-6 space-y-4 rounded-[var(--radius-2xl)]">
        <div className="flex items-center gap-2 text-[var(--text-brand)]">
          <Icon name="clinical-notes" size="1.25rem" />
          <h2 className="text-base font-bold text-[var(--text-primary)]">
            {t(uiLanguage, "guide.labels.title")}
          </h2>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {LABELS.map((item) => (
            <div
              key={item.term}
              className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3.5 space-y-1"
            >
              <p className="text-xs font-bold text-[var(--text-primary)]">
                {t(uiLanguage, item.term)}
              </p>
              <p className="text-[11px] leading-5 text-[var(--text-secondary)]">
                {t(uiLanguage, item.meaning)}
              </p>
            </div>
          ))}
        </div>
      </SurfaceCard>
    </main>
  );
}
