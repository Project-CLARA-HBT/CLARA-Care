"use client";

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
import { isPublicRoute } from "@/lib/navigation.config";
import {
  clearOrganizationScopedClientState,
  getActiveOrganizationId,
  ORGANIZATION_CONTEXT_CHANGE_EVENT,
  setActiveOrganizationId,
  type OrganizationItem,
} from "@/lib/organization-context";
import { listOrganizations } from "@/lib/organization-api";
import { useSession } from "@/components/shell/session-boundary";

export interface OrganizationContextValue {
  organizations: OrganizationItem[];
  activeOrganization: OrganizationItem | null;
  activeOrganizationId: string | null;
  isLoading: boolean;
  isSwitching: boolean;
  error: string | null;
  switchOrganization: (orgId: string) => Promise<void>;
  refreshOrganizations: () => Promise<void>;
}

export const OrganizationContext = createContext<OrganizationContextValue | null>(null);

export interface OrganizationProviderProps {
  children: ReactNode;
  initialOrganizations?: OrganizationItem[];
  initialActiveOrgId?: string | null;
}

export function OrganizationProvider({
  children,
  initialOrganizations,
  initialActiveOrgId,
}: OrganizationProviderProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { isSessionChecked, isAuthenticated } = useSession();

  const [organizations, setOrganizations] = useState<OrganizationItem[]>(
    initialOrganizations ?? [],
  );
  const [activeOrgId, setActiveOrgId] = useState<string | null>(() => {
    if (initialActiveOrgId !== undefined) return initialActiveOrgId;
    return getActiveOrganizationId();
  });
  const [isLoading, setIsLoading] = useState(false);
  const [isSwitching, setIsSwitching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isPublic = isPublicRoute(pathname);

  const refreshOrganizations = useCallback(async () => {
    if (isPublic || !isSessionChecked || !isAuthenticated) {
      setOrganizations([]);
      setActiveOrgId(null);
      setError(null);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const items = await listOrganizations();
      setOrganizations(items);

      const storedId = getActiveOrganizationId();
      const matched = items.find((org) => org.id === storedId);

      if (matched) {
        setActiveOrgId(matched.id);
      } else if (items.length > 0) {
        // Default to first accessible organization
        const defaultId = items[0].id;
        setActiveOrgId(defaultId);
        setActiveOrganizationId(defaultId);
      } else {
        setActiveOrgId(null);
      }
    } catch (err: unknown) {
      // In guest or non-organization contexts, degrade gracefully
      setError(err instanceof Error ? err.message : "Failed to load organizations");
    } finally {
      setIsLoading(false);
    }
  }, [isPublic, isSessionChecked, isAuthenticated]);

  useEffect(() => {
    void refreshOrganizations();
  }, [refreshOrganizations]);

  // Synchronize with external context change events (e.g. cross-tab or interceptors)
  useEffect(() => {
    const handleContextChange = (event: Event) => {
      const customEvent = event as CustomEvent<{ previous: string | null; next: string | null }>;
      const nextId = customEvent.detail?.next ?? getActiveOrganizationId();
      setActiveOrgId(nextId);
    };

    if (typeof window !== "undefined") {
      window.addEventListener(ORGANIZATION_CONTEXT_CHANGE_EVENT, handleContextChange);
      return () => {
        window.removeEventListener(ORGANIZATION_CONTEXT_CHANGE_EVENT, handleContextChange);
      };
    }
  }, []);

  const switchOrganization = useCallback(
    async (orgId: string) => {
      if (!orgId || orgId === activeOrgId || isSwitching) return;

      setIsSwitching(true);
      try {
        // Enforce purge of tenant-scoped caches
        clearOrganizationScopedClientState();
        setActiveOrganizationId(orgId);
        setActiveOrgId(orgId);

        // Refresh router data to render under new tenant boundary
        router.refresh();
      } finally {
        setIsSwitching(false);
      }
    },
    [activeOrgId, isSwitching, router],
  );

  const activeOrganization = useMemo(() => {
    return organizations.find((org) => org.id === activeOrgId) ?? null;
  }, [organizations, activeOrgId]);

  const value = useMemo<OrganizationContextValue>(
    () => ({
      organizations,
      activeOrganization,
      activeOrganizationId: activeOrgId,
      isLoading,
      isSwitching,
      error,
      switchOrganization,
      refreshOrganizations,
    }),
    [
      organizations,
      activeOrganization,
      activeOrgId,
      isLoading,
      isSwitching,
      error,
      switchOrganization,
      refreshOrganizations,
    ],
  );

  return (
    <OrganizationContext.Provider value={value}>
      {children}
    </OrganizationContext.Provider>
  );
}

export function useOrganizationSafe(): OrganizationContextValue | null {
  return useContext(OrganizationContext);
}

export function useOrganization(): OrganizationContextValue {
  const context = useContext(OrganizationContext);
  if (!context) {
    throw new Error("useOrganization must be used within an OrganizationProvider");
  }
  return context;
}

export { useOrganization as useOrganizationContext };
export default OrganizationProvider;
