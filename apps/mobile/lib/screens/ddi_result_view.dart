import 'package:flutter/material.dart';

import '../core/ddi_user_view.dart';

/// Locale-aware presentation copy for the fixed CareGuard result chrome.
/// Clinical alert content remains authoritative API-provided text and is never
/// rewritten here. This component does not decide risk or alter DrugBank data.
class _DdiResultCopy {
  const _DdiResultCopy._(this._english);

  factory _DdiResultCopy.forContext(BuildContext context) {
    final language = Localizations.localeOf(context).languageCode.toLowerCase();
    return _DdiResultCopy._(language == 'en');
  }

  final bool _english;

  String get offlineLabel => _english
      ? 'offline / not real-time'
      : 'ngoại tuyến / không phải thời gian thực';
  String cachedResult(String timestamp) => _english
      ? 'Showing the most recently saved result ($timestamp). It may be out of date.'
      : 'Đang hiển thị kết quả lưu gần nhất ($timestamp). Kết quả có thể đã cũ.';
  String get overview => _english ? 'Overview' : 'Kết quả tổng quan';
  String risk(String value) =>
      _english ? 'Risk level: $value' : 'Mức rủi ro: $value';
  String get noClearAlert => _english
      ? 'No clear interaction alert was identified.'
      : 'Chưa ghi nhận cảnh báo tương tác rõ ràng.';
  String get recommendations => _english ? 'Recommendations' : 'Khuyến nghị';
  String get sources => _english ? 'Reference sources' : 'Nguồn tham khảo';

  String riskLabel(String risk) {
    switch (risk) {
      case 'critical':
      case 'high':
        return _english ? 'High' : 'Cao';
      case 'medium':
        return _english ? 'Medium' : 'Trung bình';
      case 'low':
        return _english ? 'Low' : 'Thấp';
      default:
        return _english ? 'Unknown' : 'Chưa xác định';
    }
  }

