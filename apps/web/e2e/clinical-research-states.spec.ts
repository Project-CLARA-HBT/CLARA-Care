import { expect, test, type Page } from "@playwright/test";

/**
 * UI fixtures only: public-source metadata and empty owner-scoped workspaces.
 * They deliberately contain no patient, prescription, or clinical decision data.
 */
async function seedPersonalSession(page: Page) {
  await page.addInitScript(() => {
    // Council and Scribe are clinician workspaces.  The role is deliberately
    // scoped to this UI route test; authorization itself remains server-owned.
    window.localStorage.setItem("clara_role", "doctor");
    window.localStorage.setItem("clara-theme", "dark");
    window.localStorage.setItem("clara_ui_language", "vi");
  });
}

async function mockWorkspaceApi(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let payload: unknown = {};

    if (path.endsWith("/auth/consent-status")) {
      payload = { consent_type: "medical_content", required_version: "e2e", accepted: true, accepted_version: "e2e" };
    } else if (path.endsWith("/auth/me")) {
      payload = { id: 1, role: "doctor" };
    } else if (path.endsWith("/profiles/context")) {
      payload = { profiles: [{ id: "profile-e2e", kind: "self", display_name: "Tôi" }], active_profile_id: "profile-e2e", active_kind: "self", cache_scope: "profile-e2e", reset_required: false };
    } else if (path.endsWith("/lifemap/today")) {
      payload = { generated_at: "2026-08-08T00:00:00Z", tasks: [], episodes: [], pending_confirmation_count: 0 };
    } else if (path.endsWith("/evidence-subscriptions") || path.endsWith("/evidence-change-notifications")) {
      payload = [];
    } else if (path.endsWith("/research/source-hub/catalog")) {
      payload = { sources: [{ key: "pubmed", label: "PubMed", description: "Nguồn chỉ mục y văn công khai.", default_query: "guideline", supports_live_sync: true }] };
    } else if (path.endsWith("/research/source-hub/records")) {
      payload = { records: [{ id: "public-source-fixture-1", source: "pubmed", title: "Public source fixture for interface verification", query: "guideline", published_at: "2025-01-01T00:00:00Z", synced_at: "2026-08-08T00:00:00Z", metadata: {} }] };
    } else if (path.endsWith("/council/cases")) {
      payload = { items: [], total: 0 };
    } else if (path.endsWith("/scribe/sessions")) {
      payload = { items: [], total: 0 };
    } else if (path.endsWith("/scribe/analytics/summary")) {
      payload = { total_sessions: 0, completed_sessions: 0, draft_sessions: 0, sessions_today: 0, avg_transcript_chars: 0 };
    }

    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(payload) });
  });
}

async function mockEvidenceResultApi(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const method = route.request().method();
    let payload: unknown;

    if (path.endsWith("/episodes/episode-e2e/evidence-questions") && method === "POST") {
      payload = {
        id: "question-e2e",
        episode_id: "episode-e2e",
        question: "Public evidence interface verification question",
        confirmed: false,
        requires_confirmation: true,
        compiled: { missing_dimensions: [] },
      };
    } else if (path.endsWith("/evidence-questions/question-e2e") && method === "PATCH") {
      payload = {
        id: "question-e2e",
        episode_id: "episode-e2e",
        question: "Public evidence interface verification question",
        confirmed: true,
        requires_confirmation: false,
        compiled: { missing_dimensions: [] },
      };
    } else if (path.endsWith("/evidence-questions/question-e2e/run") && method === "POST") {
      payload = {
        id: "run-e2e",
        evidence_question_id: "question-e2e",
        status: "completed",
        release_status: "evidence_available",
        evidence_count: 1,
        source_class_counts: { guideline: 1 },
        uncertainty: [{ dimension: "scope", status: "review", reason: "Interface fixture; not a clinical conclusion." }],
        safe_message: "Public-source fixture available for interface verification.",
        completed_at: "2026-08-08T00:00:00Z",
      };
    } else if (path.endsWith("/evidence-runs/run-e2e/matrix")) {
      payload = {
        run_id: "run-e2e",
        release_status: "evidence_available",
        unavailable_reason: null,
        source_classes: {
          guideline: [{
            evidence_id: "public-source-fixture-1",
            title: "Public source fixture for interface verification",
            source_class: "guideline",
            study_design: "guideline",
            identifiers: { fixture: "public-source" },
            provider: "Public source fixture",
            url: "https://example.invalid/public-source-fixture",
            published_at: "2025-01-01T00:00:00Z",
            excerpt: "Static public-source metadata used only to verify the evidence matrix interface.",
          }],
        },
      };
    } else if (path.endsWith("/evidence-runs/run-e2e/applicability")) {
      payload = { status: "review", matches: [], unknowns: ["Interface fixture"], mismatches: [], critical_exclusions: [], safe_message: "Review applicability with a qualified professional." };
    } else if (path.endsWith("/evidence-runs/run-e2e/contradictions")) {
      payload = { status: "none_known", items: [], safe_message: "No contradiction is represented by this interface fixture." };
    } else {
      return route.fallback();
    }

    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(payload) });
  });
}

