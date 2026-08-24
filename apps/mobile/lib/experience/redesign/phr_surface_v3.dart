// PHR surface for the CLARA_Mobile redesign (Experience_V3).
//
// Spec v5 Section 7.5:
//   Hub -> Section list -> Full-screen section editors:
//     1. Demographics
//     2. Allergies
//     3. Conditions
//     4. Medications
//     5. Measurements
//     6. Documents
//
// Regression-locked safety invariants preserved:
//   * Persistent decision-support disclaimer (INV-7)
//   * No-PII count-only analytics on save (INV-3)
//   * Vietnamese-first copy with bilingual en/vi support
//   * >=48dp tap targets (A11y)
//   * Enhanced reads (export + emergency card) gated by `phr_enhanced_mobile_enabled`

import 'dart:convert';

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../../core/analytics.dart';
import '../../core/api_client.dart';
import '../../core/feature_flags.dart';
import '../../core/session_store.dart';
import '../../screens/phr_screen.dart';
import '../../theme/components/clara_button.dart';
import '../../theme/components/clara_card.dart';
import '../../theme/components/clara_input.dart';
import '../../theme/components/section_header.dart';
import '../../theme/glass/glass_surface.dart';
import '../../theme/glass/glass_tokens.dart';
import '../../theme/tokens.dart';
import '../../widgets/error_retry_view.dart';
import '../language_controller.dart';
import 'phr_completeness.dart';

