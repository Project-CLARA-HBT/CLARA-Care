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
import '../../core/consumer_terminology.dart';
import '../../core/feature_flags.dart';
import '../../core/session_store.dart';
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
            ),
            _SafetyTab(copy: copy),
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
// Tab 3 — "An toàn": honest pointer to the in-cabinet DDI check.
// =============================================================================

class _SafetyTab extends StatelessWidget {
  const _SafetyTab({required this.copy});

  final ConsumerTerminology copy;

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
                        copy[ConsumerTerm.medicinesSafetyTitle],
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: ClaraTokens.spaceMd),
                Text(
                  copy[ConsumerTerm.medicinesSafetyDescription],
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: scheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: ClaraTokens.spaceMd),
                Builder(
                  builder: (context) {
                    final controller = DefaultTabController.maybeOf(context);
                    if (controller == null) {
                      return const SizedBox.shrink();
                    }
                    return OutlinedButton.icon(
                      onPressed: () => controller.animateTo(1),
                      icon: const Icon(Icons.inventory_2_outlined),
                      label: Text(copy[ConsumerTerm.medicinesOpenCabinet]),
                      style: OutlinedButton.styleFrom(
                        minimumSize: const Size.fromHeight(kMinTouchTarget),
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
                    copy[ConsumerTerm.medicinesSafetyNotice],
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