  String severityLabel(String severity) {
    switch (severity) {
      case 'critical':
        return _english ? 'Critical' : 'Nghiêm trọng';
      case 'high':
        return _english ? 'High' : 'Cao';
      case 'medium':
        return _english ? 'Medium' : 'Trung bình';
      case 'low':
        return _english ? 'Low' : 'Thấp';
      default:
        return _english ? 'Unknown' : 'Chưa xác định';
    }
  }
}

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
    final copy = _DdiResultCopy.forContext(context);
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
                        copy.offlineLabel,
                        style: TextStyle(
                          fontWeight: FontWeight.w700,
                          color: Colors.amber.shade900,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    copy.cachedResult(_formatCachedAt(offlineCachedAt!)),
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
                    Text(copy.overview,
                        style: Theme.of(context).textTheme.titleSmall),
                    const Spacer(),
                    Chip(
                      label: Text(copy.risk(copy.riskLabel(view.riskLevel))),
                      backgroundColor:
                          _riskColor(context).withValues(alpha: 0.15),
                      side: BorderSide(color: _riskColor(context)),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                if (view.alerts.isEmpty)
                  Text(copy.noClearAlert)
                else
                  ...view.alerts.map(
                    (alert) => _AlertTile(alert: alert, copy: copy),
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
                  Text(copy.recommendations,
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
                  Text(copy.sources,
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

/// Terminal, fail-closed CareGuard state shown before a DDI result exists.
///
/// This deliberately does not reuse [DdiResultView]: there is no risk level,
/// all-clear, recommendation, source cache, or conclusion while one or more
/// cabinet labels have no verified DrugBank identity. When candidates are
/// present, the choices are exactly those supplied by the API and can only be
/// returned to the owner-scoped cabinet recheck endpoint by [onResubmit].
class DdiMedicationClarificationView extends StatelessWidget {
  const DdiMedicationClarificationView({
    super.key,
    required this.clarifications,
    required this.selected,
    required this.onSelected,
    required this.onResubmit,
    this.loading = false,
  });

  final List<CareguardMedicationClarification> clarifications;
  final Map<int, CareguardClarificationCandidate> selected;
  final void Function(
    CareguardMedicationClarification clarification,
    CareguardClarificationCandidate candidate,
  ) onSelected;
  final VoidCallback? onResubmit;
  final bool loading;

  bool get _isComplete =>
      clarifications.isNotEmpty &&
      clarifications.every(
        (clarification) =>
            clarification.candidates.isNotEmpty &&
            selected.containsKey(clarification.cabinetItemId),
      );

  @override
  Widget build(BuildContext context) {
    final english =
        Localizations.localeOf(context).languageCode.toLowerCase() == 'en';
    final title = english
        ? 'The interaction check is not complete yet'
        : 'Chưa thể hoàn tất kiểm tra tương tác';
    final explanation = english
        ? 'We need you to choose the exact medicine for the item below before DrugBank can compare your medicines. This is not a result or an all-clear.'
        : 'Bạn cần chọn đúng thuốc cho mục bên dưới trước khi DrugBank có thể so sánh các thuốc. Đây chưa phải là kết quả và không có nghĩa là an toàn.';
    final noCandidate = english
        ? 'There is no safe source-backed choice for this medicine. Check the package or edit the medicine in your cabinet, then try again.'
        : 'Chưa có lựa chọn an toàn có nguồn cho thuốc này. Hãy kiểm tra vỏ thuốc hoặc sửa thuốc trong tủ, rồi thử lại.';
    final source = english ? 'DrugBank source' : 'Nguồn DrugBank';
    final resubmit = english
        ? 'Check again with selected medicines'
        : 'Kiểm tra lại với thuốc đã chọn';

    return Card(
      color: Colors.amber.shade50,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.info_outline, color: Colors.amber.shade900),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    title,
                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          color: Colors.amber.shade900,
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(explanation),
            const SizedBox(height: 12),
            if (clarifications.isEmpty)
              Text(noCandidate)
            else
              ...clarifications.map((clarification) => Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: _ClarificationChoices(
                      clarification: clarification,
                      selected: selected[clarification.cabinetItemId],
                      onSelected: onSelected,
                      noCandidate: noCandidate,
                      sourceLabel: source,
                    ),
                  )),
            if (clarifications.isNotEmpty) ...[
              const SizedBox(height: 4),
              FilledButton.icon(
                onPressed: loading || !_isComplete ? null : onResubmit,
                icon: loading
                    ? const SizedBox(
                        height: 18,
                        width: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.refresh),
                label: Text(resubmit),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _ClarificationChoices extends StatelessWidget {
  const _ClarificationChoices({
    required this.clarification,
    required this.selected,
    required this.onSelected,
    required this.noCandidate,
    required this.sourceLabel,
  });

  final CareguardMedicationClarification clarification;
  final CareguardClarificationCandidate? selected;
  final void Function(
    CareguardMedicationClarification clarification,
    CareguardClarificationCandidate candidate,
  ) onSelected;
  final String noCandidate;
  final String sourceLabel;

  @override
  Widget build(BuildContext context) {
    if (clarification.candidates.isEmpty) {
      return Text('${clarification.inputAlias}: $noCandidate');
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          clarification.inputAlias,
          style: Theme.of(context).textTheme.titleSmall,
        ),
        const SizedBox(height: 4),
        ...clarification.candidates.map(
          (candidate) => RadioListTile<String>(
            contentPadding: EdgeInsets.zero,
            value: candidate.drugbankId,
            groupValue: selected?.drugbankId,
            onChanged: (_) => onSelected(clarification, candidate),
            title: Text(candidate.normalizedName),
            subtitle: Text(
              [
                if (candidate.activeIngredients.isNotEmpty)
                  candidate.activeIngredients.join(', '),
                '$sourceLabel: ${candidate.sourceVersion}',
              ].join('\n'),
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
  const _AlertTile({required this.alert, required this.copy});

  final DdiAlert alert;
  final _DdiResultCopy copy;

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
                  copy.severityLabel(alert.severity),
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
