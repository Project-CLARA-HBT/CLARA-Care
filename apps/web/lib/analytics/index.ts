/**
 * Analytics facade (CLARA_Web).
 *
 * A provider-agnostic event-analytics facade that keeps the SDK choice
 * (PostHog / Google Analytics / Plausible) swappable and enforces consent and
 * PII rules in a single place. The facade:
 *
 *  - is a safe no-op when no credentials are configured (Req 9.5);
 *  - suppresses ALL transmission when analytics consent is not granted (Req 9.3);
 *  - strips PII from every payload before transmission (Req 9.4);
 *  - identifies users by an opaque, deterministic `pseudonymousId` only (Req 9.6);
 *  - emits named product events for primary Surface interactions (Req 9.1);
 *  - NEVER throws into product flows.
 *
 * `stripPii` and `pseudonymousId` are exported as pure functions so they can be
 * exercised directly by property tests (tasks 7.2–7.5).
 */

import type { UserRole } from "@/lib/auth-store";

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

export type Primitive = string | number | boolean | null;

export type AnalyticsPropValue =
  | Primitive
  | AnalyticsPropValue[]
  | { [key: string]: AnalyticsPropValue };

export type AnalyticsProps = Record<string, AnalyticsPropValue>;

export type AnalyticsEvent = {
  name: string;
  props?: AnalyticsProps;
};

export type AnalyticsProvider = "posthog" | "ga" | "plausible" | "console" | "none";

export type AnalyticsConfig = {
  provider: AnalyticsProvider;
  key?: string;
  host?: string;
};

/**
 * Minimal session-user shape consumed by the facade. Mirrors the identity
 * fields used elsewhere in the web app (`user_id`, `role`, `email`,
 * `full_name`). Only `userId` is used to derive the pseudonymous id; the PII
 * fields are deliberately never transmitted.
 */
export type SessionUser = {
  userId?: string | number | null;
  role?: UserRole;
  email?: string | null;
  fullName?: string | null;
};

/** A provider adapter. One implementation per analytics backend. */
export interface AnalyticsTransport {
  init(config: AnalyticsConfig): void;
  identify(distinctId: string): void;
  capture(event: AnalyticsEvent): void;
}

export type ConsentResolver = boolean | (() => boolean);

export type AnalyticsClientOptions = {
  config?: AnalyticsConfig;
  transport?: AnalyticsTransport;
  /** Analytics consent. Suppressed by default until explicitly granted (Req 9.3). */
  consent?: ConsentResolver;
};

// ---------------------------------------------------------------------------
// Configuration (read from NEXT_PUBLIC_ANALYTICS_SDK_* env vars)
// ---------------------------------------------------------------------------

function cleanEnv(value: string | undefined): string {
  return typeof value === "string" ? value.trim() : "";
}

function normalizeProvider(value: string): AnalyticsProvider {
  switch (value.toLowerCase()) {
    case "posthog":
      return "posthog";
    case "ga":
    case "google":
    case "google-analytics":
      return "ga";
    case "plausible":
      return "plausible";
    case "console":
      return "console";
    default:
      return "none";
  }
}

/**
 * Reads the public analytics configuration from the environment. Missing or
 * blank values resolve to a disabled (`none`) provider so the facade degrades
 * to a safe no-op (Req 9.5).
 */
export function readAnalyticsConfigFromEnv(): AnalyticsConfig {
  return {
    provider: normalizeProvider(cleanEnv(process.env.NEXT_PUBLIC_ANALYTICS_SDK_PROVIDER)),
    key: cleanEnv(process.env.NEXT_PUBLIC_ANALYTICS_SDK_KEY) || undefined,
    host: cleanEnv(process.env.NEXT_PUBLIC_ANALYTICS_SDK_HOST) || undefined,
  };
}

/**
 * A configuration counts as "configured" only when it names a real transmitting
 * provider AND supplies credentials. The `console` provider is treated as
 * configured for local debugging because it does not transmit off-device.
 */
