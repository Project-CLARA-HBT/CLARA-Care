import type { ReactNode } from "react";

export type WorkspaceId = "personal" | "clinical" | "research" | "admin";

export type AdminPreviewPersona = "clinical" | "research" | "personal";

export type UserRole = "normal" | "doctor" | "researcher" | "admin";

export const WORKSPACE_STORAGE_KEY = "clara_workspace_v2";
export const WORKSPACE_COOKIE_NAME = "clara_workspace_v2";
export const WORKSPACE_CHANGE_EVENT = "clara:workspace-change";

export const ALL_WORKSPACES: readonly WorkspaceId[] = [
  "personal",
  "clinical",
  "research",
  "admin",
] as const;

export const ALL_ADMIN_PREVIEW_PERSONAS: readonly AdminPreviewPersona[] = [
  "clinical",
  "research",
  "personal",
] as const;

export interface WorkspaceContextValue {
  activeWorkspace: WorkspaceId;
  permittedWorkspaces: WorkspaceId[];
  setActiveWorkspace: (id: WorkspaceId) => void;
  adminPreviewPersona: AdminPreviewPersona | null;
  setAdminPreviewPersona: (persona: AdminPreviewPersona | null) => void;
}

export interface WorkspaceProviderProps {
  children: ReactNode;
  serverRole?: UserRole;
  initialWorkspace?: WorkspaceId;
  initialAdminPreviewPersona?: AdminPreviewPersona | null;
  pathname?: string;
}
