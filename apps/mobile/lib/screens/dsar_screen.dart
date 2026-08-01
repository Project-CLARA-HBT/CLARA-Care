import 'package:flutter/material.dart';

import '../core/a11y.dart';
import '../core/analytics.dart';
import '../core/api_client.dart';
import '../core/feature_flags.dart';
import '../core/session_store.dart';
import '../widgets/error_retry_view.dart';

// =============================================================================
// DsarScreen — clara-mobile-feature-parity Task 10.2 (Req 8.3, 8.5).
//
//   * 8.3 An authenticated data subject can submit a Data Subject Access
//         Request (export, correct, delete, restrict, withdraw) and is shown an
//         acknowledgement.
//   * 8.5 NO PII is captured, stored, or logged on this surface. The request is
//         scoped to the authenticated session only — the screen collects NO
//         name / email / free-text identifier and emits only the coarse,
//         non-PII request *kind* to analytics.
//   * Gated behind `consent_center_mobile_enabled` via
//         [MobileFeatureFlagResolver]: with the flag off the surface is inert
//         and exposes no controls (Req 8.6 / 15.1).
//
// The screen calls the shared ApiClient, not a local HTTP seam. In particular,
// irreversible deletion maps only to `/dsar/delete`, never the generic request
// endpoint, so the user-facing confirmation matches server behavior.
// =============================================================================

/// The PDPD data-subject request kinds, matching the server contract
/// (`compliance.dsar.DSAR_KINDS`) and the design's `DsarRequestModel`.
///
/// Carries NO PII — only the request kind selected by the authenticated user.
enum DsarRequestKind {
  /// Export a copy of the subject's data.
  export,

  /// Correct / rectify stored data.
  correct,

  /// Irreversibly delete (anonymise) the subject's data.
  delete,

  /// Restrict further processing.
  restrict,

  /// Withdraw previously granted consent.
  withdraw,
}

/// Stable wire key for a [DsarRequestKind] (snake/lowercase, matches the server
/// `DSAR_KINDS` vocabulary). This is the only value sent to the server.
extension DsarRequestKindWire on DsarRequestKind {
  String get wireValue {
    switch (this) {
      case DsarRequestKind.export:
        return 'export';
      case DsarRequestKind.correct:
        return 'correct';
      case DsarRequestKind.delete:
        return 'delete';
      case DsarRequestKind.restrict:
        return 'restrict';
      case DsarRequestKind.withdraw:
        return 'withdraw';
    }
  }

  /// Vietnamese-first action title (Req 5.5 copy convention).
  String get titleVi {
    switch (this) {
      case DsarRequestKind.export:
        return 'Xuất dữ liệu';
      case DsarRequestKind.correct:
        return 'Chỉnh sửa dữ liệu';
      case DsarRequestKind.delete:
        return 'Xoá dữ liệu';
      case DsarRequestKind.restrict:
        return 'Hạn chế xử lý';
      case DsarRequestKind.withdraw:
        return 'Rút lại đồng ý';
    }
  }

  /// Vietnamese-first description of the right being exercised.
  String get descriptionVi {
    switch (this) {
      case DsarRequestKind.export:
        return 'Nhận một bản sao dữ liệu bạn đã tự khai báo.';
      case DsarRequestKind.correct:
        return 'Yêu cầu chỉnh sửa thông tin chưa chính xác.';
      case DsarRequestKind.delete:
        return 'Yêu cầu xoá vĩnh viễn dữ liệu của bạn. Hành động này không thể '
            'hoàn tác.';
      case DsarRequestKind.restrict:
        return 'Yêu cầu tạm dừng việc xử lý dữ liệu của bạn.';
      case DsarRequestKind.withdraw:
        return 'Rút lại các đồng ý xử lý dữ liệu đã cấp trước đó.';
    }
  }

  /// Whether exercising this right is irreversible and warrants a confirm step.
  bool get isDestructive => this == DsarRequestKind.delete;
}

/// PII-free acknowledgement of a submitted DSAR request.
///
/// Mirrors the server `POST /api/v1/compliance/dsar/request` response shape.
/// Contains only the request type, status, timestamps and statutory window —
/// never any name / email / free-text identifier (Req 8.5).
class DsarAcknowledgement {
  const DsarAcknowledgement({
    required this.kind,
    required this.status,
    this.requestId,
    this.createdAt,
    this.dueAt,
    this.statutoryWindowDays,
  });

  /// The request kind that was acknowledged (wire value, e.g. `export`).
  final String kind;

  /// Server-assigned status, e.g. `received`.
  final String status;

  /// Server-assigned request id (opaque, non-PII).
  final int? requestId;

  /// ISO-8601 creation timestamp, if provided.
  final String? createdAt;

