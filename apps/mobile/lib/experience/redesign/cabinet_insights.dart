// Cabinet intelligence layer for the CLARA_Mobile redesign (Experience_V3).
//
// A pure, presentational "insights" layer that sits on top of the existing
// Personal Medicine Cabinet data (the shared `/careguard/cabinet*` API) WITHOUT
// changing any CLARA_API contract. It derives everything it shows from the real
// cabinet items the screen already loaded — it never fabricates clinical data.
//
// Two pieces:
//
//   * [CabinetInsights] — a pure value type computed from the loaded items:
//     total count, distinct-active-ingredient count, expiry buckets (expired /
//     expiring-soon / valid / unknown), needs-review count, and low-stock count.
//     Pure + deterministic so it is unit-testable without widgets.
//   * [CabinetHealthCard] — a compact "sức khỏe tủ thuốc" summary surface that
//     visualizes those counts as tappable stat chips, so the user sees at a
//     glance what needs attention (hết hạn, sắp hết hạn, cần xem lại).
//
// All copy is Vietnamese-first. Status is conveyed by text + icon (not color
// alone). This module holds NO clinical logic and makes NO network calls.

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../../theme/components/clara_card.dart';
import '../../theme/tokens.dart';

/// Number of days before expiry within which an item is "sắp hết hạn".
const int kCabinetExpiringSoonDays = 30;

/// A quantity at or below this is flagged "sắp hết" (low stock) — a gentle,
/// non-clinical reorder nudge derived purely from the item's own quantity.
const int kCabinetLowStockThreshold = 5;

/// Expiry bucket for a single item, derived only from its expiry field.
enum CabinetExpiryBucket { unknown, valid, expiringSoon, expired }

/// Classifies an ISO expiry string into a bucket, purely (testable, no widgets).
CabinetExpiryBucket classifyExpiry(String expiresOn, {DateTime? now}) {
  final trimmed = expiresOn.trim();
  if (trimmed.isEmpty) return CabinetExpiryBucket.unknown;
  final parsed = DateTime.tryParse(trimmed);
  if (parsed == null) return CabinetExpiryBucket.unknown;
  final reference = now ?? DateTime.now();
  final expiryDay = DateTime(parsed.year, parsed.month, parsed.day);
  final today = DateTime(reference.year, reference.month, reference.day);
  final days = expiryDay.difference(today).inDays;
  if (days < 0) return CabinetExpiryBucket.expired;
  if (days <= kCabinetExpiringSoonDays) return CabinetExpiryBucket.expiringSoon;
  return CabinetExpiryBucket.valid;
}

/// A minimal read-only view of a cabinet item, so this module does not depend on
/// the screen's private `_CabinetMedicine` type. The screen adapts its items to
/// these records before computing insights.
typedef CabinetInsightItem = ({
  String distinctKey,
  String expiresOn,
  bool needsReview,
  num quantity,
});

/// Aggregate, deterministic insights derived from the loaded cabinet items.
@immutable
class CabinetInsights {
  const CabinetInsights({
    required this.total,
    required this.distinctIngredients,
    required this.expired,
    required this.expiringSoon,
    required this.valid,
    required this.unknownExpiry,
    required this.needsReview,
    required this.lowStock,
  });

  final int total;
  final int distinctIngredients;
  final int expired;
  final int expiringSoon;
  final int valid;
  final int unknownExpiry;
  final int needsReview;
  final int lowStock;

  /// Whether anything needs the user's attention (drives the card's tone).
  bool get hasAttentionItems =>
      expired > 0 || expiringSoon > 0 || needsReview > 0 || lowStock > 0;

  /// Whether there is enough to run a meaningful interaction check.
  bool get canCheckInteractions => distinctIngredients >= 2;

  static CabinetInsights fromItems(
    List<CabinetInsightItem> items, {
    DateTime? now,
  }) {
    var expired = 0;
    var expiringSoon = 0;
    var valid = 0;
    var unknown = 0;
    var needsReview = 0;
    var lowStock = 0;
    final distinct = <String>{};

    for (final item in items) {
      switch (classifyExpiry(item.expiresOn, now: now)) {
        case CabinetExpiryBucket.expired:
          expired++;
        case CabinetExpiryBucket.expiringSoon:
          expiringSoon++;
        case CabinetExpiryBucket.valid:
          valid++;
        case CabinetExpiryBucket.unknown:
          unknown++;
      }
      if (item.needsReview) needsReview++;
      if (item.quantity > 0 && item.quantity <= kCabinetLowStockThreshold) {
        lowStock++;
      }
      final key = item.distinctKey.trim();
      if (key.isNotEmpty) distinct.add(key.toLowerCase());
    }

    return CabinetInsights(
      total: items.length,
      distinctIngredients: distinct.length,
      expired: expired,
      expiringSoon: expiringSoon,
      valid: valid,
      unknownExpiry: unknown,
      needsReview: needsReview,
      lowStock: lowStock,
    );
  }
}

