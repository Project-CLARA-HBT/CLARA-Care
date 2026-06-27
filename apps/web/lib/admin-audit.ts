import api from "@/lib/http-client";

/**
 * Admin-action audit-log data access (Requirement 9.4).
 *
 * Thin typed client over the admin-gated audit-read endpoint:
 *   - GET /admin/audit  (admin-action audit trail, most-recent-first)
 *
 * The TypeScript shapes mirror the Pydantic response schema in
 * `services/api/src/clara_api/api/v1/endpoints/admin_audit.py` (snake_case is
 * preserved so the raw JSON maps 1:1). Every record is PII-free by construction
 * — only an opaque `actor_ref`, a bounded action/target/outcome, a PII-projected
 * `meta` payload (counts/flags only), and a timestamp are carried.
 *
 * The endpoint is gated by `require_roles("admin")` server-side (403 for any
 * non-admin role, 401 for a missing token) and returns the standard
 * feature-disabled HTTP 404 shape while `ADMIN_AUDIT_LOG_ENABLED` is off; this
 * module never weakens that contract.
 */

export type AdminAuditRecord = {
  id: number;
  actor_ref: string;
  action: string;
  target: string;
  outcome: string;
  /** Counts / flags only — never PII. */
  meta: Record<string, unknown>;
  created_at: string | null;
  [key: string]: unknown;
};

export type AdminAuditListResponse = {
  records: AdminAuditRecord[];
};

/**
 * Fetch the admin-action audit records most-recent-first. `limit` bounds the
 * number of returned rows (server caps it at 500).
 */
export async function getAdminAuditLog(limit = 100): Promise<AdminAuditListResponse> {
  const safeLimit = Number.isFinite(limit) && limit > 0 ? Math.trunc(limit) : 100;
  const response = await api.get<AdminAuditListResponse>(`/admin/audit?limit=${safeLimit}`);
  return response.data;
}
