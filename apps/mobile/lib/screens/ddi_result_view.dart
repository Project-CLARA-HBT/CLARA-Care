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
                    (alert) => Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(alert.message,
                              style: const TextStyle(
                                  fontWeight: FontWeight.w600)),
                          if (alert.details != null)
                            Padding(
                              padding: const EdgeInsets.only(top: 2),
                              child: Text(
                                alert.details!,
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                            ),
                        ],
                      ),
                    ),
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
