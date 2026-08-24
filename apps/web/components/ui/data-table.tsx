"use client";

import React, {
  useCallback,
  useEffect,
  useRef,
  type ChangeEvent,
  type Key,
  type ReactNode,
} from "react";
import Icon from "./icon";

export type DataTableDensity = "comfortable" | "compact" | "dense";
export type SortDirection = "asc" | "desc" | null;

export interface DataTableColumn<T> {
  id: string;
  header: ReactNode | ((props: { column: DataTableColumn<T>; sortDirection?: SortDirection }) => ReactNode);
  accessorKey?: keyof T;
  accessorFn?: (row: T, index: number) => any;
  cell?: (props: { row: T; value: any; index: number }) => ReactNode;
  sortable?: boolean;
  align?: "left" | "center" | "right";
  width?: string | number;
  minWidth?: string | number;
  maxWidth?: string | number;
  className?: string;
  headerClassName?: string;
}

export interface DataTablePaginationProps {
  page: number;
  pageSize: number;
  totalCount?: number;
  onPageChange: (page: number) => void;
  onPageSizeChange?: (pageSize: number) => void;
  pageSizeOptions?: number[];
  itemLabel?: string;
}

export interface DataTableProps<T> {
  data: T[];
  columns: DataTableColumn<T>[];
  keyExtractor?: (item: T, index: number) => string;
  density?: DataTableDensity;
  stickyHeader?: boolean;
  // Sorting
  sortColumn?: string | null;
  sortDirection?: SortDirection;
  onSort?: (columnId: string, direction: SortDirection) => void;
  // Row selection
  selectable?: boolean;
  selectedIds?: Set<string> | string[];
  onSelectionChange?: (selectedIds: string[]) => void;
  isRowSelectable?: (row: T, index: number) => boolean;
  // Pagination
  pagination?: DataTablePaginationProps;
  // Loading & Empty states
  loading?: boolean;
  loadingRowCount?: number;
  emptyState?: ReactNode;
  emptyMessage?: string;
  // Interactions & Customization
  onRowClick?: (row: T, index: number) => void;
  rowClassName?: string | ((row: T, index: number) => string);
  className?: string;
  containerClassName?: string;
  ariaLabel?: string;
  caption?: string;
}

const DENSITY_CONFIG: Record<
  DataTableDensity,
  {
    th: string;
    td: string;
    checkboxPadding: string;
  }
> = {
  comfortable: {
    th: "py-3.5 px-4 text-sm font-semibold",
    td: "py-3.5 px-4 text-sm",
    checkboxPadding: "px-4 py-3.5",
  },
  compact: {
    th: "py-2.5 px-3.5 text-xs font-semibold uppercase tracking-wider",
    td: "py-2.5 px-3.5 text-sm",
    checkboxPadding: "px-3.5 py-2.5",
  },
  dense: {
    th: "py-1.5 px-2.5 text-xs font-semibold uppercase tracking-wider",
    td: "py-1.5 px-2.5 text-xs",
    checkboxPadding: "px-2.5 py-1.5",
  },
};

function SortIcon({ direction }: { direction?: SortDirection }) {
  if (direction === "asc") {
    return (
      <svg
        className="h-3.5 w-3.5 shrink-0 text-[var(--brand-500)]"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="m18 15-6-6-6 6" />
      </svg>
    );
  }
  if (direction === "desc") {
    return (
      <svg
        className="h-3.5 w-3.5 shrink-0 text-[var(--brand-500)]"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="m6 9 6 6 6-6" />
      </svg>
    );
  }
  return (
    <svg
      className="h-3.5 w-3.5 shrink-0 opacity-30 group-hover:opacity-75 transition-opacity"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="m7 15 5 5 5-5" />
      <path d="m7 9 5-5 5 5" />
    </svg>
  );
}

