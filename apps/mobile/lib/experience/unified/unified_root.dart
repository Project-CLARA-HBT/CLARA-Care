// Authenticated root for CLARA_Mobile Unified (spec: clara-mobile-unified).
//
// Collapses the three parallel experience layers (legacy Dashboard,
// Experience_V2, redesign V3) into ONE product-aligned consumer information
// architecture that mirrors the web app:
//
//   Center action  → Hỏi CLARA (Chat, folds deep research)
//   Destinations   → Hôm nay (Today) · LifeMap · Thuốc & an toàn (Medicines) ·
//                    Hồ sơ (Profile hub)
//
// Responsibilities:
//   1. Load the role-scoped `mobile/summary` once → one MobileFeatureFlagResolver
//      (fail-closed: a null/unloadable summary leaves every gate at its
//      build-time default, all off in a normal build).
//   2. Server-backed first-run gate: read `GET /phr/onboarding`; while
//      `needs_onboarding` is true, present the OnboardingFlow (all roles, not
//      just consumers). On complete/skip, re-enter the shell.
//   3. Host the adaptive shell (reusing the built RedesignShell) with the
//      consumer destinations and the center Chat action.
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
import '../../theme/glass/glass_scope.dart';
import '../redesign/chat_surface_v3.dart' show ChatSurfaceV3;
import '../redesign/phr_surface_v3.dart' show PhrSurfaceV3;
import '../language_controller.dart';
import '../redesign_shell.dart';
import '../theme_controller.dart';
import 'lifemap_surface.dart';
import 'medicines_hub.dart';
import 'onboarding_flow.dart';
import 'profile_hub.dart';
import 'today_surface.dart';

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
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;
  final ThemeController? themeController;
  final LanguageController? languageController;

  @override
  State<UnifiedRoot> createState() => _UnifiedRootState();
}

class _UnifiedRootState extends State<UnifiedRoot> {
  late final LifeMapReadCache _lifeMapReadCache = LifeMapReadCache();
  bool _loading = true;
  Map<String, dynamic>? _summary;

  /// `null` while unknown; `true` while the first-run flow should be shown.
  bool _needsOnboarding = false;

  @override
  void initState() {
    super.initState();
    getAnalyticsClient().captureScreenView(kUnifiedShellViewedEvent);
    _bootstrap();
  }

  String get _role => widget.sessionStore.role ?? 'normal';

  Future<void> _bootstrap() async {
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) {
      if (mounted) setState(() => _loading = false);
      return;
    }
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
    try {
      final onboarding =
          await widget.apiClient.getPhrOnboarding(accessToken: token);
      needsOnboarding = onboarding['needs_onboarding'] == true;
    } catch (_) {
      needsOnboarding = false;
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
    if (languageController == null) {
      return _buildLocalizedShell(resolver, 'vi');
    }
    return AnimatedBuilder(
      animation: languageController,
      builder: (context, _) =>
          _buildLocalizedShell(resolver, languageController.languageCode),
    );
  }

  Widget _buildLocalizedShell(
    MobileFeatureFlagResolver resolver,
    String languageCode,
  ) {
    final copy = ConsumerTerminology.forLocale(languageCode);
    return RedesignShell(
      chatLabel: copy[ConsumerTerm.actionAskClara],
      chatIcon: Icons.forum_rounded,
      chatBody: ChatSurfaceV3(
        apiClient: widget.apiClient,
        sessionStore: widget.sessionStore,
        resolver: resolver,
      ),
      destinations: [
        RedesignDestination(
          icon: Icons.today_outlined,
          selectedIcon: Icons.today,
          label: copy[ConsumerTerm.navigationToday],
          body: TodaySurface(
            apiClient: widget.apiClient,
            sessionStore: widget.sessionStore,
            onNeedsOnboarding: () => setState(() => _needsOnboarding = true),
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
            phrBody: PhrSurfaceV3(
              apiClient: widget.apiClient,
              sessionStore: widget.sessionStore,
              resolver: resolver,
            ),
          ),
        ),
      ],
    );
  }
}
