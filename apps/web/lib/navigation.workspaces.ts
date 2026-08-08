import {
  getNavItemsByRole,
  isActiveRoute,
  type NavigationItem,
  type UserRole,
} from "@/lib/navigation.config";
import type { UILanguage } from "@/lib/ui-language";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";

export type WorkspaceId = "personal" | "clinical" | "research" | "admin";

export type WorkspaceMeta = {
  id: WorkspaceId;
  label: string;
  shortLabel: string;
  icon: string;
  homeHref: string;
};

export type WorkspaceNavigation = {
  workspace: WorkspaceMeta;
  primary: NavigationItem[];
  secondary: NavigationItem[];
};

const WORKSPACE_ROLES: Record<WorkspaceId, UserRole[]> = {
  personal: ["normal", "researcher", "doctor", "admin"],
  clinical: ["doctor", "admin"],
  research: ["researcher", "doctor", "admin"],
  admin: ["admin"],
};

const WORKSPACE_ORDER: WorkspaceId[] = ["personal", "clinical", "research", "admin"];

const PRIMARY_HREFS: Record<WorkspaceId, string[]> = {
  personal: ["/today", "/chat", "/lifemap", "/medicines", "/phr"],
  clinical: ["/chat", "/council", "/scribe"],
  research: ["/chat", "/evidence", "/research/source-hub"],
  admin: [
    "/admin/overview",
    "/admin/knowledge-sources",
    "/admin/answer-flow",
    "/admin/observability",
    "/admin/analytics",
  ],
};

const SECONDARY_HREFS: Record<WorkspaceId, string[]> = {
  personal: [
    "/visits",
    "/family",
    "/community",
    "/chat/shares",
    "/account/consent",
    "/account/data",
    "/huong-dan",
  ],
  clinical: ["/phr", "/evidence", "/research/source-hub", "/huong-dan"],
  research: ["/chat/shares", "/huong-dan"],
  admin: [
    "/admin/community-moderation",
    "/admin/analytics/clinical",
    "/admin/audit-log",
    "/admin/rag-eval",
    "/admin/rag-ingestion",
    "/admin/dsar",
    "/dashboard/control-tower",
    "/dashboard/ecosystem",
    "/research/source-hub",
    "/huong-dan",
  ],
};

const LABELS: Record<WorkspaceId, { key: UITranslationKey; icon: string; homeHref: string }> = {
  personal: {
    key: "navigation.workspace.personal",
    icon: "person",
    homeHref: "/today",
  },
  clinical: {
    key: "navigation.workspace.clinical",
    icon: "stethoscope",
    homeHref: "/dashboard",
  },
  research: {
    key: "navigation.workspace.research",
    icon: "science",
    homeHref: "/chat",
  },
  admin: {
    key: "navigation.workspace.admin",
    icon: "admin_panel_settings",
    homeHref: "/admin/overview",
  },
};

const EXTRA_ITEMS: Record<string, { key: UITranslationKey; icon: string; roles: UserRole[] }> = {
  "/chat/shares": { key: "navigation.item.chatShares", icon: "share", roles: ["normal", "researcher", "doctor", "admin"] },
  "/admin/audit-log": { key: "navigation.item.auditLog", icon: "history", roles: ["admin"] },
  "/admin/rag-eval": { key: "navigation.item.ragEval", icon: "fact_check", roles: ["admin"] },
  "/admin/rag-ingestion": { key: "navigation.item.ragIngestion", icon: "upload_file", roles: ["admin"] },
  "/dashboard/control-tower": { key: "navigation.page.controlTower.title", icon: "account_tree", roles: ["admin"] },
  "/dashboard/ecosystem": { key: "navigation.page.ecosystem.title", icon: "hub", roles: ["admin"] },
};

function item(
  href: string,
  label: string,
  icon: string,
  roles: UserRole[],
): NavigationItem {
  return {
    href,
    label,
    shortLabel: label,
    icon,
    desc: label,
    group: "support",
    roles,
    page: { title: label, subtitle: label },
  };
}

