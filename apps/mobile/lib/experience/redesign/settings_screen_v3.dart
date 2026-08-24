// Settings surface for CLARA_Mobile redesign (delegates to unified SettingsSurface).

import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/session_store.dart';
import '../language_controller.dart';
import '../presentation_mode.dart';
import '../theme_controller.dart';
import '../unified/settings_surface.dart';

/// The complete Settings ("Cài đặt") surface for Experience_V3, delegating
/// to the unified [SettingsSurface] (Spec v5 Section 7.9).
class SettingsScreenV3 extends StatelessWidget {
  const SettingsScreenV3({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    this.themeController,
    this.languageController,
    this.presentationModeController,
  });

  /// API client, used for server-side logout on sign-out.
  final ApiClient apiClient;

  /// The session/credential store.
  final SessionStore sessionStore;

  /// App-wide theme-mode state.
  final ThemeController? themeController;

  /// App-wide language state.
  final LanguageController? languageController;

  /// Optional presentation mode controller.
  final PresentationModeController? presentationModeController;

  @override
  Widget build(BuildContext context) {
    return SettingsSurface(
      apiClient: apiClient,
      sessionStore: sessionStore,
      themeController: themeController,
      languageController: languageController,
      presentationModeController: presentationModeController,
    );
  }
}
