import type { ReactNode } from "react";

/**
 * AsyncSection — the shared async-content primitive.
 *
 * Every primary Surface renders asynchronous content through one of exactly
 * four mutually exclusive states: `loading`, `empty`, `error`, or `populated`.
 * Modeling those states as a discriminated union makes the exclusivity a
 * compile-time and run-time guarantee: a value can carry exactly one `kind`,
 * so the component renders exactly one branch.
 *
 * Error messages are assumed to be PRE-SANITIZED by the caller (via
 * `sanitizeUpstreamError` from `@/lib/user-facing-text`); this component never
 * inspects or transforms the message, it only displays it. Keeping sanitization
 * at the call site keeps this component a pure presentational primitive.
 *
 * Design: `.kiro/specs/product-polish-analytics/design.md` section 6
 * Requirements: 5.2 (distinct loading / empty / error / populated states).
 */

/** Discriminated union describing the four mutually exclusive async states. */
export type AsyncState<T> =
  | { kind: "loading" }
  | { kind: "empty" }
  | { kind: "error"; message: string }
  | { kind: "populated"; data: T };

/** The four state discriminants, exposed for exhaustive checks and testing. */
export type AsyncStateKind = AsyncState<unknown>["kind"];

/** Canonical, ordered list of the async state kinds. */
export const ASYNC_STATE_KINDS = ["loading", "empty", "error", "populated"] as const;

/**
 * Resolves the single active state kind from a canonical `AsyncState`.
 *
 * Because `AsyncState<T>` is a discriminated union, a value carries exactly one
 * `kind`, so this helper returns exactly one of `loading | empty | error |
 * populated`. It is intentionally a pure, side-effect-free projection over the
 * `kind` discriminant so the mutual-exclusivity property test (task 8.2,
 * Property 21) can import it and assert that, for any generated state, exactly
 * one kind is ever active.
 *
 * Requirement 5.2.
 */
export function resolveAsyncStateKind<T>(state: AsyncState<T>): AsyncStateKind {
  return state.kind;
}

/**
 * Loose inputs that a caller typically has on hand (a loading flag, an optional
 * error string, and the fetched data). `selectAsyncState` folds them into the
 * canonical `AsyncState` so that exactly one state is ever produced.
 */
export type AsyncStateInput<T> = {
  /** True while the request is in flight. Highest priority. */
  loading?: boolean;
  /** A pre-sanitized error message, or null/undefined when there is no error. */
  error?: string | null;
  /** The fetched data, or null/undefined when nothing has loaded yet. */
  data?: T | null;
  /**
   * Optional predicate deciding whether `data` should count as empty.
   * Defaults to `defaultIsEmpty` (null/undefined, empty array, empty object,
   * or blank string are treated as empty).
   */
  isEmpty?: (data: T) => boolean;
};

/**
 * Default emptiness check used when a caller does not supply `isEmpty`.
 * Treats null/undefined, empty arrays, empty plain objects, and blank strings
 * as empty; every other value is considered populated.
 */
export function defaultIsEmpty(data: unknown): boolean {
  if (data === null || data === undefined) return true;
  if (Array.isArray(data)) return data.length === 0;
  if (typeof data === "string") return data.trim().length === 0;
  if (typeof data === "object") return Object.keys(data as object).length === 0;
  return false;
}

/**
 * Pure state-selection logic. Folds loose inputs into exactly one canonical
 * `AsyncState` using a deterministic priority:
 *
 *   loading  >  error  >  empty  >  populated
 *
 * Because the return type is the discriminated union, the result always carries
 * exactly one `kind`. This function is side-effect free so it can be exercised
 * directly by the async-state-exclusivity property test (task 9.2).
 *
 * Requirement 5.2.
 */
export function selectAsyncState<T>(input: AsyncStateInput<T>): AsyncState<T> {
  if (input.loading) {
    return { kind: "loading" };
  }

  const message = typeof input.error === "string" ? input.error.trim() : "";
  if (message) {
    return { kind: "error", message };
  }

  const { data } = input;
  const isEmpty = input.isEmpty ?? (defaultIsEmpty as (value: T) => boolean);
  if (data === null || data === undefined || isEmpty(data)) {
    return { kind: "empty" };
  }

  return { kind: "populated", data };
}

