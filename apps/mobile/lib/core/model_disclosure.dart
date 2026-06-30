/// Model-disclosure model + chip for CLARA_Mobile (Requirement 7; Property P11).
///
/// This mirrors the **web** model-disclosure semantics
/// (`services/api/src/clara_api/compliance/notice.py::model_disclosure` and
/// `apps/web/app/chat/_v2` degraded-answer badge): a response envelope may carry
/// an `ai_disclosure` block with `model_family` / `model_version` / `is_fallback`
/// **only when the backend disclosure flag is on**; when absent the affordance is
/// omitted entirely rather than shown as a placeholder (Requirement 7.5).
///
/// `isFallback` is true **iff** the answer came from the local deterministic
/// synthesiser (the `local-synth-*` sentinel), exactly as the backend computes
/// it (Correctness Property P11 / Requirements 7.3, 7.4). [ModelDisclosure]
/// honours an explicit `is_fallback` boolean when present and otherwise derives
/// the same result from the model identity, so the mobile chip stays consistent
/// with the web badge regardless of which fields the envelope carries.
///
/// The [ModelDisclosureChip] is gated behind `model_disclosure_mobile_enabled`
/// via [MobileFeatureFlagResolver]; with the flag off (the default) the chip is
/// never rendered, preserving today's behaviour (Requirement 7, 15.1).
library;

import 'package:flutter/material.dart';

import 'feature_flags.dart';

/// The fallback sentinel prefix emitted by the ML local deterministic
/// synthesiser. Mirrors `notice._FALLBACK_PREFIX` so mobile and backend agree on
/// what counts as a degraded/fallback answer (Property P11).
const String kModelDisclosureFallbackPrefix = 'local-synth';

/// Placeholder used by the backend when the model identity is unknown.
const String kModelDisclosureUnknown = 'unknown';

/// Whether a model identity denotes the local deterministic fallback synth.
///
/// Case-insensitive prefix match on `local-synth`, mirroring the backend
/// `model_disclosure` helper. An empty/blank identity is not a fallback.
bool isLocalSynthModel(String? modelIdentity) {
  final raw = (modelIdentity ?? '').trim();
  if (raw.isEmpty) {
    return false;
  }
  return raw.toLowerCase().startsWith(kModelDisclosureFallbackPrefix);
}

/// The user-visible AI model disclosure for a single response (Requirement 7.3).
///
/// Immutable value type. Build it from a CLARA_API response envelope with
/// [ModelDisclosure.fromResponse], or directly from a raw `model_used` string
/// with [ModelDisclosure.fromModelUsed] (which reproduces the backend's
/// family/version split). Equality is value-based so it is trivially testable.
@immutable
class ModelDisclosure {
  const ModelDisclosure({
    required this.modelFamily,
    required this.modelVersion,
    required this.isFallback,
  });

  /// The model family (e.g. `deepseek`), or [kModelDisclosureUnknown].
  final String modelFamily;

  /// The model version (e.g. `v3.2`), or [kModelDisclosureUnknown].
  final String modelVersion;

  /// True **iff** the answer came from the local deterministic synth
  /// (degraded / fallback path). Mirrors web semantics (Property P11).
  final bool isFallback;

  /// Builds a disclosure from a raw `model_used` identity, reproducing the
  /// backend `model_disclosure` split: family/version split on the first
  /// hyphen, `unknown` when blank or hyphen-less, and `isFallback` true iff the
  /// identity starts with `local-synth`.
  factory ModelDisclosure.fromModelUsed(String? modelUsed) {
    final raw = (modelUsed ?? '').trim();
    final fallback = isLocalSynthModel(raw);
    if (raw.isEmpty) {
      return ModelDisclosure(
        modelFamily: kModelDisclosureUnknown,
        modelVersion: kModelDisclosureUnknown,
        isFallback: fallback,
      );
    }
    final hyphen = raw.indexOf('-');
    if (hyphen < 0) {
      return ModelDisclosure(
        modelFamily: raw,
        modelVersion: kModelDisclosureUnknown,
        isFallback: fallback,
      );
    }
    final family = raw.substring(0, hyphen);
    final version = raw.substring(hyphen + 1);
    return ModelDisclosure(
      modelFamily: family.isEmpty ? kModelDisclosureUnknown : family,
      modelVersion: version.isEmpty ? kModelDisclosureUnknown : version,
      isFallback: fallback,
    );
  }

