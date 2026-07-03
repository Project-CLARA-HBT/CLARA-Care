// PHR surface for the CLARA_Mobile redesign (Experience_V3).
//
// clara-mobile-redesign, Requirement 7 (easier-to-use PHR) + the regression-
// locked safety invariants (persistent decision-support disclaimer INV-7,
// no-PII count-only analytics, Vietnamese-first copy, ≥48dp tap targets, text
// scaler, reduced motion, status by text not color alone).
//
// This rebuilds the PHR into a polished, card-sectioned surface on the shared
// V3 design system (`SectionHeader` + `ClaraCard` + `ClaraButton` + `ClaraInput`
// + `ClaraChip`), replacing the raw-Material legacy form. It reuses the legacy
// data contract verbatim by importing the public models/strings from
// `screens/phr_screen.dart` (`PhrRecordModel`, `PhrAllergy`, `PhrCondition`,
// `PhrMedication`, `PhrStrings`, `PhrEmergencyCardProjection`, the severity/
// status vocab), so it talks to the same GET/PUT `/phr/record` endpoints with
// no contract change.
//
//   * Profile card — quick-edit basics (name, dob, gender, blood type, height,
//     weight, phone, address, emergency contact, insurance, notes).
//   * Allergies / Conditions / Medications — card lists with per-entry
//     provenance + verification chips, add/edit via a bottom-sheet editor, and
//     delete-with-confirm.
//   * Enhanced reads (export + emergency card) gated behind
//     `phr_enhanced_mobile_enabled`; base PHR is always available.
//
// No-PII analytics: only the view event and a single total `entry_count` on
// save — never names, free text, or medical values.

import 'dart:convert';

import 'package:flutter/material.dart';

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

