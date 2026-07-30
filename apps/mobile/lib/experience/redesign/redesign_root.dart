// Authenticated root for the CLARA_Mobile redesign (Experience_V3).
//
// clara-mobile-redesign, Requirement 2 (restructured information architecture)
// + Requirement 11 (safety/RBAC preserved).
//
// Loads the role-scoped `mobile/summary` once, builds a single
// [MobileFeatureFlagResolver] from it, and assembles the [RedesignShell] with:
//
//   * Center circular Chat action → the redesigned Chat surface.
//   * Four flanking destinations: Trang chủ (Home), Tủ thuốc (Cabinet),
//     Hồ sơ (PHR), Thêm (More).
//
// Capability gates continue to flow through the resolver (fail-closed: a
// null/unloadable summary resolves every gate to its build-time default, all
// off in a normal build). Individual surfaces render their own inert/placeholder
// states when their gate is off, so the shell never needs to hide a slot.
//
// This root is only selected by `app.dart` when `kMobileRedesignEnabled` is on,
// and always sits INSIDE the existing `ConsentGate` (consent precedes any
// medical content — INV-1).

import 'package:flutter/material.dart';

import '../../core/analytics.dart';
import '../../core/api_client.dart';
import '../../core/consumer_terminology.dart';
import '../../core/feature_flags.dart';
import '../../core/session_store.dart';
import '../../theme/glass/glass_scope.dart';
import '../language_controller.dart';
import '../theme_controller.dart';
import '../redesign_shell.dart';
import 'home_screen_v3.dart';
import 'more_screen_v3.dart';
import 'cabinet_screen_v3.dart';
import 'chat_surface_v3.dart';
import 'phr_surface_v3.dart';

/// Coarse, no-PII screen-view event for the redesigned shell.
const String kRedesignShellViewedEvent = 'mobile_redesign_shell_viewed';

/// The redesigned authenticated root: loads the role-scoped summary once, then
/// hosts the center-Chat shell with its flanking destinations.
class RedesignRoot extends StatefulWidget {
  const RedesignRoot({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    this.themeController,
    this.languageController,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  /// App-wide theme-mode state, threaded to Settings (Appearance section).
  final ThemeController? themeController;

  /// App-wide language state, threaded to Settings (Language section).
  final LanguageController? languageController;

  @override
  State<RedesignRoot> createState() => _RedesignRootState();
}

class _RedesignRootState extends State<RedesignRoot> {
  bool _loading = true;
  Map<String, dynamic>? _summary;

  @override
  void initState() {
    super.initState();
    getAnalyticsClient().captureScreenView(kRedesignShellViewedEvent);
    _loadSummary();
  }

  String get _role => widget.sessionStore.role ?? 'normal';

  ConsumerTerminology get _copy => ConsumerTerminology.forLocale(
        widget.languageController?.languageCode,
      );

  Future<void> _loadSummary() async {
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) {
      setState(() => _loading = false);
      return;
    }
    try {
      final data = await widget.apiClient.getMobileSummary(accessToken: token);
      if (!mounted) return;
      setState(() {
        _summary = data;
        _loading = false;
      });
    } catch (_) {
      // Fail-closed: an unloadable summary leaves every capability gate at its
      // build-time default (all off in a normal build). The shell still renders
      // so the user is never stranded; privileged surfaces stay inert.
      if (!mounted) return;
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    // ONE resolver built from the loaded role-scoped summary, reused for every
    // gate — mirrors HomeScreen/DashboardScreen. A null summary ⇒ all gates off.
    final resolver = MobileFeatureFlagResolver(summary: _summary);

    // Seed the liquid-glass capability scope once here so every descendant
    // GlassSurface resolves a single decision (build gate AND device capability).
    // When the build gate or device says no, descendants render opaque (R1, R6).
    return GlassScopeProvider(
      child: _buildShell(resolver),
    );
  }

  Widget _buildShell(MobileFeatureFlagResolver resolver) {
    return RedesignShell(
      chatLabel: _copy[ConsumerTerm.actionAskClara],
      chatIcon: Icons.forum_rounded,
      chatBody: ChatSurfaceV3(
        apiClient: widget.apiClient,
        sessionStore: widget.sessionStore,
        resolver: resolver,
        languageController: widget.languageController,
      ),
      destinations: [
        RedesignDestination(
          icon: Icons.home_outlined,
          selectedIcon: Icons.home,
          label: _copy[ConsumerTerm.navigationToday],
          body: HomeScreenV3(
            apiClient: widget.apiClient,
            sessionStore: widget.sessionStore,
            resolver: resolver,
            summary: _summary,
          ),
        ),
        RedesignDestination(
          icon: Icons.medication_outlined,
          selectedIcon: Icons.medication,
          label: _copy[ConsumerTerm.navigationMedicines],
          body: CabinetScreenV3(
            apiClient: widget.apiClient,
            sessionStore: widget.sessionStore,
            resolver: resolver,
            languageController: widget.languageController,
          ),
        ),
        RedesignDestination(
          icon: Icons.folder_shared_outlined,
          selectedIcon: Icons.folder_shared,
          label: _copy[ConsumerTerm.navigationProfile],
          body: PhrSurfaceV3(
            apiClient: widget.apiClient,
            sessionStore: widget.sessionStore,
            resolver: resolver,
            languageController: widget.languageController,
          ),
        ),
        RedesignDestination(
          icon: Icons.apps_outlined,
          selectedIcon: Icons.apps,
          label: _copy[ConsumerTerm.navigationMore],
          body: MoreScreenV3(
            apiClient: widget.apiClient,
            sessionStore: widget.sessionStore,
            resolver: resolver,
            role: _role,
            themeController: widget.themeController,
            languageController: widget.languageController,
          ),
        ),
      ],
    );
  }
}
