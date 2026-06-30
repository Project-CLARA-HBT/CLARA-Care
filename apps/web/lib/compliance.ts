/**
 * Compliance client transport (CLARA_Web).
 *
 * Thin client over the backend compliance surface at `/api/v1/compliance/*`
 * (AI Law 134/2025 + PDPD 13/2023). Every capability here is **additive and
 * feature-flagged**: the corresponding web surfaces only activate when their
 * `NEXT_PUBLIC_COMPLIANCE_*` flag is explicitly enabled. With the flags off (the
 * default) none of these calls are made, so current behavior is preserved
 * (regulatory-compliance Requirement 8.1, 8.2).
 *
 * Mutating calls go through the shared `http-client`, which attaches the CSRF
 * header for cookie-authenticated unsafe requests (Requirement 8.5; Property
 * P10).
 *
 * No PII is ever sent in analytics from this layer — the surfaces that use it
 * emit only coarse, non-identifying signals.
 */

import api from "@/lib/http-client";

// ---------------------------------------------------------------------------
// Feature flags (client-readable, default OFF ⇒ preserve current behavior)
// ---------------------------------------------------------------------------

const TRUTHY = new Set(["1", "true", "on"]);

function parseFlag(value: string | null | undefined): boolean {
  if (typeof value !== "string") return false;
  return TRUTHY.has(value.trim().toLowerCase());
}

/** Whether the AI Transparency Notice acknowledgement gate is enabled. */
export function isTransparencyNoticeEnabled(): boolean {
  return parseFlag(process.env.NEXT_PUBLIC_COMPLIANCE_TRANSPARENCY_NOTICE_ENABLED);
}

/** Whether the granular Consent Center surface is enabled. */
export function isGranularConsentEnabled(): boolean {
  return parseFlag(process.env.NEXT_PUBLIC_COMPLIANCE_GRANULAR_CONSENT_ENABLED);
}

/** Whether the DSAR self-service surface is enabled. */
export function isDsarEnabled(): boolean {
  return parseFlag(process.env.NEXT_PUBLIC_COMPLIANCE_DSAR_ENABLED);
}

// ---------------------------------------------------------------------------
// AI Transparency Notice (Requirement 1)
// ---------------------------------------------------------------------------

export type TransparencyNotice = {
  enabled: boolean;
  version: string;
  acknowledged: boolean;
  acknowledged_version?: string | null;
  acknowledged_at?: string | null;
  title?: Record<string, string> | null;
  body?: Record<string, string> | null;
};

/**
 * Fetches the current AI Transparency Notice and the user's acknowledgement
 * state. When the backend feature is disabled it returns `{ enabled: false }`,
 * which callers treat as "do not gate".
 */
export async function getTransparencyNotice(): Promise<TransparencyNotice> {
  const { data } = await api.get<TransparencyNotice>("/compliance/transparency-notice");
  return data;
}

/** Records acknowledgement of a specific notice version (CSRF-protected POST). */
export async function acknowledgeTransparencyNotice(version: string): Promise<void> {
  await api.post("/compliance/transparency-notice/ack", { version });
}

// ---------------------------------------------------------------------------
// Granular consent (Requirement 2)
// ---------------------------------------------------------------------------

/** The distinct, separately-toggleable processing purposes (design §B). */
export type ConsentPurpose =
  | "core_service"
  | "personalization"
  | "research"
  | "cross_border_processing"
  | "sharing"
  | "ai_transparency";

export type ConsentRecord = {
  purpose: ConsentPurpose;
  granted: boolean;
  policy_version?: string | null;
  updated_at?: string | null;
};

export type ConsentListResponse = {
  enabled: boolean;
  policy_version?: string | null;
  consents: ConsentRecord[];
};

/**
 * Raw backend shape for `GET /compliance/consent` (design §B). When the feature
 * is disabled the backend returns `{ enabled: false }`; otherwise `consents` is
 * a `{ purpose: granted }` projection of the append-only ledger's latest state.
 */
type RawConsentListResponse = {
  enabled: boolean;
  policy_version?: string | null;
  purposes?: string[];
  consents?: Record<string, boolean>;
};

/** Lists the consent ledger projection (latest state per purpose). */
export async function listConsents(): Promise<ConsentListResponse> {
  const { data } = await api.get<RawConsentListResponse>("/compliance/consent");
  const consents: ConsentRecord[] = Object.entries(data.consents ?? {}).map(
    ([purpose, granted]) => ({
      purpose: purpose as ConsentPurpose,
      granted: Boolean(granted),
    }),
  );
  return {
    enabled: Boolean(data.enabled),
    policy_version: data.policy_version ?? null,
    consents,
  };
}

/** Grants consent for a purpose (append-only ledger; CSRF-protected). */
export async function grantConsent(
  purpose: ConsentPurpose,
  policyVersion?: string,
): Promise<void> {
  await api.post("/compliance/consent/grant", {
    purpose,
    ...(policyVersion ? { policy_version: policyVersion } : {}),
  });
}

/** Withdraws consent for a purpose (append-only ledger; CSRF-protected). */
export async function withdrawConsent(purpose: ConsentPurpose): Promise<void> {
  await api.post("/compliance/consent/withdraw", { purpose });
}

// ---------------------------------------------------------------------------
// DSAR — data-subject access requests (Requirement 3)
// ---------------------------------------------------------------------------

export type DsarKind = "export" | "correct" | "delete" | "restrict" | "withdraw";

export type DsarStatus = "received" | "in_progress" | "fulfilled" | "rejected";