export function isConfigured(config: AnalyticsConfig): boolean {
  if (config.provider === "none") return false;
  if (config.provider === "console") return true;
  return Boolean(config.key && config.key.length > 0);
}

// ---------------------------------------------------------------------------
// PII stripping (pure, exported for property tests)
// ---------------------------------------------------------------------------

/**
 * Curated denylist of normalized property keys that always carry PII or
 * free-text content. Matched after normalization (lowercase, alphanumerics
 * only).
 */
const PII_KEY_DENYLIST = new Set<string>([
  // Names
  "name",
  "fullname",
  "firstname",
  "lastname",
  "givenname",
  "familyname",
  "surname",
  "displayname",
  "username",
  "patientname",
  // Contact / identity
  "email",
  "emailaddress",
  "phone",
  "phonenumber",
  "address",
  "ssn",
  "dob",
  "dateofbirth",
  "birthdate",
  // Free-text query content
  "q",
  "query",
  "question",
  "prompt",
  "message",
  "text",
  "content",
  "input",
  "userinput",
  "search",
  "searchquery",
  "body",
  "note",
  "notes",
  "transcript",
  // Medical content
  "drug",
  "drugs",
  "druglist",
  "medication",
  "medications",
  "medicine",
  "medicines",
  "symptom",
  "symptoms",
  "allergy",
  "allergies",
  "diagnosis",
  "prescription",
  "labs",
]);

/**
 * Substring patterns (normalized) that mark a key as PII even when not an exact
 * match — e.g. `patient_email`, `drug_names`, `free_text_query`.
 */
const PII_KEY_PATTERNS = [
  "email",
  "query",
  "drug",
  "medication",
  "medicine",
  "symptom",
  "allergy",
  "diagnos",
  "prescription",
  "freetext",
  "patient",
  "password",
];

function normalizeKey(key: string): string {
  return key.toLowerCase().replace(/[^a-z0-9]+/g, "");
}

/** Returns true when the property key must be dropped before transmission. */
export function isPiiKey(key: string): boolean {
  const normalized = normalizeKey(key);
  if (!normalized) return false;
  if (PII_KEY_DENYLIST.has(normalized)) return true;
  return PII_KEY_PATTERNS.some((pattern) => normalized.includes(pattern));
}

function stripPiiValue(value: AnalyticsPropValue): AnalyticsPropValue {
  if (Array.isArray(value)) {
    return value.map((item) => stripPiiValue(item));
  }
  if (value && typeof value === "object") {
    return stripPiiProps(value as AnalyticsProps);
  }
  return value;
}

function stripPiiProps(props: AnalyticsProps): AnalyticsProps {
  const output: AnalyticsProps = {};
  for (const [key, value] of Object.entries(props)) {
    if (isPiiKey(key)) continue;
    output[key] = stripPiiValue(value);
  }
  return output;
}

/**
 * Returns a copy of the event with all PII keys removed from its props
 * (recursively, including nested objects and arrays). The event `name` is a
 * developer-controlled label and is preserved as-is (Req 9.4).
 */
export function stripPii(event: AnalyticsEvent): AnalyticsEvent {
  if (!event.props) {
    return { name: event.name };
  }
  return { name: event.name, props: stripPiiProps(event.props) };
}

// ---------------------------------------------------------------------------
// Pseudonymous identity (pure, exported for property tests)
// ---------------------------------------------------------------------------

const PSEUDONYMOUS_PREFIX = "anon_";

/**
 * Deterministic, opaque, one-way pseudonymous identifier derived from a stable
 * user key (preferring `user_id`). The same user always maps to the same id,
 * and the id never equals or contains the user's email or name (Req 9.6).
 */
export function pseudonymousId(user: SessionUser | null | undefined): string {
  const stableKey = resolveStableKey(user);
  return PSEUDONYMOUS_PREFIX + sha256Hex(`clara:analytics:${stableKey}`);
}

