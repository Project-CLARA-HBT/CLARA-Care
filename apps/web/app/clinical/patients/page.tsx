"use client";

import PageShell from "@/components/ui/page-shell";
import PatientRoster from "@/components/clinical/patient-roster";
import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

export default function ClinicalPatientsPage() {
  const language = useUILanguage();

  return (
    <PageShell
      title={t(language, "clinical.patients.title")}
      description={t(language, "clinical.patients.subtitle")}
      variant="plain"
    >
      <PatientRoster />
    </PageShell>
  );
}
