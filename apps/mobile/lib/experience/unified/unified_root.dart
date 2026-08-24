// Authenticated root for CLARA_Mobile Unified (spec: clara-mobile-unified).
//
// Collapses the three parallel experience layers (legacy Dashboard,
// Experience_V2, redesign V3) into ONE product-aligned consumer information
// architecture that mirrors the web app, dynamically adapting to user role
// and presentation mode:
//
//   Personal Mode:  Hôm nay | LifeMap | Hỏi CLARA | Thuốc | Hồ sơ
//   Clinical Mode:  Tổng quan | Hội chẩn | Hỏi CLARA | Ghi chép | Thêm
//   Research Mode:  Hỏi CLARA | Bằng chứng | Nguồn | Thêm
//
// Responsibilities:
//   1. Load the role-scoped `mobile/summary` once → one MobileFeatureFlagResolver
//      (fail-closed: a null/unloadable summary leaves every gate at its
//      build-time default, all off in a normal build).
//   2. Server-backed first-run gate: read `GET /phr/onboarding`; while
//      `needs_onboarding` is true, present the OnboardingFlow (all roles, not
//      just consumers). On complete/skip, re-enter the shell.
//   3. Host the adaptive shell (reusing the built RedesignShell) with the
//      mode-appropriate destinations and the center Chat action.
//
// This root is only selected by `app.dart` when `kMobileUnifiedEnabled` is on,
// and always sits INSIDE the existing `ConsentGate` (consent precedes any
// medical content — INV-1). Chat/PHR/Cabinet/Scribe/Settings surfaces are
// reused verbatim so their tested safety invariants hold.

import 'package:flutter/material.dart';

import '../../core/analytics.dart';
import '../../core/api_client.dart';
import '../../core/consumer_terminology.dart';
import '../../core/feature_flags.dart';
import '../../core/lifemap_read_cache.dart';
import '../../core/session_store.dart';
import '../../screens/research_screen.dart';
import '../../theme/glass/glass_scope.dart';
import '../language_controller.dart';
import '../presentation_mode.dart';
import '../redesign/chat_surface_v3.dart' show ChatSurfaceV3;
import '../redesign/council_surface_v3.dart' show CouncilSurfaceV3;
import '../redesign/more_screen_v3.dart' show MoreScreenV3;
import '../redesign/phr_surface_v3.dart' show PhrSurfaceV3;
import '../redesign/scribe_surface_v3.dart' show ScribeSurfaceV3;
import '../redesign_shell.dart';
import '../spatial/adaptive_clara_shell.dart';
import '../theme_controller.dart';
import 'clinical_overview_surface.dart';
import 'lifemap_surface.dart';
import 'living_evidence_surface.dart';
import 'medicines_hub.dart';
import 'onboarding_flow.dart';
import 'profile_hub.dart';
import 'today_surface.dart';
import 'visits_surface.dart';

/// Coarse, no-PII screen-view event for the unified shell.
const String kUnifiedShellViewedEvent = 'mobile_unified_shell_viewed';

/// The unified authenticated root. See file header.
class UnifiedRoot extends StatefulWidget {
  const UnifiedRoot({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    this.themeController,
    this.languageController,
    this.presentationModeController,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;
  final ThemeController? themeController;
  final LanguageController? languageController;
  final PresentationModeController? presentationModeController;

  @override
  State<UnifiedRoot> createState() => _UnifiedRootState();
}

class _UnifiedRootState extends State<UnifiedRoot> {
  late final LifeMapReadCache _lifeMapReadCache = LifeMapReadCache();
  late final PresentationModeController _modeController;
  bool _loading = true;
  Map<String, dynamic>? _summary;

  /// `null` while unknown; `true` while the first-run flow should be shown.
  bool _needsOnboarding = false;

  @override
  void initState() {
    super.initState();
    getAnalyticsClient().captureScreenView(kUnifiedShellViewedEvent);
    _modeController = widget.presentationModeController ??
        PresentationModeController(initialRole: widget.sessionStore.role);
    _modeController.addListener(_onModeChanged);
    _bootstrap();
  }

  @override
  void dispose() {
    _modeController.removeListener(_onModeChanged);
    if (widget.presentationModeController == null) {
      _modeController.dispose();
    }
    super.dispose();
  }

  void _onModeChanged() {
    if (mounted) setState(() {});
  }

  @override
  void didUpdateWidget(covariant UnifiedRoot oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.sessionStore.role != oldWidget.sessionStore.role) {
      _modeController.updateRole(widget.sessionStore.role);
    }
  }

  String get _role => widget.sessionStore.role ?? 'normal';

  Future<void> _bootstrap() async {
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) {
      if (mounted) setState(() => _loading = false);
      return;
    }
    _modeController.updateRole(_role);
    final isProfessional =
        _role == 'doctor' || _role == 'researcher' || _role == 'admin';
    // Load the summary and onboarding status concurrently. Both fail-closed:
    // an unloadable summary leaves gates at defaults; an unreadable onboarding
    // status defaults to "not needed" so the user is never trapped out of the
    // app by a transient error.
    Map<String, dynamic>? summary;
    bool needsOnboarding = false;
    try {
      summary = await widget.apiClient.getMobileSummary(accessToken: token);
    } catch (_) {
      summary = null;
    }
    if (!isProfessional) {
      try {
        final onboarding =
            await widget.apiClient.getPhrOnboarding(accessToken: token);
        needsOnboarding = onboarding['needs_onboarding'] == true;
      } catch (_) {
        needsOnboarding = false;
      }
    }
    if (!mounted) return;
    setState(() {
      _summary = summary;
      _needsOnboarding = needsOnboarding;
      _loading = false;
    });
  }