function resolveStableKey(user: SessionUser | null | undefined): string {
  if (!user) return "anonymous";
  if (user.userId !== undefined && user.userId !== null) {
    const key = String(user.userId).trim();
    if (key) return `uid:${key}`;
  }
  // No stable user id: hash whatever identity material exists so the output is
  // still one-way and never contains the raw email/name. Falls back to a shared
  // anonymous bucket when nothing is available.
  const fallback = (user.email ?? user.fullName ?? "").trim();
  return fallback ? `id:${fallback}` : "anonymous";
}

// --- SHA-256 (pure, synchronous, dependency-free) --------------------------

const SHA256_K = [
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
];

function utf8Bytes(str: string): number[] {
  const out: number[] = [];
  for (let i = 0; i < str.length; i += 1) {
    let code = str.charCodeAt(i);
    if (code < 0x80) {
      out.push(code);
    } else if (code < 0x800) {
      out.push(0xc0 | (code >> 6), 0x80 | (code & 0x3f));
    } else if (code >= 0xd800 && code <= 0xdbff) {
      const hi = code;
      const lo = str.charCodeAt(i + 1);
      i += 1;
      const cp = 0x10000 + ((hi - 0xd800) << 10) + (lo - 0xdc00);
      out.push(
        0xf0 | (cp >> 18),
        0x80 | ((cp >> 12) & 0x3f),
        0x80 | ((cp >> 6) & 0x3f),
        0x80 | (cp & 0x3f),
      );
    } else {
      out.push(0xe0 | (code >> 12), 0x80 | ((code >> 6) & 0x3f), 0x80 | (code & 0x3f));
    }
  }
  return out;
}

function rotr(value: number, bits: number): number {
  return (value >>> bits) | (value << (32 - bits));
}

function toHex8(value: number): string {
  return (value >>> 0).toString(16).padStart(8, "0");
}

/** Computes the lowercase hex SHA-256 digest of a UTF-8 string. */
export function sha256Hex(input: string): string {
  const bytes = utf8Bytes(input);
  const byteLength = bytes.length;

  bytes.push(0x80);
  while (bytes.length % 64 !== 56) {
    bytes.push(0);
  }
  const bitLenHi = Math.floor((byteLength * 8) / 0x100000000);
  const bitLenLo = (byteLength * 8) >>> 0;
  bytes.push(
    (bitLenHi >>> 24) & 0xff,
    (bitLenHi >>> 16) & 0xff,
    (bitLenHi >>> 8) & 0xff,
    bitLenHi & 0xff,
    (bitLenLo >>> 24) & 0xff,
    (bitLenLo >>> 16) & 0xff,
    (bitLenLo >>> 8) & 0xff,
    bitLenLo & 0xff,
  );

  let h0 = 0x6a09e667;
  let h1 = 0xbb67ae85;
  let h2 = 0x3c6ef372;
  let h3 = 0xa54ff53a;
  let h4 = 0x510e527f;
  let h5 = 0x9b05688c;
  let h6 = 0x1f83d9ab;
  let h7 = 0x5be0cd19;

  const w = new Array<number>(64);

  for (let offset = 0; offset < bytes.length; offset += 64) {
    for (let t = 0; t < 16; t += 1) {
      const i = offset + t * 4;
      w[t] = ((bytes[i] << 24) | (bytes[i + 1] << 16) | (bytes[i + 2] << 8) | bytes[i + 3]) | 0;
    }
    for (let t = 16; t < 64; t += 1) {
      const s0 = rotr(w[t - 15], 7) ^ rotr(w[t - 15], 18) ^ (w[t - 15] >>> 3);
      const s1 = rotr(w[t - 2], 17) ^ rotr(w[t - 2], 19) ^ (w[t - 2] >>> 10);
      w[t] = (w[t - 16] + s0 + w[t - 7] + s1) | 0;
    }

    let a = h0;
    let b = h1;
    let c = h2;
    let d = h3;
    let e = h4;
    let f = h5;
    let g = h6;
    let h = h7;

    for (let t = 0; t < 64; t += 1) {
      const bigS1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
      const ch = (e & f) ^ (~e & g);
      const temp1 = (h + bigS1 + ch + SHA256_K[t] + w[t]) | 0;
      const bigS0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
      const maj = (a & b) ^ (a & c) ^ (b & c);
      const temp2 = (bigS0 + maj) | 0;

      h = g;
      g = f;
      f = e;
      e = (d + temp1) | 0;
      d = c;
      c = b;
      b = a;
      a = (temp1 + temp2) | 0;
    }

    h0 = (h0 + a) | 0;
    h1 = (h1 + b) | 0;
    h2 = (h2 + c) | 0;
    h3 = (h3 + d) | 0;
    h4 = (h4 + e) | 0;
    h5 = (h5 + f) | 0;
    h6 = (h6 + g) | 0;
    h7 = (h7 + h) | 0;
  }

  return (
    toHex8(h0) + toHex8(h1) + toHex8(h2) + toHex8(h3) + toHex8(h4) + toHex8(h5) + toHex8(h6) + toHex8(h7)
  );
}