/// The redesigned PHR ("Hồ sơ sức khỏe") surface. See file header.
class PhrSurfaceV3 extends StatefulWidget {
  const PhrSurfaceV3({
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
  State<PhrSurfaceV3> createState() => _PhrSurfaceV3State();
}

class _PhrSurfaceV3State extends State<PhrSurfaceV3> {
  PhrStrings get _s => PhrStrings(
        widget.languageController?.languageCode == 'en'
            ? PhrLang.en
            : PhrLang.vi,
      );

  bool _loading = false;
  bool _saving = false;
  String? _loadError;
  String? _saveError;
  PhrRecordModel? _record;

  // Profile controllers, created once and rebound on load/save.
  final _fullName = TextEditingController();
  final _dob = TextEditingController();
  final _gender = TextEditingController();
  final _bloodType = TextEditingController();
  final _height = TextEditingController();
  final _weight = TextEditingController();
  final _phone = TextEditingController();
  final _address = TextEditingController();
  final _emName = TextEditingController();
  final _emPhone = TextEditingController();
  final _insurance = TextEditingController();
  final _notes = TextEditingController();

  bool get _enhancedEnabled => widget.resolver.phrEnhancedEnabled;

  @override
  void initState() {
    super.initState();
    getAnalyticsClient().captureScreenView(MobileAnalyticsEvents.phrViewed);
    for (final c in [
      _fullName,
      _dob,
      _gender,
      _bloodType,
      _height,
      _weight,
      _phone,
      _address,
      _emName,
      _emPhone,
      _insurance,
      _notes,
    ]) {
      c.addListener(_onFieldChanged);
    }
    _load();
  }

  void _onFieldChanged() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    for (final c in [
      _fullName,
      _dob,
      _gender,
      _bloodType,
      _height,
      _weight,
      _phone,
      _address,
      _emName,
      _emPhone,
      _insurance,
      _notes,
    ]) {
      c.dispose();
    }
    super.dispose();
  }

  void _bind(PhrRecordModel r) {
    _fullName.text = r.fullName;
    _dob.text = r.dateOfBirth ?? '';
    _gender.text = r.gender;
    _bloodType.text = r.bloodType;
    _height.text = r.heightCm?.toString() ?? '';
    _weight.text = r.weightKg?.toString() ?? '';
    _phone.text = r.phone;
    _address.text = r.address;
    _emName.text = r.emergencyContactName;
    _emPhone.text = r.emergencyContactPhone;
    _insurance.text = r.insuranceId;
    _notes.text = r.notes;
  }

  double? _toDouble(String value) {
    final t = value.trim();
    if (t.isEmpty) return null;
    return double.tryParse(t);
  }

  Future<void> _load() async {
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) {
      setState(() => _loadError = _s.loadError);
      return;
    }
    setState(() {
      _loading = true;
      _loadError = null;
      _saveError = null;
    });
    try {
      final data = await widget.apiClient.getPhrRecord(accessToken: token);
      final record = PhrRecordModel.fromJson(data);
      if (!mounted) return;
      setState(() => _record = record);
      _bind(record);
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _loadError = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(() => _loadError = _s.loadError);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  PhrCompleteness _computeCompleteness(PhrRecordModel record) {
    return PhrCompleteness.compute(
      english: widget.languageController?.languageCode == 'en',
      fullName: _fullName.text,
      dateOfBirth: _dob.text,
      gender: _gender.text,
      bloodType: _bloodType.text,
      heightCm: _height.text,
      weightKg: _weight.text,
      phone: _phone.text,
      emergencyContactName: _emName.text,
      emergencyContactPhone: _emPhone.text,
      allergyCount: record.allergies.length,
      conditionCount: record.conditions.length,
      medicationCount: record.medications.length,
    );
  }

  void _captureProfile(PhrRecordModel r) {
    r.fullName = _fullName.text.trim();
    final dob = _dob.text.trim();
    r.dateOfBirth = dob.isEmpty ? null : dob;
    r.gender = _gender.text.trim();
    r.bloodType = _bloodType.text.trim();
    r.heightCm = _toDouble(_height.text);
    r.weightKg = _toDouble(_weight.text);
    r.phone = _phone.text.trim();
    r.address = _address.text.trim();
    r.emergencyContactName = _emName.text.trim();
    r.emergencyContactPhone = _emPhone.text.trim();
    r.insuranceId = _insurance.text.trim();
    r.notes = _notes.text.trim();
  }

  Future<void> _save() async {
    final record = _record;
    final token = widget.sessionStore.accessToken;
    if (record == null) return;
    if (token == null || token.isEmpty) {
      setState(() => _saveError = _s.loadError);
      return;
    }
    _captureProfile(record);
    setState(() {
      _saving = true;
      _saveError = null;
    });
    try {
      final data = await widget.apiClient.updatePhrRecord(
        accessToken: token,
        payload: record.toJson(),
      );
      // No-PII analytics: single total entry count only.
      getAnalyticsClient().capture(
        AnalyticsEvent(MobileAnalyticsEvents.phrSaved, {
          'entry_count': record.allergies.length +
              record.conditions.length +
              record.medications.length,
        }),
      );
      final updated = PhrRecordModel.fromJson(data);
      if (!mounted) return;
      setState(() => _record = updated);
      _bind(updated);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(_s.saved)),
      );
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _saveError = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(() => _saveError = _s.loadError);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  void _openDemographics(PhrRecordModel record) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => PhrDemographicsScreen(
          strings: _s,
          fullName: _fullName,
          dob: _dob,
          gender: _gender,
          bloodType: _bloodType,
          phone: _phone,
          address: _address,
          emName: _emName,
          emPhone: _emPhone,
          onChanged: () => setState(() {}),
        ),
      ),
    );
  }

  void _openAllergies(PhrRecordModel record) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => PhrAllergiesScreen(
          strings: _s,
          allergies: record.allergies,
          onChanged: () => setState(() {}),
        ),
      ),
    );
  }

  void _openConditions(PhrRecordModel record) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => PhrConditionsScreen(
          strings: _s,
          conditions: record.conditions,
          onChanged: () => setState(() {}),
        ),
      ),
    );
  }

  void _openMedications(PhrRecordModel record) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => PhrMedicationsScreen(
          strings: _s,
          medications: record.medications,
          onChanged: () => setState(() {}),
        ),
      ),
    );
  }

  void _openMeasurements(PhrRecordModel record) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => PhrMeasurementsScreen(
          strings: _s,
          height: _height,
          weight: _weight,
          onChanged: () => setState(() {}),
        ),
      ),
    );
  }

  void _openDocuments(PhrRecordModel record) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => PhrDocumentsScreen(
          strings: _s,
          insurance: _insurance,
          notes: _notes,
          onChanged: () => setState(() {}),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final languageController = widget.languageController;
    if (languageController == null) return _buildScaffold();
    return AnimatedBuilder(
      animation: languageController,
      builder: (context, _) => _buildScaffold(),
    );
  }

  Widget _buildScaffold() {
    return Scaffold(
      appBar: AppBar(
        title: Text(_s.title),
        actions: [
          if (_enhancedEnabled && _record != null) ...[
            IconButton(
              tooltip: _s.emergencyCardAction,
              icon: const Icon(Icons.emergency_outlined),
              onPressed: _openEmergencyCard,
            ),
            IconButton(
              tooltip: _s.exportAction,
              icon: const Icon(Icons.ios_share),
              onPressed: _openExport,
            ),
          ],
        ],
      ),
      floatingActionButton: _record == null
          ? null
          : FloatingActionButton.extended(
              onPressed: _saving ? null : _save,
              icon: _saving
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.save_outlined),
              label: Text(_saving ? _s.saving : _s.save),
            ),
      body: SafeArea(child: _buildBody()),
    );
  }

  Widget _buildBody() {
    if (_loading && _record == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_loadError != null && _record == null) {
      return ErrorRetryView(message: _loadError!, onRetry: _load);
    }
    final record = _record;
    if (record == null) {
      return ErrorRetryView(message: _s.loadError, onRetry: _load);
    }

    final isEnglish = widget.languageController?.languageCode == 'en';
    final nameVal = _fullName.text.trim();
    final nameDisplay = nameVal.isEmpty
        ? (isEnglish ? 'No name set' : 'Chưa cập nhật họ tên')
        : nameVal;

    final allergiesSummary = record.allergies.isEmpty
        ? (isEnglish ? 'No allergies recorded' : 'Chưa có dị ứng ghi nhận')
        : '${record.allergies.length} ${isEnglish ? 'items' : 'mục'} (${record.allergies.map((a) => a.name).take(2).join(', ')}${record.allergies.length > 2 ? '...' : ''})';

    final conditionsSummary = record.conditions.isEmpty
        ? (isEnglish ? 'No conditions recorded' : 'Chưa có bệnh lý ghi nhận')
        : '${record.conditions.length} ${isEnglish ? 'items' : 'mục'} (${record.conditions.map((c) => c.name).take(2).join(', ')}${record.conditions.length > 2 ? '...' : ''})';

    final medicationsSummary = record.medications.isEmpty
        ? (isEnglish ? 'No medications recorded' : 'Chưa có thuốc ghi nhận')
        : '${record.medications.length} ${isEnglish ? 'items' : 'mục'} (${record.medications.map((m) => m.name).take(2).join(', ')}${record.medications.length > 2 ? '...' : ''})';

    final heightVal = _height.text.trim();
    final weightVal = _weight.text.trim();
    final measurementsSummary = (heightVal.isEmpty && weightVal.isEmpty)
        ? (isEnglish ? 'No vitals recorded' : 'Chưa có chỉ số')
        : '${heightVal.isNotEmpty ? '$heightVal cm' : '--'} · ${weightVal.isNotEmpty ? '$weightVal kg' : '--'}';

    final insuranceVal = _insurance.text.trim();
    final documentsSummary = insuranceVal.isEmpty
        ? (isEnglish ? 'Insurance & clinical notes' : 'Bảo hiểm y tế & ghi chú')
        : '${isEnglish ? 'Insurance' : 'BHYT'}: $insuranceVal';

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.only(
          top: ClaraTokens.spaceSm,
          bottom: ClaraTokens.spaceXl * 2,
        ),
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: ClaraTokens.spaceMd,
            ),
            child: PhrDisclaimerBanner(text: _s.disclaimer),
          ),
          const SizedBox(height: ClaraTokens.spaceSm),
          Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: ClaraTokens.spaceMd,
            ),
            child: PhrCompletenessCard(
              completeness: _computeCompleteness(record),
              title: _s.completenessTitle,
              completeMessage: _s.completenessComplete,
              nextUpLabel: _s.completenessNextUp,
              english: isEnglish,
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceSm),
          if (_saveError != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(
                ClaraTokens.spaceMd,
                0,
                ClaraTokens.spaceMd,
                ClaraTokens.spaceSm,
              ),
              child: _InlineError(message: _saveError!),
            ),
          SectionHeader(
            title: isEnglish ? 'Health Record Sections' : 'Danh mục hồ sơ',
          ),
          Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: ClaraTokens.spaceMd,
            ),
            child: Column(
              children: [
                // 1. Demographics
                _SectionHubCard(
                  icon: Icons.person_outline,
                  title: _s.sectionProfile,
                  subtitle: nameDisplay,
                  badge: nameVal.isNotEmpty
                      ? (isEnglish ? 'Filled' : 'Đã điền')
                      : (isEnglish ? 'Required' : 'Cần điền'),
                  onTap: () => _openDemographics(record),
                ),
                const SizedBox(height: ClaraTokens.spaceSm),
                // 2. Allergies
                _SectionHubCard(
                  icon: Icons.warning_amber_outlined,
                  title: _s.sectionAllergies,
                  subtitle: allergiesSummary,
                  badge: '${record.allergies.length}',
                  onTap: () => _openAllergies(record),
                ),
                const SizedBox(height: ClaraTokens.spaceSm),
                // 3. Conditions
                _SectionHubCard(
                  icon: Icons.favorite_border,
                  title: _s.sectionConditions,
                  subtitle: conditionsSummary,
                  badge: '${record.conditions.length}',
                  onTap: () => _openConditions(record),
                ),
                const SizedBox(height: ClaraTokens.spaceSm),
                // 4. Medications
                _SectionHubCard(
                  icon: Icons.medication_outlined,
                  title: _s.sectionMedications,
                  subtitle: medicationsSummary,
                  badge: '${record.medications.length}',
                  onTap: () => _openMedications(record),
                ),
                const SizedBox(height: ClaraTokens.spaceSm),
                // 5. Measurements
                _SectionHubCard(
                  icon: Icons.straighten_outlined,
                  title: isEnglish ? 'Measurements & Vitals' : 'Chỉ số sinh hiệu',
                  subtitle: measurementsSummary,
                  badge: (heightVal.isNotEmpty && weightVal.isNotEmpty)
                      ? (isEnglish ? 'Updated' : 'Đã đo')
                      : (isEnglish ? 'Optional' : 'Tùy chọn'),
                  onTap: () => _openMeasurements(record),
                ),
                const SizedBox(height: ClaraTokens.spaceSm),
                // 6. Documents
                _SectionHubCard(
                  icon: Icons.description_outlined,
                  title: isEnglish ? 'Documents & Notes' : 'Tài liệu & Ghi chú',
                  subtitle: documentsSummary,
                  badge: (insuranceVal.isNotEmpty || _notes.text.isNotEmpty)
                      ? (isEnglish ? 'Saved' : 'Đã lưu')
                      : (isEnglish ? 'Optional' : 'Tùy chọn'),
                  onTap: () => _openDocuments(record),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // --- Enhanced (flag-gated) read-only surfaces --------------------------------

  void _openExport() {
    final record = _record;
    if (record == null) return;
    final pretty = const JsonEncoder.withIndent('  ').convert(record.toJson());
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _ReadOnlySheet(
        title: _s.exportTitle,
        closeLabel: _s.close,
        child: SelectableText(
          pretty,
          style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
        ),
      ),
    );
  }

  void _openEmergencyCard() {
    final record = _record;
    if (record == null) return;
    final card = PhrEmergencyCardProjection.fromRecord(record);
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _ReadOnlySheet(
        title: _s.emergencyCardTitle,
        closeLabel: _s.close,
        child: card.isEmpty
            ? Text(_s.emergencyEmpty)
            : Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _EmergencyLine(
                    label: _s.bloodType,
                    value: card.bloodType.isEmpty
                        ? _s.bloodTypeUnknown
                        : card.bloodType,
                  ),
                  _EmergencyLine(
                    label: _s.emergencyContactName,
                    value: card.emergencyContactName.isEmpty
                        ? _s.noEmergencyContact
                        : '${card.emergencyContactName} · ${card.emergencyContactPhone}',
                  ),
                  const Divider(height: ClaraTokens.spaceLg),
                  Text(_s.sectionAllergies,
                      style: Theme.of(context).textTheme.titleSmall),
                  for (final a in card.allergies)
                    Text('• ${a.name} (${_s.severityLabel(a.severity)})'),
                  const SizedBox(height: ClaraTokens.spaceSm),
                  Text(_s.sectionMedications,
                      style: Theme.of(context).textTheme.titleSmall),
                  for (final m in card.currentMedications)
                    Text('• ${m.name}${m.dose.isEmpty ? '' : ' — ${m.dose}'}'),
                ],
              ),
      ),
    );
  }
}

