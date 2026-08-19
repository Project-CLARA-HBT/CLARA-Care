// Friendly empty state for CLARA_Mobile Experience_V2 (Requirement 6.2).
//
// A Vietnamese-first empty-state surface shown when a data region has no items:
// a calm icon, a short title, a guiding message, and an optional action slot
// (e.g., "Tạo mới"). Copy defaults are Vietnamese; callers may override either
// string for a more specific surface ("Chưa có hồ sơ", "Không có kết quả", …).
//
// This is distinct from the error/offline states: a failed load reuses the
// existing `ErrorRetryView` (`lib/widgets/error_retry_view.dart`) and offline
// surfaces reuse `OfflineBanner` (`lib/widgets/offline_banner.dart`) — this
// widget is only for the "loaded successfully, but nothing to show" case.
//
// Accessibility:
//   * The whole surface is wrapped with `A11yLabeled` so a screen reader
//     announces the title as a region heading and reads the message as its
//     value (status conveyed by text/semantics, not color — Requirement 9.5).
//   * The decorative icon is excluded from semantics to avoid a duplicate
//     announcement.
//
// Pure UI: spacing/radius read from `ClaraTokens`; no analytics, no I/O.

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../../theme/tokens.dart';

/// Vietnamese-first default empty-state title.
const String kClaraEmptyStateTitle = 'Chưa có dữ liệu';

/// Vietnamese-first default empty-state guidance message.
const String kClaraEmptyStateMessage =
    'Hiện chưa có nội dung để hiển thị. Khi có dữ liệu mới, nó sẽ xuất hiện ở đây.';

/// A friendly, Vietnamese-first empty state with an icon, title, message, and
/// an optional action button slot (Requirement 6.2).
///
/// ```dart
/// ClaraEmptyState(
///   icon: Icons.folder_open_outlined,
///   title: 'Chưa có hồ sơ',
///   message: 'Bạn chưa lưu hồ sơ nào.',
///   action: ClaraSecondaryButtonOrFilledButton(...),
/// );
/// ```
///
/// All copy defaults to Vietnamese; pass [title]/[message] to tailor a surface.
class ClaraEmptyState extends StatelessWidget {
  const ClaraEmptyState({
    super.key,
    this.icon = Icons.inbox_outlined,
    this.title = kClaraEmptyStateTitle,
    this.message = kClaraEmptyStateMessage,
    this.action,
    this.padding = const EdgeInsets.all(ClaraTokens.spaceXl),
  });

  /// Leading status icon (decorative; the title/message carry the meaning).
  final IconData icon;

  /// Vietnamese-first heading; announced as a region header.
  final String title;

  /// Vietnamese-first guiding message; announced as the region value.
  final String message;

  /// Optional action affordance rendered below the message (e.g., a button).
  final Widget? action;

  /// Outer padding around the centered content.
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return A11yLabeled(
      label: title,
      value: message,
      isHeader: true,
      child: Center(
        child: Padding(
          padding: padding,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Decorative icon: excluded so the title/message are the single
              // authoritative announcement.
              ExcludeSemantics(
                child: Icon(
                  icon,
                  size: 48,
                  color: scheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: ClaraTokens.spaceMd),
              Text(
                title,
                textAlign: TextAlign.center,
                style: theme.textTheme.titleMedium?.copyWith(
                  color: scheme.onSurface,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: ClaraTokens.spaceSm),
              Text(
                message,
                textAlign: TextAlign.center,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: scheme.onSurfaceVariant,
                ),
              ),
              if (action != null) ...[
                const SizedBox(height: ClaraTokens.spaceLg),
                action!,
              ],
            ],
          ),
        ),
      ),
    );
  }
}
