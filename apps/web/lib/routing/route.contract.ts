import type { UserRole } from "@/lib/auth-store";

export type { UserRole };

export type RouteWorkspace =
  | "personal"
  | "clinical"
  | "research"
  | "admin"
  | "public"
  | "utility";

export type RouteShellMode =
  | "standard"
  | "focus"
  | "immersive"
  | "public"
  | "contextual";

export type RouteArchetype =
  | "Hub"
  | "ListDetail"
  | "Workflow"
  | "Conversation"
  | "CommandCenter"
  | "Settings"
  | "Landing"
  | "Legal"
  | "Auth"
  | "Reader"
  | "Redirect";

export type RouteAccess = "public" | "authenticated" | "role_gated";

export interface RouteContract {
  routeId: string;
  path: string;
  workspace: RouteWorkspace;
  shellMode: RouteShellMode;
  archetype: RouteArchetype;
  access: RouteAccess;
  allowedRoles: UserRole[];
  isAlias: boolean;
  canonicalTarget?: string;
}

export const ROUTE_WORKSPACES: readonly RouteWorkspace[] = [
  "personal",
  "clinical",
  "research",
  "admin",
  "public",
  "utility",
] as const;

export const ROUTE_SHELL_MODES: readonly RouteShellMode[] = [
  "standard",
  "focus",
  "immersive",
  "public",
  "contextual",
] as const;

export const ROUTE_ARCHETYPES: readonly RouteArchetype[] = [
  "Hub",
  "ListDetail",
  "Workflow",
  "Conversation",
  "CommandCenter",
  "Settings",
  "Landing",
  "Legal",
  "Auth",
  "Reader",
  "Redirect",
] as const;

export const ROUTE_ACCESS_LEVELS: readonly RouteAccess[] = [
  "public",
  "authenticated",
  "role_gated",
] as const;

export const ALL_ROLES: readonly UserRole[] = [
  "normal",
  "researcher",
  "doctor",
  "admin",
] as const;

export const PROFESSIONAL_ROLES: readonly UserRole[] = [
  "researcher",
  "doctor",
  "admin",
] as const;

export const CLINICAL_ROLES: readonly UserRole[] = [
  "doctor",
  "admin",
] as const;

export const ADMIN_ROLES: readonly UserRole[] = ["admin"] as const;
