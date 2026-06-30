import 'package:flutter/material.dart';

import 'app.dart';
import 'core/api_client.dart';
import 'core/feature_flags.dart';
import 'core/session_store.dart';
import 'experience/language_controller.dart';

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

  final sessionStore = SessionStore();
  final apiClient = ApiClient(baseUrl: _defaultApiBaseUrl);

  // Enable pre-flight expiry refresh + single 401-retry against /auth/refresh,
  // persisting or clearing the secure-storage session (Req 6.2, 6.3). Additive:
  // the client behaves exactly as before until these hooks are attached.
  apiClient.authHooks = SessionStoreAuthHooks(sessionStore);

  // Experience_V2 only: construct the app-wide language controller and hydrate
  // the persisted preference before the first frame so the locale applies on
  // launch (Req 9.1, 9.2). When the flag is OFF we pass null, leaving the
  // legacy launch path byte-for-byte unchanged.
  LanguageController? languageController;
  if (kMobileExperienceV2Enabled) {
    languageController = LanguageController();
    await languageController.load();
  }

  runApp(
    ClaraApp(
      apiClient: apiClient,
      sessionStore: sessionStore,
      languageController: languageController,
    ),
  );
}
