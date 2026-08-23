import 'package:flutter/material.dart';

import '../theme/tokens.dart';

/// The 4 presentation modes in CLARA (Web & Mobile parity).
///
/// A presentation mode is purely a UI layout and navigation context:
/// - Personal: consumer-focused health journey, today tasks, medicines, personal PHR
/// - Clinical: clinician-focused tools (Scribe, Council, clinical notes)
/// - Research: evidence synthesis, research source hub, PubMed verification
/// - Administration: operational telemetry, system configuration, compliance DSAR
///
/// INVARIANT:
/// Server RBAC authorization is locked and authoritative. Changing the presentation
/// mode modifies ONLY client view presentation and NEVER alters user roles,
/// permissions, or backend authorization gates.
enum PresentationMode {
  personal,
  clinical,
  research,
  admin,
}

/// Permitted presentation modes by authenticated user role.
///
/// All professional roles (doctor, researcher, admin) are permitted to switch
/// to the Personal presentation view.
const Map<String, List<PresentationMode>> kPermittedModesByRole = {
  'normal': [PresentationMode.personal],
  'researcher': [PresentationMode.personal, PresentationMode.research],
  'doctor': [
    PresentationMode.personal,
    PresentationMode.clinical,
    PresentationMode.research,
  ],
  'admin': [
    PresentationMode.personal,
    PresentationMode.clinical,
    PresentationMode.research,
    PresentationMode.admin,
  ],
};

/// Default presentation mode mapping by user role:
/// - normal -> Personal
/// - doctor -> Clinical
/// - researcher -> Research
/// - admin -> Administration
PresentationMode defaultModeForRole(String? role) {
  switch (role?.trim().toLowerCase()) {
    case 'doctor':
      return PresentationMode.clinical;
    case 'researcher':
      return PresentationMode.research;
    case 'admin':
      return PresentationMode.admin;
    case 'normal':
    default:
      return PresentationMode.personal;
  }
}

/// Returns the list of permitted presentation modes for [role].
List<PresentationMode> permittedModesForRole(String? role) {
  final normalized = role?.trim().toLowerCase() ?? 'normal';
  return kPermittedModesByRole[normalized] ?? const [PresentationMode.personal];
}

/// Checks if [mode] is permitted for the given [role].
bool isModePermittedForRole(PresentationMode mode, String? role) {
  return permittedModesForRole(role).contains(mode);
}

/// Metadata describing a presentation mode (Vietnamese-first with English fallback).
class PresentationModeMeta {
  const PresentationModeMeta({
    required this.mode,
    required this.labelVi,
    required this.labelEn,
    required this.icon,
  });

  final PresentationMode mode;
  final String labelVi;
  final String labelEn;
  final IconData icon;

  String label(String? languageCode) =>
      languageCode == 'en' ? labelEn : labelVi;
}

const Map<PresentationMode, PresentationModeMeta> kPresentationModeMeta = {
  PresentationMode.personal: PresentationModeMeta(
    mode: PresentationMode.personal,
    labelVi: 'Cá nhân',
    labelEn: 'Personal',
    icon: Icons.person_outline,
  ),
  PresentationMode.clinical: PresentationModeMeta(
    mode: PresentationMode.clinical,
    labelVi: 'Lâm sàng',
    labelEn: 'Clinical',
    icon: Icons.medical_services_outlined,
  ),
  PresentationMode.research: PresentationModeMeta(
    mode: PresentationMode.research,
    labelVi: 'Nghiên cứu',
    labelEn: 'Research',
    icon: Icons.science_outlined,
  ),
  PresentationMode.admin: PresentationModeMeta(
    mode: PresentationMode.admin,
    labelVi: 'Quản trị',
    labelEn: 'Administration',
    icon: Icons.admin_panel_settings_outlined,
  ),
};

