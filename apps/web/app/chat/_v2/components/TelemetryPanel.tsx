"use client";

import { useMemo } from "react";

import type { UserRole } from "@/lib/auth-store";
import type { UILanguage } from "@/lib/ui-language";
import type { ResearchTier2Result } from "@/lib/research";
import RoleGatedTelemetry from "@/components/telemetry/telemetry-panel";
import { buildSourceIntel } from "@/app/chat/_v2/lib/telemetry-format";

/**
 * Detailed telemetry panel for the rebuilt CLARA Chat (CHAT_V2).
 *
 * Source-intel detail. Wrapped in the shared role-gated
 * `TelemetryPanel` so the detailed view renders ONLY for admins (Requirement
 * 6.6; design Property P7); non-admins get nothing here (detailed telemetry is
 * admin-only — their answer view already carries the safety summary). This
 * component reads only coarse, non-PII telemetry shapes.
 */

export type TelemetryPanelProps = {
  role: UserRole;
  result: ResearchTier2Result | null;
  uiLanguage: UILanguage;
};

export default function TelemetryPanel({ role, result, uiLanguage }: TelemetryPanelProps) {
  const isEn = uiLanguage === "en";
  const sourceIntel = useMemo(() => buildSourceIntel(result), [result]);

  return (
    <RoleGatedTelemetry role={role} className="w-full">
      <aside
        aria-label={isEn ? "System telemetry" : "Telemetry hệ thống"}
        className="space-y-2 rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3"
      >
        <p className="text-[10px] font-black uppercase tracking-[0.12em] text-[var(--text-muted)]">
          {isEn ? "Telemetry" : "Theo dõi"}
        </p>

        <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2">
          <div className="flex items-center justify-between gap-2">
            <p className="text-[9px] uppercase tracking-[0.12em] text-[var(--text-muted)]">
              {isEn ? "Source intel" : "Nguồn"}
            </p>
            <span className="text-[11px] font-semibold text-[var(--text-primary)]">
              {sourceIntel.activeCount}
            </span>
          </div>
          {sourceIntel.all.length ? (
            <ul className="mt-1.5 space-y-1">
              {sourceIntel.all.slice(0, 6).map((item) => (
                <li
                  key={item.name}
                  className="flex items-center justify-between gap-2 text-[11px] text-[var(--text-secondary)]"
                >
                  <span className="truncate">{item.name}</span>
                  <span className="shrink-0 text-[10px] text-[var(--text-muted)]">
                    {item.status}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-1 text-[11px] text-[var(--text-muted)]">
              {isEn ? "No source signal yet." : "Chưa có tín hiệu nguồn."}
            </p>
          )}
        </div>
      </aside>
    </RoleGatedTelemetry>
  );
}
