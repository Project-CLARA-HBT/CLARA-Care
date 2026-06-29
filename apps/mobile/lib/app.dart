import 'package:flutter/material.dart';

import 'core/api_client.dart';
import 'core/session_store.dart';
import 'screens/dashboard_screen.dart';
import 'screens/login_screen.dart';
import 'widgets/consent_gate.dart';

class ClaraApp extends StatefulWidget {
  const ClaraApp({
    super.key,
    required this.apiClient,
    required this.sessionStore,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

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
    return MaterialApp(
      title: 'CLARA Mobile',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.teal),
        useMaterial3: true,
      ),
      home: FutureBuilder<void>(
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
                  child: DashboardScreen(
                    apiClient: widget.apiClient,
                    sessionStore: widget.sessionStore,
                  ),
                );
              }
              return LoginScreen(
                apiClient: widget.apiClient,
                sessionStore: widget.sessionStore,
              );
            },
          );
        },
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
