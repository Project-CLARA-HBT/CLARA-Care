#!/usr/bin/env node

/**
 * Projects the versioned, static consumer-terminology contract into the web
 * and Flutter source trees. The contract deliberately excludes clinical free
 * text, health state, consent/RBAC and safety dispositions; this generator
 * must never be used as a generic translation pipeline.
 *
 * Usage:
 *   node scripts/generate-consumer-terminology.mjs          # update files
 *   node scripts/generate-consumer-terminology.mjs --check  # fail if stale
 */
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const WEB_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const REPOSITORY_ROOT = resolve(WEB_ROOT, "..", "..");
const SOURCE_PATH = resolve(
  REPOSITORY_ROOT,
  "contracts/consumer-terminology/consumer-terminology.v1.json",
);
const WEB_OUTPUT_PATH = resolve(
  WEB_ROOT,
  "lib/i18n/consumer-terminology.generated.ts",
);
const MOBILE_OUTPUT_PATH = resolve(
  REPOSITORY_ROOT,
  "apps/mobile/lib/core/consumer_terminology.generated.dart",
);
const CHECK_ONLY = process.argv.slice(2).includes("--check");

function fail(message) {
  process.stderr.write(`consumer terminology generator: ${message}\n`);
  process.exitCode = 1;
}

function dartString(value) {
  return value
    .replaceAll("\\", "\\\\")
    .replaceAll("'", "\\'")
    .replaceAll("\n", "\\n")
    .replaceAll("\r", "\\r");
}

function renderWeb(contract) {
  const localeBlocks = contract.locales
    .map((locale) => {
      const messages = Object.entries(contract.messages)
        .map(([key, values]) => `    ${JSON.stringify(key)}: ${JSON.stringify(values[locale])},`)
        .join("\n");
      return `  ${locale}: {\n${messages}\n  },`;
    })
    .join("\n");

  return `import type { UILanguage } from "@/lib/ui-language";

// GENERATED FROM contracts/consumer-terminology/consumer-terminology.v1.json.
// Static product wording only. This is not a clinical-language translation
// layer and must not receive medical free text, PII, state, or safety data.
export const CONSUMER_TERMINOLOGY_VERSION = ${JSON.stringify(contract.version)} as const;

export const CONSUMER_TERMINOLOGY_MESSAGES = {
${localeBlocks}
} as const satisfies Record<UILanguage, Record<string, string>>;

export type ConsumerTerminologyKey = keyof typeof CONSUMER_TERMINOLOGY_MESSAGES.vi;
`;
}

function renderMobile(contract) {
  const localeBlocks = contract.locales
    .map((locale) => {
      const messages = Object.entries(contract.messages)
        .map(([key, values]) => `    '${dartString(key)}': '${dartString(values[locale])}',`)
        .join("\n");
      return `  '${locale}': {\n${messages}\n  },`;
    })
    .join("\n");

  return `/// GENERATED FROM contracts/consumer-terminology/consumer-terminology.v1.json.
///
/// Static product wording only. This is not a clinical-language translation
/// layer and must not receive medical free text, PII, state, or safety data.
library;

const String kConsumerTerminologyContractVersion = '${dartString(contract.version)}';

const Map<String, Map<String, String>> kConsumerTerminologyMessages = {
${localeBlocks}
};
`;
}

function validate(contract) {
  if (contract.contract !== "clara.consumer-terminology") {
    fail("unexpected contract name");
    return false;
  }
  if (contract.default_locale !== "vi") {
    fail("Vietnamese must remain the default locale");
    return false;
  }
  if (JSON.stringify(contract.locales) !== JSON.stringify(["vi", "en"])) {
    fail("v1 requires exactly vi and en locales");
    return false;
  }
  if (!contract.scope?.includes("clinical free text")) {
    fail("contract must declare its clinical free-text boundary");
    return false;
  }
  for (const [key, values] of Object.entries(contract.messages ?? {})) {
    if (!key || typeof values?.vi !== "string" || !values.vi || typeof values.en !== "string" || !values.en) {
      fail(`each message needs non-empty vi/en static wording (${key || "unknown key"})`);
      return false;
    }
  }
  return true;
}

const contract = JSON.parse(readFileSync(SOURCE_PATH, "utf8"));
if (!validate(contract)) process.exit(1);

const outputs = [
  [WEB_OUTPUT_PATH, renderWeb(contract)],
  [MOBILE_OUTPUT_PATH, renderMobile(contract)],
];
for (const [path, next] of outputs) {
  const current = readFileSync(path, "utf8");
  if (CHECK_ONLY) {
    if (current !== next) fail(`${path.replace(`${REPOSITORY_ROOT}/`, "")} is stale; run npm run consumer-terminology:generate`);
  } else if (current !== next) {
    writeFileSync(path, next, "utf8");
    process.stdout.write(`updated ${path.replace(`${REPOSITORY_ROOT}/`, "")}\n`);
  }
}

if (!process.exitCode) {
  process.stdout.write(
    `consumer terminology ${CHECK_ONLY ? "projection check passed" : "projections generated"}: ${Object.keys(contract.messages).length} keys, ${contract.version}.\n`,
  );
}
