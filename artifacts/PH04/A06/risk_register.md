# Risk Register — PH04 A06 (Mobile Flutter: Tenant Context)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH04-A06-01 | Stale or unauthorized organization ID sent in header leads to 403 or cross-tenant query failure | Medium | Low | Server-side tenant resolver validates user organization membership and returns safe reset; mobile store clears organizationId on logout or expired session hydrate. | Mitigated |
| RISK-PH04-A06-02 | Organization ID omitted during SSE stream connections or multipart uploads causing server fallback to unscoped personal context | Medium | Low | Updated `streamChat`, `streamResearchJob`, and `_postMultipart` to explicitly read `activeOrganizationId` and attach header. Tested in hermetic suite. | Mitigated |
| RISK-PH04-A06-03 | Local cache pollution across different organizations on shared mobile device | High | Low | PersistentSessionStore clears organizationId on user logout and purge cycles; cache keys scoped per user subject. | Mitigated |
