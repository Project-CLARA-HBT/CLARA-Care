"use client";

import { Suspense, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { HubLayout } from "@/components/page/hub-layout";
import { Tabs, TabPanel, type TabItem } from "@/components/ui/tabs";
import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import MedicinesListTab from "./list-tab";
import MedicinesCabinetTab from "./cabinet-tab";
import MedicinesSafetyTab from "./safety-tab";

const DEFAULT_TAB = "list";

function isTabKey(value: string | null): value is "list" | "cabinet" | "safety" {
  return value === "list" || value === "cabinet" || value === "safety";
}

function MedicinesHub() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const language = useUILanguage();
  const requested = searchParams.get("tab");
  const active = isTabKey(requested) ? requested : DEFAULT_TAB;
  const tabItems: TabItem[] = [
    {
      key: "list",
      label: t(language, "medicines.tab.list"),
      icon: "medication",
    },
    {
      key: "cabinet",
      label: t(language, "medicines.tab.cabinet"),
      icon: "inventory_2",
    },
    {
      key: "safety",
      label: t(language, "medicines.tab.safety"),
      icon: "labs",
    },
  ];

  const onChange = useCallback(
    (key: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("tab", key);
      router.replace(`/medicines?${params.toString()}`);
    },
    [router, searchParams],
  );

  return (
    <HubLayout
      workspace="personal"
      data-workspace="personal"
      title={t(language, "medicines.title")}
      description={t(language, "medicines.description")}
    >
      <div className="space-y-5" data-testid="medicines-workspace">
        <Tabs
          idBase="medicines"
          items={tabItems}
          active={active}
          onChange={onChange}
          ariaLabel={t(language, "medicines.tabs")}
        />

        <TabPanel idBase="medicines" tabKey="list" active={active}>
          <MedicinesListTab />
        </TabPanel>
        <TabPanel idBase="medicines" tabKey="cabinet" active={active}>
          <MedicinesCabinetTab />
        </TabPanel>
        <TabPanel idBase="medicines" tabKey="safety" active={active}>
          <MedicinesSafetyTab />
        </TabPanel>
      </div>
    </HubLayout>
  );
}

export default function MedicinesPage() {
  return (
    <Suspense fallback={null}>
      <MedicinesHub />
    </Suspense>
  );
}
