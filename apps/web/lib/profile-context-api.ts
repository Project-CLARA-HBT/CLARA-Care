import api from "@/lib/http-client";
import type { ProfileActivation, ProfileContext } from "@/lib/profile-context";

export async function getProfileContext(): Promise<ProfileContext> {
  return (await api.get<ProfileContext>("/profiles/context")).data;
}

export async function activateOwnedProfile(profileId: string): Promise<ProfileActivation> {
  return (
    await api.post<ProfileActivation>(`/profiles/${encodeURIComponent(profileId)}/activate`)
  ).data;
}
