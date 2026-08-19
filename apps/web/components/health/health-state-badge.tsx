import type { ReactNode } from "react";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import type { IconName } from "@/components/ui/icon";

export type HealthState =
  | "confirmed"
  | "user-reported"
  | "user_reported"
  | "imported"
  | "device"
  | "unconfirmed"
  | "stopped"
  | "conflict"
  | "stale";

export type NormalizedHealthState =
  | "confirmed"
  | "user-reported"
  | "imported"
  | "device"
  | "unconfirmed"
  | "stopped"
  | "conflict"
  | "stale";

export interface HealthStateMeta {
  labelVi: string;
  labelEn: string;
  tone: BadgeTone;
  icon: IconName;
}

export const HEALTH_STATE_MAP: Record<NormalizedHealthState, HealthStateMeta> = {
  confirmed: {
    labelVi: "Bác sĩ xác nhận",
    labelEn: "Clinician confirmed",
    tone: "ok",
    icon: "check",
  },
  "user-reported": {
    labelVi: "Người dùng ghi nhận",
    labelEn: "Self-reported",
    tone: "neutral",
    icon: "user-card",
  },
  imported: {
    labelVi: "Nhập từ hồ sơ",
    labelEn: "Imported record",
    tone: "brand",
    icon: "folder",
  },
  device: {
    labelVi: "Từ thiết bị đo",
    labelEn: "Device measurement",
    tone: "brand",
    icon: "scan",
  },
  unconfirmed: {
    labelVi: "Chưa xác nhận",
    labelEn: "Unconfirmed",
    tone: "warn",
    icon: "help",
  },
  stopped: {
    labelVi: "Đã ngưng",
    labelEn: "Stopped",
    tone: "neutral",
    icon: "stop",
  },
  conflict: {
    labelVi: "Có mâu thuẫn",
    labelEn: "In conflict",
    tone: "danger",
    icon: "warning",
  },
  stale: {
    labelVi: "Cần cập nhật",
    labelEn: "Needs update",
    tone: "warn",
    icon: "calendar",
  },
};

export function normalizeHealthState(state: HealthState): NormalizedHealthState {
  if (state === "user_reported") return "user-reported";
  return state;
}

export interface HealthStateBadgeProps {
  state: HealthState;
  locale?: "vi" | "en";
  label?: ReactNode;
  tone?: BadgeTone;
  showIcon?: boolean;
  className?: string;
}

export function HealthStateBadge({
  state,
  locale = "vi",
  label,
  tone,
  showIcon = true,
  className = "",
}: HealthStateBadgeProps) {
  const normalized = normalizeHealthState(state);
  const meta = HEALTH_STATE_MAP[normalized] ?? HEALTH_STATE_MAP.unconfirmed;
  const activeTone = tone ?? meta.tone;
  const activeLabel = label ?? (locale === "en" ? meta.labelEn : meta.labelVi);

  return (
    <Badge
      tone={activeTone}
      icon={showIcon ? meta.icon : undefined}
      className={`health-state-badge ${className}`}
      data-health-state={normalized}
      data-testid={`health-state-badge-${normalized}`}
    >
      <span>{activeLabel}</span>
    </Badge>
  );
}

export default HealthStateBadge;
