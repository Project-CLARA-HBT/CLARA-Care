import type { ReactNode } from "react";

export type ServerRole = "normal" | "researcher" | "doctor" | "admin";
export type UserRole = ServerRole;

export interface SessionUser {
  id: string | number;
  email: string;
  full_name?: string;
}

export interface ServerSessionState {
  serverRole: ServerRole | null;
  isAuthenticated: boolean;
  isHydrating: boolean;
  user: SessionUser | null;
  error: Error | null;
  logout: () => Promise<void>;
  refreshSession: () => Promise<void>;
}

export type ServerSessionContextValue = ServerSessionState;

export const VALID_SERVER_ROLES: readonly ServerRole[] = [
  "normal",
  "researcher",
  "doctor",
  "admin",
] as const;

export function normalizeServerRole(value: unknown): ServerRole | null {
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

export interface SessionProviderProps {
  children: ReactNode;
  initialSession?: Partial<ServerSessionState>;
  autoHydrate?: boolean;
}
