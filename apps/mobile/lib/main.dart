import 'package:flutter/material.dart';

import 'app.dart';
import 'core/api_client.dart';
import 'core/feature_flags.dart';
import 'core/public_share_link.dart';
import 'core/session_store.dart';
import 'experience/language_controller.dart';
import 'experience/theme_controller.dart';
import 'widgets/screen_error_boundary.dart';

// Default to the documented local dev API port (8100). The web app and API
// docs (README) run the gateway on 8100; the previous 8000 default was config
// drift (audit MOB-5). Override at build time with
// `--dart-define=CLARA_API_BASE_URL=...`.
const _defaultApiBaseUrl = String.fromEnvironment(
  'CLARA_API_BASE_URL',
  defaultValue: 'http://localhost:8100',
);

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  ScreenErrorBoundary.install();

  final sessionStore = SessionStore();
  final apiClient = ApiClient(baseUrl: _defaultApiBaseUrl);
  final publicShareLinks = PublicShareLinkController();
  await publicShareLinks.start();

  // Enable pre-flight expiry refresh + single 401-retry against /auth/refresh,
  // persisting or clearing the secure-storage session (Req 6.2, 6.3). Additive:
  // the client behaves exactly as before until these hooks are attached.
  apiClient.authHooks = SessionStoreAuthHooks(sessionStore);

  // Experience_V2 only: construct the app-wide language controller and hydrate
  // the persisted preference before the first frame so the locale applies on
  // launch (Req 9.1, 9.2). When the flag is OFF we pass null, leaving the
  // legacy launch path byte-for-byte unchanged.
  //
  // The redesign (Experience_V3) also uses the language controller and adds an
  // app-wide theme-mode controller (light-mode-first) hydrated before the first
  // frame so the persisted theme applies on launch. Both are constructed when
  // EITHER the redesign or the legacy V2 flag is on; the redesign path
  // additionally wires the theme controller.
  final bool needsLocaleWiring = kMobileUnifiedEnabled ||
      kMobileRedesignEnabled ||
      kMobileExperienceV2Enabled;
  LanguageController? languageController;
  if (needsLocaleWiring) {
    languageController = LanguageController();
    await languageController.load();
  }

  ThemeController? themeController;
  if (kMobileUnifiedEnabled || kMobileRedesignEnabled) {
    themeController = ThemeController();
    await themeController.load();
  }

  runApp(
    ClaraApp(
      apiClient: apiClient,
      sessionStore: sessionStore,
      publicShareLinks: publicShareLinks,
      languageController: languageController,
      themeController: themeController,
    ),
  );
}
