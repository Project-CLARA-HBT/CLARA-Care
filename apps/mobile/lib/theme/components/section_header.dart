// Section-header component for CLARA_Mobile Experience_V2 (Req 2.2, 2.3, 9.3).
//
// `SectionHeader` is the consistent heading used to title a region on the
// modern surfaces (Home quick-actions, settings groups, recent items, etc.). It
// renders the [title] with the M3 title type scale and an optional trailing
// action (e.g., a "Xem tất cả" text button), with padding read from
// `ClaraTokens` so section rhythm stays consistent and tunable in one place.
//
// Accessibility (Requirement 9.3): the title is wrapped in
// `A11yLabeled(isHeader: true, ...)` so assistive technology announces it as a
// heading and users can navigate the screen by headings. The title text also
// honors the OS dynamic text-scaling preference via `A11y.resolveTextScaler`
// (Requirement 2.3) and ellipsizes rather than clipping when space is tight.
//
// Copy is caller-provided and Vietnamese-first: [title] is supplied by the call
// site (no hard-coded English lives here).

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../tokens.dart';

/// A heading row that titles a content region and is exposed as an
/// accessibility header.
///
/// Pure presentation: it lays out the [title] (styled with [emphasize] choosing
/// `titleLarge` vs. `titleMedium`) and an optional [trailing] action, applies
/// token-driven padding, and marks the heading via `A11yLabeled(isHeader:
/// true)` (Requirement 9.3). No I/O or analytics.
class SectionHeader extends StatelessWidget {
  const SectionHeader({
    super.key,
    required this.title,
    this.trailing,
    this.emphasize = false,
  });

  /// Heading text and screen-reader header label (caller-provided, localized).
  final String title;

  /// Optional trailing action widget (e.g., a "see all" button) aligned to the
  /// end of the row.
  final Widget? trailing;

  /// When `true`, uses the larger `titleLarge` style for a more prominent
  /// section heading; otherwise uses `titleMedium`. Defaults to `false`.
  final bool emphasize;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final titleStyle = emphasize ? textTheme.titleLarge : textTheme.titleMedium;

    // Honor OS text scaling (clamped) so the heading stays legible without
    // clipping (Requirement 2.3).
    final textScaler = A11y.resolveTextScaler(context);

    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: ClaraTokens.spaceMd,
        vertical: ClaraTokens.spaceSm,
      ),
      child: Row(
        children: [
          // The heading itself, announced as an accessibility header (Req 9.3).
          Expanded(
            child: A11yLabeled(
              label: title,
              isHeader: true,
              child: Text(
                title,
                style: titleStyle,
                textScaler: textScaler,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ),
          if (trailing != null) ...[
            const SizedBox(width: ClaraTokens.spaceSm),
            trailing!,
          ],
        ],
      ),
    );
  }
}
