"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { usePathname } from "next/navigation";
import {
  getPermittedWorkspaces,
  getStoredWorkspace,
  isValidAdminPreviewPersona,
  isValidWorkspace,
  reconcileWorkspaceWithRoute,
  saveStoredWorkspace,
} from "./workspace.config";
import {
  getStoredAdminPreviewMode,
  setStoredAdminPreviewMode,
} from "@/lib/auth-store";
import {
  WORKSPACE_STORAGE_KEY,
  type AdminPreviewPersona,
  type WorkspaceContextValue,
  type WorkspaceId,
  type WorkspaceProviderProps,
} from "./workspace.contract";

export const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({
  children,
  serverRole = "normal",
  initialWorkspace,
  initialAdminPreviewPersona,
  pathname: propPathname,
}: WorkspaceProviderProps) {
  const hookPathname = usePathname();
  const currentPathname = propPathname ?? hookPathname ?? "";

  const permittedWorkspaces = useMemo(
    () => getPermittedWorkspaces(serverRole),
    [serverRole],
  );

  const [activeWorkspace, setActiveWorkspaceState] = useState<WorkspaceId>(() => {
    if (initialWorkspace && permittedWorkspaces.includes(initialWorkspace)) {
      return initialWorkspace;
    }
    const stored = getStoredWorkspace();
    return reconcileWorkspaceWithRoute({
      pathname: currentPathname,
      serverRole,
      currentWorkspace: stored,
      permittedWorkspaces,
    });
  });

  const [adminPreviewPersona, setAdminPreviewPersonaState] =
    useState<AdminPreviewPersona | null>(() => {
      if (serverRole !== "admin") return null;
      if (
        initialAdminPreviewPersona !== undefined &&
        (initialAdminPreviewPersona === null ||
          isValidAdminPreviewPersona(initialAdminPreviewPersona))
      ) {
        return initialAdminPreviewPersona;
      }
      const stored = getStoredAdminPreviewMode();
      return isValidAdminPreviewPersona(stored) ? stored : null;
    });

  // Reconcile active workspace when pathname, role, or permitted workspaces change
  useEffect(() => {
    const nextWorkspace = reconcileWorkspaceWithRoute({
      pathname: currentPathname,
      serverRole,
      currentWorkspace: activeWorkspace,
      permittedWorkspaces,
    });

    if (nextWorkspace !== activeWorkspace) {
      setActiveWorkspaceState(nextWorkspace);
      saveStoredWorkspace(nextWorkspace);
    }

    if (serverRole !== "admin" && adminPreviewPersona !== null) {
      setAdminPreviewPersonaState(null);
      setStoredAdminPreviewMode(null);
    }
  }, [
    currentPathname,
    serverRole,
    permittedWorkspaces,
    activeWorkspace,
    adminPreviewPersona,
  ]);

  // Synchronize across tabs on storage change
  useEffect(() => {
    if (typeof window === "undefined") return;
    const onStorageChange = (e: StorageEvent) => {
      if (e.key === WORKSPACE_STORAGE_KEY && isValidWorkspace(e.newValue)) {
        if (permittedWorkspaces.includes(e.newValue)) {
          setActiveWorkspaceState(e.newValue);
        }
      }
    };
    window.addEventListener("storage", onStorageChange);
    return () => window.removeEventListener("storage", onStorageChange);
  }, [permittedWorkspaces]);

  const setActiveWorkspace = useCallback(
    (id: WorkspaceId) => {
      if (!isValidWorkspace(id)) return;
      if (!permittedWorkspaces.includes(id)) {
        return;
      }
      setActiveWorkspaceState(id);
      saveStoredWorkspace(id);
    },
    [permittedWorkspaces],
  );

  const setAdminPreviewPersona = useCallback(
    (persona: AdminPreviewPersona | null) => {
      if (serverRole !== "admin") {
        return;
      }
      const validPersona =
        persona && isValidAdminPreviewPersona(persona) ? persona : null;
      setAdminPreviewPersonaState(validPersona);
      setStoredAdminPreviewMode(validPersona);
    },
    [serverRole],
  );

  const value = useMemo<WorkspaceContextValue>(
    () => ({
      activeWorkspace,
      permittedWorkspaces,
      setActiveWorkspace,
      adminPreviewPersona,
      setAdminPreviewPersona,
    }),
    [
      activeWorkspace,
      permittedWorkspaces,
      setActiveWorkspace,
      adminPreviewPersona,
      setAdminPreviewPersona,
    ],
  );

  return (
    <WorkspaceContext.Provider value={value}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace(): WorkspaceContextValue {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error("useWorkspace must be used within a WorkspaceProvider");
  }
  return context;
}

export default WorkspaceProvider;
