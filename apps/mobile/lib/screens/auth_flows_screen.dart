import 'package:flutter/material.dart';

import '../core/api_client.dart';

/// Auth-lifecycle parity screens (clara-mobile-feature-parity Req 6.1).
///
/// These cover the account flows the web app exposes but the mobile starter
/// lacked: register, verify-email, forgot-password, and reset-password. They
/// consume the additive [ApiClient.register] / [ApiClient.verifyEmail] /
/// [ApiClient.forgotPassword] / [ApiClient.resetPassword] helpers (task 8.1)
/// and introduce no new CLARA_API contract (Req 15.5). Entry points are wired
/// from the login screen.
///
/// All copy is Vietnamese-first and every error is PII-free (Req 11.1). Each
/// screen contains its own try/catch so a failure never crashes the app
/// (Req 11.4).

/// Registration form: creates an account then routes the user to the
/// email-verification step (Req 6.1).
class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key, required this.apiClient});

  final ApiClient apiClient;

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _fullNameController = TextEditingController();

  bool _acceptedTerms = false;
  bool _acceptedPrivacy = false;
  bool _acceptedMedicalConsent = false;
  bool _isLoading = false;
  String? _error;
  String? _info;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    _fullNameController.dispose();
    super.dispose();
  }

  bool get _consentsComplete =>
      _acceptedTerms && _acceptedPrivacy && _acceptedMedicalConsent;

  Future<void> _register() async {
    final email = _emailController.text.trim();
    final password = _passwordController.text;
    final fullName = _fullNameController.text.trim();

    if (email.isEmpty || password.isEmpty) {
      setState(() => _error = 'Vui lòng nhập email và mật khẩu.');
      return;
    }
    if (!_consentsComplete) {
      setState(() => _error =
          'Vui lòng đồng ý với điều khoản, quyền riêng tư và miễn trừ y tế.');
      return;
    }

    setState(() {
      _isLoading = true;
      _error = null;
      _info = null;
    });

    try {
      await widget.apiClient.register(payload: {
        'email': email,
        'password': password,
        if (fullName.isNotEmpty) 'full_name': fullName,
        'accepted_terms': _acceptedTerms,
        'accepted_privacy': _acceptedPrivacy,
        'accepted_medical_consent': _acceptedMedicalConsent,
      });
      if (!mounted) return;
      // Route to the verification step so the user can confirm their email.
      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(
          builder: (_) => VerifyEmailScreen(apiClient: widget.apiClient),
        ),
      );
    } on ApiException catch (error) {
      setState(() {
        _error = error.statusCode == 409
            ? 'Email này đã được đăng ký. Vui lòng đăng nhập.'
            : error.message;
      });
    } catch (_) {
      setState(() => _error = 'Đăng ký thất bại. Vui lòng thử lại.');
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Đăng ký')),
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
                  TextField(
                    controller: _fullNameController,
                    decoration: const InputDecoration(
                      labelText: 'Họ và tên (tuỳ chọn)',
                      border: OutlineInputBorder(),
                    ),
                    enabled: !_isLoading,
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _emailController,
                    decoration: const InputDecoration(
                      labelText: 'Email',
                      border: OutlineInputBorder(),
                    ),
                    keyboardType: TextInputType.emailAddress,
                    autocorrect: false,
                    enabled: !_isLoading,
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
                  ),
                  const SizedBox(height: 8),
                  CheckboxListTile(
                    value: _acceptedTerms,
                    onChanged: _isLoading
                        ? null
                        : (v) => setState(() => _acceptedTerms = v ?? false),
                    title: const Text('Tôi đồng ý với Điều khoản sử dụng'),
                    controlAffinity: ListTileControlAffinity.leading,
                    contentPadding: EdgeInsets.zero,
                  ),
                  CheckboxListTile(
                    value: _acceptedPrivacy,
                    onChanged: _isLoading
                        ? null
                        : (v) => setState(() => _acceptedPrivacy = v ?? false),
                    title: const Text('Tôi đồng ý với Chính sách quyền riêng tư'),
                    controlAffinity: ListTileControlAffinity.leading,
                    contentPadding: EdgeInsets.zero,
                  ),
                  CheckboxListTile(
                    value: _acceptedMedicalConsent,
                    onChanged: _isLoading
                        ? null
                        : (v) =>
                            setState(() => _acceptedMedicalConsent = v ?? false),
                    title: const Text(
                        'Tôi hiểu CLARA hỗ trợ quyết định, không thay thế bác sĩ'),
                    controlAffinity: ListTileControlAffinity.leading,
                    contentPadding: EdgeInsets.zero,
                  ),
                  const SizedBox(height: 12),
                  FilledButton(
                    style: FilledButton.styleFrom(
                      minimumSize: const Size.fromHeight(48),
                    ),
                    onPressed: _isLoading ? null : _register,
                    child: _isLoading
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Text('Tạo tài khoản'),
                  ),
                  TextButton(
                    onPressed: _isLoading
                        ? null
                        : () => Navigator.of(context).push(
                              MaterialPageRoute<void>(
                                builder: (_) => VerifyEmailScreen(
                                    apiClient: widget.apiClient),
                              ),
                            ),
                    child: const Text('Đã có mã xác thực? Xác thực email'),
                  ),
                  if (_info != null) ...[
                    const SizedBox(height: 8),
                    Text(_info!),
                  ],
                  if (_error != null) ...[
                    const SizedBox(height: 8),
                    Text(
                      _error!,
                      style: TextStyle(
                          color: Theme.of(context).colorScheme.error),
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

/// Verifies an email-verification token (Req 6.1).
class VerifyEmailScreen extends StatefulWidget {
  const VerifyEmailScreen({super.key, required this.apiClient});

  final ApiClient apiClient;

  @override
  State<VerifyEmailScreen> createState() => _VerifyEmailScreenState();
}

class _VerifyEmailScreenState extends State<VerifyEmailScreen> {
  final _tokenController = TextEditingController();

  bool _isLoading = false;
  bool _verified = false;
  String? _error;

  @override
  void dispose() {
    _tokenController.dispose();
    super.dispose();
  }

  Future<void> _verify() async {
    final token = _tokenController.text.trim();
    if (token.isEmpty) {
      setState(() => _error = 'Vui lòng nhập mã xác thực.');
      return;
    }
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      await widget.apiClient.verifyEmail(token: token);
      if (!mounted) return;
      setState(() => _verified = true);
    } on ApiException catch (error) {
      setState(() {
        _error = error.statusCode == 400
            ? 'Mã xác thực không hợp lệ hoặc đã hết hạn.'
            : error.message;
      });
    } catch (_) {
      setState(() => _error = 'Xác thực thất bại. Vui lòng thử lại.');
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Xác thực email')),
      body: Center(
        child: SingleChildScrollView(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: _verified
                  ? Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.verified, size: 48),
                        const SizedBox(height: 12),
                        const Text(
                          'Email của bạn đã được xác thực. Bạn có thể đăng nhập.',
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 16),
                        FilledButton(
                          style: FilledButton.styleFrom(
                            minimumSize: const Size.fromHeight(48),
                          ),
                          onPressed: () =>
                              Navigator.of(context).popUntil((r) => r.isFirst),
                          child: const Text('Về trang đăng nhập'),
                        ),
                      ],
                    )
                  : Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        const Text(
                          'Nhập mã xác thực được gửi tới email của bạn.',
                        ),
                        const SizedBox(height: 12),
                        TextField(
                          controller: _tokenController,
                          decoration: const InputDecoration(
                            labelText: 'Mã xác thực',
                            border: OutlineInputBorder(),
                          ),
                          autocorrect: false,
                          enabled: !_isLoading,
                        ),
                        const SizedBox(height: 16),
                        FilledButton(
                          style: FilledButton.styleFrom(
                            minimumSize: const Size.fromHeight(48),
                          ),
                          onPressed: _isLoading ? null : _verify,
                          child: _isLoading
                              ? const SizedBox(
                                  width: 20,
                                  height: 20,
                                  child:
                                      CircularProgressIndicator(strokeWidth: 2),
                                )
                              : const Text('Xác thực'),
                        ),
                        if (_error != null) ...[
                          const SizedBox(height: 12),
                          Text(
                            _error!,
                            style: TextStyle(
                                color: Theme.of(context).colorScheme.error),
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

/// Requests a password-reset email then routes to the reset step (Req 6.1).
class ForgotPasswordScreen extends StatefulWidget {
  const ForgotPasswordScreen({super.key, required this.apiClient});

  final ApiClient apiClient;

  @override
  State<ForgotPasswordScreen> createState() => _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends State<ForgotPasswordScreen> {
  final _emailController = TextEditingController();

  bool _isLoading = false;
  bool _submitted = false;
  String? _error;

  @override
  void dispose() {
    _emailController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final email = _emailController.text.trim();
    if (email.isEmpty) {
      setState(() => _error = 'Vui lòng nhập email.');
      return;
    }
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      await widget.apiClient.forgotPassword(email: email);
      if (!mounted) return;
      // The server always returns an accepted envelope to avoid account
      // enumeration, so we always show the same neutral confirmation.
      setState(() => _submitted = true);
    } on ApiException catch (error) {
      setState(() => _error = error.message);
    } catch (_) {
      setState(() => _error = 'Yêu cầu thất bại. Vui lòng thử lại.');
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Quên mật khẩu')),
      body: Center(
        child: SingleChildScrollView(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: _submitted
                  ? Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        const Icon(Icons.mark_email_read_outlined, size: 48),
                        const SizedBox(height: 12),
                        const Text(
                          'Nếu email tồn tại trong hệ thống, chúng tôi đã gửi '
                          'hướng dẫn đặt lại mật khẩu. Vui lòng kiểm tra hộp thư.',
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 16),
                        FilledButton(
                          style: FilledButton.styleFrom(
                            minimumSize: const Size.fromHeight(48),
                          ),
                          onPressed: () => Navigator.of(context).push(
                            MaterialPageRoute<void>(
                              builder: (_) => ResetPasswordScreen(
                                  apiClient: widget.apiClient),
                            ),
                          ),
                          child: const Text('Tôi đã có mã đặt lại'),
                        ),
                      ],
                    )
                  : Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        const Text(
                          'Nhập email của bạn để nhận hướng dẫn đặt lại mật khẩu.',
                        ),
                        const SizedBox(height: 12),
                        TextField(
                          controller: _emailController,
                          decoration: const InputDecoration(
                            labelText: 'Email',
                            border: OutlineInputBorder(),
                          ),
                          keyboardType: TextInputType.emailAddress,
                          autocorrect: false,
                          enabled: !_isLoading,
                        ),
                        const SizedBox(height: 16),
                        FilledButton(
                          style: FilledButton.styleFrom(
                            minimumSize: const Size.fromHeight(48),
                          ),
                          onPressed: _isLoading ? null : _submit,
                          child: _isLoading
                              ? const SizedBox(
                                  width: 20,
                                  height: 20,
                                  child:
                                      CircularProgressIndicator(strokeWidth: 2),
                                )
                              : const Text('Gửi yêu cầu'),
                        ),
                        TextButton(
                          onPressed: _isLoading
                              ? null
                              : () => Navigator.of(context).push(
                                    MaterialPageRoute<void>(
                                      builder: (_) => ResetPasswordScreen(
                                          apiClient: widget.apiClient),
                                    ),
                                  ),
                          child: const Text('Tôi đã có mã đặt lại'),
                        ),
                        if (_error != null) ...[
                          const SizedBox(height: 8),
                          Text(
                            _error!,
                            style: TextStyle(
                                color: Theme.of(context).colorScheme.error),
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

/// Resets a password using a reset token (Req 6.1).
class ResetPasswordScreen extends StatefulWidget {
  const ResetPasswordScreen({super.key, required this.apiClient});

  final ApiClient apiClient;

  @override
  State<ResetPasswordScreen> createState() => _ResetPasswordScreenState();
}

class _ResetPasswordScreenState extends State<ResetPasswordScreen> {
  final _tokenController = TextEditingController();
  final _passwordController = TextEditingController();

  bool _isLoading = false;
  bool _reset = false;
  String? _error;

  @override
  void dispose() {
    _tokenController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _reset_() async {
    final token = _tokenController.text.trim();
    final newPassword = _passwordController.text;
    if (token.isEmpty || newPassword.isEmpty) {
      setState(() => _error = 'Vui lòng nhập mã đặt lại và mật khẩu mới.');
      return;
    }
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      await widget.apiClient
          .resetPassword(token: token, newPassword: newPassword);
      if (!mounted) return;
      setState(() => _reset = true);
    } on ApiException catch (error) {
      setState(() {
        _error = error.statusCode == 400
            ? 'Mã đặt lại không hợp lệ hoặc đã hết hạn.'
            : error.message;
      });
    } catch (_) {
      setState(() => _error = 'Đặt lại mật khẩu thất bại. Vui lòng thử lại.');
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Đặt lại mật khẩu')),
      body: Center(
        child: SingleChildScrollView(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: _reset
                  ? Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.lock_reset, size: 48),
                        const SizedBox(height: 12),
                        const Text(
                          'Mật khẩu của bạn đã được đặt lại. Vui lòng đăng nhập '
                          'bằng mật khẩu mới.',
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 16),
                        FilledButton(
                          style: FilledButton.styleFrom(
                            minimumSize: const Size.fromHeight(48),
                          ),
                          onPressed: () =>
                              Navigator.of(context).popUntil((r) => r.isFirst),
                          child: const Text('Về trang đăng nhập'),
                        ),
                      ],
                    )
                  : Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        const Text(
                          'Nhập mã đặt lại từ email và mật khẩu mới của bạn.',
                        ),
                        const SizedBox(height: 12),
                        TextField(
                          controller: _tokenController,
                          decoration: const InputDecoration(
                            labelText: 'Mã đặt lại',
                            border: OutlineInputBorder(),
                          ),
                          autocorrect: false,
                          enabled: !_isLoading,
                        ),
                        const SizedBox(height: 12),
                        TextField(
                          controller: _passwordController,
                          decoration: const InputDecoration(
                            labelText: 'Mật khẩu mới',
                            border: OutlineInputBorder(),
                          ),
                          obscureText: true,
                          enabled: !_isLoading,
                        ),
                        const SizedBox(height: 16),
                        FilledButton(
                          style: FilledButton.styleFrom(
                            minimumSize: const Size.fromHeight(48),
                          ),
                          onPressed: _isLoading ? null : _reset_,
                          child: _isLoading
                              ? const SizedBox(
                                  width: 20,
                                  height: 20,
                                  child:
                                      CircularProgressIndicator(strokeWidth: 2),
                                )
                              : const Text('Đặt lại mật khẩu'),
                        ),
                        if (_error != null) ...[
                          const SizedBox(height: 12),
                          Text(
                            _error!,
                            style: TextStyle(
                                color: Theme.of(context).colorScheme.error),
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
