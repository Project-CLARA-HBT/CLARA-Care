"use client";

import { useCallback, useContext, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { SessionContext } from "@/components/shell/session-boundary";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Icon, { type IconName } from "@/components/ui/icon";
import { SurfaceCard } from "@/components/ui/surface";
import { getRole, setAuthoritativeServerRole, type UserRole } from "@/lib/auth-store";
import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

type WorkspaceCardId = "admin" | "clinical" | "research" | "personal";

interface WorkspaceCapability {
  id: string;
  label: string;
  descVi: string;
  descEn: string;
  href: string;
  icon: IconName;
  highlight?: boolean;
}

interface WorkspaceCardConfig {
  id: WorkspaceCardId;
  role: UserRole;
  previewMode: "clinical" | "research" | "personal" | null;
  titleVi: string;
  titleEn: string;
  badgeVi: string;
  badgeEn: string;
  badgeTone: "brand" | "ok" | "warn" | "neutral" | "danger";
  personaTitleVi: string;
  personaTitleEn: string;
  personaVi: string;
  personaEn: string;
  descriptionVi: string;
  descriptionEn: string;
  homePath: string;
  icon: IconName;
  accentColor: string;
  capabilities: WorkspaceCapability[];
}

const WORKSPACE_CARDS: WorkspaceCardConfig[] = [
  {
    id: "admin",
    role: "admin",
    previewMode: null,
    titleVi: "Quản trị Toàn diện (Admin Command)",
    titleEn: "Administration Command",
    badgeVi: "Vận hành & An ninh",
    badgeEn: "Operations & Security",
    badgeTone: "brand",
    personaTitleVi: "Đối tượng phù hợp:",
    personaTitleEn: "Target Persona:",
    personaVi: "Quản trị viên hệ thống, Trưởng khoa Y tế, Cán bộ tuân thủ & An ninh",
    personaEn: "System Administrators, Clinical Leads, Operations & Compliance Officers",
    descriptionVi:
      "Bàn điều khiển trung tâm tối cao để quản trị hạ tầng AI, phân quyền người dùng, giám sát luồng quyết định y tế và tuân thủ an toàn FIDES.",
    descriptionEn:
      "Central command cockpit to govern platform infrastructure, manage users & RBAC, inspect real-time AI decision flows, and enforce FIDES safety.",
    homePath: "/admin/overview",
    icon: "settings",
    accentColor: "border-indigo-500/40 bg-indigo-500/5 hover:border-indigo-500/80",
    capabilities: [
      {
        id: "overview",
        label: "Overview",
        descVi: "Báo cáo tổng quan vận hành & an toàn",
        descEn: "Operational health & safety overview",
        href: "/admin/overview",
        icon: "calendar",
      },
      {
        id: "system-health",
        label: "System health",
        descVi: "Giám sát sức khỏe hạ tầng, API, ML & Redis",
        descEn: "Infrastructure, API, ML & Redis telemetry",
        href: "/admin/system",
        icon: "settings",
      },
      {
        id: "user-admin",
        label: "User admin",
        descVi: "Quản lý danh tính, kích hoạt tài khoản & phân quyền",
        descEn: "User identity, access control & role assignment",
        href: "/admin/users",
        icon: "user-card",
      },
      {
        id: "security-audit",
        label: "Security audit",
        descVi: "Nhật ký kiểm toán bảo mật & truy vết hệ thống",
        descEn: "Security audit ledger & access tracing",
        href: "/admin/audit-log",
        icon: "clinical-notes",
      },
      {
        id: "flow-debugger",
        label: "Flow debugger",
        descVi: "Gỡ lỗi và kiểm tra trực quan luồng trả lời AI",
        descEn: "Visual inspection & debugging of AI answer flows",
        href: "/admin/answer-flow",
        icon: "progress",
      },
      {
        id: "ingestion-monitor",
        label: "Ingestion monitor",
        descVi: "Giám sát nạp tri thức RAG & đồng bộ tài liệu",
        descEn: "RAG knowledge ingestion & pipeline monitoring",
        href: "/admin/rag-ingestion",
        icon: "upload",
      },
    ],
  },
  {
    id: "clinical",
    role: "doctor",
    previewMode: "clinical",
    titleVi: "Bác sĩ Lâm sàng (Clinical Instrument)",
    titleEn: "Clinical Instrument",
    badgeVi: "Bác sĩ & Hội đồng",
    badgeEn: "Clinicians & Specialists",
    badgeTone: "ok",
    personaTitleVi: "Đối tượng phù hợp:",
    personaTitleEn: "Target Persona:",
    personaVi: "Bác sĩ lâm sàng, Chuyên gia nội/ngoại khoa, Bác sĩ hội chẩn",
    personaEn: "Medical Doctors, Clinicians, Multidisciplinary Specialists",
    descriptionVi:
      "Không gian công cụ lâm sàng chuyên sâu hỗ trợ hội chẩn đa tác tử, ghi chép bối cảnh khám tự động và phân tầng nguy cơ bệnh nhân.",
    descriptionEn:
      "Specialized clinical instrument suite featuring multi-agent council deliberation, ambient audio medical documentation, and patient queue triage.",
    homePath: "/clinical/overview",
    icon: "clinical-notes",
    accentColor: "border-emerald-500/40 bg-emerald-500/5 hover:border-emerald-500/80",
    capabilities: [
      {
        id: "clinical-overview",
        label: "Clinical Overview launchpad",
        descVi: "Bàn điều khiển lâm sàng tổng quan & ca bệnh",
        descEn: "Clinical command center & active case launchpad",
        href: "/clinical/overview",
        icon: "clinical-notes",
      },
      {
        id: "council",
        label: "Council multi-agent deliberation",
        descVi: "Hội chẩn đa chuyên khoa với các tác tử AI",
        descEn: "Multi-agent consensus & conflict resolution",
        href: "/council",
        icon: "contact",
      },
      {
        id: "scribe",
        label: "Scribe ambient transcription",
        descVi: "Ghi chép khám bệnh và trích xuất bệnh án SOAP",
        descEn: "Ambient consultation audio recording & SOAP note",
        href: "/scribe",
        icon: "mic",
      },
      {
        id: "patient-queue",
        label: "Patient queue",
        descVi: "Hàng đợi bệnh nhân & phân tầng nguy cơ ưu tiên",
        descEn: "Real-time patient queue & triage stratification",
        href: "/clinical/patients",
        icon: "user-card",
      },
    ],
  },
  {
    id: "research",
    role: "researcher",
    previewMode: "research",
    titleVi: "Nhà nghiên cứu Y sinh (Living Evidence)",
    titleEn: "Living Evidence",
    badgeVi: "Bằng chứng & Nghiên cứu",
    badgeEn: "Evidence & Research",
    badgeTone: "brand",
    personaTitleVi: "Đối tượng phù hợp:",
    personaTitleEn: "Target Persona:",
    personaVi: "Nhà nghiên cứu y sinh, Dược sĩ lâm sàng, Học giả y khoa",
    personaEn: "Biomedical Researchers, Pharmacologists, Medical Scholars",
    descriptionVi:
      "Không gian tổng hợp bằng chứng y văn sống, đối chiếu thử nghiệm lâm sàng, quản lý nguồn dữ liệu uy tín và AI nghiên cứu chuyên sâu.",
    descriptionEn:
      "Living evidence synthesis workspace, literature search across PubMed & Cochrane, verified source catalog, and evidence-grounded research chat.",
    homePath: "/evidence",
    icon: "search",
    accentColor: "border-sky-500/40 bg-sky-500/5 hover:border-sky-500/80",
    capabilities: [
      {
        id: "evidence-synthesis",
        label: "Evidence synthesis",
        descVi: "Tổng hợp bằng chứng sống & phân cấp GRADE",
        descEn: "Living evidence trackers & guideline synthesis",
        href: "/evidence",
        icon: "progress",
      },
      {
        id: "literature-search",
        label: "Literature search",
        descVi: "Tra cứu y văn PubMed, Cochrane & Bộ Y tế",
        descEn: "Multi-database literature search & deep dive",
        href: "/chat",
        icon: "search",
      },
      {
        id: "source-hub",
        label: "Source hub catalog",
        descVi: "Danh mục nguồn tri thức y khoa đã xác thực",
        descEn: "Curated biomedical evidence source registry",
        href: "/research/source-hub",
        icon: "folder",
      },
      {
        id: "research-chat",
        label: "AI research chat",
        descVi: "Trợ lý AI chuyên sâu đối thoại khoa học có trích dẫn",
        descEn: "Evidence-backed conversational research agent",
        href: "/chat",
        icon: "chat",
      },
    ],
  },
  {
    id: "personal",
    role: "normal",
    previewMode: "personal",
    titleVi: "Người dùng Cá nhân (Personal Companion)",
    titleEn: "Personal Companion",
    badgeVi: "Cá nhân & Gia đình",
    badgeEn: "Personal & Family",
    badgeTone: "warn",
    personaTitleVi: "Đối tượng phù hợp:",
    personaTitleEn: "Target Persona:",
    personaVi: "Người bệnh, Người chăm sóc gia đình, Cá nhân theo dõi sức khỏe",
    personaEn: "Patients, Family Caregivers, Health-conscious Individuals",
    descriptionVi:
      "Trợ lý đồng hành sức khỏe cá nhân và gia đình, hướng dẫn các hành động hôm nay, theo dõi hành trình bệnh và quản lý tủ thuốc an toàn.",
    descriptionEn:
      "Personal and family health companion with next-action daily plan, longitudinal care journeys, medication cabinet, and family sharing.",
    homePath: "/today",
    icon: "user-card",
    accentColor: "border-amber-500/40 bg-amber-500/5 hover:border-amber-500/80",
    capabilities: [
      {
        id: "today-canvas",
        label: "Next-action Today canvas",
        descVi: "Bảng việc hôm nay & các hành động sức khỏe ưu tiên",
        descEn: "Daily care tasks, reminders & next best actions",
        href: "/today",
        icon: "check",
      },
      {
        id: "lifemap",
        label: "LifeMap care journeys",
        descVi: "Bản đồ hành trình chăm sóc & lộ trình điều trị",
        descEn: "Longitudinal health journeys & care milestones",
        href: "/lifemap",
        icon: "progress",
      },
      {
        id: "medicines-cabinet",
        label: "Medicines safety cabinet",
        descVi: "Tủ thuốc gia đình, quét đơn thuốc & cảnh báo tương tác",
        descEn: "Medicine cabinet, prescription OCR & DDI screening",
        href: "/medicines",
        icon: "medication",
      },
      {
        id: "family-sharing",
        label: "Family sharing",
        descVi: "Vòng tròn gia đình & chia sẻ hồ sơ có kiểm soát",
        descEn: "Family health circle & granular care sharing",
        href: "/family",
        icon: "contact",
      },
    ],
  },
];

export default function RoleSelectPage() {
  const language = useUILanguage();
  const router = useRouter();
  const session = useContext(SessionContext);

  const [activeRole, setActiveRole] = useState<UserRole>(() => {
    return session?.role ?? getRole();
  });
  const [activePreview, setActivePreview] = useState<string | null>(() => {
    return session?.adminPreviewMode ?? null;
  });
  const [filterQuery, setFilterQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<WorkspaceCardId | "all">("all");
  const [lastActionStatus, setLastActionStatus] = useState<string | null>(null);

  // Sync state if session updates
  useEffect(() => {
    if (session?.role) {
      setActiveRole(session.role);
    }
    if (session?.adminPreviewMode !== undefined) {
      setActivePreview(session.adminPreviewMode);
    }
  }, [session?.role, session?.adminPreviewMode]);

  // Determine current active workspace ID
  const activeWorkspaceId = useMemo<WorkspaceCardId>(() => {
    if (activeRole === "admin") {
      if (activePreview === "clinical") return "clinical";
      if (activePreview === "research") return "research";
      if (activePreview === "personal") return "personal";
      return "admin";
    }
    if (activeRole === "doctor") return "clinical";
    if (activeRole === "researcher") return "research";
    return "personal";
  }, [activeRole, activePreview]);

  // Persistence handler
  const persistSelection = useCallback(
    (targetRole: UserRole, targetPreview: "clinical" | "research" | "personal" | null, workspaceId: WorkspaceCardId) => {
      setAuthoritativeServerRole(targetRole);
      try {
        window.localStorage.setItem(`clara_active_workspace:${targetRole}`, workspaceId);
        window.localStorage.setItem("clara_active_workspace", workspaceId);
      } catch {
        // Safe fallback for restricted storage environments
      }

      if (session) {
        session.setRole(targetRole);
        if (session.role === "admin") {
          session.setAdminPreviewMode(targetPreview);
        }
      }

      setActiveRole(targetRole);
      setActivePreview(targetPreview);
    },
    [session],
  );

  // 1-Click Role / Preview Switch
  const handleSelectWorkspace = useCallback(
    (card: WorkspaceCardConfig) => {
      persistSelection(card.role, card.previewMode, card.id);
      const message =
        language === "vi"
          ? `Đã kích hoạt chế độ xem: ${card.titleVi}`
          : `Activated workspace view: ${card.titleEn}`;
      setLastActionStatus(message);
    },
    [persistSelection, language],
  );

  // Instant Launch to Target Workspace
  const handleInstantLaunch = useCallback(
    (card: WorkspaceCardConfig) => {
      persistSelection(card.role, card.previewMode, card.id);
      router.push(card.homePath);
    },
    [persistSelection, router],
  );

  // Quick capability jump
  const handleCapabilityJump = useCallback(
    (card: WorkspaceCardConfig, capability: WorkspaceCapability) => {
      persistSelection(card.role, card.previewMode, card.id);
      router.push(capability.href);
    },
    [persistSelection, router],
  );

  // Filtered Cards
  const visibleCards = useMemo(() => {
    return WORKSPACE_CARDS.filter((card) => {
      if (selectedCategory !== "all" && card.id !== selectedCategory) {
        return false;
      }
      if (!filterQuery.trim()) return true;

      const q = filterQuery.toLowerCase().trim();
      const matchTitle =
        card.titleVi.toLowerCase().includes(q) || card.titleEn.toLowerCase().includes(q);
      const matchDesc =
        card.descriptionVi.toLowerCase().includes(q) ||
        card.descriptionEn.toLowerCase().includes(q);
      const matchPersona =
        card.personaVi.toLowerCase().includes(q) || card.personaEn.toLowerCase().includes(q);
      const matchCapability = card.capabilities.some(
        (cap) =>
          cap.label.toLowerCase().includes(q) ||
          cap.descVi.toLowerCase().includes(q) ||
          cap.descEn.toLowerCase().includes(q),
      );

      return matchTitle || matchDesc || matchPersona || matchCapability;
    });
  }, [filterQuery, selectedCategory]);

  return (
    <div className="relative min-h-[100dvh] w-full bg-[var(--bg-canvas)] py-8 px-4 sm:px-6 lg:px-12">
      {/* Background ambient lighting */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
      >
        <div className="absolute -top-40 left-1/2 h-96 w-96 -translate-x-1/2 rounded-full bg-[var(--brand-500)]/10 blur-3xl" />
        <div className="absolute top-1/3 right-10 h-80 w-80 rounded-full bg-emerald-500/10 blur-3xl" />
        <div className="absolute bottom-20 left-10 h-80 w-80 rounded-full bg-amber-500/10 blur-3xl" />
      </div>

      <div className="mx-auto max-w-7xl space-y-8">
        {/* Header Hero Section */}
        <header className="text-center sm:text-left">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-2 rounded-full border border-[color:var(--brand-500)]/30 bg-[var(--surface-brand-soft)] px-3 py-1 text-xs font-semibold text-[var(--text-brand)]">
                <Icon name="settings" size="0.95rem" />
                <span>
                  {language === "vi"
                    ? "Trung tâm Điều phối Không gian & Vai trò"
                    : "Role & Workspace Selection Canvas"}
                </span>
              </div>
              <h1 className="text-2xl font-extrabold tracking-tight text-[var(--text-primary)] sm:text-3xl lg:text-4xl">
                {language === "vi"
                  ? "Chọn Không gian Làm việc & Vai trò"
                  : "Select Your Workspace & Role"}
              </h1>
              <p className="max-w-3xl text-sm leading-relaxed text-[var(--text-secondary)] sm:text-base">
                {language === "vi"
                  ? "CLARA cung cấp 4 bàn làm việc chuyên biệt theo từng đối tượng: Quản trị, Lâm sàng, Nghiên cứu y sinh và Chăm sóc cá nhân. Bạn có thể kích hoạt xem trước hoặc chuyển đổi tức thì với một chạm."
                  : "CLARA features 4 distinct purpose-built workspaces tailored for Admin Command, Clinical Practice, Biomedical Research, and Personal Companion. Switch active preview or launch instantly with 1 click."}
              </p>
            </div>

            {/* Quick Actions & Redirection Anchor */}
            <div className="flex shrink-0 flex-wrap items-center justify-center gap-3 sm:justify-end">
              <Link
                href="/huong-dan"
                className="inline-flex min-h-[40px] items-center gap-1.5 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 text-xs font-semibold text-[var(--text-primary)] shadow-sm transition hover:bg-[var(--surface-muted)]"
                title={t(language, "roleRedirect.title")}
              >
                <Icon name="help" size="1rem" />
                <span>{language === "vi" ? "Hướng dẫn sử dụng" : "User Guide"}</span>
              </Link>

              <Link
                href="/home"
                className="inline-flex min-h-[40px] items-center gap-1.5 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 text-xs font-semibold text-[var(--text-primary)] shadow-sm transition hover:bg-[var(--surface-muted)]"
              >
                <Icon name="arrow-right" size="1rem" />
                <span>{language === "vi" ? "Về trang chủ" : "Go to Home"}</span>
              </Link>
            </div>
          </div>

          {/* Active Role & Live Feedback Bar */}
          <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)]/80 p-3.5 backdrop-blur-md">
            <div className="flex flex-wrap items-center gap-2.5 text-xs">
              <span className="font-medium text-[var(--text-secondary)]">
                {language === "vi" ? "Trạng thái hiện tại:" : "Current Status:"}
              </span>
              <Badge tone="brand" className="font-mono font-bold uppercase">
                {activeRole}
              </Badge>
              {activePreview && (
                <Badge tone="warn" className="font-semibold">
                  {language === "vi"
                    ? `Xem trước: ${activePreview}`
                    : `Preview: ${activePreview}`}
                </Badge>
              )}
              <span className="hidden text-[var(--text-muted)] sm:inline">|</span>
              <span className="text-[var(--text-secondary)]">
                {language === "vi"
                  ? `Không gian đang chọn: `
                  : `Active Workspace: `}
                <strong className="text-[var(--text-primary)]">
                  {WORKSPACE_CARDS.find((c) => c.id === activeWorkspaceId)?.titleVi}
                </strong>
              </span>
            </div>

            {lastActionStatus && (
              <div
                role="status"
                className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--status-ok-text)] motion-safe:animate-fade-in"
              >
                <Icon name="check" size="0.95rem" />
                <span>{lastActionStatus}</span>
              </div>
            )}
          </div>
        </header>

        {/* Filter & Search Bar */}
        <section aria-label="Tìm kiếm và lọc không gian" className="space-y-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            {/* Category Filter Tabs */}
            <div className="flex flex-wrap items-center gap-1.5" role="tablist" aria-label="Lọc theo phân hệ">
              <button
                key="all"
                type="button"
                data-testid="filter-tab-all"
                onClick={() => setSelectedCategory("all")}
                className={`min-h-[36px] rounded-[var(--radius-lg)] px-3 py-1.5 text-xs font-semibold transition ${
                  selectedCategory === "all"
                    ? "bg-[var(--brand-600)] text-[var(--button-primary-text)] shadow-sm"
                    : "border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
                }`}
              >
                {language === "vi" ? "Tất cả (4)" : "All (4)"}
              </button>

              {WORKSPACE_CARDS.map((card) => {
                const isSelected = selectedCategory === card.id;
                return (
                  <button
                    key={card.id}
                    type="button"
                    data-testid={`filter-tab-${card.id}`}
                    onClick={() => setSelectedCategory(card.id)}
                    className={`inline-flex min-h-[36px] items-center gap-1.5 rounded-[var(--radius-lg)] px-3 py-1.5 text-xs font-semibold transition ${
                      isSelected
                        ? "bg-[var(--brand-600)] text-[var(--button-primary-text)] shadow-sm"
                        : "border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
                    }`}
                  >
                    <Icon name={card.icon} size="0.9rem" />
                    <span>{language === "vi" ? card.badgeVi : card.badgeEn}</span>
                  </button>
                );
              })}
            </div>

            {/* Omni-search input */}
            <div className="relative w-full sm:w-72 lg:w-80">
              <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-[var(--text-muted)]">
                <Icon name="search" size="1rem" />
              </span>
              <input
                type="search"
                value={filterQuery}
                onChange={(e) => setFilterQuery(e.target.value)}
                placeholder={
                  language === "vi"
                    ? "Tìm tính năng, vai trò (vd: Scribe, DDI, Audit)..."
                    : "Filter capabilities (e.g. Scribe, Audit, DDI)..."
                }
                className="min-h-[38px] w-full rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] py-1.5 pl-9 pr-3 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus-ring"
              />
              {filterQuery && (
                <button
                  type="button"
                  onClick={() => setFilterQuery("")}
                  className="absolute inset-y-0 right-2.5 flex items-center text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                  aria-label="Xóa bộ lọc"
                >
                  <Icon name="close" size="0.9rem" />
                </button>
              )}
            </div>
          </div>
        </section>

        {/* 4 Workspace Cards Grid */}
        <main
          id="workspace-cards-grid"
          className="grid grid-cols-1 gap-6 lg:grid-cols-2"
          role="region"
          aria-label="Danh sách Không gian Làm việc"
        >
          {visibleCards.map((card) => {
            const isActive = activeWorkspaceId === card.id;

            return (
              <SurfaceCard
                key={card.id}
                data-testid={`workspace-card-${card.id}`}
                className={`relative flex flex-col justify-between overflow-hidden rounded-[var(--radius-2xl)] border-2 p-6 transition-all duration-200 sm:p-7 ${
                  isActive
                    ? "border-[color:var(--brand-500)] shadow-lg ring-2 ring-[var(--brand-500)]/20"
                    : "border-[color:var(--shell-border)] hover:border-[color:var(--shell-border-strong)] hover:shadow-md"
                } bg-[var(--surface-panel)]`}
              >
                {/* Active Indicator Ribbon */}
                {isActive && (
                  <div className="absolute top-0 right-0 rounded-bl-[var(--radius-lg)] bg-[var(--brand-600)] px-3 py-1 text-[11px] font-bold tracking-wider text-[var(--button-primary-text)] uppercase shadow-sm">
                    {language === "vi" ? "Đang Hoạt động" : "Active"}
                  </div>
                )}

                <div className="space-y-5">
                  {/* Card Header */}
                  <div className="flex items-start gap-4">
                    <div
                      className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-[var(--radius-xl)] border border-current p-2.5 ${
                        isActive
                          ? "bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                          : "bg-[var(--surface-muted)] text-[var(--text-primary)]"
                      }`}
                      aria-hidden="true"
                    >
                      <Icon name={card.icon} size="1.6rem" />
                    </div>

                    <div className="min-w-0 flex-1 pr-16">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone={card.badgeTone} className="font-semibold">
                          {language === "vi" ? card.badgeVi : card.badgeEn}
                        </Badge>
                        <span className="font-mono text-[11px] text-[var(--text-muted)]">
                          role: {card.role}
                        </span>
                      </div>

                      <h2 className="mt-1.5 text-lg font-bold text-[var(--text-primary)] sm:text-xl">
                        {language === "vi" ? card.titleVi : card.titleEn}
                      </h2>
                    </div>
                  </div>

                  {/* Target Persona Tagline */}
                  <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)]/60 bg-[var(--surface-muted)]/70 p-3 text-xs leading-relaxed text-[var(--text-secondary)]">
                    <span className="font-bold text-[var(--text-primary)]">
                      {language === "vi" ? card.personaTitleVi : card.personaTitleEn}{" "}
                    </span>
                    <span>{language === "vi" ? card.personaVi : card.personaEn}</span>
                  </div>

                  {/* Rich Description */}
                  <p className="text-xs leading-relaxed text-[var(--text-secondary)] sm:text-sm">
                    {language === "vi" ? card.descriptionVi : card.descriptionEn}
                  </p>

                  {/* Key Capabilities List */}
                  <div className="space-y-2 pt-2">
                    <div className="flex items-center justify-between">
                      <h3 className="text-xs font-bold tracking-wider text-[var(--text-muted)] uppercase">
                        {language === "vi"
                          ? `Tính năng trọng tâm (${card.capabilities.length}):`
                          : `Key Capabilities (${card.capabilities.length}):`}
                      </h3>
                      <span className="text-[11px] text-[var(--text-muted)]">
                        {language === "vi" ? "Chạm để mở ngay" : "Click to launch directly"}
                      </span>
                    </div>

                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      {card.capabilities.map((cap) => (
                        <button
                          key={cap.id}
                          type="button"
                          data-testid={`capability-btn-${cap.id}`}
                          onClick={() => handleCapabilityJump(card, cap)}
                          className="group flex items-start gap-2.5 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)]/80 bg-[var(--surface-panel)] p-2.5 text-left transition hover:border-[color:var(--brand-500)]/60 hover:bg-[var(--surface-muted)] focus-ring"
                        >
                          <span className="mt-0.5 text-[var(--text-muted)] transition group-hover:text-[var(--text-brand)]">
                            <Icon name={cap.icon} size="1rem" />
                          </span>
                          <div className="min-w-0 flex-1">
                            <span className="block truncate text-xs font-semibold text-[var(--text-primary)] group-hover:text-[var(--text-brand)]">
                              {cap.label}
                            </span>
                            <span className="block line-clamp-1 text-[11px] text-[var(--text-muted)]">
                              {language === "vi" ? cap.descVi : cap.descEn}
                            </span>
                          </div>
                          <span className="mt-0.5 text-[var(--text-muted)] opacity-0 transition group-hover:opacity-100">
                            <Icon name="arrow-right" size="0.85rem" />
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Card Actions Footer */}
                <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-[color:var(--shell-border)] pt-4">
                  <button
                    type="button"
                    data-testid={`select-role-${card.id}`}
                    onClick={() => handleSelectWorkspace(card)}
                    className={`inline-flex min-h-[38px] items-center gap-1.5 rounded-[var(--radius-lg)] border px-3.5 text-xs font-semibold transition ${
                      isActive
                        ? "border-[color:var(--brand-500)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                        : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:bg-[var(--surface-panel)] hover:text-[var(--text-primary)]"
                    }`}
                  >
                    <Icon name="check" size="0.95rem" />
                    <span>
                      {isActive
                        ? language === "vi"
                          ? "Đang chọn vai trò này"
                          : "Current Role Active"
                        : language === "vi"
                          ? "Chọn vai trò này"
                          : "Select This Role"}
                    </span>
                  </button>

                  <Button
                    type="button"
                    variant="primary"
                    size="sm"
                    data-testid={`launch-workspace-${card.id}`}
                    onClick={() => handleInstantLaunch(card)}
                    className="min-h-[38px] gap-1.5 px-4 text-xs font-bold"
                  >
                    <span>
                      {language === "vi"
                        ? `Khởi chạy ${card.badgeVi}`
                        : `Launch ${card.badgeEn}`}
                    </span>
                    <Icon name="arrow-right" size="1rem" />
                  </Button>
                </div>
              </SurfaceCard>
            );
          })}
        </main>

        {/* Empty Search Fallback */}
        {visibleCards.length === 0 && (
          <SurfaceCard className="p-12 text-center">
            <Icon name="search" size="2.5rem" className="mx-auto text-[var(--text-muted)]" />
            <h2 className="mt-3 text-base font-bold text-[var(--text-primary)]">
              {language === "vi"
                ? "Không tìm thấy tính năng hoặc vai trò phù hợp"
                : "No matching workspace or capability found"}
            </h2>
            <p className="mt-1 text-xs text-[var(--text-secondary)]">
              {language === "vi"
                ? `Không có kết quả nào cho "${filterQuery}". Vui lòng thử từ khóa khác.`
                : `No results matching "${filterQuery}". Please try another search term.`}
            </p>
            <button
              type="button"
              onClick={() => {
                setFilterQuery("");
                setSelectedCategory("all");
              }}
              className="mt-4 inline-flex items-center gap-1.5 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-2 text-xs font-semibold text-[var(--text-primary)] hover:bg-[var(--surface-muted)]"
            >
              <Icon name="refresh" size="0.95rem" />
              <span>{language === "vi" ? "Đặt lại bộ lọc" : "Reset Filter"}</span>
            </button>
          </SurfaceCard>
        )}

        {/* Safety & Compliance Invariant Clarification Banner */}
        <section
          aria-label="Quy chuẩn an toàn và phân quyền RBAC"
          className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)]/60 p-5 text-xs text-[var(--text-secondary)]"
        >
          <div className="flex items-start gap-3">
            <div className="mt-0.5 text-[var(--brand-600)] shrink-0">
              <Icon name="warning" size="1.25rem" />
            </div>
            <div className="space-y-1">
              <h2 className="text-xs font-bold text-[var(--text-primary)]">
                {language === "vi"
                  ? "Nguyên tắc An toàn & Phân quyền RBAC của CLARA"
                  : "CLARA Safety Invariant & RBAC Principle"}
              </h2>
              <p className="leading-relaxed">
                {language === "vi"
                  ? "Việc chuyển đổi không gian làm việc hoặc chế độ xem trước trên giao diện chỉ điều chỉnh góc nhìn và bố cục tác vụ. Mọi thao tác truy xuất dữ liệu bệnh án, kê đơn hay thẩm định thuốc luôn được bảo vệ nghiêm ngặt bởi ranh giới phân quyền máy chủ RBAC và hàng rào an toàn FIDES."
                  : "Workspace selection and client preview switching configure presentation layouts and prioritized task surfaces. Server-side RBAC and FIDES clinical guardrails remain the authoritative safety boundary for all PHR and medical actions."}
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
