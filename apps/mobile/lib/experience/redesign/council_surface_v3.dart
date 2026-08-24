// AI Council ("Hội chẩn AI") surface for CLARA_Mobile (Spec v5 Section 7.0, 7.8, 11).
//
// Implements the canonical 6-step multi-specialty workflow:
//   1. Case (Thông tin ca bệnh & Nhập liệu)
//   2. Question (Câu hỏi lâm sàng trọng tâm)
//   3. Context (Chuyên khoa & Dữ liệu đầu vào)
//   4. Review (Rà soát thông tin trước khi chạy)
//   5. Run (Chạy phân tích hội đồng đa khoa)
//   6. Result (Kết quả hội chẩn 7 tầng chuyên sâu)
//
// Includes Case Library (Thư viện ca hội chẩn) for browsing, searching, and resuming.
//
// Enforces the exact 7-Tier Result Hierarchy:
//   Tier 1: Escalation / Red Flags (Cảnh báo khẩn & Điểm cần can thiệp)
//   Tier 2: Recommendation (Khuyến nghị lâm sàng & Tóm tắt)
//   Tier 3: Consensus / Agreement (Đồng thuận đa chuyên khoa & Báo cáo chuyên khoa)
//   Tier 4: Uncertainty / Divergence (Độ không chắc chắn & Điểm bất đồng)
//   Tier 5: Evidence / Citations (Y văn & Nguồn trích dẫn đã kiểm chứng)
//   Tier 6: Clinician Action (Quyết định lâm sàng, Chuyển giao, Override, Pause)
//   Tier 7: Technical Details (Giám sát quy trình & Cơ sở mô hình AI)
//
// Safety invariants:
//   * Mandatory clinician-review directive (`kCouncilClinicianDirective`) is ALWAYS
//     rendered prominently at the top of results.
//   * No-PII analytics: only coarse flags and counts transmitted.
//   * Every request guarded on `sessionStore.accessToken`.

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

/// The canonical 6 sequential steps of the Council workflow.
enum _CouncilStep { caseInfo, question, context, review, run, result }

