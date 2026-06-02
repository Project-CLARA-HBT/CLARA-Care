import 'package:flutter/material.dart';

import '../core/analytics.dart';
import '../core/api_client.dart';
import '../core/session_store.dart';

/// Minimum number of distinct medicines required before a DDI check may run,
/// mirroring the web two-medicine guard (Requirement 3.5).
const int _minimumDdiMedicines = 2;

class CareguardScreen extends StatefulWidget {
  const CareguardScreen({
    super.key,
    required this.apiClient,
    required this.sessionStore,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  @override
  State<CareguardScreen> createState() => _CareguardScreenState();
}

class _CareguardScreenState extends State<CareguardScreen> {
  final _medicinesController = TextEditingController();
  final _allergiesController = TextEditingController();

  bool _isLoading = false;
  String? _error;
  _DdiUserView? _view;

  @override
  void initState() {
    super.initState();
    getAnalyticsClient()
        .captureScreenView(MobileAnalyticsEvents.careguardViewed);
  }

  @override
  void dispose() {
    _medicinesController.dispose();
    _allergiesController.dispose();
    super.dispose();
  }

  /// Split a free-text field into a trimmed, non-empty list (newline/comma).
  List<String> _parseList(String value) {
    return value
        .split(RegExp(r'[\n,]'))
        .map((item) => item.trim())
        .where((item) => item.isNotEmpty)
        .toList();
  }

  /// Count distinct, case-insensitive medicine names.
  int _countDistinct(List<String> medicines) {
    return medicines.map((m) => m.toLowerCase()).toSet().length;
  }

  Future<void> _submit() async {
    final medicines = _parseList(_medicinesController.text);
    final token = widget.sessionStore.accessToken;

    // Two-medicine guard: do NOT call the analysis endpoint with fewer than
    // two distinct medicines; prompt the user instead (Requirement 3.5).
    if (_countDistinct(medicines) < _minimumDdiMedicines) {
      setState(() {
        _view = null;
        _error = 'Cần ít nhất 2 thuốc để kiểm tra tương tác.';
      });
      return;
    }

    if (token == null || token.isEmpty) {
      setState(() {
        _error = 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.';
      });
      return;
    }

    setState(() {
      _isLoading = true;
      _error = null;
      _view = null;
    });

    // Named product event for a DDI analysis. Only a non-PII count is attached;
    // the medicine list itself is never transmitted (stripped by the client).
    getAnalyticsClient().capture(
      AnalyticsEvent(
        MobileAnalyticsEvents.careguardAnalyzed,
        {'medicine_count': _countDistinct(medicines)},
      ),
    );

    try {
      final response = await widget.apiClient.analyzeCareguard(
        accessToken: token,
        payload: {
          'medications': medicines,
          'allergies': _parseList(_allergiesController.text),
          'symptoms': <String>[],
          'labs': <String, dynamic>{},
        },
      );

      if (!mounted) {
        return;
      }

      setState(() {
        _view = _DdiUserView.fromPayload(response);
      });
    } on ApiException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = error.message;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = 'Không thể kiểm tra tương tác thuốc lúc này. Vui lòng thử lại.';
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final view = _view;

    return Scaffold(
      appBar: AppBar(title: const Text('Kiểm tra tương tác thuốc')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            controller: _medicinesController,
            minLines: 3,
            maxLines: 6,
            enabled: !_isLoading,
            decoration: const InputDecoration(
              labelText: 'Danh sách thuốc',
              border: OutlineInputBorder(),
              hintText: 'Mỗi dòng một thuốc (ví dụ: Warfarin\nIbuprofen)',
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _allergiesController,
            minLines: 1,
            maxLines: 3,
            enabled: !_isLoading,
            decoration: const InputDecoration(
              labelText: 'Dị ứng (không bắt buộc)',
              border: OutlineInputBorder(),
              hintText: 'Mỗi dòng một dị ứng hoặc phân tách bằng dấu phẩy',
            ),
          ),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: _isLoading ? null : _submit,
            child: _isLoading
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Kiểm tra tương tác thuốc'),
          ),
          const SizedBox(height: 12),
          if (_error != null)
            Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          if (view != null) _DdiResultView(view: view),
        ],
      ),
    );
  }
}

