import { afterEach, describe, expect, it, vi } from "vitest";

import {
  amendScribeNote,
  captureScribeConsent,
  exportScribeNote,
  generateScribeNote,
  getScribeAudit,
  getScribeCoding,
  getScribeGrounding,
  signScribeNote,
} from "@/lib/scribe";

/**
 * Web coverage for the Clara Scribe enterprise review→sign workflow HTTP clients
 * (spec `clara-scribe-enterprise`, task 3.4 — Requirements 4, 8, 9).
 *
 * The streaming client is covered by `scribe.stream.test.ts` and the pure review
 * helpers by `scribe-review.test.ts`; this file fills the remaining gap — the
 * consent → generate → sign → amend → audit → export client functions that drive
 * the sign workflow — by asserting each issues the correct method + URL + payload
 * and returns the server shape unchanged.
 */

// `vi.mock` is hoisted above module-level declarations, so the mock fns must be
// created inside `vi.hoisted` to be safely referenced by the factory below.
const { post, get, patch } = vi.hoisted(() => ({
  post: vi.fn(),
  get: vi.fn(),
  patch: vi.fn(),
}));

vi.mock("@/lib/http-client", () => ({ default: { post, get, patch } }));

afterEach(() => {
  vi.clearAllMocks();
});

describe("captureScribeConsent (Req 4)", () => {
  it("POSTs to the session consent URL and returns the consent record", async () => {
    post.mockResolvedValueOnce({ data: { session_id: 7, consent_id: 3, captured: true } });
    const result = await captureScribeConsent(7, { method: "verbal", scope: "encounter" });
    expect(post).toHaveBeenCalledWith("/scribe/sessions/7/consent", {
      method: "verbal",
      scope: "encounter",
    });
    expect(result.captured).toBe(true);
    expect(result.consent_id).toBe(3);
  });

  it("defaults to an empty payload when no consent details are given", async () => {
    post.mockResolvedValueOnce({ data: { session_id: 7, consent_id: 1, captured: true } });
    await captureScribeConsent(7);
    expect(post).toHaveBeenCalledWith("/scribe/sessions/7/consent", {});
  });
});

describe("generate → sign → amend lifecycle (Req 8)", () => {
  it("generateScribeNote POSTs the template to the notes URL and returns in_review", async () => {
    post.mockResolvedValueOnce({
      data: { id: 7, title: "t", status: "in_review", transcript: "x", created_at: "", updated_at: "" },
    });
    const session = await generateScribeNote(7, { template_id: "soap" });
    expect(post).toHaveBeenCalledWith("/scribe/sessions/7/notes", { template_id: "soap" });
    expect(session.status).toBe("in_review");
  });

  it("generateScribeNote defaults to an empty payload", async () => {
    post.mockResolvedValueOnce({
      data: { id: 7, title: "t", status: "in_review", transcript: "x", created_at: "", updated_at: "" },
    });
    await generateScribeNote(7);
    expect(post).toHaveBeenCalledWith("/scribe/sessions/7/notes", {});
  });

  it("signScribeNote POSTs an empty body to the sign URL and returns signed", async () => {
    post.mockResolvedValueOnce({
      data: { id: 7, title: "t", status: "signed", transcript: "x", created_at: "", updated_at: "" },
    });
    const session = await signScribeNote(7);
    expect(post).toHaveBeenCalledWith("/scribe/sessions/7/sign", {});
    expect(session.status).toBe("signed");
  });

  it("amendScribeNote POSTs the amend payload and returns the amended status", async () => {
    post.mockResolvedValueOnce({
      data: { id: 7, title: "t", status: "amended", transcript: "y", created_at: "", updated_at: "" },
    });
    const session = await amendScribeNote(7, { template_id: "soap", transcript: "y" });
    expect(post).toHaveBeenCalledWith("/scribe/sessions/7/amend", {
      template_id: "soap",
      transcript: "y",
    });
    expect(session.status).toBe("amended");
  });
});

describe("getScribeAudit (Req 8.4)", () => {
  it("GETs the audit URL and returns the append-only entries", async () => {
    get.mockResolvedValueOnce({
      data: {
        session_id: 7,
        entries: [
          {
            id: 1,
            actor: 42,
            action: "note_signed",
            from_status: "in_review",
            to_status: "signed",
            detail: {},
            created_at: "2026-01-01T00:00:00Z",
          },
        ],
      },
    });
    const audit = await getScribeAudit(7);
    expect(get).toHaveBeenCalledWith("/scribe/sessions/7/audit");
    expect(audit.entries).toHaveLength(1);
    expect(audit.entries[0].action).toBe("note_signed");
  });
});

