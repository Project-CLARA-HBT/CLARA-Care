# CLARA Design Tokens (Canonical)

Canonical token contract for CLARA Care Spatial Design System (v3.0.0).

## Source of Truth
- `clara.tokens.json`: Canonical definition of brand colors, semantic status, light/dark neutrals, glass materials, spacing, radius, elevation, motion, and typography.
- `schema.json`: JSON schema validating token structure.

## Artifact Generation
To compile tokens into web CSS variables and Flutter Dart constants:
```bash
node generate.js
```

### Outputs
1. **Web:** `apps/web/styles/generated/tokens.css`
2. **Mobile:** `apps/mobile/lib/theme/generated/clara_tokens.g.dart`

Do NOT edit generated artifacts manually.
