// Unified Settings surface for CLARA_Mobile (Spec v5 Section 7.9).
//
// Features:
//   * Theme selector: Light / Dark / System modes driven by [ThemeController].
//   * Biometric authentication: FaceID / Fingerprint toggle.
//   * Offline cache purge: Purges LifeMap and Careguard offline cached projections.
//   * Security sessions: Current identity info, device session state, and sign-out.
//   * Language switcher: Vietnamese / English selection via [LanguageController].
//   * Notifications shortcut: Direct navigation to [NotificationsSurface].
//   * Safety copy & disclosures: AI transparency notice, Privacy & consent, About.

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../../core/ai_transparency_notice.dart';
import '../../core/api_client.dart';
import '../../core/careguard_offline_cache.dart';
import '../../core/consumer_terminology.dart';
import '../../core/lifemap_read_cache.dart';
import '../../core/session_store.dart';
import '../../theme/components/clara_button.dart';
import '../../theme/components/section_header.dart';
import '../../theme/glass/glass_surface.dart';
import '../../theme/glass/glass_tokens.dart';
import '../../theme/tokens.dart';
import '../language_controller.dart';
import '../presentation_mode.dart';
import '../settings/language_toggle.dart';
import '../theme_controller.dart';
import 'notifications_surface.dart';

/// Storage key for biometric authentication preference.
const String kSettingsBiometricKey = 'clara.settings.biometric_enabled';

/// The unified Settings ("Cài đặt") surface (Spec v5 Section 7.9).
class SettingsSurface extends StatefulWidget {
  const SettingsSurface({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    this.themeController,
    this.languageController,
    this.presentationModeController,
    this.lifeMapReadCache,
    this.secureStorage,
    this.initialBiometricEnabled = false,
    this.onCachePurged,
    this.onNotificationsTap,
  });

  /// API client for server-side logout and session management.
  final ApiClient apiClient;

  /// The persistent session/credential store.
  final SessionStore sessionStore;

  /// App-wide theme-mode state. When null, appearance choices are hidden.
  final ThemeController? themeController;

  /// App-wide language state. When null, language choices are hidden.
  final LanguageController? languageController;

  /// Optional presentation mode controller for role-gated mode switching.
  final PresentationModeController? presentationModeController;

  /// Optional offline read cache for LifeMap projections.
  final LifeMapReadCache? lifeMapReadCache;

  /// Optional storage interface for cache deletion.
  final SessionSecureStorage? secureStorage;

  /// Initial biometric enabled state.
  final bool initialBiometricEnabled;

  /// Optional callback invoked after the offline cache is purged.
  final VoidCallback? onCachePurged;

  /// Optional callback or navigation override for notifications settings.
  final VoidCallback? onNotificationsTap;

  @override
  State<SettingsSurface> createState() => _SettingsSurfaceState();
}

class _SettingsSurfaceState extends State<SettingsSurface> {
  late bool _biometricEnabled = widget.initialBiometricEnabled;
  bool _isPurgingCache = false;

  Future<void> _toggleBiometric(bool value) async {
    setState(() {
      _biometricEnabled = value;
    });
  }

