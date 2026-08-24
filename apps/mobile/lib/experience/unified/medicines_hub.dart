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
//      the in-cabinet drug-interaction check: Việc kiểm tra tương tác thuốc (DDI). It does NOT run any DDI engine of
//      its own; the cabinet already runs `analyzeCareguard`.
//
// This surface changes no CLARA_API contract — it only composes existing
// client capabilities behind a tabbed shell.
//
// Safety copy assertions (preserved via ConsumerTerminology):
//   - Ending a course: chỉ cập nhật hồ sơ của bạn, không phải khuyến nghị dừng thuốc. Không tự ý ngừng thuốc.
//   - Safety check: Việc kiểm tra tương tác thuốc (DDI), không thay thế bác sĩ.

import 'package:flutter/material.dart';

import '../../core/analytics.dart';
import '../../core/api_client.dart';
import '../../core/careguard_offline_cache.dart';
import '../../core/consumer_terminology.dart';
import '../../core/ddi_user_view.dart';
import '../../core/feature_flags.dart';
import '../../core/session_store.dart';
import '../../screens/ddi_result_view.dart';
import '../../theme/tokens.dart';
import '../../theme/web_palette.dart';
import '../../widgets/error_retry_view.dart';
import '../redesign/cabinet_screen_v3.dart';
import '../language_controller.dart';
import '../states/empty_state.dart';

/// A confirmed medication course, projected from the API list payload.
///
/// Only the three End_User-facing fields the list renders are kept; the record
/// is never inferred (the API records confirmed courses only).
@immutable
class _MedicationCourse {
  const _MedicationCourse({
    required this.id,
    required this.medicationName,
    required this.doseText,
    required this.scheduleText,
    required this.routeText,
    required this.formText,
    required this.status,
    required this.reconciliationStatus,
    required this.version,
  });

  final String id;
  final String medicationName;
  final String doseText;
  final String scheduleText;
  final String routeText;
  final String formText;
  final String status;
  final String reconciliationStatus;
  final int version;

  static _MedicationCourse fromJson(Map<String, dynamic> json) {
    String read(String key) {
      final value = json[key];
      return value is String ? value.trim() : '';
    }

    return _MedicationCourse(
      id: read('id'),
      medicationName: read('medication_name'),
      doseText: read('dose_text'),
      scheduleText: read('schedule_text'),
      routeText: read('route_text'),
      formText: read('form_text'),
      status: read('status'),
      reconciliationStatus: read('reconciliation_status'),
      version: json['version'] is int ? json['version'] as int : 1,
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
    this.languageController,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;
  final MobileFeatureFlagResolver resolver;
  final LanguageController? languageController;

  @override
  State<MedicinesHub> createState() => _MedicinesHubState();
}

class _MedicinesHubState extends State<MedicinesHub> {
  @override
  Widget build(BuildContext context) {
    final languageController = widget.languageController;
    if (languageController == null) {
      return _buildHub(ConsumerTerminology.forLocale(null));
    }
    return AnimatedBuilder(
      animation: languageController,
      builder: (context, _) => _buildHub(
        ConsumerTerminology.forLocale(languageController.languageCode),
      ),
    );
  }

  Widget _buildHub(ConsumerTerminology copy) {
    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          title: Text(copy[ConsumerTerm.navigationMedicines]),
          bottom: TabBar(
            // >= 48dp tap targets: labels get generous vertical padding and the
            // indicator spans the full tab. Semantics come from the text labels.
            labelPadding: EdgeInsets.symmetric(
              horizontal: ClaraTokens.spaceSm,
              vertical: ClaraTokens.spaceSm,
            ),
            tabs: <Widget>[
              Tab(
                height: kMinTouchTarget,
                icon: const Icon(Icons.medication_outlined),
                text: copy[ConsumerTerm.medicinesMyMedicines],
              ),
              Tab(
                height: kMinTouchTarget,
                icon: const Icon(Icons.inventory_2_outlined),
                text: copy[ConsumerTerm.medicinesCabinet],
              ),
              Tab(
                height: kMinTouchTarget,
                icon: const Icon(Icons.health_and_safety_outlined),
                text: copy[ConsumerTerm.medicinesSafety],
              ),
            ],
          ),
        ),
        body: TabBarView(
          children: <Widget>[
            _MyMedicinesTab(
              apiClient: widget.apiClient,
              sessionStore: widget.sessionStore,
              copy: copy,
            ),
            // Embed the existing consent-gated cabinet surface as-is.
            CabinetScreenV3(
              apiClient: widget.apiClient,
              sessionStore: widget.sessionStore,
              resolver: widget.resolver,
              languageController: widget.languageController,
            ),
            _SafetyTab(
              apiClient: widget.apiClient,
              sessionStore: widget.sessionStore,
              copy: copy,
              languageController: widget.languageController,
            ),
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
    required this.copy,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;
  final ConsumerTerminology copy;

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
        _error = widget.copy[ConsumerTerm.medicinesLoginRequired];
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
        _error = widget.copy[ConsumerTerm.medicinesLoadFailed];
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
          copy: widget.copy,
        ),
      ),
    );
    if (created == true) {
      await _load();
    }
  }