/// End_User DDI projection: only risk level, alerts, recommendations, and
/// reference sources. Runtime mode, fallback flags, and connector source_errors
/// are intentionally excluded (Requirements 3.1, 3.6).
class _DdiResultView extends StatelessWidget {
  const _DdiResultView({required this.view});

  final _DdiUserView view;

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

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: 8),
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
                      backgroundColor: _riskColor(context).withValues(alpha: 0.15),
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
                              style: const TextStyle(fontWeight: FontWeight.w600)),
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

class _DdiAlert {
  const _DdiAlert({required this.message, this.details});

  final String message;
  final String? details;
}

/// Parses the raw CareGuard payload into an End_User-safe view, dropping
/// telemetry (mode/fallback/source_errors) per Requirements 3.1/3.6.
class _DdiUserView {
  _DdiUserView({
    required this.riskLevel,
    required this.alerts,
    required this.recommendations,
    required this.sources,
  });

  final String riskLevel;
  final List<_DdiAlert> alerts;
  final List<String> recommendations;
  final List<String> sources;

  String get riskLabel {
    switch (riskLevel) {
      case 'high':
      case 'critical':
        return 'Cao';
      case 'medium':
        return 'Trung bình';
      case 'low':
        return 'Thấp';
      default:
        return 'Chưa xác định';
    }
  }

  static String _classifyRisk(String? raw) {
    final value = (raw ?? '').toLowerCase();
    if (RegExp(r'critical|contra|fatal').hasMatch(value)) return 'critical';
    if (RegExp(r'severe|major|high|danger').hasMatch(value)) return 'high';
    if (RegExp(r'moderate|medium|amber').hasMatch(value)) return 'medium';
    if (RegExp(r'minor|low|safe|none').hasMatch(value)) return 'low';
    return 'unknown';
  }

  static List<String> _stringList(dynamic value) {
    if (value is List) {
      return value
          .map((item) => item?.toString().trim() ?? '')
          .where((item) => item.isNotEmpty)
          .toList();
    }
    if (value is String && value.trim().isNotEmpty) {
      return [value.trim()];
    }
    return const [];
  }

  factory _DdiUserView.fromPayload(Map<String, dynamic> payload) {
    final risk = payload['risk'];
    final riskTier = payload['risk_tier'] ??
        payload['riskTier'] ??
        payload['tier'] ??
        (risk is Map ? risk['level'] : risk);

    final rawAlerts = payload['ddi_alerts'] ?? payload['ddiAlerts'];
    final alerts = <_DdiAlert>[];
    if (rawAlerts is List) {
      for (final item in rawAlerts) {
        if (item is String && item.trim().isNotEmpty) {
          alerts.add(_DdiAlert(message: item.trim()));
        } else if (item is Map) {
          final map = item.cast<String, dynamic>();
          final message = (map['title'] ??
                  map['interaction'] ??
                  map['message'] ??
                  map['summary'])
              ?.toString()
              .trim();
          if (message != null && message.isNotEmpty) {
            final details =
                (map['details'] ?? map['description'] ?? map['recommendation'])
                    ?.toString()
                    .trim();
            alerts.add(_DdiAlert(
              message: message,
              details: (details != null && details.isNotEmpty) ? details : null,
            ));
          }
        }
      }
    }

    final recommendations = <String>[
      ..._stringList(payload['recommendations']),
      ..._stringList(payload['recommendation']),
    ];

    // Sources come from the attribution block (label only); connector errors
    // are never surfaced.
    final sources = <String>[];
    final attribution = payload['attribution'];
    if (attribution is Map) {
      final list = attribution['sources'];
      if (list is List) {
        for (final item in list) {
          if (item is Map) {
            final name = item['name']?.toString().trim();
            if (name != null && name.isNotEmpty && !sources.contains(name)) {
              sources.add(name);
            }
          }
        }
      }
    }

    return _DdiUserView(
      riskLevel: _classifyRisk(riskTier?.toString()),
      alerts: alerts,
      recommendations: recommendations.toSet().toList(),
      sources: sources,
    );
  }
}
