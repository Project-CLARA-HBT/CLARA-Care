# E07: Canonicalization Conformance Benchmark Summary

- **Freeze ID**: `GLHS-CANONICALIZATION-E07-20260928-01`
- **Analyzed At (UTC)**: `2026-09-28T19:19:26.836252+00:00`
- **Total Test Vectors**: `35`
- **Python v2-RFC8785 Passed**: `35`
- **Python v2-RFC8785 Failed**: `0`
- **Byte Equality Rate**: `100.00%`
- **Cross-Runtime Determinism**: `True`
- **Claim Eligible**: `True`

## Vector Category Summary

| Category | Total Vectors | Passed | Pass Rate |
| --- | --- | --- | --- |
| `containers` | 4 | 4 | 100.00% |
| `float_exponent` | 3 | 3 | 100.00% |
| `float_extreme` | 2 | 2 | 100.00% |
| `float_integral` | 1 | 1 | 100.00% |
| `float_subnormal` | 2 | 2 | 100.00% |
| `float_zero` | 1 | 1 | 100.00% |
| `integer_limits` | 2 | 2 | 100.00% |
| `integer_primitives` | 3 | 3 | 100.00% |
| `medical_assertion` | 1 | 1 | 100.00% |
| `rejection_decimal_precision` | 1 | 1 | 100.00% |
| `rejection_integer_overflow` | 1 | 1 | 100.00% |
| `rejection_non_finite` | 1 | 1 | 100.00% |
| `rejection_surrogate` | 2 | 2 | 100.00% |
| `rfc8785_official` | 1 | 1 | 100.00% |
| `string_escaping` | 2 | 2 | 100.00% |
| `string_unicode` | 1 | 1 | 100.00% |
| `type_distinction` | 2 | 2 | 100.00% |
| `utf16_sorting` | 5 | 5 | 100.00% |

## Conformance Invariants
- **Authoritative Profile**: `clara.canonical-json.v2-rfc8785`
- **Key Ordering**: UTF-16 code units (RFC 8785 Section 3.2.3)
- **Character Escaping**: Control chars 0x00-0x1F hex escaped, raw UTF-8 for >=0x20
- **Surrogate Rejection**: Strict rejection of lone surrogates (0xD800 - 0xDFFF)
- **Integer Safety**: I-JSON safe integer range `[-9007199254740991, 9007199254740991]`
- **Float Formatting**: ECMAScript `Number::toString` formatting, `-0.0` normalized to `0`
