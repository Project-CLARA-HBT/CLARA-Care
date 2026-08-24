"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import PageShell from "@/components/ui/page-shell";
import ClinicalOverview, { ClinicalOverviewLaunchpad } from "@/components/clinical/clinical-overview";
import ResearchOverview, { ResearchOverviewLaunchpad } from "@/components/research/research-overview";
import { getRole, type UserRole } from "@/lib/auth-store";
import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

export default function DashboardPage() {
  const language = useUILanguage();
  const router = useRouter();
  const [role, setRole] = useState<UserRole>(() => getRole() || "normal");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const currentRole = getRole();
    setRole(currentRole);
    setMounted(true);

    if (currentRole === "admin") {
      router.replace("/admin/overview");
    } else if (currentRole === "normal") {
      router.replace("/today");
    }
  }, [router]);

  if (!mounted) {
    if (role === "doctor") {
      return (
        <PageShell
          title={t(language, "clinical.overview.title")}
          description={t(language, "clinical.overview.subtitle")}
          variant="plain"
        >
        <ClinicalOverview />
      </PageShell>
    );
  }
  if (role === "researcher") {
    return (
      <PageShell
        title={t(language, "navigation.item.research.title")}
        description={t(language, "navigation.item.research.subtitle")}
        variant="plain"
      >
        <ResearchOverview />
      </PageShell>
    );
  }
  return null;
}

if (role === "admin") {
  return (
    <div className="flex min-h-[40vh] items-center justify-center text-sm text-[var(--text-muted)]" role="status">
      {language === "vi" ? "Đang chuyển hướng đến Trung tâm Quản trị…" : "Redirecting to Admin Overview…"}
    </div>
  );
}

if (role === "normal") {
  return (
    <div className="flex min-h-[40vh] items-center justify-center text-sm text-[var(--text-muted)]" role="status">
      {language === "vi" ? "Đang chuyển hướng đến Trang hôm nay…" : "Redirecting to Today…"}
    </div>
  );
}

if (role === "doctor") {
  return (
    <PageShell
      title={t(language, "clinical.overview.title")}
      description={t(language, "clinical.overview.subtitle")}
      variant="plain"
    >
      <ClinicalOverview />
    </PageShell>
  );
}

if (role === "researcher") {
  return (
    <PageShell
      title={t(language, "navigation.item.research.title")}
      description={t(language, "navigation.item.research.subtitle")}
      variant="plain"
    >
      <ResearchOverview />
      </PageShell>
    );
  }

  return null;
}
