"use client";

import PageShell from "@/components/ui/page-shell";
import ClinicalOverviewLaunchpad from "@/components/clinical/clinical-overview-launchpad";
import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

export default function ClinicalOverviewSubroutePage() {
  const language = useUILanguage();

  return (
    <PageShell
      title={t(language, "clinical.overview.title")}
      description={t(language, "clinical.overview.subtitle")}
      variant="plain"
    >
      <ClinicalOverviewLaunchpad />
    </PageShell>
  );
}
