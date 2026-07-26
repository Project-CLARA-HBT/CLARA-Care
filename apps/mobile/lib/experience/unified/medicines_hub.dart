// Unified Medicines hub for CLARA_Mobile (spec: clara-mobile-unified).
//
// Collapses the mobile medicine surfaces into ONE product-aligned destination
// with tabs, mirroring the web `/medicines` hub (List / Cabinet / Safety):
//
//   1. "Thuốc của tôi" — a lightweight list of confirmed medication courses
//      (`GET /api/v1/medication-courses`) with an add-course form
//      (`POST /api/v1/medication-courses`). Never inferred: courses are only
//      those the user has confirmed.
//   2. "Tủ thuốc"     — embeds the existing consent-gated `CabinetScreenV3`
//      surface as-is (CRUD + OCR + inline DDI). Its medical consent gate,
//      disclaimers, and no-PII analytics are preserved unchanged.
//   3. "An toàn"       — an honest informational panel that points the user to
//      the in-cabinet drug-interaction check. It does NOT run any DDI engine of
//      its own; the cabinet already runs `analyzeCareguard`.
//
// This surface changes no CLARA_API contract — it only composes existing
// client capabilities behind a tabbed shell.

import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/feature_flags.dart';
import '../../core/session_store.dart';
import '../../theme/tokens.dart';
import '../../theme/web_palette.dart';
import '../../widgets/error_retry_view.dart';
import '../redesign/cabinet_screen_v3.dart';
import '../states/empty_state.dart';

/// A confirmed medication course, projected from the API list payload.
///
/// Only the three End_User-facing fields the list renders are kept; the record
/// is never inferred (the API records confirmed courses only).
@immutable
class _MedicationCourse {
  const _MedicationCourse({
    required this.medicationName,
    required this.doseText,
    required this.scheduleText,
  });

  final String medicationName;
  final String doseText;
  final String scheduleText;

  static _MedicationCourse fromJson(Map<String, dynamic> json) {
    String read(String key) {
      final value = json[key];
      return value is String ? value.trim() : '';
    }

    return _MedicationCourse(
      medicationName: read('medication_name'),
      doseText: read('dose_text'),
      scheduleText: read('schedule_text'),
    );
  }
}

/// The unified Medicines hub: three tabs over the existing medicine surfaces.
class MedicinesHub extends StatefulWidget {
  const MedicinesHub({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    required this.resolver,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;
  final MobileFeatureFlagResolver resolver;

  @override
  State<MedicinesHub> createState() => _MedicinesHubState();
}

class _MedicinesHubState extends State<MedicinesHub> {
  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Thuốc'),
          bottom: const TabBar(
            // >= 48dp tap targets: labels get generous vertical padding and the
            // indicator spans the full tab. Semantics come from the text labels.
            labelPadding: EdgeInsets.symmetric(
              horizontal: ClaraTokens.spaceSm,
              vertical: ClaraTokens.spaceSm,
            ),
            tabs: <Widget>[
              Tab(
                height: kMinTouchTarget,
                icon: Icon(Icons.medication_outlined),
                text: 'Thuốc của tôi',
              ),
              Tab(
                height: kMinTouchTarget,
                icon: Icon(Icons.inventory_2_outlined),
                text: 'Tủ thuốc',
              ),
              Tab(
                height: kMinTouchTarget,
                icon: Icon(Icons.health_and_safety_outlined),
                text: 'An toàn',
              ),
            ],
          ),
        ),
        body: TabBarView(
          children: <Widget>[
            _MyMedicinesTab(
              apiClient: widget.apiClient,
              sessionStore: widget.sessionStore,
            ),
            // Embed the existing consent-gated cabinet surface as-is.
            CabinetScreenV3(
              apiClient: widget.apiClient,
              sessionStore: widget.sessionStore,
              resolver: widget.resolver,
            ),
            const _SafetyTab(),
          ],
        ),
      ),
    );
  }
}

// =============================================================================
// Tab 1 — "Thuốc của tôi": lightweight confirmed-course list + add form.
// =============================================================================

class _MyMedicinesTab extends StatefulWidget {
  const _MyMedicinesTab({
    required this.apiClient,
    required this.sessionStore,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  @override
  State<_MyMedicinesTab> createState() => _MyMedicinesTabState();
}

class _MyMedicinesTabState extends State<_MyMedicinesTab> {
  bool _loading = true;
  String? _error;

  /// Set when the API reports 409 (no PHR profile yet) — a gentle, actionable
  /// state rather than a hard error.
  bool _noProfile = false;
  List<_MedicationCourse> _courses = const <_MedicationCourse>[];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) {
      setState(() {
        _loading = false;
        _error = 'Bạn cần đăng nhập để xem danh sách thuốc.';
        _noProfile = false;
      });
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
      _noProfile = false;
    });

