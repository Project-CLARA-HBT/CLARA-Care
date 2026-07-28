import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock("@/lib/http-client", () => ({ default: api }));

import {
  checkDrugBankDdi,
  correctMedicationCourse,
  endMedicationCourse,
} from "@/lib/medication-courses";

describe("medication course convergence client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("corrects an opaque course with idempotency and optimistic concurrency", async () => {
    api.post.mockResolvedValue({ data: { id: "med/opaque", version: 3 } });

    await correctMedicationCourse("med/opaque", 2, {
      medication_name: "Metformin",
      dose_text: "850 mg",
      reason: "Sửa dữ liệu đã nhập nhầm",
    });

    expect(api.post).toHaveBeenCalledWith(
      "/medication-courses/med%2Fopaque/correct",
      expect.objectContaining({
        medication_name: "Metformin",
        reason: "Sửa dữ liệu đã nhập nhầm",
      }),
      {
        headers: {
          "Idempotency-Key": expect.any(String),
          "If-Match": "2",
        },
      },
    );
  });

  it("ends a course by adding history rather than issuing DELETE", async () => {
    api.post.mockResolvedValue({ data: { id: "med-1", status: "ended", version: 2 } });

    await endMedicationCourse("med-1", 1, "Người dùng cập nhật hồ sơ");

    expect(api.post).toHaveBeenCalledWith(
      "/medication-courses/med-1/end",
      { reason: "Người dùng cập nhật hồ sơ" },
      {
        headers: {
          "Idempotency-Key": expect.any(String),
          "If-Match": "1",
        },
      },
    );
  });

  it("passes opaque confirmed-course ids to the DrugBank-only route unchanged", async () => {
    api.post.mockResolvedValue({
      data: {
        conclusion_available: true,
        required_source: "drugbank",
        source_version: "licensed-2026-07",
        courses: [],
        ddi_alerts: [],
        recommendation: "",
      },
    });

    await checkDrugBankDdi(["med_a", "med_b"]);

    expect(api.post).toHaveBeenCalledWith("/medication-courses/safety/ddi", {
      course_ids: ["med_a", "med_b"],
    });
  });
});
