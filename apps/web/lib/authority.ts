export type AuthorityState =
  | "authoritative"
  | "known_empty"
  | "unavailable"
  | "degraded"
  | "stale";

export interface DataEnvelope<T> {
  data: T | null;
  state: AuthorityState;
  error?: {
    message: string;
    correlationId?: string;
    statusCode?: number;
  };
  generatedAt: string;
  resourceVersion?: string;
  provenance?: {
    source: string;
    policyVersion?: string;
    digest?: string;
  };
}

export function wrapAuthoritative<T>(
  data: T,
  version?: string,
  provenance?: DataEnvelope<T>["provenance"]
): DataEnvelope<T> {
  const envelope: DataEnvelope<T> = {
    data,
    state: "authoritative",
    generatedAt: new Date().toISOString(),
  };

  if (version !== undefined) {
    envelope.resourceVersion = version;
  }

  if (provenance !== undefined) {
    envelope.provenance = provenance;
  }

  return envelope;
}

export function wrapKnownEmpty<T>(
  emptyValue: T,
  provenance?: DataEnvelope<T>["provenance"]
): DataEnvelope<T> {
  const envelope: DataEnvelope<T> = {
    data: emptyValue,
    state: "known_empty",
    generatedAt: new Date().toISOString(),
  };

  if (provenance !== undefined) {
    envelope.provenance = provenance;
  }

  return envelope;
}

export function wrapUnavailable<T = unknown>(
  message: string,
  correlationId?: string,
  statusCode?: number
): DataEnvelope<T> {
  const error: {
    message: string;
    correlationId?: string;
    statusCode?: number;
  } = {
    message,
  };

  if (correlationId !== undefined) {
    error.correlationId = correlationId;
  }

  if (statusCode !== undefined) {
    error.statusCode = statusCode;
  }

  return {
    data: null,
    state: "unavailable",
    error,
    generatedAt: new Date().toISOString(),
  };
}
