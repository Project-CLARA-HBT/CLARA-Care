"use client";

import { useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import Icon, { type IconName } from "@/components/ui/icon";
import { type UserRole } from "@/lib/navigation.config";
import { ClaraOrb } from "./clara-orb";
import {
  useShellMode,
  type ShellDisplayMode,
} from "./shell-mode-provider";

export interface PaletteAction {
  id: string;
  title: string;
  description?: string;
  category: "modes" | "navigation" | "clinical" | "research" | "admin" | "actions";
  icon: IconName;
  roles?: UserRole[];
  shortcut?: string;
  keywords?: string[];
  onSelect?: () => void;
  href?: string;
}

export interface CommandPaletteProps {
  open?: boolean;
  onClose?: () => void;
  role?: UserRole;
  className?: string;
}

const CATEGORY_LABELS: Record<PaletteAction["category"], { vi: string; en: string }> = {
  modes: { vi: "Chế độ hiển thị Shell", en: "Shell Display Modes" },
  navigation: { vi: "Điều hướng chính", en: "Navigation" },
  clinical: { vi: "Công cụ lâm sàng", en: "Clinical Tools" },
  research: { vi: "Tra cứu & Bằng chứng", en: "Research & Evidence" },
  admin: { vi: "Quản trị & Giám sát", en: "Admin & Observability" },
  actions: { vi: "Hành động & Tiện ích", en: "Actions & Utilities" },
};

export function CommandPalette({
  open: propOpen,
  onClose: propOnClose,
  role = "normal",
  className = "",
}: CommandPaletteProps) {
  const router = useRouter();
  const shellContext = useShellMode();

  const isOpen = propOpen ?? shellContext.isCommandPaletteOpen;
  const handleClose = useCallback(() => {
    if (propOnClose) {
      propOnClose();
    } else {
      shellContext.closeCommandPalette();
    }
  }, [propOnClose, shellContext]);

  // Zero-PII search query state: completely local in-memory React state
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);

  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);
  const dialogId = useId();

  // Reset query and selected index on open
  useEffect(() => {
    if (isOpen) {
      previouslyFocusedRef.current = document.activeElement as HTMLElement | null;
      setQuery("");
      setSelectedIndex(0);
      const timer = setTimeout(() => {
        inputRef.current?.focus();
      }, 50);
      return () => clearTimeout(timer);
    } else {
      if (previouslyFocusedRef.current && typeof previouslyFocusedRef.current.focus === "function") {
        previouslyFocusedRef.current.focus();
      }
    }
  }, [isOpen]);

  // Actions catalog with role permissions
  const allActions = useMemo<PaletteAction[]>(() => {
    const actions: PaletteAction[] = [
      // 1. Shell Modes
      {
        id: "mode-explore",
        title: "Chế độ Khám phá (Explore)",
        description: "Giao diện đầy đủ, mở rộng thông tin & điều hướng",
        category: "modes",
        icon: "calendar",
        shortcut: "M 1",
        keywords: ["explore", "kham pha", "default", "standard"],
        onSelect: () => shellContext.setMode("explore"),
      },
      {
        id: "mode-focus",
        title: "Chế độ Tập trung (Focus)",
        description: "Giảm thiểu sao nhãng, tập trung xử lý công việc",
        category: "modes",
        icon: "edit",
        shortcut: "M 2",
        keywords: ["focus", "tap trung", "writing", "composer"],
        onSelect: () => shellContext.setMode("focus"),
      },
      {
        id: "mode-immersive",
        title: "Chế độ Toàn màn hình (Immersive)",
        description: "Mở rộng tối đa không gian làm việc chuyên sâu",
        category: "modes",
        icon: "zoom-in",
        shortcut: "M 3",
        keywords: ["immersive", "toan man hinh", "fullscreen", "canvas"],
        onSelect: () => shellContext.setMode("immersive"),
      },
      {
        id: "mode-read",
        title: "Chế độ Đọc tài liệu (Reading)",
        description: "Tối ưu hóa độ rộng và kiểu chữ cho văn bản y tế",
        category: "modes",
        icon: "clinical-notes",
        shortcut: "M 4",
        keywords: ["read", "doc", "literature", "article"],
        onSelect: () => shellContext.setMode("read"),
      },
      {
        id: "mode-dense",
        title: "Chế độ Dữ liệu cô đọng (Dense)",
        description: "Tăng mật độ hiển thị bảng và dữ liệu lâm sàng",
        category: "modes",
        icon: "scan",
        shortcut: "M 5",
        keywords: ["dense", "co dong", "compact", "matrix", "table"],
        onSelect: () => shellContext.setMode("dense"),
      },

      // 2. Navigation
      {
        id: "nav-home",
        title: "Hôm nay (Home / Today)",
        description: "Bức tranh sức khỏe và công việc hôm nay",
        category: "navigation",
        icon: "calendar",
        shortcut: "G H",
        keywords: ["hom nay", "today", "home", "lich"],
        href: "/home",
      },
      {
        id: "nav-health",
        title: "Sức khỏe (Health Hub)",
        description: "Hồ sơ cá nhân, hành trình LifeMap và thuốc",
        category: "navigation",
        icon: "body",
        shortcut: "G S",
        keywords: ["suc khoe", "health", "phr", "lifemap", "thuoc"],
        href: "/health",
      },
      {
        id: "nav-ask",
        title: "Hỏi CLARA (Ask Assistant)",
        description: "Trợ lý hỏi đáp y tế có kiểm soát an toàn",
        category: "navigation",
        icon: "chat",
        shortcut: "G A",
        keywords: ["hoi", "ask", "chat", "ai", "tu van"],
        href: "/ask",
      },
      {
        id: "nav-care",
        title: "Chăm sóc (Care & Visits)",
        description: "Chuẩn bị buổi khám và theo dõi lịch chăm sóc",
        category: "navigation",
        icon: "clinical-notes",
        shortcut: "G C",
        keywords: ["cham soc", "care", "kham", "visits", "bac si"],
        href: "/care",
      },
      {
        id: "nav-you",
        title: "Cá nhân & Tài khoản (You)",
        description: "Hồ sơ, người thân hỗ trợ và quyền riêng tư",
        category: "navigation",
        icon: "user-card",
        shortcut: "G Y",
        keywords: ["ca nhan", "you", "family", "tai khoan", "privacy"],
        href: "/you",
      },
      {
        id: "nav-medicines",
        title: "Tủ thuốc & An toàn (Medicines)",
        description: "Danh sách thuốc đã xác nhận và kiểm tra tương tác",
        category: "navigation",
        icon: "medication",
        shortcut: "G M",
        keywords: ["thuoc", "medicines", "tu thuoc", "ddi", "tuong tac"],
        href: "/medicines",
      },

      // 3. Clinical Tools (Doctors & Admins)
      {
        id: "clinical-scribe",
        title: "CLARA Scribe (Ghi âm khám bệnh)",
        description: "Ghi chép và tổng hợp bệnh án lâm sàng tự động",
        category: "clinical",
        icon: "mic",
        roles: ["doctor", "admin"],
        shortcut: "C S",
        keywords: ["scribe", "ghi am", "benh an", "audio", "transcript"],
        href: "/scribe",
      },
      {
        id: "clinical-council",
        title: "CLARA Council (Hội chẩn đa chuyên khoa)",
        description: "Tham vấn đa chuyên khoa và đánh giá bằng chứng",
        category: "clinical",
        icon: "contact",
        roles: ["doctor", "admin"],
        shortcut: "C C",
        keywords: ["council", "hoi chan", "chuyen khoa", "consilium"],
        href: "/council",
      },
      {
        id: "clinical-dashboard",
        title: "Bàn làm việc Bác sĩ (Clinician Command Center)",
        description: "Quản lý ca khám, tóm tắt và tiếp nhận bệnh nhân",
        category: "clinical",
        icon: "calendar",
        roles: ["doctor", "admin"],
        shortcut: "C D",
        keywords: ["dashboard", "tong quan", "lam sang", "command center"],
        href: "/dashboard",
      },

      // 4. Research & Evidence (Researchers, Doctors, Admins)
      {
        id: "research-hub",
        title: "Tra cứu Y khoa (Living Evidence)",
        description: "Tra cứu y văn, bằng chứng lâm sàng và ma trận tổng hợp",
        category: "research",
        icon: "search",
        roles: ["researcher", "doctor", "admin"],
        shortcut: "R H",
        keywords: ["research", "tra cuu", "evidence", "y van", "literature"],
        href: "/evidence",
      },

      // 5. Admin & Observability (Admins)
      {
        id: "admin-tower",
        title: "Tháp Điều phối Hệ thống (Control Tower)",
        description: "Cấu hình mô hình, RAG và tham số điều phối an toàn",
        category: "admin",
        icon: "settings",
        roles: ["admin"],
        shortcut: "A T",
        keywords: ["control tower", "dieu phoi", "admin", "config"],
        href: "/admin",
      },
      {
        id: "admin-observability",
        title: "Giám sát Vận hành (Observability)",
        description: "Theo dõi độ trễ, lưu lượng và cảnh báo hệ thống",
        category: "admin",
        icon: "progress",
        roles: ["admin"],
        shortcut: "A O",
        keywords: ["observability", "giam sat", "metrics", "latency"],
        href: "/admin/observability",
      },
      {
        id: "admin-flow",
        title: "Trình gỡ lỗi luồng RAG (Flow Debugger)",
        description: "Kiểm tra từng chặng truy vấn và trích xuất tài liệu",
        category: "admin",
        icon: "scan",
        roles: ["admin"],
        shortcut: "A F",
        keywords: ["flow", "luong", "debugger", "rag", "retrieval"],
        href: "/admin/flow-debugger",
      },
      {
        id: "admin-dsar",
        title: "Kiểm toán Quyền Dữ liệu (DSAR & Audit)",
        description: "Quản lý yêu cầu trích xuất và xóa dữ liệu người dùng",
        category: "admin",
        icon: "clinical-notes",
        roles: ["admin"],
        shortcut: "A D",
        keywords: ["dsar", "audit", "kiem toan", "privacy", "gdpr"],
        href: "/admin/dsar",
      },

      // 6. Actions & Utilities
      {
        id: "action-help",
        title: "Hướng dẫn sử dụng & Trợ giúp",
        description: "Trung tâm tài liệu và câu hỏi thường gặp",
        category: "actions",
        icon: "help",
        shortcut: "?",
        keywords: ["huong dan", "help", "tro giup", "faq", "guide"],
        href: "/huong-dan",
      },
    ];

    // Filter by role
    return actions.filter((action) => {
      if (!action.roles) return true;
      return action.roles.includes(role);
    });
  }, [role, shellContext]);

  // Filter actions by query
  const filteredActions = useMemo(() => {
    const trimmed = query.trim().toLowerCase();
    if (!trimmed) return allActions;

    return allActions.filter((action) => {
      const matchTitle = action.title.toLowerCase().includes(trimmed);
      const matchDesc = action.description?.toLowerCase().includes(trimmed);
      const matchShortcut = action.shortcut?.toLowerCase().includes(trimmed);
      const matchKeywords = action.keywords?.some((kw) => kw.toLowerCase().includes(trimmed));

      return matchTitle || matchDesc || matchShortcut || matchKeywords;
    });
  }, [allActions, query]);

  // Group filtered actions by category
  const groupedActions = useMemo(() => {
    const groups: Array<{
      category: PaletteAction["category"];
      labelVi: string;
      items: PaletteAction[];
    }> = [];

    const order: PaletteAction["category"][] = [
      "modes",
      "navigation",
      "clinical",
      "research",
      "admin",
      "actions",
    ];

    for (const cat of order) {
      const items = filteredActions.filter((a) => a.category === cat);
      if (items.length > 0) {
        groups.push({
          category: cat,
          labelVi: CATEGORY_LABELS[cat].vi,
          items,
        });
      }
    }

    return groups;
  }, [filteredActions]);

  // Flat list of visible items for keyboard navigation
  const flatItems = useMemo(
    () => groupedActions.flatMap((g) => g.items),
    [groupedActions],
  );

  // Execute selected action
  const executeAction = useCallback(
    (action: PaletteAction) => {
      handleClose();
      if (action.onSelect) {
        action.onSelect();
      } else if (action.href) {
        router.push(action.href);
      }
    },
    [handleClose, router],
  );

  // Keyboard navigation handler inside input
  const handleKeyDown = useCallback(
    (event: ReactKeyboardEvent<HTMLInputElement>) => {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setSelectedIndex((prev) => (flatItems.length === 0 ? 0 : (prev + 1) % flatItems.length));
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        setSelectedIndex((prev) =>
          flatItems.length === 0 ? 0 : (prev - 1 + flatItems.length) % flatItems.length,
        );
      } else if (event.key === "Enter") {
        event.preventDefault();
        const selected = flatItems[selectedIndex];
        if (selected) {
          executeAction(selected);
        }
      } else if (event.key === "Escape") {
        event.preventDefault();
        handleClose();
      }
    },
    [flatItems, selectedIndex, executeAction, handleClose],
  );

  // Ensure selected index stays in bounds
  useEffect(() => {
    if (selectedIndex >= flatItems.length) {
      setSelectedIndex(0);
    }
  }, [flatItems.length, selectedIndex]);

  // Scroll active item into view
  useEffect(() => {
    if (listRef.current) {
      const activeEl = listRef.current.querySelector<HTMLElement>('[data-selected="true"]');
      if (activeEl && typeof activeEl.scrollIntoView === "function") {
        activeEl.scrollIntoView({ block: "nearest" });
      }
    }
  }, [selectedIndex]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center p-4 pt-[10vh] sm:p-6 sm:pt-[12vh]"
      role="dialog"
      aria-modal="true"
      aria-labelledby={`${dialogId}-title`}
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-[rgba(10,14,19,0.75)] backdrop-blur-md transition-opacity"
        onClick={handleClose}
        aria-hidden="true"
      />

      {/* Palette Card */}
      <div
        className={[
          "relative z-10 w-full max-w-2xl overflow-hidden rounded-[var(--radius-2xl)]",
          "border border-[color:var(--shell-border)] bg-[var(--surface-header)]/96 backdrop-blur-2xl",
          "shadow-2xl flex flex-col max-h-[75vh]",
          className,
        ].join(" ")}
      >
        <span id={`${dialogId}-title`} className="sr-only">
          Bảng lệnh CLARA (Command Palette)
        </span>

        {/* Search Header */}
        <div className="flex items-center gap-3 border-b border-[color:var(--shell-border)] px-4 py-3.5">
          <ClaraOrb size="sm" state={query ? "processing" : "idle"} interactive={false} />

          <input
            ref={inputRef}
            type="text"
            role="combobox"
            aria-expanded="true"
            aria-controls={`${dialogId}-results`}
            aria-autocomplete="list"
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
            data-pii-safe="true"
            placeholder="Tìm kiếm tính năng, tài liệu, hành động... (Nhập 'explore', 'scribe', 'thuốc'...)"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            onKeyDown={handleKeyDown}
            className="flex-1 bg-transparent text-sm font-medium text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none"
          />

          {query && (
            <button
              type="button"
              onClick={() => setQuery("")}
              aria-label="Xóa nội dung tìm kiếm"
              className="text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] transition"
            >
              Xóa
            </button>
          )}

          <kbd className="hidden sm:inline-block rounded border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--text-muted)]">
            ESC
          </kbd>
        </div>

        {/* Results List */}
        <div
          ref={listRef}
          id={`${dialogId}-results`}
          role="listbox"
          className="flex-1 overflow-y-auto p-2 clara-scrollbar space-y-3"
        >
          {flatItems.length === 0 ? (
            <div className="py-12 text-center">
              <Icon name="search" size={24} className="mx-auto text-[var(--text-muted)] opacity-50 mb-2" />
              <p className="text-sm font-medium text-[var(--text-primary)]">
                Không tìm thấy lệnh hoặc tính năng phù hợp
              </p>
              <p className="mt-1 text-xs text-[var(--text-muted)]">
                Thử tìm theo từ khóa như: &quot;khám phá&quot;, &quot;scribe&quot;, &quot;hồ sơ&quot;, &quot;thuốc&quot;, &quot;chế độ&quot;...
              </p>
            </div>
          ) : (
            groupedActions.map((group) => {
              return (
                <div key={group.category} role="group" aria-label={group.labelVi}>
                  <div className="px-3 py-1 text-[10px] font-bold uppercase tracking-[0.12em] text-[var(--text-muted)]">
                    {group.labelVi} ({group.items.length})
                  </div>

                  <div className="mt-1 space-y-0.5">
                    {group.items.map((action) => {
                      const itemIndex = flatItems.findIndex((a) => a.id === action.id);
                      const isSelected = itemIndex === selectedIndex;

                      return (
                        <div
                          key={action.id}
                          role="option"
                          id={`${dialogId}-opt-${action.id}`}
                          aria-selected={isSelected}
                          data-selected={isSelected}
                          onClick={() => executeAction(action)}
                          onMouseEnter={() => setSelectedIndex(itemIndex)}
                          className={[
                            "flex items-center justify-between gap-3 rounded-xl px-3 py-2.5 cursor-pointer transition",
                            isSelected
                              ? "bg-[var(--surface-active)] text-[var(--text-primary)] ring-1 ring-[var(--brand-500)]/40"
                              : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]",
                          ].join(" ")}
                        >
                          <div className="flex min-w-0 items-center gap-3">
                            <span
                              className={[
                                "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border",
                                isSelected
                                  ? "border-[color:var(--brand-500)]/50 bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                                  : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)]",
                              ].join(" ")}
                            >
                              <Icon name={action.icon} size={16} aria-hidden="true" />
                            </span>

                            <div className="min-w-0">
                              <p className="truncate text-xs font-semibold text-[var(--text-primary)]">
                                {action.title}
                              </p>
                              {action.description && (
                                <p className="truncate text-[11px] text-[var(--text-muted)]">
                                  {action.description}
                                </p>
                              )}
                            </div>
                          </div>

                          {action.shortcut && (
                            <kbd
                              className={[
                                "shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-semibold tracking-wider",
                                isSelected
                                  ? "border-[color:var(--brand-500)]/40 bg-[var(--surface-panel)] text-[var(--text-brand)]"
                                  : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-muted)]",
                              ].join(" ")}
                            >
                              {action.shortcut}
                            </kbd>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer Navigation Hints */}
        <div className="flex items-center justify-between border-t border-[color:var(--shell-border)] px-4 py-2.5 text-[11px] text-[var(--text-muted)] bg-[var(--surface-panel)]/50">
          <div className="flex items-center gap-4">
            <span className="inline-flex items-center gap-1">
              <kbd className="rounded border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-1 py-0.2 text-[10px]">
                ↑
              </kbd>
              <kbd className="rounded border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-1 py-0.2 text-[10px]">
                ↓
              </kbd>
              <span>Di chuyển</span>
            </span>
            <span className="inline-flex items-center gap-1">
              <kbd className="rounded border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-1 py-0.2 text-[10px]">
                ↵
              </kbd>
              <span>Chọn</span>
            </span>
          </div>

          <span className="text-[10px] text-[var(--text-muted)]">
            Không lưu vết dữ liệu cá nhân (Zero PII)
          </span>
        </div>
      </div>
    </div>
  );
}

export default CommandPalette;