  Future<void> _purgeOfflineCache(ConsumerTerminology copy) async {
    final isEnglish = copy.locale == 'en';
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(isEnglish ? 'Purge Offline Cache' : 'Xóa bộ nhớ đệm ngoại tuyến'),
        content: Text(
          isEnglish
              ? 'Are you sure you want to purge all offline cached health records and medication data on this device?'
              : 'Bạn có chắc chắn muốn xóa toàn bộ bản sao ngoại tuyến của hồ sơ sức khỏe và dữ liệu thuốc trên thiết bị này không?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: Text(copy[ConsumerTerm.settingsCancel]),
          ),
          TextButton(
            key: const Key('confirm-purge-cache-dialog-button'),
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: Text(isEnglish ? 'Purge' : 'Xóa dữ liệu'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    setState(() {
      _isPurgingCache = true;
    });

    try {
      if (widget.lifeMapReadCache != null) {
        await widget.lifeMapReadCache!.save(const <String, dynamic>{}, validity: Duration.zero);
      }
      
      final storage = widget.secureStorage;
      if (storage != null) {
        final userId = widget.sessionStore.userId ?? widget.sessionStore.email;
        await storage.delete(LifeMapReadCache.storageKey);
        await storage.delete(CareguardOfflineCache.storageKey);
        if (userId != null && userId.isNotEmpty) {
          await storage.delete(LifeMapReadCache.scopedStorageKey(userId));
          await storage.delete(CareguardOfflineCache.scopedStorageKey(userId));
        }
      }

      widget.onCachePurged?.call();

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              isEnglish
                  ? 'Offline cache purged successfully.'
                  : 'Đã xóa bộ nhớ đệm ngoại tuyến thành công.',
            ),
          ),
        );
      }
    } catch (_) {
      // Fail closed, silent handle
    } finally {
      if (mounted) {
        setState(() {
          _isPurgingCache = false;
        });
      }
    }
  }

  Future<void> _signOut() async {
    final token = widget.sessionStore.accessToken;
    try {
      await widget.apiClient.logout(accessToken: token);
    } catch (_) {
      // Best-effort server logout
    }
    await widget.sessionStore.clear();
  }

  Future<void> _confirmSignOut(BuildContext context, ConsumerTerminology copy) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(copy[ConsumerTerm.settingsSignOutConfirmTitle]),
        content: Text(copy[ConsumerTerm.settingsSignOutConfirmDescription]),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: Text(copy[ConsumerTerm.settingsCancel]),
          ),
          TextButton(
            key: const Key('confirm-sign-out-dialog-button'),
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: Text(copy[ConsumerTerm.settingsSignOut]),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      await _signOut();
    }
  }

  Future<void> _revokeOtherSessions(ConsumerTerminology copy) async {
    final isEnglish = copy.locale == 'en';
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(isEnglish ? 'Revoke Other Sessions' : 'Đăng xuất các thiết bị khác'),
        content: Text(
          isEnglish
              ? 'This will invalidate all active sign-in sessions on other phones and web browsers.'
              : 'Thao tác này sẽ chấm dứt mọi phiên đăng nhập đang hoạt động trên các điện thoại và trình duyệt web khác.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: Text(copy[ConsumerTerm.settingsCancel]),
          ),
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: Text(isEnglish ? 'Revoke All' : 'Chấm dứt tất cả'),
          ),
        ],
      ),
    );
    if (confirmed == true && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            isEnglish
                ? 'All other active sessions have been revoked.'
                : 'Đã chấm dứt tất cả các phiên đăng nhập khác.',
          ),
        ),
      );
    }
  }

  void _openNotifications(BuildContext context) {
    if (widget.onNotificationsTap != null) {
      widget.onNotificationsTap!();
      return;
    }
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => NotificationsSurface(
          apiClient: widget.apiClient,
          sessionStore: widget.sessionStore,
          languageController: widget.languageController,
        ),
      ),
    );
  }

  void _openModePicker(BuildContext context, PresentationModeController controller, ConsumerTerminology copy) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Theme.of(context).colorScheme.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(ClaraTokens.radiusLg)),
      ),
      builder: (_) => PresentationModeSelectorSheet(
        controller: controller,
        languageCode: copy.locale,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final controller = widget.languageController;
    if (controller == null) {
      return _buildLocalized(context, ConsumerTerminology.forLocale(null));
    }
    return AnimatedBuilder(
      animation: controller,
      builder: (context, _) => _buildLocalized(
        context,
        ConsumerTerminology.forLocale(controller.languageCode),
      ),
    );
  }

  Widget _buildLocalized(BuildContext context, ConsumerTerminology copy) {
    final isEnglish = copy.locale == 'en';
    return Scaffold(
      appBar: AppBar(title: Text(copy[ConsumerTerm.settingsTitle])),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.only(bottom: ClaraTokens.spaceXl),
          children: [
            if (widget.themeController != null)
              _ThemeSection(controller: widget.themeController!, copy: copy),
            if (widget.languageController != null)
              LanguageToggle(controller: widget.languageController!),
            
            // Security & Sessions Section (Spec v5 Section 7.9)
            _SecuritySessionsSection(
              sessionStore: widget.sessionStore,
              copy: copy,
              onSignOut: () => _confirmSignOut(context, copy),
              onRevokeOtherSessions: () => _revokeOtherSessions(copy),
              presentationModeController: widget.presentationModeController,
              onOpenModePicker: (modeCtrl) => _openModePicker(context, modeCtrl, copy),
            ),

            _PrivacySection(copy: copy),

            // Biometric Authentication Section (Spec v5 Section 7.9)
            _BiometricSection(
              enabled: _biometricEnabled,
              onChanged: _toggleBiometric,
              isEnglish: isEnglish,
            ),

            // Offline Cache Purge Section (Spec v5 Section 7.9)
            _OfflineCacheSection(
              isPurging: _isPurgingCache,
              onPurge: () => _purgeOfflineCache(copy),
              isEnglish: isEnglish,
            ),

            // Notifications Shortcut
            _NotificationsEntrySection(
              onTap: () => _openNotifications(context),
              isEnglish: isEnglish,
            ),

            _TransparencySection(copy: copy, locale: copy.locale),
            _AboutSection(copy: copy),
            _HelpSection(copy: copy),
          ],
        ),
      ),
    );
  }
}

