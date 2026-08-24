import type { UserRole } from "./navigation.access";

export type { UserRole };

export type RouteAccessCategory =
  | "public"
  | "personal"
  | "clinical"
  | "research"
  | "admin"
  | "utility";

export type CanonicalExperience =
  | "personal"
  | "clinical"
  | "research"
  | "admin"
  | "public"
  | "utility";

export type ShellMode =
  | "PUBLIC_MARKETING"
  | "PUBLIC_AUTH"
  | "PUBLIC_LEGAL"
  | "PUBLIC_SHARE"
  | "EXPLORE"
  | "FOCUS"
  | "IMMERSIVE"
  | "READ"
  | "READ_COMPOSE"
  | "DENSE"
  | "ADMIN_COMMAND"
  | "ROLE_ADAPTER"
  | "UTILITY_FOCUS"
  | "ALIAS_REDIRECT"
  | "ALIAS_CONTEXT";

export interface RouteLayoutContract {
  routeId: string;
  path: string;
  access: RouteAccessCategory;
  roles: UserRole[];
  canonicalExperience: CanonicalExperience;
  shellMode: ShellMode;
  layoutArchetype: string;
  targetPath?: string;
}
