"use client";

import React, { forwardRef } from "react";

export interface FloatingChromeProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
}

export const FloatingChrome = forwardRef<HTMLDivElement, FloatingChromeProps>(
  ({ children, className = "", ...rest }, ref) => {
    return (
      <div
        ref={ref}
        className={`clara-floating-chrome z-30 inline-flex items-center rounded-2xl ${className}`}
        {...rest}
      >
        {children}
      </div>
    );
  }
);

FloatingChrome.displayName = "FloatingChrome";
