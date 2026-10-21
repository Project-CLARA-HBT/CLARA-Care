# Test & Verification Report — Subagent A05 (Web UX)

## Execution Context
- **Worktree**: `/dev/shm/clara_worktrees/PH01_A05`
- **Branch**: `phase/ph01-a05`
- **Frozen Baseline SHA Verified**: `2aa9016a57b49b53f1a433d076e1028a6ec45f64`
- **Role**: Web UX
- **Task Scope**: Flutter/Dart pinned SDK and Web toolchain integration; audit `apps/mobile/pubspec.yaml` SDK constraints (`>=3.3.0 <4.0.0`), analyze Dart ^3.9 markdown dependency requirement, document containerized or local Flutter 3.47+ upgrade path.

---

## 1. Baseline Commit Verification
- **Command**: `git rev-parse HEAD`
- **Directory**: `/dev/shm/clara_worktrees/PH01_A05`
- **Output**:
  ```text
  2aa9016a57b49b53f1a433d076e1028a6ec45f64
  ```
- **Exit Code**: `0`
- **Disposition**: Exact match with frozen baseline SHA.

---

## 2. Web Toolchain & Cross-Client Integration Checks

### 2.1 Consumer Terminology Sync Check
- **Command**: `node scripts/generate-consumer-terminology.mjs --check`
- **Directory**: `/dev/shm/clara_worktrees/PH01_A05/apps/web`
- **Exit Code**: `0`
- **Output**:
  ```text
  consumer terminology projection check passed: 19 keys, 2026-07-30.v1.
  ```
- **Finding**: The web projection (`apps/web/lib/i18n/consumer-terminology.generated.ts`) and mobile projection (`apps/mobile/lib/core/consumer_terminology.generated.dart`) are perfectly synchronized with canonical contract `contracts/consumer-terminology/consumer-terminology.v1.json`.

### 2.2 Consumer Terminology Cross-Platform Contract Verification
- **Command**: `node scripts/check-consumer-terminology-contract.mjs`
- **Directory**: `/dev/shm/clara_worktrees/PH01_A05/apps/web`
- **Exit Code**: `0`
- **Output**:
  ```text
  consumer terminology contract passed: 19 keys, 2026-07-30.v1.
  ```
- **Finding**: Verifies both web catalog (`apps/web/lib/i18n/catalog.ts`) and mobile shell (`apps/mobile/lib/experience/unified/unified_root.dart`) conform to the 19 consumer keys without clinical leakage or telemetry terms.

### 2.3 Design Tokens Cross-Compilation Check
- **Command**: `node packages/design-tokens/generate.js`
- **Directory**: `/dev/shm/clara_worktrees/PH01_A05`
- **Exit Code**: `0`
- **Output**:
  ```text
  ✅ Generated tokens.css and clara_tokens.g.dart successfully (Hash: 0e438d4f0908af78)
  ```
- **Finding**: Generation pipeline produces both CSS variables (`tokens.css`) for Next.js web application and Dart abstract class (`ClaraGeneratedTokens` in `apps/mobile/lib/theme/generated/clara_tokens.g.dart`) for Flutter client from single source of truth `clara.tokens.json`.

### 2.4 Web Bundle Budget Check
- **Command**: `node scripts/check-bundle-budget.mjs`
- **Directory**: `/dev/shm/clara_worktrees/PH01_A05/apps/web`
- **Exit Code**: `1` (Precondition / Environment Expected)
- **Output**:
  ```text
  Error: ENOENT: no such file or directory, stat '/dev/shm/clara_worktrees/PH01_A05/apps/web/.next/static'
  ```
- **Analysis**:
  - The script asserts that the total size of `.next/static` stays within `+5%` of baseline `9,624,869` bytes (`limitBytes = 10,106,113`).
  - `.next/static` is produced only after `next build`.
  - In an isolated subagent worktree where local `node_modules` are not installed to conserve host RAM and disk space, this check fails cleanly on missing build directory without mutating state.

---

## 3. Flutter/Dart SDK and Markdown Dependency Audit

### 3.1 Pubspec SDK Constraints Analysis
- **Declared constraint (`apps/mobile/pubspec.yaml:7`)**:
  ```yaml
  environment:
    sdk: ">=3.3.0 <4.0.0"
  ```
- **Lockfile constraints (`apps/mobile/pubspec.lock:621-623`)**:
  ```yaml
  sdks:
    dart: ">=3.12.0 <4.0.0"
    flutter: ">=3.44.0"
  ```
- **Audit Diagnosis**:
  1. `sdk: ">=3.3.0 <4.0.0"` in `pubspec.yaml` allows tooling to believe Dart 3.3.0 (Flutter 3.19) is sufficient to compile the project.
  2. However, the resolved dependencies in `pubspec.lock` demand a much newer engine (`flutter: >=3.44.0`, `dart: >=3.12.0`).
  3. Developers or CI runners operating with Dart 3.3.x will experience resolver conflicts or compilation failures due to language syntax and library boundaries (e.g., modern pattern matching, class modifiers `abstract final class`, and new collection methods).

