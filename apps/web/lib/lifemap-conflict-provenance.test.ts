import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  LifeMapConflictProvenanceHelper,
  isLifeMapConflictProvenanceEnabled,
  type ContradictionSource,
  type ResolutionActionInput,
} from "./lifemap-conflict-provenance";
import * as lifemapApi from "./lifemap";

vi.mock("./lifemap", () => ({
  resolveLifeMapEvent: vi.fn(),
  disputeLifeMapEvent: vi.fn(),
  correctLifeMapEvent: vi.fn(),
  actOnLifeMapReviewFinding: vi.fn(),
}));

describe("LifeMap Conflict Provenance Helper (PH12 A05)", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    vi.clearAllMocks();
    process.env = { ...originalEnv };
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  describe("Feature Flag Gating", () => {
    it("defaults to false when environment variable is unset", () => {
      delete process.env.NEXT_PUBLIC_LIFEMAP_CONFLICT_PROVENANCE_ENABLED;
      expect(isLifeMapConflictProvenanceEnabled()).toBe(false);
    });

    it("evaluates to false when explicitly set to 'false' or empty string", () => {
      process.env.NEXT_PUBLIC_LIFEMAP_CONFLICT_PROVENANCE_ENABLED = "false";
      expect(isLifeMapConflictProvenanceEnabled()).toBe(false);

      process.env.NEXT_PUBLIC_LIFEMAP_CONFLICT_PROVENANCE_ENABLED = "  ";
      expect(isLifeMapConflictProvenanceEnabled()).toBe(false);
    });

    it("evaluates to true when set to 'true', '1', or 'on'", () => {
      process.env.NEXT_PUBLIC_LIFEMAP_CONFLICT_PROVENANCE_ENABLED = "true";
      expect(isLifeMapConflictProvenanceEnabled()).toBe(true);

      process.env.NEXT_PUBLIC_LIFEMAP_CONFLICT_PROVENANCE_ENABLED = "1";
      expect(isLifeMapConflictProvenanceEnabled()).toBe(true);

      process.env.NEXT_PUBLIC_LIFEMAP_CONFLICT_PROVENANCE_ENABLED = "on";
      expect(isLifeMapConflictProvenanceEnabled()).toBe(true);
    });
  });

  describe("Audit Rationale Validation", () => {
    it("rejects empty or whitespace-only rationale", () => {
      expect(LifeMapConflictProvenanceHelper.validateResolutionReason("").valid).toBe(false);
      expect(LifeMapConflictProvenanceHelper.validateResolutionReason("   ").valid).toBe(false);
    });

    it("rejects rationale shorter than 2 characters", () => {
      const res = LifeMapConflictProvenanceHelper.validateResolutionReason("x");
      expect(res.valid).toBe(false);
      expect(res.error).toContain("tối thiểu 2 ký tự");
    });

    it("rejects rationale longer than 500 characters", () => {
      const longStr = "a".repeat(501);
      const res = LifeMapConflictProvenanceHelper.validateResolutionReason(longStr);
      expect(res.valid).toBe(false);
      expect(res.error).toContain("tối đa 500 ký tự");
    });

    it("accepts valid rationale between 2 and 500 characters", () => {
      const res = LifeMapConflictProvenanceHelper.validateResolutionReason(
        "Xác nhận theo đơn thuốc EMR Bệnh viện Bạch Mai",
      );
      expect(res.valid).toBe(true);
      expect(res.error).toBeUndefined();
    });
  });

  describe("Contradiction Classification", () => {
    it("classifies insufficient sources (< 2) as advisory", () => {
      const singleSource: ContradictionSource[] = [
        {
          sourceId: "src-1",
          sourceType: "EMR_INTEGRATION",
          attribution: "BV Bạch Mai",
          occurredAt: "2026-08-01T08:00:00Z",
          recordedAt: "2026-08-01T09:00:00Z",
          revision: 1,
          truthState: "confirmed",
          valueDisplay: "Amlodipine 5mg",
          payload: { dosage: "5mg" },
          confidence: 0.98,
          contentHash: "sha256-abc123",
          isAuthoritative: true,
        },
      ];
      const result = LifeMapConflictProvenanceHelper.classifyContradiction(singleSource);
      expect(result.severity).toBe("advisory");
      expect(result.type).toBe("duplicate_suspicion");
    });

    it("flags critical contradiction when Hospital EMR disagrees with Patient Portal / Device", () => {
      const sources: ContradictionSource[] = [
        {
          sourceId: "src-emr",
          sourceType: "EMR_INTEGRATION",
          attribution: "BV Bạch Mai",
          occurredAt: "2026-08-01T08:00:00Z",
          recordedAt: "2026-08-01T09:00:00Z",
          revision: 1,
          truthState: "confirmed",
          valueDisplay: "Amlodipine 5mg 1 viên/ngày",
          payload: { dosage: "5mg" },
          confidence: 0.99,
          contentHash: "sha256-emr",
          isAuthoritative: true,
        },
        {
          sourceId: "src-patient",
          sourceType: "PATIENT_PORTAL",
          attribution: "Bệnh nhân tự nhập",
          occurredAt: "2026-08-01T08:30:00Z",
          recordedAt: "2026-08-01T08:35:00Z",
          revision: 1,
          truthState: "user_reported",
          valueDisplay: "Amlodipine 10mg 2 viên/ngày",
          payload: { dosage: "10mg" },
          confidence: 0.8,
          contentHash: "sha256-user",
          isAuthoritative: false,
        },
      ];
      const result = LifeMapConflictProvenanceHelper.classifyContradiction(sources);
      expect(result.severity).toBe("critical");
      expect(result.type).toBe("contradiction");
      expect(result.summaryVi).toContain("Bất đồng giữa dữ liệu bệnh viện (EMR)");
    });

    it("identifies temporal drift when valid time delta exceeds 48 hours", () => {
      const sources: ContradictionSource[] = [
        {
          sourceId: "src-1",
          sourceType: "DOCUMENT_OCR",
          attribution: "Phiếu xét nghiệm",
          occurredAt: "2026-08-01T08:00:00Z",
          recordedAt: "2026-08-01T09:00:00Z",
          revision: 1,
          truthState: "confirmed",
          valueDisplay: "Glucose 100 mg/dL",
          payload: { glucose: 100 },
          confidence: 0.95,
          contentHash: "sha256-1",
          isAuthoritative: false,
        },
        {
          sourceId: "src-2",
          sourceType: "DOCUMENT_OCR",
          attribution: "Phiếu khám phòng khám",
          occurredAt: "2026-08-05T08:00:00Z", // 4 days later
          recordedAt: "2026-08-05T09:00:00Z",
          revision: 1,
          truthState: "confirmed",
          valueDisplay: "Glucose 140 mg/dL",
          payload: { glucose: 140 },
          confidence: 0.92,
          contentHash: "sha256-2",
          isAuthoritative: false,
        },
      ];
      const result = LifeMapConflictProvenanceHelper.classifyContradiction(sources);
      expect(result.severity).toBe("warning");
      expect(result.type).toBe("temporal_drift");
      expect(result.summaryVi).toContain("Độ lệch thời gian thực tế");
    });
  });

  describe("Resolution Execution & Concurrency Headers", () => {
    it("constructs optimistic concurrency headers with If-Match and Idempotency-Key", () => {
      const headers = LifeMapConflictProvenanceHelper.buildResolutionHeaders(3, "custom-key");
      expect(headers["If-Match"]).toBe("3");
      expect(headers["Idempotency-Key"]).toBe("custom-key");
    });

    it("executes 'accept_source' resolution and delegates to resolveLifeMapEvent", async () => {
      vi.mocked(lifemapApi.resolveLifeMapEvent).mockResolvedValue(undefined);

      const input: ResolutionActionInput = {
        conflictId: "cnf-01",
        eventId: "evt-100",
        currentRevision: 2,
        action: "accept_source",
        chosenSourceId: "src-emr",
        reason: "Xác nhận số đo chính thức từ khoa Tim mạch.",
      };

      const result = await LifeMapConflictProvenanceHelper.executeResolution(input);
      expect(result.status).toBe("resolved");
      expect(result.auditReceiptId).toBeDefined();
      expect(lifemapApi.resolveLifeMapEvent).toHaveBeenCalledWith(
        "evt-100",
        2,
        expect.stringContaining("src-emr"),
      );
    });

    it("executes 'dispute_all' and delegates to disputeLifeMapEvent", async () => {
      vi.mocked(lifemapApi.disputeLifeMapEvent).mockResolvedValue(undefined);

      const input: ResolutionActionInput = {
        conflictId: "cnf-02",
        eventId: "evt-101",
        currentRevision: 1,
        action: "dispute_all",
        reason: "Cả 2 số đo đều không trùng khớp với triệu chứng lâm sàng.",
      };

      const result = await LifeMapConflictProvenanceHelper.executeResolution(input);
      expect(result.status).toBe("resolved");
      expect(lifemapApi.disputeLifeMapEvent).toHaveBeenCalledWith(
        "evt-101",
        1,
        expect.stringContaining("Clinical Dispute"),
      );
    });

    it("executes 'amendment' and delegates to correctLifeMapEvent", async () => {
      vi.mocked(lifemapApi.correctLifeMapEvent).mockResolvedValue(undefined);

      const input: ResolutionActionInput = {
        conflictId: "cnf-03",
        eventId: "evt-102",
        currentRevision: 4,
        action: "amendment",
        reason: "Bác sĩ điều chỉnh lại phác đồ sau đối chiếu.",
        amendmentPayload: { dosage: "7.5mg" },
      };

      const result = await LifeMapConflictProvenanceHelper.executeResolution(input);
      expect(result.status).toBe("resolved");
      expect(lifemapApi.correctLifeMapEvent).toHaveBeenCalledWith(
        "evt-102",
        4,
        { dosage: "7.5mg" },
        "Bác sĩ điều chỉnh lại phác đồ sau đối chiếu.",
      );
    });

    it("executes 'dismiss' and delegates to actOnLifeMapReviewFinding", async () => {
      vi.mocked(lifemapApi.actOnLifeMapReviewFinding).mockResolvedValue({
        id: "find-01",
        kind: "contradiction",
        field_key: "dosage",
        reason_code: "dup",
        proposal_source: "rule",
        revision_ids: ["r1", "r2"],
        rule_version: "v1",
        status: "dismissed",
        resolution_reason: "Không ảnh hưởng",
        requires_human_resolution: false,
      });

      const input: ResolutionActionInput = {
        conflictId: "find-01",
        eventId: "evt-103",
        currentRevision: 1,
        action: "dismiss",
        reason: "Không ảnh hưởng",
      };

      const result = await LifeMapConflictProvenanceHelper.executeResolution(input);
      expect(result.status).toBe("dismissed");
      expect(lifemapApi.actOnLifeMapReviewFinding).toHaveBeenCalledWith(
        "find-01",
        "dismissed",
        "Không ảnh hưởng",
      );
    });

    it("throws error when resolution reason fails validation", async () => {
      const input: ResolutionActionInput = {
        conflictId: "cnf-invalid",
        eventId: "evt-104",
        currentRevision: 1,
        action: "accept_source",
        reason: "",
      };

      await expect(
        LifeMapConflictProvenanceHelper.executeResolution(input),
      ).rejects.toThrow("Vui lòng nhập lý do");
    });
  });
});