/// Shared wrapper for settings groups.
class _SettingsGroup extends StatelessWidget {
  const _SettingsGroup({
    required this.title,
    required this.child,
    this.clinical = false,
  });

  final String title;
  final Widget child;
  final bool clinical;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        SectionHeader(title: title),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
          child: A11yLabeled(
            label: title,
            child: GlassSurface(
              blurSigma: GlassTokens.blurCard,
              radius: GlassTokens.radiusCard,
              fill: GlassFill.regular,
              clinical: clinical,
              padding: const EdgeInsets.all(ClaraTokens.spaceMd),
              child: Material(
                type: MaterialType.transparency,
                child: child,
              ),
            ),
          ),
        ),
      ],
    );
  }
}

// --- Giao diện (Theme / Appearance) ------------------------------------------

class _ThemeOption {
  const _ThemeOption(this.mode, this.label, this.icon);

  final ThemeMode mode;
  final String label;
  final IconData icon;
}

class _ThemeSection extends StatelessWidget {
  const _ThemeSection({required this.controller, required this.copy});

  final ThemeController controller;
  final ConsumerTerminology copy;

  @override
  Widget build(BuildContext context) {
    final textScaler = A11y.resolveTextScaler(context);
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        final selected = controller.themeMode;
        final options = <_ThemeOption>[
          _ThemeOption(
            ThemeMode.light,
            copy[ConsumerTerm.settingsThemeLight],
            Icons.light_mode_outlined,
          ),
          _ThemeOption(
            ThemeMode.dark,
            copy[ConsumerTerm.settingsThemeDark],
            Icons.dark_mode_outlined,
          ),
          _ThemeOption(
            ThemeMode.system,
            copy[ConsumerTerm.settingsThemeSystem],
            Icons.settings_suggest_outlined,
          ),
        ];
        return _SettingsGroup(
          title: copy[ConsumerTerm.settingsAppearanceTitle],
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: ClaraTokens.spaceXs),
            child: RadioGroup<ThemeMode>(
              groupValue: selected,
              onChanged: (value) {
                if (value != null) {
                  controller.setThemeMode(value);
                }
              },
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  for (final option in options)
                    _ThemeRadioTile(
                      option: option,
                      groupValue: selected,
                      textScaler: textScaler,
                      selectedSuffix: copy[ConsumerTerm.settingsSelected],
                      notSelectedSuffix: copy[ConsumerTerm.settingsNotSelected],
                    ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

class _ThemeRadioTile extends StatelessWidget {
  const _ThemeRadioTile({
    required this.option,
    required this.groupValue,
    required this.textScaler,
    required this.selectedSuffix,
    required this.notSelectedSuffix,
  });

  final _ThemeOption option;
  final ThemeMode groupValue;
  final TextScaler textScaler;
  final String selectedSuffix;
  final String notSelectedSuffix;

  @override
  Widget build(BuildContext context) {
    final isSelected = option.mode == groupValue;
    final selectedLabel = isSelected ? selectedSuffix : notSelectedSuffix;

    return Semantics(
      inMutuallyExclusiveGroup: true,
      selected: isSelected,
      button: true,
      label: '${option.label}, $selectedLabel',
      child: ExcludeSemantics(
        child: ConstrainedBox(
          constraints: const BoxConstraints(
            minHeight: A11y.minTapTargetDimension,
          ),
          child: RadioListTile<ThemeMode>(
            key: Key('theme-option-${option.mode.name}'),
            value: option.mode,
            controlAffinity: ListTileControlAffinity.trailing,
            secondary: Icon(option.icon),
            title: Text(option.label, textScaler: textScaler),
          ),
        ),
      ),
    );
  }
}

// --- Biometric Authentication (FaceID / Fingerprint) ------------------------

class _BiometricSection extends StatelessWidget {
  const _BiometricSection({
    required this.enabled,
    required this.onChanged,
    required this.isEnglish,
  });

  final bool enabled;
  final ValueChanged<bool> onChanged;
  final bool isEnglish;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final textScaler = A11y.resolveTextScaler(context);
    final title = isEnglish ? 'Biometric Security' : 'Bảo mật sinh trắc học';
    final subtitle = isEnglish
        ? 'Use FaceID or Fingerprint for quick unlock and medical data privacy.'
        : 'Sử dụng FaceID hoặc Vân tay để mở khóa nhanh và bảo vệ quyền riêng tư hồ sơ y tế.';

    return _SettingsGroup(
      title: title,
      child: SwitchListTile.adaptive(
        key: const Key('settings-biometric-switch'),
        value: enabled,
        onChanged: onChanged,
        secondary: Icon(Icons.fingerprint_rounded, color: theme.colorScheme.primary),
        title: Text(
          isEnglish ? 'Biometric Authentication (FaceID / Fingerprint)' : 'Xác thực sinh trắc học (FaceID / Vân tay)',
          style: theme.textTheme.titleSmall,
          textScaler: textScaler,
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 4.0),
          child: Text(
            subtitle,
            style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            textScaler: textScaler,
          ),
        ),
      ),
    );
  }
}

// --- Offline Cache Purge -----------------------------------------------------

class _OfflineCacheSection extends StatelessWidget {
  const _OfflineCacheSection({
    required this.isPurging,
    required this.onPurge,
    required this.isEnglish,
  });

  final bool isPurging;
  final VoidCallback onPurge;
  final bool isEnglish;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final textScaler = A11y.resolveTextScaler(context);
    final title = isEnglish ? 'Offline Cache' : 'Bộ nhớ đệm ngoại tuyến';

    return _SettingsGroup(
      title: title,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.cached_outlined, size: 20, color: theme.colorScheme.onSurfaceVariant),
              const SizedBox(width: ClaraTokens.spaceMd),
              Expanded(
                child: Text(
                  isEnglish
                      ? 'Cached projections of your LifeMap and medication safety reviews are stored on this device for offline access.'
                      : 'Bản sao ngoại tuyến của LifeMap và kiểm tra an toàn thuốc được lưu trên thiết bị để xem khi không có mạng.',
                  style: theme.textTheme.bodyMedium,
                  textScaler: textScaler,
                ),
              ),
            ],
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          Align(
            alignment: Alignment.centerLeft,
            child: ClaraButton.secondary(
              key: const Key('settings-purge-cache-button'),
              label: isEnglish ? 'Purge Offline Cache' : 'Xóa bộ nhớ đệm ngoại tuyến',
              icon: Icons.delete_sweep_outlined,
              loading: isPurging,
              onPressed: onPurge,
            ),
          ),
        ],
      ),
    );
  }
}

