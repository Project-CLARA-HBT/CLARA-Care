import 'package:flutter/material.dart';

import '../core/api_client.dart';

/// A gate that requires the backend medical-disclaimer consent to be accepted
/// before revealing gated medical [child] content (Requirement 6.6).
///
/// After login the app must surface the consent acknowledgement before serving
/// gated medical content WHERE the backend requires it (`/auth/consent-status`).
/// This widget encapsulates that decision so the app shell can wrap any gated
/// surface (e.g. the dashboard) without each screen re-implementing the check.
///
/// Behavior:
///   * **Disabled ([enabled] == false):** renders [child] directly and never
///     calls the API. Used by tests and any caller that opts out of the gate.
///   * **Loading:** shows a spinner while `GET /auth/consent-status` resolves.
///   * **Status load failed:** fails CLOSED — blocks [child] and presents a
///     non-PII retry affordance rather than serving gated content (Req 6.6,
///     11.4). A transient network/server error must never leak gated content.
///   * **`accepted == false`:** renders the consent acceptance step; tapping
///     accept calls `POST /auth/consent` with the server-provided
///     `required_version`, then reveals [child].
///   * **`accepted == true`:** renders [child].
///
/// The widget contains its own async/error handling so a failure never crashes
/// the host shell (Requirement 11.4). It reuses the existing
/// [ApiClient.getConsentStatus] / [ApiClient.acceptConsent] helpers and
/// introduces no new CLARA_API contract (Req 15.5).
class ConsentGate extends StatefulWidget {
  const ConsentGate({
    super.key,
    required this.apiClient,
    required this.accessToken,
    required this.child,
    this.enabled = true,
    this.onAccepted,
  });

  /// Client used to read/accept the medical-disclaimer consent.
  final ApiClient apiClient;

  /// The authenticated access token used for the consent calls.
  final String accessToken;

  /// The gated medical content revealed once consent is accepted.
  final Widget child;

  /// When false the gate is inert and [child] renders unchanged.
  final bool enabled;

  /// Optional callback invoked once acceptance is recorded.
  final VoidCallback? onAccepted;

  @override
  State<ConsentGate> createState() => _ConsentGateState();
}

class _ConsentGateState extends State<ConsentGate> {
  bool _loading = true;
  bool _accepted = false;
  bool _saving = false;
  String? _loadError;
  String? _saveError;

  /// The consent version the server currently requires; stamped onto the
  /// acceptance call so we acknowledge exactly the version we were shown.
  String _requiredVersion = '';

  @override
  void initState() {
    super.initState();
    if (widget.enabled) {
      _evaluate();
    } else {
      // Gate disabled: pass through to the child without touching the API.
      _loading = false;
      _accepted = true;
    }
  }

  Future<void> _evaluate() async {
    setState(() {
      _loading = true;
      _loadError = null;
    });
    try {
      final status = await widget.apiClient
          .getConsentStatus(accessToken: widget.accessToken);
      if (!mounted) return;
      final accepted = status['accepted'] == true;
      final requiredVersion =
          (status['required_version'] as String?)?.trim() ?? '';
      setState(() {
        _accepted = accepted;
        _requiredVersion = requiredVersion;
        _loading = false;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        // Fail closed: an unreadable status blocks gated content (Req 6.6).
        _loadError = error.message;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loadError =
            'Không thể kiểm tra trạng thái đồng ý. Vui lòng thử lại.';
        _loading = false;
      });
    }
  }

  Future<void> _accept() async {
    setState(() {
      _saving = true;
      _saveError = null;
    });
    try {
      await widget.apiClient.acceptConsent(
        accessToken: widget.accessToken,
        consentVersion: _requiredVersion,
      );
      if (!mounted) return;
      setState(() {
        _accepted = true;
        _saving = false;
      });
      widget.onAccepted?.call();
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _saveError = error.message;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _saveError = 'Không thể lưu xác nhận. Vui lòng thử lại.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.enabled || _accepted) {
      return widget.child;
    }
    if (_loading) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }
    if (_loadError != null) {
      return _ConsentUnavailableView(
        message: _loadError!,
        onRetry: _evaluate,
      );
    }
    return _ConsentAcceptanceView(
      version: _requiredVersion,
      saving: _saving,
      error: _saveError,
      onAccept: _accept,
    );
  }
}

