import 'package:flutter/material.dart';

import '../core/analytics.dart';
import '../core/api_client.dart';
import '../core/session_store.dart';

// =============================================================================
// Council mobile parity (clara-council-upgrade Requirement 8.3, 8.4, 8.5, 8.6).
//
// This screen brings the web case-based flow to mobile: create a case, run
// intake, select specialists, run the Council, and review the persisted result.
// It reuses the existing Council_API case endpoints (via [ApiClient]) so there
// is no mobile-only result shape — the result is the shared `run_council`
// envelope and the screen renders consensus / divergence / final recommendation
// from the same keys as the web (Requirement 8.2, 8.3).
//
// Gating (Requirement 8.5): the surface is exposed only when BOTH
//   * the build-time [kCouncilMobileParityEnabled] flag is on, AND
//   * the `council` feature flag from the feature-flags endpoint is enabled for
//     the user (checked by the dashboard before routing here).
// With the build flag off, the dashboard routes to the legacy direct-run
// `CouncilScreen` instead, so today's behavior is preserved byte-for-byte.
//
// Privacy (Requirement 8.4): analytics events transmit only the non-PII
// specialist count (and coarse, content-free flags) — never transcript,
// symptoms, medications, or history free text. The shared consent + PII-strip
// [Analytics] facade is the final guard.
// =============================================================================

/// Build-time, client-readable feature flag. Override with
/// `--dart-define=COUNCIL_MOBILE_PARITY_ENABLED=true`. Defaults to OFF so the
/// parity surfaces are never exposed unless explicitly enabled (Requirement
/// 8.5). When off, the dashboard keeps routing to the legacy `CouncilScreen`.
const bool kCouncilMobileParityEnabled =
    bool.fromEnvironment('COUNCIL_MOBILE_PARITY_ENABLED', defaultValue: false);

/// The "review with a licensed clinician" directive, preserved on every Council
/// output regardless of state (Requirement 8.3, mirrors the web). Always
/// rendered on the result surface.
const String kCouncilClinicianDirective =
    'Kết quả hội chẩn chỉ mang tính hỗ trợ quyết định, không thay thế chẩn đoán '
    'y khoa. Vui lòng tham vấn bác sĩ có chuyên môn (licensed clinician) trước '
    'khi đưa ra quyết định lâm sàng.';

/// The three sequential phases of the parity flow, mirroring the web wizard.
enum _CouncilPhase { intake, specialists, result }