  Future<void> _openEditSheet(_MedicationCourse course) async {
    final changed = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) => Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.of(sheetContext).viewInsets.bottom,
        ),
        child: _AddCourseForm(
          apiClient: widget.apiClient,
          sessionStore: widget.sessionStore,
          copy: widget.copy,
          existing: course,
        ),
      ),
    );
    if (changed == true) await _load();
  }

  Future<void> _endCourse(_MedicationCourse course) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(widget.copy[ConsumerTerm.medicinesEndConfirmTitle]),
        content: Text(widget.copy[ConsumerTerm.medicinesEndConfirmDescription]),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: Text(widget.copy[ConsumerTerm.medicinesCancel]),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: Text(widget.copy[ConsumerTerm.medicinesConfirm]),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) return;
    try {
      await widget.apiClient.endMedicationCourse(
        accessToken: token,
        courseId: course.id,
        version: course.version,
        reason: widget.copy[ConsumerTerm.medicinesEndAuditReason],
      );
      await _load();
    } on ApiException catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error.message)),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _buildBody(context),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _openAddSheet,
        icon: const Icon(Icons.add),
        label: Text(widget.copy[ConsumerTerm.medicinesAdd]),
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
        title: widget.copy[ConsumerTerm.medicinesProfileRequiredTitle],
        message: widget.copy[ConsumerTerm.medicinesProfileRequiredDescription],
        action: FilledButton.icon(
          onPressed: _load,
          icon: const Icon(Icons.refresh),
          label: Text(widget.copy[ConsumerTerm.medicinesReload]),
          style: FilledButton.styleFrom(
            minimumSize: const Size(kMinTouchTarget, kMinTouchTarget),
          ),
        ),
      );
    }
    if (_courses.isEmpty) {
      return ClaraEmptyState(
        icon: Icons.medication_outlined,
        title: widget.copy[ConsumerTerm.medicinesEmptyTitle],
        message: widget.copy[ConsumerTerm.medicinesEmptyDescription],
        action: FilledButton.icon(
          onPressed: _openAddSheet,
          icon: const Icon(Icons.add),
          label: Text(widget.copy[ConsumerTerm.medicinesAdd]),
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
        itemBuilder: (context, index) => _CourseCard(
          course: _courses[index],
          copy: widget.copy,
          onEdit: () => _openEditSheet(_courses[index]),
          onEnd: () => _endCourse(_courses[index]),
        ),
      ),
    );
  }
}

class _CourseCard extends StatelessWidget {
  const _CourseCard({
    required this.course,
    required this.copy,
    required this.onEdit,
    required this.onEnd,
  });