/// A compact "sức khỏe tủ thuốc" summary card visualizing [CabinetInsights] as
/// a row of stat chips. Purely presentational; the parent owns the data and the
/// optional tap handlers (e.g. filter the list by a bucket).
class CabinetHealthCard extends StatelessWidget {
  const CabinetHealthCard({
    super.key,
    required this.insights,
    this.onTapExpiring,
    this.onTapExpired,
    this.onTapReview,
  });

  final CabinetInsights insights;
  final VoidCallback? onTapExpiring;
  final VoidCallback? onTapExpired;
  final VoidCallback? onTapReview;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final textScaler = A11y.resolveTextScaler(context);

    final headline = insights.hasAttentionItems
        ? 'Tủ thuốc cần bạn để ý một vài mục'
        : 'Tủ thuốc của bạn đang ổn';
    final headlineIcon = insights.hasAttentionItems
        ? Icons.notifications_active_outlined
        : Icons.verified_outlined;
    final headlineColor = insights.hasAttentionItems
        ? Colors.orange.shade800
        : Colors.green.shade700;

    return ClaraCard.static_(
      semanticLabel: 'Tổng quan sức khỏe tủ thuốc',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              ExcludeSemantics(
                child: Icon(headlineIcon, size: 20, color: headlineColor),
              ),
              const SizedBox(width: ClaraTokens.spaceSm),
              Expanded(
                child: Text(
                  headline,
                  style: theme.textTheme.titleSmall
                      ?.copyWith(fontWeight: FontWeight.w700),
                  textScaler: textScaler,
                ),
              ),
            ],
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          Wrap(
            spacing: ClaraTokens.spaceSm,
            runSpacing: ClaraTokens.spaceSm,
            children: [
              _InsightStat(
                icon: Icons.medication_outlined,
                value: '${insights.total}',
                label: 'thuốc',
                tint: scheme.primary,
              ),
              _InsightStat(
                icon: Icons.science_outlined,
                value: '${insights.distinctIngredients}',
                label: 'hoạt chất',
                tint: scheme.primary,
              ),
              if (insights.expired > 0)
                _InsightStat(
                  icon: Icons.event_busy_outlined,
                  value: '${insights.expired}',
                  label: 'đã hết hạn',
                  tint: scheme.error,
                  onTap: onTapExpired,
                ),
              if (insights.expiringSoon > 0)
                _InsightStat(
                  icon: Icons.hourglass_bottom_outlined,
                  value: '${insights.expiringSoon}',
                  label: 'sắp hết hạn',
                  tint: Colors.orange.shade800,
                  onTap: onTapExpiring,
                ),
              if (insights.needsReview > 0)
                _InsightStat(
                  icon: Icons.help_outline,
                  value: '${insights.needsReview}',
                  label: 'cần xem lại',
                  tint: Colors.orange.shade800,
                  onTap: onTapReview,
                ),
              if (insights.lowStock > 0)
                _InsightStat(
                  icon: Icons.inventory_2_outlined,
                  value: '${insights.lowStock}',
                  label: 'sắp hết',
                  tint: Colors.orange.shade800,
                ),
            ],
          ),
        ],
      ),
    );
  }
}

/// A single stat pill (icon + value + label). Optionally tappable to jump to
/// the related items. Meaning is carried by the label text, not color alone.
class _InsightStat extends StatelessWidget {
  const _InsightStat({
    required this.icon,
    required this.value,
    required this.label,
    required this.tint,
    this.onTap,
  });

  final IconData icon;
  final String value;
  final String label;
  final Color tint;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final textScaler = A11y.resolveTextScaler(context);

    final content = Container(
      padding: const EdgeInsets.symmetric(
        horizontal: ClaraTokens.spaceMd,
        vertical: ClaraTokens.spaceSm,
      ),
      decoration: BoxDecoration(
        color: tint.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
        border: Border.all(color: tint.withValues(alpha: 0.24)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          ExcludeSemantics(child: Icon(icon, size: 18, color: tint)),
          const SizedBox(width: ClaraTokens.spaceSm),
          Text(
            value,
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w700,
              color: scheme.onSurface,
            ),
            textScaler: textScaler,
          ),
          const SizedBox(width: 4),
          Text(
            label,
            style: theme.textTheme.bodySmall
                ?.copyWith(color: scheme.onSurfaceVariant),
            textScaler: textScaler,
          ),
        ],
      ),
    );

    final semantic = Semantics(
      label: '$value $label',
      button: onTap != null,
      container: true,
      child: content,
    );

    if (onTap == null) return semantic;
    return MinTapTarget(
      child: Material(
        type: MaterialType.transparency,
        child: InkWell(
          borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
          onTap: onTap,
          child: semantic,
        ),
      ),
    );
  }
}
