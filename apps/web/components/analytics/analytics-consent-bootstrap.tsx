"use client";

import { useEffect } from "react";
import { getConsentStatus } from "@/lib/consent";
import { getAnalyticsClient } from "@/lib/analytics";
import { getRole } from "@/lib/auth-store";

/**
 * Bootstraps the Analytics facade and wires analytics consent from the existing
 * consent surface (Req 9.3).
 *
 * The CLARA platform records a single per-user medical-data consent
 * (`UserConsent` via `/auth/consent-status`). Until that consent is granted the
 * analytics client suppresses ALL transmission, and once granted the facade is
 * initialized lazily and may transmit (only when credentials are configured —
 * Req 9.5). This component holds no UI; it simply mirrors the consent decision
 * into the shared analytics client on mount and whenever the route/role changes.
 *
 * It is deliberately resilient: any failure to read consent leaves analytics in
 * its safe, suppressed default and never breaks the surrounding product flow.
 */
export default function AnalyticsConsentBootstrap() {
  useEffect(() => {
    let cancelled = false;

    const sync = async () => {
      const client = getAnalyticsClient();
      try {
        const status = await getConsentStatus();
        if (cancelled) return;
        // Only transmit when the user has granted consent. setConsent also
        // initializes the transport lazily once consent flips to granted, and
        // remains a no-op when credentials are absent (Req 9.5).
        client.setConsent(Boolean(status.accepted));
        if (status.accepted) {
          client.identify({
            userId: typeof status.user_id === "number" ? status.user_id : null,
            role: getRole(),
          });
        }
      } catch {
        if (cancelled) return;
        // No readable consent → keep analytics suppressed.
        client.setConsent(false);
      }
    };

    void sync();
    return () => {
      cancelled = true;
    };
  }, []);

  return null;
}
