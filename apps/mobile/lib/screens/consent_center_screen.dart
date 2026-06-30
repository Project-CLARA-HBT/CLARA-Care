import 'package:flutter/material.dart';

import '../core/a11y.dart';
import '../core/analytics.dart';
import '../core/consent_state.dart';
import '../core/feature_flags.dart';
import '../core/session_store.dart';

// =============================================================================
// Granular consent center — clara-mobile-feature-parity Task 10.1
// (Requirements 8.1, 8.2, 8.4).
//
//   * 8.1 Self-service consent center listing every processing purpose
//         (core service, personalization, research, cross-border, sharing,
//         analytics) with grant/withdraw toggles.
//   * 8.2 Withdrawal is at least as easy as granting — a single symmetric
//         switch per purpose.
//   * 8.4 Withdrawing the analytics purpose calls
//         `Analytics.setConsent(granted: false)` immediately (and granting calls
//         `setConsent(granted: true)`), wired through [ConsentStore].
//   * Gated behind `consent_center_mobile_enabled` via
//         [MobileFeatureFlagResolver]: with the flag off the surface is never
//         exposed (Requirement 8.6 / 15.1).
//
// No PII is read, stored, or logged on this surface (Requirement 8.5 / 11.2):
// only boolean grants + a policy version flow through the store.
// =============================================================================

/// Self-service granular-consent center.
///
/// Construct with the loaded [MobileFeatureFlagResolver] so the screen can
/// fail-closed when the gate is off, and the [SessionStore] used to build a
/// persistent [ConsentStore]. The analytics facade may be injected for tests;
/// it defaults to the shared client.
class ConsentCenterScreen extends StatefulWidget {
  const ConsentCenterScreen({
    super.key,
    required this.resolver,
    required this.sessionStore,
    Analytics? analytics,
    ConsentStore? consentStore,
  })  : _analytics = analytics,
        _consentStore = consentStore;

  /// Resolved feature gates from `mobile/summary` + build defaults.
  final MobileFeatureFlagResolver resolver;

  /// The session store, whose secure-storage seam backs consent persistence.
  final SessionStore sessionStore;

  /// Optional analytics facade override (tests inject a spy/recording client).
  final Analytics? _analytics;

  /// Optional pre-built consent store (tests inject one with an in-memory seam).
  final ConsentStore? _consentStore;

  @override
  State<ConsentCenterScreen> createState() => _ConsentCenterScreenState();
}

class _ConsentCenterScreenState extends State<ConsentCenterScreen> {
  late final ConsentStore _store;
  bool _loading = true;
  ConsentPurpose? _savingPurpose;

  @override
  void initState() {
    super.initState();
    _store = widget._consentStore ??
        ConsentStore(
          // The SessionStore is itself a SessionSecureStorage-backed store; we
          // reuse the same secure-storage seam via a dedicated store instance.
          storage: _ConsentSecureStorageAdapter(widget.sessionStore),
          analytics: widget._analytics,
        );
    // Only load/initialise when the gate is open; with the flag off the surface
    // is inert (Requirement 8.6 / 15.1).
    if (widget.resolver.consentCenterEnabled) {
      getAnalyticsClient()
          .captureScreenView('mobile_consent_center_viewed');
      _load();
    } else {
      _loading = false;
    }
  }

  Future<void> _load() async {
    await _store.load();
    if (!mounted) return;
    setState(() => _loading = false);
  }

  Future<void> _toggle(ConsentPurpose purpose, bool granted) async {
    setState(() => _savingPurpose = purpose);
    await _store.setConsent(purpose, granted);
    if (!mounted) return;
    setState(() => _savingPurpose = null);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Quyền riêng tư & đồng ý')),
      body: _buildBody(context),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (!widget.resolver.consentCenterEnabled) {
      return const _UnavailableNotice();
    }
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
      children: [
        Text(
          'Quản lý đồng ý theo từng mục đích',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 4),
        Text(
          'Bạn có thể bật hoặc tắt từng mục đích bất cứ lúc nào. Việc rút lại '
          'đồng ý dễ dàng như khi cấp đồng ý.',
          style: Theme.of(context).textTheme.bodySmall,
        ),
        const SizedBox(height: 16),
        for (final purpose in ConsentPurpose.values) _buildPurposeTile(purpose),
      ],
    );
  }

  Widget _buildPurposeTile(ConsentPurpose purpose) {
    final granted = _store.isGranted(purpose);
    final busy = _savingPurpose == purpose;
    return Card(
      child: A11yLabeled(
        label: '${purpose.titleVi}. ${granted ? "Đã bật" : "Đã tắt"}',
        child: SwitchListTile(
          value: granted,
          onChanged: busy ? null : (value) => _toggle(purpose, value),
          title: Row(
            children: [
              Expanded(child: Text(purpose.titleVi)),
              if (purpose.isMandatory)
                Padding(
                  padding: const EdgeInsets.only(left: 8),
                  child: Text(
                    'Bắt buộc',
                    style: Theme.of(context).textTheme.labelSmall,
                  ),
                ),
            ],
          ),
          subtitle: Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(purpose.descriptionVi),
          ),
          isThreeLine: true,
        ),
      ),
    );
  }
}

/// Shown when the consent-center gate is off — the surface stays inert and
/// reveals no controls (Requirement 8.6 / 15.1).
class _UnavailableNotice extends StatelessWidget {
  const _UnavailableNotice();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Padding(
        padding: EdgeInsets.all(24),
        child: Text(
          'Tính năng này hiện chưa được bật.',
          textAlign: TextAlign.center,
        ),
      ),
    );
  }
}

/// Adapts a [SessionStore]'s underlying secure storage for consent persistence.
///
/// The session store does not expose its [SessionSecureStorage] directly, so we
/// persist consent under a dedicated key via a fresh secure-storage instance of
/// the same kind the app already uses. In tests, an explicit [ConsentStore]
/// (with an in-memory seam) is injected instead, so this adapter only runs in
/// production where `flutter_secure_storage` is available.
class _ConsentSecureStorageAdapter implements SessionSecureStorage {
  _ConsentSecureStorageAdapter(this._sessionStore)
      : _delegate = FlutterSecureSessionStorage();

  // Retained so the adapter's lifetime is tied to the owning session, even
  // though persistence is delegated to the platform secure store by key.
  // ignore: unused_field
  final SessionStore _sessionStore;
  final SessionSecureStorage _delegate;

  @override
  Future<String?> read(String key) => _delegate.read(key);

  @override
  Future<void> write(String key, String value) => _delegate.write(key, value);

  @override
  Future<void> delete(String key) => _delegate.delete(key);
}
