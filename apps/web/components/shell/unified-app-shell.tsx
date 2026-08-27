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
import AdminPreviewBanner from "@/components/shell/admin-preview-banner";
import GlobalContextBar from "@/components/shell/global-context-bar";
import FloatingPrimaryDock from "@/components/shell/floating-primary-dock";
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

const AUTH_STANDALONE_ROUTES = new Set([
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
  "/auth/callback",
]);

function isAuthOrStandaloneRoute(pathname: string | null): boolean {
  if (!pathname) return false;
  if (pathname === "/") return true; // Landing page uses dedicated spatial landing navbar & footer
  if (AUTH_STANDALONE_ROUTES.has(pathname)) return true;
  if (
    pathname === "/welcome" ||
    pathname.startsWith("/welcome/") ||
    pathname === "/onboarding" ||
    pathname.startsWith("/onboarding/") ||
    pathname === "/role-select" ||
    pathname.startsWith("/share/")
  ) {
    return true;
  }
  return false;
}

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

  const isStandalone = isAuthOrStandaloneRoute(pathname);

  const isImmersivePath = IMMERSIVE_LAYOUT_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
  const isChatLayout = pathname === "/chat" || pathname.startsWith("/chat/");
  const hideBottomDock = shellMode.isImmersive;

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

  // On public auth/onboarding/standalone routes: suppresses app shell, mounts clean container
  if (isStandalone) {
    return (
      <div
        id="public-shell-root"
        className="min-h-[100dvh] bg-[var(--bg-canvas)] text-[var(--text-primary)]"
      >
        <main id="main-content" tabIndex={-1}>
          {children}
        </main>
        <CommandPalette role={effectiveRole} />
      </div>
    );
  }

  // On standard/focus/dense/explore/read/immersive app routes:
  return (
    <div
      data-testid="unified-app-shell"
      className="min-h-screen bg-[var(--bg-canvas)] text-[var(--text-primary)]"
    >
      <a href="#main-content" className="skip-link">
        {t(uiLanguage, "navigation.skipToContent")}
      </a>
      <TransparencyNoticeGate />

      {/* 1. Top: Admin Preview Banner */}
      <AdminPreviewBanner />

      {/* 2. Top: GlobalContextBar */}
      <GlobalContextBar />

      {/* 3. Main Content Canvas */}
      <main
        id="main-content"
        data-testid="content-frame"
        data-immersive={isImmersivePath || shellMode.isImmersive ? "true" : "false"}
        tabIndex={-1}
        className={[
          "app-content-canvas flex-1",
          isImmersivePath
            ? isChatLayout
              ? "px-0 pb-[calc(env(safe-area-inset-bottom,0px)+5.5rem)] pt-0 sm:px-0 sm:pb-24 sm:pt-0 lg:px-0 lg:pb-0 lg:pt-0"
              : "px-0 pb-[calc(env(safe-area-inset-bottom,0px)+5.5rem)] pt-0 sm:px-0.5 sm:pb-24 sm:pt-0 lg:px-0.5 lg:pb-1 lg:pt-0"
            : "px-4 pb-[calc(env(safe-area-inset-bottom,0px)+6.5rem)] pt-5 sm:px-6 sm:pb-28 sm:pt-7 lg:px-12 lg:pb-24 lg:pt-8",
        ].join(" ")}
      >
        <div
          className={[
            "w-full",
            isImmersivePath ? "max-w-none" : "mx-auto max-w-[1120px]",
          ].join(" ")}
        >
          {children}
        </div>
      </main>

      {/* 4. Bottom: FloatingPrimaryDock with CLARA Orb (role-adaptive) */}
      {!hideBottomDock && <FloatingPrimaryDock role={effectiveRole} />}

      {/* 5. Universal Command Palette (Cmd+K / Ctrl+K) */}
      <CommandPalette role={effectiveRole} />
    </div>
  );
}

export default UnifiedAppShell;
