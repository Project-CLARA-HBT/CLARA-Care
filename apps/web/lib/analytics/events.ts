/**
 * Named product events (CLARA_Web).
 *
 * A thin, centralized layer of named-event emitters for primary Surface
 * interactions (Chat, Research, CareGuard, Council, Scribe, Admin). Every
 * emitter routes through the consent/PII-guarded {@link getAnalyticsClient}
 * facade, so:
 *
 *  - nothing transmits without analytics consent (Req 9.3);
 *  - nothing transmits without configured credentials (Req 9.5);
 *  - PII is stripped from every payload by the facade (Req 9.4);
 *  - emitting NEVER throws into product flows.
 *
 * IMPORTANT: callers MUST NOT pass free-text queries, drug names, transcripts,
 * patient content, names, or emails as event props. Keep props limited to
 * coarse, non-identifying signals (surface name, coarse mode, risk level,
 * counts). The facade strips known PII keys as a backstop, but the contract is
 * to only ever pass safe, aggregate values here.
 */

import { getAnalyticsClient, type AnalyticsProps } from "@/lib/analytics";

/** Canonical names for the primary-Surface product events (Req 9.1). */
export const ANALYTICS_EVENTS = {
  chatMessageSent: "chat_message_sent",
  researchStarted: "research_started",
  // Mirrors the mobile facade naming (`MobileAnalyticsEvents`, e.g.
  // `mobile_research_submitted` / `mobile_research_viewed`) with the web
  // `<surface>_<action>` convention (the `mobile_` prefix dropped).
  researchSubmitted: "research_submitted",
  researchViewed: "research_viewed",
  researchSourcesSynced: "research_sources_synced",
  careguardViewed: "careguard_viewed",
  careguardDdiChecked: "careguard_ddi_checked",
  councilViewed: "council_viewed",
  councilRun: "council_run",
  scribeViewed: "scribe_viewed",
  scribeGenerated: "scribe_generated",
  // Admin surfaces. A coarse, generic event plus one named event per primary
  // Admin surface, mirroring the per-screen naming convention used by the
  // mobile facade (`MobileAnalyticsEvents`, e.g. `mobile_dashboard_viewed`).
  adminSurfaceViewed: "admin_surface_viewed",
  adminOverviewViewed: "admin_overview_viewed",
  adminKnowledgeSourcesViewed: "admin_knowledge_sources_viewed",
  adminAnswerFlowViewed: "admin_answer_flow_viewed",
  adminObservabilityViewed: "admin_observability_viewed",
  adminAnalyticsViewed: "admin_analytics_viewed",
  adminClinicalAnalyticsViewed: "admin_clinical_analytics_viewed",
  // Consumer Home surface events
  homeViewed: "home_viewed",
  homeActionClicked: "home_action_clicked",
  homeAlertClicked: "home_alert_clicked",
  homeScheduleItemClicked: "home_schedule_item_clicked",
  homeRecentChangeClicked: "home_recent_change_clicked",
} as const;

export type AnalyticsEventName = (typeof ANALYTICS_EVENTS)[keyof typeof ANALYTICS_EVENTS];

/**
 * Emits a named event through the shared analytics client. Wrapped so that a
 * misconfigured or throwing client can never break a product flow.
 */
