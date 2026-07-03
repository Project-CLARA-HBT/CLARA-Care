// AI Council ("Hội chẩn AI") surface for the CLARA_Mobile redesign
// (Experience_V3).
//
// clara-mobile-redesign, Task 6. A polished, guided 3-step wizard
// (intake → chọn chuyên khoa → kết quả) built on the `ClaraTokens` design
// system, replacing the dense single form of the legacy
// `CouncilCaseScreen`. It drives the SAME case-based Council_API endpoints
// via [ApiClient] (create case → run intake → run council), so there is no
// mobile-only result shape — consensus / divergence / final recommendation /
// participating specialists are read from the shared `run_council` envelope
// keys, exactly as the legacy screen and the web wizard.
//
// Safety invariants (preserved from the legacy flow):
//   * The "review with a licensed clinician / not-a-doctor" directive
//     (`kCouncilClinicianDirective`) is ALWAYS rendered prominently on the
//     result step, regardless of state.
//   * Analytics are no-PII: only coarse, content-free flags/counts are
//     transmitted (`has_transcript` boolean, `specialist_count`) — never
//     transcript, symptom, medication, or history free text.
//   * Every network call is guarded on `sessionStore.accessToken`; a
//     null/empty token surfaces a Vietnamese session-expiry message and no
//     request is made.
//
// This surface adds no new API calls and changes no contract; it reuses the
// existing components and the shared clinician directive constant.

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../../core/analytics.dart';
import '../../core/api_client.dart';
import '../../core/session_store.dart';
import '../../screens/council_case_screen.dart' show kCouncilClinicianDirective;
import '../../theme/components/clara_button.dart';
import '../../theme/components/clara_card.dart';
import '../../theme/components/clara_chip.dart';
import '../../theme/components/clara_input.dart';
import '../../theme/components/section_header.dart';
import '../../theme/glass/glass_surface.dart';
import '../../theme/glass/glass_tokens.dart';
import '../../theme/tokens.dart';
import '../../widgets/error_retry_view.dart';
import '../states/skeleton.dart';

/// The three sequential steps of the guided wizard.
enum _CouncilStep { intake, specialists, result }

