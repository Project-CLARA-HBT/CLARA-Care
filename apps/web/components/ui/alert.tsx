"use client";

import type { HTMLAttributes, ReactNode } from "react";
import React, { useState } from "react";
import { Icon, resolveIconName, type IconName } from "@/components/ui/icon";

export type AlertTone =
  | "info"
  | "warn"
  | "warning"
  | "danger"
  | "error"
  | "success"
  | "neutral";

export type AlertVariant = "subtle" | "bordered" | "filled" | "banner";

export interface AlertProps extends Omit<HTMLAttributes<HTMLDivElement>, "title"> {
  title?: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  tone?: AlertTone;
  icon?: IconName | string | ReactNode | false;
  dismissible?: boolean;
  onDismiss?: () => void;
  action?: ReactNode;
  variant?: AlertVariant;
  className?: string;
  role?: string;
}

type NormalizedTone = "info" | "warn" | "danger" | "success" | "neutral";

function normalizeTone(tone: AlertTone = "info"): NormalizedTone {
  if (tone === "warning") return "warn";
  if (tone === "error") return "danger";
  return tone;
}

const DEFAULT_ICONS: Record<NormalizedTone, IconName> = {
  info: "clinical-notes",
  warn: "warning",
  danger: "warning",
  success: "check",
  neutral: "clinical-notes",
};

const VARIANT_TONE_STYLES: Record<AlertVariant, Record<NormalizedTone, { container: string; icon: string }>> = {
  subtle: {
    info: {
      container:
        "bg-[var(--status-info-bg,var(--status-ok-bg))] border-[color:var(--status-info-border,var(--status-ok-border))] text-[var(--text-primary)]",
      icon: "text-[var(--status-info-text,var(--text-brand))]",
    },
    warn: {
      container:
        "bg-[var(--status-warn-bg)] border-[color:var(--status-warn-border)] text-[var(--text-primary)]",
      icon: "text-[var(--status-warn-text)]",
    },
    danger: {
      container:
        "bg-[var(--status-danger-bg)] border-[color:var(--status-danger-border)] text-[var(--text-primary)]",
      icon: "text-[var(--status-danger-text)]",
    },
    success: {
      container:
        "bg-[var(--status-ok-bg)] border-[color:var(--status-ok-border)] text-[var(--text-primary)]",
      icon: "text-[var(--status-ok-text)]",
    },
    neutral: {
      container:
        "bg-[var(--surface-muted)] border-[color:var(--shell-border)] text-[var(--text-primary)]",
      icon: "text-[var(--text-secondary)]",
    },
  },
  bordered: {
    info: {
      container:
        "bg-transparent border-[color:var(--status-info-border,var(--status-ok-border))] text-[var(--text-primary)]",
      icon: "text-[var(--status-info-text,var(--text-brand))]",
    },
    warn: {
      container:
        "bg-transparent border-[color:var(--status-warn-border)] text-[var(--text-primary)]",
      icon: "text-[var(--status-warn-text)]",
    },
    danger: {
      container:
        "bg-transparent border-[color:var(--status-danger-border)] text-[var(--text-primary)]",
      icon: "text-[var(--status-danger-text)]",
    },
    success: {
      container:
        "bg-transparent border-[color:var(--status-ok-border)] text-[var(--text-primary)]",
      icon: "text-[var(--status-ok-text)]",
    },
    neutral: {
      container:
        "bg-transparent border-[color:var(--shell-border)] text-[var(--text-primary)]",
      icon: "text-[var(--text-secondary)]",
    },
  },
  filled: {
    info: {
      container: "bg-[var(--brand-600)] border-transparent text-white",
      icon: "text-white",
    },
    warn: {
      container: "bg-[#fabd34] border-transparent text-black",
      icon: "text-black",
    },
    danger: {
      container: "bg-[var(--danger-500,#ba1a1a)] border-transparent text-white",
      icon: "text-white",
    },
    success: {
      container: "bg-[var(--brand-700,#003ea8)] border-transparent text-white",
      icon: "text-white",
    },
    neutral: {
      container: "bg-[var(--surface-panel)] border-[color:var(--shell-border)] text-[var(--text-primary)]",
      icon: "text-[var(--text-secondary)]",
    },
  },
  banner: {
    info: {
      container:
        "bg-[var(--status-info-bg,var(--status-ok-bg))] border-[color:var(--status-info-border,var(--status-ok-border))] text-[var(--text-primary)] rounded-none border-x-0",
      icon: "text-[var(--status-info-text,var(--text-brand))]",
    },
    warn: {
      container:
        "bg-[var(--status-warn-bg)] border-[color:var(--status-warn-border)] text-[var(--text-primary)] rounded-none border-x-0",
      icon: "text-[var(--status-warn-text)]",
    },
    danger: {
      container:
        "bg-[var(--status-danger-bg)] border-[color:var(--status-danger-border)] text-[var(--text-primary)] rounded-none border-x-0",
      icon: "text-[var(--status-danger-text)]",
    },
    success: {
      container:
        "bg-[var(--status-ok-bg)] border-[color:var(--status-ok-border)] text-[var(--text-primary)] rounded-none border-x-0",
      icon: "text-[var(--status-ok-text)]",
    },
    neutral: {
      container:
        "bg-[var(--surface-muted)] border-[color:var(--shell-border)] text-[var(--text-primary)] rounded-none border-x-0",
      icon: "text-[var(--text-secondary)]",
    },
  },
};