async function mockActiveScribeApi(page: Page) {
  const session = {
    id: 101,
    title: "Interface review session",
    status: "draft",
    transcript: "Public workflow fixture transcript. No patient data is represented.",
    soap: {
      subjective: "Interface fixture.",
      objective: "No clinical observation represented.",
      assessment: "Review-only fixture.",
      plan: "No action generated.",
    },
    insights: {},
    metadata: {},
    last_processed_at: "2026-08-08T00:00:00Z",
    created_at: "2026-08-08T00:00:00Z",
    updated_at: "2026-08-08T00:00:00Z",
  };
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/scribe/sessions/101/recording-data/capability")) {
      return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Not enabled" }) });
    }
    if (path.endsWith("/scribe/sessions/101")) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(session) });
    }
    if (path.endsWith("/scribe/sessions")) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [session], total: 1 }) });
    }
    if (path.endsWith("/scribe/analytics/summary")) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ total_sessions: 1, completed_sessions: 0, draft_sessions: 1, sessions_today: 1, avg_transcript_chars: 62 }) });
    }
    return route.fallback();
  });
}

async function mockCouncilResultApi(page: Page) {
  const councilCase = {
    id: 202,
    title: "Interface-only Council result",
    status: "completed",
    intake_mode: "text",
    transcript: "No patient data is represented by this interface fixture.",
    request: {
      symptoms: [],
      labs: {},
      medications: [],
      history: "Interface-only fixture.",
      specialist_count: 2,
      specialists: ["Review A", "Review B"],
    },
    result: {
      final_recommendation: "Interface-only output; not a clinical conclusion.",
      consensus: "Review the display hierarchy before use.",
      conflicts: ["Human review remains required for this fixture."],
      divergence: [],
      reasoning_timeline: [
        { sequence: 1, step: "intake" },
        { sequence: 2, step: "review" },
      ],
      citation_quality: { total_citations: 0, average_evidence_strength: null },
      medication_safety: {
        state: "unavailable",
        drugbank_state: "unavailable",
        drugbank_version: "",
        alert_ids: [],
        triage_floor: null,
        review_required: true,
      },
    },
    raw_result: null,
    last_run_at: "2026-08-08T00:00:00Z",
    created_at: "2026-08-08T00:00:00Z",
    updated_at: "2026-08-08T00:00:00Z",
  };
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/council/cases/202")) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(councilCase) });
    }
    return route.fallback();
  });
}