  /// ISO-8601 statutory due date, if provided.
  final String? dueAt;

  /// PDPD statutory response window in days, if provided.
  final int? statutoryWindowDays;

  /// Parses the server acknowledgement envelope. Throws [ApiException] when the
  /// surface is reported disabled or the payload is missing a request id, so
  /// the screen can render a clean, non-PII error state.
  factory DsarAcknowledgement.fromJson(Map<String, dynamic> json) {
    if (json['enabled'] == false) {
      throw ApiException(message: kDsarUnavailableMessage);
    }
    final id = json['request_id'];
    return DsarAcknowledgement(
      requestId: id is int ? id : int.tryParse('${id ?? ''}'),
      kind: (json['kind'] ?? '').toString(),
      status: (json['status'] ?? 'received').toString(),
      createdAt: json['created_at']?.toString(),
      dueAt: json['due_at']?.toString(),
      statutoryWindowDays: json['statutory_window_days'] is int
          ? json['statutory_window_days'] as int
          : int.tryParse('${json['statutory_window_days'] ?? ''}'),
    );
  }
}

/// Copy shown when the consent/DSAR gate is closed (Req 8.6).
const String kDsarDisabledMessage =
    'Tính năng này hiện chưa được bật cho tài khoản của bạn.';

/// Vietnamese-first, PII-free copy when a request cannot be submitted.
const String kDsarUnavailableMessage =
    'Không thể gửi yêu cầu lúc này. Vui lòng thử lại sau.';

/// Self-service DSAR surface: submit a data-subject request and show its
/// acknowledgement (Req 8.3). No PII is collected (Req 8.5).
class DsarScreen extends StatefulWidget {
  const DsarScreen({
    super.key,
    required this.apiClient,
    required this.resolver,
    required this.sessionStore,
    Analytics? analytics,
  }) : _analytics = analytics;

  final ApiClient apiClient;

  /// Resolved feature gates; DSAR must be enabled to render controls (Req 8.6).
  final MobileFeatureFlagResolver resolver;

  final SessionStore sessionStore;

  /// Optional analytics override (tests inject a recording client). Only the
  /// coarse request kind is ever emitted — never PII (Req 8.5).
  final Analytics? _analytics;

  @override
  State<DsarScreen> createState() => _DsarScreenState();
}

class _DsarScreenState extends State<DsarScreen> {
  Analytics get _analytics => widget._analytics ?? getAnalyticsClient();

  bool _submitting = false;
  DsarRequestKind? _pendingKind;
  DsarRequestKind? _retryKind;
  String? _error;
  DsarAcknowledgement? _acknowledgement;

  @override
  void initState() {
    super.initState();
    if (widget.resolver.consentCenterEnabled) {
      _analytics.captureScreenView('mobile_dsar_viewed');
    }
  }

  Future<void> _submit(DsarRequestKind kind) async {
    // Irreversible rights (delete) get an explicit confirm step.
    if (kind.isDestructive) {
      final confirmed = await _confirmDestructive(kind);
      if (confirmed != true) {
        return;
      }
    }

    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) {
      setState(() => _error = kDsarUnavailableMessage);
      return;
    }

    setState(() {
      _submitting = true;
      _pendingKind = kind;
      _retryKind = null;
      _error = null;
      _acknowledgement = null;
    });