export function AlertTitle({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <h4 className={`font-semibold text-sm leading-tight text-inherit ${className}`}>
      {children}
    </h4>
  );
}

export function AlertDescription({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`text-xs sm:text-sm leading-relaxed opacity-90 mt-1 ${className}`}>
      {children}
    </div>
  );
}

export function Alert({
  title,
  description,
  children,
  tone = "info",
  icon,
  dismissible = false,
  onDismiss,
  action,
  variant = "subtle",
  className = "",
  role,
  ...rest
}: AlertProps) {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) {
    return null;
  }

  const normalizedTone = normalizeTone(tone);
  const toneStyle = VARIANT_TONE_STYLES[variant]?.[normalizedTone] ?? VARIANT_TONE_STYLES.subtle[normalizedTone];

  // Default accessible role
  const computedRole = role ?? (normalizedTone === "danger" || normalizedTone === "warn" ? "alert" : "status");

  const handleDismiss = () => {
    setDismissed(true);
    onDismiss?.();
  };

  const renderIcon = () => {
    if (icon === false) return null;
    if (React.isValidElement(icon)) {
      return <span className={`shrink-0 mt-0.5 ${toneStyle.icon}`}>{icon}</span>;
    }
    const iconName = typeof icon === "string" ? resolveIconName(icon) : DEFAULT_ICONS[normalizedTone];
    return (
      <span className={`shrink-0 mt-0.5 ${toneStyle.icon}`} aria-hidden="true">
        <Icon name={iconName} size="1.25rem" />
      </span>
    );
  };

  const roundedClass = variant === "banner" ? "" : "rounded-[var(--radius-lg)]";

  return (
    <div
      role={computedRole}
      data-tone={normalizedTone}
      data-variant={variant}
      className={`relative flex items-start gap-3 border p-4 transition-all duration-150 ${roundedClass} ${toneStyle.container} ${className}`}
      {...rest}
    >
      {renderIcon()}

      <div className="min-w-0 flex-1">
        {title && <AlertTitle>{title}</AlertTitle>}
        {description && <AlertDescription>{description}</AlertDescription>}
        {children && !description && (
          <div className={`${title ? "mt-1" : ""} text-xs sm:text-sm leading-relaxed opacity-90`}>
            {children}
          </div>
        )}
        {children && description && (
          <div className="mt-2 text-xs sm:text-sm leading-relaxed">
            {children}
          </div>
        )}
        {action && <div className="mt-3 flex items-center gap-2">{action}</div>}
      </div>

      {(dismissible || onDismiss) && (
        <button
          type="button"
          onClick={handleDismiss}
          aria-label="Đóng thông báo"
          className="shrink-0 -mr-1 -mt-1 rounded-[var(--radius-sm)] p-1.5 opacity-70 transition hover:opacity-100 focus-ring hover:bg-black/10 dark:hover:bg-white/10"
        >
          <Icon name="close" size="1rem" aria-hidden="true" />
        </button>
      )}
    </div>
  );
}

export default Alert;
