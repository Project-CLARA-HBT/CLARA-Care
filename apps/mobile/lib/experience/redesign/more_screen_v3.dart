// "Thêm" (More) surface for the CLARA_Mobile redesign (Experience_V3).
//
// clara-mobile-redesign, Requirement 2.4 (secondary surfaces collected under
// More) + Requirement 11 (RBAC / capability gates preserved, fail-closed).
//
// Lists the role-gated surfaces that are not primary destinations: AI Council,
// Medical Scribe (doctor/admin), CareGuard interaction check, Consent Center,
// Settings, and Help. Every entry is derived from the already-loaded [resolver]
// (fail-closed: a gate that is off is simply not listed), mirroring the web
// "More"/grouped-nav behavior.
//
// Baseline: this is a functional router built on the existing screens. Task 4
// (Settings) and Tasks 6/8 (Council/Scribe redesign) replace the destinations
// with their redesigned surfaces; the entry list here stays the same.

import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/consumer_terminology.dart';
import '../../core/feature_flags.dart';
import '../../core/session_store.dart';
import '../../screens/consent_center_screen.dart';
import '../../theme/components/section_header.dart';
import '../../theme/glass/glass_surface.dart';
import '../../theme/glass/glass_tokens.dart';
import '../../theme/tokens.dart';
import '../connected_health/connected_health_screen.dart';
import 'scribe_surface_v3.dart';
import 'social_surface_v3.dart';
import '../language_controller.dart';
import '../theme_controller.dart';
import 'settings_screen_v3.dart';

/// A single More entry (icon + title + subtitle + destination builder).
class _MoreEntry {
  const _MoreEntry({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.builder,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final WidgetBuilder builder;
}

/// The "Thêm" (More) surface. See file header.
class MoreScreenV3 extends StatelessWidget {
  const MoreScreenV3({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    required this.resolver,
    required this.role,
    this.themeController,
    this.languageController,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;
  final MobileFeatureFlagResolver resolver;
  final String role;

  /// App-wide theme-mode state, threaded to Settings (Appearance section).
  final ThemeController? themeController;

  /// App-wide language state, threaded to Settings (Language section).
  final LanguageController? languageController;

  // Scribe opens for the doctor role (existing) and, per the redesign request,
  // also for admin. Still fail-closed: requires the `scribe_mobile_enabled`
  // capability gate on top of the authorized role.
  bool get _canScribe =>
      resolver.scribeEnabled && (role == 'doctor' || role == 'admin');

  List<_MoreEntry> _entries(ConsumerTerminology copy) {
    final entries = <_MoreEntry>[];

    // Community (health social platform) — gated by the mobile social flag.
    if (kMobileSocialEnabled) {
      entries.add(
        _MoreEntry(
          icon: Icons.forum_outlined,
          title: copy[ConsumerTerm.profileHubCommunityTitle],
          subtitle: copy[ConsumerTerm.profileHubCommunityDescription],
          builder: (_) => SocialSurfaceV3(
            apiClient: apiClient,
            sessionStore: sessionStore,
            languageController: languageController,
          ),
        ),
      );
    }

    // Connected health is an optional personal-data feature for all roles.
    entries.add(
      _MoreEntry(
        icon: Icons.monitor_heart_outlined,
        title: 'Dữ liệu sức khỏe',
        subtitle: 'Quản lý các nguồn bạn đã cho phép kết nối',
        builder: (_) => ConnectedHealthScreen(
          apiClient: apiClient,
          sessionStore: sessionStore,
          languageController: languageController,
        ),
      ),
    );

    // Medical Scribe (doctor + scribe flag).
    if (_canScribe) {
      entries.add(
        _MoreEntry(
          icon: Icons.mic_none_outlined,
          title: 'Ghi chú lâm sàng',
          subtitle: 'Ghi âm và tạo ghi chú SOAP',
          builder: (_) => ScribeSurfaceV3(
            apiClient: apiClient,
            sessionStore: sessionStore,
            resolver: resolver,
          ),
        ),
      );
    }

    // Consent center (gated).
    if (resolver.consentCenterEnabled) {
      entries.add(
        _MoreEntry(
          icon: Icons.privacy_tip_outlined,
          title: 'Quyền riêng tư & đồng ý',
          subtitle: 'Quản lý đồng ý theo mục đích',
          builder: (_) => ConsentCenterScreen(
            resolver: resolver,
            sessionStore: sessionStore,
          ),
        ),
      );
    }

    // Settings — always available.
    entries.add(
      _MoreEntry(
        icon: Icons.settings_outlined,
        title: 'Cài đặt',
        subtitle: 'Giao diện, ngôn ngữ, tài khoản và quyền riêng tư',
        builder: (_) => SettingsScreenV3(
          apiClient: apiClient,
          sessionStore: sessionStore,
          themeController: themeController,
          languageController: languageController,
        ),
      ),
    );

    return entries;
  }

  void _open(BuildContext context, WidgetBuilder builder) {
    Navigator.of(context).push(MaterialPageRoute<void>(builder: builder));
  }

  @override
  Widget build(BuildContext context) {
    final languageController = this.languageController;
    if (languageController == null) {
      return _buildLocalized(
        context,
        ConsumerTerminology.forLocale(null),
      );
    }
    return AnimatedBuilder(
      animation: languageController,
      builder: (context, _) => _buildLocalized(
        context,
        ConsumerTerminology.forLocale(languageController.languageCode),
      ),
    );
  }

  Widget _buildLocalized(BuildContext context, ConsumerTerminology copy) {
    final entries = _entries(copy);
    return Scaffold(
      appBar: AppBar(title: const Text('Thêm')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.symmetric(vertical: ClaraTokens.spaceSm),
          children: [
            const SectionHeader(title: 'Công cụ khác'),
            // The list container is pure navigation chrome (icon + title +
            // subtitle routers, no clinical content), so it sits on a liquid-
            // glass surface. When the ambient GlassScope is off the same
            // container renders opaque with identical geometry. The tile copy
            // and ≥48dp `ListTile` targets are unchanged.
            Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: ClaraTokens.spaceMd,
              ),
              child: GlassSurface(
                blurSigma: GlassTokens.blurCard,
                radius: GlassTokens.radiusCard,
                fill: GlassFill.regular,
                padding: const EdgeInsets.symmetric(
                  vertical: ClaraTokens.spaceXs,
                ),
                // A transparent Material gives the ListTiles a surface to
                // paint their ink on; the glass fill/shape stays owned by
                // GlassSurface.
                child: Material(
                  type: MaterialType.transparency,
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      for (final entry in entries)
                        ListTile(
                          leading: Icon(entry.icon),
                          title: Text(entry.title),
                          subtitle: Text(entry.subtitle),
                          trailing: const Icon(Icons.chevron_right),
                          onTap: () => _open(context, entry.builder),
                        ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