// =============================================================================
// Section 1: Demographics Full-Screen Editor
// =============================================================================

class PhrDemographicsScreen extends StatelessWidget {
  const PhrDemographicsScreen({
    super.key,
    required this.strings,
    required this.fullName,
    required this.dob,
    required this.gender,
    required this.bloodType,
    required this.phone,
    required this.address,
    required this.emName,
    required this.emPhone,
    required this.onChanged,
  });

  final PhrStrings strings;
  final TextEditingController fullName;
  final TextEditingController dob;
  final TextEditingController gender;
  final TextEditingController bloodType;
  final TextEditingController phone;
  final TextEditingController address;
  final TextEditingController emName;
  final TextEditingController emPhone;
  final VoidCallback onChanged;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(strings.sectionProfile),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(ClaraTokens.spaceMd),
          children: [
            ClaraCard.static_(
              semanticLabel: strings.sectionProfile,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  ClaraInput(label: strings.fullName, controller: fullName),
                  const SizedBox(height: ClaraTokens.spaceSm),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: ClaraInput(
                          label: strings.dateOfBirth,
                          hint: 'YYYY-MM-DD',
                          controller: dob,
                        ),
                      ),
                      const SizedBox(width: ClaraTokens.spaceSm),
                      Expanded(
                        child: ClaraInput(
                          label: strings.gender,
                          controller: gender,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: ClaraTokens.spaceSm),
                  ClaraInput(label: strings.bloodType, controller: bloodType),
                  const SizedBox(height: ClaraTokens.spaceSm),
                  ClaraInput(
                    label: strings.phone,
                    controller: phone,
                    keyboardType: TextInputType.phone,
                  ),
                  const SizedBox(height: ClaraTokens.spaceSm),
                  ClaraInput(label: strings.address, controller: address),
                  const SizedBox(height: ClaraTokens.spaceMd),
                  Text(
                    strings.emergencyContactName,
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                  const SizedBox(height: ClaraTokens.spaceSm),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: ClaraInput(
                          label: strings.name,
                          controller: emName,
                        ),
                      ),
                      const SizedBox(width: ClaraTokens.spaceSm),
                      Expanded(
                        child: ClaraInput(
                          label: strings.phone,
                          controller: emPhone,
                          keyboardType: TextInputType.phone,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: ClaraTokens.spaceLg),
            ClaraButton.primary(
              label: strings.done,
              onPressed: () {
                onChanged();
                Navigator.of(context).pop();
              },
            ),
          ],
        ),
      ),
    );
  }
}

