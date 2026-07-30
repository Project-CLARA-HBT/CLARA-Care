// Complete Settings surface for the CLARA_Mobile redesign (Experience_V3).
//
// clara-mobile-redesign, Requirement 4 (complete Settings surface) + the
// regression-locked safety invariants (no-PII analytics, sign-out fully clears
// the session, Vietnamese-first copy, ≥48dp tap targets, text scaler, reduced
// motion, selection conveyed by text/semantics not color alone).
//
// This replaces the near-empty placeholder with a structured, sectioned
// settings experience built entirely from the shared design system
// (`SectionHeader` + `GlassSurface` chrome + `ClaraButton`). Control-only
// groups sit on liquid-glass chrome; safety-copy groups (consent, AI
// transparency, the not-a-doctor positioning) force the opaque path (R11):
//
//   * Giao diện (Appearance) — theme mode (Sáng / Tối / Hệ thống) driven by the
//     injected [ThemeController]; changing it applies app-wide immediately
//     because the controller notifies the app root. Hidden when no controller
//     is provided (Requirement 4.2 / 1.3).
//   * Ngôn ngữ (Language) — reuses the existing [LanguageToggle] over the
//     injected [LanguageController]; hidden when no controller is provided
//     (Requirement 4.3).
//   * Tài khoản (Account) — signed-in email + role, and a confirmed sign-out
//     that best-effort revokes server sessions then fully clears the session
//     via `SessionStore.clear()`, which routes back to login via the app root's
//     session listener (Requirement 4.4, 4.5).
//   * Quyền riêng tư & đồng ý (Privacy & consent) — an informational entry
//     describing consent management (Requirement 4.5). Kept as a simple tile:
//     this surface does not receive a consent resolver, so it does not deep-link
//     into the Consent Center to stay fail-closed and dependency-clean.
//   * Minh bạch AI (AI transparency) — surfaces the versioned transparency
//     notice text (`kCurrentAiTransparencyNotice`) and the configured model
//     family/version disclosure (Requirement 4.6, 4.7).
//   * Giới thiệu (About/legal) + Trợ giúp (Help) — static tiles: app
//     name/version, the not-a-doctor positioning, and help placeholders
//     (Requirement 4.6, 4.7).
//
// This widget performs NO analytics itself (the language controller owns its
// single coarse no-PII event) and never displays secret values such as tokens
// (Requirement 4.8).

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../../core/ai_transparency_notice.dart';
import '../../core/api_client.dart';
import '../../core/consumer_terminology.dart';
import '../../core/model_disclosure.dart';
import '../../core/session_store.dart';
import '../../theme/components/clara_button.dart';
import '../../theme/components/section_header.dart';
import '../../theme/glass/glass_surface.dart';
import '../../theme/glass/glass_tokens.dart';
import '../../theme/tokens.dart';
import '../language_controller.dart';
import '../settings/language_toggle.dart';
import '../theme_controller.dart';

/// The complete Settings ("Cài đặt") surface for Experience_V3. See file header.
class SettingsScreenV3 extends StatelessWidget {
  const SettingsScreenV3({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    this.themeController,
    this.languageController,
  });

  /// API client, used for a best-effort server-side logout on sign-out.
  final ApiClient apiClient;

  /// The session/credential store. Sign-out clears it to route back to login.
  final SessionStore sessionStore;

  /// App-wide theme-mode state. When `null` the Appearance section is hidden.
  final ThemeController? themeController;

  /// App-wide language state. When `null` the Language section is hidden.
  final LanguageController? languageController;

  @override
  Widget build(BuildContext context) {
    final controller = languageController;
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
    return Scaffold(
      appBar: AppBar(title: Text(copy[ConsumerTerm.settingsTitle])),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.only(bottom: ClaraTokens.spaceXl),
          children: [
            if (themeController != null)
              _ThemeSection(controller: themeController!, copy: copy),
            if (languageController != null)
              LanguageToggle(controller: languageController!),
            _AccountSection(
              apiClient: apiClient,
              sessionStore: sessionStore,
              copy: copy,
            ),
            _PrivacySection(copy: copy),
            _TransparencySection(copy: copy, locale: copy.locale),
            _AboutSection(copy: copy),
            _HelpSection(copy: copy),
          ],
        ),
      ),
    );
  }
}

/// Shared padding + card wrapper for a settings group so the sections keep a
/// consistent rhythm (matches [LanguageToggle]'s layout).
///
/// Chrome-only groups (controls: theme, account, help) render on a liquid-glass
/// surface; when the ambient [GlassScope] is off the same card renders opaque
/// with identical geometry. Groups whose card hosts safety-sensitive copy
/// (consent, AI transparency/disclosure, the not-a-doctor/emergency positioning)
/// pass [clinical] so the surface is FORCED opaque and never translucent (R11).
/// The grouping region keeps its screen-reader [title] label either way.
class _SettingsGroup extends StatelessWidget {
  const _SettingsGroup({
    required this.title,
    required this.child,
    this.clinical = false,
  });

  final String title;
  final Widget child;

