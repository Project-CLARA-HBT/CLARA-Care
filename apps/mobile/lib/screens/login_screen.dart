import 'package:flutter/material.dart';

import '../core/analytics.dart';
import '../core/api_client.dart';
import '../core/session_store.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({
    super.key,
    required this.apiClient,
    required this.sessionStore,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();

  bool _isLoading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    // Named product event for the primary login screen view. The shared client
    // is a safe no-op until analytics is configured AND consent is granted.
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

    if (email.isEmpty || password.isEmpty) {
      setState(() {
        _error = 'Vui lòng nhập email và mật khẩu.';
      });
      return;
    }

    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final response = await widget.apiClient.login(
        email: email,
        password: password,
      );
      // Persist the authenticated session via the PersistentSessionStore so the
      // app shell restores it on relaunch (Requirements 10.1, 10.2).
      await widget.sessionStore.setSession(
        email: email,
        accessToken: response.accessToken,
        refreshToken: response.refreshToken,
        role: response.role,
      );
      // Named product event for a successful sign-in. PII (email) is never
      // sent: the shared client strips PII and only transmits with consent.
      getAnalyticsClient()
          .capture(const AnalyticsEvent(MobileAnalyticsEvents.loginSucceeded));
    } on ApiException catch (error) {
      setState(() {
        _error = error.statusCode == 401
            ? 'Đăng nhập thất bại. Vui lòng kiểm tra lại thông tin.'
            : error.message;
      });
    } catch (_) {
      setState(() {
        _error = 'Đăng nhập thất bại. Vui lòng thử lại.';
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Đăng nhập'),
      ),
      body: Center(
        child: SingleChildScrollView(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    'CLARA',
                    style: Theme.of(context).textTheme.headlineSmall,
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Đăng nhập để truy cập CLARA Chat, Self-Med và các công cụ chuyên môn.',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 13),
                  ),
                  const SizedBox(height: 20),
                  TextField(
                    controller: _emailController,
                    decoration: const InputDecoration(
                      labelText: 'Email',
                      border: OutlineInputBorder(),
                    ),
                    keyboardType: TextInputType.emailAddress,
                    autocorrect: false,
                    enabled: !_isLoading,
                    onSubmitted: (_) => _isLoading ? null : _login(),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _passwordController,
                    decoration: const InputDecoration(
                      labelText: 'Mật khẩu',
                      border: OutlineInputBorder(),
                    ),
                    obscureText: true,
                    enabled: !_isLoading,
                    onSubmitted: (_) => _isLoading ? null : _login(),
                  ),
                  const SizedBox(height: 16),
                  FilledButton(
                    onPressed: _isLoading ? null : _login,
                    child: _isLoading
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Text('Đăng nhập'),
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 12),
                    Text(
                      _error!,
                      style:
                          TextStyle(color: Theme.of(context).colorScheme.error),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
