"use client";

import React, {
  forwardRef,
  type ElementType,
  type HTMLAttributes,
  type ReactNode,
} from "react";

export type ContentFrameMaxWidth =
  | "default"
  | "full"
  | "narrow"
  | "wide"
  | "dense";

export interface ContentFrameProps extends HTMLAttributes<HTMLElement> {
  children: ReactNode;
  as?: ElementType;
  isImmersive?: boolean;
  isChatLayout?: boolean;
  maxWidth?: ContentFrameMaxWidth;
  className?: string;
  containerClassName?: string;
}

export const ContentFrame = forwardRef<HTMLElement, ContentFrameProps>(
  (
    {
      as: Component = "main",
      children,
      isImmersive = false,
      isChatLayout = false,
      maxWidth = "default",
      className = "",
      containerClassName = "",
      id = "main-content",
      tabIndex = -1,
      ...rest
    },
    ref,
  ) => {
    return (
      <Component
        ref={ref}
        id={id}
        tabIndex={tabIndex}
        data-testid="content-frame"
        data-immersive={isImmersive ? "true" : "false"}
        className={[
          "app-content-canvas flex-1",
          isChatLayout
            ? "px-0 pb-0 pt-0 sm:px-0 sm:pb-0 sm:pt-0 lg:px-0 lg:pb-0 lg:pt-0 h-[calc(100dvh-54px)] flex flex-col min-h-0 overflow-hidden"
            : isImmersive
              ? "px-0 pb-6 pt-0 sm:px-0.5 sm:pb-8 sm:pt-0 lg:px-0.5 lg:pb-1 lg:pt-0"
              : "px-4 pb-[calc(env(safe-area-inset-bottom,0px)+6rem)] pt-5 sm:px-6 sm:pb-28 sm:pt-7 lg:px-12 lg:pb-24 lg:pt-8",
          className,
        ].join(" ")}
        {...rest}
      >
        <div
          className={[
            "w-full",
            isChatLayout
              ? "h-full flex flex-col min-h-0 max-w-none"
              : isImmersive
                ? "max-w-none"
                : maxWidth === "full"
                  ? "max-w-full"
                  : maxWidth === "narrow"
                    ? "mx-auto max-w-3xl"
                    : maxWidth === "dense"
                      ? "mx-auto max-w-[1680px]"
                      : "mx-auto max-w-[1120px]",
            containerClassName,
          ].join(" ")}
        >
          {children}
        </div>
      </Component>
    );
  },
);

ContentFrame.displayName = "ContentFrame";

export default ContentFrame;