  void _onOnboardingDone() {
    if (!mounted) return;
    setState(() => _needsOnboarding = false);
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    if (_needsOnboarding) {
      return OnboardingFlow(
        apiClient: widget.apiClient,
        sessionStore: widget.sessionStore,
        onDone: _onOnboardingDone,
        languageController: widget.languageController,
      );
    }

    final resolver = MobileFeatureFlagResolver(summary: _summary);
    return GlassScopeProvider(child: _buildShell(resolver));
  }

  Widget _buildShell(MobileFeatureFlagResolver resolver) {
    final languageController = widget.languageController;
    final listenables = <Listenable>[
      _modeController,
      if (languageController != null) languageController,
    ];
    return ListenableBuilder(
      listenable: Listenable.merge(listenables),
      builder: (context, _) => _buildLocalizedShell(
        context,
        resolver,
        languageController?.languageCode ?? 'vi',
      ),
    );
  }

  Widget _buildLocalizedShell(
    BuildContext context,
    MobileFeatureFlagResolver resolver,
    String languageCode,
  ) {
    final copy = ConsumerTerminology.forLocale(languageCode);
    final isEnglish = languageCode == 'en';
    final mode = _modeController.mode;

    final chatBody = ChatSurfaceV3(
      apiClient: widget.apiClient,
      sessionStore: widget.sessionStore,
      resolver: resolver,
      languageController: widget.languageController,
    );

    final List<RedesignDestination> destinations;

    switch (mode) {
      case PresentationMode.clinical:
      case PresentationMode.admin:
        destinations = [
          RedesignDestination(
            icon: Icons.dashboard_outlined,
            selectedIcon: Icons.dashboard,
            label: isEnglish ? 'Overview' : 'Tổng quan',
            body: ClinicalOverviewSurface(
              apiClient: widget.apiClient,
              sessionStore: widget.sessionStore,
              resolver: resolver,
              summary: _summary,
              languageController: widget.languageController,
            ),
          ),
          RedesignDestination(
            icon: Icons.groups_outlined,
            selectedIcon: Icons.groups,
            label: isEnglish ? 'Council' : 'Hội chẩn',
            body: CouncilSurfaceV3(
              apiClient: widget.apiClient,
              sessionStore: widget.sessionStore,
            ),
          ),
          RedesignDestination(
            icon: Icons.mic_none_outlined,
            selectedIcon: Icons.mic,
            label: isEnglish ? 'Scribe' : 'Ghi chép',
            body: ScribeSurfaceV3(
              apiClient: widget.apiClient,
              sessionStore: widget.sessionStore,
              resolver: resolver,
            ),
          ),
          RedesignDestination(
            icon: Icons.apps_outlined,
            selectedIcon: Icons.apps,
            label: copy[ConsumerTerm.navigationMore],
            body: MoreScreenV3(
              apiClient: widget.apiClient,
              sessionStore: widget.sessionStore,
              resolver: resolver,
              role: _role,
              themeController: widget.themeController,
              languageController: widget.languageController,
              presentationModeController: _modeController,
            ),
          ),
        ];
        break;

      case PresentationMode.research:
        destinations = [
          RedesignDestination(
            icon: Icons.fact_check_outlined,
            selectedIcon: Icons.fact_check,
            label: isEnglish ? 'Evidence' : 'Bằng chứng',
            body: LivingEvidenceSurface(
              apiClient: widget.apiClient,
              sessionStore: widget.sessionStore,
              languageController: widget.languageController,
            ),
          ),
          RedesignDestination(
            icon: Icons.science_outlined,
            selectedIcon: Icons.science,
            label: isEnglish ? 'Sources' : 'Nguồn',
            body: ResearchScreen(
              apiClient: widget.apiClient,
              sessionStore: widget.sessionStore,
              deepResearchEnabled: resolver.isEnabled('research_mobile_deep'),
            ),
          ),
          RedesignDestination(
            icon: Icons.apps_outlined,
            selectedIcon: Icons.apps,
            label: copy[ConsumerTerm.navigationMore],
            body: MoreScreenV3(
              apiClient: widget.apiClient,
              sessionStore: widget.sessionStore,
              resolver: resolver,
              role: _role,
              themeController: widget.themeController,
              languageController: widget.languageController,
              presentationModeController: _modeController,
            ),
          ),
        ];
        break;

      case PresentationMode.personal:
        destinations = [
          RedesignDestination(
            icon: Icons.today_outlined,
            selectedIcon: Icons.today,
            label: copy[ConsumerTerm.navigationToday],
            body: TodaySurface(
              apiClient: widget.apiClient,
              sessionStore: widget.sessionStore,
              onNeedsOnboarding: () => setState(() => _needsOnboarding = true),
              onAskHealth: () => _openChat(context, resolver),
              onCheckMedicines: () => _openMedicines(context, resolver),
              onSaveHealthInfo: () => _openHealthProfile(context, resolver),
              onPrepareVisit: () => _openVisitPreparation(context, resolver),
              readCache: _lifeMapReadCache,
              languageController: widget.languageController,
            ),
          ),
          RedesignDestination(
            icon: Icons.route_outlined,
            selectedIcon: Icons.route,
            label: copy[ConsumerTerm.navigationLifeMap],
            body: LifeMapSurface(
              apiClient: widget.apiClient,
              sessionStore: widget.sessionStore,
              languageController: widget.languageController,
            ),
          ),
          RedesignDestination(
            icon: Icons.medication_outlined,
            selectedIcon: Icons.medication,
            label: copy[ConsumerTerm.navigationMedicines],
            body: MedicinesHub(
              apiClient: widget.apiClient,
              sessionStore: widget.sessionStore,
              resolver: resolver,
              languageController: widget.languageController,
            ),
          ),
          RedesignDestination(
            icon: Icons.folder_shared_outlined,
            selectedIcon: Icons.folder_shared,
            label: copy[ConsumerTerm.navigationProfile],
            body: ProfileHub(
              apiClient: widget.apiClient,
              sessionStore: widget.sessionStore,
              resolver: resolver,
              role: _role,
              themeController: widget.themeController,
              languageController: widget.languageController,
              presentationModeController: _modeController,
              phrBody: PhrSurfaceV3(
                apiClient: widget.apiClient,
                sessionStore: widget.sessionStore,
                resolver: resolver,
                languageController: widget.languageController,
              ),
            ),
          ),
        ];
        break;
    }

    return AdaptiveClaraShell(
      key: ValueKey<PresentationMode>(mode),
      chatLabel: copy[ConsumerTerm.actionAskClara],
      chatIcon: Icons.forum_rounded,
      chatBody: chatBody,
      destinations: destinations,
      presentationMode: mode,
      presentationModeController: _modeController,
      languageCode: languageCode,
    );
  }

