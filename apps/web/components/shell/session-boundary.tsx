"use client";

import { isAxiosError } from "axios";
import { usePathname, useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  clearTokens,
  getRole,
  setRole as setStoredRole,
  type UserRole,
} from "@/lib/auth-store";
import api from "@/lib/http-client";
import { beginLogout } from "@/lib/logout";
import {
  getRoleHomePath,
  isAuthenticatedUtilityRoute,
  isPublicRoute,
  isRouteAllowedForRole,
} from "@/lib/navigation.config";
import { getPhrOnboarding } from "@/lib/phr-onboarding";

export type AdminPreviewMode = "clinical" | "research" | "personal";

export type SessionContextValue = {
  role: UserRole;
  effectiveRole: UserRole;
  adminPreviewMode: AdminPreviewMode | null;
  setAdminPreviewMode: (mode: AdminPreviewMode | null) => void;
  setRole: (role: UserRole) => void;
  isRoleHydrated: boolean;
  isSessionChecked: boolean;
  isLoggingOut: boolean;
  handleLogout: () => void;
};

export const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionBoundary({
  children,
  initialPreviewMode = null,
}: {
  children: ReactNode;
  initialPreviewMode?: AdminPreviewMode | null;
}) {
  const pathname = usePathname();
  const router = useRouter();

  const [role, setRoleState] = useState<UserRole>("normal");
  const [adminPreviewMode, setAdminPreviewMode] = useState<AdminPreviewMode | null>(
    initialPreviewMode,
  );
  const [isRoleHydrated, setIsRoleHydrated] = useState(false);
  const [isSessionChecked, setIsSessionChecked] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const effectiveRole = useMemo<UserRole>(() => {
    if (role !== "admin" || !adminPreviewMode) return role;
    switch (adminPreviewMode) {
      case "clinical":
        return "doctor";
      case "research":
        return "researcher";
      case "personal":
        return "normal";
      default:
        return role;
    }
  }, [role, adminPreviewMode]);

  useEffect(() => {
    let active = true;
    const hydrateSession = async () => {
      if (isPublicRoute(pathname)) {
        setRoleState(getRole());
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
          setRoleState(serverRole);
        } else if (active) {
          setRoleState(getRole());
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
        if (active) setRoleState(getRole());
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
  }, [pathname, router]);

  useEffect(() => {
    if (isPublicRoute(pathname)) return;
    if (!isRoleHydrated || !isSessionChecked) return;
    const allowed =
      isAuthenticatedUtilityRoute(pathname) ||
      isRouteAllowedForRole(pathname, role);
    if (allowed) return;
    router.replace(getRoleHomePath(role));
  }, [isRoleHydrated, isSessionChecked, pathname, role, router]);

  useEffect(() => {
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
        // Fail open when additive onboarding endpoint is temporarily unavailable.
      }
    };
    void enforceFirstRunSetup();
    return () => {
      active = false;
    };
  }, [isRoleHydrated, isSessionChecked, pathname, role, router]);

  const handleLogout = useCallback(() => {
    if (isLoggingOut) return;
    setIsLoggingOut(true);
    beginLogout();
  }, [isLoggingOut]);

  const setRole = useCallback((nextRole: UserRole) => {
    setRoleState(nextRole);
    setStoredRole(nextRole);
  }, []);

  const value = useMemo<SessionContextValue>(
    () => ({
      role,
      effectiveRole,
      adminPreviewMode,
      setAdminPreviewMode,
      setRole,
      isRoleHydrated,
      isSessionChecked,
      isLoggingOut,
      handleLogout,
    }),
    [
      role,
      effectiveRole,
      adminPreviewMode,
      setAdminPreviewMode,
      setRole,
      isRoleHydrated,
      isSessionChecked,
      isLoggingOut,
      handleLogout,
    ],
  );

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useSession(): SessionContextValue {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSession must be used within a SessionBoundary");
  }
  return context;
}