// =============================================================================
// Section 2: Allergies Full-Screen Editor
// =============================================================================

class PhrAllergiesScreen extends StatefulWidget {
  const PhrAllergiesScreen({
    super.key,
    required this.strings,
    required this.allergies,
    required this.onChanged,
  });

  final PhrStrings strings;
  final List<PhrAllergy> allergies;
  final VoidCallback onChanged;

  @override
  State<PhrAllergiesScreen> createState() => _PhrAllergiesScreenState();
}

class _PhrAllergiesScreenState extends State<PhrAllergiesScreen> {
  Future<void> _edit(PhrAllergy? existing) async {
    final result = await showModalBottomSheet<PhrAllergy>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _AllergySheet(strings: widget.strings, existing: existing),
    );
    if (result == null) return;
    setState(() {
      if (existing == null) {
        widget.allergies.add(result);
      } else {
        final i = widget.allergies.indexOf(existing);
        if (i >= 0) widget.allergies[i] = result;
      }
    });
    widget.onChanged();
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.strings;
    return Scaffold(
      appBar: AppBar(
        title: Text(s.sectionAllergies),
        actions: [
          IconButton(
            tooltip: s.add,
            icon: const Icon(Icons.add),
            onPressed: () => _edit(null),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _edit(null),
        icon: const Icon(Icons.add),
        label: Text(s.add),
      ),
      body: SafeArea(
        child: widget.allergies.isEmpty
            ? Center(
                child: Padding(
                  padding: const EdgeInsets.all(ClaraTokens.spaceLg),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        Icons.warning_amber_outlined,
                        size: 48,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                      const SizedBox(height: ClaraTokens.spaceMd),
                      Text(
                        s.emptySection,
                        style: Theme.of(context).textTheme.bodyLarge,
                      ),
                      const SizedBox(height: ClaraTokens.spaceMd),
                      ClaraButton.secondary(
                        label: s.add,
                        icon: Icons.add,
                        onPressed: () => _edit(null),
                      ),
                    ],
                  ),
                ),
              )
            : ListView(
                padding: const EdgeInsets.all(ClaraTokens.spaceMd),
                children: [
                  for (final a in widget.allergies) ...[
                    _EntryCard(
                      title: a.name,
                      subtitle: [
                        if (a.reaction.isNotEmpty) a.reaction,
                        s.severityLabel(a.severity),
                      ].join(' · '),
                      source: s.sourceLabel(a.informationSource),
                      verification: s.verificationLabel(a.verificationStatus),
                      editTooltip: s.edit,
                      deleteTooltip: s.delete,
                      onEdit: () => _edit(a),
                      onDelete: () {
                        setState(() => widget.allergies.remove(a));
                        widget.onChanged();
                      },
                    ),
                    const SizedBox(height: ClaraTokens.spaceSm),
                  ],
                ],
              ),
      ),
    );
  }
}

// =============================================================================
// Section 3: Conditions Full-Screen Editor
// =============================================================================

class PhrConditionsScreen extends StatefulWidget {
  const PhrConditionsScreen({
    super.key,
    required this.strings,
    required this.conditions,
    required this.onChanged,
  });

  final PhrStrings strings;
  final List<PhrCondition> conditions;
  final VoidCallback onChanged;

  @override
  State<PhrConditionsScreen> createState() => _PhrConditionsScreenState();
}