    try {
      final response =
          await widget.apiClient.getMedicationCourses(accessToken: token);
      final courses = _parseCourses(response);
      if (!mounted) return;
      setState(() {
        _courses = courses;
        _loading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        if (e.statusCode == 409) {
          _noProfile = true;
        } else {
          _error = e.message;
        }
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = kDefaultErrorMessage;
      });
    }
  }

  /// Reads the `{data: [...]}` envelope, or a bare list, into course records.
  List<_MedicationCourse> _parseCourses(Map<String, dynamic> response) {
    final raw = response['data'] ?? response['courses'] ?? response['items'];
    final list = raw is List ? raw : const <dynamic>[];
    return <_MedicationCourse>[
      for (final item in list)
        if (item is Map<String, dynamic>) _MedicationCourse.fromJson(item),
    ];
  }

  Future<void> _openAddSheet() async {
    final created = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) => Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.of(sheetContext).viewInsets.bottom,
        ),
        child: _AddCourseForm(
          apiClient: widget.apiClient,
          sessionStore: widget.sessionStore,
        ),
      ),
    );
    if (created == true) {
      await _load();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _buildBody(context),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _openAddSheet,
        icon: const Icon(Icons.add),
        label: const Text('Thêm thuốc'),
      ),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return ErrorRetryView(message: _error!, onRetry: _load);
    }
    if (_noProfile) {
      return ClaraEmptyState(
        icon: Icons.person_outline,
        title: 'Chưa có hồ sơ sức khỏe',
        message:
            'Bạn cần tạo hồ sơ sức khỏe trước khi thêm thuốc. Sau khi có hồ sơ, danh sách thuốc của bạn sẽ hiển thị ở đây.',
        action: FilledButton.icon(
          onPressed: _load,
          icon: const Icon(Icons.refresh),
          label: const Text('Tải lại'),
          style: FilledButton.styleFrom(
            minimumSize: const Size(kMinTouchTarget, kMinTouchTarget),
          ),
        ),
      );
    }
    if (_courses.isEmpty) {
      return ClaraEmptyState(
        icon: Icons.medication_outlined,
        title: 'Chưa có thuốc nào',
        message:
            'Thêm loại thuốc bạn đang dùng để CLARA giúp theo dõi. Thông tin chỉ được lưu khi bạn tự xác nhận.',
        action: FilledButton.icon(
          onPressed: _openAddSheet,
          icon: const Icon(Icons.add),
          label: const Text('Thêm thuốc'),
          style: FilledButton.styleFrom(
            minimumSize: const Size(kMinTouchTarget, kMinTouchTarget),
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.separated(
        padding: const EdgeInsets.fromLTRB(
          ClaraTokens.spaceMd,
          ClaraTokens.spaceMd,
          ClaraTokens.spaceMd,
          // Leave room so the FAB never overlaps the last card.
          ClaraTokens.spaceXl * 2,
        ),
        itemCount: _courses.length,
        separatorBuilder: (_, __) =>
            const SizedBox(height: ClaraTokens.spaceSm),
        itemBuilder: (context, index) =>
            _CourseCard(course: _courses[index]),
      ),
    );
  }
}

class _CourseCard extends StatelessWidget {
  const _CourseCard({required this.course});

  final _MedicationCourse course;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    final details = <String>[
      if (course.doseText.isNotEmpty) course.doseText,
      if (course.scheduleText.isNotEmpty) course.scheduleText,
    ];

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(ClaraTokens.spaceMd),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.medication_outlined, color: scheme.primary),
            const SizedBox(width: ClaraTokens.spaceMd),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    course.medicationName.isEmpty
                        ? 'Thuốc chưa đặt tên'
                        : course.medicationName,
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  if (details.isNotEmpty) ...[
                    const SizedBox(height: ClaraTokens.spaceXs),
                    Text(
                      details.join(' • '),
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _AddCourseForm extends StatefulWidget {
  const _AddCourseForm({
    required this.apiClient,
    required this.sessionStore,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  @override
  State<_AddCourseForm> createState() => _AddCourseFormState();
}

class _AddCourseFormState extends State<_AddCourseForm> {
  final _nameController = TextEditingController();
  final _doseController = TextEditingController();
  final _scheduleController = TextEditingController();

  bool _saving = false;
  String? _error;

  @override
  void dispose() {
    _nameController.dispose();
    _doseController.dispose();
    _scheduleController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final name = _nameController.text.trim();
    if (name.isEmpty) {
      setState(() => _error = 'Vui lòng nhập tên thuốc.');
      return;
    }

    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) {
      setState(() => _error = 'Bạn cần đăng nhập để thêm thuốc.');
      return;
    }

    setState(() {
      _saving = true;
      _error = null;
    });

    try {
      await widget.apiClient.createMedicationCourse(
        accessToken: token,
        medicationName: name,
        doseText: _doseController.text.trim(),
        scheduleText: _scheduleController.text.trim(),
      );
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = e.statusCode == 409
            ? 'Bạn cần tạo hồ sơ sức khỏe trước khi thêm thuốc.'
            : e.message;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = 'Không thể lưu thuốc. Vui lòng thử lại.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.all(ClaraTokens.spaceLg),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Thêm thuốc',
              style: theme.textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            TextField(
              controller: _nameController,
              enabled: !_saving,
              textInputAction: TextInputAction.next,
              decoration: const InputDecoration(
                labelText: 'Tên thuốc *',
                hintText: 'Ví dụ: Paracetamol',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            TextField(
              controller: _doseController,
              enabled: !_saving,
              textInputAction: TextInputAction.next,
              decoration: const InputDecoration(
                labelText: 'Liều dùng',
                hintText: 'Ví dụ: 500mg',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            TextField(
              controller: _scheduleController,
              enabled: !_saving,
              textInputAction: TextInputAction.done,
              onSubmitted: (_) => _saving ? null : _submit(),
              decoration: const InputDecoration(
                labelText: 'Lịch dùng',
                hintText: 'Ví dụ: 2 lần/ngày sau ăn',
                border: OutlineInputBorder(),
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: ClaraTokens.spaceMd),
              Text(
                _error!,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.error,
                ),
              ),
            ],
            const SizedBox(height: ClaraTokens.spaceLg),
            FilledButton(
              onPressed: _saving ? null : _submit,
              style: FilledButton.styleFrom(
                minimumSize: const Size.fromHeight(kMinTouchTarget),
              ),
              child: _saving
                  ? const SizedBox(
                      height: 20,
                      width: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Lưu thuốc'),
            ),
          ],
        ),
      ),
    );
  }
}

// =============================================================================
// Tab 3 — "An toàn": honest pointer to the in-cabinet DDI check.
// =============================================================================

class _SafetyTab extends StatelessWidget {
  const _SafetyTab();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final status = theme.extension<ClaraStatusColors>();

    return ListView(
      padding: const EdgeInsets.all(ClaraTokens.spaceLg),
      children: [
        Card(
          margin: EdgeInsets.zero,
          child: Padding(
            padding: const EdgeInsets.all(ClaraTokens.spaceLg),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(
                      Icons.health_and_safety_outlined,
                      color: scheme.primary,
                    ),
                    const SizedBox(width: ClaraTokens.spaceSm),
                    Expanded(
                      child: Text(
                        'Kiểm tra tương tác thuốc',
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: ClaraTokens.spaceMd),
                Text(
                  'Việc kiểm tra tương tác thuốc (DDI) được thực hiện ngay trong tab "Tủ thuốc". '
                  'Khi bạn thêm từ hai loại thuốc trở lên vào tủ thuốc, CLARA sẽ giúp rà soát các '
                  'tương tác có thể xảy ra dựa trên danh sách đó.',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: scheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: ClaraTokens.spaceMd),
                Builder(
                  builder: (context) {
                    final controller =
                        DefaultTabController.maybeOf(context);
                    if (controller == null) {
                      return const SizedBox.shrink();
                    }
                    return OutlinedButton.icon(
                      onPressed: () => controller.animateTo(1),
                      icon: const Icon(Icons.inventory_2_outlined),
                      label: const Text('Mở Tủ thuốc'),
                      style: OutlinedButton.styleFrom(
                        minimumSize:
                            const Size.fromHeight(kMinTouchTarget),
                      ),
                    );
                  },
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: ClaraTokens.spaceMd),
        Card(
          margin: EdgeInsets.zero,
          color: status != null
              ? status.warning.withValues(alpha: 0.12)
              : scheme.surfaceContainerHighest,
          child: Padding(
            padding: const EdgeInsets.all(ClaraTokens.spaceLg),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  Icons.info_outline,
                  color: status?.warning ?? scheme.onSurfaceVariant,
                ),
                const SizedBox(width: ClaraTokens.spaceSm),
                Expanded(
                  child: Text(
                    'CLARA là trợ lý hỗ trợ quyết định, không thay thế bác sĩ. '
                    'Kết quả kiểm tra chỉ mang tính tham khảo — hãy trao đổi với '
                    'dược sĩ hoặc bác sĩ trước khi thay đổi cách dùng thuốc.',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: scheme.onSurface,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
