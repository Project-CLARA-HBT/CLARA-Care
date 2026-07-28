import 'dart:async';

import 'package:flutter/material.dart';

import '../core/analytics.dart';
import '../core/api_client.dart';
import '../core/research_telemetry_gate.dart';
import '../core/session_store.dart';
import '../widgets/research_telemetry_panel.dart';

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

  /// Fast mode answers synchronously via `POST /research/tier2`. Deep and
  /// deep_beta enqueue a tier2 job and stream progress over SSE.
  bool get usesJobStream => this != ResearchMode.fast;
}

/// Snapshot of a research job's progress, normalized from the API job payload
/// (`progress.flow_stages`, `active_stage`, `active_status`, `status_note`).
class ResearchProgress {
  const ResearchProgress({
    required this.stages,
    required this.activeStage,
    required this.activeStatus,
    required this.statusNote,
    required this.jobStatus,
  });

  final List<ResearchProgressStage> stages;
  final String activeStage;
  final String activeStatus;
  final String statusNote;
  final String jobStatus;

  bool get isEmpty =>
      stages.isEmpty && statusNote.isEmpty && activeStage.isEmpty;

  /// Builds a progress snapshot from a job response/SSE payload. Reads the
  /// nested `progress` object emitted by the API SSE contract; tolerates a
  /// flattened shape as a fallback.
  factory ResearchProgress.fromSnapshot(Map<String, dynamic> snapshot) {
    final jobStatus = (snapshot['status'] ?? '').toString().trim();
    final progressRaw = snapshot['progress'];
    final progress =
        progressRaw is Map ? progressRaw.cast<String, dynamic>() : snapshot;

    final stagesRaw = progress['flow_stages'];
    final stages = <ResearchProgressStage>[];
    if (stagesRaw is List) {
      for (final item in stagesRaw) {
        if (item is Map) {
          final stage = ResearchProgressStage.fromMap(
            item.cast<String, dynamic>(),
          );
          if (stage != null) {
            stages.add(stage);
          }
        }
      }
    }

    return ResearchProgress(
      stages: stages,
      activeStage: (progress['active_stage'] ?? '').toString().trim(),
      activeStatus: (progress['active_status'] ?? '').toString().trim(),
      statusNote: (progress['status_note'] ?? '').toString().trim(),
      jobStatus: jobStatus,
    );
  }
}

/// A single pipeline stage surfaced in the mobile progress view.
class ResearchProgressStage {
  const ResearchProgressStage({
    required this.id,
    required this.label,
    required this.status,
    required this.detail,
  });

  final String id;
  final String label;
  final String status;
  final String detail;

  bool get isComplete {
    final normalized = status.toLowerCase();
    return normalized == 'completed' ||
        normalized == 'complete' ||
        normalized == 'done';
  }

  bool get isActive {
    final normalized = status.toLowerCase();
    return normalized == 'in_progress' ||
        normalized == 'running' ||
        normalized == 'active';
  }

  bool get isError {
    final normalized = status.toLowerCase();
    return normalized == 'failed' || normalized == 'error';
  }

  static ResearchProgressStage? fromMap(Map<String, dynamic> map) {
    final id = (map['id'] ?? map['stage'] ?? '').toString().trim();
    final labelRaw = (map['label'] ?? '').toString().trim();
    final label = labelRaw.isNotEmpty
        ? labelRaw
        : (id.isNotEmpty ? id.replaceAll('_', ' ') : '');
    if (label.isEmpty) {
      return null;
    }
    return ResearchProgressStage(
      id: id,
      label: label,
      status: (map['status'] ?? 'pending').toString().trim(),
      detail: (map['detail'] ?? map['note'] ?? '').toString().trim(),
    );
  }
}

