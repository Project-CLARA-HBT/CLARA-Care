import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'core/api_client.dart';
import 'core/feature_flags.dart';
import 'core/session_store.dart';
import 'experience/app_shell.dart';
import 'experience/home_screen.dart';
import 'experience/language_controller.dart';
import 'experience/onboarding/onboarding_gate.dart';
import 'experience/settings/language_toggle.dart';
import 'screens/dashboard_screen.dart';
import 'screens/login_screen.dart';
import 'screens/phr_screen.dart';
import 'screens/scribe_screen.dart';
import 'theme/clara_theme.dart';
import 'widgets/consent_gate.dart';

class ClaraApp extends StatefulWidget {
  const ClaraApp({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    this.languageController,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  /// App-wide language state for Experience_V2 (Req 9.1, 9.2). Constructed and
  /// hydrated in `main` only when the flag is ON; `null` on the legacy path so
  /// the `MaterialApp` is built without any locale wiring (byte-for-byte the
  /// pre-feature construction).
  final LanguageController? languageController;

  @override
  State<ClaraApp> createState() => _ClaraAppState();
}

class _ClaraAppState extends State<ClaraApp> {
  /// Launch hydration future. Reads persisted credentials from secure storage
  /// and either restores a valid session (Requirement 10.2) or clears the
  /// store when the stored token is expired/invalid (Requirement 10.3).
  late final Future<void> _hydration;

  @override
  void initState() {
    super.initState();
    // Hydrate before deciding the initial route. Guard against unexpected
    // storage failures so a corrupt/expired session never crashes launch:
    // on failure we clear the store and fall through to the login screen.
    _hydration = widget.sessionStore.hydrate().catchError(
      (_) => widget.sessionStore.clear(),
    );
  }

  @override
  Widget build(BuildContext context) {
    // Experience_V2 is purely additive and default OFF (Req 1.1, 1.2, 1.3): the
    // single compile-time gate selects the modern Material 3 theme + adaptive
    // shell root, otherwise the app stays byte-for-byte the legacy experience.
    //
    // Locale wiring (Req 9.1, 9.2) is layered on top and is itself gated: it is
    // applied ONLY when the flag is ON *and* a [LanguageController] was injected
    // by `main`. When that is not the case (legacy path, or flag-on without a
    // controller) we build the unchanged `MaterialApp` below with no locale
    // wiring at all.
    final languageController = widget.languageController;
    if (kMobileExperienceV2Enabled && languageController != null) {
      // V2 with a controller: rebuild whenever the language changes so the
      // selected locale applies app-wide. `flutter_localizations` supplies the
      // Global*Localizations delegates so `MaterialLocalizations` resolves for
      // the Vietnamese ('vi') locale as well as English — without them, setting
      // `locale: vi` leaves the default (English-only) localizations unable to
      // produce `MaterialLocalizations`, which crashes any `AppBar`/Material
      // widget ("No MaterialLocalizations found").
      return ListenableBuilder(
        listenable: languageController,
        builder: (context, _) => MaterialApp(
          title: 'CLARA Mobile',
          theme: ClaraTheme.light(polished: kMobileUxPolishEnabled),
          darkTheme: ClaraTheme.dark(polished: kMobileUxPolishEnabled),
          locale: languageController.locale,
          localizationsDelegates: const <LocalizationsDelegate<dynamic>>[
            GlobalMaterialLocalizations.delegate,
            GlobalWidgetsLocalizations.delegate,
            GlobalCupertinoLocalizations.delegate,
          ],
          supportedLocales: const <Locale>[Locale('vi'), Locale('en')],
          home: _buildHome(),
        ),
      );
    }

    // Legacy / flag-off (and the defensive flag-on-without-controller) path:
    // byte-for-byte the pre-feature `MaterialApp` — no locale, no
    // supportedLocales.
    return MaterialApp(
      title: 'CLARA Mobile',
      // V2: Material 3 light/dark themes from the brand seed, system-driven
      // (Req 2.1, 2.6). Legacy: the existing teal seed `ThemeData`, unchanged.
      theme: kMobileExperienceV2Enabled
          ? ClaraTheme.light(polished: kMobileUxPolishEnabled)
          : ThemeData(
              colorScheme: ColorScheme.fromSeed(seedColor: Colors.teal),
              useMaterial3: true,
            ),
      darkTheme: kMobileExperienceV2Enabled
          ? ClaraTheme.dark(polished: kMobileUxPolishEnabled)
          : null,
      home: _buildHome(),
    );
  }

  /// The hydration-gated launch surface shared by both `MaterialApp`
  /// constructions (legacy and locale-aware). Unchanged from the original
  /// inline `home:` builder.
  Widget _buildHome() {
    return FutureBuilder<void>(
      future: _hydration,
      builder: (context, snapshot) {
        // While hydration is in flight, show a splash so we don't briefly
        // flash the login screen before a valid session is restored.
        if (snapshot.connectionState != ConnectionState.done) {
          return const _LaunchSplash();
        }

        // After hydration completes, react to session changes (login/logout)
        // and route accordingly. A valid restored token resolves to the
        // dashboard (10.2); an absent/cleared token resolves to login (10.3).
        return AnimatedBuilder(
          animation: widget.sessionStore,
          builder: (context, _) {
            if (widget.sessionStore.isAuthenticated) {
              // Consent gate before gated medical content (Req 6.6): after
              // login, if the backend consent status is not accepted, present
              // the acceptance step before routing into the dashboard. The
              // gate is keyed by the access token so it re-evaluates whenever
              // the session changes (e.g. refresh / re-login).
              return ConsentGate(
                key: ValueKey<String?>(widget.sessionStore.accessToken),
                apiClient: widget.apiClient,
                accessToken: widget.sessionStore.accessToken ?? '',
                child: _authenticatedRoot(),
              );
            }
            return LoginScreen(
              apiClient: widget.apiClient,
              sessionStore: widget.sessionStore,
            );
          },
        );
      },
    );
  }

  /// The authenticated surface hosted inside the [ConsentGate].
  ///
  /// Flag OFF (legacy, default): the unchanged [DashboardScreen]. Flag ON
  /// (Experience_V2): the first-run [OnboardingGate] wrapping the adaptive
  /// [AppShell] of primary destinations (Req 1.1–1.3, 3.5, 5.6).
  Widget _authenticatedRoot() {
    if (!kMobileExperienceV2Enabled) {
      return DashboardScreen(
        apiClient: widget.apiClient,
        sessionStore: widget.sessionStore,
      );
    }
    return OnboardingGate(
      child: AppShell(
        destinations: [
          // Trang chủ (Home) — modern role-aware landing (Req 4.6).
          ShellDestination(
            icon: Icons.home_outlined,
            selectedIcon: Icons.home,
            label: 'Trang chủ',
            body: HomeScreen(
              apiClient: widget.apiClient,
              sessionStore: widget.sessionStore,
            ),
          ),
          // Hồ sơ (PHR) — always reachable; enhanced reads gated by the
          // resolver (null summary ⇒ all gates off ⇒ legacy PHR — Req 5.6).
          ShellDestination(
            icon: Icons.folder_shared_outlined,
            selectedIcon: Icons.folder_shared,
            label: 'Hồ sơ',
            body: PhrScreen(
              apiClient: widget.apiClient,
              sessionStore: widget.sessionStore,
              featureFlags: MobileFeatureFlagResolver(),
            ),
          ),
          // Ghi chú (Record / Scribe) — inert unless `scribe_mobile_enabled`
          // is granted; a default resolver fails closed.
          ShellDestination(
            icon: Icons.mic_none,
            selectedIcon: Icons.mic,
            label: 'Ghi chú',
            body: ScribeScreen(
              apiClient: widget.apiClient,
              sessionStore: widget.sessionStore,
              featureFlags: MobileFeatureFlagResolver(),
            ),
          ),
          // Cài đặt (Settings) — the global language toggle (Req 9.1, 9.2)
          // when a controller is available; a calm placeholder otherwise.
          ShellDestination(
            icon: Icons.settings_outlined,
            selectedIcon: Icons.settings,
            label: 'Cài đặt',
            body: _settingsBody(),
          ),
        ],
      ),
    );
  }

  /// The Settings tab body for Experience_V2.
  ///
  /// When a [LanguageController] is available (the normal V2 launch via `main`),
  /// renders the real [LanguageToggle] inside a scrollable list so the language
  /// preference applies app-wide (Req 9.1, 9.2). As a defensive fallback — a V2
  /// build that somehow lacks a controller — it keeps the calm placeholder so
  /// the Settings destination is always reachable.
  Widget _settingsBody() {
    final controller = widget.languageController;
    if (controller == null) {
      return const _SettingsPlaceholder();
    }
    return Scaffold(
      body: ListView(
        children: [
          LanguageToggle(controller: controller),
        ],
      ),
    );
  }
}

/// Minimal launch splash shown while persisted credentials are loaded.
class _LaunchSplash extends StatelessWidget {
  const _LaunchSplash();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(child: CircularProgressIndicator()),
    );
  }
}

/// Temporary Settings tab body for Experience_V2. The language toggle and the
/// rest of the settings surface are added in task 9.2; for now this is a calm
/// Vietnamese-first placeholder so the Settings destination is reachable.
class _SettingsPlaceholder extends StatelessWidget {
  const _SettingsPlaceholder();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(child: Text('Cài đặt')),
    );
  }
}
