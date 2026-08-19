import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import {
  HealthStateBadge,
  HEALTH_STATE_MAP,
  type HealthState,
  type NormalizedHealthState,
} from "./health-state-badge";

afterEach(cleanup);

describe("HealthStateBadge", () => {
  const ALL_STATES: HealthState[] = [
    "confirmed",
    "user-reported",
    "user_reported",
    "imported",
    "device",
    "unconfirmed",
    "stopped",
    "conflict",
    "stale",
  ];

  it.each(ALL_STATES)("renders health state %s with default Vietnamese label and icon", (state) => {
    const { container } = render(<HealthStateBadge state={state} locale="vi" />);
    const normalized: NormalizedHealthState = state === "user_reported" ? "user-reported" : state;
    const meta = HEALTH_STATE_MAP[normalized];

    expect(screen.getByText(meta.labelVi)).toBeInTheDocument();
    const badge = container.querySelector(".health-state-badge");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveAttribute("data-health-state", normalized);
  });

  it.each(ALL_STATES)("renders health state %s with English label when locale is en", (state) => {
    render(<HealthStateBadge state={state} locale="en" />);
    const normalized: NormalizedHealthState = state === "user_reported" ? "user-reported" : state;
    const meta = HEALTH_STATE_MAP[normalized];

    expect(screen.getByText(meta.labelEn)).toBeInTheDocument();
  });

  it("supports custom label overrides", () => {
    render(<HealthStateBadge state="confirmed" label="Đã duyệt bởi BS. Mai" />);
    expect(screen.getByText("Đã duyệt bởi BS. Mai")).toBeInTheDocument();
  });

  it("hides icon when showIcon is false", () => {
    const { container } = render(<HealthStateBadge state="confirmed" showIcon={false} />);
    const svg = container.querySelector("svg");
    expect(svg).toBeNull();
  });

  it("supports tone override", () => {
    const { container } = render(<HealthStateBadge state="unconfirmed" tone="danger" />);
    const badge = container.querySelector(".health-state-badge");
    expect(badge?.className).toContain("status-danger");
  });
});