class ResearchScreen extends StatefulWidget {
  const ResearchScreen({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    this.deepResearchEnabled = false,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  /// Remote-config gate (`RESEARCH_MOBILE_DEEP_ENABLED`). When false the
  /// deep/deep_beta modes are disabled and only fast research is offered,
  /// preserving the legacy default-off behavior.
  final bool deepResearchEnabled;

  @override
  State<ResearchScreen> createState() => _ResearchScreenState();
}

class _ResearchScreenState extends State<ResearchScreen> {
  final _queryController = TextEditingController();

  ResearchMode _mode = ResearchMode.fast;
  bool _isLoading = false;
  String? _error;
  Map<String, dynamic>? _result;
  ResearchProgress? _progress;
  StreamSubscription<SseEvent>? _streamSub;

  /// Role-gated telemetry decision for the current run (R3, mirrored per
  /// R19.4). Detailed telemetry is shown only to admins; if the role cannot be
  /// evaluated the job is blocked and this stays null.
  TelemetryGateDecision? _telemetryGate;

  @override
  void initState() {
    super.initState();
    getAnalyticsClient()
        .captureScreenView(MobileAnalyticsEvents.researchViewed);
  }

  @override
  void dispose() {
    _streamSub?.cancel();
    _queryController.dispose();
    super.dispose();
  }

  bool _modeEnabled(ResearchMode mode) {
    if (mode.usesJobStream) {
      return widget.deepResearchEnabled;
    }
    return true;
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

    if (!_modeEnabled(_mode)) {
      setState(() {
        _error = 'Chế độ nghiên cứu chuyên sâu hiện chưa được bật.';
      });
      return;
    }

    // Role-gated telemetry (Requirement 19.4): mirror the R3 gate and fail
    // closed. If the user's role cannot be evaluated, block the research job
    // rather than leaking ungated telemetry.
    final gate = evaluateTelemetryGate(widget.sessionStore.role);
    if (gate.blockJob) {
      setState(() {
        _telemetryGate = null;
        _error =
            'Không thể xác thực quyền truy cập. Phiên nghiên cứu đã bị chặn.';
      });
      return;
    }

    // Cancel any in-flight stream before starting a new run.
    await _streamSub?.cancel();
    _streamSub = null;

    setState(() {
      _isLoading = true;
      _error = null;
      _result = null;
      _progress = null;
      _telemetryGate = gate;
    });

    // Named product event for a research submission. Only the non-PII mode is
    // attached; the free-text query is never sent (stripped by the client).
    getAnalyticsClient().capture(
      AnalyticsEvent(
        MobileAnalyticsEvents.researchSubmitted,
        {'mode': _mode.apiValue},
      ),
    );

    final payload = <String, dynamic>{
      'query': query,
      'research_mode': _mode.apiValue,
      'ui_language': 'vi',
    };

    if (_mode.usesJobStream) {
      await _submitJob(token: token, payload: payload);
    } else {
      await _submitFast(token: token, payload: payload);
    }
  }

  Future<void> _submitFast({
    required String token,
    required Map<String, dynamic> payload,
  }) async {
    try {
      final response = await widget.apiClient.researchTier2(
        accessToken: token,
        payload: payload,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _result = response;
      });
    } on ApiException catch (error) {
      _setError(error.message);
    } catch (_) {
      _setError('Hệ thống đang bận, vui lòng thử lại.');
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _submitJob({
    required String token,
    required Map<String, dynamic> payload,
  }) async {
    final Map<String, dynamic> job;
    try {
      job = await widget.apiClient.createResearchJob(
        accessToken: token,
        payload: payload,
      );
    } on ApiException catch (error) {
      _setError(error.message);
      _stopLoading();
      return;
    } catch (_) {
      _setError('Hệ thống đang bận, vui lòng thử lại.');
      _stopLoading();
      return;
    }

    final jobId = (job['job_id'] ?? '').toString();
    if (jobId.isEmpty) {
      _setError('Không thể khởi tạo phiên nghiên cứu.');
      _stopLoading();
      return;
    }

    if (!mounted) {
      return;
    }
    setState(() {
      _progress = ResearchProgress.fromSnapshot(job);
    });

    _streamSub = widget.apiClient
        .streamResearchJob(accessToken: token, jobId: jobId)
        .listen(
      _onStreamEvent,
      onError: (Object error) {
        final message = error is ApiException
            ? error.message
            : 'Mất kết nối tới phiên nghiên cứu.';
        _setError(message);
        _stopLoading();
      },
      onDone: _stopLoading,
      cancelOnError: true,
    );
  }

  void _onStreamEvent(SseEvent event) {
    if (!mounted) {
      return;
    }
    final data = event.json;
    if (data == null) {
      return;
    }

    if (event.event == 'error') {
      final message =
          (data['message'] ?? 'Phiên nghiên cứu gặp lỗi.').toString();
      _setError(message);
      _stopLoading();
      return;
    }

    final snapshot = ResearchProgress.fromSnapshot(data);
    setState(() {
      _progress = snapshot;
    });

    final status = snapshot.jobStatus.toLowerCase();
    if (status == 'completed') {
      final resultRaw = data['result'];
      setState(() {
        _result = resultRaw is Map
            ? resultRaw.cast<String, dynamic>()
            : <String, dynamic>{};
      });
      _stopLoading();
    } else if (status == 'failed') {
      final message =
          (data['error'] ?? 'Phiên nghiên cứu thất bại.').toString();
      _setError(message.isNotEmpty ? message : 'Phiên nghiên cứu thất bại.');
      _stopLoading();
    }
  }

  void _setError(String message) {
    if (!mounted) {
      return;
    }
    setState(() {
      _error = message;
    });
  }

  void _stopLoading() {
    if (!mounted) {
      return;
    }
    setState(() {
      _isLoading = false;
    });
  }

  String _answerText(Map<String, dynamic> result) {
    for (final key in [
      'answer_markdown',
      'answer_md',
      'answer',
      'summary',
      'message'
    ]) {
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
        final title =
            (map['title'] ?? map['name'] ?? map['source'] ?? map['url'])
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
    final progress = _progress;
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
            segments: [
              const ButtonSegment(
                value: ResearchMode.fast,
                label: Text('Nhanh'),
              ),
              ButtonSegment(
                value: ResearchMode.deep,
                label: const Text('Tư duy'),
                enabled: widget.deepResearchEnabled,
              ),
              ButtonSegment(
                value: ResearchMode.deepBeta,
                label: const Text('Pro'),
                enabled: widget.deepResearchEnabled,
              ),
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
          // Progress stays visible while running and remains visible after the
          // job completes (Requirement 19.3). Telemetry detail is role-gated:
          // admins see the detailed rail; everyone else sees a sanitized
          // summary (Requirements 3, 19.4).
          if (progress != null && !progress.isEmpty) ...[
            _ProgressView(
              progress: progress,
              isLoading: _isLoading,
              showDetailed: _telemetryGate?.showDetailed ?? false,
            ),
            const SizedBox(height: 12),
          ],
          if (result != null) ...[
            if (answer.isNotEmpty)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Kết quả',
                          style: Theme.of(context).textTheme.titleSmall),
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
            // Hidden-by-default technical telemetry (verification matrix,
            // reasoning chain, sources) from the raw result envelope. Keeps the
            // Pro/Deep evidence detail available on demand without inlining it
            // into the answer body. Self-hides when there is nothing to show.
            ResearchTelemetryPanel(envelope: result),
          ],
        ],
      ),
    );
  }
}

/// Renders the ordered pipeline stages and the current status note streamed
/// over SSE. Mirrors the web progressive-disclosure surface in a compact form.
class _ProgressView extends StatelessWidget {
  const _ProgressView({
    required this.progress,
    required this.isLoading,
    required this.showDetailed,
  });