/// The redesigned PHR ("Hồ sơ sức khỏe") surface. See file header.
class PhrSurfaceV3 extends StatefulWidget {
  const PhrSurfaceV3({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    required this.resolver,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;
  final MobileFeatureFlagResolver resolver;

  @override
  State<PhrSurfaceV3> createState() => _PhrSurfaceV3State();
}

class _PhrSurfaceV3State extends State<PhrSurfaceV3> {
  static const PhrStrings _s = PhrStrings(PhrLang.vi);

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
    _load();
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
      // No-PII analytics: a single total entry count only (category-specific
      // keys would be stripped by the PII filter anyway).
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

  @override
  Widget build(BuildContext context) {
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
          SectionHeader(title: _s.sectionProfile),
          _buildProfileCard(),
          SectionHeader(
            title: _s.sectionAllergies,
            trailing: _AddButton(onPressed: () => _editAllergy(null)),
          ),
          _buildAllergyList(record),
          SectionHeader(
            title: _s.sectionConditions,
            trailing: _AddButton(onPressed: () => _editCondition(null)),
          ),
          _buildConditionList(record),
          SectionHeader(
            title: _s.sectionMedications,
            trailing: _AddButton(onPressed: () => _editMedication(null)),
          ),
          _buildMedicationList(record),
        ],
      ),
    );
  }

  // --- Profile -----------------------------------------------------------------

  Widget _buildProfileCard() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
      child: ClaraCard.static_(
        semanticLabel: _s.sectionProfile,
        child: Column(
          children: [
            ClaraInput(label: _s.fullName, controller: _fullName),
            const SizedBox(height: ClaraTokens.spaceSm),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: ClaraInput(
                    label: _s.dateOfBirth,
                    hint: 'YYYY-MM-DD',
                    controller: _dob,
                  ),
                ),
                const SizedBox(width: ClaraTokens.spaceSm),
                Expanded(
                    child: ClaraInput(label: _s.gender, controller: _gender)),
              ],
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child:
                      ClaraInput(label: _s.bloodType, controller: _bloodType),
                ),
                const SizedBox(width: ClaraTokens.spaceSm),
                Expanded(
                  child: ClaraInput(
                    label: _s.heightCm,
                    controller: _height,
                    keyboardType: TextInputType.number,
                  ),
                ),
                const SizedBox(width: ClaraTokens.spaceSm),
                Expanded(
                  child: ClaraInput(
                    label: _s.weightKg,
                    controller: _weight,
                    keyboardType: TextInputType.number,
                  ),
                ),
              ],
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            ClaraInput(
              label: _s.phone,
              controller: _phone,
              keyboardType: TextInputType.phone,
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            ClaraInput(label: _s.address, controller: _address),
            const SizedBox(height: ClaraTokens.spaceSm),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: ClaraInput(
                    label: _s.emergencyContactName,
                    controller: _emName,
                  ),
                ),
                const SizedBox(width: ClaraTokens.spaceSm),
                Expanded(
                  child: ClaraInput(
                    label: _s.emergencyContactPhone,
                    controller: _emPhone,
                    keyboardType: TextInputType.phone,
                  ),
                ),
              ],
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            ClaraInput(label: _s.insuranceId, controller: _insurance),
            const SizedBox(height: ClaraTokens.spaceSm),
            ClaraInput(label: _s.notes, controller: _notes, maxLines: 3),
          ],
        ),
      ),
    );
  }

  // --- Entry lists -------------------------------------------------------------

  Widget _sectionPadding(Widget child) => Padding(
        padding: const EdgeInsets.fromLTRB(
          ClaraTokens.spaceMd,
          0,
          ClaraTokens.spaceMd,
          ClaraTokens.spaceSm,
        ),
        child: child,
      );

  // The empty-section placeholder is pure chrome (a no-entries hint, not a
  // clinical value), so it may sit on a liquid-glass surface. When the ambient
  // GlassScope is off the same card renders opaque with identical geometry. All
  // clinical PHR surfaces (profile, entry cards, disclaimer) stay on opaque
  // ClaraCard and are never placed on translucent glass (R11).
  Widget _emptyCard() => _sectionPadding(
        GlassSurface(
          blurSigma: GlassTokens.blurCard,
          radius: GlassTokens.radiusCard,
          fill: GlassFill.regular,
          padding: const EdgeInsets.all(ClaraTokens.spaceMd),
          child: Text(
            _s.emptySection,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
          ),
        ),
      );

  Widget _buildAllergyList(PhrRecordModel record) {
    if (record.allergies.isEmpty) return _emptyCard();
    return Column(
      children: [
        for (final a in record.allergies)
          _sectionPadding(
            _EntryCard(
              title: a.name,
              subtitle: [
                if (a.reaction.isNotEmpty) a.reaction,
                _s.severityLabel(a.severity),
              ].join(' · '),
              source: _s.sourceLabel(a.informationSource),
              verification: _s.verificationLabel(a.verificationStatus),
              onEdit: () => _editAllergy(a),
              onDelete: () => setState(() => record.allergies.remove(a)),
            ),
          ),
      ],
    );
  }

  Widget _buildConditionList(PhrRecordModel record) {
    if (record.conditions.isEmpty) return _emptyCard();
    return Column(
      children: [
        for (final c in record.conditions)
          _sectionPadding(
            _EntryCard(
              title: c.name,
              subtitle: [
                _s.statusLabel(c.status),
                if ((c.diagnosedOn ?? '').isNotEmpty) c.diagnosedOn!,
              ].join(' · '),
              source: _s.sourceLabel(c.informationSource),
              verification: _s.verificationLabel(c.verificationStatus),
              onEdit: () => _editCondition(c),
              onDelete: () => setState(() => record.conditions.remove(c)),
            ),
          ),
      ],
    );
  }

  Widget _buildMedicationList(PhrRecordModel record) {
    if (record.medications.isEmpty) return _emptyCard();
    return Column(
      children: [
        for (final m in record.medications)
          _sectionPadding(
            _EntryCard(
              title: m.name,
              subtitle: [
                if (m.dose.isNotEmpty) m.dose,
                if (m.frequency.isNotEmpty) m.frequency,
                if (m.isCurrent) _s.isCurrent,
              ].join(' · '),
              source: _s.sourceLabel(m.informationSource),
              verification: _s.verificationLabel(m.verificationStatus),
              onEdit: () => _editMedication(m),
              onDelete: () => setState(() => record.medications.remove(m)),
            ),
          ),
      ],
    );
  }

  // --- Editors (bottom sheets) -------------------------------------------------

  Future<void> _editAllergy(PhrAllergy? existing) async {
    final record = _record;
    if (record == null) return;
    final result = await showModalBottomSheet<PhrAllergy>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _AllergySheet(strings: _s, existing: existing),
    );
    if (result == null) return;
    setState(() {
      if (existing == null) {
        record.allergies.add(result);
      } else {
        final i = record.allergies.indexOf(existing);
        if (i >= 0) record.allergies[i] = result;
      }
    });
  }

  Future<void> _editCondition(PhrCondition? existing) async {
    final record = _record;
    if (record == null) return;
    final result = await showModalBottomSheet<PhrCondition>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _ConditionSheet(strings: _s, existing: existing),
    );
    if (result == null) return;
    setState(() {
      if (existing == null) {
        record.conditions.add(result);
      } else {
        final i = record.conditions.indexOf(existing);
        if (i >= 0) record.conditions[i] = result;
      }
    });
  }

  Future<void> _editMedication(PhrMedication? existing) async {
    final record = _record;
    if (record == null) return;
    final result = await showModalBottomSheet<PhrMedication>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _MedicationSheet(strings: _s, existing: existing),
    );
    if (result == null) return;
    setState(() {
      if (existing == null) {
        record.medications.add(result);
      } else {
        final i = record.medications.indexOf(existing);
        if (i >= 0) record.medications[i] = result;
      }
    });
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

// --- Shared small widgets ------------------------------------------------------

class _AddButton extends StatelessWidget {
  const _AddButton({required this.onPressed});

  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return TextButton.icon(
      onPressed: onPressed,
      icon: const Icon(Icons.add, size: 18),
      label: const Text('Thêm'),
    );
  }
}

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
    required this.onEdit,
    required this.onDelete,
  });

  final String title;
  final String subtitle;
  final String source;
  final String verification;
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
                tooltip: 'Sửa',
                icon: const Icon(Icons.edit_outlined, size: 20),
                onPressed: onEdit,
              ),
              IconButton(
                tooltip: 'Xóa',
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

// --- Editor sheets -------------------------------------------------------------

/// Shared scaffold for a bottom-sheet entry editor.
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

/// A themed dropdown for a fixed vocabulary (severity/status), labeled via the
/// shared `PhrStrings` helpers so copy stays Vietnamese-first.
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

/// Client-side entry id for a newly added entry. The `PUT /record` contract
/// requires a non-empty id per item (max 64 chars).
String _mkId(String prefix) =>
    '${prefix}_${DateTime.now().microsecondsSinceEpoch}';
