"use client";

import { Suspense, useCallback, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { HealthPageHeader } from "@/components/consumer/health-page-header";
import { Tabs, TabPanel, type TabItem } from "@/components/ui/tabs";
import { useUILanguage } from "@/lib/use-ui-language";
import { t } from "@/lib/i18n/catalog";
import MedicinesListTab from "@/app/medicines/list-tab";
import MedicinesCabinetTab from "@/app/medicines/cabinet-tab";
import MedicinesSafetyTab from "@/app/medicines/safety-tab";

const DEFAULT_TAB = "list";

function isTabKey(value: string | null): value is "list" | "cabinet" | "safety" {
  return value === "list" || value === "cabinet" || value === "safety";
}

function ConsumerMedicationsHub() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const uiLanguage = useUILanguage();
  const isEn = uiLanguage === "en";

  const requested = searchParams.get("tab");
  const active = isTabKey(requested) ? requested : DEFAULT_TAB;

  const tabItems: TabItem[] = [
    {
      key: "list",
      label: isEn ? "Active Courses" : "Đơn thuốc & Phác đồ",
      icon: "medication",
    },
    {
      key: "cabinet",
      label: isEn ? "Medicine Cabinet" : "Tủ thuốc gia đình",
      icon: "inventory_2",
    },
    {
      key: "safety",
      label: isEn ? "Safety & Interactions" : "An toàn & Tương tác",
      icon: "labs",
    },
  ];

  const onChange = useCallback(
    (key: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("tab", key);
      router.replace(`/health/medications?${params.toString()}`);
    },
    [router, searchParams],
  );

  return (
    <div
      className="mx-auto max-w-5xl space-y-6 pb-12"
      data-testid="consumer-medications-page"
    >
      <HealthPageHeader
        title={isEn ? "Medication Hub" : "Thuốc & Tủ thuốc"}
        subtitle={
          isEn
            ? "Unified medication management: active courses, family cabinet items, and verified safety interaction checks."
            : "Trung tâm quản lý thuốc: đơn thuốc đã xác nhận, tủ thuốc gia đình và đối chiếu an toàn tương tác."
        }
        backHref="/health"
        backLabel={isEn ? "Back to Health" : "Quay lại Sức khỏe"}
        locale={uiLanguage}
        primaryAction={{
          label: isEn ? "+ Add Medicine" : "+ Thêm thuốc",
          href: "/medicines/add",
          icon: "plus",
        }}
        secondaryAction={{
          label: isEn ? "Scan Prescription" : "Quét toa thuốc",
          href: "/phr",
          icon: "scan",
        }}
      />

      <div className="space-y-5">
        <Tabs
          idBase="health-medications"
          items={tabItems}
          active={active}
          onChange={onChange}
          ariaLabel={isEn ? "Medication sections" : "Các phân hệ quản lý thuốc"}
        />

        <TabPanel idBase="health-medications" tabKey="list" active={active}>
          <MedicinesListTab />
        </TabPanel>
        <TabPanel idBase="health-medications" tabKey="cabinet" active={active}>
          <MedicinesCabinetTab />
        </TabPanel>
        <TabPanel idBase="health-medications" tabKey="safety" active={active}>
          <MedicinesSafetyTab />
        </TabPanel>
      </div>
    </div>
  );
}

export default function ConsumerMedicationsPage() {
  return (
    <Suspense fallback={null}>
      <ConsumerMedicationsHub />
    </Suspense>
  );
}
