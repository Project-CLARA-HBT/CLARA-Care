"use client";

import {
  ReactNode,
  useContext,
  useEffect,
  useState,
} from "react";
import { usePathname, useRouter } from "next/navigation";
import { isAxiosError } from "axios";
import TransparencyNoticeGate from "@/components/compliance/transparency-notice-gate";
import PreviewContextStrip from "@/components/shell/preview-context-strip";
import AdminPreviewBanner, {
  PreviewBanner,
} from "@/components/shell/admin-preview-banner";
import GlobalCommandBar from "@/components/shell/global-context-bar";
import ContextHeader from "@/components/shell/context-header";
import ContentFrame from "@/components/shell/content-frame";
import WorkspaceDock from "@/components/shell/workspace-dock";
import FloatingNavbar from "@/components/shell/floating-navbar";
import CommandPalette from "@/components/shell/command-palette";
import { PreferenceContext } from "@/components/shell/preference-provider";
import { SessionContext } from "@/components/shell/session-boundary";
import { ProfileBoundaryContext } from "@/components/shell/profile-boundary";
import { useShellMode } from "@/components/shell/shell-mode-provider";
import {
  clearTokens,
  getRole,
  setAuthoritativeServerRole,
} from "@/lib/auth-store";
import api from "@/lib/http-client";
import {
  getRoleHomePath,
  isAuthenticatedUtilityRoute,
  isPublicRoute,
  isRouteAllowedForRole,
  type UserRole,
} from "@/lib/navigation.config";
import { getPhrOnboarding } from "@/lib/phr-onboarding";
import { t } from "@/lib/i18n/catalog";

export interface UnifiedAppShellProps {
  children: ReactNode;
}

const IMMERSIVE_LAYOUT_PREFIXES = ["/chat", "/research", "/council", "/scribe"];

