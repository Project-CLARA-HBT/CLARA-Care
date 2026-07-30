import type { UILanguage } from "@/lib/ui-language";

import {
  CONSUMER_TERMINOLOGY_MESSAGES,
  type ConsumerTerminologyKey,
} from "./consumer-terminology.generated";

/**
 * Typed bridge to the cross-client, static terminology contract.
 *
 * Unknown locales are intentionally resolved by callers to `vi`; no runtime
 * content is accepted here, so this helper cannot be used to transform health
 * data or send it to telemetry.
 */
export function consumerTerm(locale: UILanguage, key: ConsumerTerminologyKey): string {
  return CONSUMER_TERMINOLOGY_MESSAGES[locale][key];
}

export type { ConsumerTerminologyKey } from "./consumer-terminology.generated";
export { CONSUMER_TERMINOLOGY_VERSION } from "./consumer-terminology.generated";