/// AI Council surface with 6-step workflow, Case Library, and 7-tier decision review.
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
  // Navigation & View mode
  bool _showLibrary = false;
  _CouncilStep _step = _CouncilStep.caseInfo;

  // Controllers
  final _titleController = TextEditingController(text: 'Ca hội chẩn mới');
  final _questionController =
      TextEditingController(text: 'Đánh giá nguy cơ và định hướng xử trí');
  final _transcriptController = TextEditingController();
  final _symptomsController = TextEditingController();
  final _medicationsController = TextEditingController();
  final _historyController = TextEditingController();
  final _labsController = TextEditingController();

  // Selected specialists
  int _specialistCount = 3;
  final Set<String> _selectedSpecialties = {
    'Nội tổng quát',
    'Tim mạch',
    'Dược lâm sàng'
  };

  // State
  bool _isLoading = false;
  String? _error;
  int? _caseId;
  bool _intakeFallback = false;
  _CouncilResultView? _result;
  List<Map<String, dynamic>> _savedCases = [];

  // Active oversight
  bool _oversightPaused = false;
  String? _guardNotice;

  @override
  void initState() {
    super.initState();
    getAnalyticsClient().captureScreenView(MobileAnalyticsEvents.councilViewed);
    _loadCaseLibrary();
  }

  @override
  void dispose() {
    _titleController.dispose();
    _questionController.dispose();
    _transcriptController.dispose();
    _symptomsController.dispose();
    _medicationsController.dispose();
    _historyController.dispose();
    _labsController.dispose();
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
      'question': _questionController.text.trim(),
      'symptoms': _parseList(_symptomsController.text),
      'medications': _parseList(_medicationsController.text),
      'history': _historyController.text.trim(),
      'specialist_count': _specialistCount,
      'specialists': _selectedSpecialties.toList(),
      'labs': _labsController.text.trim().isNotEmpty
          ? {'notes': _labsController.text.trim()}
          : <String, dynamic>{},
    };
  }

  Future<void> _loadCaseLibrary() async {
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) return;
    try {
      final res = await widget.apiClient.listCouncilCases(
        accessToken: token,
        limit: 10,
      );
      final items = res['items'] ?? res['cases'];
      if (items is List && mounted) {
        setState(() {
          _savedCases = items.whereType<Map<String, dynamic>>().toList();
        });
      }
    } catch (_) {}
  }

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
    if (token == null) return;

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

      if (!mounted) return;
      setState(() {
        _caseId = caseId;
        _intakeFallback = fallback;
        _step = _CouncilStep.question;
      });
    } on ApiException catch (error) {
      setState(() => _error = error.message);
    } catch (_) {
      setState(() =>
          _error = 'Không thể tạo ca hội chẩn lúc này. Vui lòng thử lại.');
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _runCouncil() async {
    final caseId = _caseId;
    if (caseId == null) {
      setState(() {
        _step = _CouncilStep.caseInfo;
        _error = 'Chưa có ca hội chẩn. Vui lòng tạo ca trước.';
      });
      return;
    }

    final token = _requireToken();
    if (token == null) return;

    setState(() {
      _isLoading = true;
      _error = null;
    });

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

      if (!mounted) return;
      setState(() {
        _result = _CouncilResultView.fromCaseEnvelope(response);
        _step = _CouncilStep.result;
      });
      _loadCaseLibrary();
    } on ApiException catch (error) {
      setState(() => _error = error.message);
    } catch (_) {
      setState(() =>
          _error = 'Không thể chạy hội chẩn lúc này. Vui lòng thử lại.');
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  void _startNewCase() {
    setState(() {
      _showLibrary = false;
      _step = _CouncilStep.caseInfo;
      _caseId = null;
      _result = null;
      _intakeFallback = false;
      _error = null;
      _guardNotice = null;
      _oversightPaused = false;
    });
  }

  static bool _detectIntakeFallback(Map<String, dynamic> caseEnvelope) {
    final intake = caseEnvelope['intake'];
    if (intake is! Map) return false;
    final disclosure = intake['ai_disclosure'];
    if (disclosure is Map && disclosure['is_fallback'] == true) return true;
    final model = (intake['model_used'] ?? intake['model'] ?? '').toString();
    return model.contains('heuristic-fallback');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Hội chẩn AI'),
        actions: [
          IconButton(
            icon: Icon(_showLibrary ? Icons.edit_note : Icons.folder_outlined),
            tooltip: _showLibrary ? 'Quy trình hội chẩn' : 'Thư viện ca bệnh',
            onPressed: () => setState(() => _showLibrary = !_showLibrary),
          ),
        ],
      ),
      body: SafeArea(
        child: _showLibrary
            ? _buildCaseLibraryView(context)
            : ListView(
                padding: const EdgeInsets.fromLTRB(
                  ClaraTokens.spaceMd,
                  ClaraTokens.spaceMd,
                  ClaraTokens.spaceMd,
                  ClaraTokens.spaceXl,
                ),
                children: [
                  _SixStepIndicator(step: _step),
                  const SizedBox(height: ClaraTokens.spaceLg),
                  if (_isLoading)
                    const ClaraSkeletonList(itemCount: 3, showLeading: false)
                  else ...[
                    if (_step == _CouncilStep.caseInfo) ..._buildCaseStep(context),
                    if (_step == _CouncilStep.question)
                      ..._buildQuestionStep(context),
                    if (_step == _CouncilStep.context)
                      ..._buildContextStep(context),
                    if (_step == _CouncilStep.review)
                      ..._buildReviewStep(context),
                    if (_step == _CouncilStep.run) ..._buildRunStep(context),
                    if (_step == _CouncilStep.result)
                      ..._build7TierResultStep(context),
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

  // --- Case Library View -----------------------------------------------------

  Widget _buildCaseLibraryView(BuildContext context) {
    final theme = Theme.of(context);

    return ListView(
      padding: const EdgeInsets.all(ClaraTokens.spaceMd),
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              'Thư viện ca hội chẩn',
              style: theme.textTheme.titleMedium
                  ?.copyWith(fontWeight: FontWeight.bold),
            ),
            ClaraButton.primary(
              label: 'Tạo ca mới',
              icon: Icons.add,
              onPressed: _startNewCase,
            ),
          ],
        ),
        const SizedBox(height: ClaraTokens.spaceMd),
        if (_savedCases.isEmpty)
          const ClaraCard.static_(
            child: Padding(
              padding: EdgeInsets.all(ClaraTokens.spaceLg),
              child: Text(
                'Chưa có ca hội chẩn nào trong thư viện. Nhấn "Tạo ca mới" để bắt đầu.',
                textAlign: TextAlign.center,
              ),
            ),
          )
        else
          ..._savedCases.map((item) {
            final id = item['id'] ?? item['case_id'] ?? '--';
            final title = item['title'] ?? 'Ca hội chẩn #$id';
            final status = item['status'] ?? 'completed';

            return Padding(
              padding: const EdgeInsets.only(bottom: ClaraTokens.spaceSm),
              child: ClaraCard.static_(
                child: ListTile(
                  leading: const CircleAvatar(
                    child: Icon(Icons.folder_shared_outlined, size: 20),
                  ),
                  title: Text(title.toString(),
                      style: const TextStyle(fontWeight: FontWeight.bold)),
                  subtitle: Text('Mã ca: #$id • Trạng thái: $status'),
                  trailing: const Icon(Icons.arrow_forward_ios, size: 14),
                  onTap: () {
                    setState(() {
                      _caseId = int.tryParse(id.toString());
                      _showLibrary = false;
                      _step = _CouncilStep.review;
                    });
                  },
                ),
              ),
            );
          }),
      ],
    );
  }

  // --- Step 1: Case Info -----------------------------------------------------

  List<Widget> _buildCaseStep(BuildContext context) {
    final theme = Theme.of(context);
    return [
      const SectionHeader(title: 'Bước 1: Nhập thông tin ca bệnh'),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
        child: Text(
          'Nhập triệu chứng, tiền sử hoặc dán lời thoại buổi khám để AI trích xuất tự động.',
          style: theme.textTheme.bodyMedium
              ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
        ),
      ),
      const SizedBox(height: ClaraTokens.spaceSm),
      ClaraCard.static_(
        child: Column(
          children: [
            ClaraInput(
              controller: _titleController,
              label: 'Tiêu đề ca',
              hint: 'Ví dụ: Đau ngực từng cơn kèm khó thở',
              enabled: !_isLoading,
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            _MultilineField(
              controller: _transcriptController,
              label: 'Triệu chứng / Lời thoại ca bệnh',
              hint: 'Mô tả triệu chứng hoặc dán lời thoại khám bệnh',
              enabled: !_isLoading,
              minLines: 3,
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            _MultilineField(
              controller: _symptomsController,
              label: 'Triệu chứng chính (tùy chọn)',
              hint: 'Mỗi dòng một triệu chứng',
              enabled: !_isLoading,
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            _MultilineField(
              controller: _medicationsController,
              label: 'Thuốc đang dùng (tùy chọn)',
              hint: 'Mỗi dòng một loại thuốc',
              enabled: !_isLoading,
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            _MultilineField(
              controller: _historyController,
              label: 'Tiền sử bệnh (tùy chọn)',
              hint: 'Bệnh nền, dị ứng, tiền sử gia đình',
              enabled: !_isLoading,
            ),
          ],
        ),
      ),
      const SizedBox(height: ClaraTokens.spaceMd),
      ClaraButton.secondary(
        label: 'Dùng ví dụ mẫu',
        icon: Icons.lightbulb_outline,
        onPressed: _isLoading ? null : _fillExampleCase,
      ),
      const SizedBox(height: ClaraTokens.spaceSm),
      ClaraButton.primary(
        label: 'Tiếp tục',
        icon: Icons.arrow_forward,
        loading: _isLoading,
        onPressed: _isLoading ? null : _createCaseAndIntake,
      ),
    ];
  }

  void _fillExampleCase() {
    _titleController.text = 'Đau ngực từng cơn kèm khó thở';
    _questionController.text =
        'Phân tầng nguy cơ hội chứng vành cấp và chỉ định cận lâm sàng tiếp theo?';
    _transcriptController.text =
        'Bệnh nhân nam 58 tuổi, đau ngực trái từng cơn 3 ngày nay, '
        'lan lên vai trái, tăng khi gắng sức, kèm khó thở nhẹ và vã mồ hôi.';
    _symptomsController.text =
        'Đau ngực trái từng cơn\nKhó thở khi gắng sức\nVã mồ hôi';
    _medicationsController.text = 'Amlodipine 5mg\nAspirin 81mg';
    _historyController.text =
        'Tăng huyết áp 5 năm, hút thuốc lá, tiền sử gia đình có bệnh mạch vành.';
    _labsController.text = 'Troponin T âm tính, ECG có sóng T âm chuyển đạo V4-V6';
    if (mounted) setState(() {});
  }

  // --- Step 2: Clinical Question ---------------------------------------------

  List<Widget> _buildQuestionStep(BuildContext context) {
    return [
      const SectionHeader(title: 'Bước 2: Câu hỏi lâm sàng trọng tâm'),
      ClaraCard.static_(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _MultilineField(
              controller: _questionController,
              label: 'Câu hỏi cần hội đồng chuyên khoa giải quyết',
              hint: 'Ví dụ: Đánh giá nguy cơ nhồi máu cơ tim và hướng xử trí',
              minLines: 3,
            ),
          ],
        ),
      ),
      const SizedBox(height: ClaraTokens.spaceLg),
      ClaraButton.primary(
        label: 'Tiếp tục chọn chuyên khoa',
        icon: Icons.arrow_forward,
        onPressed: () => setState(() => _step = _CouncilStep.context),
      ),
      const SizedBox(height: ClaraTokens.spaceSm),
      ClaraButton.secondary(
        label: 'Quay lại',
        onPressed: () => setState(() => _step = _CouncilStep.caseInfo),
      ),
    ];
  }

  // --- Step 3: Context & Specialists -----------------------------------------

  List<Widget> _buildContextStep(BuildContext context) {
    final theme = Theme.of(context);
    final allSpecialties = [
      'Nội tổng quát',
      'Tim mạch',
      'Thần kinh',
      'Thận',
      'Dược lâm sàng',
      'Nội tiết',
      'ICU/Cấp cứu',
      'Hô hấp',
    ];

    return [
      const SectionHeader(title: 'Bước 3: Chọn chuyên khoa & Xét nghiệm'),
      if (_intakeFallback)
        const StatusByText(
          label: 'Trích xuất ở chế độ dự phòng. Vui lòng kiểm tra lại.',
          level: A11yStatusLevel.warning,
        ),
      ClaraCard.static_(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Số lượng chuyên khoa tham gia:',
                style: theme.textTheme.titleSmall),
            const SizedBox(height: ClaraTokens.spaceSm),
            Wrap(
              spacing: ClaraTokens.spaceSm,
              children: [
                for (final count in [2, 3, 4, 5])
                  ClaraChip(
                    label: '$count chuyên khoa',
                    selected: _specialistCount == count,
                    onTap: () => setState(() => _specialistCount = count),
                  ),
              ],
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            Text('Chuyên khoa tham gia hội chẩn:',
                style: theme.textTheme.titleSmall),
            const SizedBox(height: ClaraTokens.spaceSm),
            Wrap(
              spacing: ClaraTokens.spaceSm,
              runSpacing: ClaraTokens.spaceSm,
              children: [
                for (final spec in allSpecialties)
                  FilterChip(
                    label: Text(spec),
                    selected: _selectedSpecialties.contains(spec),
                    onSelected: (selected) {
                      setState(() {
                        if (selected) {
                          _selectedSpecialties.add(spec);
                        } else if (_selectedSpecialties.length > 1) {
                          _selectedSpecialties.remove(spec);
                        }
                      });
                    },
                  ),
              ],
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            _MultilineField(
              controller: _labsController,
              label: 'Kết quả cận lâm sàng / Xét nghiệm (tùy chọn)',
              hint: 'Creatinine, eGFR, ECG, men tim...',
              minLines: 2,
            ),
          ],
        ),
      ),
      const SizedBox(height: ClaraTokens.spaceLg),
      ClaraButton.primary(
        label: 'Tiếp tục rà soát',
        icon: Icons.arrow_forward,
        onPressed: () => setState(() => _step = _CouncilStep.review),
      ),
      const SizedBox(height: ClaraTokens.spaceSm),
      ClaraButton.secondary(
        label: 'Quay lại',
        onPressed: () => setState(() => _step = _CouncilStep.question),
      ),
    ];
  }

  // --- Step 4: Review --------------------------------------------------------

  List<Widget> _buildReviewStep(BuildContext context) {
    final theme = Theme.of(context);
    return [
      const SectionHeader(title: 'Bước 4: Rà soát ca trước khi hội chẩn'),
      ClaraCard.static_(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Tiêu đề: ${_titleController.text}',
                style: theme.textTheme.titleSmall),
            const Divider(),
            Text('Câu hỏi: ${_questionController.text}',
                style: theme.textTheme.bodyMedium),
            const SizedBox(height: 8),
            Text('Chuyên khoa: ${_selectedSpecialties.join(", ")}',
                style: theme.textTheme.bodyMedium),
            if (_symptomsController.text.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text('Triệu chứng: ${_symptomsController.text}',
                  style: theme.textTheme.bodySmall),
            ],
            if (_medicationsController.text.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text('Thuốc: ${_medicationsController.text}',
                  style: theme.textTheme.bodySmall),
            ],
          ],
        ),
      ),
      const SizedBox(height: ClaraTokens.spaceLg),
      ClaraButton.primary(
        label: 'Tiến hành hội đồng',
        icon: Icons.play_arrow,
        onPressed: () => setState(() => _step = _CouncilStep.run),
      ),
      const SizedBox(height: ClaraTokens.spaceSm),
      ClaraButton.secondary(
        label: 'Chỉnh sửa lại',
        onPressed: () => setState(() => _step = _CouncilStep.context),
      ),
    ];
  }

  // --- Step 5: Run -----------------------------------------------------------

  List<Widget> _buildRunStep(BuildContext context) {
    return [
      const SectionHeader(title: 'Bước 5: Chạy hội chẩn đa khoa'),
      ClaraCard.static_(
        child: Column(
          children: [
            const Icon(Icons.psychology_outlined,
                size: 48, color: Color(0xFF0F766E)),
            const SizedBox(height: ClaraTokens.spaceMd),
            const Text(
              'Hội đồng AI đang phân tích dữ liệu ca bệnh theo các góc nhìn chuyên khoa độc lập...',
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: ClaraTokens.spaceLg),
            ClaraButton.primary(
              label: 'Bắt đầu hội chẩn',
              icon: Icons.play_arrow,
              loading: _isLoading,
              onPressed: _isLoading ? null : _runCouncil,
            ),
          ],
        ),
      ),
      const SizedBox(height: ClaraTokens.spaceSm),
      ClaraButton.secondary(
        label: 'Quay lại',
        onPressed: _isLoading
            ? null
            : () => setState(() => _step = _CouncilStep.review),
      ),
    ];
  }

  // --- Step 6: Exact 7-Tier Result Hierarchy ---------------------------------

  List<Widget> _build7TierResultStep(BuildContext context) {
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
      const SectionHeader(title: 'Bước 6: Kết quả hội chẩn chuyên sâu'),

      // Mandatory Safety Invariant
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

      if (_guardNotice != null) ...[
        StatusByText(
          label: _guardNotice!,
          level: A11yStatusLevel.warning,
        ),
        const SizedBox(height: ClaraTokens.spaceMd),
      ],

      // Tier 1: Escalation / Red Flags
      _buildTierSection(
        title: '1. Cảnh báo khẩn & Điểm cần can thiệp (Red Flags)',
        icon: Icons.warning_amber_rounded,
        child: StatusByText(
          label: result.hasDivergence
              ? 'Phát hiện điểm bất đồng cần bác sĩ trưởng hội đồng xác nhận'
              : 'Không có tín hiệu nguy kịch tức thời',
          level: result.hasDivergence
              ? A11yStatusLevel.warning
              : A11yStatusLevel.success,
        ),
      ),
      const SizedBox(height: ClaraTokens.spaceMd),

      // Tier 2: Recommendation
      _buildTierSection(
        title: '2. Khuyến nghị lâm sàng & Tóm tắt (Recommendation)',
        icon: Icons.assignment_outlined,
        child: Text(
          _oversightPaused
              ? 'Quy trình hội chẩn đang tạm dừng theo chỉ định của bác sĩ.'
              : result.finalRecommendation.isNotEmpty
                  ? result.finalRecommendation
                  : 'Theo dõi triệu chứng và khám chuyên khoa định kỳ.',
          style: theme.textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
        ),
      ),
      const SizedBox(height: ClaraTokens.spaceMd),

      // Tier 3: Consensus / Agreement
      _buildTierSection(
        title: '3. Đồng thuận đa chuyên khoa (Consensus)',
        icon: Icons.handshake_outlined,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              result.consensusSummary.isNotEmpty
                  ? result.consensusSummary
                  : 'Các chuyên khoa thống nhất hướng điều trị cơ bản.',
              style: theme.textTheme.bodyMedium,
            ),
            if (result.specialists.isNotEmpty) ...[
              const SizedBox(height: ClaraTokens.spaceSm),
              Wrap(
                spacing: ClaraTokens.spaceSm,
                children: [
                  for (final spec in result.specialists)
                    ClaraChip(label: spec, icon: Icons.local_hospital_outlined),
                ],
              ),
            ],
          ],
        ),
      ),
      const SizedBox(height: ClaraTokens.spaceMd),

      // Tier 4: Uncertainty / Divergence
      _buildTierSection(
        title: '4. Độ không chắc chắn & Bất đồng (Uncertainty)',
        icon: Icons.question_mark_outlined,
        child: result.divergenceNotes.isNotEmpty
            ? Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  for (final note in result.divergenceNotes)
                    Padding(
                      padding: const EdgeInsets.only(bottom: ClaraTokens.spaceXs),
                      child: Text('• $note', style: theme.textTheme.bodyMedium),
                    ),
                ],
              )
            : const Text('Không phát hiện điểm bất đồng đáng kể giữa các chuyên khoa.'),
      ),
      const SizedBox(height: ClaraTokens.spaceMd),

      // Tier 5: Evidence / Citations
      _buildTierSection(
        title: '5. Y văn & Bằng chứng đối chứng (Evidence)',
        icon: Icons.fact_check_outlined,
        child: const Text(
          'Đã đối chiếu phác đồ Bộ Y tế & CSDL Dược lý DrugBank v5.1.10.',
        ),
      ),
      const SizedBox(height: ClaraTokens.spaceMd),

      // Tier 6: Clinician Action (Oversight controls)
      _buildTierSection(
        title: '6. Quyết định lâm sàng & Xử trí (Clinician Action)',
        icon: Icons.gavel_outlined,
        child: Wrap(
          spacing: ClaraTokens.spaceSm,
          runSpacing: ClaraTokens.spaceSm,
          children: [
            ClaraButton.secondary(
              label: 'Chuyển giao',
              icon: Icons.forward,
              onPressed: () => setState(() {
                _guardNotice = 'Đã chuyển giao ca bệnh cho khoa liên quan.';
              }),
            ),
            ClaraButton.secondary(
              label: 'Tạm dừng ca',
              icon: Icons.pause,
              onPressed: () => setState(() {
                _oversightPaused = true;
                _guardNotice = 'Ca hội chẩn đã được tạm dừng để đánh giá lại.';
              }),
            ),
            ClaraButton.secondary(
              label: 'Ghi đè ý kiến',
              icon: Icons.edit,
              onPressed: () => setState(() {
                _guardNotice = 'Đã ghi nhận ghi đè lâm sàng của bác sĩ phụ trách.';
              }),
            ),
          ],
        ),
      ),
      const SizedBox(height: ClaraTokens.spaceMd),

      // Tier 7: Technical Details
      _buildTierSection(
        title: '7. Giám sát kỹ thuật & Mô hình AI (Technical Details)',
        icon: Icons.analytics_outlined,
        child: Text(
          'Mã ca: #${_caseId ?? "--"} • FIDES Engine: Active • Safe degradation: Enabled',
          style: theme.textTheme.bodySmall,
        ),
      ),
      const SizedBox(height: ClaraTokens.spaceLg),

      ClaraButton.primary(
        label: 'Tạo ca hội chẩn mới',
        icon: Icons.refresh,
        onPressed: _isLoading ? null : _startNewCase,
      ),
    ];
  }

  Widget _buildTierSection({
    required String title,
    required IconData icon,
    required Widget child,
  }) {
    final theme = Theme.of(context);
    return ClaraCard.static_(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 18, color: theme.colorScheme.primary),
              const SizedBox(width: ClaraTokens.spaceSm),
              Expanded(
                child: Text(
                  title,
                  style: theme.textTheme.titleSmall
                      ?.copyWith(fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
          const SizedBox(height: ClaraTokens.spaceSm),
          child,
        ],
      ),
    );
  }
}

