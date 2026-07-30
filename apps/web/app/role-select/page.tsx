"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/http-client";
import { SurfaceCard } from "@/components/ui/surface";
import {
  getRoleHomePath,
  type UserRole,
} from "@/lib/navigation.config";
import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

/**
 * Compatibility redirect for old bookmarks.
 *
 * Roles are assigned by the authenticated server account and are never
 * switchable client-side. Keeping this route as a redirect avoids breaking old
 * links while removing the misleading privilege-like UI.
 */
export default function LegacyRoleSelectionRedirect() {
  const language = useUILanguage();
  const router = useRouter();

  useEffect(() => {
    let active = true;
    const redirectToAuthoritativeHome = async () => {
      try {
        const response = await api.get<{ role?: UserRole }>("/auth/me", {
          timeout: 15000,
        });
        if (!active) return;
        router.replace(getRoleHomePath(response.data?.role ?? "normal"));
      } catch {
        if (active) router.replace("/login");
      }
    };
    void redirectToAuthoritativeHome();
    return () => {
      active = false;
    };
  }, [router]);

  return (
    <main className="mx-auto flex min-h-[100dvh] max-w-lg items-center justify-center px-4 py-12 sm:px-6">
      <SurfaceCard className="w-full p-7 text-center sm:p-9">
        <div role="status">
          <span
            className="material-symbols-outlined animate-pulse text-3xl text-[var(--brand-600)]"
            aria-hidden="true"
          >
            shield_person
          </span>
          <h1 className="mt-3 text-lg font-semibold text-[var(--text-primary)]">
            {t(language, "roleRedirect.title")}
          </h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            {t(language, "roleRedirect.description")}
          </p>
        </div>
      </SurfaceCard>
    </main>
  );
}
