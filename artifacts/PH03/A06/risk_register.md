# Risk Register — PH03 A06 (Mobile Flutter: Secure Password Reset & Recovery)

| Risk ID | Description | Severity | Likelihood | Mitigation Strategy | Owner | Status |
|---------|-------------|----------|------------|---------------------|-------|--------|
| RISK-01 | Stale offline caches and tokens leaking after password reset across shared family devices | HIGH | MEDIUM | `purgeOnPasswordReset()` triggered synchronously upon successful password reset, clearing all session credentials, JWT tokens, and scoped/unscoped LifeMap/CareGuard offline caches. | A06 (Mobile) | MITIGATED |
| RISK-02 | KeyStore / Keychain decryption failure or corruption causing fatal startup app crashes | HIGH | LOW | `AndroidOptions` configured with `resetOnError: true` and `encryptedSharedPreferences: true`; Keychain configured with `first_unlock_this_device` and `synchronizable: false` (iCloud sync disabled). | A06 (Mobile) | MITIGATED |
| RISK-03 | Biometric token protection bypass via in-memory session persistence | MEDIUM | LOW | `PersistentSessionStore` enforces `hasStoredCredentials && !isBiometricLocked`. When biometrics are enabled, hydration locks the session until `unlockBiometric()` succeeds. | A06 (Mobile) | MITIGATED |
| RISK-04 | User account enumeration via forgot-password probing | MEDIUM | MEDIUM | Client respects backend neutral envelope (`ForgotPasswordResponse.accepted = true`) and displays consistent neutral guidance regardless of account existence. | A06 (Mobile) | MITIGATED |
| RISK-05 | Insecure new password submission violating backend complexity/length policies | LOW | MEDIUM | Mobile UI handles 422 HTTP responses with user-facing Vietnamese error messages without leaking PII or internal validation traces. | A06 (Mobile) | MITIGATED |
