# Source Authenticity, Provenance Integrity & Licensing Audit (PH10)

## Executive Summary
This research investigation audits external medical vocabulary sources, knowledge bases, and drug mapping datasets to verify source authenticity, licensing compliance, and provenance tracking across The CLARA Care.

## Audited External Knowledge Sources

| Source Identifier | Publisher / Regulatory Authority | License / Terms of Use | Usage in CLARA | Verification Status |
|---|---|---|---|---|
| **ICD-10-CM / VN** | WHO & Vietnam Ministry of Health (MOH) | Open Public Health Classification | Diagnostic classification coding | **VERIFIED** (Official MOH Circular) |
| **LOINC** | Regenstrief Institute | Free for global clinical use | Laboratory & vital sign normalization | **VERIFIED** (Standard clinical terms) |
| **RxNorm** | US National Library of Medicine (NLM) | Public Domain (U.S. Govt) | Active ingredient normalization | **VERIFIED** (Standard mapping) |
| **Vietnam Drug Circulars** | Cục Quản lý Dược (DAV / MOH Vietnam) | Public Regulatory Register | Brand name & registration codes | **VERIFIED** (National drug formulary) |
| **PubMed / Europe PMC** | NLM / EMBL-EBI | Open Access & CC BY subsets | Living evidence tier 2 retrieval | **VERIFIED** (Open access filtered) |

## Provenance Integrity Invariants
1. **Cryptographic Source Fingerprinting:** Each external dataset release (e.g. quarterly RxNorm updates or MOH circular revisions) is sealed with an SHA-256 manifest hash in `knowledge_sources`.
2. **Attribution & Licensing Guardrails:** Responses generated from external knowledge citations include attribution entries without republishing proprietary texts.
3. **No Commercial Data Resale:** External vocabularies are utilized solely for clinical normalization and patient safety DDI checking.
