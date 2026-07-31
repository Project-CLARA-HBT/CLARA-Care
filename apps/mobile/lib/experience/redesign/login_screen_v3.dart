// Modern login surface for the CLARA_Mobile redesign (Experience_V3).
//
// clara-mobile-redesign, Requirement 10 (redesigned authentication surfaces).
// A polished, light-first sign-in built on the shared design system
// (`ClaraInput`, `ClaraButton`, `ClaraTokens`), replacing the raw-Material
// `LoginScreen`. It preserves the exact auth contract and behavior:
//
//   * `ApiClient.login(email, password)` → persist via `SessionStore.setSession`
//     (Requirement 10.1, 10.2), which routes into the app via the root's
//     session listener.
//   * Friendly Vietnamese-first 401 messaging distinct from other errors
//     (Requirement 10.4).
//   * Coarse, no-PII analytics: `loginViewed` on open, `loginSucceeded` on a
//     successful sign-in — the email/password are NEVER sent to analytics
//     (Requirement 10.5).
//   * Routes to the existing register / forgot-password flows, which inherit
//     the new light palette + input theme automatically (Requirement 10.3).
//
// Additions over the legacy screen: inline empty-field validation, a show/hide
// password toggle, a branded hero header, and ≥48dp tap targets via the shared
// components.

import 'package:flutter/material.dart';

import '../../core/analytics.dart';
import '../../core/api_client.dart';
import '../../core/consumer_terminology.dart';
import '../../core/session_store.dart';
import '../language_controller.dart';
import '../../screens/auth_flows_screen.dart';
import '../../theme/components/clara_button.dart';
import '../../theme/components/clara_input.dart';
import '../../theme/glass/glass_surface.dart';
import '../../theme/glass/glass_tokens.dart';
import '../../theme/tokens.dart';

