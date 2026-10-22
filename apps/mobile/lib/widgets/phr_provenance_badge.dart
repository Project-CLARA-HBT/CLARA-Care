import 'package:flutter/material.dart';

/// Provenance and verification badge for mobile PHR clinical observations.
class PhrProvenanceBadge extends StatelessWidget {
  const PhrProvenanceBadge({
    super.key,
    required this.sourceType,
    required this.isVerified,
    this.sourceName,
  });

  final String sourceType; // "EMR", "OCR", "SCRIBE", "SELF"
  final bool isVerified;
  final String? sourceName;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isSelf = sourceType == "SELF";

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: isSelf
            ? theme.colorScheme.errorContainer.withOpacity(0.4)
            : theme.colorScheme.primaryContainer.withOpacity(0.5),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: isSelf ? theme.colorScheme.error : theme.colorScheme.primary,
          width: 0.8,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            isSelf ? Icons.person_outline : (isVerified ? Icons.verified : Icons.document_scanner),
            size: 14,
            color: isSelf ? theme.colorScheme.error : theme.colorScheme.primary,
          ),
          const SizedBox(width: 4),
          Text(
            _badgeLabel(),
            style: theme.textTheme.labelSmall?.copyWith(
              fontWeight: FontWeight.bold,
              color: isSelf ? theme.colorScheme.error : theme.colorScheme.primary,
            ),
          ),
        ],
      ),
    );
  }

  String _badgeLabel() {
    switch (sourceType) {
      case "EMR":
        return sourceName ?? "Bệnh viện liên thông";
      case "OCR":
        return "Đơn thuốc quét";
      case "SCRIBE":
        return "Bác sĩ khám";
      case "SELF":
      default:
        return "Tự khai báo";
    }
  }
}