function emit(name: AnalyticsEventName, props?: AnalyticsProps): void {
  try {
    getAnalyticsClient().track(name, props);
  } catch {
    // Analytics must never break product flows.
  }
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------

/**
 * A chat message was submitted on the Chat surface. `mode` is the coarse
 * End_User mode selection (fast/deep/deep_beta) and `transport` is the resolved
 * routing decision (tier1_chat / tier2_job). No message text is included.
 */
export function trackChatMessageSent(props: {
  mode: string;
  transport: string;
}): void {
  emit(ANALYTICS_EVENTS.chatMessageSent, {
    surface: "chat",
    mode: props.mode,
    transport: props.transport,
  });
}

// ---------------------------------------------------------------------------
// Research
// ---------------------------------------------------------------------------

/**
 * A deep research (tier2) run was started. `mode` is the coarse Deep_Mode
 * selection. No query text is included.
 */
export function trackResearchStarted(props: { mode: string }): void {
  emit(ANALYTICS_EVENTS.researchStarted, {
    surface: "research",
    mode: props.mode,
  });
}

/**
 * A Research query was submitted on the Research surface. Mirrors the mobile
 * `mobile_research_submitted` event. `mode` is the coarse, non-PII End_User
 * mode selection (fast/deep/deep_beta) and `transport` is the resolved routing
 * decision (tier1_chat / tier2_job). The free-text query is NEVER included.
 */
export function trackResearchSubmitted(props: {
  mode: string;
  transport?: string;
}): void {
  emit(ANALYTICS_EVENTS.researchSubmitted, {
    surface: "research",
    mode: props.mode,
    ...(props.transport ? { transport: props.transport } : {}),
  });
}

/**
 * The Research surface was viewed. Mirrors the mobile `mobile_research_viewed`
 * per-screen convention. No PII or query content is included.
 */
export function trackResearchViewed(): void {
  emit(ANALYTICS_EVENTS.researchViewed, {
    surface: "research",
  });
}

/**
 * A Research Source Hub sync completed. Only coarse, non-identifying signals
 * are recorded: the source key (e.g. `pubmed`) and the fetched/stored record
 * counts. The free-text sync query and any record content are NEVER included.
 */
export function trackResearchSourcesSynced(props: {
  source: string;
  fetched: number;
  stored: number;
}): void {
  emit(ANALYTICS_EVENTS.researchSourcesSynced, {
    surface: "research",
    source: props.source,
    fetched: props.fetched,
    stored: props.stored,
  });
}

// ---------------------------------------------------------------------------
// CareGuard / SelfMed
// ---------------------------------------------------------------------------

/**
 * The CareGuard/SelfMed surface was viewed. Mirrors the mobile
 * `careguardViewed` event. No PII or drug content is included.
 */
export function trackCareguardViewed(props?: { surface?: string }): void {
  emit(ANALYTICS_EVENTS.careguardViewed, {
    surface: props?.surface ?? "careguard",
  });
}

/**
 * A DDI interaction check completed on the CareGuard/SelfMed surface. Only the
 * coarse aggregate signals are recorded: the overall risk level, the number of
 * alerts, and the number of medicines analyzed. No drug names are included.
 */
export function trackCareguardDdiChecked(props: {
  riskLevel: string;
  alertCount: number;
  medicineCount: number;
  source?: string;
}): void {
  emit(ANALYTICS_EVENTS.careguardDdiChecked, {
    surface: "careguard",
    risk_level: props.riskLevel,
    alert_count: props.alertCount,
    medicine_count: props.medicineCount,
    ...(props.source ? { source: props.source } : {}),
  });
}

// ---------------------------------------------------------------------------
// Council
// ---------------------------------------------------------------------------

/**
 * The Council surface was viewed. Mirrors the per-screen `*_viewed` convention
 * used by the other surfaces (`careguard_viewed`, `research_viewed`) and the
 * mobile facade. No case/patient content is included.
 */
export function trackCouncilViewed(props?: { view?: string }): void {
  emit(ANALYTICS_EVENTS.councilViewed, {
    surface: "council",
    ...(props?.view ? { view: props.view } : {}),
  });
}

/**
 * A Council case was run. Only coarse configuration is recorded (specialist
 * count). No case/patient content is included.
 */
export function trackCouncilRun(props: { specialistCount: number }): void {
  emit(ANALYTICS_EVENTS.councilRun, {
    surface: "council",
    specialist_count: props.specialistCount,
  });
}

// ---------------------------------------------------------------------------
// Scribe
// ---------------------------------------------------------------------------

/**
 * The Scribe surface was viewed. Mirrors the per-screen `*_viewed` convention
 * used by the mobile facade (`MobileAnalyticsEvents`) and the web
 * `careguard_viewed` event. No transcript, patient, or note content is
 * included.
 */
export function trackScribeViewed(): void {
  emit(ANALYTICS_EVENTS.scribeViewed, {
    surface: "scribe",
  });
}

/**
 * A Scribe SOAP note was generated/regenerated or finalized. `action` is the
 * coarse trigger; no transcript or note content is included.
 */
export function trackScribeGenerated(props: { action: "regenerate" | "finalize" }): void {
  emit(ANALYTICS_EVENTS.scribeGenerated, {
    surface: "scribe",
    action: props.action,
  });
}

// ---------------------------------------------------------------------------
// Admin
// ---------------------------------------------------------------------------

/** Coarse, non-identifying labels for each primary Admin surface. */
export type AdminView =
  | "overview"
  | "knowledge_sources"
  | "answer_flow"
  | "observability"
  | "product_analytics"
  | "clinical_analytics";

/** Maps an Admin view to its dedicated named view-event. */
const ADMIN_VIEW_EVENTS: Record<AdminView, AnalyticsEventName> = {
  overview: ANALYTICS_EVENTS.adminOverviewViewed,
  knowledge_sources: ANALYTICS_EVENTS.adminKnowledgeSourcesViewed,
  answer_flow: ANALYTICS_EVENTS.adminAnswerFlowViewed,
  observability: ANALYTICS_EVENTS.adminObservabilityViewed,
  product_analytics: ANALYTICS_EVENTS.adminAnalyticsViewed,
  clinical_analytics: ANALYTICS_EVENTS.adminClinicalAnalyticsViewed,
};

/**
 * An Admin surface/dashboard was viewed. Emits the dedicated named event for
 * the given `view` (e.g. `admin_overview_viewed`, `admin_analytics_viewed`)
 * mirroring the per-screen naming used by the mobile facade, and also emits the
 * coarse `admin_surface_viewed` event so a single roll-up stream of Admin
 * activity remains available. `view` is a coarse, non-identifying label — no
 * PII is included.
 */
export function trackAdminSurfaceViewed(props: { view: AdminView }): void {
  emit(ADMIN_VIEW_EVENTS[props.view], {
    surface: "admin",
    view: props.view,
  });
  emit(ANALYTICS_EVENTS.adminSurfaceViewed, {
    surface: "admin",
    view: props.view,
  });
}

// ---------------------------------------------------------------------------
// Consumer Home
// ---------------------------------------------------------------------------

/**
 * The Consumer Home surface was viewed. No PII or clinical data included.
 */
export function trackHomeViewed(): void {
  emit(ANALYTICS_EVENTS.homeViewed, {
    surface: "home",
  });
}

/**
 * A primary or quick action was clicked on the Home surface.
 * Only coarse action kind and optional severity are recorded. No health details.
 */
export function trackHomeActionClicked(props: {
  actionKind: string;
  severity?: string;
  targetHref?: string;
}): void {
  emit(ANALYTICS_EVENTS.homeActionClicked, {
    surface: "home",
    action_kind: props.actionKind,
    ...(props.severity ? { severity: props.severity } : {}),
    ...(props.targetHref ? { target_href: props.targetHref } : {}),
  });
}

/**
 * A safety alert banner was clicked on Home.
 */
export function trackHomeAlertClicked(props: {
  severity: string;
  alertKind?: string;
}): void {
  emit(ANALYTICS_EVENTS.homeAlertClicked, {
    surface: "home",
    severity: props.severity,
    ...(props.alertKind ? { alert_kind: props.alertKind } : {}),
  });
}

/**
 * A scheduled medication, visit, or care task item was clicked on Home.
 */
export function trackHomeScheduleItemClicked(props: {
  itemKind: string;
}): void {
  emit(ANALYTICS_EVENTS.homeScheduleItemClicked, {
    surface: "home",
    item_kind: props.itemKind,
  });
}

/**
 * A recent change item was clicked on Home.
 */
export function trackHomeRecentChangeClicked(props: {
  changeKind: string;
}): void {
  emit(ANALYTICS_EVENTS.homeRecentChangeClicked, {
    surface: "home",
    change_kind: props.changeKind,
  });
}
