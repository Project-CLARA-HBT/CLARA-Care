"use client";

import { ReactNode, useContext, useEffect, useState } from "react";
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
  setRole as setStoredRole,
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

type Props = {
  children: ReactNode;
};

const IMMERSIVE_LAYOUT_PREFIXES = ["/chat", "/research", "/council", "/scribe"];

export default function AppShell({ children }: Props) {
  const pathname = usePathname();
  const router = useRouter();

  const sessionContext = useContext(SessionContext);
  const preferenceContext = useContext(PreferenceContext);
  const profileBoundaryContext = useContext(ProfileBoundaryContext);
  const shellMode = useShellMode();

  // Fallback state if rendered outside SessionBoundary (e.g. standalone tests)
  const [localRole, setLocalRole] = useState<UserRole>("normal");
  const [isRoleHydrated, setIsRoleHydrated] = useState(false);
  const [isSessionChecked, setIsSessionChecked] = useState(false);

  const role = sessionContext ? sessionContext.role : localRole;
  const effectiveRole = sessionContext ? sessionContext.effectiveRole : role;
  const adminPreviewMode = sessionContext ? sessionContext.adminPreviewMode : null;
  const uiLanguage = preferenceContext ? preferenceContext.uiLanguage : "vi";

  const hideSidebar =
    isPublicRoute(pathname) || isAuthenticatedUtilityRoute(pathname);
  const isImmersiveLayout = IMMERSIVE_LAYOUT_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
  const isChatLayout = pathname === "/chat" || pathname.startsWith("/chat/");
  const hideFloatingDock = shellMode.isImmersive;

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
          setStoredRole(serverRole);
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

  if (hideSidebar) {
    return (
      <main
        id="main-content"
        className="min-h-[100dvh] bg-[var(--bg-canvas)] text-[var(--text-primary)]"
      >
        {children}
        <CommandPalette role={effectiveRole} />
      </main>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--bg-canvas)] text-[var(--text-primary)]">
      <a href="#main-content" className="skip-link">
        {t(uiLanguage, "navigation.skipToContent")}
      </a>
      <TransparencyNoticeGate />

      {/* Top: Admin Preview Banner */}
      <AdminPreviewBanner />

      {/* Top: GlobalContextBar */}
      <GlobalContextBar />

      {/* Main Content Canvas */}
      <main
        id="main-content"
        tabIndex={-1}
        className={[
          "app-content-canvas flex-1",
          isImmersiveLayout
            ? isChatLayout
              ? "px-0 pb-[calc(env(safe-area-inset-bottom,0px)+5rem)] pt-0 sm:px-0 sm:pb-24 sm:pt-0 lg:px-0 lg:pb-0 lg:pt-0"
              : "px-0 pb-[calc(env(safe-area-inset-bottom,0px)+5rem)] pt-0 sm:px-0.5 sm:pb-24 sm:pt-0 lg:px-0.5 lg:pb-1 lg:pt-0"
            : "px-4 pb-[calc(env(safe-area-inset-bottom,0px)+6rem)] pt-5 sm:px-6 sm:pb-28 sm:pt-7 lg:px-12 lg:pb-24 lg:pt-8",
        ].join(" ")}
      >
        <div
          className={[
            "w-full",
            isImmersiveLayout ? "max-w-none" : "mx-auto max-w-[1120px]",
          ].join(" ")}
        >
          {children}
        </div>
      </main>

      {/* Bottom: FloatingPrimaryDock (with CLARA Orb) */}
      {!hideFloatingDock && <FloatingPrimaryDock role={effectiveRole} />}

      {/* Universal Command Palette (Cmd+K / Ctrl+K) */}
      <CommandPalette role={effectiveRole} />
    </div>
  );
}