// --- Notifications Shortcut --------------------------------------------------

class _NotificationsEntrySection extends StatelessWidget {
  const _NotificationsEntrySection({
    required this.onTap,
    required this.isEnglish,
  });

  final VoidCallback onTap;
  final bool isEnglish;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final textScaler = A11y.resolveTextScaler(context);
    final title = isEnglish ? 'Notifications' : 'Thông báo';

    return _SettingsGroup(
      title: title,
      child: ListTile(
        key: const Key('settings-notifications-tile'),
        contentPadding: EdgeInsets.zero,
        leading: Icon(Icons.notifications_outlined, color: theme.colorScheme.primary),
        title: Text(
          isEnglish ? 'Notification Preferences' : 'Tùy chọn thông báo',
          style: theme.textTheme.titleSmall,
          textScaler: textScaler,
        ),
        subtitle: Text(
          isEnglish
              ? 'Medication reminders, care journey alerts, family updates'
              : 'Lịch uống thuốc, cảnh báo hành trình chăm sóc, cập nhật gia đình',
          style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
          textScaler: textScaler,
        ),
        trailing: const Icon(Icons.chevron_right),
        onTap: onTap,
      ),
    );
  }
}

// --- Security Sessions (Phiên đăng nhập & Bảo mật) ---------------------------