function meta(id: WorkspaceId, language: UILanguage): WorkspaceMeta {
  const value = LABELS[id];
  const label = t(language, value.key);
  return { id, label, shortLabel: label, icon: value.icon, homeHref: value.homeHref };
}

export function getAvailableWorkspaces(
  role: UserRole,
  language: UILanguage = "vi",
): WorkspaceMeta[] {
  return WORKSPACE_ORDER.filter((id) => WORKSPACE_ROLES[id].includes(role)).map((id) =>
    meta(id, language),
  );
}

export function isWorkspaceAvailable(role: UserRole, workspace: WorkspaceId): boolean {
  return WORKSPACE_ROLES[workspace].includes(role);
}

function allPresentationItems(role: UserRole, language: UILanguage): NavigationItem[] {
  const items = getNavItemsByRole(role, language);
  const known = new Set(items.map((entry) => entry.href));
  for (const [href, extra] of Object.entries(EXTRA_ITEMS)) {
    if (extra.roles.includes(role) && !known.has(href)) {
      items.push(item(href, t(language, extra.key), extra.icon, extra.roles));
    }
  }
  return items;
}

export function getWorkspaceNavigation(
  role: UserRole,
  workspace: WorkspaceId,
  language: UILanguage = "vi",
): WorkspaceNavigation {
  const safeWorkspace = isWorkspaceAvailable(role, workspace)
    ? workspace
    : getAvailableWorkspaces(role, language)[0]?.id ?? "personal";
  const all = allPresentationItems(role, language);
  const byHref = new Map(all.map((entry) => [entry.href, entry]));
  const primary = PRIMARY_HREFS[safeWorkspace]
    .map((href) => byHref.get(href))
    .filter((entry): entry is NavigationItem => Boolean(entry))
    .slice(0, 7);
  const secondary = SECONDARY_HREFS[safeWorkspace]
    .map((href) => byHref.get(href))
    .filter((entry): entry is NavigationItem => Boolean(entry));

  return { workspace: meta(safeWorkspace, language), primary, secondary };
}

export function getWorkspaceForPath(
  pathname: string,
  role: UserRole,
  current?: WorkspaceId,
): WorkspaceId {
  const available = getAvailableWorkspaces(role).map((entry) => entry.id);
  // `/dashboard` is the authenticated professional landing page, not a
  // workspace destination. Keep the user's current permitted workspace in the
  // shell while the overview is open; use a role-appropriate presentation
  // fallback only when there is no prior choice. Route authorization remains
  // independently enforced by navigation.access.ts.
  if (pathname === "/dashboard") {
    if (current && available.includes(current)) return current;
    if (role === "researcher" && available.includes("research")) return "research";
    if (role === "doctor" && available.includes("clinical")) return "clinical";
    if (role === "admin" && available.includes("admin")) return "admin";
    return available[0] ?? "personal";
  }
  if (current && available.includes(current)) {
    const currentPaths = [...PRIMARY_HREFS[current], ...SECONDARY_HREFS[current]];
    if (currentPaths.some((href) => isActiveRoute(pathname, href))) return current;
  }

  const preferred: WorkspaceId[] = pathname.startsWith("/admin")
    ? ["admin"]
    : pathname.startsWith("/council") || pathname.startsWith("/scribe")
      ? ["clinical"]
      : pathname.startsWith("/research") || pathname.startsWith("/evidence")
        ? ["research"]
        : ["personal", "clinical", "research", "admin"];

  return preferred.find((id) => available.includes(id)) ?? available[0] ?? "personal";
}

export function getMobileWorkspaceNav(
  role: UserRole,
  workspace: WorkspaceId,
  language: UILanguage = "vi",
): NavigationItem[] {
  return getWorkspaceNavigation(role, workspace, language).primary.slice(0, 4);
}