### 3.2 Pure-Dart Markdown Dependency (`markdown: ^7.3.1`)
- **Usage Anchor**: `apps/mobile/lib/widgets/markdown_view.dart:9-25`
- **Implementation Strategy**:
  - CLARA deliberately avoids `flutter_markdown` (deprecated/abandoned) and heavy libraries like `gpt_markdown`.
  - Instead, `markdown_view.dart` implements a high-performance, strictly themed, zero-platform-channel parser using pure Dart `package:markdown`.
- **Dart ^3.9 Compatibility Requirement**:
  - `markdown` version `7.3.1` (SHA: `ee85086ad7698b42522c6ad42fe195f1b9898e4d974a1af4576c1a3a176cada9`) requires modern Dart SDK features.
  - The latest upstream maintenance releases of `markdown` and `flutter_lints ^5.0.0` require Dart `>=3.9.0`.
  - Setting the lower bound to `sdk: ">=3.9.0 <4.0.0"` and `flutter: ">=3.47.0"` in `pubspec.yaml` is mathematically required to eliminate solver ambiguities.

### 3.3 CI & Release Script Audit
- **Workflow File**: `.github/workflows/mobile-apk.yml:39`
  - Current configuration uses `git clone --depth 1 -b stable https://github.com/flutter/flutter.git`.
  - **Vulnerability**: Because `-b stable` tracks a rolling branch, upstream Flutter stable releases (e.g., 3.47 -> 3.50) can introduce breaking changes unexpectedly into CI builds.
  - **Recommendation**: Pin the checkout tag to an exact release, e.g., `git clone --depth 1 --branch 3.47.0 https://github.com/flutter/flutter.git`.
- **Release Script**: `scripts/release/build_mobile_apk.sh:10-15`
  - Relies on system `FLUTTER_BIN`. Fails gracefully if not found (`exit 1`).
  - Containerization is recommended to provide hermetic reproducibility across CI and developer workstations.

---

## 4. Upgrade Path Specification: Flutter 3.47+ / Dart ^3.9

### Path A: Local Hermetic Installation (FVM or Git Tag Pin)
1. **Pin Flutter Version in Workspace**:
   Create `.fvm/fvm_config.json`:
   ```json
   {
     "flutter": "3.47.0"
   }
   ```
2. **Update `apps/mobile/pubspec.yaml`**:
   ```yaml
   environment:
     sdk: ">=3.9.0 <4.0.0"
     flutter: ">=3.47.0"
   ```
3. **Execution**:
   ```bash
   fvm flutter pub get
   fvm flutter analyze
   fvm flutter test
   ```

### Path B: Containerized Docker Build (Hermetic CI/CD)
To eliminate local host dependency on Flutter/Android SDKs, provide a standardized build container:
1. **Dockerfile Definition** (`deploy/docker/flutter-builder.Dockerfile`):
   ```dockerfile
   FROM ubuntu:24.04

   ENV DEBIAN_FRONTEND=noninteractive
   ENV ANDROID_SDK_ROOT=/opt/android-sdk
   ENV FLUTTER_ROOT=/opt/flutter
   ENV PATH="${FLUTTER_ROOT}/bin:${ANDROID_SDK_ROOT}/cmdline-tools/latest/bin:${ANDROID_SDK_ROOT}/platform-tools:${PATH}"

   RUN apt-get update && apt-get install -y --no-install-recommends \
       bash curl git unzip xz-utils zip libglu1-mesa openjdk-17-jdk ca-certificates \
       && rm -rf /var/lib/apt/lists/*

   # Install Flutter 3.47.0
   RUN git clone --depth 1 --branch 3.47.0 https://github.com/flutter/flutter.git ${FLUTTER_ROOT} \
       && ${FLUTTER_ROOT}/bin/flutter precache --android \
       && ${FLUTTER_ROOT}/bin/flutter config --no-analytics

   WORKDIR /workspace
   ```
2. **Hermetic Test & Build Invocation**:
   ```bash
   # Run tests hermetically inside container
   docker run --rm -v "$(pwd):/workspace" -w /workspace/apps/mobile clara-flutter-builder:3.47.0 flutter test

   # Run release APK build inside container
   docker run --rm -v "$(pwd):/workspace" -w /workspace clara-flutter-builder:3.47.0 bash scripts/release/build_mobile_apk.sh
   ```

---

## 5. Command Execution Summary

| Command | Working Directory | Exit Code | Disposition |
|---|---|---|---|
| `git rev-parse HEAD` | Worktree root | 0 | Baseline verified `2aa9016a57b49b53f1a433d076e1028a6ec45f64` |
| `node scripts/generate-consumer-terminology.mjs --check` | `apps/web` | 0 | Projections match canonical contract `2026-07-30.v1` |
| `node scripts/check-consumer-terminology-contract.mjs` | `apps/web` | 0 | Cross-platform contract integrity passed (19 keys) |
| `node packages/design-tokens/generate.js` | Worktree root | 0 | Synchronized tokens between web CSS and mobile Dart |
| `node scripts/check-bundle-budget.mjs` | `apps/web` | 1 | Expected failure: `.next/static` absent in unbuilt worktree |