test.describe("Evidence, Source Hub, Council and Scribe states", () => {
  test.beforeEach(async ({ page }) => {
    await mockWorkspaceApi(page);
    await seedPersonalSession(page);
  });

  test("renders deliberate first-use states and a public-source result without leaking technical errors", async ({ page }) => {
    test.setTimeout(90_000);
    const routes = [
      { path: "/evidence", content: "Cần một hành trình", semantic: "text" },
      { path: "/research/source-hub", content: "Nguồn nghiên cứu", semantic: "heading" },
      { path: "/council", content: "Chưa có dữ liệu phân tích", semantic: "text" },
      { path: "/scribe", content: "Danh sách phiên", semantic: "heading" },
    ];

    for (const route of routes) {
      const response = await page.goto(route.path, { waitUntil: "domcontentloaded", timeout: 20_000 });
      expect(response?.status(), `${route.path} document status`).toBeLessThan(400);
      await expect(page.locator("main#main-content")).toBeVisible();
      // Navigation may retain an off-canvas copy of a route label at tablet and
      // mobile widths.  Use the page heading only where the product renders a
      // heading; Council intentionally exposes its empty-state label as text.
      const content = route.semantic === "heading"
        ? page.getByRole("heading", { name: route.content, exact: true }).last()
        : page.getByText(route.content, { exact: true }).last();
      await expect(content).toBeVisible();
      await expect(page.locator("body")).not.toContainText("Application error");
      await expect(page.locator("body")).not.toContainText("Traceback");
      const horizontalOverflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(horizontalOverflow, `${route.path} must keep horizontal scrolling within its local controls`).toBeLessThanOrEqual(1);
    }

    await expect(page.getByText("Chưa có phiên nào.", { exact: true })).toBeVisible();

    await page.goto("/research/source-hub", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("Kết quả nguồn nghiên cứu", { exact: true })).toBeVisible();
    await expect(page.getByText("Public source fixture for interface verification", { exact: true })).toBeVisible();
  });

  test("renders the evidence matrix only after the explicit question-review flow", async ({ page }) => {
    await mockEvidenceResultApi(page);
    await page.route("**/api/v1/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith("/lifemap/today")) {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            generated_at: "2026-08-08T00:00:00Z",
            tasks: [],
            episodes: [{ id: "episode-e2e", title: "Interface verification episode", priority: "routine" }],
            pending_confirmation_count: 0,
          }),
        });
      }
      return route.fallback();
    });

    await page.goto("/evidence", { waitUntil: "domcontentloaded" });
    await page.getByLabel("Điều bạn muốn biết").fill("Public evidence interface verification question");
    await page.getByRole("button", { name: "Lưu để xem lại" }).click();
    await page.getByRole("button", { name: "Tôi đã kiểm tra câu hỏi" }).click();
    await page.getByRole("button", { name: "Tìm bằng chứng" }).click();

    await expect(page.getByText("Kết quả bằng chứng", { exact: true })).toBeVisible();
    await expect(page.getByText("Public source fixture for interface verification", { exact: true })).toBeVisible();
    await page.getByText("Độ không chắc chắn của lần chạy này", { exact: true }).click();
    await expect(page.getByText(/Interface fixture; not a clinical conclusion\./)).toBeVisible();
    const horizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(horizontalOverflow).toBeLessThanOrEqual(1);
  });

  test("renders an active Scribe session while keeping unavailable deletion controls fail-closed", async ({ page }) => {
    await mockActiveScribeApi(page);
    await page.goto("/scribe", { waitUntil: "domcontentloaded" });

    await expect(page.getByText("Interface review session", { exact: true }).first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Bản ghi thời gian thực", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Bản nháp SOAP", exact: true })).toBeVisible();
    await expect(page.getByText("Public workflow fixture transcript. No patient data is represented.", { exact: true }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: /Xóa dữ liệu ghi âm|Delete recording data/ })).toHaveCount(0);
    const horizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(horizontalOverflow).toBeLessThanOrEqual(1);
  });

  test("renders a review-only Council result without representing it as a clinical conclusion", async ({ page }) => {
    await mockCouncilResultApi(page);
    await page.goto("/council/result?caseId=202", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: "Kết quả hội chẩn", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Tóm tắt kết quả", exact: true })).toBeVisible();
    await expect(page.getByText(/Interface-only output; not a clinical conclusion/)).toBeVisible();
    await expect(page.getByText(/Chưa thể xác nhận đầy đủ an toàn thuốc từ nguồn bắt buộc/)).toBeVisible();
    await expect(page.getByText(/Human review remains required for this fixture/)).toBeVisible();
    const horizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(horizontalOverflow).toBeLessThanOrEqual(1);
  });
});
