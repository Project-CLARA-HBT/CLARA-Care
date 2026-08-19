import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import axios, { AxiosInstance } from "axios";
import {
  ApiV2Client,
  ApiV2ClientError,
  formatEtag,
  normalizeApiV2Error,
  parseEtag,
} from "./v2-client";
import * as authStore from "@/lib/auth-store";
import * as profileContext from "@/lib/profile-context";

describe("ETag Helpers", () => {
  it("formats strong and weak ETags correctly", () => {
    expect(formatEtag("42")).toBe('"42"');
    expect(formatEtag('"42"')).toBe('"42"');
    expect(formatEtag(100)).toBe('"100"');
    expect(formatEtag("5", true)).toBe('W/"5"');
    expect(formatEtag('W/"5"', true)).toBe('W/"5"');
  });

  it("parses ETags stripping quotes and weak prefixes", () => {
    expect(parseEtag('"42"')).toBe("42");
    expect(parseEtag('W/"42"')).toBe("42");
    expect(parseEtag("42")).toBe("42");
    expect(parseEtag(null)).toBeNull();
    expect(parseEtag(undefined)).toBeNull();
    expect(parseEtag("   ")).toBeNull();
  });
});

describe("Error Normalization", () => {
  it("returns ApiV2ClientError as-is if already normalized", () => {
    const err = new ApiV2ClientError({
      message: "Custom error",
      code: "CUSTOM",
      status: 400,
    });
    expect(normalizeApiV2Error(err)).toBe(err);
  });

  it("normalizes cancellation / abort errors", () => {
    const abortErr = new Error("The operation was aborted");
    abortErr.name = "AbortError";
    const normalized = normalizeApiV2Error(abortErr);
    expect(normalized.isCancelled).toBe(true);
    expect(normalized.code).toBe("CANCELLED");
    expect(normalized.status).toBe(0);
  });

  it("normalizes network and timeout errors", () => {
    const timeoutErr = {
      isAxiosError: true,
      name: "AxiosError",
      message: "timeout of 5000ms exceeded",
      code: "ECONNABORTED",
    };
    const normalizedTimeout = normalizeApiV2Error(timeoutErr);
    expect(normalizedTimeout.isNetworkError).toBe(true);
    expect(normalizedTimeout.code).toBe("TIMEOUT");

    const netErr = {
      isAxiosError: true,
      name: "AxiosError",
      message: "Network Error",
      code: "ERR_NETWORK",
    };
    const normalizedNet = normalizeApiV2Error(netErr);
    expect(normalizedNet.isNetworkError).toBe(true);
    expect(normalizedNet.code).toBe("NETWORK_ERROR");
  });

  it("normalizes structured ApiV2ErrorEnvelope responses", () => {
    const envelopeErr = {
      isAxiosError: true,
      name: "AxiosError",
      response: {
        status: 409,
        data: {
          code: "state_conflict",
          message_key: "errors.state_conflict",
          message: "Conflict detected",
          params: { resource: "profile" },
          details: { diff: ["name"] },
          safe_to_reapply: false,
          current_version: "v5",
          changed_fields: ["name"],
        },
      },
    };
    const normalized = normalizeApiV2Error(envelopeErr);
    expect(normalized.isConflict).toBe(true);
    expect(normalized.code).toBe("state_conflict");
    expect(normalized.messageKey).toBe("errors.state_conflict");
    expect(normalized.message).toBe("Conflict detected");
    expect(normalized.safeToReapply).toBe(false);
    expect(normalized.currentVersion).toBe("v5");
    expect(normalized.changedFields).toEqual(["name"]);
    expect(normalized.status).toBe(409);
  });

  it("normalizes FastAPI validation error array details", () => {
    const fastApiValErr = {
      isAxiosError: true,
      name: "AxiosError",
      response: {
        status: 422,
        data: {
          detail: [
            { loc: ["body", "base_version"], msg: "Field required", type: "missing" },
          ],
        },
      },
    };
    const normalized = normalizeApiV2Error(fastApiValErr);
    expect(normalized.isValidationError).toBe(true);
    expect(normalized.code).toBe("validation_error");
    expect(Array.isArray(normalized.details)).toBe(true);
  });

  it("normalizes gateway 502/503/504 HTML errors into friendly messages", () => {
    const gwErr = {
      isAxiosError: true,
      name: "AxiosError",
      response: {
        status: 502,
        data: "<html><body>502 Bad Gateway</body></html>",
      },
    };
    const normalized = normalizeApiV2Error(gwErr);
    expect(normalized.status).toBe(502);
    expect(normalized.message).toContain("502");
  });
});

