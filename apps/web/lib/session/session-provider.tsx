"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { isAxiosError } from "axios";
import api from "@/lib/http-client";
import { clearTokens, setAuthoritativeServerRole } from "@/lib/auth-store";
import {
  normalizeServerRole,
  type ServerRole,
  type ServerSessionState,
  type SessionProviderProps,
  type SessionUser,
} from "./session.contract";

export const SessionContext = createContext<ServerSessionState | null>(null);

export function SessionProvider({
  children,
  initialSession,
  autoHydrate = true,
}: SessionProviderProps) {
  const [serverRole, setServerRole] = useState<ServerRole | null>(
    initialSession?.serverRole ?? null,
  );
  const [user, setUser] = useState<SessionUser | null>(
    initialSession?.user ?? null,
  );
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(
    initialSession?.isAuthenticated ?? false,
  );
  const [isHydrating, setIsHydrating] = useState<boolean>(
    initialSession?.isHydrating ?? (autoHydrate && !initialSession),
  );
  const [error, setError] = useState<Error | null>(
    initialSession?.error ?? null,
  );

  const isHydratingRef = useRef(false);

  const fetchSession = useCallback(async () => {
    if (isHydratingRef.current) return;
    isHydratingRef.current = true;
    setIsHydrating(true);
    setError(null);

    try {
      const response = await api.get<{
        role?: string;
        email?: string;
        subject?: string;
        full_name?: string;
        id?: string | number;
      }>("/auth/me", { timeout: 15000 });

      const rawData = response.data;
      const role = normalizeServerRole(rawData?.role);
      const email =
        typeof rawData?.email === "string"
          ? rawData.email
          : typeof rawData?.subject === "string"
            ? rawData.subject
            : "";
      const id =
        rawData?.id !== undefined
          ? rawData.id
          : rawData?.subject !== undefined
            ? rawData.subject
            : "";
      const fullName =
        typeof rawData?.full_name === "string" ? rawData.full_name : undefined;

      const resolvedRole: ServerRole = role ?? "normal";
      setServerRole(resolvedRole);
      setAuthoritativeServerRole(resolvedRole);
      setUser({ id, email, full_name: fullName });
      setIsAuthenticated(true);
      setError(null);
    } catch (err: unknown) {
      const status = isAxiosError(err) ? Number(err.response?.status ?? 0) : 0;
      if (status === 401 || status === 403) {
        clearTokens();
        setServerRole(null);
        setAuthoritativeServerRole(null);
        setUser(null);
        setIsAuthenticated(false);
        setError(null);
      } else {
        setServerRole(null);
        setAuthoritativeServerRole(null);
        setUser(null);
        setIsAuthenticated(false);
        setError(err instanceof Error ? err : new Error(String(err)));
      }
    } finally {
      setIsHydrating(false);
      isHydratingRef.current = false;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout", {}, { timeout: 5000 });
    } catch {
      // Safe fallback on upstream revocation failure
    } finally {
      clearTokens();
      setServerRole(null);
      setAuthoritativeServerRole(null);
      setUser(null);
      setIsAuthenticated(false);
      setError(null);
      if (typeof window !== "undefined") {
        window.location.replace("/logout");
      }
    }
  }, []);

  const refreshSession = useCallback(async () => {
    await fetchSession();
  }, [fetchSession]);

  useEffect(() => {
    if (autoHydrate && !initialSession) {
      void fetchSession();
    }
  }, [autoHydrate, fetchSession, initialSession]);

  const value = useMemo<ServerSessionState>(
    () => ({
      serverRole,
      isAuthenticated,
      isHydrating,
      user,
      error,
      logout,
      refreshSession,
    }),
    [
      serverRole,
      isAuthenticated,
      isHydrating,
      user,
      error,
      logout,
      refreshSession,
    ],
  );

  return (
    <SessionContext.Provider value={value}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession(): ServerSessionState {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSession must be used within a SessionProvider");
  }
  return context;
}

export const useServerSession = useSession;
export const ServerSessionProvider = SessionProvider;
export default SessionProvider;