  /// These routes are intentionally explicit rather than synthetic shortcuts:
  /// every card opens the same existing consent-gated surface available from
  /// the unified navigation. None writes health data or bypasses onboarding.
  void _openChat(BuildContext context, MobileFeatureFlagResolver resolver) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => ChatSurfaceV3(
          apiClient: widget.apiClient,
          sessionStore: widget.sessionStore,
          resolver: resolver,
          languageController: widget.languageController,
        ),
      ),
    );
  }

  void _openMedicines(BuildContext context, MobileFeatureFlagResolver resolver) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => MedicinesHub(
          apiClient: widget.apiClient,
          sessionStore: widget.sessionStore,
          resolver: resolver,
          languageController: widget.languageController,
        ),
      ),
    );
  }

  void _openHealthProfile(
    BuildContext context,
    MobileFeatureFlagResolver resolver,
  ) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => PhrSurfaceV3(
          apiClient: widget.apiClient,
          sessionStore: widget.sessionStore,
          resolver: resolver,
          languageController: widget.languageController,
        ),
      ),
    );
  }

  void _openVisitPreparation(
    BuildContext context,
    MobileFeatureFlagResolver resolver,
  ) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => VisitsSurface(
          apiClient: widget.apiClient,
          sessionStore: widget.sessionStore,
          languageController: widget.languageController,
          useLifeMapDraft: resolver.lifeMapVietnameseDraftsEnabled,
        ),
      ),
    );
  }
}
