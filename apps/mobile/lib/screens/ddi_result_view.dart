import 'package:flutter/material.dart';

import '../core/careguard_offline_cache.dart';
import '../core/ddi_user_view.dart';

/// Renders the End_User DDI projection ([DdiUserView]) — risk level, alerts,
/// recommendations, and reference sources only. Runtime mode, fallback flags,
/// and connector `source_errors` are never surfaced (Requirements 3.1, 3.6,
/// 8.4). Shared by the manual DDI check screen and the cabinet CRUD screen so
/// both surfaces present interaction results identically.
class DdiResultView extends StatelessWidget {
  const DdiResultView({super.key, required this.view, this.offlineCachedAt});

  final DdiUserView view;

  /// When non-null, this result was served from the offline cache and is stale.
  final DateTime? offlineCachedAt;

  Color _riskColor(BuildContext context) {
    switch (view.riskLevel) {
      case 'high':
      case 'critical':
        return Colors.red.shade700;
      case 'medium':
        return Colors.orange.shade800;
      case 'low':
        return Colors.green.shade700;
      default:
        return Theme.of(context).colorScheme.outline;
    }
  }

  String _formatCachedAt(DateTime value) {
    final local = value.toLocal();
    String two(int n) => n.toString().padLeft(2, '0');
    return '${two(local.day)}/${two(local.month)}/${local.year} '
        '${two(local.hour)}:${two(local.minute)}';
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: 8),
        if (offlineCachedAt != null)
          Card(
            color: Colors.amber.shade50,
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.cloud_off,
                          size: 18, color: Colors.amber.shade900),
                      const SizedBox(width: 6),
                      Text(
                        careguardOfflineLabel,
                        style: TextStyle(
                          fontWeight: FontWeight.w700,
                          color: Colors.amber.shade900,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Đang hiển thị kết quả lưu gần nhất '
                    '(${_formatCachedAt(offlineCachedAt!)}). Kết quả có thể đã cũ.',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
          ),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text('Kết quả tổng quan',
                        style: Theme.of(context).textTheme.titleSmall),
                    const Spacer(),
                    Chip(
                      label: Text('Mức rủi ro: ${view.riskLabel}'),
                      backgroundColor:
                          _riskColor(context).withValues(alpha: 0.15),
                      side: BorderSide(color: _riskColor(context)),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                if (view.alerts.isEmpty)
                  const Text('Chưa ghi nhận cảnh báo tương tác rõ ràng.')
                else
                  ...view.alerts.map(
                    (alert) => _AlertTile(alert: alert),
                  ),
              ],
            ),
          ),
        ),
        if (view.recommendations.isNotEmpty)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Khuyến nghị',
                      style: Theme.of(context).textTheme.titleSmall),
                  const SizedBox(height: 6),
                  ...view.recommendations.map(
                    (rec) => Padding(
                      padding: const EdgeInsets.only(bottom: 4),
                      child: Text('• $rec'),
                    ),
                  ),
                ],
              ),
            ),
          ),
        if (view.sources.isNotEmpty)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Nguồn tham khảo',
                      style: Theme.of(context).textTheme.titleSmall),
                  const SizedBox(height: 6),
                  Text(view.sources.join(', ')),
                ],
              ),
            ),
          ),
      ],
    );
  }
}

/// A single interaction alert rendered professionally: a leading severity badge
/// (color + icon + Vietnamese text so meaning is never color-only), the two
/// interacting medications as chips, and the message + optional detail line.
class _AlertTile extends StatelessWidget {
  const _AlertTile({required this.alert});

  final DdiAlert alert;

  Color _severityColor(BuildContext context) {
    switch (alert.severity) {
      case 'critical':
        return Colors.red.shade900;
      case 'high':
        return Colors.red.shade700;
      case 'medium':
        return Colors.orange.shade800;
      case 'low':
        return Colors.green.shade700;
      default:
        return Theme.of(context).colorScheme.outline;
    }
  }

  IconData _severityIcon() {
    switch (alert.severity) {
      case 'critical':
        return Icons.dangerous;
      case 'high':
        return Icons.warning_amber_rounded;
      case 'medium':
        return Icons.info_outline;
      case 'low':
        return Icons.check_circle_outline;
      default:
        return Icons.help_outline;
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = _severityColor(context);
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(_severityIcon(), size: 18, color: color),
              const SizedBox(width: 6),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  alert.severityLabel,
                  style: theme.textTheme.labelSmall?.copyWith(
                    color: color,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ],
          ),
          if (alert.medications.isNotEmpty) ...[
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final med in alert.medications)
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: theme.colorScheme.surfaceContainerHighest,
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      med,
                      style: theme.textTheme.labelSmall
                          ?.copyWith(fontWeight: FontWeight.w600),
                    ),
                  ),
              ],
            ),
          ],
          const SizedBox(height: 8),
          Text(
            alert.message,
            style: const TextStyle(fontWeight: FontWeight.w600),
          ),
          if (alert.details != null)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                alert.details!,
                style: theme.textTheme.bodySmall,
              ),
            ),
        ],
      ),
    );
  }
}