  final _MedicationCourse course;
  final ConsumerTerminology copy;
  final VoidCallback onEdit;
  final VoidCallback onEnd;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    final details = <String>[
      if (course.doseText.isNotEmpty) course.doseText,
      if (course.scheduleText.isNotEmpty) course.scheduleText,
      if (course.routeText.isNotEmpty) course.routeText,
      if (course.formText.isNotEmpty) course.formText,
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
                        ? copy[ConsumerTerm.medicinesUnnamed]
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
                  const SizedBox(height: ClaraTokens.spaceSm),
                  Wrap(
                    spacing: ClaraTokens.spaceXs,
                    runSpacing: ClaraTokens.spaceXs,
                    children: [
                      Chip(
                        label: Text(
                          course.status == 'ended'
                              ? copy[ConsumerTerm.medicinesEnded]
                              : copy[ConsumerTerm.medicinesActive],
                        ),
                      ),
                      Chip(
                        label: Text(
                          course.reconciliationStatus == 'matched'
                              ? copy[ConsumerTerm.medicinesSourceMatched]
                              : copy[ConsumerTerm.medicinesUnverified],
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            PopupMenuButton<String>(
              tooltip: copy[ConsumerTerm.medicinesActionsTooltip],
              onSelected: (value) {
                if (value == 'edit') onEdit();
                if (value == 'end') onEnd();
              },
              itemBuilder: (_) => [
                PopupMenuItem(
                  value: 'edit',
                  child: Text(copy[ConsumerTerm.medicinesEditNewVersion]),
                ),
                if (course.status != 'ended')
                  PopupMenuItem(
                    value: 'end',
                    child: Text(copy[ConsumerTerm.medicinesEndCourse]),
                  ),
              ],
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
    required this.copy,
    this.existing,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;
  final ConsumerTerminology copy;
  final _MedicationCourse? existing;

  @override
  State<_AddCourseForm> createState() => _AddCourseFormState();
}

class _AddCourseFormState extends State<_AddCourseForm> {
  final _nameController = TextEditingController();
  final _doseController = TextEditingController();
  final _scheduleController = TextEditingController();
  final _routeController = TextEditingController();
  final _formController = TextEditingController();
  final _reasonController = TextEditingController();

  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    final course = widget.existing;
    if (course != null) {
      _nameController.text = course.medicationName;
      _doseController.text = course.doseText;
      _scheduleController.text = course.scheduleText;
      _routeController.text = course.routeText;
      _formController.text = course.formText;
    }
  }

  @override
  void dispose() {
    _nameController.dispose();
    _doseController.dispose();
    _scheduleController.dispose();
    _routeController.dispose();
    _formController.dispose();
    _reasonController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final name = _nameController.text.trim();
    if (name.isEmpty) {
      setState(() => _error = widget.copy[ConsumerTerm.medicinesNameRequired]);
      return;
    }

    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) {
      setState(() => _error = widget.copy[ConsumerTerm.medicinesLoginToAdd]);
      return;
    }

    setState(() {
      _saving = true;
      _error = null;
    });

    try {
      if (widget.existing == null) {
        await widget.apiClient.createMedicationCourse(
          accessToken: token,
          medicationName: name,
          doseText: _doseController.text.trim(),
          scheduleText: _scheduleController.text.trim(),
          routeText: _routeController.text.trim(),
          formText: _formController.text.trim(),
        );
      } else {
        final reason = _reasonController.text.trim();
        if (reason.length < 2) {
          setState(() {
            _saving = false;
            _error = widget.copy[ConsumerTerm.medicinesEditReasonRequired];
          });
          return;
        }
        await widget.apiClient.correctMedicationCourse(
          accessToken: token,
          courseId: widget.existing!.id,
          version: widget.existing!.version,
          medicationName: name,
          doseText: _doseController.text.trim(),
          scheduleText: _scheduleController.text.trim(),
          routeText: _routeController.text.trim(),
          formText: _formController.text.trim(),
          reason: reason,
        );
      }
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = e.statusCode == 409
            ? widget.copy[ConsumerTerm.medicinesProfileRequiredDescription]
            : e.message;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = widget.copy[ConsumerTerm.medicinesSaveFailed];
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
              widget.existing == null
                  ? widget.copy[ConsumerTerm.medicinesAddTitle]
                  : widget.copy[ConsumerTerm.medicinesEditTitle],
              style: theme.textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            TextField(
              controller: _nameController,
              enabled: !_saving,
              textInputAction: TextInputAction.next,
              decoration: InputDecoration(
                labelText: widget.copy[ConsumerTerm.medicinesNameLabel],
                hintText: widget.copy[ConsumerTerm.medicinesNameHint],
                border: const OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            TextField(
              controller: _doseController,
              enabled: !_saving,
              textInputAction: TextInputAction.next,
              decoration: InputDecoration(
                labelText: widget.copy[ConsumerTerm.medicinesDoseLabel],
                hintText: widget.copy[ConsumerTerm.medicinesDoseHint],
                border: const OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            TextField(
              controller: _scheduleController,
              enabled: !_saving,
              textInputAction: TextInputAction.next,
              decoration: InputDecoration(
                labelText: widget.copy[ConsumerTerm.medicinesScheduleLabel],
                hintText: widget.copy[ConsumerTerm.medicinesScheduleHint],
                border: const OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _routeController,
                    enabled: !_saving,
                    textInputAction: TextInputAction.next,
                    decoration: InputDecoration(
                      labelText: widget.copy[ConsumerTerm.medicinesRouteLabel],
                      hintText: widget.copy[ConsumerTerm.medicinesRouteHint],
                      border: const OutlineInputBorder(),
                    ),
                  ),
                ),
                const SizedBox(width: ClaraTokens.spaceSm),
                Expanded(
                  child: TextField(
                    controller: _formController,
                    enabled: !_saving,
                    textInputAction: widget.existing == null
                        ? TextInputAction.done
                        : TextInputAction.next,
                    onSubmitted: widget.existing == null && !_saving
                        ? (_) => _submit()
                        : null,
                    decoration: InputDecoration(
                      labelText: widget.copy[ConsumerTerm.medicinesFormLabel],
                      hintText: widget.copy[ConsumerTerm.medicinesFormHint],
                      border: const OutlineInputBorder(),
                    ),
                  ),
                ),
              ],
            ),
            if (widget.existing != null) ...[
              const SizedBox(height: ClaraTokens.spaceMd),
              TextField(
                controller: _reasonController,
                enabled: !_saving,
                textInputAction: TextInputAction.done,
                onSubmitted: (_) => _saving ? null : _submit(),
                decoration: InputDecoration(
                  labelText: widget.copy[ConsumerTerm.medicinesEditReasonLabel],
                  hintText: widget.copy[ConsumerTerm.medicinesEditReasonHint],
                  border: const OutlineInputBorder(),
                ),
              ),
            ],
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
                  : Text(
                      widget.existing == null
                          ? widget.copy[ConsumerTerm.medicinesSave]
                          : widget.copy[ConsumerTerm.medicinesSaveNewVersion],
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

// =============================================================================
// Tab 3 — "An toàn": DrugBank-backed interaction checking & DDI analysis.
// =============================================================================

class _SafetyTab extends StatefulWidget {
  const _SafetyTab({
    required this.apiClient,
    required this.sessionStore,
    required this.copy,
    this.languageController,
    CareguardOfflineCache? offlineCache,
  }) : _offlineCache = offlineCache;

  final ApiClient apiClient;
  final SessionStore sessionStore;
  final ConsumerTerminology copy;
  final LanguageController? languageController;
  final CareguardOfflineCache? _offlineCache;

  @override
  State<_SafetyTab> createState() => _SafetyTabState();
}

class _SafetyTabState extends State<_SafetyTab> {
  bool _loadingCabinet = true;
  String? _cabinetError;
  int _distinctCabinetCount = 0;

  bool _checking = false;
  String? _checkError;
  DdiUserView? _ddiView;
  DateTime? _ddiOfflineCachedAt;
  List<CareguardMedicationClarification>? _ddiClarifications;
  Map<int, CareguardClarificationCandidate> _selectedClarifications =
      <int, CareguardClarificationCandidate>{};

  final _freeTextMedicationsController = TextEditingController();
  final _freeTextAllergiesController = TextEditingController();
  bool _quickCheckExpanded = false;

  late final CareguardOfflineCache _offlineCache;

  @override
  void initState() {
    super.initState();
    _offlineCache = widget._offlineCache ??
        CareguardOfflineCache(
          storage: FlutterSecureSessionStorage(),
          userId: widget.sessionStore.userId ?? widget.sessionStore.email,
        );
    _loadCabinetInfo();
  }

  @override
  void dispose() {
    _freeTextMedicationsController.dispose();
    _freeTextAllergiesController.dispose();
    super.dispose();
  }

  String? get _token {
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) return null;
    return token;
  }

  String get _locale =>
      widget.languageController?.languageCode.toLowerCase().startsWith('en') ==
              true
          ? 'en'
          : 'vi';

  Future<void> _loadCabinetInfo() async {
    final token = _token;
    if (token == null) {
      setState(() {
        _loadingCabinet = false;
        _cabinetError = widget.copy[ConsumerTerm.medicinesLoginRequired];
      });
      return;
    }

    setState(() {
      _loadingCabinet = true;
      _cabinetError = null;
    });

    try {
      final data =
          await widget.apiClient.getCareguardCabinet(accessToken: token);
      final rawItems = data['items'];
      final distinctKeys = <String>{};
      if (rawItems is List) {
        for (final item in rawItems) {
          if (item is Map) {
            final normalized =
                (item['normalized_name'] ?? '').toString().trim();
            final name = (item['drug_name'] ?? '').toString().trim();
            final key = normalized.isNotEmpty
                ? normalized.toLowerCase()
                : name.toLowerCase();
            if (key.isNotEmpty) distinctKeys.add(key);
          }
        }
      }
      if (!mounted) return;
      setState(() {
        _distinctCabinetCount = distinctKeys.length;
        _loadingCabinet = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _loadingCabinet = false;
        _cabinetError = e.message;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loadingCabinet = false;
        _cabinetError = widget.copy[ConsumerTerm.medicinesLoadFailed];
      });
    }
  }

  List<Map<String, dynamic>> get _selectedResolutions =>
      _ddiClarifications
          ?.map((clarification) {
            final candidate =
                _selectedClarifications[clarification.cabinetItemId];
            if (candidate == null) return null;
            return <String, dynamic>{
              'cabinet_item_id': clarification.cabinetItemId,
              'input_alias': clarification.inputAlias,
              'drugbank_id': candidate.drugbankId,
              'drugbank_version': candidate.sourceVersion,
            };
          })
          .whereType<Map<String, dynamic>>()
          .toList(growable: false) ??
      const <Map<String, dynamic>>[];

  bool get _clarificationsComplete =>
      _ddiClarifications != null &&
      _ddiClarifications!.isNotEmpty &&
      _ddiClarifications!.every(
        (clarification) =>
            clarification.candidates.isNotEmpty &&
            _selectedClarifications.containsKey(clarification.cabinetItemId),
      );

  Future<void> _checkCabinetDdi() async {
    final token = _token;
    if (token == null) return;

    if (_distinctCabinetCount < 2) {
      setState(() {
        _checkError = _locale == 'en'
            ? 'At least 2 different medicines are needed in your cabinet to check interactions.'
            : 'Cần ít nhất 2 thuốc khác nhau trong tủ để kiểm tra tương tác.';
        _ddiView = null;
        _ddiClarifications = null;
      });
      return;
    }

    if (_ddiClarifications != null && !_clarificationsComplete) {
      setState(() {
        _checkError = _locale == 'en'
            ? 'Choose a DrugBank-backed medicine for each item before checking again.'
            : 'Hãy chọn thuốc có nguồn DrugBank cho từng mục trước khi kiểm tra lại.';
      });
      return;
    }

    setState(() {
      _checking = true;
      _checkError = null;
      _ddiView = null;
      _ddiOfflineCachedAt = null;
    });

    getAnalyticsClient().capture(
      AnalyticsEvent(
        MobileAnalyticsEvents.careguardAnalyzed,
        {'medicine_count': _distinctCabinetCount},
      ),
    );

    try {
      final response = await widget.apiClient.autoCheckCareguardCabinet(
        accessToken: token,
        allergies: const <String>[],
        symptoms: const <String>[],
        labs: const <String, dynamic>{},
        locale: _locale,
        resolutions: _selectedResolutions,
      );
      if (!mounted) return;
      final clarifications = medicationClarificationsFromPayload(response);
      if (clarifications != null) {
        setState(() {
          _ddiView = null;
          _ddiOfflineCachedAt = null;
          _ddiClarifications = clarifications;
          _selectedClarifications = <int, CareguardClarificationCandidate>{};
          _checkError = null;
        });
        return;
      }
      final view = DdiUserView.fromPayload(response);
      await _offlineCache.save(view.toCacheJson());
      if (!mounted) return;
      setState(() {
        _ddiView = view;
        _ddiOfflineCachedAt = null;
        _ddiClarifications = null;
        _selectedClarifications = <int, CareguardClarificationCandidate>{};
      });
    } on ApiException catch (e) {
      await _handleDdiFailure(e, e.message);
    } catch (e) {
      await _handleDdiFailure(
        e,
        _locale == 'en'
            ? 'We could not check medicine interactions right now. Try again.'
            : 'Không thể kiểm tra tương tác thuốc lúc này. Vui lòng thử lại.',
      );
    } finally {
      if (mounted) setState(() => _checking = false);
    }
  }

  Future<void> _checkFreeTextDdi() async {
    final token = _token;
    if (token == null) return;

    final rawMeds = _freeTextMedicationsController.text;
    final medicines = rawMeds
        .split(RegExp(r'[\n,]'))
        .map((m) => m.trim())
        .where((m) => m.isNotEmpty)
        .toList();
    final distinctMeds = medicines.map((m) => m.toLowerCase()).toSet();

    if (distinctMeds.length < 2) {
      setState(() {
        _checkError = _locale == 'en'
            ? 'Enter at least 2 different medicines to check interactions.'
            : 'Cần nhập ít nhất 2 thuốc khác nhau để kiểm tra tương tác.';
        _ddiView = null;
        _ddiClarifications = null;
      });
      return;
    }

    final allergies = _freeTextAllergiesController.text
        .split(RegExp(r'[\n,]'))
        .map((a) => a.trim())
        .where((a) => a.isNotEmpty)
        .toList();

    setState(() {
      _checking = true;
      _checkError = null;
      _ddiView = null;
      _ddiOfflineCachedAt = null;
      _ddiClarifications = null;
    });

    getAnalyticsClient().capture(
      AnalyticsEvent(
        MobileAnalyticsEvents.careguardAnalyzed,
        {'medicine_count': distinctMeds.length},
      ),
    );

    try {
      final response = await widget.apiClient.analyzeCareguard(
        accessToken: token,
        payload: {
          'medications': medicines,
          'allergies': allergies,
          'symptoms': <String>[],
          'labs': <String, dynamic>{},
        },
      );
      if (!mounted) return;
      if (medicationClarificationsFromPayload(response) != null) {
        setState(() {
          _ddiView = null;
          _ddiOfflineCachedAt = null;
          _checkError = ddiMedicationClarificationUnavailableMessage(context);
        });
        return;
      }
      final view = DdiUserView.fromPayload(response);
      setState(() {
        _ddiView = view;
        _ddiOfflineCachedAt = null;
        _ddiClarifications = null;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _checkError = e.message);
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _checkError = _locale == 'en'
            ? 'We could not check medicine interactions right now. Try again.'
            : 'Không thể kiểm tra tương tác thuốc lúc này. Vui lòng thử lại.';
      });
    } finally {
      if (mounted) setState(() => _checking = false);
    }
  }

  Future<void> _handleDdiFailure(Object error, String fallbackMessage) async {
    if (isLikelyOfflineFailure(error)) {
      final cached = await _offlineCache.read();
      if (!mounted) return;
      if (cached != null) {
        setState(() {
          _ddiView = DdiUserView.fromCacheJson(cached.view);
          _ddiOfflineCachedAt = cached.cachedAt;
          _checkError = null;
        });
        return;
      }
    }
    if (!mounted) return;
    setState(() {
      _ddiView = null;
      _ddiOfflineCachedAt = null;
      _checkError = fallbackMessage;
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final status = theme.extension<ClaraStatusColors>();

    return RefreshIndicator(
      onRefresh: _loadCabinetInfo,
      child: ListView(
        padding: const EdgeInsets.all(ClaraTokens.spaceLg),
        children: [
          // Header Card
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
                          widget.copy[ConsumerTerm.medicinesSafetyTitle],
                          style: theme.textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: ClaraTokens.spaceMd),
                  Text(
                    widget.copy[ConsumerTerm.medicinesSafetyDescription],
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceMd),

          // Cabinet-driven DDI check section
          Card(
            margin: EdgeInsets.zero,
            child: Padding(
              padding: const EdgeInsets.all(ClaraTokens.spaceLg),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.inventory_2_outlined, color: scheme.primary),
                      const SizedBox(width: ClaraTokens.spaceSm),
                      Expanded(
                        child: Text(
                          _locale == 'en'
                              ? 'Check interactions from Cabinet'
                              : 'Kiểm tra tương tác từ Tủ thuốc',
                          style: theme.textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: ClaraTokens.spaceSm),
                  if (_loadingCabinet)
                    const Padding(
                      padding: EdgeInsets.symmetric(vertical: ClaraTokens.spaceSm),
                      child: LinearProgressIndicator(),
                    )
                  else if (_cabinetError != null)
                    Text(
                      _cabinetError!,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: scheme.error,
                      ),
                    )
                  else ...[
                    Text(
                      _locale == 'en'
                          ? 'Current medicines in cabinet: $_distinctCabinetCount.'
                          : 'Số thuốc hiện có trong tủ: $_distinctCabinetCount thuốc.',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(height: ClaraTokens.spaceMd),
                    if (_distinctCabinetCount < 2) ...[
                      Text(
                        _locale == 'en'
                            ? 'Add at least 2 different medicines to your cabinet to check interactions.'
                            : 'Cần ít nhất 2 thuốc khác nhau trong tủ để kiểm tra tương tác.',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: status?.warning ?? Colors.orange.shade800,
                        ),
                      ),
                      const SizedBox(height: ClaraTokens.spaceSm),
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
                            label: Text(
                              widget.copy[ConsumerTerm.medicinesOpenCabinet],
                            ),
                            style: OutlinedButton.styleFrom(
                              minimumSize: const Size.fromHeight(kMinTouchTarget),
                            ),
                          );
                        },
                      ),
                    ] else
                      FilledButton.icon(
                        onPressed: _checking ? null : _checkCabinetDdi,
                        icon: _checking
                            ? const SizedBox(
                                width: 18,
                                height: 18,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Icon(Icons.medication_liquid),
                        label: Text(
                          _locale == 'en'
                              ? 'Check interactions in cabinet'
                              : 'Kiểm tra tương tác thuốc trong tủ',
                        ),
                        style: FilledButton.styleFrom(
                          minimumSize: const Size.fromHeight(kMinTouchTarget),
                        ),
                      ),
                  ],
                ],
              ),
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceMd),

          // Quick Free-text DDI check section
          Card(
            margin: EdgeInsets.zero,
            child: Padding(
              padding: const EdgeInsets.all(ClaraTokens.spaceLg),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  InkWell(
                    onTap: () => setState(() {
                      _quickCheckExpanded = !_quickCheckExpanded;
                    }),
                    child: Row(
                      children: [
                        Icon(Icons.edit_note, color: scheme.primary),
                        const SizedBox(width: ClaraTokens.spaceSm),
                        Expanded(
                          child: Text(
                            _locale == 'en'
                                ? 'Quick check (enter custom list)'
                                : 'Kiểm tra nhanh (danh sách tự nhập)',
                            style: theme.textTheme.titleSmall?.copyWith(
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                        Icon(
                          _quickCheckExpanded
                              ? Icons.expand_less
                              : Icons.expand_more,
                        ),
                      ],
                    ),
                  ),
                  if (_quickCheckExpanded) ...[
                    const SizedBox(height: ClaraTokens.spaceMd),
                    TextField(
                      controller: _freeTextMedicationsController,
                      enabled: !_checking,
                      minLines: 2,
                      maxLines: 4,
                      decoration: InputDecoration(
                        labelText: _locale == 'en'
                            ? 'Medicines (one per line or comma-separated)'
                            : 'Danh sách thuốc (mỗi dòng một thuốc)',
                        hintText: _locale == 'en'
                            ? 'Warfarin\nIbuprofen'
                            : 'Warfarin\nIbuprofen',
                        border: const OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: ClaraTokens.spaceSm),
                    TextField(
                      controller: _freeTextAllergiesController,
                      enabled: !_checking,
                      minLines: 1,
                      maxLines: 2,
                      decoration: InputDecoration(
                        labelText: _locale == 'en'
                            ? 'Allergies (optional)'
                            : 'Dị ứng (không bắt buộc)',
                        hintText: _locale == 'en'
                            ? 'Penicillin, Aspirin'
                            : 'Penicillin, Aspirin',
                        border: const OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: ClaraTokens.spaceMd),
                    OutlinedButton.icon(
                      onPressed: _checking ? null : _checkFreeTextDdi,
                      icon: _checking
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.search),
                      label: Text(
                        _locale == 'en'
                            ? 'Check custom list'
                            : 'Kiểm tra danh sách đã nhập',
                      ),
                      style: OutlinedButton.styleFrom(
                        minimumSize: const Size.fromHeight(kMinTouchTarget),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),

          // Error banner
          if (_checkError != null) ...[
            const SizedBox(height: ClaraTokens.spaceMd),
            Card(
              margin: EdgeInsets.zero,
              color: scheme.errorContainer,
              child: Padding(
                padding: const EdgeInsets.all(ClaraTokens.spaceMd),
                child: Text(
                  _checkError!,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: scheme.onErrorContainer,
                  ),
                ),
              ),
            ),
          ],

          // Clarification View (DrugBank source candidate resolution)
          if (_ddiClarifications != null) ...[
            const SizedBox(height: ClaraTokens.spaceMd),
            DdiMedicationClarificationView(
              clarifications: _ddiClarifications!,
              selected: _selectedClarifications,
              loading: _checking,
              onSelected: (clarification, candidate) => setState(() {
                _selectedClarifications =
                    Map<int, CareguardClarificationCandidate>.from(
                  _selectedClarifications,
                )..[clarification.cabinetItemId] = candidate;
                _checkError = null;
              }),
              onResubmit: _checkCabinetDdi,
            ),
          ],

          // Results View
          if (_ddiView != null) ...[
            const SizedBox(height: ClaraTokens.spaceMd),
            DdiResultView(
              view: _ddiView!,
              offlineCachedAt: _ddiOfflineCachedAt,
            ),
          ],

          // Safety Notice & Disclaimer
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
                      widget.copy[ConsumerTerm.medicinesSafetyNotice],
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
      ),
    );
  }
}
