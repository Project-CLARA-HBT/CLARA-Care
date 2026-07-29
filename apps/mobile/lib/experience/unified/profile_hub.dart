// "Hồ sơ" (Profile) hub for CLARA_Mobile Unified.
//
// clara-mobile-unified, Requirement 2.2: a single Profile destination that
// collects the secondary personal surfaces (PHR record, Connected Health,
// Consent Center, Settings, Guide) plus role-gated tools. Every entry is
// derived from the loaded [resolver] and role (fail-closed: an off gate is
// simply not listed), mirroring the web grouped-nav / "More" behavior and the
// existing MoreScreenV3.
//
// This hub is pure navigation chrome (icon + title + subtitle routers, no
// clinical content). It reuses the already-built V3 surfaces so nothing is
// duplicated: PHR, Scribe, Social, Connected Health, Consent Center, Settings.

import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/feature_flags.dart';
import '../../core/session_store.dart';
import '../../screens/consent_center_screen.dart';
import '../../theme/components/section_header.dart';
import '../../theme/tokens.dart';
import '../../screens/council_case_screen.dart'
    show kCouncilMobileParityEnabled;
import '../connected_health/connected_health_screen.dart';
import '../language_controller.dart';
import 'family_surface.dart';
import 'living_evidence_surface.dart';
import 'visits_surface.dart';
import '../redesign/council_surface_v3.dart' show CouncilSurfaceV3;
import '../redesign/scribe_surface_v3.dart' show ScribeSurfaceV3;
import '../redesign/settings_screen_v3.dart' show SettingsScreenV3;
import '../redesign/social_surface_v3.dart' show SocialSurfaceV3;
import '../theme_controller.dart';

/// A single Profile entry (icon + title + subtitle + destination builder).
class _ProfileEntry {
  const _ProfileEntry({
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

/// The "Hồ sơ" (Profile) hub. See file header. [phrBody] is the primary PHR
/// surface shown inline at the top; the list below routes to secondary tools.
class ProfileHub extends StatelessWidget {
  const ProfileHub({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    required this.resolver,
    required this.role,
    required this.phrBody,
    this.themeController,
    this.languageController,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;
  final MobileFeatureFlagResolver resolver;
  final String role;

  /// The primary PHR surface (PhrSurfaceV3), shown as the hub's main content.
  final Widget phrBody;

  final ThemeController? themeController;
  final LanguageController? languageController;

  bool get _canScribe =>
      resolver.scribeEnabled && (role == 'doctor' || role == 'admin');

  // AI Council (multi-specialist case review) is a clinician tool: doctor/admin
  // only, and gated by the council parity flag (fail-closed).
  bool get _canCouncil =>
      kCouncilMobileParityEnabled && (role == 'doctor' || role == 'admin');

  List<_ProfileEntry> _entries() {
    final entries = <_ProfileEntry>[];

    // Visit preparation — collecting concerns/intake for an appointment.
    entries.add(
      _ProfileEntry(
        icon: Icons.event_note_outlined,
        title: 'Chuẩn bị đi khám',
        subtitle: 'Gom câu hỏi và thông tin cho buổi khám',
        builder: (_) => VisitsSurface(
          apiClient: apiClient,
          sessionStore: sessionStore,
        ),
      ),
    );

    // Family Circle — minimal, revocable, consent-based sharing.
    entries.add(
      _ProfileEntry(
        icon: Icons.family_restroom_outlined,
        title: 'Người thân & chia sẻ',
        subtitle: 'Chia sẻ tối thiểu với người hỗ trợ, có thể thu hồi',
        builder: (_) => FamilySurface(
          apiClient: apiClient,
          sessionStore: sessionStore,
        ),
      ),
    );

    entries.add(
      _ProfileEntry(
        icon: Icons.fact_check_outlined,
        title: 'Bằng chứng đang cập nhật',
        subtitle: 'Theo dõi thay đổi đã được chuyên gia rà soát',
        builder: (_) => LivingEvidenceSurface(
          apiClient: apiClient,
          sessionStore: sessionStore,
        ),
      ),
    );

    if (kMobileSocialEnabled) {
      entries.add(
        _ProfileEntry(
          icon: Icons.forum_outlined,
          title: 'Cộng đồng',
          subtitle: 'Chia sẻ và hỏi đáp cùng cộng đồng sức khỏe',
          builder: (_) => SocialSurfaceV3(
            apiClient: apiClient,
            sessionStore: sessionStore,
          ),
        ),
      );
    }

    entries.add(
      _ProfileEntry(
        icon: Icons.monitor_heart_outlined,
        title: 'Dữ liệu sức khỏe',
        subtitle: 'Quản lý các nguồn bạn đã cho phép kết nối',
        builder: (_) => ConnectedHealthScreen(
          apiClient: apiClient,
          sessionStore: sessionStore,
        ),
      ),
    );

    if (_canScribe) {
      entries.add(
        _ProfileEntry(
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

    // AI Council — guided multi-specialist case wizard (doctor/admin, gated).
    if (_canCouncil) {
      entries.add(
        _ProfileEntry(
          icon: Icons.groups_outlined,
          title: 'Hội chẩn ca bệnh',
          subtitle: 'Tập hợp góc nhìn đa chuyên khoa cho ca khó',
          builder: (_) => CouncilSurfaceV3(
            apiClient: apiClient,
            sessionStore: sessionStore,
          ),
        ),
      );
    }

    if (resolver.consentCenterEnabled) {
      entries.add(
        _ProfileEntry(
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

    entries.add(
      _ProfileEntry(
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
    final entries = _entries();
    return Scaffold(
      appBar: AppBar(title: const Text('Hồ sơ')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.symmetric(vertical: ClaraTokens.spaceSm),
          children: [
            // Primary PHR surface inline. It brings its own scroll view, so it
            // is height-bounded to avoid an unbounded-height nesting error.
            SizedBox(
              height: MediaQuery.of(context).size.height * 0.55,
              child: phrBody,
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            const SectionHeader(title: 'Công cụ & quyền riêng tư'),
            Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: ClaraTokens.spaceMd,
              ),
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
                        minVerticalPadding: ClaraTokens.spaceSm,
                        onTap: () => _open(context, entry.builder),
                      ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
