// PHR profile-completeness meter for the CLARA_Mobile redesign (Experience_V3).
//
// A friendly, at-a-glance summary of how complete the user's health record is,
// so the PHR feels less like a blank form and more like a guided profile. It is
// PURE + presentational: it derives everything from the fields the record
// already carries and makes NO network calls and stores no PII. The parent owns
// the data and passes the computed [PhrCompleteness] value.
//
// The score is a simple weighted fraction across the health-record dimensions
// that matter most for decision support and emergencies (identity, vitals,
// emergency contact, allergies, conditions, medications). It is intentionally
// non-clinical: it measures how much the user has filled in, never judges the
// content. Vietnamese-first copy.

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../../theme/components/clara_card.dart';
import '../../theme/tokens.dart';

/// A single completeness dimension with a filled flag and a friendly label.
@immutable
class PhrCompletenessItem {
  const PhrCompletenessItem({
    required this.label,
    required this.filled,
  });

  final String label;
  final bool filled;
}

/// Aggregate profile completeness derived from the loaded PHR record.
@immutable
class PhrCompleteness {
  const PhrCompleteness({required this.items});

  final List<PhrCompletenessItem> items;

  int get filledCount => items.where((i) => i.filled).length;
  int get totalCount => items.length;

  /// 0.0–1.0 fraction of dimensions filled.
  double get fraction => totalCount == 0 ? 0.0 : filledCount / totalCount;

  /// 0–100 percentage, rounded.
  int get percent => (fraction * 100).round();

  /// The dimensions still missing, so the UI can nudge the next best action.
  List<PhrCompletenessItem> get missing =>
      items.where((i) => !i.filled).toList();

  /// Builds the completeness summary from the live PHR field values + entry
  /// counts. Pure: a field counts as filled when it has non-whitespace content
  /// (or, for a category, at least one entry). Labels are Vietnamese-first and
  /// name the next best action the user can take.
  static PhrCompleteness compute({
    required String fullName,
    required String dateOfBirth,
    required String gender,
    required String bloodType,
    required String heightCm,
    required String weightKg,
    required String phone,
    required String emergencyContactName,
    required String emergencyContactPhone,
    required int allergyCount,
    required int conditionCount,
    required int medicationCount,
  }) {
    bool has(String v) => v.trim().isNotEmpty;
    return PhrCompleteness(
      items: [
        PhrCompletenessItem(label: 'Họ tên', filled: has(fullName)),
        PhrCompletenessItem(label: 'Ngày sinh', filled: has(dateOfBirth)),
        PhrCompletenessItem(label: 'Giới tính', filled: has(gender)),
        PhrCompletenessItem(label: 'Nhóm máu', filled: has(bloodType)),
        PhrCompletenessItem(
          label: 'Chiều cao & cân nặng',
          filled: has(heightCm) && has(weightKg),
        ),
        PhrCompletenessItem(label: 'Số điện thoại', filled: has(phone)),
        PhrCompletenessItem(
          label: 'Liên hệ khẩn cấp',
          filled: has(emergencyContactName) && has(emergencyContactPhone),
        ),
        PhrCompletenessItem(label: 'Dị ứng', filled: allergyCount > 0),
        PhrCompletenessItem(label: 'Bệnh nền', filled: conditionCount > 0),
        PhrCompletenessItem(
            label: 'Thuốc đang dùng', filled: medicationCount > 0),
      ],
    );
  }
}

/// A compact card visualizing [PhrCompleteness] as a progress bar + the next
/// few missing items. Purely presentational. Meaning is carried by text, not
/// color alone (a11y).
class PhrCompletenessCard extends StatelessWidget {
  const PhrCompletenessCard({
    super.key,
    required this.completeness,
    required this.title,
    required this.completeMessage,
    required this.nextUpLabel,
  });

  final PhrCompleteness completeness;

  /// e.g. "Hồ sơ của bạn".
  final String title;

  /// Shown when everything is filled, e.g. "Hồ sơ đã đầy đủ".
  final String completeMessage;

  /// Prefix for the missing-items hint, e.g. "Nên bổ sung".
  final String nextUpLabel;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final textScaler = A11y.resolveTextScaler(context);
    final pct = completeness.percent;
    final missing = completeness.missing;

    final tint = pct >= 80
        ? Colors.green.shade700
        : pct >= 50
            ? scheme.primary
            : Colors.orange.shade800;

    return ClaraCard.static_(
      semanticLabel: '$title: hoàn thiện $pct phần trăm',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  title,
                  style: theme.textTheme.titleSmall
                      ?.copyWith(fontWeight: FontWeight.w700),
                  textScaler: textScaler,
                ),
              ),
              Text(
                '$pct%',
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w800,
                  color: tint,
                ),
                textScaler: textScaler,
              ),
            ],
          ),
          const SizedBox(height: ClaraTokens.spaceSm),
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              value: completeness.fraction,
              minHeight: 8,
              backgroundColor: scheme.surfaceContainerHighest,
              valueColor: AlwaysStoppedAnimation<Color>(tint),
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceSm),
          if (missing.isEmpty)
            Row(
              children: [
                ExcludeSemantics(
                  child: Icon(Icons.verified_outlined,
                      size: 16, color: Colors.green.shade700),
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    completeMessage,
                    style: theme.textTheme.bodySmall,
                    textScaler: textScaler,
                  ),
                ),
              ],
            )
          else
            Text(
              '$nextUpLabel: ${missing.take(3).map((i) => i.label).join(', ')}',
              style: theme.textTheme.bodySmall
                  ?.copyWith(color: scheme.onSurfaceVariant),
              textScaler: textScaler,
            ),
        ],
      ),
    );
  }
}