/** Vietnamese copy used when a caller does not override a slot. */
const DEFAULTS = {
  loadingLabel: "Đang tải dữ liệu...",
  emptyTitle: "Chưa có dữ liệu",
  emptyDescription: "Hiện chưa có nội dung để hiển thị.",
  errorTitle: "Đã xảy ra sự cố"
} as const;

export type AsyncSectionProps<T> = {
  /** The current async state. Exactly one branch is rendered. */
  state: AsyncState<T>;
  /** Renders the populated state with the resolved data. */
  children: (data: T) => ReactNode;

  /** Optional full overrides for each non-populated state. */
  renderLoading?: () => ReactNode;
  renderEmpty?: () => ReactNode;
  renderError?: (message: string) => ReactNode;

  /** Lightweight copy overrides for the default slots (Vietnamese defaults). */
  loadingLabel?: string;
  emptyTitle?: string;
  emptyDescription?: string;
  errorTitle?: string;

  /** Extra classes applied to the outer wrapper of the default state slots. */
  className?: string;
};

function slotClassName(className?: string): string {
  return ["rounded-[var(--radius-lg)]", className].filter(Boolean).join(" ");
}

function DefaultLoading({ label, className }: { label: string; className?: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={[
        slotClassName(className),
        "flex items-center justify-center gap-3 border border-[color:var(--shell-border)]",
        "bg-[var(--surface-muted)] px-5 py-8 text-sm text-[var(--text-secondary)]"
      ].join(" ")}
    >
      <span
        aria-hidden="true"
        className="h-4 w-4 animate-spin rounded-full border-2 border-[color:var(--shell-border)] border-t-[color:var(--brand-600)]"
      />
      <span>{label}</span>
    </div>
  );
}

function DefaultEmpty({
  title,
  description,
  className
}: {
  title: string;
  description: string;
  className?: string;
}) {
  return (
    <div
      className={[
        slotClassName(className),
        "border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)]",
        "px-5 py-8 text-center"
      ].join(" ")}
    >
      <p className="text-base font-semibold text-[var(--text-primary)]">{title}</p>
      <p className="mt-1 text-sm text-[var(--text-secondary)]">{description}</p>
    </div>
  );
}

function DefaultError({
  title,
  message,
  className
}: {
  title: string;
  message: string;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={[
        slotClassName(className),
        "border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)]",
        "px-5 py-6 text-center"
      ].join(" ")}
    >
      <p className="text-base font-semibold text-[color:var(--status-danger-text)]">{title}</p>
      <p className="mt-1 text-sm text-[color:var(--status-danger-text)]">{message}</p>
    </div>
  );
}

/**
 * Renders exactly one of `loading | empty | error | populated` based on the
 * discriminated `state`. Callers provide the populated renderer via `children`
 * and may override any of the other three slots, or just tweak their copy.
 *
 * Requirement 5.2.
 */
export function AsyncSection<T>({
  state,
  children,
  renderLoading,
  renderEmpty,
  renderError,
  loadingLabel = DEFAULTS.loadingLabel,
  emptyTitle = DEFAULTS.emptyTitle,
  emptyDescription = DEFAULTS.emptyDescription,
  errorTitle = DEFAULTS.errorTitle,
  className
}: AsyncSectionProps<T>): ReactNode {
  switch (state.kind) {
    case "loading":
      return renderLoading ? (
        <>{renderLoading()}</>
      ) : (
        <DefaultLoading label={loadingLabel} className={className} />
      );
    case "empty":
      return renderEmpty ? (
        <>{renderEmpty()}</>
      ) : (
        <DefaultEmpty title={emptyTitle} description={emptyDescription} className={className} />
      );
    case "error":
      return renderError ? (
        <>{renderError(state.message)}</>
      ) : (
        <DefaultError title={errorTitle} message={state.message} className={className} />
      );
    case "populated":
      return <>{children(state.data)}</>;
    default: {
      // Exhaustiveness guard: if a new kind is added, this fails to compile.
      const _exhaustive: never = state;
      return _exhaustive;
    }
  }
}

export default AsyncSection;