class _PhrConditionsScreenState extends State<PhrConditionsScreen> {
  Future<void> _edit(PhrCondition? existing) async {
    final result = await showModalBottomSheet<PhrCondition>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _ConditionSheet(strings: widget.strings, existing: existing),
    );
    if (result == null) return;
    setState(() {
      if (existing == null) {
        widget.conditions.add(result);
      } else {
        final i = widget.conditions.indexOf(existing);
        if (i >= 0) widget.conditions[i] = result;
      }
    });
    widget.onChanged();
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.strings;
    return Scaffold(
      appBar: AppBar(
        title: Text(s.sectionConditions),
        actions: [
          IconButton(
            tooltip: s.add,
            icon: const Icon(Icons.add),
            onPressed: () => _edit(null),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _edit(null),
        icon: const Icon(Icons.add),
        label: Text(s.add),
      ),
      body: SafeArea(
        child: widget.conditions.isEmpty
            ? Center(
                child: Padding(
                  padding: const EdgeInsets.all(ClaraTokens.spaceLg),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        Icons.favorite_border,
                        size: 48,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                      const SizedBox(height: ClaraTokens.spaceMd),
                      Text(
                        s.emptySection,
                        style: Theme.of(context).textTheme.bodyLarge,
                      ),
                      const SizedBox(height: ClaraTokens.spaceMd),
                      ClaraButton.secondary(
                        label: s.add,
                        icon: Icons.add,
                        onPressed: () => _edit(null),
                      ),
                    ],
                  ),
                ),
              )
            : ListView(
                padding: const EdgeInsets.all(ClaraTokens.spaceMd),
                children: [
                  for (final c in widget.conditions) ...[
                    _EntryCard(
                      title: c.name,
                      subtitle: [
                        s.statusLabel(c.status),
                        if ((c.diagnosedOn ?? '').isNotEmpty) c.diagnosedOn!,
                      ].join(' · '),
                      source: s.sourceLabel(c.informationSource),
                      verification: s.verificationLabel(c.verificationStatus),
                      editTooltip: s.edit,
                      deleteTooltip: s.delete,
                      onEdit: () => _edit(c),
                      onDelete: () {
                        setState(() => widget.conditions.remove(c));
                        widget.onChanged();
                      },
                    ),
                    const SizedBox(height: ClaraTokens.spaceSm),
                  ],
                ],
              ),
      ),
    );
  }
}

// =============================================================================
// Section 4: Medications Full-Screen Editor
// =============================================================================

class PhrMedicationsScreen extends StatefulWidget {
  const PhrMedicationsScreen({
    super.key,
    required this.strings,
    required this.medications,
    required this.onChanged,
  });

  final PhrStrings strings;
  final List<PhrMedication> medications;
  final VoidCallback onChanged;

  @override
  State<PhrMedicationsScreen> createState() => _PhrMedicationsScreenState();
}

class _PhrMedicationsScreenState extends State<PhrMedicationsScreen> {
  Future<void> _edit(PhrMedication? existing) async {
    final result = await showModalBottomSheet<PhrMedication>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _MedicationSheet(strings: widget.strings, existing: existing),
    );
    if (result == null) return;
    setState(() {
      if (existing == null) {
        widget.medications.add(result);
      } else {
        final i = widget.medications.indexOf(existing);
        if (i >= 0) widget.medications[i] = result;
      }
    });
    widget.onChanged();
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.strings;
    return Scaffold(
      appBar: AppBar(
        title: Text(s.sectionMedications),
        actions: [
          IconButton(
            tooltip: s.add,
            icon: const Icon(Icons.add),
            onPressed: () => _edit(null),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _edit(null),
        icon: const Icon(Icons.add),
        label: Text(s.add),
      ),
      body: SafeArea(
        child: widget.medications.isEmpty
            ? Center(
                child: Padding(
                  padding: const EdgeInsets.all(ClaraTokens.spaceLg),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        Icons.medication_outlined,
                        size: 48,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                      const SizedBox(height: ClaraTokens.spaceMd),
                      Text(
                        s.emptySection,
                        style: Theme.of(context).textTheme.bodyLarge,
                      ),
                      const SizedBox(height: ClaraTokens.spaceMd),
                      ClaraButton.secondary(
                        label: s.add,
                        icon: Icons.add,
                        onPressed: () => _edit(null),
                      ),
                    ],
                  ),
                ),
              )
            : ListView(
                padding: const EdgeInsets.all(ClaraTokens.spaceMd),
                children: [
                  for (final m in widget.medications) ...[
                    _EntryCard(
                      title: m.name,
                      subtitle: [
                        if (m.dose.isNotEmpty) m.dose,
                        if (m.frequency.isNotEmpty) m.frequency,
                        if (m.isCurrent) s.isCurrent,
                      ].join(' · '),
                      source: s.sourceLabel(m.informationSource),
                      verification: s.verificationLabel(m.verificationStatus),
                      editTooltip: s.edit,
                      deleteTooltip: s.delete,
                      onEdit: () => _edit(m),
                      onDelete: () {
                        setState(() => widget.medications.remove(m));
                        widget.onChanged();
                      },
                    ),
                    const SizedBox(height: ClaraTokens.spaceSm),
                  ],
                ],
              ),
      ),
    );
  }
}

// =============================================================================
// Section 5: Measurements Full-Screen Editor
// =============================================================================

class PhrMeasurementsScreen extends StatelessWidget {
  const PhrMeasurementsScreen({
    super.key,
    required this.strings,
    required this.height,
    required this.weight,
    required this.onChanged,
  });