class _SecuritySessionsSection extends StatelessWidget {
  const _SecuritySessionsSection({
    required this.sessionStore,
    required this.copy,
    required this.onSignOut,
    required this.onRevokeOtherSessions,
    this.presentationModeController,
    this.onOpenModePicker,
  });

  final SessionStore sessionStore;
  final ConsumerTerminology copy;
  final VoidCallback onSignOut;
  final VoidCallback onRevokeOtherSessions;
  final PresentationModeController? presentationModeController;
  final void Function(PresentationModeController)? onOpenModePicker;

  @override
  Widget build(BuildContext context) {
    final isEnglish = copy.locale == 'en';
    final listenables = <Listenable>[
      sessionStore,
      if (presentationModeController != null) presentationModeController!,
    ];

    return ListenableBuilder(
      listenable: Listenable.merge(listenables),
      builder: (context, _) {
        final email = sessionStore.email;
        final role = sessionStore.role;
        final modeController = presentationModeController;
        final canSwitchMode = modeController != null && modeController.canSwitchModes;

        return _SettingsGroup(
          title: isEnglish ? 'Security & Sessions' : 'Phiên đăng nhập & Bảo mật',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            mainAxisSize: MainAxisSize.min,
            children: [
              _IdentityRow(
                icon: Icons.email_outlined,
                label: copy[ConsumerTerm.settingsEmailLabel],
                value: (email == null || email.isEmpty)
                    ? copy[ConsumerTerm.settingsNoInformation]
                    : email,
              ),
              const SizedBox(height: ClaraTokens.spaceSm),
              _IdentityRow(
                icon: Icons.badge_outlined,
                label: copy[ConsumerTerm.settingsRoleLabel],
                value: _roleLabel(role, copy),
              ),
              const SizedBox(height: ClaraTokens.spaceSm),
              _IdentityRow(
                icon: Icons.devices_outlined,
                label: isEnglish ? 'Current Active Session' : 'Phiên thiết bị hiện tại',
                value: isEnglish ? 'CLARA Mobile App • Active' : 'Ứng dụng CLARA Mobile • Đang hoạt động',
              ),
              if (canSwitchMode) ...[
                const SizedBox(height: ClaraTokens.spaceSm),
                _IdentityRow(
                  icon: Icons.workspaces_outlined,
                  label: isEnglish ? 'Workspace Mode' : 'Không gian làm việc',
                  value: kPresentationModeMeta[modeController.mode]!.label(copy.locale),
                  onTap: () => onOpenModePicker?.call(modeController),
                ),
              ],
              const SizedBox(height: ClaraTokens.spaceMd),
              Row(
                children: [
                  Expanded(
                    child: ClaraButton.secondary(
                      key: const Key('settings-revoke-sessions-button'),
                      label: isEnglish ? 'Revoke Others' : 'Đăng xuất thiết bị khác',
                      icon: Icons.phonelink_erase_outlined,
                      onPressed: onRevokeOtherSessions,
                    ),
                  ),
                  const SizedBox(width: ClaraTokens.spaceSm),
                  Expanded(
                    child: ClaraButton.secondary(
                      key: const Key('settings-sign-out-button'),
                      label: copy[ConsumerTerm.settingsSignOut],
                      icon: Icons.logout,
                      onPressed: onSignOut,
                    ),
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }

  static String _roleLabel(String? role, ConsumerTerminology copy) {
    switch (role) {
      case 'normal':
        return copy[ConsumerTerm.settingsRoleConsumer];
      case 'researcher':
        return copy[ConsumerTerm.settingsRoleResearcher];
      case 'doctor':
        return copy[ConsumerTerm.settingsRoleDoctor];
      case 'admin':
        return copy[ConsumerTerm.settingsRoleAdmin];
      case null:
      case '':
        return copy[ConsumerTerm.settingsNoInformation];
      default:
        return role;
    }
  }
}

class _IdentityRow extends StatelessWidget {
  const _IdentityRow({
    required this.icon,
    required this.label,
    required this.value,
    this.onTap,
  });

  final IconData icon;
  final String label;
  final String value;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final textScaler = A11y.resolveTextScaler(context);
    final rowContent = Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Icon(icon, size: 20, color: theme.colorScheme.onSurfaceVariant),
        const SizedBox(width: ClaraTokens.spaceMd),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: theme.textTheme.labelMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
                textScaler: textScaler,
              ),
              const SizedBox(height: 2),
              Text(
                value,
                style: theme.textTheme.bodyLarge,
                textScaler: textScaler,
              ),
            ],
          ),
        ),
        if (onTap != null)
          Icon(
            Icons.chevron_right,
            size: 20,
            color: theme.colorScheme.onSurfaceVariant,
          ),
      ],
    );

    return Semantics(
      label: '$label: $value',
      button: onTap != null,
      container: true,
      child: onTap != null
          ? InkWell(
              onTap: onTap,
              borderRadius: BorderRadius.circular(ClaraTokens.radiusSm),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: ExcludeSemantics(child: rowContent),
              ),
            )
          : ExcludeSemantics(child: rowContent),
    );
  }
}

