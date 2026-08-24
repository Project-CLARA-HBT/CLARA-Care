// "Hồ sơ" (Profile) hub for CLARA_Mobile Unified.
//
// Spec v5 Section 7.4:
//   * Taxonomy: Identity -> Health Record (PHR) -> Family & Sharing ->
//     Connected Health -> Privacy & Consent -> Data Rights -> Settings -> Help.
//   * Council and Scribe are removed from consumer Profile navigation.
//   * PHR is no longer embedded as a 55% fixed-height child; it is a full-screen
//     navigation destination.

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../../core/api_client.dart';
import '../../core/consumer_terminology.dart';
import '../../core/feature_flags.dart';
import '../../core/session_store.dart';
import '../../screens/consent_center_screen.dart';
import '../../screens/dsar_screen.dart';
import '../../theme/components/clara_card.dart';
import '../../theme/components/section_header.dart';
import '../../theme/tokens.dart';
import '../connected_health/connected_health_screen.dart';
import '../language_controller.dart';
import '../presentation_mode.dart';
import '../redesign/phr_surface_v3.dart';
import '../redesign/social_surface_v3.dart';
import '../theme_controller.dart';
import 'family_surface.dart';
import 'living_evidence_surface.dart';
import 'notifications_surface.dart';
import 'settings_surface.dart';
import 'visits_surface.dart';

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