  final PhrStrings strings;
  final TextEditingController height;
  final TextEditingController weight;
  final VoidCallback onChanged;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final h = double.tryParse(height.text.trim());
    final w = double.tryParse(weight.text.trim());
    double? bmi;
    String bmiCategory = '';
    if (h != null && w != null && h > 0 && w > 0) {
      final hM = h / 100.0;
      bmi = w / (hM * hM);
      if (bmi < 18.5) {
        bmiCategory = 'Thiếu cân (Underweight)';
      } else if (bmi <= 22.9) {
        bmiCategory = 'Bình thường — Chuẩn châu Á (Normal)';
      } else if (bmi <= 24.9) {
        bmiCategory = 'Tiền béo phì (Overweight)';
      } else {
        bmiCategory = 'Béo phì (Obese)';
      }
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Chỉ số sinh hiệu'),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(ClaraTokens.spaceMd),
          children: [
            ClaraCard.static_(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: ClaraInput(
                          label: strings.heightCm,
                          controller: height,
                          keyboardType: TextInputType.number,
                        ),
                      ),
                      const SizedBox(width: ClaraTokens.spaceSm),
                      Expanded(
                        child: ClaraInput(
                          label: strings.weightKg,
                          controller: weight,
                          keyboardType: TextInputType.number,
                        ),
                      ),
                    ],
                  ),
                  if (bmi != null) ...[
                    const SizedBox(height: ClaraTokens.spaceMd),
                    Container(
                      padding: const EdgeInsets.all(ClaraTokens.spaceSm),
                      decoration: BoxDecoration(
                        color: theme.colorScheme.primaryContainer.withValues(alpha: 0.5),
                        borderRadius: BorderRadius.circular(ClaraTokens.radiusSm),
                      ),
                      child: Row(
                        children: [
                          Icon(
                            Icons.health_and_safety_outlined,
                            color: theme.colorScheme.primary,
                          ),
                          const SizedBox(width: ClaraTokens.spaceSm),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'Chỉ số BMI: ${bmi.toStringAsFixed(1)} kg/m²',
                                  style: theme.textTheme.titleSmall?.copyWith(
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                                Text(
                                  bmiCategory,
                                  style: theme.textTheme.bodySmall?.copyWith(
                                    color: theme.colorScheme.onSurfaceVariant,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            GlassSurface(
              blurSigma: GlassTokens.blurCard,
              radius: GlassTokens.radiusCard,
              fill: GlassFill.regular,
              padding: const EdgeInsets.all(ClaraTokens.spaceMd),
              child: Row(
                children: [
                  Icon(
                    Icons.info_outline,
                    size: 20,
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                  const SizedBox(width: ClaraTokens.spaceSm),
                  Expanded(
                    child: Text(
                      'Cập nhật chiều cao và cân nặng định kỳ giúp CLARA tính toán liều lượng thuốc an toàn và phát hiện tương tác chính xác hơn.',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: ClaraTokens.spaceLg),
            ClaraButton.primary(
              label: strings.done,
              onPressed: () {
                onChanged();
                Navigator.of(context).pop();
              },
            ),
          ],
        ),
      ),
    );
  }
}

// =============================================================================
// Section 6: Documents Full-Screen Editor
// =============================================================================

class PhrDocumentsScreen extends StatelessWidget {
  const PhrDocumentsScreen({
    super.key,
    required this.strings,
    required this.insurance,
    required this.notes,
    required this.onChanged,
  });

  final PhrStrings strings;
  final TextEditingController insurance;
  final TextEditingController notes;
  final VoidCallback onChanged;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Tài liệu & Ghi chú'),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(ClaraTokens.spaceMd),
          children: [
            ClaraCard.static_(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  ClaraInput(
                    label: strings.insuranceId,
                    controller: insurance,
                    hint: 'VD: DN4010123456789',
                  ),
                  const SizedBox(height: ClaraTokens.spaceMd),
                  ClaraInput(
                    label: strings.notes,
                    controller: notes,
                    maxLines: 5,
                    hint: 'Ghi chú thêm về lịch sử phẫu thuật, cấy ghép y tế hoặc dặn dò của bác sĩ...',
                  ),
                ],
              ),
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            GlassSurface(
              blurSigma: GlassTokens.blurCard,
              radius: GlassTokens.radiusCard,
              fill: GlassFill.regular,
              padding: const EdgeInsets.all(ClaraTokens.spaceMd),
              child: Row(
                children: [
                  Icon(
                    Icons.lock_outline,
                    size: 20,
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                  const SizedBox(width: ClaraTokens.spaceSm),
                  Expanded(
                    child: Text(
                      'Tất cả tài liệu y tế và ghi chú được mã hóa an toàn theo tiêu chuẩn PDPD và chỉ dùng để hỗ trợ sức khỏe cho bạn.',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: ClaraTokens.spaceLg),
            ClaraButton.primary(
              label: strings.done,
              onPressed: () {
                onChanged();
                Navigator.of(context).pop();
              },
            ),
          ],
        ),
      ),
    );
  }
}

// =============================================================================
// Hub Section Card Widget
// =============================================================================

class _SectionHubCard extends StatelessWidget {
  const _SectionHubCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.badge,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final String badge;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ConstrainedBox(
      constraints: const BoxConstraints(minHeight: A11y.minTapTargetDimension),
      child: ClaraCard(
        semanticLabel: '$title, $subtitle',
        onTap: onTap,
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(ClaraTokens.spaceSm),
              decoration: BoxDecoration(
                color: theme.colorScheme.primaryContainer.withValues(alpha: 0.5),
                borderRadius: BorderRadius.circular(ClaraTokens.radiusSm),
              ),
              child: Icon(icon, size: 24, color: theme.colorScheme.primary),
            ),
            const SizedBox(width: ClaraTokens.spaceMd),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          title,
                          style: theme.textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 8,
                          vertical: 2,
                        ),
                        decoration: BoxDecoration(
                          color: theme.colorScheme.surfaceContainerHighest,
                          borderRadius: BorderRadius.circular(ClaraTokens.radiusSm),
                        ),
                        child: Text(
                          badge,
                          style: theme.textTheme.labelSmall?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 2),
                  Text(
                    subtitle,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            const SizedBox(width: ClaraTokens.spaceSm),
            Icon(
              Icons.chevron_right,
              size: 20,
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ],
        ),
      ),
    );
  }
}

// =============================================================================
// Shared small widgets & editor sheets
// =============================================================================

class _InlineError extends StatelessWidget {
  const _InlineError({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(ClaraTokens.spaceSm),
      decoration: BoxDecoration(
        color: scheme.errorContainer,
        borderRadius: BorderRadius.circular(ClaraTokens.radiusSm),
      ),
      child: Row(
        children: [
          Icon(Icons.error_outline, size: 18, color: scheme.onErrorContainer),
          const SizedBox(width: ClaraTokens.spaceSm),
          Expanded(
            child: Text(
              message,
              style: TextStyle(color: scheme.onErrorContainer),
            ),
          ),
        ],
      ),
    );
  }
}

class _EntryCard extends StatelessWidget {
  const _EntryCard({
    required this.title,
    required this.subtitle,
    required this.source,
    required this.verification,
    required this.editTooltip,
    required this.deleteTooltip,
    required this.onEdit,
    required this.onDelete,
  });

  final String title;
  final String subtitle;
  final String source;
  final String verification;
  final String editTooltip;
  final String deleteTooltip;
  final VoidCallback onEdit;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ClaraCard.static_(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  title,
                  style: theme.textTheme.titleMedium
                      ?.copyWith(fontWeight: FontWeight.w600),
                ),
              ),
              IconButton(
                tooltip: editTooltip,
                icon: const Icon(Icons.edit_outlined, size: 20),
                onPressed: onEdit,
              ),
              IconButton(
                tooltip: deleteTooltip,
                icon: const Icon(Icons.delete_outline, size: 20),
                onPressed: onDelete,
              ),
            ],
          ),
          if (subtitle.trim().isNotEmpty)
            Text(
              subtitle,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          const SizedBox(height: ClaraTokens.spaceSm),
          Wrap(
            spacing: ClaraTokens.spaceSm,
            children: [
              _Badge(label: source, icon: Icons.source_outlined),
              _Badge(label: verification, icon: Icons.verified_outlined),
            ],
          ),
        ],
      ),
    );
  }
}