describe("ApiV2Client Header Injection and Request Handling", () => {
  let mockAxios: {
    request: ReturnType<typeof vi.fn>;
  };
  let client: ApiV2Client;

  beforeEach(() => {
    mockAxios = {
      request: vi.fn(),
    };
    client = new ApiV2Client("http://localhost:8000/api/v2", mockAxios as unknown as AxiosInstance);

    vi.spyOn(authStore, "getCsrfToken").mockReturnValue("test-csrf-token");
    vi.spyOn(profileContext, "getActiveProfileId").mockReturnValue("profile-123");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("injects profile context header automatically", async () => {
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: { data: { success: true } },
    });

    const res = await client.get("/home");
    expect(mockAxios.request).toHaveBeenCalledTimes(1);
    const callConfig = mockAxios.request.mock.calls[0][0];

    expect(callConfig.headers["X-CLARA-Profile-Context"]).toBe("profile-123");
    expect(res.data).toEqual({ success: true });
  });

  it("allows overriding profileId in options or skipping profile context", async () => {
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: { success: true },
    });

    await client.get("/home", { profileId: "custom-profile-456" });
    let callConfig = mockAxios.request.mock.calls[0][0];
    expect(callConfig.headers["X-CLARA-Profile-Context"]).toBe("custom-profile-456");

    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: { success: true },
    });
    await client.get("/home", { skipProfileContext: true });
    callConfig = mockAxios.request.mock.calls[1][0];
    expect(callConfig.headers["X-CLARA-Profile-Context"]).toBeUndefined();
  });

  it("injects CSRF token for mutating methods and omits for GET", async () => {
    mockAxios.request.mockResolvedValue({
      status: 200,
      headers: {},
      data: { ok: true },
    });

    // 1. GET -> no CSRF
    await client.get("/health/timeline");
    expect(mockAxios.request.mock.calls[0][0].headers["X-CSRF-Token"]).toBeUndefined();

    // 2. POST -> attaches CSRF
    await client.post("/health/allergies", { name: "Peanuts" });
    expect(mockAxios.request.mock.calls[1][0].headers["X-CSRF-Token"]).toBe("test-csrf-token");

    // 3. PATCH -> attaches CSRF
    await client.patch("/health/demographics", { age: 30 });
    expect(mockAxios.request.mock.calls[2][0].headers["X-CSRF-Token"]).toBe("test-csrf-token");

    // 4. DELETE -> attaches CSRF
    await client.delete("/health/allergies/1");
    expect(mockAxios.request.mock.calls[3][0].headers["X-CSRF-Token"]).toBe("test-csrf-token");
  });

  it("injects ETag / base_version as If-Match header and Idempotency-Key", async () => {
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: { etag: '"v4"' },
      data: {
        data: { updated: true },
        meta: { server_version: "2.0" },
      },
    });

    const res = await client.patch(
      "/health/allergies/1",
      { severity: "high" },
      {
        baseVersion: "v3",
        idempotencyKey: "cmd-idemp-123",
      },
    );

    const callConfig = mockAxios.request.mock.calls[0][0];
    expect(callConfig.headers["If-Match"]).toBe('"v3"');
    expect(callConfig.headers["Idempotency-Key"]).toBe("cmd-idemp-123");
    expect(res.etag).toBe("v4");
    expect(res.data).toEqual({ updated: true });
    expect(res.meta).toEqual({ server_version: "2.0" });
  });

  it("unwraps ApiV2ResponseEnvelopeDto and exposes data and metadata", async () => {
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: { "x-request-id": "req-1" },
      data: {
        data: { id: "item-1", title: "Test Item" },
        meta: { total: 1 },
        message: { key: "messages.loaded", severity: "info" },
        warnings: [{ key: "warnings.slow", severity: "warning" }],
      },
    });

    const res = await client.get<{ id: string; title: string }>("/items/item-1");
    expect(res.data).toEqual({ id: "item-1", title: "Test Item" });
    expect(res.meta).toEqual({ total: 1 });
    expect(res.message?.key).toBe("messages.loaded");
    expect(res.warnings?.[0].key).toBe("warnings.slow");
    expect(res.headers["x-request-id"]).toBe("req-1");
  });

  it("fetchData directly returns payload data", async () => {
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: { data: [1, 2, 3] },
    });

    const items = await client.fetchData<number[]>("/numbers");
    expect(items).toEqual([1, 2, 3]);
  });

  it("getHome fetches profile-scoped home overview payload", async () => {
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: {
          profile: { id: "p-123", display_name: "Nguyen" },
          today: [],
          recent_changes: [],
          alerts: [],
        },
      },
    });

    const homeData = await client.getHome("p-123");
    expect(homeData.profile?.display_name).toBe("Nguyen");
    expect(mockAxios.request).toHaveBeenCalledWith(
      expect.objectContaining({
        url: "/home",
        method: "GET",
        headers: expect.objectContaining({
          "X-CLARA-Profile-Context": "p-123",
        }),
      }),
    );
  });

  it("getHealthSummary fetches profile-scoped health summary", async () => {
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: {
          current: {
            allergies: [{ id: "a1", substance: "Peanut", severity: "severe" }],
            conditions: [{ id: "c1", name: "Hypertension", clinical_status: "active" }],
            medications: [],
            important_measurements: [],
          },
          recent_results: [],
          documents: [],
          conflicts: [],
        },
      },
    });

    const summary = await client.getHealthSummary("p-123");
    expect(summary.current.allergies).toHaveLength(1);
    expect(summary.current.conditions[0].name).toBe("Hypertension");
    expect(mockAxios.request).toHaveBeenCalledWith(
      expect.objectContaining({
        url: "/health/summary",
        method: "GET",
        headers: expect.objectContaining({
          "X-CLARA-Profile-Context": "p-123",
        }),
      }),
    );
  });

  it("getHealthTimeline serializes query parameters properly", async () => {
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: {
          items: [{ id: "ev-1", title: "Blood Test", kind: "result", effective_at: "2026-08-19" }],
          next_cursor: "cursor-2",
        },
      },
    });

    const timeline = await client.getHealthTimeline(
      {
        cursor: "cursor-1",
        period: "month",
        types: ["result", "medication"],
        search: "glucose",
        limit: 15,
      },
      "p-123",
    );

    expect(timeline.items).toHaveLength(1);
    expect(timeline.next_cursor).toBe("cursor-2");
    expect(mockAxios.request).toHaveBeenCalledWith(
      expect.objectContaining({
        url: "/health/timeline",
        method: "GET",
        params: expect.objectContaining({
          cursor: "cursor-1",
          period: "month",
          types: "result,medication",
          search: "glucose",
          limit: 15,
        }),
        headers: expect.objectContaining({
          "X-CLARA-Profile-Context": "p-123",
        }),
      }),
    );
  });

  it("executes bounded writes with ETag/base_version for demographics, allergies, conditions, and measurements", async () => {
    // 1. updateDemographics
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: { etag: '"v2"' },
      data: { data: { full_name: "Nguyen Van B", blood_type: "O+" } },
    });
    const updatedDemo = await client.updateDemographics(
      { full_name: "Nguyen Van B", blood_type: "O+", base_version: "v1" },
    );
    expect(updatedDemo.full_name).toBe("Nguyen Van B");
    expect(mockAxios.request.mock.calls[0][0].headers["If-Match"]).toBe('"v1"');
    expect(mockAxios.request.mock.calls[0][0].headers["X-CSRF-Token"]).toBe("test-csrf-token");

    // 2. addAllergy
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: { data: { id: "a2", substance: "Pollen", severity: "mild" } },
    });
    const newAllergy = await client.addAllergy({ substance: "Pollen", severity: "mild" });
    expect(newAllergy.id).toBe("a2");
    expect(mockAxios.request.mock.calls[1][0].url).toBe("/health/allergies");

    // 3. updateAllergy
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: { data: { id: "a2", substance: "Pollen", severity: "moderate" } },
    });
    const updatedAllergy = await client.updateAllergy("a2", { severity: "moderate", base_version: "v2" });
    expect(updatedAllergy.severity).toBe("moderate");
    expect(mockAxios.request.mock.calls[2][0].url).toBe("/health/allergies/a2");
    expect(mockAxios.request.mock.calls[2][0].headers["If-Match"]).toBe('"v2"');

    // 4. deleteAllergy
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: { data: { success: true } },
    });
    const delAllergy = await client.deleteAllergy("a2");
    expect(delAllergy.success).toBe(true);
    expect(mockAxios.request.mock.calls[3][0].method).toBe("DELETE");

    // 5. addCondition
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: { data: { id: "c2", name: "Asthma", clinical_status: "active" } },
    });
    const newCond = await client.addCondition({ name: "Asthma", clinical_status: "active" });
    expect(newCond.id).toBe("c2");

    // 6. updateCondition
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: { data: { id: "c2", name: "Asthma", clinical_status: "resolved" } },
    });
    const updatedCond = await client.updateCondition("c2", { clinical_status: "resolved", base_version: "v3" });
    expect(updatedCond.clinical_status).toBe("resolved");

    // 7. deleteCondition
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: { data: { success: true } },
    });
    const delCond = await client.deleteCondition("c2");
    expect(delCond.success).toBe(true);

    // 8. addMeasurement
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: { data: { id: "m1", type: "blood_pressure", systolic: 120, diastolic: 80, unit: "mmHg", recorded_at: "2026-08-19" } },
    });
    const newMeas = await client.addMeasurement({
      type: "blood_pressure",
      value: "120/80",
      systolic: 120,
      diastolic: 80,
      unit: "mmHg",
      recorded_at: "2026-08-19",
    });
    expect(newMeas.id).toBe("m1");

    // 9. ask
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: {
          answer: { main_message: "Uống thuốc theo đơn", actions: [], sections: [] },
          safety: { urgency: "routine" },
        },
      },
    });
    const askRes = await client.ask({
      text: "Khi nào uống thuốc?",
      entry_context: { kind: "medication", resource_id: "med-1", label: "Aspirin" },
    });
    expect(askRes.answer.main_message).toBe("Uống thuốc theo đơn");
    expect(askRes.safety?.urgency).toBe("routine");
  });

  it("streamAsk handles SSE events and invokes callbacks correctly", async () => {
    const sseChunks = [
      "event: start\ndata: {}\n\n",
      'event: token\ndata: {"text":"Xin "}\n\n',
      'event: token\ndata: {"text":"chào"}\n\n',
      'event: safety\ndata: {"urgency":"routine","guidance":"Theo dõi thêm"}\n\n',
      'event: evidence\ndata: {"personal_evidence":[{"id":"pe1","title":"Aspirin"}],"disclosure":{"used_personal_context":true,"data_classes":["medications"]}}\n\n',
      'event: proposals\ndata: [{"id":"wp1","kind":"medication","title":"Paracetamol"}]\n\n',
      'event: unknowns\ndata: [{"missing_factor":"Liều dùng"}]\n\n',
      'event: done\ndata: {"answer":{"main_message":"Xin chào"}}\n\n',
    ];

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        for (const chunk of sseChunks) {
          controller.enqueue(encoder.encode(chunk));
        }
        controller.close();
      },
    });

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: stream,
    });
    globalThis.fetch = mockFetch;

    const tokens: string[] = [];
    let receivedSafety: any = null;
    let receivedEvidence: any = null;
    let receivedProposals: any = null;
    let receivedUnknowns: any = null;
    let doneEnvelope: any = null;

    await client.streamAsk(
      { text: "Chào CLARA" },
      {
        onToken: (t) => tokens.push(t),
        onSafety: (s) => (receivedSafety = s),
        onEvidence: (e) => (receivedEvidence = e),
        onProposals: (p) => (receivedProposals = p),
        onUnknowns: (u) => (receivedUnknowns = u),
        onDone: (env) => (doneEnvelope = env),
      },
    );

    expect(tokens).toEqual(["Xin ", "chào"]);
    expect(receivedSafety?.urgency).toBe("routine");
    expect(receivedEvidence?.personal_evidence?.[0].title).toBe("Aspirin");
    expect(receivedProposals?.[0].title).toBe("Paracetamol");
    expect(receivedUnknowns?.[0].missing_factor).toBe("Liều dùng");
    expect(doneEnvelope?.answer?.main_message).toBe("Xin chào");
  });

  it("streamAsk falls back to non-streaming ask when SSE endpoint returns 404", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      body: null,
    });
    globalThis.fetch = mockFetch;

    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: {
          answer: { main_message: "Fallback response", actions: [], sections: [] },
          safety: { urgency: "none" },
        },
      },
    });

    let mainMsg = "";
    let doneEnv: any = null;

    await client.streamAsk(
      { text: "Fallback test" },
      {
        onMainMessage: (m) => (mainMsg = m),
        onDone: (env) => (doneEnv = env),
      },
    );

    expect(mainMsg).toBe("Fallback response");
    expect(doneEnv?.answer?.main_message).toBe("Fallback response");
  });

  it("handles capture lifecycle methods: create, upload, get, review, and commit", async () => {
    // 1. createCaptureSession
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: {
          id: "cap-sess-1",
          input_kind: "upload",
          status: "draft",
          candidates: [],
        },
      },
    });

    const session = await client.createCaptureSession({ input_kind: "upload", locale: "vi" });
    expect(session.id).toBe("cap-sess-1");
    expect(mockAxios.request).toHaveBeenLastCalledWith(
      expect.objectContaining({
        url: "/capture/sessions",
        method: "POST",
        data: { input_kind: "upload", locale: "vi" },
      }),
    );

    // 2. uploadCaptureArtifact
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: {
          id: "art-1",
          media_type: "image/png",
          filename: "prescription.png",
        },
      },
    });

    const fakeFile = new File(["dummy content"], "prescription.png", { type: "image/png" });
    const artifact = await client.uploadCaptureArtifact("cap-sess-1", fakeFile);
    expect(artifact.id).toBe("art-1");
    expect(mockAxios.request).toHaveBeenLastCalledWith(
      expect.objectContaining({
        url: "/capture/sessions/cap-sess-1/artifacts",
        method: "POST",
        data: expect.any(FormData),
      }),
    );

    // 3. getCaptureSession
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: {
          id: "cap-sess-1",
          status: "ready",
          candidates: [
            {
              id: "cand-1",
              category: "medication",
              field_name: "medication_name",
              value: "Panadol 500mg",
              status: "pending",
            },
          ],
        },
      },
    });

    const fetchedSession = await client.getCaptureSession("cap-sess-1");
    expect(fetchedSession.status).toBe("ready");
    expect(fetchedSession.candidates).toHaveLength(1);
    expect(mockAxios.request).toHaveBeenLastCalledWith(
      expect.objectContaining({
        url: "/capture/sessions/cap-sess-1",
        method: "GET",
      }),
    );

    // 4. reviewCaptureCandidate
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: {
          id: "cand-1",
          category: "medication",
          field_name: "medication_name",
          value: "Panadol Extra",
          status: "edited",
        },
      },
    });

    const reviewed = await client.reviewCaptureCandidate("cand-1", "edit", {
      value: "Panadol Extra",
      reason: "User modified name",
    });
    expect(reviewed.status).toBe("edited");
    expect(mockAxios.request).toHaveBeenLastCalledWith(
      expect.objectContaining({
        url: "/capture/candidates/cand-1/review",
        method: "POST",
        data: { action: "edit", value: "Panadol Extra", reason: "User modified name" },
      }),
    );

    // 5. commitCaptureSession
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: {
          success: true,
          committed_count: 1,
          target_section: "medications",
          redirect_url: "/health/medications",
        },
      },
    });

    const commitRes = await client.commitCaptureSession("cap-sess-1", {
      candidate_ids: ["cand-1"],
      target_section: "medications",
    });
    expect(commitRes.success).toBe(true);
    expect(commitRes.committed_count).toBe(1);
    expect(mockAxios.request).toHaveBeenLastCalledWith(
      expect.objectContaining({
        url: "/capture/sessions/cap-sess-1/commit",
        method: "POST",
        data: { candidate_ids: ["cand-1"], target_section: "medications" },
      }),
    );
  });

  it("handles care, visit preparation, symptom check, and medication safety client methods", async () => {
    // 1. getCareSummary
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: {
          upcoming_visits: [{ id: "v1", title: "Cardiology Visit", scheduled_at: "2026-08-25" }],
          prep_prompts: [{ id: "p1", title: "Prepare questions", action_href: "/care/prepare" }],
          active_tasks: [{ id: "t1", title: "Measure BP" }],
        },
      },
    });

    const careSummary = await client.getCareSummary("profile-123");
    expect(careSummary.upcoming_visits).toHaveLength(1);
    expect(careSummary.prep_prompts).toHaveLength(1);
    expect(careSummary.active_tasks).toHaveLength(1);
    expect(mockAxios.request).toHaveBeenLastCalledWith(
      expect.objectContaining({
        url: "/care/summary",
        method: "GET",
        headers: expect.objectContaining({ "X-CLARA-Profile-Context": "profile-123" }),
      }),
    );

    // 2. getVisits
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: [
          { id: "v1", title: "Cardiology Visit", scheduled_at: "2026-08-25", status: "scheduled" },
        ],
      },
    });

    const visits = await client.getVisits({ status: "scheduled" }, "profile-123");
    expect(visits).toHaveLength(1);
    expect(mockAxios.request).toHaveBeenLastCalledWith(
      expect.objectContaining({
        url: "/care/visits",
        method: "GET",
        params: { status: "scheduled" },
      }),
    );

    // 3. createVisit
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: { id: "v2", title: "Endocrinology Visit", scheduled_at: "2026-09-01", status: "scheduled" },
      },
    });

    const createdVisit = await client.createVisit({
      title: "Endocrinology Visit",
      scheduled_at: "2026-09-01",
    });
    expect(createdVisit.id).toBe("v2");
    expect(mockAxios.request).toHaveBeenLastCalledWith(
      expect.objectContaining({
        url: "/care/visits",
        method: "POST",
        data: { title: "Endocrinology Visit", scheduled_at: "2026-09-01" },
      }),
    );

    // 4. prepareVisit
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: {
          visit_id: "v1",
          purpose: "Cardiology follow-up",
          summary: "Summary ready",
          what_changed: ["Stable BP"],
          patient_questions: ["Can I reduce dosage?"],
          patient_goals: ["Understand labs"],
          created_at: "2026-08-20",
        },
      },
    });

    const prepResult = await client.prepareVisit("v1", {
      purpose: "Cardiology follow-up",
      changes_since_last_visit: ["Stable BP"],
      questions: ["Can I reduce dosage?"],
      goals: ["Understand labs"],
    });
    expect(prepResult.purpose).toBe("Cardiology follow-up");
    expect(prepResult.patient_questions).toContain("Can I reduce dosage?");
    expect(mockAxios.request).toHaveBeenLastCalledWith(
      expect.objectContaining({
        url: "/care/visits/v1/prepare",
        method: "POST",
      }),
    );

    // 5. checkSymptoms
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: {
          urgency: "routine",
          is_red_flag_emergency: false,
          title: "Routine Consultation",
          explanation: "Symptoms should be evaluated routinely.",
          care_navigation_guidance: "Book a specialist visit.",
          recommended_actions: ["Rest and monitor"],
          clinician_handoff_summary: "Headache for 2 days.",
          questions_for_doctor: ["What caused this?"],
          when_to_seek_immediate_care: ["Severe sudden onset"],
        },
      },
    });

    const triageResult = await client.checkSymptoms({
      symptoms: ["Headache"],
      duration: "1_3_days",
      severity: "moderate",
    });
    expect(triageResult.urgency).toBe("routine");
    expect(triageResult.is_red_flag_emergency).toBe(false);
    expect(mockAxios.request).toHaveBeenLastCalledWith(
      expect.objectContaining({
        url: "/care/check-symptoms",
        method: "POST",
      }),
    );

    // 6. getMedicationsHub
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: {
          medications: [{ id: "m1", name: "Amlodipine", status: "active" }],
          cabinet: [{ id: "cab1", name: "Panadol" }],
          safety_alerts: [],
        },
      },
    });

    const medHub = await client.getMedicationsHub("profile-123");
    expect(medHub.medications).toHaveLength(1);
    expect(medHub.cabinet).toHaveLength(1);
    expect(mockAxios.request).toHaveBeenLastCalledWith(
      expect.objectContaining({
        url: "/health/medications/hub",
        method: "GET",
      }),
    );

    // 7. checkMedicationSafety
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: {
          has_critical_ddi: false,
          safety_score: 95,
          interactions: [{ severity: "info", title: "Food interaction", description: "Take with meals" }],
        },
      },
    });

    const safetyRes = await client.checkMedicationSafety({
      medication_ids: ["m1"],
      new_medication_name: "Ibuprofen",
    });
    expect(safetyRes.has_critical_ddi).toBe(false);
    expect(safetyRes.interactions).toHaveLength(1);
    expect(mockAxios.request).toHaveBeenLastCalledWith(
      expect.objectContaining({
        url: "/health/medications/safety-check",
        method: "POST",
      }),
    );
  });

  it("handles you, profile, emergency card, sharing, privacy, integrations, and notification methods", async () => {
    // 1. getYouOverview
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: {
          emergency_card: { allergies_count: 2, conditions_count: 1, medications_count: 3, medical_alerts: ["Dị ứng nặng Penicillin"], is_configured: true },
          family_sharing: { active_grants_count: 2, received_grants_count: 1, pending_invites_count: 0, members: [] },
          privacy_ai: { data_classes_used: ["medications", "conditions"], ai_features_enabled: true, cot_disabled: true, retention_policy_days: 90, consent_status: "granted" },
          integrations: { total_connected: 2, sources: [] },
          professional_mode: { eligible: true, role: "doctor" },
        },
      },
    });

    const youOverview = await client.getYouOverview("profile-123");
    expect(youOverview.emergency_card.allergies_count).toBe(2);
    expect(youOverview.family_sharing.active_grants_count).toBe(2);
    expect(youOverview.privacy_ai.cot_disabled).toBe(true);
    expect(mockAxios.request).toHaveBeenLastCalledWith(
      expect.objectContaining({
        url: "/you/overview",
        method: "GET",
        headers: expect.objectContaining({ "X-CLARA-Profile-Context": "profile-123" }),
      }),
    );

    // 2. getProfileDetails & updateProfileDetails
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: {
          id: "profile-123",
          display_name: "Nguyễn Văn A",
          blood_type: "O+",
          medical_alerts: ["Dị ứng Penicillin"],
        },
      },
    });
    const profileDetails = await client.getProfileDetails("profile-123");
    expect(profileDetails.display_name).toBe("Nguyễn Văn A");

    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: { id: "profile-123", display_name: "Nguyễn Văn B", blood_type: "A+" },
      },
    });
    const updatedProfile = await client.updateProfileDetails({ display_name: "Nguyễn Văn B" });
    expect(updatedProfile.display_name).toBe("Nguyễn Văn B");

    // 3. getEmergencyCard & updateEmergencyCard
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: {
          blood_type: "O+",
          allergies: [{ name: "Aspirin", severity: "severe" }],
          current_medications: [{ name: "Amlodipine", dose: "5mg" }],
          conditions: [{ name: "Tăng huyết áp" }],
          included_fields: { allergies: true, current_medications: true, conditions: true, blood_type: true, emergency_contact: true },
        },
      },
    });
    const emCard = await client.getEmergencyCard("profile-123");
    expect(emCard.allergies).toHaveLength(1);

    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: {
          blood_type: "O+",
          allergies: [{ name: "Aspirin", severity: "severe" }],
          current_medications: [],
          conditions: [],
          included_fields: { allergies: true, current_medications: false, conditions: false, blood_type: true, emergency_contact: true },
        },
      },
    });
    const updatedEmCard = await client.updateEmergencyCard({ blood_type: "O+" });
    expect(updatedEmCard.included_fields.current_medications).toBe(false);

    // 4. sharing overview, create grant, revoke grant, access logs
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: {
          grants: [{ id: "g1", grantee_name: "Trần Thị B", grantee_relationship: "spouse", categories: ["medications"], allowed_actions: ["view"], purpose: "care_coordination", status: "active", created_at: "2026-08-19", expires_at: "2026-09-19" }],
          received_grants: [],
          access_logs: [{ id: "l1", actor_name: "Trần Thị B", actor_role: "caregiver", action: "view", object_type: "medications", accessed_at: "2026-08-19T10:00:00Z", outcome: "allowed" }],
        },
      },
    });
    const sharingOverview = await client.getSharingOverview("profile-123");
    expect(sharingOverview.grants).toHaveLength(1);
    expect(sharingOverview.access_logs).toHaveLength(1);

    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: { id: "g2", grantee_name: "Lê Văn C", grantee_relationship: "child", categories: ["medications", "allergies"], allowed_actions: ["view"], purpose: "visit_support", status: "active", created_at: "2026-08-19", expires_at: "2026-09-19" },
      },
    });
    const newGrant = await client.createSharingGrant({
      grantee_name: "Lê Văn C",
      grantee_relationship: "child",
      categories: ["medications", "allergies"],
      allowed_actions: ["view"],
      purpose: "visit_support",
      duration_days: 30,
    });
    expect(newGrant.grantee_name).toBe("Lê Văn C");

    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: { success: true, revoked_at: "2026-08-19T10:30:00Z" },
      },
    });
    const revokeRes = await client.revokeSharingGrant("g1");
    expect(revokeRes.success).toBe(true);

    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: [{ id: "l2", actor_name: "BS An", actor_role: "doctor", action: "view", object_type: "emergency_card", accessed_at: "2026-08-19", outcome: "allowed" }],
      },
    });
    const logs = await client.getSharingAccessLogs("profile-123");
    expect(logs).toHaveLength(1);

    // 5. AI transparency & preferences
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: {
          data_classes_used: [{ key: "meds", name: "Thuốc", purpose: "DDI check", sensitive: true }],
          retention_policy: { days: 90, description: "90 days", auto_delete_enabled: true },
          cot_zero_disclosure: { operates_without_cot: true, description: "No CoT stored", verified_guardrails: ["FIDES"] },
          ai_feature_controls: { symptom_insights_enabled: true, visit_prep_suggestions_enabled: true, medication_safety_ai_enabled: true, search_summaries_enabled: true },
          consent_status: { version: "v2.1", status: "granted", requires_reconsent: false, purposes: [] },
        },
      },
    });
    const aiTrans = await client.getAiTransparency("profile-123");
    expect(aiTrans.cot_zero_disclosure.operates_without_cot).toBe(true);

    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: { symptom_insights_enabled: false, visit_prep_suggestions_enabled: true },
      },
    });
    const updatedAiPrefs = await client.updateAiPreferences({ symptom_insights_enabled: false });
    expect(updatedAiPrefs.symptom_insights_enabled).toBe(false);

    // 6. Integrations & sync
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: {
          sources: [
            { id: "s1", name: "health_connect", title: "Health Connect", description: "Android Health Data", connected: true, sync_enabled: true, last_sync_at: "2026-08-19T08:00:00Z", status: "active", category_permissions: { steps: true, heart_rate: true, blood_pressure: true, sleep: true, blood_glucose: false, oxygen_saturation: false } },
          ],
        },
      },
    });
    const integrations = await client.getIntegrations("profile-123");
    expect(integrations.sources).toHaveLength(1);
    expect(integrations.sources[0].connected).toBe(true);

    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: { id: "s1", name: "health_connect", title: "Health Connect", description: "Android Health Data", connected: true, sync_enabled: false, last_sync_at: "2026-08-19T08:00:00Z", status: "active", category_permissions: { steps: false, heart_rate: true, blood_pressure: true, sleep: true, blood_glucose: false, oxygen_saturation: false } },
      },
    });
    const updatedIntegration = await client.updateIntegrationSource("s1", { sync_enabled: false });
    expect(updatedIntegration.sync_enabled).toBe(false);

    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: { success: true, synced_at: "2026-08-19T11:00:00Z" },
      },
    });
    const syncRes = await client.syncIntegrationSource("s1");
    expect(syncRes.success).toBe(true);

    // 7. Notifications
    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: {
          categories: { medications: true, visits: true, review_items: true, safety_alerts: true },
          channels: { push: true, email: true, in_app: true },
          quiet_hours: { enabled: true, start_time: "22:00", end_time: "07:00" },
        },
      },
    });
    const notifPrefs = await client.getNotificationPreferences("profile-123");
    expect(notifPrefs.categories.medications).toBe(true);
    expect(notifPrefs.quiet_hours.enabled).toBe(true);

    mockAxios.request.mockResolvedValueOnce({
      status: 200,
      headers: {},
      data: {
        data: {
          categories: { medications: true, visits: true, review_items: false, safety_alerts: true },
          channels: { push: true, email: true, in_app: true },
          quiet_hours: { enabled: false, start_time: "22:00", end_time: "07:00" },
        },
      },
    });
    const updatedNotif = await client.updateNotificationPreferences({
      categories: { medications: true, visits: true, review_items: false, safety_alerts: true },
    });
    expect(updatedNotif.categories.review_items).toBe(false);
  });

  it("supports cancellation via AbortSignal", async () => {
    const controller = new AbortController();
    controller.abort();

    mockAxios.request.mockImplementationOnce(() => {
      const err = new Error("canceled");
      (err as unknown as { __CANCEL__: boolean }).__CANCEL__ = true;
      return Promise.reject(err);
    });

    await expect(
      client.get("/slow-query", { signal: controller.signal }),
    ).rejects.toThrow(ApiV2ClientError);
  });
});