/// The "Hồ sơ" (Profile) hub. See file header.
class ProfileHub extends StatelessWidget {
  const ProfileHub({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    required this.resolver,
    required this.role,
    this.phrBody,
    this.themeController,
    this.languageController,
    this.presentationModeController,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;
  final MobileFeatureFlagResolver resolver;
  final String role;

  /// Optional PHR body or builder override. When not provided, routes to [PhrSurfaceV3].
  final Widget? phrBody;

  final ThemeController? themeController;
  final LanguageController? languageController;
  final PresentationModeController? presentationModeController;

  List<_ProfileEntry> _entries(ConsumerTerminology copy) {
    final entries = <_ProfileEntry>[];

    // 1. Health Record (PHR) — full-screen navigation destination.
    entries.add(
      _ProfileEntry(
        icon: Icons.assignment_outlined,
        title: copy[ConsumerTerm.profileHubPhrTitle],
        subtitle: copy[ConsumerTerm.profileHubPhrDescription],
        builder: (_) =>
            phrBody ??
            PhrSurfaceV3(
              apiClient: apiClient,
              sessionStore: sessionStore,
              resolver: resolver,
              languageController: languageController,
            ),
      ),
    );

    // Visit preparation — collecting concerns/intake for an appointment.
    entries.add(
      _ProfileEntry(
        icon: Icons.event_note_outlined,
        title: copy[ConsumerTerm.profileHubVisitsTitle],
        subtitle: copy[ConsumerTerm.profileHubVisitsDescription],
        builder: (_) => VisitsSurface(
          apiClient: apiClient,
          sessionStore: sessionStore,
          languageController: languageController,
        ),
      ),
    );

    // 2. Family & Sharing — minimal, revocable, consent-based sharing.
    entries.add(
      _ProfileEntry(
        icon: Icons.family_restroom_outlined,
        title: copy[ConsumerTerm.profileHubFamilyTitle],
        subtitle: copy[ConsumerTerm.profileHubFamilyDescription],
        builder: (_) => FamilySurface(
          apiClient: apiClient,
          sessionStore: sessionStore,
          languageController: languageController,
        ),
      ),
    );

    entries.add(
      _ProfileEntry(
        icon: Icons.fact_check_outlined,
        title: copy[ConsumerTerm.profileHubEvidenceTitle],
        subtitle: copy[ConsumerTerm.profileHubEvidenceDescription],
        builder: (_) => LivingEvidenceSurface(
          apiClient: apiClient,
          sessionStore: sessionStore,
          languageController: languageController,
        ),
      ),
    );

    if (kMobileSocialEnabled) {
      entries.add(
        _ProfileEntry(
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

    // 3. Connected Health — IoT & synced personal devices.
    entries.add(
      _ProfileEntry(
        icon: Icons.monitor_heart_outlined,
        title: copy[ConsumerTerm.profileHubHealthDataTitle],
        subtitle: copy[ConsumerTerm.profileHubHealthDataDescription],
        builder: (_) => ConnectedHealthScreen(
          apiClient: apiClient,
          sessionStore: sessionStore,
          languageController: languageController,
        ),
      ),
    );

    // 4. Privacy & Consent & 5. Data Rights (PDPD).
    if (resolver.consentCenterEnabled) {
      entries.add(
        _ProfileEntry(
          icon: Icons.privacy_tip_outlined,
          title: copy[ConsumerTerm.profileHubConsentTitle],
          subtitle: copy[ConsumerTerm.profileHubConsentDescription],
          builder: (_) => ConsentCenterScreen(
            apiClient: apiClient,
            resolver: resolver,
            sessionStore: sessionStore,
          ),
        ),
      );
      entries.add(
        _ProfileEntry(
          icon: Icons.manage_search_outlined,
          title: copy[ConsumerTerm.profileHubDataRightsTitle],
          subtitle: copy[ConsumerTerm.profileHubDataRightsDescription],
          builder: (_) => DsarScreen(
            apiClient: apiClient,
            resolver: resolver,
            sessionStore: sessionStore,
          ),
        ),
      );
    }

    final modeController = presentationModeController ??
        (permittedModesForRole(role).length > 1
            ? PresentationModeController(initialRole: role)
            : null);

    if (modeController != null && modeController.canSwitchModes) {
      final modeMeta = kPresentationModeMeta[modeController.mode]!;
      final lang = languageController?.languageCode ?? 'vi';
      entries.add(
        _ProfileEntry(
          icon: Icons.workspaces_outlined,
          title: lang == 'en' ? 'Workspace Mode' : 'Không gian làm việc',
          subtitle: modeMeta.label(lang),
          builder: (_) => PresentationModeScreen(
            controller: modeController,
            languageCode: lang,
          ),
        ),
      );
    }

    // Notifications preferences (Spec v5 Section 7.10)
    entries.add(
      _ProfileEntry(
        icon: Icons.notifications_outlined,
        title: copy.locale == 'en' ? 'Notifications' : 'Thông báo',
        subtitle: copy.locale == 'en'
            ? 'Medication reminders, care journey alerts, and family updates'
            : 'Lịch uống thuốc, cảnh báo hành trình và cập nhật gia đình',
        builder: (_) => NotificationsSurface(
          apiClient: apiClient,
          sessionStore: sessionStore,
          languageController: languageController,
        ),
      ),
    );

    // 6. Settings / Preferences (Spec v5 Section 7.9).
    entries.add(
      _ProfileEntry(
        icon: Icons.settings_outlined,
        title: copy[ConsumerTerm.profileHubSettingsTitle],
        subtitle: copy[ConsumerTerm.profileHubSettingsDescription],
        builder: (_) => SettingsSurface(
          apiClient: apiClient,
          sessionStore: sessionStore,
          themeController: themeController,
          languageController: languageController,
          presentationModeController: modeController,
        ),
      ),
    );

    // 7. Help & Support.
    entries.add(
      _ProfileEntry(
        icon: Icons.help_outline,
        title: copy[ConsumerTerm.profileHubHelpTitle],
        subtitle: copy[ConsumerTerm.profileHubHelpDescription],
        builder: (_) => _HelpSurface(copy: copy),
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
      return _buildLocalized(context, ConsumerTerminology.forLocale(null));
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
    final email = sessionStore.email;
    final isEnglish = copy.locale == 'en';

    return Scaffold(
      appBar: AppBar(title: Text(copy[ConsumerTerm.navigationProfile])),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.symmetric(vertical: ClaraTokens.spaceSm),
          children: [
            // Identity Header card (Spec v5 §7.4: Identity at top of taxonomy)
            Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: ClaraTokens.spaceMd,
                vertical: ClaraTokens.spaceXs,
              ),
              child: ClaraCard.static_(
                semanticLabel: isEnglish ? 'Account Identity' : 'Thông tin tài khoản',
                child: Row(
                  children: [
                    CircleAvatar(
                      radius: 26,
                      backgroundColor:
                          Theme.of(context).colorScheme.primaryContainer,
                      child: Icon(
                        Icons.person_outline,
                        size: 28,
                        color:
                            Theme.of(context).colorScheme.onPrimaryContainer,
                      ),
                    ),
                    const SizedBox(width: ClaraTokens.spaceMd),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            (email == null || email.isEmpty)
                                ? copy[ConsumerTerm.settingsNoInformation]
                                : email,
                            style: Theme.of(context)
                                .textTheme
                                .titleMedium
                                ?.copyWith(fontWeight: FontWeight.w600),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          const SizedBox(height: ClaraTokens.spaceXs),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: Theme.of(context)
                                  .colorScheme
                                  .surfaceContainerHighest,
                              borderRadius:
                                  BorderRadius.circular(ClaraTokens.radiusSm),
                            ),
                            child: Text(
                              _roleLabel(role, isEnglish),
                              style: Theme.of(context)
                                  .textTheme
                                  .labelSmall
                                  ?.copyWith(
                                    color: Theme.of(context)
                                        .colorScheme
                                        .onSurfaceVariant,
                                  ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            SectionHeader(
              title: copy[ConsumerTerm.profileHubToolsAndPrivacy],
            ),
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
                      ConstrainedBox(
                        constraints: const BoxConstraints(
                          minHeight: A11y.minTapTargetDimension,
                        ),
                        child: ListTile(
                          leading: Icon(entry.icon),
                          title: Text(entry.title),
                          subtitle: Text(entry.subtitle),
                          trailing: const Icon(Icons.chevron_right),
                          minVerticalPadding: ClaraTokens.spaceSm,
                          onTap: () => _open(context, entry.builder),
                        ),
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

  static String _roleLabel(String role, bool isEnglish) {
    switch (role.toLowerCase()) {
      case 'doctor':
        return isEnglish ? 'Doctor / Clinician' : 'Bác sĩ / Cán bộ y tế';
      case 'admin':
        return isEnglish ? 'Administrator' : 'Quản trị viên';
      case 'researcher':
        return isEnglish ? 'Researcher' : 'Nhà nghiên cứu';
      default:
        return isEnglish ? 'Personal Account' : 'Tài khoản cá nhân';
    }
  }
}

/// A dedicated Help and Support surface for CLARA.
class _HelpSurface extends StatelessWidget {
  const _HelpSurface({required this.copy});

  final ConsumerTerminology copy;

  @override
  Widget build(BuildContext context) {
    final isEnglish = copy.locale == 'en';
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text(copy[ConsumerTerm.profileHubHelpTitle]),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(ClaraTokens.spaceMd),
          children: [
            ClaraCard.static_(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(
                        Icons.info_outline,
                        color: theme.colorScheme.primary,
                      ),
                      const SizedBox(width: ClaraTokens.spaceSm),
                      Text(
                        isEnglish
                            ? 'About CLARA Assistant'
                            : 'Về Trợ lý Sức khỏe CLARA',
                        style: theme.textTheme.titleMedium
                            ?.copyWith(fontWeight: FontWeight.w600),
                      ),
                    ],
                  ),
                  const SizedBox(height: ClaraTokens.spaceSm),
                  Text(
                    isEnglish
                        ? 'CLARA is a Vietnamese, safety-first Medical AI Assistant designed to support personal health tracking, medication safety, and clinical decision support. CLARA is an assistant, not a replacement for a qualified doctor.'
                        : 'CLARA là Trợ lý AI Y tế tiếng Việt ưu tiên an toàn, hỗ trợ theo dõi sức khỏe cá nhân, tra cứu an toàn thuốc và hỗ trợ quyết định y khoa. CLARA là công cụ hỗ trợ, không thay thế bác sĩ điều trị.',
                    style: theme.textTheme.bodyMedium,
                  ),
                ],
              ),
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            SectionHeader(
              title: isEnglish ? 'Frequently Asked Questions' : 'Câu hỏi thường gặp',
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            ClaraCard.static_(
              child: ExpansionTile(
                title: Text(
                  isEnglish
                      ? 'Is my health data secure and private?'
                      : 'Dữ liệu sức khỏe của tôi có được bảo mật không?',
                  style: theme.textTheme.titleSmall,
                ),
                children: [
                  Padding(
                    padding: const EdgeInsets.all(ClaraTokens.spaceSm),
                    child: Text(
                      isEnglish
                          ? 'Yes. CLARA strictly enforces PDPD compliance and FHIR consent policies. Your health data is encrypted and only shared with explicit consent.'
                          : 'Có. CLARA tuân thủ nghiêm ngặt Nghị định Bảo vệ Dữ liệu Cá nhân (PDPD) và chuẩn đồng ý FHIR. Dữ liệu của bạn được mã hóa và chỉ chia sẻ khi có sự đồng ý rõ ràng.',
                      style: theme.textTheme.bodyMedium,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            ClaraCard.static_(
              child: ExpansionTile(
                title: Text(
                  isEnglish
                      ? 'How do I check drug interactions?'
                      : 'Làm thế nào để kiểm tra tương tác thuốc?',
                  style: theme.textTheme.titleSmall,
                ),
                children: [
                  Padding(
                    padding: const EdgeInsets.all(ClaraTokens.spaceSm),
                    child: Text(
                      isEnglish
                          ? 'Navigate to the Medicines tab to scan medicine labels with OCR or add medicines to your cabinet. CareGuard DDI will automatically verify safety.'
                          : 'Truy cập mục Tủ thuốc để quét vỏ hộp thuốc qua camera hoặc thêm thuốc vào tủ. CareGuard DDI sẽ tự động kiểm tra tương tác thuốc.',
                      style: theme.textTheme.bodyMedium,
                    ),
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