class _Badge extends StatelessWidget {
  const _Badge({required this.label, required this.icon});

  final String label;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(ClaraTokens.radiusSm),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 13, color: scheme.onSurfaceVariant),
          const SizedBox(width: 4),
          Text(
            label,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: scheme.onSurfaceVariant,
                ),
          ),
        ],
      ),
    );
  }
}

class _EmergencyLine extends StatelessWidget {
  const _EmergencyLine({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: RichText(
        text: TextSpan(
          style: Theme.of(context).textTheme.bodyMedium,
          children: [
            TextSpan(
              text: '$label: ',
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
            TextSpan(text: value),
          ],
        ),
      ),
    );
  }
}

class _ReadOnlySheet extends StatelessWidget {
  const _ReadOnlySheet({
    required this.title,
    required this.closeLabel,
    required this.child,
  });

  final String title;
  final String closeLabel;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.only(
          left: ClaraTokens.spaceMd,
          right: ClaraTokens.spaceMd,
          top: ClaraTokens.spaceMd,
          bottom:
              MediaQuery.of(context).viewInsets.bottom + ClaraTokens.spaceMd,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: ClaraTokens.spaceMd),
            Flexible(child: SingleChildScrollView(child: child)),
            const SizedBox(height: ClaraTokens.spaceMd),
            ClaraButton.secondary(
              label: closeLabel,
              onPressed: () => Navigator.of(context).pop(),
            ),
          ],
        ),
      ),
    );
  }
}

class _EditorSheetScaffold extends StatelessWidget {
  const _EditorSheetScaffold({
    required this.title,
    required this.saveLabel,
    required this.cancelLabel,
    required this.onSave,
    required this.children,
  });