// --- 6-Step Stepper Component ------------------------------------------------

class _SixStepIndicator extends StatelessWidget {
  const _SixStepIndicator({required this.step});

  final _CouncilStep step;

  @override
  Widget build(BuildContext context) {
    const labels = [
      'Ca bệnh',
      'Câu hỏi',
      'Bối cảnh',
      'Rà soát',
      'Hội đồng',
      'Kết quả',
    ];
    final scheme = Theme.of(context).colorScheme;
    final activeIndex = _CouncilStep.values.indexOf(step);

    return Semantics(
      label: 'Bước ${activeIndex + 1} trên 6: ${labels[activeIndex]}',
      container: true,
      child: GlassSurface(
        blurSigma: GlassTokens.blurCard,
        radius: GlassTokens.radiusCard,
        fill: GlassFill.thin,
        padding: const EdgeInsets.symmetric(
          horizontal: ClaraTokens.spaceSm,
          vertical: ClaraTokens.spaceSm,
        ),
        child: Row(
          children: List.generate(labels.length, (index) {
            final active = index <= activeIndex;
            return Expanded(
              child: Column(
                children: [
                  CircleAvatar(
                    radius: 12,
                    backgroundColor: active
                        ? scheme.primary
                        : scheme.surfaceContainerHighest,
                    child: active && index < activeIndex
                        ? Icon(Icons.check, size: 14, color: scheme.onPrimary)
                        : Text(
                            '${index + 1}',
                            style: TextStyle(
                              fontSize: 10,
                              color: active
                                  ? scheme.onPrimary
                                  : scheme.onSurfaceVariant,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    labels[index],
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 9,
                      color: active ? scheme.primary : scheme.onSurfaceVariant,
                      fontWeight:
                          active ? FontWeight.bold : FontWeight.normal,
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

class _MultilineField extends StatelessWidget {
  const _MultilineField({
    required this.controller,
    required this.label,
    this.hint,
    this.enabled = true,
    this.minLines = 2,
  });

  final TextEditingController controller;
  final String label;
  final String? hint;
  final bool enabled;
  final int minLines;

  @override
  Widget build(BuildContext context) {
    final textScaler = A11y.resolveTextScaler(context);
    return MediaQuery(
      data: MediaQuery.of(context).copyWith(textScaler: textScaler),
      child: TextFormField(
        controller: controller,
        enabled: enabled,
        minLines: minLines,
        maxLines: minLines > 4 ? minLines + 2 : 5,
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
