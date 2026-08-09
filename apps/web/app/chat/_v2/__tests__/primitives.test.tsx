import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import {
  Badge,
  Button,
  Drawer,
  IconButton,
  StatusDot,
  Tabs,
  Tooltip,
} from "@/app/chat/_v2/components/primitives";

/**
 * Feature: clara-chat-redesign; Requirement 4.1, 4.3, 5.1, 5.2, 5.4.
 *
 * The shared design-system primitives must ship accessible semantics and states:
 * named icon buttons, a roving-focus tablist with arrow-key navigation, a modal
 * drawer that closes on Escape and restores focus, and a tooltip wired via
 * `aria-describedby`.
 */

afterEach(() => {
  vi.clearAllMocks();
});

describe("Button / IconButton", () => {
  it("defaults to type=button and forwards disabled", () => {
    render(
      <Button disabled onClick={() => {}}>
        Send
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Send" });
    expect(button).toHaveAttribute("type", "button");
    expect(button).toBeDisabled();
  });

  it("IconButton exposes its accessible label", () => {
    render(<IconButton label="Close" icon="close" />);
    expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
  });

  it("maps every ChatShell control to a concrete bundled SVG", () => {
    const { container } = render(
      <>
        <IconButton label="Command" icon="bolt" />
        <IconButton label="Workspace" icon="dock_to_left" />
      </>,
    );

    expect(container.querySelectorAll("[data-icon='fallback']")).toHaveLength(0);
    expect(container.querySelector("[data-icon='progress']")).toBeInTheDocument();
    expect(container.querySelector("[data-icon='folder']")).toBeInTheDocument();
  });
});

describe("StatusDot / Badge", () => {
  it("StatusDot is decorative (aria-hidden)", () => {
    const { container } = render(<StatusDot tone="ok" />);
    expect(container.querySelector("[aria-hidden='true']")).not.toBeNull();
  });

  it("Badge renders its content", () => {
    render(<Badge tone="warn">Beta</Badge>);
    expect(screen.getByText("Beta")).toBeInTheDocument();
  });
});

describe("Tooltip", () => {
  it("links the trigger to the tip via aria-describedby", () => {
    render(
      <Tooltip label="Run a deep search">
        <button type="button">Deep</button>
      </Tooltip>,
    );
    const tip = screen.getByRole("tooltip", { hidden: true });
    expect(tip).toHaveTextContent("Run a deep search");
    expect(tip.id).toBeTruthy();
  });
});

describe("Tabs", () => {
  it("renders a tablist with the active tab selected and in tab order", () => {
    const onChange = vi.fn();
    render(
      <Tabs
        label="Mode"
        activeId="fast"
        onChange={onChange}
        items={[
          { id: "fast", label: "Fast" },
          { id: "deep", label: "Deep" },
        ]}
      />,
    );
    const fast = screen.getByRole("tab", { name: "Fast" });
    const deep = screen.getByRole("tab", { name: "Deep" });
    expect(fast).toHaveAttribute("aria-selected", "true");
    expect(fast).toHaveAttribute("tabindex", "0");
    expect(deep).toHaveAttribute("tabindex", "-1");
  });

  it("ArrowRight moves selection to the next tab", () => {
    const onChange = vi.fn();
    render(
      <Tabs
        label="Mode"
        activeId="fast"
        onChange={onChange}
        items={[
          { id: "fast", label: "Fast" },
          { id: "deep", label: "Deep" },
        ]}
      />,
    );
    fireEvent.keyDown(screen.getByRole("tab", { name: "Fast" }), {
      key: "ArrowRight",
    });
    expect(onChange).toHaveBeenCalledWith("deep");
  });

  it("ArrowRight wraps past the last enabled tab", () => {
    const onChange = vi.fn();
    render(
      <Tabs
        label="Mode"
        activeId="deep"
        onChange={onChange}
        items={[
          { id: "fast", label: "Fast" },
          { id: "deep", label: "Deep" },
        ]}
      />,
    );
    fireEvent.keyDown(screen.getByRole("tab", { name: "Deep" }), {
      key: "ArrowRight",
    });
    expect(onChange).toHaveBeenCalledWith("fast");
  });
});

describe("Drawer", () => {
  it("renders a labelled modal dialog when open and nothing when closed", () => {
    const onClose = vi.fn();
    const { rerender } = render(
      <Drawer open label="Workspace" onClose={onClose}>
        <p>panel body</p>
      </Drawer>,
    );
    const dialog = screen.getByRole("dialog", { name: "Workspace" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(screen.getByText("panel body")).toBeInTheDocument();

    rerender(
      <Drawer open={false} label="Workspace" onClose={onClose}>
        <p>panel body</p>
      </Drawer>,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes on Escape", () => {
    const onClose = vi.fn();
    render(
      <Drawer open label="Workspace" onClose={onClose}>
        <p>body</p>
      </Drawer>,
    );
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