describe("getScribeGrounding (Req 12.7)", () => {
  it("GETs the note-version grounding URL and returns the report shape", async () => {
    get.mockResolvedValueOnce({
      data: {
        session_id: 7,
        version_no: 2,
        grounding: {
          version: "scribe-grounding-v1",
          enabled: true,
          statements: [
            {
              statement: "BP 120/80",
              section: "objective",
              significant: true,
              critical_safety: true,
              grounded: true,
              supporting_span_ids: ["seg-0003"],
              method: "nli",
              status: "grounded",
              asserted: true,
              fact_check: "supported",
            },
          ],
          grounded_claim_rate: 1,
          unverified_candidates: [],
          total_significant: 1,
          grounded_significant: 1,
        },
      },
    });
    const result = await getScribeGrounding(7, 2);
    expect(get).toHaveBeenCalledWith("/scribe/sessions/7/notes/2/grounding");
    expect(result.version_no).toBe(2);
    expect(result.grounding.enabled).toBe(true);
    expect(result.grounding.statements[0].supporting_span_ids).toEqual(["seg-0003"]);
  });

  it("propagates a rejection so the caller can render the editor unchanged (flag off / 404)", async () => {
    get.mockRejectedValueOnce(new Error("Scribe grounding is disabled."));
    await expect(getScribeGrounding(7, 1)).rejects.toThrow("disabled");
    expect(get).toHaveBeenCalledWith("/scribe/sessions/7/notes/1/grounding");
  });
});

describe("getScribeCoding (Req 14.3/14.5)", () => {
  it("GETs the note-version coding URL and returns advisory, unselected suggestions", async () => {
    get.mockResolvedValueOnce({
      data: {
        session_id: 7,
        version_no: 2,
        coding: {
          icd: [],
          medications: [],
          interactions: [],
          advisory: true,
          em_cpt: [
            {
              code: "99214",
              kind: "E/M",
              system: "E/M",
              display: "Office visit, level 4",
              display_vi: "Khám phòng khám, mức 4",
              level: 4,
              spans: ["seg-0001"],
              rationale: "moderate MDM",
              selected: false,
              status: "advisory",
            },
          ],
        },
      },
    });
    const result = await getScribeCoding(7, 2);
    expect(get).toHaveBeenCalledWith("/scribe/sessions/7/notes/2/coding");
    expect(result.version_no).toBe(2);
    expect(result.coding.em_cpt?.[0].code).toBe("99214");
    // Nothing is auto-selected from the server (Req 14.3/14.5).
    expect(result.coding.em_cpt?.[0].selected).toBe(false);
  });

  it("propagates a rejection so the caller can render the editor unchanged (flag off / 404)", async () => {
    get.mockRejectedValueOnce(new Error("Scribe E/M+CPT coding is disabled."));
    await expect(getScribeCoding(7, 1)).rejects.toThrow("disabled");
    expect(get).toHaveBeenCalledWith("/scribe/sessions/7/notes/1/coding");
  });
});

describe("exportScribeNote (Req 9)", () => {
  it("md export GETs with format=md and returns the rendered markdown", async () => {
    get.mockResolvedValueOnce({ data: { format: "md", markdown: "# Note\nbody" } });
    const result = await exportScribeNote(7, "md");
    expect(get).toHaveBeenCalledWith("/scribe/sessions/7/export", { params: { format: "md" } });
    expect(result.format).toBe("md");
    if (result.format === "md") {
      expect(result.markdown).toContain("# Note");
    }
  });

  it("fhir export GETs with format=fhir and returns the DocumentReference JSON", async () => {
    get.mockResolvedValueOnce({
      data: { resourceType: "DocumentReference", status: "current" },
    });
    const result = await exportScribeNote(7, "fhir");
    expect(get).toHaveBeenCalledWith("/scribe/sessions/7/export", { params: { format: "fhir" } });
    expect(result.format).toBe("fhir");
    if (result.format === "fhir") {
      expect(result.document.resourceType).toBe("DocumentReference");
    }
  });

  it("docx export fetches a blob and names the file from Content-Disposition", async () => {
    const blob = new Blob([new Uint8Array([1, 2, 3])]);
    get.mockResolvedValueOnce({
      data: blob,
      headers: { "content-disposition": 'attachment; filename="clinical-note-7.docx"' },
    });
    const result = await exportScribeNote(7, "docx");
    expect(get).toHaveBeenCalledWith("/scribe/sessions/7/export", {
      params: { format: "docx" },
      responseType: "blob",
    });
    expect(result.format).toBe("docx");
    if (result.format === "docx") {
      expect(result.blob).toBe(blob);
      expect(result.filename).toBe("clinical-note-7.docx");
    }
  });

  it("docx export falls back to a default filename when no header is present", async () => {
    const blob = new Blob([new Uint8Array([9])]);
    get.mockResolvedValueOnce({ data: blob, headers: {} });
    const result = await exportScribeNote(7, "docx");
    if (result.format === "docx") {
      expect(result.filename).toBe("clinical-note-7.docx");
    }
  });

  it("defaults to md export when no format is supplied", async () => {
    get.mockResolvedValueOnce({ data: { markdown: "x" } });
    const result = await exportScribeNote(7);
    expect(get).toHaveBeenCalledWith("/scribe/sessions/7/export", { params: { format: "md" } });
    expect(result.format).toBe("md");
  });
});