  final ResearchProgress progress;
  final bool isLoading;

  /// When true (admin only), the detailed telemetry rail is shown verbatim.
  /// Otherwise labels and notes are sanitized to the summary view (R3.2, R3.5).
  final bool showDetailed;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final note = showDetailed
        ? progress.statusNote
        : stripTelemetryLabels(progress.statusNote);

    return Card(
      key: const Key('research-progress'),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                if (isLoading)
                  const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                else
                  Icon(Icons.check_circle,
                      size: 18, color: theme.colorScheme.primary),
                const SizedBox(width: 8),
                Text('Tiến trình', style: theme.textTheme.titleSmall),
              ],
            ),
            if (note.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(note, style: theme.textTheme.bodySmall),
            ],
            if (progress.stages.isNotEmpty) ...[
              const SizedBox(height: 8),
              ...progress.stages.map(
                (stage) => _StageRow(stage: stage, showDetailed: showDetailed),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _StageRow extends StatelessWidget {
  const _StageRow({required this.stage, required this.showDetailed});

  final ResearchProgressStage stage;
  final bool showDetailed;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final IconData icon;
    final Color color;
    if (stage.isError) {
      icon = Icons.error_outline;
      color = theme.colorScheme.error;
    } else if (stage.isComplete) {
      icon = Icons.check_circle;
      color = theme.colorScheme.primary;
    } else if (stage.isActive) {
      icon = Icons.autorenew;
      color = theme.colorScheme.secondary;
    } else {
      icon = Icons.radio_button_unchecked;
      color = theme.disabledColor;
    }

    // Stage labels keep their pipeline names but have internal telemetry labels
    // stripped for the sanitized summary; the per-stage detail is part of the
    // detailed rail and is only shown to admins (R3.2, R3.5).
    final label =
        showDetailed ? stage.label : stripTelemetryLabels(stage.label);
    final showDetail = showDetailed && stage.detail.isNotEmpty;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: theme.textTheme.bodyMedium),
                if (showDetail)
                  Text(stage.detail, style: theme.textTheme.bodySmall),
              ],
            ),
          ),
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
