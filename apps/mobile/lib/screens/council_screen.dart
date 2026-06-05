import 'package:flutter/material.dart';

import '../core/analytics.dart';
import '../core/api_client.dart';
import '../core/session_store.dart';

class CouncilScreen extends StatefulWidget {
  const CouncilScreen({
    super.key,
    required this.apiClient,
    required this.sessionStore,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  @override
  State<CouncilScreen> createState() => _CouncilScreenState();
}

class _CouncilScreenState extends State<CouncilScreen> {
  final _symptomsController = TextEditingController();
  final _medicationsController = TextEditingController();
  final _historyController = TextEditingController();

  int _specialistCount = 3;
  bool _isLoading = false;
  String? _error;
  _CouncilView? _view;

  @override
  void initState() {
    super.initState();
    getAnalyticsClient()
        .captureScreenView(MobileAnalyticsEvents.councilViewed);
  }

  @override
  void dispose() {
    _symptomsController.dispose();
    _medicationsController.dispose();
    _historyController.dispose();
    super.dispose();
  }

  List<String> _parseList(String value) {
    return value
        .split(RegExp(r'[\n,]'))
        .map((item) => item.trim())
        .where((item) => item.isNotEmpty)
        .toList();
  }

  Future<void> _submit() async {
    final symptoms = _parseList(_symptomsController.text);
    final history = _historyController.text.trim();
    final token = widget.sessionStore.accessToken;

    if (symptoms.isEmpty && history.isEmpty) {
      setState(() {
        _error = 'Vui lòng nhập triệu chứng hoặc bệnh sử để hội chẩn.';
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

    // Named product event for a council run. Only the non-PII specialist count
    // is attached; symptoms/history free text is never transmitted.
    getAnalyticsClient().capture(
      AnalyticsEvent(
        MobileAnalyticsEvents.councilRun,
        {'specialist_count': _specialistCount},
      ),
    );

    try {
      final response = await widget.apiClient.runCouncil(
        accessToken: token,
        payload: {
          'symptoms': symptoms,
          'medications': _parseList(_medicationsController.text),
          'history': history,
          'specialist_count': _specialistCount,
          'labs': <String, dynamic>{},
          'specialists': <String>[],
        },
      );

      if (!mounted) {
        return;
      }

      setState(() {
        _view = _CouncilView.fromPayload(response);
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
        _error = 'Không thể chạy hội chẩn lúc này. Vui lòng thử lại.';
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
      appBar: AppBar(title: const Text('Hội chẩn AI')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            controller: _symptomsController,
            minLines: 2,
            maxLines: 5,
            enabled: !_isLoading,
            decoration: const InputDecoration(
              labelText: 'Triệu chứng',
              border: OutlineInputBorder(),
              hintText: 'Mỗi dòng một triệu chứng',
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _medicationsController,
            minLines: 1,
            maxLines: 4,
            enabled: !_isLoading,
            decoration: const InputDecoration(
              labelText: 'Thuốc đang dùng (không bắt buộc)',
              border: OutlineInputBorder(),
              hintText: 'Mỗi dòng một thuốc',
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _historyController,
            minLines: 2,
            maxLines: 5,
            enabled: !_isLoading,
            decoration: const InputDecoration(
              labelText: 'Bệnh sử / tóm tắt ca',
              border: OutlineInputBorder(),
              hintText: 'Mô tả ngắn gọn bệnh sử và bối cảnh ca bệnh',
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              const Text('Số chuyên khoa'),
              const Spacer(),
              DropdownButton<int>(
                value: _specialistCount,
                onChanged: _isLoading
                    ? null
                    : (value) {
                        if (value != null) {
                          setState(() {
                            _specialistCount = value;
                          });
                        }
                      },
                items: const [2, 3, 4, 5]
                    .map((n) => DropdownMenuItem(value: n, child: Text('$n')))
                    .toList(),
              ),
            ],
          ),
          const SizedBox(height: 8),
          FilledButton(
            onPressed: _isLoading ? null : _submit,
            child: _isLoading
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Chạy hội chẩn'),
          ),
          const SizedBox(height: 12),
          if (_error != null)
            Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          if (view != null) _CouncilResultView(view: view),
        ],
      ),
    );
  }
}

class _CouncilResultView extends StatelessWidget {
  const _CouncilResultView({required this.view});

  final _CouncilView view;

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
                    Icon(
                      view.hasDivergence ? Icons.warning_amber : Icons.check_circle,
                      color: view.hasDivergence
                          ? Colors.orange.shade800
                          : Colors.green.shade700,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        view.hasDivergence
                            ? 'Có điểm khác biệt giữa các chuyên khoa'
                            : 'Các chuyên khoa đồng thuận',
                        style: Theme.of(context).textTheme.titleSmall,
                      ),
                    ),
                  ],
                ),
                if (view.consensusSummary.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  const Text('Tóm tắt đồng thuận',
                      style: TextStyle(fontWeight: FontWeight.w600)),
                  const SizedBox(height: 2),
                  Text(view.consensusSummary),
                ],
              ],
            ),
          ),
        ),
        if (view.finalRecommendation.isNotEmpty)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Khuyến nghị cuối cùng',
                      style: Theme.of(context).textTheme.titleSmall),
                  const SizedBox(height: 6),
                  Text(view.finalRecommendation),
                ],
              ),
            ),
          ),
        if (view.divergenceNotes.isNotEmpty)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Điểm cần lưu ý',
                      style: Theme.of(context).textTheme.titleSmall),
                  const SizedBox(height: 6),
                  ...view.divergenceNotes.map(
                    (note) => Padding(
                      padding: const EdgeInsets.only(bottom: 4),
                      child: Text('• $note'),
                    ),
                  ),
                ],
              ),
            ),
          ),
        if (view.specialists.isNotEmpty)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Chuyên khoa tham gia',
                      style: Theme.of(context).textTheme.titleSmall),
                  const SizedBox(height: 6),
                  Text(view.specialists.join(', ')),
                ],
              ),
            ),
          ),
      ],
    );
  }
}

/// End_User council projection mirroring the web consensus/divergence layout.
class _CouncilView {
  _CouncilView({
    required this.consensusSummary,
    required this.finalRecommendation,
    required this.divergenceNotes,
    required this.specialists,
    required this.hasDivergence,
  });

  final String consensusSummary;
  final String finalRecommendation;
  final List<String> divergenceNotes;
  final List<String> specialists;
  final bool hasDivergence;

  static List<String> _stringList(dynamic value) {
    if (value is List) {
      return value
          .map((item) {
            if (item is String) return item.trim();
            if (item is Map) {
              return (item['note'] ?? item['summary'] ?? item['description'] ?? '')
                  .toString()
                  .trim();
            }
            return item?.toString().trim() ?? '';
          })
          .where((item) => item.isNotEmpty)
          .toList();
    }
    return const [];
  }

  factory _CouncilView.fromPayload(Map<String, dynamic> payload) {
    final divergence = _stringList(payload['divergence_notes']);
    final conflicts = _stringList(payload['conflict_list']);
    final notes = <String>[...divergence, ...conflicts];

    return _CouncilView(
      consensusSummary: (payload['consensus_summary'] ?? '').toString().trim(),
      finalRecommendation:
          (payload['final_recommendation'] ?? '').toString().trim(),
      divergenceNotes: notes,
      specialists: _stringList(payload['requested_specialists']),
      hasDivergence: notes.isNotEmpty,
    );
  }
}