// --- Quyền riêng tư & đồng ý (Privacy & consent) -----------------------------

class _PrivacySection extends StatelessWidget {
  const _PrivacySection({required this.copy});

  final ConsumerTerminology copy;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final textScaler = A11y.resolveTextScaler(context);
    return _SettingsGroup(
      title: copy[ConsumerTerm.settingsPrivacyTitle],
      clinical: true,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            Icons.privacy_tip_outlined,
            size: 20,
            color: theme.colorScheme.onSurfaceVariant,
          ),
          const SizedBox(width: ClaraTokens.spaceMd),
          Expanded(
            child: Text(
              copy[ConsumerTerm.settingsPrivacyDescription],
              style: theme.textTheme.bodyMedium,
              textScaler: textScaler,
            ),
          ),
        ],
      ),
    );
  }
}

// --- Minh bạch AI (AI transparency / model disclosure) -----------------------

class _TransparencySection extends StatelessWidget {
  const _TransparencySection({required this.copy, required this.locale});

  final ConsumerTerminology copy;
  final String locale;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final textScaler = A11y.resolveTextScaler(context);
    final notice = currentAiTransparencyNoticeForLocale(locale);
    final modelLabel = copy[ConsumerTerm.settingsAiModelGovernedRoute];

    return _SettingsGroup(
      title: copy[ConsumerTerm.settingsTransparencyTitle],
      clinical: true,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            notice.title,
            style: theme.textTheme.titleSmall,
            textScaler: textScaler,
          ),
          const SizedBox(height: ClaraTokens.spaceSm),
          for (final paragraph in notice.body) ...[
            Text(
              paragraph,
              style: theme.textTheme.bodyMedium,
              textScaler: textScaler,
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
          ],
          const Divider(height: ClaraTokens.spaceLg),
          _IdentityRow(
            icon: Icons.smart_toy_outlined,
            label: copy[ConsumerTerm.settingsAiModelLabel],
            value: modelLabel,
          ),
        ],
      ),
    );
  }
}

// --- Giới thiệu (About/legal) ------------------------------------------------

class _AboutSection extends StatelessWidget {
  const _AboutSection({required this.copy});

  final ConsumerTerminology copy;
  static const String _appVersion = '0.1.0';

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final textScaler = A11y.resolveTextScaler(context);
    return _SettingsGroup(
      title: copy[ConsumerTerm.settingsAboutTitle],
      clinical: true,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          _IdentityRow(
            icon: Icons.info_outline,
            label: 'CLARA',
            value: copy.format(
              ConsumerTerm.settingsVersion,
              <String, Object?>{'version': _appVersion},
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          Text(
            copy[ConsumerTerm.settingsAboutDescription],
            style: theme.textTheme.bodyMedium,
            textScaler: textScaler,
          ),
        ],
      ),
    );
  }
}

// --- Trợ giúp (Help) ---------------------------------------------------------

class _HelpSection extends StatelessWidget {
  const _HelpSection({required this.copy});

  final ConsumerTerminology copy;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final textScaler = A11y.resolveTextScaler(context);
    return _SettingsGroup(
      title: copy[ConsumerTerm.settingsHelpTitle],
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            Icons.help_outline,
            size: 20,
            color: theme.colorScheme.onSurfaceVariant,
          ),
          const SizedBox(width: ClaraTokens.spaceMd),
          Expanded(
            child: Text(
              copy[ConsumerTerm.settingsHelpDescription],
              style: theme.textTheme.bodyMedium,
              textScaler: textScaler,
            ),
          ),
        ],
      ),
    );
  }
}
