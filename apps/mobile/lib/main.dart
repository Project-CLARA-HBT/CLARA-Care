import 'package:flutter/material.dart';

import 'app.dart';
import 'core/api_client.dart';
import 'core/session_store.dart';

// Default to the documented local dev API port (8100). The web app and API
// docs (README) run the gateway on 8100; the previous 8000 default was config
// drift (audit MOB-5). Override at build time with
// `--dart-define=CLARA_API_BASE_URL=...`.
const _defaultApiBaseUrl = String.fromEnvironment(
  'CLARA_API_BASE_URL',
  defaultValue: 'http://localhost:8100',
);

void main() {
  WidgetsFlutterBinding.ensureInitialized();

  final sessionStore = SessionStore();
  final apiClient = ApiClient(baseUrl: _defaultApiBaseUrl);

  runApp(
    ClaraApp(
      apiClient: apiClient,
      sessionStore: sessionStore,
    ),
  );
}