class CouncilCaseScreen extends StatefulWidget {
  const CouncilCaseScreen({
    super.key,
    required this.apiClient,
    required this.sessionStore,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  @override
  State<CouncilCaseScreen> createState() => _CouncilCaseScreenState();
}

class _CouncilCaseScreenState extends State<CouncilCaseScreen> {
  final _titleController = TextEditingController(text: 'Ca hội chẩn mới');
  final _transcriptController = TextEditingController();
  final _symptomsController = TextEditingController();
  final _medicationsController = TextEditingController();
  final _historyController = TextEditingController();

  _CouncilPhase _phase = _CouncilPhase.intake;
  int _specialistCount = 3;
  bool _isLoading = false;
  String? _error;

  int? _caseId;
  bool _intakeFallback = false;
  _CouncilCaseView? _view;

  @override
  void initState() {
    super.initState();
    getAnalyticsClient()
        .captureScreenView(MobileAnalyticsEvents.councilViewed);
  }

  @override
  void dispose() {
    _titleController.dispose();
    _transcriptController.dispose();
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

  String? _requireToken() {
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) {
      setState(() {
        _error = 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.';
      });
      return null;
    }
    return token;
  }

  Map<String, dynamic> _buildRequestPayload() {
    return {
      'symptoms': _parseList(_symptomsController.text),
      'medications': _parseList(_medicationsController.text),
      'history': _historyController.text.trim(),
      'specialist_count': _specialistCount,
      'labs': <String, dynamic>{},
      'specialists': <String>[],
    };
  }

  /// Phase 1 → 2: create the case and (when a transcript is present) run intake.
  Future<void> _createCaseAndIntake() async {
    final symptoms = _parseList(_symptomsController.text);
    final history = _historyController.text.trim();
    final transcript = _transcriptController.text.trim();

    if (symptoms.isEmpty && history.isEmpty && transcript.isEmpty) {
      setState(() {
        _error =
            'Vui lòng nhập bệnh sử, triệu chứng hoặc lời thoại để tạo ca hội chẩn.';
      });
      return;
    }

    final token = _requireToken();
    if (token == null) {
      return;
    }

    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final created = await widget.apiClient.createCouncilCase(
        accessToken: token,
        payload: {
          'title': _titleController.text.trim().isEmpty
              ? 'Ca hội chẩn mới'
              : _titleController.text.trim(),
          'intake_mode': 'transcript',
          'transcript': transcript,
          'request': _buildRequestPayload(),
        },
      );

      final caseId = (created['id'] as num?)?.toInt();
      if (caseId == null) {
        throw ApiException(message: 'Không nhận được mã ca hội chẩn từ server.');
      }

      // Non-PII analytics: only coarse flags, no clinical free text
      // (Requirement 8.4).
      getAnalyticsClient().capture(
        AnalyticsEvent(
          MobileAnalyticsEvents.councilCaseCreated,
          {'has_transcript': transcript.isNotEmpty},
        ),
      );

      var fallback = false;
      if (transcript.isNotEmpty) {
        final intake = await widget.apiClient.submitCouncilCaseIntake(
          accessToken: token,
          caseId: caseId,
          transcript: transcript,
        );
        fallback = _detectIntakeFallback(intake);
      }

      if (!mounted) {
        return;
      }
      setState(() {
        _caseId = caseId;
        _intakeFallback = fallback;
        _phase = _CouncilPhase.specialists;
      });
    } on ApiException catch (error) {
      _setError(error.message);
    } catch (_) {
      _setError('Không thể tạo ca hội chẩn lúc này. Vui lòng thử lại.');
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  /// Phase 2 → 3: run the Council for the persisted case.
  Future<void> _runCouncil() async {
    final caseId = _caseId;
    if (caseId == null) {
      setState(() {
        _phase = _CouncilPhase.intake;
        _error = 'Chưa có ca hội chẩn. Vui lòng tạo ca trước.';
      });
      return;
    }

    final token = _requireToken();
    if (token == null) {
      return;
    }

    setState(() {
      _isLoading = true;
      _error = null;
    });

    // Named product event for a council run. Only the non-PII specialist count
    // is attached; clinical free text is never transmitted (Requirement 8.4).
    getAnalyticsClient().capture(
      AnalyticsEvent(
        MobileAnalyticsEvents.councilRun,
        {'specialist_count': _specialistCount},
      ),
    );

    try {
      final response = await widget.apiClient.runCouncilCase(
        accessToken: token,
        caseId: caseId,
        request: _buildRequestPayload(),
        specialistCount: _specialistCount,
      );

      if (!mounted) {
        return;
      }
      setState(() {
        _view = _CouncilCaseView.fromCaseEnvelope(response);
        _phase = _CouncilPhase.result;
      });
    } on ApiException catch (error) {
      _setError(error.message);
    } catch (_) {
      _setError('Không thể chạy hội chẩn lúc này. Vui lòng thử lại.');
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
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

  void _startNewCase() {
    setState(() {
      _phase = _CouncilPhase.intake;
      _caseId = null;
      _view = null;
      _intakeFallback = false;
      _error = null;
    });
  }

  static bool _detectIntakeFallback(Map<String, dynamic> caseEnvelope) {
    final intake = caseEnvelope['intake'];
    if (intake is! Map) {
      return false;
    }
    final disclosure = intake['ai_disclosure'];
    if (disclosure is Map && disclosure['is_fallback'] == true) {
      return true;
    }
    final model = (intake['model_used'] ?? intake['model'] ?? '').toString();
    return model.contains('heuristic-fallback');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Hội chẩn AI (theo ca)')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _PhaseIndicator(phase: _phase),
          const SizedBox(height: 16),
          if (_phase == _CouncilPhase.intake) ..._buildIntakeStep(context),
          if (_phase == _CouncilPhase.specialists)
            ..._buildSpecialistsStep(context),
          if (_phase == _CouncilPhase.result) ..._buildResultStep(context),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ],
        ],
      ),
    );
  }

  List<Widget> _buildIntakeStep(BuildContext context) {
    return [
      TextField(
        controller: _titleController,
        enabled: !_isLoading,
        decoration: const InputDecoration(
          labelText: 'Tên ca',
          border: OutlineInputBorder(),
        ),
      ),
      const SizedBox(height: 12),
      TextField(
        controller: _transcriptController,
        minLines: 2,
        maxLines: 5,
        enabled: !_isLoading,
        decoration: const InputDecoration(
          labelText: 'Lời thoại / mô tả ca (không bắt buộc)',
          border: OutlineInputBorder(),
          hintText: 'Dán nội dung trao đổi để hệ thống trích xuất thông tin',
        ),
      ),
      const SizedBox(height: 12),
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
      const SizedBox(height: 16),
      FilledButton(
        onPressed: _isLoading ? null : _createCaseAndIntake,
        child: _isLoading
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            : const Text('Tạo ca & trích xuất'),
      ),
    ];
  }

  List<Widget> _buildSpecialistsStep(BuildContext context) {
    return [
      if (_intakeFallback)
        Card(
          color: Colors.amber.shade50,
          child: const Padding(
            padding: EdgeInsets.all(12),
            child: Row(
              children: [
                Icon(Icons.info_outline, color: Colors.orange),
                SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Trích xuất ở chế độ dự phòng (degraded). Vui lòng kiểm tra '
                    'lại thông tin trước khi hội chẩn.',
                  ),
                ),
              ],
            ),
          ),
        ),
      if (_intakeFallback) const SizedBox(height: 12),
      Text(
        'Ca #${_caseId ?? '--'} đã được tạo. Chọn số chuyên khoa tham gia hội chẩn.',
        style: Theme.of(context).textTheme.bodyMedium,
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
      const SizedBox(height: 16),
      FilledButton(
        onPressed: _isLoading ? null : _runCouncil,
        child: _isLoading
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            : const Text('Chạy hội chẩn'),
      ),
      const SizedBox(height: 8),
      TextButton(
        onPressed: _isLoading
            ? null
            : () => setState(() => _phase = _CouncilPhase.intake),
        child: const Text('Quay lại chỉnh sửa thông tin'),
      ),
    ];
  }