export function DataTable<T>({
  data,
  columns,
  keyExtractor,
  density = "compact",
  stickyHeader = true,
  sortColumn,
  sortDirection = null,
  onSort,
  selectable = false,
  selectedIds,
  onSelectionChange,
  isRowSelectable,
  pagination,
  loading = false,
  loadingRowCount = 5,
  emptyState,
  emptyMessage = "Không có dữ liệu",
  onRowClick,
  rowClassName,
  className = "",
  containerClassName = "",
  ariaLabel = "Bảng dữ liệu",
  caption,
}: DataTableProps<T>) {
  const headerCheckboxRef = useRef<HTMLInputElement>(null);
  const densityStyles = DENSITY_CONFIG[density] ?? DENSITY_CONFIG.compact;

  const selectedSet = React.useMemo(() => {
    if (!selectedIds) return new Set<string>();
    return selectedIds instanceof Set ? selectedIds : new Set(selectedIds);
  }, [selectedIds]);

  const defaultKeyExtractor = useCallback(
    (row: T, index: number): string => {
      if (keyExtractor) return keyExtractor(row, index);
      if (row && typeof row === "object") {
        if ("id" in row && (row as any).id !== undefined) return String((row as any).id);
        if ("key" in row && (row as any).key !== undefined) return String((row as any).key);
      }
      return String(index);
    },
    [keyExtractor],
  );

  // Compute selectable rows
  const selectableRowIds = React.useMemo(() => {
    if (!selectable) return [];
    return data
      .map((row, index) => ({
        id: defaultKeyExtractor(row, index),
        selectable: isRowSelectable ? isRowSelectable(row, index) : true,
      }))
      .filter((item) => item.selectable)
      .map((item) => item.id);
  }, [data, defaultKeyExtractor, isRowSelectable, selectable]);

  const isAllSelected =
    selectableRowIds.length > 0 &&
    selectableRowIds.every((id) => selectedSet.has(id));

  const isSomeSelected =
    selectableRowIds.some((id) => selectedSet.has(id)) && !isAllSelected;

  useEffect(() => {
    if (headerCheckboxRef.current) {
      headerCheckboxRef.current.indeterminate = isSomeSelected;
    }
  }, [isSomeSelected]);

  const handleHeaderCheckboxChange = (event: ChangeEvent<HTMLInputElement>) => {
    if (!onSelectionChange) return;
    if (event.target.checked) {
      const merged = new Set([...Array.from(selectedSet), ...selectableRowIds]);
      onSelectionChange(Array.from(merged));
    } else {
      const next = new Set(selectedSet);
      selectableRowIds.forEach((id) => next.delete(id));
      onSelectionChange(Array.from(next));
    }
  };

  const handleRowCheckboxChange = (
    rowId: string,
    event: ChangeEvent<HTMLInputElement>,
  ) => {
    event.stopPropagation();
    if (!onSelectionChange) return;
    const next = new Set(selectedSet);
    if (event.target.checked) {
      next.add(rowId);
    } else {
      next.delete(rowId);
    }
    onSelectionChange(Array.from(next));
  };

  const handleSortClick = (columnId: string, currentDirection?: SortDirection) => {
    if (!onSort) return;
    let nextDirection: SortDirection = "asc";
    if (sortColumn === columnId) {
      if (currentDirection === "asc") nextDirection = "desc";
      else if (currentDirection === "desc") nextDirection = null;
      else nextDirection = "asc";
    }
    onSort(columnId, nextDirection);
  };

  const totalColumns = columns.length + (selectable ? 1 : 0);

  return (
    <div
      className={`relative flex w-full flex-col overflow-hidden rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-sm ${containerClassName}`}
    >
      <div className="w-full overflow-x-auto">
        <table
          className={`w-full border-collapse text-left ${className}`}
          aria-label={ariaLabel}
          aria-busy={loading || undefined}
        >
          {caption ? <caption className="sr-only">{caption}</caption> : null}

          {/* Table Header */}
          <thead
            className={`border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)] ${
              stickyHeader ? "sticky top-0 z-10 backdrop-blur-md" : ""
            }`}
          >
            <tr>
              {selectable && (
                <th
                  scope="col"
                  className={`w-10 text-center ${densityStyles.checkboxPadding}`}
                >
                  <label className="inline-flex items-center justify-center cursor-pointer">
                    <input
                      ref={headerCheckboxRef}
                      type="checkbox"
                      aria-label="Chọn tất cả các hàng"
                      checked={isAllSelected}
                      onChange={handleHeaderCheckboxChange}
                      disabled={loading || selectableRowIds.length === 0}
                      className="h-4 w-4 rounded-[var(--radius-sm)] border-[color:var(--shell-border-strong)] bg-[var(--surface-panel)] text-[var(--brand-600)] focus:ring-2 focus:ring-[var(--focus-ring-color)] cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
                    />
                  </label>
                </th>
              )}

              {columns.map((column) => {
                const isSorted = sortColumn === column.id;
                const activeDirection = isSorted ? sortDirection : null;
                const isSortable = Boolean(column.sortable && onSort);

                const alignClasses =
                  column.align === "center"
                    ? "text-center justify-center"
                    : column.align === "right"
                    ? "text-right justify-end"
                    : "text-left justify-start";

                const style: React.CSSProperties = {
                  width: column.width,
                  minWidth: column.minWidth,
                  maxWidth: column.maxWidth,
                };

                return (
                  <th
                    key={column.id}
                    scope="col"
                    style={style}
                    aria-sort={
                      isSortable
                        ? activeDirection === "asc"
                          ? "ascending"
                          : activeDirection === "desc"
                          ? "descending"
                          : "none"
                        : undefined
                    }
                    className={`${densityStyles.th} ${
                      column.headerClassName ?? ""
                    }`}
                  >
                    {isSortable ? (
                      <button
                        type="button"
                        onClick={() => handleSortClick(column.id, activeDirection)}
                        className={`group inline-flex items-center gap-1.5 font-inherit text-inherit hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--focus-ring-color)] rounded-[var(--radius-sm)] ${alignClasses}`}
                      >
                        <span>
                          {typeof column.header === "function"
                            ? column.header({ column, sortDirection: activeDirection })
                            : column.header}
                        </span>
                        <SortIcon direction={activeDirection} />
                      </button>
                    ) : (
                      <div className={`inline-flex items-center ${alignClasses}`}>
                        {typeof column.header === "function"
                          ? column.header({ column, sortDirection: activeDirection })
                          : column.header}
                      </div>
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>

          {/* Table Body */}
          <tbody className="divide-y divide-[color:var(--shell-border)] text-[var(--text-primary)]">
            {/* Loading State */}
            {loading && data.length === 0 ? (
              Array.from({ length: loadingRowCount }).map((_, rowIndex) => (
                <tr
                  key={`skeleton-row-${rowIndex}`}
                  className="animate-pulse bg-[var(--surface-panel)]"
                >
                  {selectable && (
                    <td className={`text-center ${densityStyles.checkboxPadding}`}>
                      <div className="mx-auto h-4 w-4 rounded-[var(--radius-sm)] bg-[var(--surface-muted)]" />
                    </td>
                  )}
                  {columns.map((column) => (
                    <td
                      key={`skeleton-cell-${column.id}-${rowIndex}`}
                      className={densityStyles.td}
                    >
                      <div className="h-4 w-3/4 rounded-[var(--radius-sm)] bg-[var(--surface-muted)]" />
                    </td>
                  ))}
                </tr>
              ))
            ) : data.length === 0 ? (
              /* Empty State */
              <tr>
                <td
                  colSpan={totalColumns}
                  className="px-6 py-12 text-center text-[var(--text-secondary)]"
                >
                  {emptyState ? (
                    emptyState
                  ) : (
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Icon
                        name="clinical-notes"
                        size={32}
                        className="text-[var(--text-tertiary)] opacity-60"
                      />
                      <p className="text-sm font-medium">{emptyMessage}</p>
                    </div>
                  )}
                </td>
              </tr>
            ) : (
              /* Data Rows */
              data.map((row, rowIndex) => {
                const rowKey = defaultKeyExtractor(row, rowIndex);
                const isSelected = selectedSet.has(rowKey);
                const isRowSelectableFlag = isRowSelectable
                  ? isRowSelectable(row, rowIndex)
                  : true;

                const customRowClass =
                  typeof rowClassName === "function"
                    ? rowClassName(row, rowIndex)
                    : rowClassName || "";

                return (
                  <tr
                    key={rowKey}
                    aria-selected={selectable ? isSelected : undefined}
                    onClick={onRowClick ? () => onRowClick(row, rowIndex) : undefined}
                    className={`transition-colors duration-100 ${
                      onRowClick ? "cursor-pointer hover:bg-[var(--surface-muted)]" : ""
                    } ${
                      isSelected
                        ? "bg-[var(--surface-brand-soft)] hover:bg-[var(--surface-brand-soft)]/90"
                        : "hover:bg-[var(--surface-muted)]/50"
                    } ${customRowClass}`}
                  >
                    {selectable && (
                      <td
                        className={`w-10 text-center ${densityStyles.checkboxPadding}`}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <label className="inline-flex items-center justify-center cursor-pointer">
                          <input
                            type="checkbox"
                            aria-label={`Chọn hàng ${rowIndex + 1}`}
                            checked={isSelected}
                            disabled={!isRowSelectableFlag}
                            onChange={(e) => handleRowCheckboxChange(rowKey, e)}
                            className="h-4 w-4 rounded-[var(--radius-sm)] border-[color:var(--shell-border-strong)] bg-[var(--surface-panel)] text-[var(--brand-600)] focus:ring-2 focus:ring-[var(--focus-ring-color)] cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
                          />
                        </label>
                      </td>
                    )}

                    {columns.map((column) => {
                      let cellContent: ReactNode;
                      const rawValue = column.accessorKey
                        ? (row as any)[column.accessorKey]
                        : column.accessorFn
                        ? column.accessorFn(row, rowIndex)
                        : undefined;

                      if (column.cell) {
                        cellContent = column.cell({
                          row,
                          value: rawValue,
                          index: rowIndex,
                        });
                      } else {
                        cellContent =
                          rawValue !== undefined && rawValue !== null
                            ? String(rawValue)
                            : null;
                      }

                      const alignClass =
                        column.align === "center"
                          ? "text-center"
                          : column.align === "right"
                          ? "text-right"
                          : "text-left";

                      return (
                        <td
                          key={column.id}
                          className={`${densityStyles.td} ${alignClass} ${
                            column.className ?? ""
                          }`}
                        >
                          {cellContent}
                        </td>
                      );
                    })}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      {pagination && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3 text-xs sm:text-sm text-[var(--text-secondary)]">
          {/* Summary / Range Info */}
          <div className="flex items-center gap-2">
            <span>
              {pagination.totalCount !== undefined
                ? `Hiển thị ${
                    data.length === 0
                      ? 0
                      : (pagination.page - 1) * pagination.pageSize + 1
                  } - ${Math.min(
                    pagination.page * pagination.pageSize,
                    pagination.totalCount,
                  )} trên ${pagination.totalCount} ${
                    pagination.itemLabel || "mục"
                  }`
                : `Trang ${pagination.page}`}
            </span>

            {pagination.pageSizeOptions && pagination.onPageSizeChange && (
              <div className="flex items-center gap-1.5 ml-3">
                <span className="text-xs text-[var(--text-tertiary)]">
                  Mỗi trang:
                </span>
                <select
                  value={pagination.pageSize}
                  aria-label="Số dòng mỗi trang"
                  onChange={(e) =>
                    pagination.onPageSizeChange?.(Number(e.target.value))
                  }
                  className="rounded-[var(--radius-sm)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-1 text-xs text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--focus-ring-color)]"
                >
                  {pagination.pageSizeOptions.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {/* Navigation Buttons */}
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              aria-label="Trang trước"
              disabled={pagination.page <= 1 || loading}
              onClick={() => pagination.onPageChange(pagination.page - 1)}
              className="inline-flex items-center justify-center rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] transition hover:bg-[var(--surface-muted)] disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring-color)]"
            >
              <Icon name="arrow-left" size={14} className="mr-1" />
              Trước
            </button>

            <span className="px-2 font-medium text-[var(--text-primary)]">
              {pagination.page}
              {pagination.totalCount !== undefined
                ? ` / ${Math.max(
                    1,
                    Math.ceil(pagination.totalCount / pagination.pageSize),
                  )}`
                : ""}
            </span>

            <button
              type="button"
              aria-label="Trang sau"
              disabled={
                loading ||
                (pagination.totalCount !== undefined
                  ? pagination.page >=
                    Math.ceil(pagination.totalCount / pagination.pageSize)
                  : data.length < pagination.pageSize)
              }
              onClick={() => pagination.onPageChange(pagination.page + 1)}
              className="inline-flex items-center justify-center rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] transition hover:bg-[var(--surface-muted)] disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring-color)]"
            >
              Sau
              <Icon name="arrow-right" size={14} className="ml-1" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default DataTable;
