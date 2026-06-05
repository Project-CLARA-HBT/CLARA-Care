import 'package:flutter/material.dart';

import '../core/analytics.dart';
import '../core/api_client.dart';
import '../core/session_store.dart';

/// Research execution modes, mirroring the web research surface. The internal
/// values match the API `research_mode` enum; the labels use the Vietnamese
/// task-oriented vocabulary from the web client (`Nhanh`/`Tư duy`/`Pro`).
enum ResearchMode { fast, deep, deepBeta }

extension on ResearchMode {
  String get apiValue {
    switch (this) {
      case ResearchMode.fast:
        return 'fast';
      case ResearchMode.deep:
        return 'deep';
      case ResearchMode.deepBeta:
        return 'deep_beta';
    }
  }

  String get label {
    switch (this) {
      case ResearchMode.fast:
        return 'Nhanh';
      case ResearchMode.deep:
        return 'Tư duy';
      case ResearchMode.deepBeta:
        return 'Pro';
    }
  }
}

class ResearchScreen extends StatefulWidget {
  const ResearchScreen({
    super.key,
    required this.apiClient,
    required this.sessionStore,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  @override
  State<ResearchScreen> createState() => _ResearchScreenState();
}

class _ResearchScreenState extends State<ResearchScreen> {
  final _queryController = TextEditingController();

  ResearchMode _mode = ResearchMode.fast;
  bool _isLoading = false;
  String? _error;
  Map<String, dynamic>? _result;

  @override
  void initState() {
    super.initState();
    getAnalyticsClient()
        .captureScreenView(MobileAnalyticsEvents.researchViewed);
  }

  @override
  void dispose() {
    _queryController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final query = _queryController.text.trim();
    final token = widget.sessionStore.accessToken;

    if (query.isEmpty) {
      setState(() {
        _error = 'Vui lòng nhập câu hỏi nghiên cứu.';
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
      _result = null;
    });

    // Named product event for a research submission. Only the non-PII mode is
    // attached; the free-text query is never sent (stripped by the client).
    getAnalyticsClient().capture(
      AnalyticsEvent(
        MobileAnalyticsEvents.researchSubmitted,
        {'mode': _mode.apiValue},
      ),
    );

    try {
      final response = await widget.apiClient.researchTier2(
        accessToken: token,
        payload: {
          'query': query,
          'research_mode': _mode.apiValue,
          'ui_language': 'vi',
        },
      );

      if (!mounted) {
        return;
      }

      setState(() {
        _result = response;
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
        _error = 'Hệ thống đang bận, vui lòng thử lại.';
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  String _answerText(Map<String, dynamic> result) {
    for (final key in ['answer', 'answer_markdown', 'answer_md', 'summary', 'message']) {
      final value = result[key];
      if (value is String && value.trim().isNotEmpty) {
        return value.trim();
      }
    }
    return '';
  }

  List<_Citation> _citations(Map<String, dynamic> result) {
    final raw = result['citations'] ?? result['sources'];
    if (raw is! List) {
      return const [];
    }
    final output = <_Citation>[];
    for (final item in raw) {
      if (item is String && item.trim().isNotEmpty) {
        output.add(_Citation(title: item.trim()));
      } else if (item is Map) {
        final map = item.cast<String, dynamic>();
        final title = (map['title'] ?? map['name'] ?? map['source'] ?? map['url'])
            ?.toString()
            .trim();
        if (title != null && title.isNotEmpty) {
          output.add(_Citation(
            title: title,
            url: map['url']?.toString(),
          ));
        }
      }
    }
    return output;
  }

  @override
  Widget build(BuildContext context) {
    final result = _result;
    final answer = result != null ? _answerText(result) : '';
    final citations = result != null ? _citations(result) : const <_Citation>[];

    return Scaffold(
      appBar: AppBar(title: const Text('Nghiên cứu y khoa')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            controller: _queryController,
            minLines: 3,
            maxLines: 6,
            enabled: !_isLoading,
            decoration: const InputDecoration(
              labelText: 'Câu hỏi',
              border: OutlineInputBorder(),
              hintText: 'Nhập câu hỏi nghiên cứu y khoa...',
            ),
          ),
          const SizedBox(height: 12),
          Text(
            'Chế độ',
            style: Theme.of(context).textTheme.labelLarge,
          ),
          const SizedBox(height: 6),
          SegmentedButton<ResearchMode>(
            segments: const [
              ButtonSegment(value: ResearchMode.fast, label: Text('Nhanh')),
              ButtonSegment(value: ResearchMode.deep, label: Text('Tư duy')),
              ButtonSegment(value: ResearchMode.deepBeta, label: Text('Pro')),
            ],
            selected: {_mode},
            onSelectionChanged: _isLoading
                ? null
                : (selection) {
                    setState(() {
                      _mode = selection.first;
                    });
                  },
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
                : const Text('Tìm hiểu'),
          ),
          const SizedBox(height: 12),
          if (_error != null)
            Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          if (result != null) ...[
            if (answer.isNotEmpty)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Kết quả', style: Theme.of(context).textTheme.titleSmall),
                      const SizedBox(height: 8),
                      SelectableText(answer),
                    ],
                  ),
                ),
              )
            else
              const Card(
                child: Padding(
                  padding: EdgeInsets.all(12),
                  child: Text('Chưa có nội dung trả lời cho câu hỏi này.'),
                ),
              ),
            if (citations.isNotEmpty) ...[
              const SizedBox(height: 12),
              Text('Nguồn tham khảo',
                  style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 6),
              ...citations.map(
                (citation) => ListTile(
                  dense: true,
                  leading: const Icon(Icons.link),
                  title: Text(citation.title),
                  subtitle: citation.url != null ? Text(citation.url!) : null,
                ),
              ),
            ],
          ],
        ],
      ),
    );
  }
}

class _Citation {
  const _Citation({required this.title, this.url});

  final String title;
  final String? url;
}
