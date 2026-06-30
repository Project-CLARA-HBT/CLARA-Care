import 'package:flutter/material.dart';

import '../core/ai_transparency_notice.dart';

/// A gate that requires acknowledgement of the versioned [AiTransparencyNotice]
/// before revealing medical [child] content (Requirement 7.1, 7.2).
///
/// Behavior:
///   * **Flag off ([enabled] == false):** renders [child] directly and never
///     touches the store. This preserves today's behavior exactly when
///     `transparency_notice_mobile_enabled` resolves false (Requirement 15.2).
///   * **Flag on, current version unacknowledged:** renders the notice with an
///     acknowledge action. Tapping it persists the current
///     [AiTransparencyNotice.version] via [AiTransparencyNoticeStore] and then
///     reveals [child].
///   * **Flag on, current version already acknowledged:** renders [child].
///   * **Versioned re-prompt:** if a newer notice version is published, the
///     persisted version no longer matches and the notice is shown again.
///
/// The widget contains its own async/error handling so a storage failure never
/// crashes the host screen (Requirement 11.4): a read failure is treated as
/// "not acknowledged" (fail-closed — the notice is shown), and a write failure
/// surfaces an inline, PII-free retry message.
class AiTransparencyNoticeGate extends StatefulWidget {
  const AiTransparencyNoticeGate({
    super.key,
    required this.enabled,
    required this.store,
    required this.child,
    this.notice = kCurrentAiTransparencyNotice,
    this.onAcknowledged,
  });

  /// Resolved value of `transparency_notice_mobile_enabled`. When false the
  /// gate is inert and [child] renders unchanged.
  final bool enabled;

  /// Persistence seam for the acknowledged version.
  final AiTransparencyNoticeStore store;

  /// The medical content gated behind acknowledgement.
  final Widget child;

  /// The notice to present. Defaults to [kCurrentAiTransparencyNotice].
  final AiTransparencyNotice notice;

  /// Optional callback invoked once acknowledgement is recorded.
  final VoidCallback? onAcknowledged;

  @override
  State<AiTransparencyNoticeGate> createState() =>
      _AiTransparencyNoticeGateState();
}

class _AiTransparencyNoticeGateState extends State<AiTransparencyNoticeGate> {
  bool _loading = true;
  bool _needsAck = false;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    if (widget.enabled) {
      _evaluate();
    } else {
      // Flag off: nothing to evaluate; child renders directly in build().
      _loading = false;
    }
  }

  Future<void> _evaluate() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    String? acknowledged;
    try {
      acknowledged = await widget.store.acknowledgedVersion();
    } catch (_) {
      // Treat an unreadable store as "not acknowledged" so we fail closed and
      // show the notice rather than skipping it.
      acknowledged = null;
    }
    if (!mounted) return;
    setState(() {
      _needsAck = AiTransparencyNoticeStore.needsAcknowledgement(
        currentVersion: widget.notice.version,
        acknowledgedVersion: acknowledged,
      );
      _loading = false;
    });
  }

  Future<void> _acknowledge() async {
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.store.acknowledge(widget.notice.version);
      if (!mounted) return;
      setState(() {
        _needsAck = false;
        _saving = false;
      });
      widget.onAcknowledged?.call();
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = 'Không thể lưu xác nhận. Vui lòng thử lại.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    // Flag off -> behavior unchanged.
    if (!widget.enabled) {
      return widget.child;
    }
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (!_needsAck) {
      return widget.child;
    }
    return _AiTransparencyNoticeView(
      notice: widget.notice,
      saving: _saving,
      error: _error,
      onAcknowledge: _acknowledge,
    );
  }
}

/// Presentational notice card. Status is conveyed by text (not color alone) and
/// the action exposes a semantics label (Requirement 10.1, 10.5).
class _AiTransparencyNoticeView extends StatelessWidget {
  const _AiTransparencyNoticeView({
    required this.notice,
    required this.saving,
    required this.error,
    required this.onAcknowledge,
  });

  final AiTransparencyNotice notice;
  final bool saving;
  final String? error;
  final VoidCallback onAcknowledge;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.info_outline),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        notice.title,
                        style: theme.textTheme.titleMedium,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                for (final paragraph in notice.body)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Text(paragraph, style: theme.textTheme.bodyMedium),
                  ),
                Text(
                  'Phiên bản thông báo: ${notice.version}',
                  style: theme.textTheme.bodySmall,
                ),
                const SizedBox(height: 16),
                Semantics(
                  button: true,
                  label: notice.acknowledgeLabel,
                  child: SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      // ≥48dp target (Requirement 10.2).
                      style: FilledButton.styleFrom(
                        minimumSize: const Size.fromHeight(48),
                      ),
                      onPressed: saving ? null : onAcknowledge,
                      child: saving
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : Text(notice.acknowledgeLabel),
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
      ],
    );
  }
}
