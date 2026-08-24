"use client";

import React, { useEffect, useMemo, type ReactNode } from "react";
import { SessionContext } from "./session-provider";
import type {
  ServerRole,
  ServerSessionState,
  SessionUser,
} from "./session.contract";
import { setAuthoritativeServerRole } from "@/lib/auth-store";

export interface TestSessionInjectorProps {
  children: ReactNode;
  role?: ServerRole | null;
  user?: SessionUser | null;
  isAuthenticated?: boolean;
  isHydrating?: boolean;
  error?: Error | null;
  logout?: () => Promise<void>;
  refreshSession?: () => Promise<void>;
  sessionState?: Partial<ServerSessionState>;
}

/**
 * Test utility for injecting mock server session states into component unit and integration test trees.
 * Strictly for unit test mocking only.
 */
export function TestSessionInjector({
  children,
  role = "normal",
  user = { id: "test-user-id", email: "test@example.com", full_name: "Test User" },
  isAuthenticated = true,
  isHydrating = false,
  error = null,
  logout = async () => {},
  refreshSession = async () => {},
  sessionState,
}: TestSessionInjectorProps) {
  const resolvedRole =
    sessionState?.serverRole !== undefined ? sessionState.serverRole : role;
  const resolvedUser =
    sessionState?.user !== undefined ? sessionState.user : user;
  const resolvedIsAuthenticated =
    sessionState?.isAuthenticated !== undefined
      ? sessionState.isAuthenticated
      : isAuthenticated;
  const resolvedIsHydrating =
    sessionState?.isHydrating !== undefined
      ? sessionState.isHydrating
      : isHydrating;
  const resolvedError =
    sessionState?.error !== undefined ? sessionState.error : error;
  const resolvedLogout = sessionState?.logout ?? logout;
  const resolvedRefreshSession = sessionState?.refreshSession ?? refreshSession;

  // Synchronize auth-store in memory for synchronous getRole() callers during test execution
  setAuthoritativeServerRole(resolvedRole);

  useEffect(() => {
    setAuthoritativeServerRole(resolvedRole);
    return () => {
      setAuthoritativeServerRole(null);
    };
  }, [resolvedRole]);

  const value = useMemo<ServerSessionState>(
    () => ({
      serverRole: resolvedRole,
      isAuthenticated: resolvedIsAuthenticated,
      isHydrating: resolvedIsHydrating,
      user: resolvedUser,
      error: resolvedError,
      logout: resolvedLogout,
      refreshSession: resolvedRefreshSession,
    }),
    [
      resolvedRole,
      resolvedIsAuthenticated,
      resolvedIsHydrating,
      resolvedUser,
      resolvedError,
      resolvedLogout,
      resolvedRefreshSession,
    ],
  );

  return (
    <SessionContext.Provider value={value}>
      {children}
    </SessionContext.Provider>
  );
}

export default TestSessionInjector;
