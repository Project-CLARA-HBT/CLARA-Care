# Cross-Agent Dependency Request — Subagent A05 (Web UX) -> Subagent A06 (Mobile Flutter)

## Target Subagent
- **Target**: Subagent A06 (Mobile Flutter)
- **Path Lane**: `apps/mobile/`
- **Requesting Agent**: Subagent A05 (Web UX)

## Request Details

### Background
During the PH01 audit of the mobile toolchain and web/mobile integration contracts, Subagent A05 analyzed:
1. `apps/mobile/pubspec.yaml` line 7: `sdk: ">=3.3.0 <4.0.0"`
2. `apps/mobile/pubspec.lock` lines 621-623: `dart: ">=3.12.0 <4.0.0"`, `flutter: ">=3.44.0"`
3. The AST-based pure-Dart markdown parser in `apps/mobile/lib/widgets/markdown_view.dart` which imports `package:markdown/markdown.dart`.

### Requested Change
In order to eliminate SDK version drift and align with the Flutter 3.47+ / Dart ^3.9 toolchain upgrade:
1. Update `apps/mobile/pubspec.yaml`:
   ```yaml
   environment:
     sdk: ">=3.9.0 <4.0.0"
     flutter: ">=3.47.0"
   ```
2. Re-run `flutter pub get` with Flutter 3.47.0+ to ensure lockfile synchronization.

### Ownership Boundary Compliance
Because `apps/mobile/` is strictly within Subagent A06's write lane, Subagent A05 has not modified `apps/mobile/pubspec.yaml` directly, adhering to the multi-agent isolated worktree protocol.