  final String title;
  final String saveLabel;
  final String cancelLabel;
  final VoidCallback onSave;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.only(
          left: ClaraTokens.spaceMd,
          right: ClaraTokens.spaceMd,
          top: ClaraTokens.spaceMd,
          bottom:
              MediaQuery.of(context).viewInsets.bottom + ClaraTokens.spaceMd,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: ClaraTokens.spaceMd),
            Flexible(
              child: SingleChildScrollView(
                child: Column(children: children),
              ),
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            Row(
              children: [
                Expanded(
                  child: ClaraButton.secondary(
                    label: cancelLabel,
                    onPressed: () => Navigator.of(context).pop(),
                  ),
                ),
                const SizedBox(width: ClaraTokens.spaceSm),
                Expanded(
                  child: ClaraButton.primary(
                    label: saveLabel,
                    onPressed: onSave,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _AllergySheet extends StatefulWidget {
  const _AllergySheet({required this.strings, this.existing});

  final PhrStrings strings;
  final PhrAllergy? existing;

  @override
  State<_AllergySheet> createState() => _AllergySheetState();
}

class _AllergySheetState extends State<_AllergySheet> {
  late final TextEditingController _name;
  late final TextEditingController _reaction;
  late final TextEditingController _note;
  late String _severity;
  String? _error;

  @override
  void initState() {
    super.initState();
    final e = widget.existing;
    _name = TextEditingController(text: e?.name ?? '');
    _reaction = TextEditingController(text: e?.reaction ?? '');
    _note = TextEditingController(text: e?.note ?? '');
    _severity = e?.severity ?? 'unknown';
  }

  @override
  void dispose() {
    _name.dispose();
    _reaction.dispose();
    _note.dispose();
    super.dispose();
  }

  void _save() {
    final name = _name.text.trim();
    if (name.isEmpty) {
      setState(() => _error = widget.strings.nameRequired);
      return;
    }
    final e = widget.existing;
    Navigator.of(context).pop(
      PhrAllergy(
        id: e?.id ?? _mkId('allergy'),
        name: name,
        reaction: _reaction.text.trim(),
        severity: _severity,
        note: _note.text.trim(),
        informationSource: e?.informationSource ?? 'self-declared',
        verificationStatus: e?.verificationStatus ?? 'unconfirmed',
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.strings;
    return _EditorSheetScaffold(
      title: s.sectionAllergies,
      saveLabel: s.done,
      cancelLabel: s.cancel,
      onSave: _save,
      children: [
        ClaraInput(label: s.name, controller: _name, errorText: _error),
        const SizedBox(height: ClaraTokens.spaceSm),
        ClaraInput(label: s.reaction, controller: _reaction),
        const SizedBox(height: ClaraTokens.spaceSm),
        _SeverityDropdown(
          label: s.severity,
          value: _severity,
          options: kAllergySeverities,
          labelFor: s.severityLabel,
          onChanged: (v) => setState(() => _severity = v),
        ),
        const SizedBox(height: ClaraTokens.spaceSm),
        ClaraInput(label: s.note, controller: _note, maxLines: 2),
      ],
    );
  }
}

class _ConditionSheet extends StatefulWidget {
  const _ConditionSheet({required this.strings, this.existing});

  final PhrStrings strings;
  final PhrCondition? existing;

  @override
  State<_ConditionSheet> createState() => _ConditionSheetState();
}

class _ConditionSheetState extends State<_ConditionSheet> {
  late final TextEditingController _name;
  late final TextEditingController _diagnosedOn;
  late final TextEditingController _note;
  late String _status;
  String? _error;

  @override
  void initState() {
    super.initState();
    final e = widget.existing;
    _name = TextEditingController(text: e?.name ?? '');
    _diagnosedOn = TextEditingController(text: e?.diagnosedOn ?? '');
    _note = TextEditingController(text: e?.note ?? '');
    _status = e?.status ?? 'unknown';
  }

  @override
  void dispose() {
    _name.dispose();
    _diagnosedOn.dispose();
    _note.dispose();
    super.dispose();
  }

  void _save() {
    final name = _name.text.trim();
    if (name.isEmpty) {
      setState(() => _error = widget.strings.nameRequired);
      return;
    }
    final e = widget.existing;
    final diagnosed = _diagnosedOn.text.trim();
    Navigator.of(context).pop(
      PhrCondition(
        id: e?.id ?? _mkId('condition'),
        name: name,
        status: _status,
        diagnosedOn: diagnosed.isEmpty ? null : diagnosed,
        note: _note.text.trim(),
        informationSource: e?.informationSource ?? 'self-declared',
        verificationStatus: e?.verificationStatus ?? 'unconfirmed',
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.strings;
    return _EditorSheetScaffold(
      title: s.sectionConditions,
      saveLabel: s.done,
      cancelLabel: s.cancel,
      onSave: _save,
      children: [
        ClaraInput(label: s.name, controller: _name, errorText: _error),
        const SizedBox(height: ClaraTokens.spaceSm),
        _SeverityDropdown(
          label: s.clinicalStatus,
          value: _status,
          options: kConditionStatuses,
          labelFor: s.statusLabel,
          onChanged: (v) => setState(() => _status = v),
        ),
        const SizedBox(height: ClaraTokens.spaceSm),
        ClaraInput(
          label: s.diagnosedOn,
          hint: 'YYYY-MM-DD',
          controller: _diagnosedOn,
        ),
        const SizedBox(height: ClaraTokens.spaceSm),
        ClaraInput(label: s.note, controller: _note, maxLines: 2),
      ],
    );
  }
}

class _MedicationSheet extends StatefulWidget {
  const _MedicationSheet({required this.strings, this.existing});

  final PhrStrings strings;
  final PhrMedication? existing;

  @override
  State<_MedicationSheet> createState() => _MedicationSheetState();
}

class _MedicationSheetState extends State<_MedicationSheet> {
  late final TextEditingController _name;
  late final TextEditingController _dose;
  late final TextEditingController _frequency;
  late final TextEditingController _startedOn;
  late final TextEditingController _note;
  late bool _isCurrent;
  String? _error;

  @override
  void initState() {
    super.initState();
    final e = widget.existing;
    _name = TextEditingController(text: e?.name ?? '');
    _dose = TextEditingController(text: e?.dose ?? '');
    _frequency = TextEditingController(text: e?.frequency ?? '');
    _startedOn = TextEditingController(text: e?.startedOn ?? '');
    _note = TextEditingController(text: e?.note ?? '');
    _isCurrent = e?.isCurrent ?? true;
  }

  @override
  void dispose() {
    _name.dispose();
    _dose.dispose();
    _frequency.dispose();
    _startedOn.dispose();
    _note.dispose();
    super.dispose();
  }

  void _save() {
    final name = _name.text.trim();
    if (name.isEmpty) {
      setState(() => _error = widget.strings.nameRequired);
      return;
    }
    final e = widget.existing;
    final started = _startedOn.text.trim();
    Navigator.of(context).pop(
      PhrMedication(
        id: e?.id ?? _mkId('medication'),
        name: name,
        dose: _dose.text.trim(),
        frequency: _frequency.text.trim(),
        startedOn: started.isEmpty ? null : started,
        isCurrent: _isCurrent,
        note: _note.text.trim(),
        informationSource: e?.informationSource ?? 'self-declared',
        verificationStatus: e?.verificationStatus ?? 'unconfirmed',
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.strings;
    return _EditorSheetScaffold(
      title: s.sectionMedications,
      saveLabel: s.done,
      cancelLabel: s.cancel,
      onSave: _save,
      children: [
        ClaraInput(label: s.name, controller: _name, errorText: _error),
        const SizedBox(height: ClaraTokens.spaceSm),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(child: ClaraInput(label: s.dose, controller: _dose)),
            const SizedBox(width: ClaraTokens.spaceSm),
            Expanded(
              child: ClaraInput(label: s.frequency, controller: _frequency),
            ),
          ],
        ),
        const SizedBox(height: ClaraTokens.spaceSm),
        ClaraInput(
          label: s.startedOn,
          hint: 'YYYY-MM-DD',
          controller: _startedOn,
        ),
        const SizedBox(height: ClaraTokens.spaceSm),
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: Text(s.isCurrent),
          value: _isCurrent,
          onChanged: (v) => setState(() => _isCurrent = v),
        ),
        ClaraInput(label: s.note, controller: _note, maxLines: 2),
      ],
    );
  }
}

class _SeverityDropdown extends StatelessWidget {
  const _SeverityDropdown({
    required this.label,
    required this.value,
    required this.options,
    required this.labelFor,
    required this.onChanged,
  });

  final String label;
  final String value;
  final List<String> options;
  final String Function(String) labelFor;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return InputDecorator(
      decoration: InputDecoration(labelText: label),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          value: value,
          isExpanded: true,
          onChanged: (v) {
            if (v != null) onChanged(v);
          },
          items: [
            for (final o in options)
              DropdownMenuItem<String>(value: o, child: Text(labelFor(o))),
          ],
        ),
      ),
    );
  }
}

String _mkId(String prefix) =>
    '${prefix}_${DateTime.now().microsecondsSinceEpoch}';
