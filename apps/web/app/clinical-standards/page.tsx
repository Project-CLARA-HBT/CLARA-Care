"use client";

import PageShell from "@/components/ui/page-shell";
import ClinicalStandards from "@/components/clinical/clinical-standards";
import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

export default function ClinicalStandardsRootPage() {
  const language = useUILanguage();

  return (
    <PageShell
      title={t(language, "clinical.standards.title")}
      description={t(language, "clinical.standards.subtitle")}
      variant="plain"
    >
      <ClinicalStandards />
    </PageShell>
  );
}
