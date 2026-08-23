"use client";

import React from "react";
import Button from "./button";

interface EmptyStateProps {
  title: string;
  description: string;
  icon?: React.ReactNode;
  primaryAction?: {
    label: string;
    onClick?: () => void;
    href?: string;
  };
  secondaryAction?: {
    label: string;
    onClick?: () => void;
    href?: string;
  };
  className?: string;
}

export function EmptyState({
  title,
  description,
  icon,
  primaryAction,
  secondaryAction,
  className = "",
}: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center p-8 text-center rounded-[var(--radius-lg,20px)] border border-[var(--border-subtle)] bg-[var(--surface-0)]/70 backdrop-blur-sm ${className}`}
    >
      {icon && (
        <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--clara-brand-50)] dark:bg-[var(--clara-brand-900)]/30 text-[var(--action-primary)] shadow-sm">
          {icon}
        </div>
      )}
      <h3 className="text-base sm:text-lg font-semibold text-[var(--text-primary)]">
        {title}
      </h3>
      <p className="mt-1.5 max-w-md text-sm text-[var(--text-secondary)] leading-relaxed">
        {description}
      </p>
      {(primaryAction || secondaryAction) && (
        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
          {primaryAction && (
            primaryAction.href ? (
              <Button as="link" href={primaryAction.href} variant="primary">
                {primaryAction.label}
              </Button>
            ) : (
              <Button onClick={primaryAction.onClick} variant="primary">
                {primaryAction.label}
              </Button>
            )
          )}
          {secondaryAction && (
            secondaryAction.href ? (
              <Button as="link" href={secondaryAction.href} variant="secondary">
                {secondaryAction.label}
              </Button>
            ) : (
              <Button onClick={secondaryAction.onClick} variant="secondary">
                {secondaryAction.label}
              </Button>
            )
          )}
        </div>
      )}
    </div>
  );
}

export default EmptyState;
