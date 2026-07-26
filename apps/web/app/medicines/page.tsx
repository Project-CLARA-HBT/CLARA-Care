"use client";

import { Suspense, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import PageShell from "@/components/ui/page-shell";
import { Tabs, TabPanel, type TabItem } from "@/components/ui/tabs";
import MedicinesListTab from "./list-tab";
import MedicinesCabinetTab from "./cabinet-tab";
import MedicinesSafetyTab from "./safety-tab";

const TAB_ITEMS: TabItem[] = [
  { key: "list", label: "Thuốc của tôi", icon: "medication" },
  { key: "cabinet", label: "Tủ thuốc", icon: "inventory_2" },
  { key: "safety", label: "An toàn tương tác", icon: "labs" },
];

const DEFAULT_TAB = "list";

function isTabKey(value: string | null): value is "list" | "cabinet" | "safety" {
  return value === "list" || value === "cabinet" || value === "safety";
}

function MedicinesHub() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const requested = searchParams.get("tab");
  const active = isTabKey(requested) ? requested : DEFAULT_TAB;

  const onChange = useCallback(
    (key: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("tab", key);
      router.replace(`/medicines?${params.toString()}`);
    },
    [router, searchParams],
  );

  return (
    <PageShell
      variant="plain"
      title="Thuốc & an toàn tương tác"
      description="Quản lý thuốc đã xác nhận, tủ thuốc cá nhân và kiểm tra tương tác an toàn trong một nơi."
    >
      <div className="space-y-5">
        <Tabs
          idBase="medicines"
          items={TAB_ITEMS}
          active={active}
          onChange={onChange}
          ariaLabel="Khu vực thuốc và an toàn tương tác"
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
    </PageShell>
  );
}

export default function MedicinesPage() {
  return (
    <Suspense fallback={null}>
      <MedicinesHub />
    </Suspense>
  );
}