/// Controller managing client presentation mode.
///
/// Server RBAC is authoritative and locked to the session token; switching
/// [mode] changes only client presentation and never grants unauthorized
/// capabilities or alters backend roles.
class PresentationModeController extends ChangeNotifier {
  PresentationModeController({String? initialRole}) {
    _role = initialRole;
    _mode = defaultModeForRole(initialRole);
  }

  String? _role;
  late PresentationMode _mode;

  PresentationMode get mode => _mode;
  String? get role => _role;

  List<PresentationMode> get permittedModes => permittedModesForRole(_role);

  bool get canSwitchModes => permittedModes.length > 1;

  void updateRole(String? newRole) {
    if (_role == newRole) return;
    _role = newRole;
    if (!isModePermittedForRole(_mode, newRole)) {
      _mode = defaultModeForRole(newRole);
    }
    notifyListeners();
  }

  bool setMode(PresentationMode nextMode) {
    if (!isModePermittedForRole(nextMode, _role)) {
      return false;
    }
    if (_mode == nextMode) return true;
    _mode = nextMode;
    notifyListeners();
    return true;
  }
}

/// Full screen route wrapper for the presentation mode selector.
class PresentationModeScreen extends StatelessWidget {
  const PresentationModeScreen({
    super.key,
    required this.controller,
    this.languageCode = 'vi',
  });

  final PresentationModeController controller;
  final String languageCode;

  @override
  Widget build(BuildContext context) {
    final isEnglish = languageCode == 'en';
    return Scaffold(
      appBar: AppBar(
        title: Text(isEnglish ? 'Workspace Mode' : 'Không gian làm việc'),
      ),
      body: PresentationModeSelectorSheet(
        controller: controller,
        languageCode: languageCode,
      ),
    );
  }
}

/// UI sheet allowing doctors, researchers, and administrators to select a permitted mode.
class PresentationModeSelectorSheet extends StatelessWidget {
  const PresentationModeSelectorSheet({
    super.key,
    required this.controller,
    this.languageCode = 'vi',
  });

  final PresentationModeController controller;
  final String languageCode;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final permitted = controller.permittedModes;
    final isEnglish = languageCode == 'en';

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: ClaraTokens.spaceMd,
          vertical: ClaraTokens.spaceLg,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              isEnglish ? 'Workspace Mode' : 'Không gian làm việc',
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: ClaraTokens.spaceXs),
            Text(
              isEnglish
                  ? 'Switching presentation mode changes view layout only. Server authorization remains locked.'
                  : 'Chuyển không gian làm việc chỉ thay đổi giao diện hiển thị. Quyền hạn máy chủ được giữ nguyên.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            for (final mode in permitted) ...[
              _ModeTile(
                meta: kPresentationModeMeta[mode]!,
                selected: controller.mode == mode,
                languageCode: languageCode,
                onTap: () {
                  controller.setMode(mode);
                  Navigator.of(context).pop();
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

class _ModeTile extends StatelessWidget {
  const _ModeTile({
    required this.meta,
    required this.selected,
    required this.languageCode,
    required this.onTap,
  });

  final PresentationModeMeta meta;
  final bool selected;
  final String languageCode;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Material(
      color: selected
          ? theme.colorScheme.primaryContainer.withValues(alpha: 0.25)
          : theme.colorScheme.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
        side: BorderSide(
          color: selected
              ? theme.colorScheme.primary
              : theme.colorScheme.outlineVariant,
          width: selected ? 2 : 1,
        ),
      ),
      child: ListTile(
        leading: Icon(
          meta.icon,
          color: selected
              ? theme.colorScheme.primary
              : theme.colorScheme.onSurfaceVariant,
        ),
        title: Text(
          meta.label(languageCode),
          style: theme.textTheme.bodyMedium?.copyWith(
            fontWeight: selected ? FontWeight.bold : FontWeight.normal,
            color: selected
                ? theme.colorScheme.primary
                : theme.colorScheme.onSurface,
          ),
        ),
        trailing: selected
            ? Icon(Icons.check_circle, color: theme.colorScheme.primary)
            : null,
        onTap: onTap,
      ),
    );
  }
}