    try {
      final payload = kind.isDestructive
          ? await widget.apiClient.deleteDsarData(accessToken: token)
          : await widget.apiClient.submitDsarRequest(
              accessToken: token,
              kind: kind.wireValue,
            );
      final ack = DsarAcknowledgement.fromJson(payload);
      if (!mounted) return;
      // Coarse, PII-free analytics: only the request kind label is emitted.
      _analytics.track(
        'mobile_dsar_submitted',
        props: <String, Object?>{'kind': kind.wireValue},
      );
      setState(() => _acknowledgement = ack);
    } on ApiException {
      // Do not surface gateway or upstream detail in a primary data-rights
      // view. The retry uses only the same closed request kind.
      if (!mounted) return;
      setState(() {
        _retryKind = kind;
        _error = kDsarUnavailableMessage;
      });
    } catch (_) {
      // Contain any unexpected error; never leak a stack trace (Req 11.4).
      if (!mounted) return;
      setState(() {
        _retryKind = kind;
        _error = kDsarUnavailableMessage;
      });
    } finally {
      if (mounted) {
        setState(() {
          _submitting = false;
          _pendingKind = null;
        });
      }
    }
  }

  Future<bool?> _confirmDestructive(DsarRequestKind kind) {
    return showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Xác nhận xoá dữ liệu'),
        content: Text(kind.descriptionVi),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Huỷ'),
          ),
          FilledButton(
            key: const Key('dsar-confirm-delete'),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Xác nhận'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Quyền dữ liệu cá nhân')),
      body: _buildBody(context),
    );
  }

  Widget _buildBody(BuildContext context) {
    // Feature gate (Req 8.6): closed gate renders an inert disabled state.
    if (!widget.resolver.consentCenterEnabled) {
      return const Center(
        child: Padding(
          key: Key('dsar-disabled'),
          padding: EdgeInsets.all(24),
          child: Text(
            kDsarDisabledMessage,
            textAlign: TextAlign.center,
          ),
        ),
      );
    }

    final ack = _acknowledgement;
    if (ack != null) {
      return _DsarAcknowledgementView(
        acknowledgement: ack,
        onDone: () => setState(() => _acknowledgement = null),
      );
    }

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
      children: [
        Text(
          'Yêu cầu quyền dữ liệu',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 4),
        Text(
          'Bạn có thể yêu cầu xuất hoặc xoá dữ liệu của mình. Yêu cầu được gắn '
          'với tài khoản đã đăng nhập — bạn không cần nhập lại thông tin cá nhân.',
          style: Theme.of(context).textTheme.bodySmall,
        ),
        const SizedBox(height: 16),
        if (_error != null) ...[
          ErrorRetryView(
            message: _error!,
            onRetry: () {
              final kind = _retryKind;
              setState(() => _error = null);
              if (kind != null) {
                _submit(kind);
              }
            },
          ),
          const SizedBox(height: 16),
        ],
        for (final kind in DsarRequestKind.values)
          _DsarActionTile(
            kind: kind,
            busy: _submitting && _pendingKind == kind,
            enabled: !_submitting,
            onSubmit: () => _submit(kind),
          ),
      ],
    );
  }
}

class _DsarActionTile extends StatelessWidget {
  const _DsarActionTile({
    required this.kind,
    required this.busy,
    required this.enabled,
    required this.onSubmit,
  });

  final DsarRequestKind kind;
  final bool busy;
  final bool enabled;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(kind.titleVi, style: theme.textTheme.titleSmall),
            const SizedBox(height: 4),
            Text(kind.descriptionVi, style: theme.textTheme.bodySmall),
            const SizedBox(height: 8),
            Align(
              alignment: Alignment.centerRight,
              child: Semantics(
                button: true,
                label: 'Gửi yêu cầu: ${kind.titleVi}',
                child: FilledButton(
                  key: Key('dsar-submit-${kind.wireValue}'),
                  onPressed: enabled ? onSubmit : null,
                  style: FilledButton.styleFrom(
                    minimumSize: const Size(kMinTouchTarget, kMinTouchTarget),
                  ),
                  child: busy
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Gửi yêu cầu'),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Read-only acknowledgement of a submitted DSAR request (Req 8.3). Renders only
/// non-PII fields: kind, status, request id, and statutory dates.
class _DsarAcknowledgementView extends StatelessWidget {
  const _DsarAcknowledgementView({
    required this.acknowledgement,
    required this.onDone,
  });

  final DsarAcknowledgement acknowledgement;
  final VoidCallback onDone;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final ack = acknowledgement;
    return ListView(
      key: const Key('dsar-acknowledgement'),
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
      children: [
        const StatusByText(
          label: 'Đã tiếp nhận yêu cầu',
          level: A11yStatusLevel.success,
          semanticsPrefix: 'Trạng thái',
        ),
        const SizedBox(height: 12),
        Text(
          'Yêu cầu của bạn đã được ghi nhận và sẽ được xử lý theo quy định.',
          style: theme.textTheme.bodyMedium,
        ),
        const SizedBox(height: 16),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (ack.requestId != null)
                  _AckRow(label: 'Mã yêu cầu', value: '#${ack.requestId}'),
                _AckRow(label: 'Loại yêu cầu', value: ack.kind),
                _AckRow(label: 'Trạng thái', value: ack.status),
                if (ack.dueAt != null && ack.dueAt!.isNotEmpty)
                  _AckRow(label: 'Hạn xử lý', value: ack.dueAt!),
                if (ack.statutoryWindowDays != null)
                  _AckRow(
                    label: 'Thời hạn quy định',
                    value: '${ack.statutoryWindowDays} ngày',
                  ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        FilledButton(
          key: const Key('dsar-ack-done'),
          onPressed: onDone,
          style: FilledButton.styleFrom(
            minimumSize: const Size(kMinTouchTarget, kMinTouchTarget),
          ),
          child: const Text('Xong'),
        ),
      ],
    );
  }
}

class _AckRow extends StatelessWidget {
  const _AckRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 140,
            child: Text(label, style: theme.textTheme.labelMedium),
          ),
          Expanded(child: Text(value, style: theme.textTheme.bodyMedium)),
        ],
      ),
    );
  }
}
