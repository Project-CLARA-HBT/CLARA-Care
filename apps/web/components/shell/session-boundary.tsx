"use client";

import { isAxiosError } from "axios";
import { usePathname, useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  clearTokens,
  getRole,
  setRole as setStoredRole,
  getStoredAdminPreviewMode,
  setStoredAdminPreviewMode,
  ADMIN_PREVIEW_COOKIE_NAME,
  ADMIN_PREVIEW_CHANGE_EVENT,
  ADMIN_PREVIEW_STORAGE_KEY,
  ROLE_CHANGE_EVENT,
  ROLE_KEY,
  SESSION_CHANGE_EVENT,
  type UserRole,
  type AdminPreviewMode,
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

export type { AdminPreviewMode };
export {
  ROLE_KEY,
  ADMIN_PREVIEW_STORAGE_KEY,
  ADMIN_PREVIEW_COOKIE_NAME,
  ADMIN_PREVIEW_CHANGE_EVENT,
  ROLE_CHANGE_EVENT,
  SESSION_CHANGE_EVENT,
  getStoredAdminPreviewMode,
  setStoredAdminPreviewMode,
};

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

function normalizeMode(value: unknown): AdminPreviewMode | null {
  if (value === "clinical" || value === "research" || value === "personal") {
    return value;
  }
  return null;
}

function normalizeRole(value: unknown): UserRole | null {
  if (
    value === "normal" ||
    value === "researcher" ||
    value === "doctor" ||
    value === "admin"
  ) {
    return value;
  }
  return null;
}

export function SessionBoundary({
  children,
  initialPreviewMode = null,
}: {
  children: ReactNode;
  initialPreviewMode?: AdminPreviewMode | null;
}) {
  const pathname = usePathname();
  const router = useRouter();

  const [role, setRoleState] = useState<UserRole>(() => getRole() || "normal");
  const [adminPreviewMode, setAdminPreviewModeState] = useState<AdminPreviewMode | null>(
    () => initialPreviewMode ?? getStoredAdminPreviewMode(),
  );
  const [isRoleHydrated, setIsRoleHydrated] = useState(false);
  const [isSessionChecked, setIsSessionChecked] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const hasHydratedServerSessionRef = useRef(false);

  useEffect(() => {
    if (initialPreviewMode !== undefined) {
      setAdminPreviewModeState(normalizeMode(initialPreviewMode));
    }
  }, [initialPreviewMode]);

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

  const setAdminPreviewMode = useCallback((mode: AdminPreviewMode | null) => {
    const validMode = normalizeMode(mode);
    setAdminPreviewModeState(validMode);
    setStoredAdminPreviewMode(validMode);
    if (typeof window !== "undefined") {
      try {
        if (validMode) {
          window.localStorage.setItem(ADMIN_PREVIEW_STORAGE_KEY, validMode);
          document.cookie = `${ADMIN_PREVIEW_COOKIE_NAME}=${encodeURIComponent(validMode)}; Path=/; Max-Age=${60 * 60 * 24 * 7}; SameSite=Lax`;
        } else {
          window.localStorage.removeItem(ADMIN_PREVIEW_STORAGE_KEY);
          document.cookie = `${ADMIN_PREVIEW_COOKIE_NAME}=; Path=/; Max-Age=0; SameSite=Lax`;
        }
      } catch {
        // noop
      }
      window.dispatchEvent(
        new CustomEvent(ADMIN_PREVIEW_CHANGE_EVENT, { detail: validMode }),
      );
      window.dispatchEvent(
        new CustomEvent(SESSION_CHANGE_EVENT, {
          detail: { adminPreviewMode: validMode },
        }),
      );
    }
  }, []);

  const setRole = useCallback((nextRole: UserRole) => {
    const validRole = normalizeRole(nextRole);
    if (!validRole) return;
    setRoleState(validRole);
    setStoredRole(validRole);
    if (typeof window !== "undefined") {
      try {
        window.localStorage.setItem(ROLE_KEY, validRole);
      } catch {
        // noop
      }
      window.dispatchEvent(
        new CustomEvent(ROLE_CHANGE_EVENT, { detail: validRole }),
      );
      window.dispatchEvent(
        new CustomEvent(SESSION_CHANGE_EVENT, { detail: { role: validRole } }),
      );
    }
  }, []);

  // Listen to cross-component and cross-tab events
  useEffect(() => {
    if (typeof window === "undefined") return;

    const onPreviewEvent = (event: Event) => {
      const customEvent = event as CustomEvent<AdminPreviewMode | null>;
      const nextMode = normalizeMode(customEvent.detail);
      setAdminPreviewModeState((prev) => (prev !== nextMode ? nextMode : prev));
    };

    const onRoleEvent = (event: Event) => {
      const customEvent = event as CustomEvent<UserRole>;
      const nextRole = normalizeRole(customEvent.detail);
      if (nextRole) {
        setRoleState((prev) => (prev !== nextRole ? nextRole : prev));
      }
    };

    const onStorage = (event: StorageEvent) => {
      if (event.key === ADMIN_PREVIEW_STORAGE_KEY) {
        const nextMode = normalizeMode(event.newValue);
        setAdminPreviewModeState((prev) => (prev !== nextMode ? nextMode : prev));
      } else if (event.key === ROLE_KEY) {
        const nextRole = normalizeRole(event.newValue);
        if (nextRole) {
          setRoleState((prev) => (prev !== nextRole ? nextRole : prev));
        }
      }
    };

    window.addEventListener(ADMIN_PREVIEW_CHANGE_EVENT, onPreviewEvent);
    window.addEventListener(ROLE_CHANGE_EVENT, onRoleEvent);
    window.addEventListener("storage", onStorage);

    return () => {
      window.removeEventListener(ADMIN_PREVIEW_CHANGE_EVENT, onPreviewEvent);
      window.removeEventListener(ROLE_CHANGE_EVENT, onRoleEvent);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  useEffect(() => {
    let active = true;
    const hydrateSession = async () => {
      if (isPublicRoute(pathname)) {
        setRoleState(getRole());
        setIsRoleHydrated(true);
        setIsSessionChecked(true);
        return;
      }

      // Avoid dropping session or overwriting developer role switches on internal route transitions
      if (hasHydratedServerSessionRef.current && isSessionChecked) {
        setIsRoleHydrated(true);
        return;
      }

      try {
        const response = await api.get<{ role?: UserRole }>("/auth/me", {
          timeout: 15000,
        });
        const serverRole = normalizeRole(response.data?.role);
        if (active && serverRole) {
          setStoredRole(serverRole);
          setRoleState(serverRole);
        } else if (active) {
          setRoleState(getRole());
        }
        hasHydratedServerSessionRef.current = true;
      } catch (error) {
        const status = isAxiosError(error)
          ? Number(error.response?.status ?? 0)
          : 0;
        if (active && status === 401) {
          clearTokens();
          setStoredAdminPreviewMode(null);
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
  }, [pathname, router, isSessionChecked]);

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
    setStoredAdminPreviewMode(null);
    beginLogout();
  }, [isLoggingOut]);

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

export default SessionBoundary;
