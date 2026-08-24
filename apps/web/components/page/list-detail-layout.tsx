"use client";

import React, {
  forwardRef,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import { Sheet } from "@/components/ui/sheet";
import { EmptyState } from "@/components/ui/empty-state";
import { SurfaceCard } from "@/components/ui/surface";
import { PageFrame, type PageCanvasBg, type PageGutter, type PageMaxWidth } from "./page-frame";
import { PageHeader, type BreadcrumbItem, type PageHeaderBackAction } from "./page-header";

export type ListDetailInspectorMode = "drawer" | "split" | "modal" | "side-sheet";
export type ListDetailSplitRatio = "50/50" | "60/40" | "65/35" | "70/30";

export interface ListDetailLayoutProps extends Omit<HTMLAttributes<HTMLElement>, "title"> {
  /** Page header element or uses PageHeader props */
  header?: ReactNode;
  eyebrow?: ReactNode;
  title?: ReactNode;
  subtitle?: ReactNode;
  description?: ReactNode;
  badges?: ReactNode;
  breadcrumbs?: BreadcrumbItem[] | ReactNode;
  headerActions?: ReactNode;
  backAction?: PageHeaderBackAction;
  /** Filter and search controls bar */
  toolbar?: ReactNode;
  /** Alias for toolbar */
  filterBar?: ReactNode;
  /** Primary list / table content */
  list: ReactNode;
  /** Detail view / inspector panel */
  detail?: ReactNode;
  /** Alias for detail */
  inspector?: ReactNode;
  /** Selected item identifier */
  selectedId?: string | number | null;
  /** Presentation mode for detail inspector */
  inspectorMode?: ListDetailInspectorMode;
  /** Open state for drawer/modal mode */
  inspectorOpen?: boolean;
  /** Callback to close inspector */
  onInspectorClose?: () => void;
  /** Fallback placeholder when no item is selected in split view */
  emptyDetailState?: ReactNode;
  /** Column split ratio in desktop split mode */
  splitRatio?: ListDetailSplitRatio;
  /** Additional body children */
  children?: ReactNode;
  /** Max width */
  maxWidth?: PageMaxWidth;
  /** Gutter padding */
  gutter?: PageGutter;
  /** Canvas background */
  canvasBg?: PageCanvasBg;
}

const SPLIT_RATIOS: Record<ListDetailSplitRatio, { list: string; detail: string }> = {
  "50/50": { list: "lg:col-span-6", detail: "lg:col-span-6" },
  "60/40": { list: "lg:col-span-7", detail: "lg:col-span-5" },
  "65/35": { list: "lg:col-span-8", detail: "lg:col-span-4" },
  "70/30": { list: "lg:col-span-8 xl:col-span-9", detail: "lg:col-span-4 xl:col-span-3" },
};

/**
 * List-Detail archetype layout primitive.
 * Supports responsive master-list + slide-over drawer / split inspector views.
 */
export const ListDetailLayout = forwardRef<HTMLElement, ListDetailLayoutProps>(
  (
    {
      header,
      eyebrow,
      title,
      subtitle,
      description,
      badges,
      breadcrumbs,
      headerActions,
      backAction,
      toolbar,
      filterBar,
      list,
      detail,
      inspector,
      selectedId,
      inspectorMode = "split",
      inspectorOpen,
      onInspectorClose,
      emptyDetailState,
      splitRatio = "65/35",
      children,
      maxWidth = "default",
      gutter = "default",
      canvasBg = "canvas",
      className = "",
      ...rest
    },
    ref
  ) => {
    const renderedHeader =
      header ??
      (title ? (
        <PageHeader
          eyebrow={eyebrow}
          title={title}
          subtitle={subtitle}
          description={description}
          badges={badges}
          breadcrumbs={breadcrumbs}
          actions={headerActions}
          backAction={backAction}
        />
      ) : null);

    const activeDetail = detail ?? inspector;
    const resolvedToolbar = toolbar ?? filterBar;
    const isOpen = inspectorOpen ?? Boolean(selectedId || activeDetail);

    const renderSplitView = () => {
      const { list: listSpan, detail: detailSpan } =
        SPLIT_RATIOS[splitRatio] ?? SPLIT_RATIOS["65/35"];

      const defaultEmptyState = (
        <SurfaceCard className="flex min-h-[360px] items-center justify-center p-8 text-center">
          <EmptyState
            title="Chưa chọn mục nào"
            description="Chọn một mục trong danh sách bên trái để xem chi tiết thông tin và thao tác nghiệp vụ."
            icon="clinical-notes"
          />
        </SurfaceCard>
      );

      return (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 lg:gap-8">
          <div className={`min-w-0 ${listSpan}`}>
            <div className="space-y-4">{list}</div>
          </div>
          <div className={`min-w-0 ${detailSpan}`}>
            <div className="sticky top-6">
              {activeDetail ? activeDetail : emptyDetailState ?? defaultEmptyState}
            </div>
          </div>
        </div>
      );
    };

    const renderDrawerView = () => {
      return (
        <div>
          <div className="space-y-4">{list}</div>
          <Sheet
            open={isOpen}
            onClose={onInspectorClose ?? (() => {})}
            side="right"
            size="lg"
          >
            {activeDetail}
          </Sheet>
        </div>
      );
    };

    return (
      <PageFrame
        ref={ref}
        archetype="list-detail"
        header={renderedHeader}
        maxWidth={maxWidth}
        gutter={gutter}
        bg={canvasBg}
        className={className}
        {...rest}
      >
        <div className="space-y-6">
          {resolvedToolbar ? (
            <div className="list-toolbar">{resolvedToolbar}</div>
          ) : null}

          {inspectorMode === "split" ? renderSplitView() : renderDrawerView()}

          {children}
        </div>
      </PageFrame>
    );
  }
);

ListDetailLayout.displayName = "ListDetailLayout";

export default ListDetailLayout;
