#!/usr/bin/env node

/**
 * Verifies the checked-in web and mobile projections of the versioned static
 * terminology source. It intentionally does not contact a translation, model,
 * or telemetry service: only product copy from the repository is inspected.
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const WEB_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const REPOSITORY_ROOT = resolve(WEB_ROOT, "..", "..");
const source = JSON.parse(
  readFileSync(
    resolve(REPOSITORY_ROOT, "contracts/consumer-terminology/consumer-terminology.v1.json"),
    "utf8",
  ),
);
const webProjection = readFileSync(
  resolve(WEB_ROOT, "lib/i18n/consumer-terminology.generated.ts"),
  "utf8",
);
const webCatalog = readFileSync(resolve(WEB_ROOT, "lib/i18n/catalog.ts"), "utf8");
const mobileProjection = readFileSync(
  resolve(REPOSITORY_ROOT, "apps/mobile/lib/core/consumer_terminology.generated.dart"),
  "utf8",
);
const mobileResolver = readFileSync(
  resolve(REPOSITORY_ROOT, "apps/mobile/lib/core/consumer_terminology.dart"),
  "utf8",
);
const mobileShell = readFileSync(
  resolve(REPOSITORY_ROOT, "apps/mobile/lib/experience/unified/unified_root.dart"),
  "utf8",
);

let failed = false;
function expect(condition, message) {
  if (condition) return;
  failed = true;
  process.stderr.write(`consumer terminology contract: ${message}\n`);
}

expect(source.contract === "clara.consumer-terminology", "unexpected contract name");
expect(source.version === "2026-07-30.v1", "unexpected or missing version");
expect(source.default_locale === "vi", "Vietnamese must remain the default locale");
expect(JSON.stringify(source.locales) === JSON.stringify(["vi", "en"]), "only vi/en static locales are supported by v1");
expect(source.scope.includes("clinical free text"), "source must state its clinical free-text boundary");

for (const [key, values] of Object.entries(source.messages ?? {})) {
  expect(typeof values.vi === "string" && values.vi.length > 0, `missing Vietnamese message for ${key}`);
  expect(typeof values.en === "string" && values.en.length > 0, `missing English message for ${key}`);
  for (const locale of ["vi", "en"]) {
    const value = values[locale];
    expect(
      webProjection.includes(`${JSON.stringify(key)}: ${JSON.stringify(value)}`),
      `web projection differs for ${locale}:${key}`,
    );
    const dartValue = String(value).replaceAll("'", "\\'");
    expect(
      mobileProjection.includes(`'${key}': '${dartValue}'`),
      `mobile projection differs for ${locale}:${key}`,
    );
  }
}

for (const projection of [webProjection, mobileProjection]) {
  expect(projection.includes(source.version), "a projection is missing the source version");
}
expect(
  webCatalog.includes('CONSUMER_TERMINOLOGY_MESSAGES') &&
    webCatalog.includes('...CONSUMER_TERMINOLOGY_MESSAGES.vi') &&
    webCatalog.includes('...CONSUMER_TERMINOLOGY_MESSAGES.en'),
  "web catalog must bridge the shared terminology projection",
);
expect(
  mobileResolver.includes("consumer_terminology.generated.dart") &&
    mobileResolver.includes("kConsumerTerminologyMessages") &&
    mobileResolver.includes("kConsumerTerminologyContractVersion"),
  "mobile resolver must consume the shared terminology projection",
);
// Every shared source key must be exposed by exactly one Flutter enum mapping.
// Keeping this derived from the source avoids a hand-maintained subset silently
// missing a new shared term (for example a shell destination) in CI.
const mobileSharedTerms = new Map();
const mobileContractMapping = /ConsumerTerm\.([A-Za-z0-9_]+) => '([^']+)'/g;
for (const match of mobileResolver.matchAll(mobileContractMapping)) {
  const [, term, key] = match;
  expect(!mobileSharedTerms.has(key), `mobile resolver maps ${key} more than once`);
  mobileSharedTerms.set(key, term);
}
for (const key of Object.keys(source.messages ?? {})) {
  const term = mobileSharedTerms.get(key);
  expect(term != null, `mobile resolver does not map shared source key ${key}`);
}
for (const [key, term] of mobileSharedTerms) {
  expect(source.messages[key] != null, `source omits mapped mobile term ${key}`);
  expect(
    mobileResolver.includes(`ConsumerTerm.${term} => '${key}'`),
    `mobile resolver does not map ${term} to ${key}`,
  );
}
for (const term of ["actionAskClara", "navigationToday", "navigationLifeMap", "navigationMedicines", "navigationProfile"]) {
  expect(
    mobileShell.includes(`ConsumerTerm.${term}`),
    `Unified shell is not wired to ${term}`,
  );
}

if (failed) process.exit(1);
process.stdout.write(
  `consumer terminology contract passed: ${Object.keys(source.messages).length} keys, ${source.version}.\n`,
);
