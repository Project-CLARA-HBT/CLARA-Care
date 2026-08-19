import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { EntryContextBanner } from "./entry-context-banner";

afterEach(cleanup);

describe("EntryContextBanner", () => {
  it("renders nothing when context is null or global", () => {
    const { container: c1 } = render(<EntryContextBanner context={null} />);
    expect(c1.firstChild).toBeNull();

    const { container: c2 } = render(
      <EntryContextBanner context={{ kind: "global" }} />
    );
    expect(c2.firstChild).toBeNull();
  });

  it("renders scoped chip for result context", () => {
    render(
      <EntryContextBanner
        context={{
          kind: "result",
          resource_id: "res-101",
          label: "Xét nghiệm máu tổng quát",
        }}
      />
    );

    const banner = screen.getByTestId("entry-context-banner");
    expect(banner).toBeInTheDocument();
    expect(screen.getByText(/Hỏi về kết quả:/i)).toBeInTheDocument();
    expect(screen.getByText("Xét nghiệm máu tổng quát")).toBeInTheDocument();
  });

  it("renders scoped chip for medication and visit contexts", () => {
    const { rerender } = render(
      <EntryContextBanner
        context={{
          kind: "medication",
          resource_id: "med-1",
          label: "Metformin 500mg",
        }}
      />
    );
    expect(screen.getByText(/Hỏi về thuốc:/i)).toBeInTheDocument();
    expect(screen.getByText("Metformin 500mg")).toBeInTheDocument();

    rerender(
      <EntryContextBanner
        context={{
          kind: "visit",
          resource_id: "vis-1",
          label: "Khám định kỳ 15/08",
        }}
      />
    );
    expect(screen.getByText(/Hỏi về lần khám:/i)).toBeInTheDocument();
    expect(screen.getByText("Khám định kỳ 15/08")).toBeInTheDocument();
  });

  it("calls onClear when clear button is clicked", () => {
    const onClear = vi.fn();
    render(
      <EntryContextBanner
        context={{
          kind: "document",
          resource_id: "doc-1",
          label: "Đơn thuốc bệnh viện",
        }}
        onClear={onClear}
      />
    );

    const clearBtn = screen.getByTestId("entry-context-clear-button");
    fireEvent.click(clearBtn);
    expect(onClear).toHaveBeenCalledTimes(1);
  });
});