  /// When true, the group hosts clinical/safety copy and MUST render opaque.
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
              // A transparent Material gives any ListTile/RadioListTile inside
              // a surface to paint its ink on (the old ClaraCard's Card did
              // this); the glass fill/shape stays owned by GlassSurface.
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

// --- Giao diện (Appearance) --------------------------------------------------

/// A single selectable theme-mode option (mode + Vietnamese label + icon).
class _ThemeOption {
  const _ThemeOption(this.mode, this.label, this.icon);

  final ThemeMode mode;
  final String label;
  final IconData icon;
}

/// The Appearance section: a radio list choosing the app-wide [ThemeMode].
///
/// Listens to the [ThemeController] so the selection always reflects controller
/// state; a pick calls [ThemeController.setThemeMode], which persists and
/// notifies the app root so the theme applies app-wide immediately
/// (Requirement 4.2 / 1.3). Selection is conveyed by text/semantics, not color
/// alone.
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

/// One theme row: a ≥48dp, screen-reader-labeled radio tile whose selected
/// state is conveyed by text/semantics (not color alone).
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
    // Convey selection in the spoken value, not by color alone.
    final selectedSuffix = isSelected ? this.selectedSuffix : notSelectedSuffix;

    return Semantics(
      inMutuallyExclusiveGroup: true,
      selected: isSelected,
      button: true,
      label: '${option.label}, $selectedSuffix',
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

// --- Tài khoản (Account) -----------------------------------------------------

/// The Account section: signed-in identity + a confirmed sign-out.
class _AccountSection extends StatelessWidget {
  const _AccountSection({
    required this.apiClient,
    required this.sessionStore,
    required this.copy,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;
  final ConsumerTerminology copy;

  /// Best-effort server logout, then fully clear the session so the app root's
  /// session listener routes back to login (Requirement 4.4, 4.5).
  Future<void> _signOut() async {
    final token = sessionStore.accessToken;
    try {
      await apiClient.logout(accessToken: token);
    } catch (_) {
      // Best-effort only: a failed/unavailable server logout must never block a
      // local sign-out. The authoritative step is clearing the local session.
    }
    await sessionStore.clear();
  }

  Future<void> _confirmSignOut(BuildContext context) async {
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

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: sessionStore,
      builder: (context, _) {
        final email = sessionStore.email;
        final role = sessionStore.role;
        return _SettingsGroup(
          title: copy[ConsumerTerm.settingsAccountTitle],
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
              const SizedBox(height: ClaraTokens.spaceMd),
              ClaraButton.secondary(
                label: copy[ConsumerTerm.settingsSignOut],
                icon: Icons.logout,
                onPressed: () => _confirmSignOut(context),
              ),
            ],
          ),
        );
      },
    );
  }

  /// Maps a raw role code to a Vietnamese-first label, falling back to the raw
  /// value (or a neutral placeholder) so nothing is ever left blank.
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

/// A labeled identity row (icon + label + value) for the Account card.
class _IdentityRow extends StatelessWidget {
  const _IdentityRow({
    required this.icon,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final textScaler = A11y.resolveTextScaler(context);
    return Semantics(
      label: '$label: $value',
      container: true,
      child: ExcludeSemantics(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
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
          ],
        ),
      ),
    );
  }
}

// --- Quyền riêng tư & đồng ý (Privacy & consent) -----------------------------

/// The Privacy & consent section: an informational description of consent
/// management. Kept simple/static (no deep navigation) because this surface does
/// not receive a consent resolver.
class _PrivacySection extends StatelessWidget {
  const _PrivacySection({required this.copy});

  final ConsumerTerminology copy;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final textScaler = A11y.resolveTextScaler(context);
    return _SettingsGroup(
      title: copy[ConsumerTerm.settingsPrivacyTitle],
      // Consent copy is safety-sensitive: force the opaque path (R11).
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

/// The AI transparency section: surfaces the versioned transparency notice text
/// and the configured model family/version disclosure (Requirement 4.6).
class _TransparencySection extends StatelessWidget {
  const _TransparencySection({required this.copy, required this.locale});

  final ConsumerTerminology copy;
  final String locale;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final textScaler = A11y.resolveTextScaler(context);
    final notice = currentAiTransparencyNoticeForLocale(locale);
    // Reuse the shared model-disclosure label for a consistent, no-secret model
    // family/version string from the governed V4 default (e.g. "deepseek v4 pro").
    final modelLabel = ModelDisclosure.fromModelUsed('deepseek-v4-pro').label;

    return _SettingsGroup(
      title: copy[ConsumerTerm.settingsTransparencyTitle],
      // AI transparency notice + model disclosure is safety copy: opaque (R11).
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

/// The About section: app name/version and the not-a-doctor positioning.
class _AboutSection extends StatelessWidget {
  const _AboutSection({required this.copy});

  final ConsumerTerminology copy;

  /// App version string. Kept as a local constant (mirrors `pubspec.yaml`) so
  /// this surface has no runtime package-info dependency.
  static const String _appVersion = '0.1.0';

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final textScaler = A11y.resolveTextScaler(context);
    return _SettingsGroup(
      title: copy[ConsumerTerm.settingsAboutTitle],
      // The not-a-doctor / emergency positioning is safety copy: opaque (R11).
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

/// The Help section: static informational tiles (placeholders for guides).
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