// ---------------------------------------------------------------------------
// Transports (provider adapters)
// ---------------------------------------------------------------------------

/** Default transport: does nothing. Used when unconfigured (Req 9.5). */
export class NoOpTransport implements AnalyticsTransport {
  init(): void {
    /* no-op */
  }

  identify(): void {
    /* no-op */
  }

  capture(): void {
    /* no-op */
  }
}

/** Local debugging transport: logs to the console; never transmits off-device. */
export class ConsoleTransport implements AnalyticsTransport {
  init(config: AnalyticsConfig): void {
    // eslint-disable-next-line no-console
    console.info("[analytics] init", { provider: config.provider, host: config.host });
  }

  identify(distinctId: string): void {
    // eslint-disable-next-line no-console
    console.info("[analytics] identify", distinctId);
  }

  capture(event: AnalyticsEvent): void {
    // eslint-disable-next-line no-console
    console.info("[analytics] capture", event.name, event.props ?? {});
  }
}

type BrowserWindow = typeof globalThis & {
  posthog?: {
    init: (key: string, options: Record<string, unknown>) => void;
    identify: (id: string) => void;
    capture: (name: string, props?: Record<string, unknown>) => void;
  };
  gtag?: (...args: unknown[]) => void;
  plausible?: (name: string, options?: { props?: Record<string, unknown> }) => void;
};

function browserGlobal(): BrowserWindow | null {
  return typeof window === "undefined" ? null : (window as BrowserWindow);
}

/**
 * Thin provider adapter scaffold. It forwards init/identify/capture to the
 * provider's official global (loaded lazily via the provider's own script
 * snippet elsewhere) when present, and degrades to a no-op otherwise. This
 * keeps the facade free of a heavy SDK dependency while leaving a clear seam
 * for wiring a real provider. It never throws.
 */
export class ProviderTransport implements AnalyticsTransport {
  private readonly provider: AnalyticsProvider;

  constructor(provider: AnalyticsProvider) {
    this.provider = provider;
  }

  init(config: AnalyticsConfig): void {
    const win = browserGlobal();
    if (!win || !config.key) return;
    if (this.provider === "posthog" && win.posthog) {
      win.posthog.init(config.key, config.host ? { api_host: config.host } : {});
    }
    // GA (gtag) and Plausible initialize via their own snippet; nothing to do
    // here beyond confirming their global is available at capture time.
  }

  identify(distinctId: string): void {
    const win = browserGlobal();
    if (!win) return;
    if (this.provider === "posthog" && win.posthog) {
      win.posthog.identify(distinctId);
    } else if (this.provider === "ga" && win.gtag) {
      win.gtag("set", { user_id: distinctId });
    }
    // Plausible has no identify concept; pseudonymous id is intentionally dropped.
  }