/// The redesigned, light-first sign-in surface. See file header.
class LoginScreenV3 extends StatefulWidget {
  const LoginScreenV3({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    this.languageController,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  /// Optional app-level locale state. The direct/legacy embedding remains
  /// Vietnamese-first through [ConsumerTerminology]'s fallback.
  final LanguageController? languageController;

  @override
  State<LoginScreenV3> createState() => _LoginScreenV3State();
}

class _LoginScreenV3State extends State<LoginScreenV3> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();

  bool _isLoading = false;
  bool _obscurePassword = true;
  String? _error;
  String? _emailError;
  String? _passwordError;

  ConsumerTerminology get _copy => ConsumerTerminology.forLocale(
        widget.languageController?.languageCode,
      );

  @override
  void initState() {
    super.initState();
    getAnalyticsClient().captureScreenView(MobileAnalyticsEvents.loginViewed);
  }

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _login() async {
    final email = _emailController.text.trim();
    final password = _passwordController.text;

    // Inline, per-field validation (Vietnamese-first).
    final emailError =
        email.isEmpty ? _copy[ConsumerTerm.loginEmailRequired] : null;
    final passwordError =
        password.isEmpty ? _copy[ConsumerTerm.loginPasswordRequired] : null;
    if (emailError != null || passwordError != null) {
      setState(() {
        _emailError = emailError;
        _passwordError = passwordError;
        _error = null;
      });
      return;
    }

    setState(() {
      _isLoading = true;
      _error = null;
      _emailError = null;
      _passwordError = null;
    });

    try {
      final response = await widget.apiClient.login(
        email: email,
        password: password,
      );
      // Persist the authenticated session so the app root routes in and the
      // shell restores it on relaunch (Requirement 10.1, 10.2).
      await widget.sessionStore.setSession(
        email: email,
        accessToken: response.accessToken,
        refreshToken: response.refreshToken,
        role: response.role,
      );
      // No-PII event: the shared client strips PII and only transmits with
      // consent; the email is never attached (Requirement 10.5).
      getAnalyticsClient()
          .capture(const AnalyticsEvent(MobileAnalyticsEvents.loginSucceeded));
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.statusCode == 401
            ? _copy[ConsumerTerm.loginUnauthorized]
            // API errors may contain an upstream/configuration detail and can
            // be in a different locale. Authentication is deliberately a
            // generic, non-account-enumerating error surface.
            : _copy[ConsumerTerm.loginFailed];
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = _copy[ConsumerTerm.loginFailed];
      });
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  void _openRegister() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => RegisterScreen(apiClient: widget.apiClient),
      ),
    );
  }

  void _openForgotPassword() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => ForgotPasswordScreen(apiClient: widget.apiClient),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final languageController = widget.languageController;
    if (languageController != null) {
      return AnimatedBuilder(
        animation: languageController,
        builder: (context, _) => _buildScaffold(context),
      );
    }
    return _buildScaffold(context);
  }

  Widget _buildScaffold(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(ClaraTokens.spaceLg),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // --- Branded hero header ---------------------------------
                  // Pure branding chrome (decorative disc + wordmark), so it
                  // may sit on a liquid-glass hero; the safety tagline below is
                  // kept off glass as plain text. When the ambient GlassScope is
                  // off the same card renders opaque with identical geometry.
                  GlassSurface(
                    blurSigma: GlassTokens.blurCard,
                    radius: GlassTokens.radiusCard,
                    fill: GlassFill.regular,
                    padding: const EdgeInsets.symmetric(
                      horizontal: ClaraTokens.spaceLg,
                      vertical: ClaraTokens.spaceMd,
                    ),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Container(
                          width: 72,
                          height: 72,
                          alignment: Alignment.center,
                          decoration: BoxDecoration(
                            color: scheme.primaryContainer,
                            borderRadius:
                                BorderRadius.circular(ClaraTokens.radiusLg),
                          ),
                          child: Icon(
                            Icons.health_and_safety_rounded,
                            size: 40,
                            color: scheme.onPrimaryContainer,
                          ),
                        ),
                        const SizedBox(height: ClaraTokens.spaceMd),
                        Text(
                          'CLARA',
                          textAlign: TextAlign.center,
                          style: theme.textTheme.headlineMedium?.copyWith(
                            fontWeight: FontWeight.w800,
                            color: scheme.primary,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: ClaraTokens.spaceMd),
                  Text(
                    _copy[ConsumerTerm.loginSafetyTagline],
                    textAlign: TextAlign.center,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: ClaraTokens.spaceXl),

                  // --- Fields ----------------------------------------------
                  ClaraInput(
                    label: _copy[ConsumerTerm.loginEmail],
                    controller: _emailController,
                    keyboardType: TextInputType.emailAddress,
                    textInputAction: TextInputAction.next,
                    enabled: !_isLoading,
                    errorText: _emailError,
                    onChanged: (_) {
                      if (_emailError != null) {
                        setState(() => _emailError = null);
                      }
                    },
                  ),
                  const SizedBox(height: ClaraTokens.spaceMd),
                  _PasswordField(
                    controller: _passwordController,
                    enabled: !_isLoading,
                    obscure: _obscurePassword,
                    errorText: _passwordError,
                    onToggle: () => setState(
                      () => _obscurePassword = !_obscurePassword,
                    ),
                    onChanged: (_) {
                      if (_passwordError != null) {
                        setState(() => _passwordError = null);
                      }
                    },
                    onSubmitted: () => _isLoading ? null : _login(),
                    label: _copy[ConsumerTerm.loginPassword],
                    showPasswordLabel: _copy[ConsumerTerm.loginShowPassword],
                    hidePasswordLabel: _copy[ConsumerTerm.loginHidePassword],
                  ),

                  if (_error != null) ...[
                    const SizedBox(height: ClaraTokens.spaceMd),
                    _ErrorBanner(message: _error!),
                  ],

                  const SizedBox(height: ClaraTokens.spaceLg),
                  ClaraButton.primary(
                    label: _copy[ConsumerTerm.loginSubmit],
                    loading: _isLoading,
                    onPressed: _isLoading ? null : _login,
                  ),
                  const SizedBox(height: ClaraTokens.spaceSm),

                  // --- Secondary actions -----------------------------------
                  Wrap(
                    alignment: WrapAlignment.spaceBetween,
                    runAlignment: WrapAlignment.center,
                    spacing: ClaraTokens.spaceSm,
                    runSpacing: ClaraTokens.spaceXs,
                    children: [
                      TextButton(
                        onPressed: _isLoading ? null : _openRegister,
                        child: Text(_copy[ConsumerTerm.loginCreateAccount]),
                      ),
                      TextButton(
                        onPressed: _isLoading ? null : _openForgotPassword,
                        child: Text(_copy[ConsumerTerm.loginForgotPassword]),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Password field with a show/hide toggle, built on [ClaraInput] chrome via a
/// trailing icon rendered in an overlaid [InputDecorator]-free composition. It
/// uses a raw [TextField] so the suffix toggle can live inside the field while
/// still reading the token-driven `inputDecorationTheme`.
class _PasswordField extends StatelessWidget {
  const _PasswordField({
    required this.controller,
    required this.enabled,
    required this.obscure,
    required this.errorText,
    required this.onToggle,
    required this.onChanged,
    required this.onSubmitted,
    required this.label,
    required this.showPasswordLabel,
    required this.hidePasswordLabel,
  });

  final TextEditingController controller;
  final bool enabled;
  final bool obscure;
  final String? errorText;
  final VoidCallback onToggle;
  final ValueChanged<String> onChanged;
  final VoidCallback onSubmitted;
  final String label;
  final String showPasswordLabel;
  final String hidePasswordLabel;

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      enabled: enabled,
      obscureText: obscure,
      textInputAction: TextInputAction.done,
      onChanged: onChanged,
      onSubmitted: (_) => onSubmitted(),
      decoration: InputDecoration(
        labelText: label,
        errorText: errorText,
        suffixIcon: Semantics(
          button: true,
          label: obscure ? showPasswordLabel : hidePasswordLabel,
          child: IconButton(
            onPressed: enabled ? onToggle : null,
            icon: Icon(
              obscure
                  ? Icons.visibility_outlined
                  : Icons.visibility_off_outlined,
            ),
          ),
        ),
      ),
    );
  }
}

/// A calm, accessible inline error banner (text conveys meaning, not color).
class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(ClaraTokens.spaceMd),
      decoration: BoxDecoration(
        color: scheme.errorContainer,
        borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
      ),
      child: Row(
        children: [
          Icon(Icons.error_outline, color: scheme.onErrorContainer, size: 20),
          const SizedBox(width: ClaraTokens.spaceSm),
          Expanded(
            child: Text(
              message,
              style: TextStyle(color: scheme.onErrorContainer),
            ),
          ),
        ],
      ),
    );
  }
}