  List<Widget> _buildResultStep(BuildContext context) {
    final view = _view;
    return [
      if (view != null) _CouncilResultCard(view: view),
      // The "review with a licensed clinician" directive is preserved on every
      // Council output regardless of state (Requirement 8.3).
      const SizedBox(height: 12),
      Card(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(Icons.health_and_safety_outlined),
              const SizedBox(width: 8),
              const Expanded(child: Text(kCouncilClinicianDirective)),
            ],
          ),
        ),
      ),
      const SizedBox(height: 16),
      OutlinedButton(
        onPressed: _isLoading ? null : _startNewCase,
        child: const Text('Tạo ca hội chẩn mới'),
      ),
    ];
  }
}

/// A compact three-step progress indicator mirroring the web wizard.
class _PhaseIndicator extends StatelessWidget {
  const _PhaseIndicator({required this.phase});

  final _CouncilPhase phase;

  @override
  Widget build(BuildContext context) {
    const labels = ['Nhập liệu', 'Chuyên khoa', 'Kết quả'];
    final activeIndex = _CouncilPhase.values.indexOf(phase);
    return Row(
      children: List.generate(labels.length, (index) {
        final active = index <= activeIndex;
        return Expanded(
          child: Column(
            children: [
              CircleAvatar(
                radius: 14,
                backgroundColor: active
                    ? Theme.of(context).colorScheme.primary
                    : Theme.of(context).colorScheme.surfaceContainerHighest,
                child: Text(
                  '${index + 1}',
                  style: TextStyle(
                    color: active
                        ? Theme.of(context).colorScheme.onPrimary
                        : Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
              const SizedBox(height: 4),
              Text(labels[index], style: Theme.of(context).textTheme.bodySmall),
            ],
          ),
        );
      }),
    );
  }
}

/// Renders the shared `run_council` result: consensus, divergence, and final
/// recommendation — the same shape as the web (Requirement 8.2, 8.3).
class _CouncilResultCard extends StatelessWidget {
  const _CouncilResultCard({required this.view});

  final _CouncilCaseView view;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(
                      view.hasDivergence
                          ? Icons.warning_amber
                          : Icons.check_circle,
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
                  Text('Điểm cần lưu ý / bất đồng',
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

/// End_User council projection for the case-scoped result envelope, reading the
/// shared `run_council` keys from the case's `result` block. Mirrors the web
/// consensus/divergence/final layout (Requirement 8.2, 8.3).
class _CouncilCaseView {
  _CouncilCaseView({
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
              return (item['note'] ??
                      item['summary'] ??
                      item['description'] ??
                      item['type'] ??
                      '')
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

  /// Builds the view from the case envelope returned by the run endpoint. The
  /// shared `run_council` result lives under the `result` key; when absent we
  /// fall back to reading the keys at the top level so the projection is robust.
  factory _CouncilCaseView.fromCaseEnvelope(Map<String, dynamic> envelope) {
    final result = envelope['result'];
    final payload = result is Map<String, dynamic> ? result : envelope;

    final divergence = _stringList(payload['divergence_notes']);
    final conflicts = _stringList(payload['conflict_list']);
    final notes = <String>[...divergence, ...conflicts];

    return _CouncilCaseView(
      consensusSummary: (payload['consensus_summary'] ?? '').toString().trim(),
      finalRecommendation:
          (payload['final_recommendation'] ?? '').toString().trim(),
      divergenceNotes: notes,
      specialists: _stringList(payload['requested_specialists']),
      hasDivergence: notes.isNotEmpty,
    );
  }
}