/// Fail-closed placeholder shown when the consent status could not be read.
/// Surfaces a non-PII message and a retry, rendered IN PLACE OF the gated
/// content so nothing leaks while the status is unknown (Req 6.6, 11.4).
class _ConsentUnavailableView extends StatelessWidget {
  const _ConsentUnavailableView({
    required this.message,
    required this.onRetry,
  });

  final String message;
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Đồng ý sử dụng')),
      body: Center(
        child: SingleChildScrollView(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.cloud_off, color: theme.colorScheme.error),
                  const SizedBox(height: 12),
                  Text(
                    message,
                    textAlign: TextAlign.center,
                    style: TextStyle(color: theme.colorScheme.error),
                  ),
                  const SizedBox(height: 16),
                  Semantics(
                    button: true,
                    label: 'Thử lại',
                    child: FilledButton.icon(
                      style: FilledButton.styleFrom(
                        minimumSize: const Size.fromHeight(48),
                      ),
                      onPressed: () => onRetry(),
                      icon: const Icon(Icons.refresh),
                      label: const Text('Thử lại'),
                    ),
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

/// Presentational consent acceptance step. Status is conveyed by text (not
/// color alone) and the action exposes a semantics label + ≥48dp target
/// (Requirement 10.1, 10.2, 10.5).
class _ConsentAcceptanceView extends StatelessWidget {
  const _ConsentAcceptanceView({
    required this.version,
    required this.saving,
    required this.error,
    required this.onAccept,
  });

  final String version;
  final bool saving;
  final String? error;
  final VoidCallback onAccept;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Đồng ý sử dụng')),
      body: Center(
        child: SingleChildScrollView(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Row(
                        children: [
                          const Icon(Icons.health_and_safety_outlined),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              'Xác nhận trước khi sử dụng',
                              style: theme.textTheme.titleMedium,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Text(
                        'CLARA là phần mềm hỗ trợ quyết định dựa trên dữ liệu '
                        'bạn tự khai báo — không phải thiết bị y tế và không '
                        'thay thế bác sĩ. Vui lòng đọc và đồng ý với tuyên bố '
                        'miễn trừ y tế trước khi tiếp tục.',
                        style: theme.textTheme.bodyMedium,
                      ),
                      const SizedBox(height: 10),
                      Text(
                        'Luôn tham khảo ý kiến của bác sĩ có chuyên môn cho các '
                        'quyết định y tế.',
                        style: theme.textTheme.bodyMedium,
                      ),
                      if (version.isNotEmpty) ...[
                        const SizedBox(height: 10),
                        Text(
                          'Phiên bản đồng ý: $version',
                          style: theme.textTheme.bodySmall,
                        ),
                      ],
                      const SizedBox(height: 16),
                      Semantics(
                        button: true,
                        label: 'Tôi đồng ý',
                        child: SizedBox(
                          width: double.infinity,
                          child: FilledButton(
                            style: FilledButton.styleFrom(
                              minimumSize: const Size.fromHeight(48),
                            ),
                            onPressed: saving ? null : onAccept,
                            child: saving
                                ? const SizedBox(
                                    width: 20,
                                    height: 20,
                                    child: CircularProgressIndicator(
                                        strokeWidth: 2),
                                  )
                                : const Text('Tôi đồng ý'),
                          ),
                        ),
                      ),
                      if (error != null) ...[
                        const SizedBox(height: 12),
                        Text(
                          error!,
                          style: TextStyle(color: theme.colorScheme.error),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