  capture(event: AnalyticsEvent): void {
    const win = browserGlobal();
    if (!win) return;
    const props = event.props as Record<string, unknown> | undefined;
    if (this.provider === "posthog" && win.posthog) {
      win.posthog.capture(event.name, props);
    } else if (this.provider === "ga" && win.gtag) {
      win.gtag("event", event.name, props ?? {});
    } else if (this.provider === "plausible" && win.plausible) {
      win.plausible(event.name, props ? { props: props } : undefined);
    }
  }
}

/** Selects a transport for a configuration. Unconfigured → no-op (Req 9.5). */
export function resolveTransport(config: AnalyticsConfig): AnalyticsTransport {
  if (!isConfigured(config)) return new NoOpTransport();
  if (config.provider === "console") return new ConsoleTransport();
  return new ProviderTransport(config.provider);
}

// ---------------------------------------------------------------------------
// AnalyticsClient
// ---------------------------------------------------------------------------

export class AnalyticsClient {
  private readonly config: AnalyticsConfig;

  private readonly transport: AnalyticsTransport;

  private consent: ConsentResolver;

  private initialized = false;

  constructor(options: AnalyticsClientOptions = {}) {
    this.config = options.config ?? readAnalyticsConfigFromEnv();
    this.transport = options.transport ?? resolveTransport(this.config);
    this.consent = options.consent ?? false;
  }

  /** True only when a transmitting provider and credentials are present (Req 9.5). */
  get configured(): boolean {
    return isConfigured(this.config);
  }

  /** Current analytics-consent state. Suppressed by default (Req 9.3). */
  get consentGranted(): boolean {
    return typeof this.consent === "function" ? Boolean(this.consent()) : Boolean(this.consent);
  }

  /** Updates analytics consent; initializes lazily once consent is granted. */
  setConsent(consent: ConsentResolver): void {
    this.consent = consent;
    if (this.consentGranted) {
      this.ensureInitialized();
    }
  }

  /** Initializes the underlying transport when configured and consented. */
  init(): void {
    this.ensureInitialized();
  }

  /** Identifies the current user by an opaque pseudonymous id only (Req 9.6). */
  identify(user: SessionUser | null | undefined): void {
    if (!this.configured) return; // 9.5 safe no-op
    if (!this.consentGranted) return; // 9.3 suppress
    this.ensureInitialized();
    this.safe(() => this.transport.identify(pseudonymousId(user)));
  }

  /** Emits a named product event with PII stripped (Req 9.1, 9.4). */
  capture(event: AnalyticsEvent): void {
    if (!this.configured) return; // 9.5 safe no-op
    if (!this.consentGranted) return; // 9.3 suppress
    this.ensureInitialized();
    this.safe(() => this.transport.capture(stripPii(event)));
  }

  /** Convenience wrapper for emitting a named event with optional props. */
  track(name: string, props?: AnalyticsProps): void {
    this.capture({ name, props });
  }

  private ensureInitialized(): void {
    if (this.initialized) return;
    if (!this.configured) return; // 9.5
    if (!this.consentGranted) return; // 9.3 — do not load/transmit without consent
    this.safe(() => this.transport.init(this.config));
    this.initialized = true;
  }

  /** Runs a transport call without ever throwing into product flows (Req 9.5). */
  private safe(fn: () => void): void {
    try {
      fn();
    } catch {
      // Analytics failures are non-fatal and must never break product flows.
    }
  }
}

// ---------------------------------------------------------------------------
// Factory + lazy singleton
// ---------------------------------------------------------------------------

/** Creates a new client. Defaults config from env and transport from provider. */
export function createAnalyticsClient(options: AnalyticsClientOptions = {}): AnalyticsClient {
  return new AnalyticsClient(options);
}

let sharedClient: AnalyticsClient | null = null;

/** Returns the process-wide analytics client, creating it on first use. */
export function getAnalyticsClient(): AnalyticsClient {
  if (!sharedClient) {
    sharedClient = createAnalyticsClient();
  }
  return sharedClient;
}