  /// Parses the `ai_disclosure` block from a CLARA_API response envelope.
  ///
  /// Returns `null` — so the caller omits the chip entirely (Requirement 7.5) —
  /// when:
  ///   * [response] is null or not a map, or
  ///   * the envelope has no `ai_disclosure` block (the backend omits it when
  ///     its disclosure flag is off), or that block is not a map.
  ///
  /// `isFallback` is taken from an explicit `is_fallback` boolean when present;
  /// otherwise it is derived from the model identity (`model_used` if carried,
  /// else the `family-version` pair) using the same `local-synth` rule the
  /// backend applies, so the mobile chip and the web badge agree (Property P11).
  static ModelDisclosure? fromResponse(Object? response) {
    if (response is! Map) {
      return null;
    }
    final block = response['ai_disclosure'];
    if (block is! Map) {
      return null;
    }

    final family = _readString(block['model_family']) ?? kModelDisclosureUnknown;
    final version =
        _readString(block['model_version']) ?? kModelDisclosureUnknown;

    final explicit = block['is_fallback'];
    final bool isFallback;
    if (explicit is bool) {
      isFallback = explicit;
    } else {
      // Derive deterministically when the backend did not send the flag.
      final modelUsed = _readString(block['model_used']) ??
          _readString(response['model_used']);
      isFallback = isLocalSynthModel(modelUsed ?? '$family-$version');
    }

    return ModelDisclosure(
      modelFamily: family,
      modelVersion: version,
      isFallback: isFallback,
    );
  }

  /// A compact human-readable label, e.g. `deepseek v3.2`. Used by the chip and
  /// for screen-reader semantics (status conveyed by text, Requirement 10.5).
  String get label {
    final family = modelFamily.trim().isEmpty
        ? kModelDisclosureUnknown
        : modelFamily.trim();
    final version = modelVersion.trim();
    if (version.isEmpty || version == kModelDisclosureUnknown) {
      return family;
    }
    return '$family $version';
  }

  static String? _readString(Object? value) {
    if (value is String) {
      final trimmed = value.trim();
      return trimmed.isEmpty ? null : trimmed;
    }
    return null;
  }

  @override
  bool operator ==(Object other) =>
      other is ModelDisclosure &&
      other.modelFamily == modelFamily &&
      other.modelVersion == modelVersion &&
      other.isFallback == isFallback;

  @override
  int get hashCode => Object.hash(modelFamily, modelVersion, isFallback);

  @override
  String toString() =>
      'ModelDisclosure(family: $modelFamily, version: $modelVersion, '
      'isFallback: $isFallback)';
}

/// A small chip that surfaces the [ModelDisclosure] for a response.
///
/// Convey status by **text**, never colour alone (Requirement 10.5): a fallback
/// answer is labelled "Dự phòng nội bộ" (degraded · local fallback), mirroring
/// the web degraded badge, and exposes a screen-reader semantics label.
///
/// Gating (Requirement 7, 15.1): use [ModelDisclosureChip.maybe] to build the
/// chip only when the `model_disclosure_mobile_enabled` gate is open **and**
/// disclosure data is present; it returns `null` otherwise so the affordance is
/// omitted rather than shown as a placeholder (Requirement 7.5).
class ModelDisclosureChip extends StatelessWidget {
  const ModelDisclosureChip({
    super.key,
    required this.disclosure,
    this.isEnglish = false,
  });

  /// The disclosure to render. Non-null by construction.
  final ModelDisclosure disclosure;

  /// Vietnamese-first by default; pass `true` for the English label.
  final bool isEnglish;

  /// Builds a chip only when [resolver] enables the model-disclosure gate and
  /// [disclosure] is non-null; returns `null` otherwise (gate off or absent
  /// data ⇒ omit the affordance, Requirement 7.5 / 15.1).
  static Widget? maybe({
    required MobileFeatureFlagResolver resolver,
    required ModelDisclosure? disclosure,
    bool isEnglish = false,
    Key? key,
  }) {
    if (!resolver.modelDisclosureEnabled || disclosure == null) {
      return null;
    }
    return ModelDisclosureChip(
      key: key,
      disclosure: disclosure,
      isEnglish: isEnglish,
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    final fallbackText =
        isEnglish ? 'Degraded · local fallback' : 'Suy giảm · dự phòng nội bộ';
    final modelText =
        isEnglish ? 'Model: ${disclosure.label}' : 'Mô hình: ${disclosure.label}';

    final text = disclosure.isFallback ? fallbackText : modelText;
    final icon = disclosure.isFallback
        ? Icons.warning_amber_rounded
        : Icons.smart_toy_outlined;

    // Status conveyed by text + icon, never colour alone (Req 10.5). The full
    // semantics label is read by assistive tech.
    final semanticsLabel = disclosure.isFallback
        ? (isEnglish
            ? 'Degraded answer from local fallback model ${disclosure.label}'
            : 'Câu trả lời suy giảm từ mô hình dự phòng nội bộ ${disclosure.label}')
        : (isEnglish
            ? 'Answer from model ${disclosure.label}'
            : 'Câu trả lời từ mô hình ${disclosure.label}');

    final background = disclosure.isFallback
        ? scheme.errorContainer
        : scheme.surfaceContainerHighest;
    final foreground = disclosure.isFallback
        ? scheme.onErrorContainer
        : scheme.onSurfaceVariant;

    return Semantics(
      label: semanticsLabel,
      container: true,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: background,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 14, color: foreground),
            const SizedBox(width: 6),
            Flexible(
              child: Text(
                text,
                style: theme.textTheme.labelSmall?.copyWith(color: foreground),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
