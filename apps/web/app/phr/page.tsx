"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import PageShell from "@/components/ui/page-shell";
import Button from "@/components/ui/button";
import Icon, { type IconName } from "@/components/ui/icon";
import { Badge } from "@/components/ui/badge";
import { LocalRail, type LocalRailItem } from "@/components/ui/local-rail";
import { useShellMode } from "@/components/shell/shell-mode-provider";
import {
  DEFAULT_PHR_CAPABILITIES,
  getPhrCapabilities,
  getPhrRecord,
  type PhrCapabilityFlags,
  type PhrRecord,
} from "@/lib/phr";
import {
  getStoredUILanguage,
  onUILanguageChange,
  type UILanguage,
} from "@/lib/ui-language";
import { formatLocaleDate, t, type UITranslationKey } from "@/lib/i18n/catalog";
import RecordSectionEditor from "@/components/phr/record-section-editor";
import {
  EMPTY_RECORD,
  getPhrText,
  normalizeRecord,
  type PhrText,
} from "@/components/phr/phr-shared";

// Explicit references required for i18n contract audit (scripts/check-i18n.mjs)
const _I18N_AUDIT_KEYS = [
  "phr.title",
  "phr.disclaimer",
  "phr.hub.identity.title",
  "phr.completeness.class.patientDemographics",
  "phr.error.sectionNotFound.title",
] as const satisfies readonly UITranslationKey[];

type HubItem = {
  href: string;
  icon: IconName;
  title: string;
  description: string;
  complete?: boolean;
  valueSummary?: string;
};