export function UnifiedAppShell({ children }: UnifiedAppShellProps) {
  const pathname = usePathname();
  const router = useRouter();

  const sessionContext = useContext(SessionContext);
  const preferenceContext = useContext(PreferenceContext);
  const profileBoundaryContext = useContext(ProfileBoundaryContext);
  const shellMode = useShellMode();

  // Fallback state if rendered outside SessionBoundary
  const [localRole, setLocalRole] = useState<UserRole>("normal");
  const [isRoleHydrated, setIsRoleHydrated] = useState(false);
  const [isSessionChecked, setIsSessionChecked] = useState(false);

  const role = sessionContext ? sessionContext.role : localRole;
  const effectiveRole = sessionContext ? sessionContext.effectiveRole : role;
  const adminPreviewMode = sessionContext ? sessionContext.adminPreviewMode : null;
  const uiLanguage = preferenceContext ? preferenceContext.uiLanguage : "vi";

  const isPublicOrUtility =
    isPublicRoute(pathname) || isAuthenticatedUtilityRoute(pathname);

  const isImmersivePath = IMMERSIVE_LAYOUT_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
  const isChatLayout = pathname === "/chat" || pathname.startsWith("/chat/");
  const isImmersive = shellMode.isImmersive;
  // Spec v8 §4.5 & §5.3: WorkspaceDock is active on Personal, Clinical, Research (including /chat); suppressed only on /admin/*
  const hideBottomDock = pathname.startsWith("/admin/") || shellMode.isImmersive;

  // Fallback hydration if outside SessionBoundary
  useEffect(() => {
    if (sessionContext) return;
    let active = true;
    const hydrateSession = async () => {
      if (isPublicRoute(pathname)) {
        setLocalRole(getRole());
        setIsRoleHydrated(true);
        setIsSessionChecked(true);
        return;
      }
      try {
        const response = await api.get<{ role?: UserRole }>("/auth/me", {
          timeout: 15000,
        });
        const serverRole = response.data?.role;
        if (
          active &&
          (serverRole === "normal" ||
            serverRole === "researcher" ||
            serverRole === "doctor" ||
            serverRole === "admin")
        ) {
          setAuthoritativeServerRole(serverRole);
          setLocalRole(serverRole);
        } else if (active) {
          setLocalRole(getRole());
        }
      } catch (error) {
        const status = isAxiosError(error)
          ? Number(error.response?.status ?? 0)
          : 0;
        if (active && status === 401) {
          clearTokens();
          router.replace(`/login?next=${encodeURIComponent(pathname)}`);
          return;
        }
        if (active) setLocalRole(getRole());
      } finally {
        if (active) {
          setIsRoleHydrated(true);
          setIsSessionChecked(true);
        }
      }
    };
    void hydrateSession();
    return () => {
      active = false;
    };
  }, [pathname, router, sessionContext]);

  // Fallback route guarding if outside SessionBoundary
  useEffect(() => {
    if (sessionContext) return;
    if (isPublicRoute(pathname)) return;
    if (!isRoleHydrated || !isSessionChecked) return;
    const allowed =
      isAuthenticatedUtilityRoute(pathname) ||
      isRouteAllowedForRole(pathname, role);
    if (allowed) return;
    router.replace(getRoleHomePath(role));
  }, [isRoleHydrated, isSessionChecked, pathname, role, router, sessionContext]);

  // Fallback first-run setup if outside SessionBoundary
  useEffect(() => {
    if (sessionContext) return;
    if (isPublicRoute(pathname)) return;
    if (!isRoleHydrated || !isSessionChecked) return;
    let active = true;
    const enforceFirstRunSetup = async () => {
      try {
        const onboarding = await getPhrOnboarding();
        if (!active) return;
        const inWelcomeFlow =
          pathname === "/welcome" ||
          pathname.startsWith("/welcome/") ||
          pathname === "/onboarding" ||
          pathname.startsWith("/onboarding/");
        const isProfessional =
          role === "doctor" || role === "researcher" || role === "admin";
        if (!isProfessional && onboarding.needs_onboarding && !inWelcomeFlow) {
          router.replace("/welcome/start");
          return;
        }
        if (!onboarding.needs_onboarding && inWelcomeFlow && pathname !== "/onboarding") {
          router.replace(getRoleHomePath(role));
        }
      } catch {
        // Fail open when onboarding endpoint is temporarily unavailable
      }
    };
    void enforceFirstRunSetup();
    return () => {
      active = false;
    };
  }, [isRoleHydrated, isSessionChecked, pathname, role, router, sessionContext]);

  // On public/auth/share routes: suppresses ContextHeader/GlobalCommandBar and WorkspaceDock, mounts clean unauthenticated container
  if (isPublicOrUtility) {
    return (
      <div
        id="public-shell-root"
        className="min-h-[100dvh] bg-[var(--bg-canvas)] text-[var(--text-primary)]"
      >
        {children}
        <CommandPalette role={effectiveRole} />
      </div>
    );
  }

  // On standard/focus/dense/explore/read/immersive routes:
  // Shell composition order: PreviewContextStrip -> GlobalCommandBar -> <main id="main-content"> (ContentFrame) -> WorkspaceDock -> CommandPalette
  return (
    <div
      data-testid="unified-app-shell"
      className="min-h-screen bg-[var(--bg-canvas)] text-[var(--text-primary)]"
    >
      <a href="#main-content" className="skip-link">
        {t(uiLanguage, "navigation.skipToContent")}
      </a>
      <TransparencyNoticeGate />

      {/* 1. Top: PreviewContextStrip & PreviewBanner (admin preview only) */}
      <PreviewContextStrip />
      <PreviewBanner />

      {/* 2. Top: GlobalCommandBar */}
      <GlobalCommandBar />

      {/* 3. Main Content Canvas: ContentFrame (<main id="main-content">) */}
      <ContentFrame
        isImmersive={isImmersive}
        isChatLayout={isChatLayout}
      >
        {children}
      </ContentFrame>

      {/* 4. Bottom: WorkspaceDock (smoothly recedes on immersive routes) */}
      {!hideBottomDock && <WorkspaceDock role={effectiveRole} />}

      {/* 5. Universal Command Palette (Cmd+K / Ctrl+K) */}
      <CommandPalette role={effectiveRole} />
    </div>
  );
}

export default UnifiedAppShell;