/// Redesigned, guided AI Council wizard. See file header.
class CouncilSurfaceV3 extends StatefulWidget {
  const CouncilSurfaceV3({
    super.key,
    required this.apiClient,
    required this.sessionStore,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  @override
  State<CouncilSurfaceV3> createState() => _CouncilSurfaceV3State();
}

class _CouncilSurfaceV3State extends State<CouncilSurfaceV3> {
  final _titleController = TextEditingController(text: 'Ca hội chẩn mới');
  final _transcriptController = TextEditingController();
  final _symptomsController = TextEditingController();
  final _medicationsController = TextEditingController();
  final _historyController = TextEditingController();

  _CouncilStep _step = _CouncilStep.intake;
  int _specialistCount = 3;
  bool _isLoading = false;
  String? _error;

  int? _caseId;
  bool _intakeFallback = false;
  _CouncilResultView? _result;

  @override
  void initState() {
    super.initState();
    getAnalyticsClient().captureScreenView(MobileAnalyticsEvents.councilViewed);
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

  // --- Payload helpers (match the legacy case-based contract exactly) --------

  List<String> _parseList(String value) {
    return value
        .split(RegExp(r'[\n,]'))
        .map((item) => item.trim())
        .where((item) => item.isNotEmpty)
        .toList();
  }

  /// Resolves a non-empty access token or sets a Vietnamese session-expiry
  /// error and returns `null` (fail-closed — no request is issued).
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

  void _setError(String message) {
    if (!mounted) {
      return;
    }
    setState(() {
      _error = message;
    });
  }

  // --- Step 1 → 2: create the case and run intake extraction -----------------

  Future<void> _createCaseAndIntake() async {
    final symptoms = _parseList(_symptomsController.text);
    final history = _historyController.text.trim();
    final transcript = _transcriptController.text.trim();

    if (symptoms.isEmpty && history.isEmpty && transcript.isEmpty) {
      setState(() {
        _error =
            'Vui lòng nhập triệu chứng, tiền sử hoặc mô tả ca để tạo hội chẩn.';
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

      final caseId = (created['id'] as num?)?.toInt() ??
          (created['case_id'] as num?)?.toInt();
      if (caseId == null) {
        throw ApiException(
            message: 'Không nhận được mã ca hội chẩn từ server.');
      }

      // No-PII analytics: only the coarse `has_transcript` flag is sent — never
      // clinical free text (transcript/symptoms/medications/history).
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
        _step = _CouncilStep.specialists;
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

  // --- Step 2 → 3: run the Council for the persisted case ---------------------

  Future<void> _runCouncil() async {
    final caseId = _caseId;
    if (caseId == null) {
      setState(() {
        _step = _CouncilStep.intake;
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

    // No-PII analytics: only the non-PII specialist count is attached.
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
        _result = _CouncilResultView.fromCaseEnvelope(response);
        _step = _CouncilStep.result;
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

  void _startNewCase() {
    setState(() {
      _step = _CouncilStep.intake;
      _caseId = null;
      _result = null;
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

  // --- Build -----------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Hội chẩn AI')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(
            ClaraTokens.spaceMd,
            ClaraTokens.spaceMd,
            ClaraTokens.spaceMd,
            ClaraTokens.spaceXl,
          ),
          children: [
            _StepIndicator(step: _step),
            const SizedBox(height: ClaraTokens.spaceLg),
            if (_isLoading)
              const ClaraSkeletonList(itemCount: 3, showLeading: false)
            else ...[
              if (_step == _CouncilStep.intake) ..._buildIntakeStep(context),
              if (_step == _CouncilStep.specialists)
                ..._buildSpecialistsStep(context),
              if (_step == _CouncilStep.result) ..._buildResultStep(context),
            ],
            if (_error != null && !_isLoading) ...[
              const SizedBox(height: ClaraTokens.spaceMd),
              StatusByText(
                label: _error!,
                level: A11yStatusLevel.danger,
                semanticsPrefix: 'Lỗi',
              ),
            ],
          ],
        ),
      ),
    );
  }

  // --- Step 1: Nhập thông tin ca bệnh ----------------------------------------

  List<Widget> _buildIntakeStep(BuildContext context) {
    final theme = Theme.of(context);
    return [
      const SectionHeader(title: 'Nhập thông tin ca bệnh'),
      Padding(
        padding: const EdgeInsets.fromLTRB(
          ClaraTokens.spaceMd,
          0,
          ClaraTokens.spaceMd,
          ClaraTokens.spaceSm,
        ),
        child: Text(
          'Cung cấp mô tả ca bệnh để hội đồng chuyên khoa AI phân tích. '
          'Bạn có thể dán lời thoại để hệ thống tự trích xuất thông tin.',
          style: theme.textTheme.bodyMedium
              ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
        ),
      ),
      ClaraCard.static_(
        semanticLabel: 'Biểu mẫu thông tin ca bệnh',
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ClaraInput(
              controller: _titleController,
              label: 'Tiêu đề ca',
              hint: 'Ví dụ: Đau ngực khó thở',
              enabled: !_isLoading,
              textInputAction: TextInputAction.next,
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            _MultilineField(
              controller: _transcriptController,
              label: 'Triệu chứng / lời thoại ca bệnh',
              hint: 'Mô tả triệu chứng, mỗi dòng một ý, hoặc dán lời thoại',
              enabled: !_isLoading,
              minLines: 3,
              maxLines: 6,
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            _MultilineField(
              controller: _symptomsController,
              label: 'Triệu chứng chính (không bắt buộc)',
              hint: 'Mỗi dòng một triệu chứng',
              enabled: !_isLoading,
              minLines: 2,
              maxLines: 4,
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            _MultilineField(
              controller: _medicationsController,
              label: 'Thuốc đang dùng (không bắt buộc)',
              hint: 'Mỗi dòng một thuốc',
              enabled: !_isLoading,
              minLines: 1,
              maxLines: 4,
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            _MultilineField(
              controller: _historyController,
              label: 'Tiền sử / bối cảnh (không bắt buộc)',
              hint: 'Tóm tắt bệnh sử và bối cảnh ca bệnh',
              enabled: !_isLoading,
              minLines: 2,
              maxLines: 4,
            ),
          ],
        ),
      ),
      const SizedBox(height: ClaraTokens.spaceLg),
      ClaraButton.primary(
        label: 'Tiếp tục',
        icon: Icons.arrow_forward,
        loading: _isLoading,
        onPressed: _isLoading ? null : _createCaseAndIntake,
      ),
    ];
  }

  // --- Step 2: Chọn số chuyên khoa -------------------------------------------

  List<Widget> _buildSpecialistsStep(BuildContext context) {
    final theme = Theme.of(context);
    return [
      const SectionHeader(title: 'Chọn số chuyên khoa'),
      if (_intakeFallback) ...[
        ClaraCard.static_(
          semanticLabel: 'Thông báo trích xuất ở chế độ dự phòng',
          child: const StatusByText(
            label:
                'Trích xuất ở chế độ dự phòng. Vui lòng kiểm tra lại thông tin '
                'trước khi hội chẩn.',
            level: A11yStatusLevel.warning,
            semanticsPrefix: 'Lưu ý',
          ),
        ),
        const SizedBox(height: ClaraTokens.spaceMd),
      ],
      ClaraCard.static_(
        semanticLabel: 'Chọn số chuyên khoa tham gia hội chẩn',
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Ca #${_caseId ?? '--'} đã sẵn sàng',
              style: theme.textTheme.titleSmall,
            ),
            const SizedBox(height: ClaraTokens.spaceXs),
            Text(
              'Chọn số lượng chuyên khoa AI tham gia. Càng nhiều chuyên khoa, '
              'góc nhìn càng đa dạng nhưng thời gian phân tích lâu hơn.',
              style: theme.textTheme.bodyMedium
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            Wrap(
              spacing: ClaraTokens.spaceSm,
              runSpacing: ClaraTokens.spaceSm,
              children: [
                for (final count in const [2, 3, 4, 5])
                  ClaraChip(
                    label: '$count chuyên khoa',
                    icon: Icons.groups_outlined,
                    selected: _specialistCount == count,
                    selectedSemanticsValue: 'Đã chọn',
                    onTap: _isLoading
                        ? null
                        : () => setState(() => _specialistCount = count),
                  ),
              ],
            ),
          ],
        ),
      ),
      const SizedBox(height: ClaraTokens.spaceLg),
      ClaraButton.primary(
        label: 'Bắt đầu hội chẩn',
        icon: Icons.play_arrow,
        loading: _isLoading,
        onPressed: _isLoading ? null : _runCouncil,
      ),
      const SizedBox(height: ClaraTokens.spaceSm),
      ClaraButton.secondary(
        label: 'Quay lại chỉnh sửa',
        icon: Icons.arrow_back,
        onPressed: _isLoading
            ? null
            : () => setState(() => _step = _CouncilStep.intake),
      ),
    ];
  }

  // --- Step 3: Kết quả --------------------------------------------------------

  List<Widget> _buildResultStep(BuildContext context) {
    final result = _result;
    if (result == null) {
      return [
        ErrorRetryView(
          message: 'Không có kết quả hội chẩn để hiển thị.',
          onRetry: _runCouncil,
        ),
      ];
    }

    final theme = Theme.of(context);
    return [
      const SectionHeader(title: 'Kết quả hội chẩn'),
      // Mandatory clinician-review directive — ALWAYS present, prominent, first.
      ClaraCard.static_(
        semanticLabel: 'Lưu ý an toàn: tham vấn bác sĩ',
        child: const StatusByText(
          label: kCouncilClinicianDirective,
          level: A11yStatusLevel.warning,
          icon: Icons.health_and_safety_outlined,
          semanticsPrefix: 'Lưu ý an toàn',
        ),
      ),
      const SizedBox(height: ClaraTokens.spaceMd),
      // Consensus / divergence headline.
      ClaraCard.static_(
        semanticLabel: 'Tình trạng đồng thuận',
        child: StatusByText(
          label: result.hasDivergence
              ? 'Có điểm khác biệt giữa các chuyên khoa'
              : 'Các chuyên khoa đồng thuận',
          level: result.hasDivergence
              ? A11yStatusLevel.warning
              : A11yStatusLevel.success,
        ),
      ),
      if (result.consensusSummary.isNotEmpty) ...[
        const SizedBox(height: ClaraTokens.spaceMd),
        _ResultSection(
          title: 'Đồng thuận',
          child:
              Text(result.consensusSummary, style: theme.textTheme.bodyMedium),
        ),
      ],
      if (result.divergenceNotes.isNotEmpty) ...[
        const SizedBox(height: ClaraTokens.spaceMd),
        _ResultSection(
          title: 'Điểm khác biệt',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              for (final note in result.divergenceNotes)
                Padding(
                  padding: const EdgeInsets.only(bottom: ClaraTokens.spaceXs),
                  child: Text('• $note', style: theme.textTheme.bodyMedium),
                ),
            ],
          ),
        ),
      ],
      if (result.finalRecommendation.isNotEmpty) ...[
        const SizedBox(height: ClaraTokens.spaceMd),
        _ResultSection(
          title: 'Khuyến nghị cuối',
          child: Text(
            result.finalRecommendation,
            style: theme.textTheme.bodyMedium,
          ),
        ),
      ],
      if (result.specialists.isNotEmpty) ...[
        const SizedBox(height: ClaraTokens.spaceMd),
        _ResultSection(
          title: 'Chuyên khoa tham gia',
          child: Wrap(
            spacing: ClaraTokens.spaceSm,
            runSpacing: ClaraTokens.spaceSm,
            children: [
              for (final specialist in result.specialists)
                ClaraChip(
                    label: specialist, icon: Icons.local_hospital_outlined),
            ],
          ),
        ),
      ],
      const SizedBox(height: ClaraTokens.spaceLg),
      ClaraButton.primary(
        label: 'Hội chẩn ca mới',
        icon: Icons.refresh,
        onPressed: _isLoading ? null : _startNewCase,
      ),
    ];
  }
}

/// A compact three-step progress indicator for the wizard.
///
/// Pure decorative navigation chrome (step numbers + labels, no clinical text),
/// so it renders on a thin liquid-glass surface; when the ambient [GlassScope]
/// is off the same indicator renders opaque with identical geometry. The
/// step/progress semantics label is preserved.
class _StepIndicator extends StatelessWidget {
  const _StepIndicator({required this.step});

  final _CouncilStep step;

  @override
  Widget build(BuildContext context) {
    const labels = ['Thông tin', 'Chuyên khoa', 'Kết quả'];
    final scheme = Theme.of(context).colorScheme;
    final activeIndex = _CouncilStep.values.indexOf(step);

    return Semantics(
      label: 'Bước ${activeIndex + 1} trên 3: ${labels[activeIndex]}',
      container: true,
      child: GlassSurface(
        blurSigma: GlassTokens.blurCard,
        radius: GlassTokens.radiusCard,
        fill: GlassFill.thin,
        padding: const EdgeInsets.symmetric(
          horizontal: ClaraTokens.spaceMd,
          vertical: ClaraTokens.spaceMd,
        ),
        child: Row(
          children: List.generate(labels.length, (index) {
            final active = index <= activeIndex;
            final circle = Column(
              children: [
                CircleAvatar(
                  radius: 16,
                  backgroundColor:
                      active ? scheme.primary : scheme.surfaceContainerHighest,
                  child: active && index < activeIndex
                      ? Icon(Icons.check, size: 18, color: scheme.onPrimary)
                      : Text(
                          '${index + 1}',
                          style: TextStyle(
                            color: active
                                ? scheme.onPrimary
                                : scheme.onSurfaceVariant,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                ),
                const SizedBox(height: ClaraTokens.spaceXs),
                Text(
                  labels[index],
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color:
                            active ? scheme.primary : scheme.onSurfaceVariant,
                        fontWeight: active ? FontWeight.w600 : FontWeight.w400,
                      ),
                ),
              ],
            );

            if (index == labels.length - 1) {
              return Expanded(child: circle);
            }
            return Expanded(
              child: Row(
                children: [
                  Expanded(child: circle),
                  Padding(
                    padding: const EdgeInsets.only(bottom: 18),
                    child: SizedBox(
                      width: ClaraTokens.spaceLg,
                      child: Divider(
                        thickness: 2,
                        color: index < activeIndex
                            ? scheme.primary
                            : scheme.surfaceContainerHighest,
                      ),
                    ),
                  ),
                ],
              ),
            );
          }),
        ),
      ),
    );
  }
}

/// A titled result section rendered on a static [ClaraCard].
class _ResultSection extends StatelessWidget {
  const _ResultSection({required this.title, required this.child});

  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return ClaraCard.static_(
      semanticLabel: title,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          A11yLabeled(
            label: title,
            isHeader: true,
            child: Text(title, style: Theme.of(context).textTheme.titleSmall),
          ),
          const SizedBox(height: ClaraTokens.spaceSm),
          child,
        ],
      ),
    );
  }
}

/// A multiline text field built on the theme's input decoration, matching the
/// [ClaraInput] look while allowing multiple lines (which `ClaraInput` does
/// not expose). Honors OS text scaling via [A11y.resolveTextScaler].
class _MultilineField extends StatelessWidget {
  const _MultilineField({
    required this.controller,
    required this.label,
    this.hint,
    this.enabled = true,
    this.minLines = 2,
    this.maxLines = 5,
  });

  final TextEditingController controller;
  final String label;
  final String? hint;
  final bool enabled;
  final int minLines;
  final int maxLines;

  @override
  Widget build(BuildContext context) {
    final textScaler = A11y.resolveTextScaler(context);
    return MediaQuery(
      data: MediaQuery.of(context).copyWith(textScaler: textScaler),
      child: TextFormField(
        controller: controller,
        enabled: enabled,
        minLines: minLines,
        maxLines: maxLines,
        keyboardType: TextInputType.multiline,
        textInputAction: TextInputAction.newline,
        decoration: InputDecoration(
          labelText: label,
          hintText: hint,
          alignLabelWithHint: true,
        ),
      ),
    );
  }
}

/// End_User projection of the case-scoped Council result envelope, reading the
/// shared `run_council` keys from the case's `result` block. Mirrors the web /
/// legacy `CouncilCaseScreen` consensus / divergence / final layout (no
/// mobile-only result shape).
class _CouncilResultView {
  _CouncilResultView({
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
  factory _CouncilResultView.fromCaseEnvelope(Map<String, dynamic> envelope) {
    final result = envelope['result'];
    final payload = result is Map<String, dynamic> ? result : envelope;

    final divergence = _stringList(payload['divergence_notes']);
    final conflicts = _stringList(payload['conflict_list']);
    final notes = <String>[...divergence, ...conflicts];

    return _CouncilResultView(
      consensusSummary: (payload['consensus_summary'] ?? '').toString().trim(),
      finalRecommendation:
          (payload['final_recommendation'] ?? '').toString().trim(),
      divergenceNotes: notes,
      specialists: _stringList(payload['requested_specialists']),
      hasDivergence: notes.isNotEmpty,
    );
  }
}
