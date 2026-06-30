/// Role-gated research telemetry for CLARA_Mobile (Requirement 19.4).
///
/// Mirrors the web role-gating defined in Requirement 3:
///
///   * The detailed telemetry rail is shown **if and only if** the requesting
///     role is `admin` (R3.1, R3.3).
///   * Every non-admin role still sees a sanitized progress summary whose
///     labels are drawn from the pipeline stage names with internal labels
///     such as "RAG mode" and "retrieval" stripped (R3.2, R3.5).
///   * The decision is **fail-closed**: if the role cannot be evaluated, no
///     telemetry is exposed and — on mobile — the research job is blocked
///     (R3.6, R19.4).
///
/// The gate is a pure function of the role alone so it can be unit/property
/// tested in isolation without rendering widgets.
library;

/// Recognized application roles.
///
/// Mirrors the web `UserRole` union (`normal | researcher | doctor | admin`)
/// so the mobile gate accepts exactly the same set of evaluable roles.
const Set<String> kKnownResearchRoles = <String>{
  'normal',
  'researcher',
  'doctor',
  'admin',
};

/// The role that unlocks the detailed telemetry rail.
const String kAdminRole = 'admin';

/// Internal telemetry labels that must never reach the sanitized summary.
///
/// Mirrors the web `stripTelemetryLabels` patterns (`research mode`,
/// `rag mode`, `fallback mode`, `retrieval`, `policy: warn/allow`). Matching is
/// case-insensitive.
final List<RegExp> _telemetryLabelPatterns = <RegExp>[
  RegExp(r'research\s+mode', caseSensitive: false),
  RegExp(r'rag\s+mode', caseSensitive: false),
  RegExp(r'fallback\s+mode', caseSensitive: false),
  RegExp(r'retrieval', caseSensitive: false),
  RegExp(r'policy:\s*warn(?:\s*/\s*allow)?', caseSensitive: false),
  RegExp(r'policy:\s*allow(?:\s*/\s*warn)?', caseSensitive: false),
];

final RegExp _collapseWhitespace = RegExp(r'\s{2,}');

/// Removes internal telemetry labels from a user-facing [text],
/// case-insensitively, repeating until the result is stable, then collapses any
/// doubled whitespace left behind. Returns an empty string for empty input.
String stripTelemetryLabels(String? text) {
  if (text == null || text.isEmpty) {
    return '';
  }
  var previous = text;
  while (true) {
    var current = previous;
    for (final pattern in _telemetryLabelPatterns) {
      current = current.replaceAll(pattern, '');
    }
    if (current == previous) {
      break;
    }
    previous = current;
  }
  return previous.replaceAll(_collapseWhitespace, ' ').trim();
}

/// Outcome of evaluating the role-based telemetry gate for the research
/// surface. All fields are derived from the role alone.
class TelemetryGateDecision {
  const TelemetryGateDecision({
    required this.canEvaluate,
    required this.showDetailed,
    required this.showSummary,
  });

  /// Whether the role could be evaluated against [kKnownResearchRoles].
  final bool canEvaluate;

  /// Whether the detailed telemetry rail may be shown (admin only).
  final bool showDetailed;

  /// Whether the sanitized progress summary may be shown.
  final bool showSummary;

  /// Fail-closed: when the role cannot be evaluated, the research job is
  /// blocked (R19.4).
  bool get blockJob => !canEvaluate;
}

/// Evaluates the role-gate for research telemetry (R3, mirrored per R19.4).
///
/// * Unknown / missing / unparseable role -> `canEvaluate == false`,
///   everything denied (fail-closed), and [TelemetryGateDecision.blockJob] is
///   `true`.
/// * `admin` -> detailed rail + summary.
/// * Any other recognized role -> summary only.
TelemetryGateDecision evaluateTelemetryGate(String? role) {
  final normalized = role?.trim().toLowerCase();
  if (normalized == null ||
      normalized.isEmpty ||
      !kKnownResearchRoles.contains(normalized)) {
    return const TelemetryGateDecision(
      canEvaluate: false,
      showDetailed: false,
      showSummary: false,
    );
  }
  final isAdmin = normalized == kAdminRole;
  return TelemetryGateDecision(
    canEvaluate: true,
    showDetailed: isAdmin,
    showSummary: true,
  );
}
