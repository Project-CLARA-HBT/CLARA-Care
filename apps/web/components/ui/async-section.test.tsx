import { describe, expect, it, afterEach } from "vitest";
import fc from "fast-check";
import { cleanup, render, screen } from "@testing-library/react";

import AsyncSection, {
  ASYNC_STATE_KINDS,
  resolveAsyncStateKind,
  selectAsyncState,
  type AsyncState,
  type AsyncStateKind
} from "@/components/ui/async-section";

/**
 * Feature: product-polish-analytics, Property 21
 * Async sections render exactly one of loading | empty | error | populated
 * (mutually exclusive).
 *
 * Validates: Requirements 5.2
 *
 * The four states are modeled as a discriminated union, so exactly one branch
 * renders for any given state. We assert this two ways: (1) at the pure-logic
 * level via `resolveAsyncStateKind`/`selectAsyncState`, and (2) at the render
 * level via React Testing Library by tagging each slot with a test id and
 * counting how many are present in the DOM.
 */

afterEach(() => {
  cleanup();
});

// Test-id markers, one per slot, so we can count rendered states.
const TID: Record<AsyncStateKind, string> = {
  loading: "slot-loading",
  empty: "slot-empty",
  error: "slot-error",
  populated: "slot-populated"
};

function renderState(state: AsyncState<string>) {
  return render(
    <AsyncSection<string>
      state={state}
      renderLoading={() => <div data-testid={TID.loading}>loading</div>}
      renderEmpty={() => <div data-testid={TID.empty}>empty</div>}
      renderError={(message) => <div data-testid={TID.error}>{message}</div>}
    >
      {(data) => <div data-testid={TID.populated}>{data}</div>}
    </AsyncSection>
  );
}

function renderedKinds(): AsyncStateKind[] {
  return ASYNC_STATE_KINDS.filter((kind) => screen.queryByTestId(TID[kind]) !== null);
}

describe("AsyncSection rendering (Feature: product-polish-analytics, Property 21)", () => {
  it("renders the loading slot only", () => {
    renderState({ kind: "loading" });
    expect(renderedKinds()).toEqual(["loading"]);
  });

  it("renders the empty slot only", () => {
    renderState({ kind: "empty" });
    expect(renderedKinds()).toEqual(["empty"]);
  });

  it("renders the error slot only, showing the (pre-sanitized) message", () => {
    renderState({ kind: "error", message: "Hệ thống đang bận, vui lòng thử lại." });
    expect(renderedKinds()).toEqual(["error"]);
    expect(screen.getByTestId(TID.error)).toHaveTextContent("Hệ thống đang bận");
  });

  it("renders the populated slot only, with the data", () => {
    renderState({ kind: "populated", data: "ket-qua" });
    expect(renderedKinds()).toEqual(["populated"]);
    expect(screen.getByTestId(TID.populated)).toHaveTextContent("ket-qua");
  });

  it("Property 21: exactly one slot renders for any generated state", () => {
    const stateArb: fc.Arbitrary<AsyncState<string>> = fc.oneof(
      fc.constant<AsyncState<string>>({ kind: "loading" }),
      fc.constant<AsyncState<string>>({ kind: "empty" }),
      fc.record({ kind: fc.constant("error" as const), message: fc.string() }),
      fc.record({ kind: fc.constant("populated" as const), data: fc.string() })
    );

    fc.assert(
      fc.property(stateArb, (state) => {
        cleanup();
        renderState(state);
        const kinds = renderedKinds();
        // Exactly one slot is present, and it matches the state's discriminant.
        return kinds.length === 1 && kinds[0] === state.kind;
      }),
      { numRuns: 200 }
    );
  });
});

describe("resolveAsyncStateKind / selectAsyncState (Property 21, pure logic)", () => {
  it("resolveAsyncStateKind returns the single active discriminant", () => {
    const stateArb: fc.Arbitrary<AsyncState<number>> = fc.oneof(
      fc.constant<AsyncState<number>>({ kind: "loading" }),
      fc.constant<AsyncState<number>>({ kind: "empty" }),
      fc.record({ kind: fc.constant("error" as const), message: fc.string() }),
      fc.record({ kind: fc.constant("populated" as const), data: fc.integer() })
    );
    fc.assert(
      fc.property(stateArb, (state) => {
        const kind = resolveAsyncStateKind(state);
        return ASYNC_STATE_KINDS.includes(kind) && kind === state.kind;
      }),
      { numRuns: 200 }
    );
  });

  it("Property 21: selectAsyncState folds loose inputs into exactly one state with the documented priority", () => {
    fc.assert(
      fc.property(
        fc.boolean(),
        fc.oneof(fc.constant(null), fc.constant(undefined), fc.string()),
        fc.oneof(fc.constant(null), fc.constant(undefined), fc.array(fc.integer())),
        (loading, error, data) => {
          const state = selectAsyncState<number[]>({ loading, error, data });
          // Result always carries exactly one valid kind.
          if (!ASYNC_STATE_KINDS.includes(state.kind)) return false;

          // Priority: loading > error > empty > populated.
          const errorMessage = typeof error === "string" ? error.trim() : "";
          if (loading) return state.kind === "loading";
          if (errorMessage) return state.kind === "error";
          if (data === null || data === undefined || data.length === 0) {
            return state.kind === "empty";
          }
          return state.kind === "populated";
        }
      ),
      { numRuns: 300 }
    );
  });
});
