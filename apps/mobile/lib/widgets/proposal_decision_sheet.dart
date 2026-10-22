import 'package:flutter/material.dart';

/// Modal bottom sheet for explicit clinician admission decision on AI proposals.
///
/// Under GLHS R4 standards, AI recommendations remain in 'PENDING' state until
/// a qualified human clinician explicitly admits or rejects them.
class ProposalDecisionSheet extends StatelessWidget {
  const ProposalDecisionSheet({
    super.key,
    required this.proposalTitle,
    required this.modelProvenance,
    required this.attestationLevel,
    required this.onAdmit,
    required this.onReject,
  });

  final String proposalTitle;
  final String modelProvenance;
  final String attestationLevel;
  final VoidCallback onAdmit;
  final ValueChanged<String> onReject;

  static Future<void> show(
    BuildContext context, {
    required String proposalTitle,
    required String modelProvenance,
    required String attestationLevel,
    required VoidCallback onAdmit,
    required ValueChanged<String> onReject,
  }) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => ProposalDecisionSheet(
        proposalTitle: proposalTitle,
        modelProvenance: modelProvenance,
        attestationLevel: attestationLevel,
        onAdmit: onAdmit,
        onReject: onReject,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: SafeArea(
        top: false,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: theme.colorScheme.outlineVariant,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text(
              'Xem xét Đề xuất Lâm sàng AI',
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              proposalTitle,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: theme.colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Nguồn gốc Mô hình: $modelProvenance',
                    style: theme.textTheme.bodySmall?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Mức độ Xác thực Bằng chứng: $attestationLevel',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.primary,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () {
                      Navigator.of(context).pop();
                      onReject('Từ chối bởi bác sĩ');
                    },
                    style: OutlinedButton.styleFrom(
                      foregroundColor: theme.colorScheme.error,
                      side: BorderSide(color: theme.colorScheme.error),
                    ),
                    child: const Text('Từ chối'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: FilledButton(
                    onPressed: () {
                      Navigator.of(context).pop();
                      onAdmit();
                    },
                    child: const Text('Chấp thuận (Admit)'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
