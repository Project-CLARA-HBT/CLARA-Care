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
  clearProfileScopedClientState,
  getActiveProfileId,
  setActiveProfileId,
  PROFILE_CONTEXT_CHANGE_EVENT,
  type ProfileContext,
  type ProfileContextProfile,
} from "@/lib/profile-context";
import {
  activateOwnedProfile,
  getProfileContext,
} from "@/lib/profile-context-api";
import { listFamilyNotifications } from "@/lib/visit-family";
import { useSession } from "./session-boundary";

export type ProfileContextBoundaryValue = {
  profileContext: ProfileContext | null;
  activeProfile: ProfileContextProfile | null;
  activeProfileId: string | null;
  isProfileChanging: boolean;
  familyNotificationCount: number;
  handleProfileChange: (profileId: string) => Promise<void>;
  refreshProfileContext: () => Promise<void>;
};

export const ProfileBoundaryContext =
  createContext<ProfileContextBoundaryValue | null>(null);

export function ProfileBoundary({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { isSessionChecked } = useSession();

  const [profileContext, setProfileContext] = useState<ProfileContext | null>(
    null,
  );
  const [isProfileChanging, setIsProfileChanging] = useState(false);
  const [familyNotificationCount, setFamilyNotificationCount] = useState(0);

  const isPublic = isPublicRoute(pathname);

  const refreshProfileContext = useCallback(async () => {
    if (isPublic || !isSessionChecked) {
      setProfileContext(null);
      setFamilyNotificationCount(0);
      return;
    }
    try {
      const [context, notifications] = await Promise.all([
        getProfileContext(),
        listFamilyNotifications().catch(() => []),
      ]);

      if (
        context.reset_required ||
        context.active_profile_id !== getActiveProfileId()
      ) {
        setActiveProfileId(context.active_profile_id);
      }
      setProfileContext(context);
      setFamilyNotificationCount(notifications.length);
    } catch {
      setProfileContext(null);
      setFamilyNotificationCount(0);
    }
  }, [isPublic, isSessionChecked]);

  useEffect(() => {
    void refreshProfileContext();
  }, [refreshProfileContext]);

  useEffect(() => {
    const handleContextChange = () => {
      void refreshProfileContext();
    };
    if (typeof window !== "undefined") {
      window.addEventListener(
        PROFILE_CONTEXT_CHANGE_EVENT,
        handleContextChange,
      );
      return () => {
        window.removeEventListener(
          PROFILE_CONTEXT_CHANGE_EVENT,
          handleContextChange,
        );
      };
    }
  }, [refreshProfileContext]);

  const handleProfileChange = useCallback(
    async (profileId: string) => {
      if (
        !profileId ||
        profileId === profileContext?.active_profile_id ||
        isProfileChanging
      ) {
        return;
      }
      const target = profileContext?.profiles.find(
        (profile) => profile.id === profileId,
      );
      if (!target || target.kind !== "self") return;

      setIsProfileChanging(true);
      try {
        const activation = await activateOwnedProfile(profileId);
        // Clear caches and store new active profile
        clearProfileScopedClientState();
        setActiveProfileId(activation.active_profile_id);
        const nextContext = await getProfileContext();
        setProfileContext(nextContext);
        router.refresh();
      } finally {
        setIsProfileChanging(false);
      }
    },
    [profileContext, isProfileChanging, router],
  );

  const activeProfile = useMemo(
    () =>
      profileContext?.profiles.find(
        (profile) => profile.id === profileContext.active_profile_id,
      ) ?? null,
    [profileContext],
  );

  const value = useMemo<ProfileContextBoundaryValue>(
    () => ({
      profileContext,
      activeProfile,
      activeProfileId: profileContext?.active_profile_id ?? null,
      isProfileChanging,
      familyNotificationCount,
      handleProfileChange,
      refreshProfileContext,
    }),
    [
      profileContext,
      activeProfile,
      isProfileChanging,
      familyNotificationCount,
      handleProfileChange,
      refreshProfileContext,
    ],
  );

  return (
    <ProfileBoundaryContext.Provider value={value}>
      {children}
    </ProfileBoundaryContext.Provider>
  );
}

export function useProfileBoundary(): ProfileContextBoundaryValue {
  const context = useContext(ProfileBoundaryContext);
  if (!context) {
    throw new Error(
      "useProfileBoundary must be used within a ProfileBoundary",
    );
  }
  return context;
}

export const ProfileProvider = ProfileBoundary;
export { useProfileBoundary as useProfileContext, useProfileBoundary as useProfile };
export default ProfileBoundary;