export default function PhrPage() {
  const pathname = usePathname();
  const { setMode } = useShellMode();

  useEffect(() => {
    setMode("focus");
  }, [setMode]);

  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");
  const [record, setRecord] = useState<PhrRecord>(EMPTY_RECORD);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");
  const [capabilities, setCapabilities] = useState<PhrCapabilityFlags>(
    DEFAULT_PHR_CAPABILITIES,
  );
  const [railCollapsed, setRailCollapsed] = useState(false);

  const text: PhrText = useMemo(() => getPhrText(uiLanguage), [uiLanguage]);
  const copy = useCallback(
    (key: UITranslationKey) => t(uiLanguage, key),
    [uiLanguage],
  );

  const isHub = !pathname || pathname === "/phr" || pathname === "/phr/";

  useEffect(() => {
    setUiLanguage(getStoredUILanguage());
    return onUILanguageChange(setUiLanguage);
  }, []);

  useEffect(() => {
    let mounted = true;
    getPhrCapabilities().then((flags) => {
      if (mounted) setCapabilities(flags);
    });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    async function run() {
      setLoading(true);
      setError("");
      try {
        const data = await getPhrRecord();
        if (!mounted) return;
        setRecord(normalizeRecord(data));
      } catch {
        if (!mounted) return;
        setError(text.loadError);
      } finally {
        if (mounted) setLoading(false);
      }
    }
    run();
    return () => {
      mounted = false;
    };
  }, [text.loadError]);

  // If accessed directly with a subpath (e.g. in unit tests rendering PhrPage with mock pathname)
  if (!isHub) {
    const sectionCandidate = pathname.replace(/^\/phr\/?/, "").split("/")[0];
    return <RecordSectionEditor section={sectionCandidate} />;
  }

  const sections: HubItem[] = [
    {
      href: "/phr/identity",
      icon: "user-card",
      title: copy("phr.hub.identity.title"),
      description: copy("phr.hub.identity.description"),
      complete: Boolean(record.full_name.trim() && record.date_of_birth),
      valueSummary: record.full_name
        ? `${record.full_name}${record.blood_type ? ` · ${record.blood_type}` : ""}`
        : undefined,
    },
    {
      href: "/phr/body",
      icon: "body",
      title: copy("phr.hub.body.title"),
      description: copy("phr.hub.body.description"),
      complete: record.height_cm !== null && record.weight_kg !== null,
      valueSummary:
        record.height_cm && record.weight_kg
          ? `${record.height_cm}cm · ${record.weight_kg}kg · BMI ${(record.weight_kg / ((record.height_cm / 100) ** 2)).toFixed(1)}`
          : undefined,
    },
    {
      href: "/phr/contact",
      icon: "contact",
      title: copy("phr.hub.contact.title"),
      description: copy("phr.hub.contact.description"),
      complete: Boolean(
        record.phone.trim() || record.emergency_contact_phone.trim(),
      ),
      valueSummary: record.phone ? record.phone : undefined,
    },
    {
      href: "/phr/allergies",
      icon: "warning",
      title: text.allergies,
      description: copy("phr.hub.allergies.description"),
      complete:
        record.allergies.length > 0 || record.allergy_status === "none_known",
      valueSummary:
        record.allergies.length > 0
          ? `${record.allergies.length} dị ứng`
          : record.allergy_status === "none_known"
            ? "Không có dị ứng"
            : undefined,
    },
    {
      href: "/phr/conditions",
      icon: "clinical-notes",
      title: text.conditions,
      description: copy("phr.hub.conditions.description"),
      complete: record.conditions.length > 0,
      valueSummary:
        record.conditions.length > 0
          ? `${record.conditions.length} bệnh nền`
          : undefined,
    },
    {
      href: "/phr/medications",
      icon: "medication",
      title: text.medications,
      description: copy("phr.hub.medications.description"),
      complete: record.medications.some((item) => item.is_current),
      valueSummary:
        record.medications.filter((m) => m.is_current).length > 0
          ? `${record.medications.filter((m) => m.is_current).length} thuốc đang dùng`
          : undefined,
    },
  ];

  const tools: HubItem[] = [
    capabilities.completeness_meter
      ? {
          href: "/phr/status",
          icon: "progress" as const,
          title: text.completenessTitle,
          description: copy("phr.hub.status.description"),
        }
      : null,
    capabilities.ocr_import
      ? {
          href: "/phr/ocr",
          icon: "scan" as const,
          title: copy("phr.hub.ocr.title"),
          description: copy("phr.hub.ocr.description"),
        }
      : null,
    capabilities.export
      ? {
          href: "/phr/export",
          icon: "download",
          title: copy("phr.hub.export.title"),
          description: copy("phr.hub.export.description"),
        }
      : null,
    capabilities.sharing
      ? {
          href: "/phr/sharing",
          icon: "share",
          title: copy("phr.hub.sharing.title"),
          description: copy("phr.hub.sharing.description"),
        }
      : null,
    capabilities.enhanced
      ? {
          href: "/phr/emergency-card",
          icon: "emergency",
          title: copy("phr.hub.emergencyCard.title"),
          description: copy("phr.hub.emergencyCard.description"),
        }
      : null,
    capabilities.reminders
      ? {
          href: "/phr/reminders",
          icon: "notifications" as const,
          title: copy("phr.hub.reminders.title"),
          description: copy("phr.hub.reminders.description"),
        }
      : null,
  ].filter((tool): tool is HubItem => tool !== null);

  const completed = sections.filter((item) => item.complete).length;
  const nextSection = sections.find((item) => !item.complete) ?? sections[0];

  const mobileSections: HubItem[] = [
    {
      href: "/phr/identity",
      icon: "user-card",
      title: copy("phr.hub.identity.title"),
      description: "",
      complete: Boolean(record.full_name.trim() && record.date_of_birth),
    },
    {
      href: "/phr/body",
      icon: "body",
      title: copy("phr.hub.body.title"),
      description: "",
      complete: record.height_cm !== null && record.weight_kg !== null,
    },
    {
      href: "/phr/conditions",
      icon: "clinical-notes",
      title: text.mobileHistory,
      description: "",
      complete:
        record.conditions.length > 0 ||
        record.medications.some((item) => item.is_current),
    },
    {
      href: "/phr/allergies",
      icon: "warning",
      title: text.allergies,
      description: "",
      complete:
        record.allergies.length > 0 || record.allergy_status === "none_known",
    },
  ];

  const mobileCompleted = mobileSections.filter((item) => item.complete).length;
  const mobilePercent = Math.round(
    (mobileCompleted / mobileSections.length) * 100,
  );
  const mobileNext =
    mobileSections.find((item) => !item.complete) ?? mobileSections[0];

  const railItems: LocalRailItem[] = [
    {
      key: "overview",
      label: "Tổng quan",
      icon: "dashboard",
      href: "/phr",
    },
    {
      key: "identity",
      label: copy("phr.hub.identity.title"),
      icon: "user-card",
      href: "/phr/identity",
      badge: Boolean(record.full_name && record.date_of_birth) ? "✓" : undefined,
    },
    {
      key: "body",
      label: copy("phr.hub.body.title"),
      icon: "body",
      href: "/phr/body",
      badge: record.height_cm && record.weight_kg ? "✓" : undefined,
    },
    {
      key: "contact",
      label: copy("phr.hub.contact.title"),
      icon: "contact",
      href: "/phr/contact",
      badge: record.phone ? "✓" : undefined,
    },
    {
      key: "allergies",
      label: text.allergies,
      icon: "warning",
      href: "/phr/allergies",
      badge:
        record.allergies.length > 0
          ? record.allergies.length
          : record.allergy_status === "none_known"
            ? "0"
            : undefined,
    },
    {
      key: "conditions",
      label: text.conditions,
      icon: "clinical-notes",
      href: "/phr/conditions",
      badge:
        record.conditions.length > 0 ? record.conditions.length : undefined,
    },
    {
      key: "medications",
      label: text.medications,
      icon: "medication",
      href: "/phr/medications",
      badge:
        record.medications.filter((m) => m.is_current).length > 0
          ? record.medications.filter((m) => m.is_current).length
          : undefined,
    },
    ...(capabilities.ocr_import
      ? [
          {
            key: "ocr",
            label: copy("phr.hub.ocr.title"),
            icon: "scan",
            href: "/phr/ocr",
          },
        ]
      : []),
  ];

  const renderSectionRows = (items: HubItem[]) =>
    items.map((item) => (
      <Button
        key={item.href}
        as="link"
        href={item.href}
        variant="secondary"
        className="group relative h-auto min-h-[76px] w-full justify-start whitespace-normal p-4 text-left transition hover:border-[color:var(--brand-500)]/40 hover:bg-[var(--surface-muted)]"
      >
        <span className="flex w-full items-center gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-[var(--radius-lg)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
            <Icon name={item.icon} size={21} />
          </span>
          <span className="min-w-0 flex-1">
            <span className="flex items-center gap-2">
              <span className="block text-sm font-bold text-[var(--text-primary)]">
                {item.title}
              </span>
              {item.valueSummary ? (
                <span className="text-xs text-[var(--text-secondary)] font-normal truncate">
                  · {item.valueSummary}
                </span>
              ) : null}
            </span>
            <span className="mt-1 block text-[13px] font-normal leading-5 text-[var(--text-secondary)]">
              {item.description}
            </span>
          </span>
          <span
            className={`shrink-0 text-xs font-semibold ${
              item.complete
                ? "text-[var(--status-ok-text)]"
                : "text-[var(--text-muted)]"
            }`}
          >
            {item.complete
              ? copy("phr.hub.status.complete")
              : copy("phr.hub.status.incomplete")}
          </span>
          <Icon
            name="arrow-right"
            size={16}
            className="text-[var(--text-muted)] transition group-hover:translate-x-0.5 group-hover:text-[var(--text-brand)]"
          />
        </span>
      </Button>
    ));

  return (
    <PageShell
      variant="plain"
      title={text.title}
      description={text.description}
    >
      {/* Mobile Layout */}
      <div className="space-y-5 md:hidden">
        {error ? (
          <p
            role="alert"
            className="rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 py-3 text-sm text-[var(--status-danger-text)]"
          >
            {error}
          </p>
        ) : null}

        <section aria-label={copy("phr.hub.progress.label")}>
          <div className="flex items-center gap-4">
            <div
              className="h-3 flex-1 overflow-hidden rounded-full bg-[var(--surface-muted)]"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={mobilePercent}
              aria-label={copy("phr.hub.progress.label")}
            >
              <div
                className="h-full rounded-full bg-[var(--brand-500)]"
                style={{ width: `${mobilePercent}%` }}
              />
            </div>
            <span className="text-lg font-bold text-[var(--text-primary)]">
              {mobilePercent}%
            </span>
          </div>
          <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
            {text.mobileProgress}
          </p>
        </section>

        <section
          className="space-y-4"
          aria-label={copy("phr.hub.sections.record")}
        >
          {mobileSections.map((item) => (
            <Button
              key={item.href}
              as="link"
              href={item.href}
              variant="secondary"
              className="h-auto min-h-[96px] w-full justify-start whitespace-normal rounded-[var(--radius-xl)] p-5 text-left"
            >
              <span className="flex w-full items-center gap-4">
                <span
                  className={`grid h-12 w-12 shrink-0 place-items-center rounded-full ${
                    item.complete
                      ? "bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                      : "bg-[var(--surface-muted)] text-[var(--text-muted)]"
                  }`}
                >
                  <Icon name={item.icon} size={25} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-xl font-semibold text-[var(--text-primary)]">
                    {item.title}
                  </span>
                  <span
                    className={`mt-1 block text-sm font-semibold ${
                      item.complete
                        ? "text-[var(--status-ok-text)]"
                        : "text-[var(--status-warn-text)]"
                    }`}
                  >
                    {item.complete
                      ? copy("phr.hub.status.complete")
                      : copy("phr.hub.status.incomplete")}
                  </span>
                </span>
                <Icon
                  name="arrow-right"
                  size={22}
                  className="text-[var(--text-secondary)]"
                />
              </span>
            </Button>
          ))}
        </section>

        {!loading ? (
          <Button
            as="link"
            href={mobileNext.href}
            icon="arrow_forward"
            iconTrailing
            className="w-full justify-center py-4 text-base"
          >
            {copy("phr.hub.progress.continue")}
          </Button>
        ) : null}
      </div>

      {/* Desktop Layout with LocalRail + Health Record Workbench Canvas */}
      <div className="hidden space-y-5 md:block">
        {error ? (
          <p
            role="alert"
            className="rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 py-3 text-sm text-[var(--status-danger-text)]"
          >
            {error}
          </p>
        ) : null}

        {/* Top Record Summary Canvas */}
        <section
          className="chrome-panel rounded-[var(--radius-xl)] p-5 sm:p-6"
          aria-label={copy("phr.hub.progress.label")}
        >
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Badge tone="brand">
                  {record.full_name || text.profile}
                </Badge>
                {record.blood_type ? (
                  <Badge tone="neutral">Nhóm máu {record.blood_type}</Badge>
                ) : null}
                {record.updated_at ? (
                  <span className="text-xs text-[var(--text-secondary)]">
                    {text.updatedAt}:{" "}
                    {formatLocaleDate(uiLanguage, record.updated_at, {
                      dateStyle: "medium",
                    })}
                  </span>
                ) : null}
              </div>
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
                {copy("phr.hub.progress.eyebrow")}
              </p>
              <h2 className="text-xl font-semibold text-[var(--text-primary)]">
                {t(uiLanguage, "phr.hub.progress.title", {
                  completed,
                  total: sections.length,
                })}
              </h2>
              <p className="max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
                {copy("phr.hub.progress.description")}
              </p>
            </div>
            {!loading ? (
              <Button
                as="link"
                href={nextSection.href}
                icon="arrow_forward"
                iconTrailing
              >
                {copy("phr.hub.progress.continue")}
              </Button>
            ) : null}
          </div>

          {/* Progress bar */}
          <div
            className="mt-5 grid grid-cols-6 gap-2"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={sections.length}
            aria-valuenow={completed}
            aria-label={copy("phr.hub.progress.label")}
          >
            {sections.map((item) => (
              <span
                key={item.href}
                className={`h-2 rounded-full transition-all ${
                  item.complete
                    ? "bg-[var(--brand-500)]"
                    : "bg-[var(--surface-muted)]"
                }`}
              />
            ))}
          </div>
        </section>

        {/* Workbench Layout: LocalRail side navigation + Canvas */}
        <div className="flex gap-6 items-start">
          <aside className="shrink-0 sticky top-20 hidden lg:block">
            <LocalRail
              items={railItems}
              activeKey="overview"
              collapsed={railCollapsed}
              onToggleCollapse={() => setRailCollapsed((prev) => !prev)}
              density="compact"
              ariaLabel="Thanh điều hướng hồ sơ sức khỏe"
            />
          </aside>

          <div className="min-w-0 flex-1 space-y-6">
            <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
              {/* Main Section Rows */}
              <div
                className="space-y-6"
                aria-label={copy("phr.hub.sections.record")}
              >
                <section className="space-y-2">
                  <h2 className="px-1 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
                    {copy("phr.hub.sections.personal")}
                  </h2>
                  {renderSectionRows(sections.slice(0, 3))}
                </section>
                <section className="space-y-2">
                  <h2 className="px-1 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
                    {copy("phr.hub.sections.important")}
                  </h2>
                  {renderSectionRows(sections.slice(3))}
                </section>
              </div>

              {/* Sidebar disclaimer & consent */}
              <aside className="space-y-4">
                <section className="chrome-panel rounded-[var(--radius-xl)] p-5">
                  <Icon
                    name="warning"
                    className="text-[var(--text-brand)]"
                    aria-hidden="true"
                  />
                  <h2 className="mt-3 text-lg font-semibold text-[var(--text-primary)]">
                    {text.consentTitle}
                  </h2>
                  <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                    {text.consentBody}
                  </p>
                  <Button
                    as="link"
                    href="/account/consent"
                    variant="secondary"
                    size="sm"
                    className="mt-4"
                  >
                    {text.consentLink}
                  </Button>
                </section>

                <p
                  role="note"
                  className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4 text-[13px] leading-6 text-[var(--text-secondary)]"
                >
                  {text.disclaimer}
                </p>
              </aside>
            </div>

            {/* Tools Section */}
            {tools.length > 0 ? (
              <section
                aria-label={copy("phr.hub.sections.tools")}
                className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3"
              >
                {tools.map((item) => (
                  <Button
                    key={item.href}
                    as="link"
                    href={item.href}
                    variant="ghost"
                    className="h-auto min-h-28 justify-start whitespace-normal p-4 text-left border border-[color:var(--shell-border)] hover:border-[color:var(--brand-500)]/40 hover:bg-[var(--surface-muted)]"
                  >
                    <span className="flex items-start gap-3">
                      <Icon
                        name={item.icon}
                        size={22}
                        className="mt-0.5 text-[var(--text-secondary)]"
                      />
                      <span>
                        <span className="block text-sm font-bold text-[var(--text-primary)]">
                          {item.title}
                        </span>
                        <span className="mt-1 block text-[13px] font-normal leading-5 text-[var(--text-secondary)]">
                          {item.description}
                        </span>
                      </span>
                    </span>
                  </Button>
                ))}
              </section>
            ) : null}
          </div>
        </div>
      </div>
    </PageShell>
  );
}