export type DsarRequestRecord = {
  id: number | string;
  kind: DsarKind;
  status: DsarStatus;
  created_at?: string | null;
  resolved_at?: string | null;
  due_at?: string | null;
  /** True when unresolved and past the statutory deadline (admin queue). */
  overdue?: boolean;
};

export type DsarListResponse = {
  enabled: boolean;
  requests: DsarRequestRecord[];
};

/**
 * Lists the authenticated subject's own DSAR requests.
 *
 * Backend contract: `GET /compliance/dsar/requests` → `{ enabled, requests }`.
 * When the feature is disabled the backend returns `{ enabled: false }`.
 */
export async function listDsarRequests(): Promise<DsarListResponse> {
  const { data } = await api.get<DsarListResponse>("/compliance/dsar/requests");
  return { enabled: Boolean(data.enabled), requests: data.requests ?? [] };
}

/** Raw acknowledgement shape returned by the backend DSAR mutation routes. */
type RawDsarAck = {
  enabled?: boolean;
  request_id?: number | string;
  id?: number | string;
  kind?: DsarKind;
  status?: DsarStatus;
  created_at?: string | null;
  resolved_at?: string | null;
  due_at?: string | null;
  statutory_window_days?: number;
};

function toDsarRecord(ack: RawDsarAck, fallbackKind: DsarKind): DsarRequestRecord {
  return {
    id: ack.request_id ?? ack.id ?? "",
    kind: ack.kind ?? fallbackKind,
    status: ack.status ?? "received",
    created_at: ack.created_at ?? null,
    resolved_at: ack.resolved_at ?? null,
    due_at: ack.due_at ?? null,
  };
}

/**
 * Submits a non-export, non-delete DSAR (`correct`, `restrict`, `withdraw`).
 * Returns the acknowledged request record (Requirement 3.5, 3.6).
 *
 * Backend contract: `POST /compliance/dsar/request` with `{ kind }`. The backend
 * records only the request type/timestamp/status — never free-text PII.
 */
export async function submitDsarRequest(
  kind: Exclude<DsarKind, "export" | "delete">,
): Promise<DsarRequestRecord> {
  const { data } = await api.post<RawDsarAck>("/compliance/dsar/request", { kind });
  return toDsarRecord(data, kind);
}

/**
 * Requests a machine-readable export of all personal data CLARA holds about the
 * subject (Requirement 3.1). Returns the parsed export bundle object.
 *
 * Backend contract: `GET /compliance/dsar/export` → `{ enabled, export }`. The
 * caller is responsible for serializing/downloading the bundle.
 */
export async function requestDsarExport(): Promise<Record<string, unknown>> {
  const { data } = await api.get<{ enabled: boolean; export?: Record<string, unknown> }>(
    "/compliance/dsar/export",
  );
  return data.export ?? {};
}

/**
 * Requests irreversible deletion / anonymization of the subject's personal data
 * (Requirement 3.3, 3.7). Returns the acknowledged request record.
 *
 * Backend contract: `POST /compliance/dsar/delete`. This performs the actual
 * transactional anonymization (not merely logging a request), so callers must
 * gate it behind an explicit confirmation step.
 */
export async function requestDsarDelete(): Promise<DsarRequestRecord> {
  const { data } = await api.post<RawDsarAck>("/compliance/dsar/delete", {});
  return toDsarRecord(data, "delete");
}

// ---------------------------------------------------------------------------
// DSAR admin queue (Requirement 3.6) — admin-only (RBAC; Property P7)
// ---------------------------------------------------------------------------

export type DsarAdminQueueResponse = {
  enabled: boolean;
  requests: DsarRequestRecord[];
  overdue_count: number;
  statutory_window_days?: number;
};

/**
 * Lists the global DSAR queue for admins, ordered by statutory urgency.
 *
 * Backend contract: `GET /compliance/dsar/admin/queue` (admin-only). Non-admin
 * callers receive 401/403 from the backend (Property P7).
 */
export async function listAdminDsarQueue(): Promise<DsarAdminQueueResponse> {
  const { data } = await api.get<DsarAdminQueueResponse>("/compliance/dsar/admin/queue");
  return {
    enabled: Boolean(data.enabled),
    requests: data.requests ?? [],
    overdue_count: data.overdue_count ?? 0,
    statutory_window_days: data.statutory_window_days,
  };
}

/**
 * Updates a DSAR request's resolution status from the admin queue.
 *
 * Backend contract: `POST /compliance/dsar/admin/status` with
 * `{ request_id, status }` (admin-only; CSRF-protected).
 */
export async function updateDsarStatus(
  requestId: number | string,
  status: DsarStatus,
): Promise<DsarRequestRecord> {
  const { data } = await api.post<RawDsarAck>("/compliance/dsar/admin/status", {
    request_id: Number(requestId),
    status,
  });
  return toDsarRecord(data, "correct");
}

// ---------------------------------------------------------------------------
// Admin compliance records (Requirement 6) — admin-only (RBAC; Property P7)
// ---------------------------------------------------------------------------

export type ComplianceRecordsResponse = {
  enabled: boolean;
  records?: Record<string, unknown>;
};

/**
 * Fetches the admin compliance-records manifest.
 *
 * Backend contract: `GET /compliance/records` (admin-only). Non-admin callers
 * receive 401/403 from the backend (Property P7).
 */
export async function getComplianceRecords(): Promise<ComplianceRecordsResponse> {
  const { data } = await api.get<ComplianceRecordsResponse>("/compliance/records");
  return { enabled: Boolean(data.enabled), records: data.records };
}
