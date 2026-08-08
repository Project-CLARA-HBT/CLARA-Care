import 'package:flutter/material.dart';

import '../core/a11y.dart';
import '../core/analytics.dart';
import '../core/api_client.dart';
import '../core/feature_flags.dart';
import '../core/session_store.dart';

// =============================================================================
// Granular consent centre — server-authoritative mobile parity.
//
// The compliance ledger is an API-owned, append-only record. This screen must
// never replace it with device-local switches: a local value would imply a
// permission changed even when API policy still sees the old value. Analytics
// remains disabled by default and is deliberately not represented as a server
// compliance purpose until it has its own governed backend contract.
// =============================================================================

enum _CompliancePurpose {
  coreService,
  aiTransparency,
  personalization,
  research,
  crossBorderProcessing,
  sharing,
}

extension on _CompliancePurpose {
  String get wireName {
    switch (this) {
      case _CompliancePurpose.coreService:
        return 'core_service';
      case _CompliancePurpose.aiTransparency:
        return 'ai_transparency';
      case _CompliancePurpose.personalization:
        return 'personalization';
      case _CompliancePurpose.research:
        return 'research';
      case _CompliancePurpose.crossBorderProcessing:
        return 'cross_border_processing';
      case _CompliancePurpose.sharing:
        return 'sharing';
    }
  }

  bool get isLocked => this == _CompliancePurpose.coreService;

  String title(bool english) {
    switch (this) {
      case _CompliancePurpose.coreService:
        return english ? 'Core service' : 'Dịch vụ cốt lõi';
      case _CompliancePurpose.aiTransparency:
        return english ? 'AI transparency' : 'Minh bạch AI';
      case _CompliancePurpose.personalization:
        return english ? 'Personalization' : 'Cá nhân hóa';
      case _CompliancePurpose.research:
        return english ? 'Research use' : 'Nghiên cứu';
      case _CompliancePurpose.crossBorderProcessing:
        return english
            ? 'Third-party / cross-border model processing'
            : 'Xử lý bởi mô hình bên thứ ba / xuyên biên giới';
      case _CompliancePurpose.sharing:
        return english ? 'Sharing' : 'Chia sẻ';
    }
  }

  String description(bool english) {
    switch (this) {
      case _CompliancePurpose.coreService:
        return english
            ? 'Required to provide CLARA core functionality while you use the service.'
            : 'Cần thiết để cung cấp chức năng cốt lõi của CLARA trong khi bạn sử dụng dịch vụ.';
      case _CompliancePurpose.aiTransparency:
        return english
            ? 'Acknowledgement of the current AI-system transparency notice.'
            : 'Xác nhận thông báo minh bạch hiện hành về hệ thống AI.';
      case _CompliancePurpose.personalization:
        return english
            ? 'Use your health record, medicine cabinet, and allergies to personalize support.'
            : 'Dùng hồ sơ sức khỏe, tủ thuốc và dị ứng để cá nhân hóa hỗ trợ.';
      case _CompliancePurpose.research:
        return english
            ? 'Allow de-identified data to improve retrieval and evidence verification.'
            : 'Cho phép dùng dữ liệu đã khử định danh để cải thiện truy xuất và kiểm chứng bằng chứng.';
      case _CompliancePurpose.crossBorderProcessing:
        return english
            ? 'Allow necessary data to be processed by a language model outside Vietnam.'
            : 'Cho phép dữ liệu cần thiết được xử lý bởi mô hình ngôn ngữ ngoài Việt Nam.';
      case _CompliancePurpose.sharing:
        return english
            ? 'Allow read-only sharing links for your records and conversations.'
            : 'Cho phép liên kết chia sẻ chỉ đọc cho hồ sơ và cuộc trò chuyện của bạn.';
    }
  }
}

/// Server-authoritative granular-consent centre.
///
/// The feature flag controls only whether this entry is visible. If the flag,
/// session, or ledger request is unavailable, no consent control is shown.
class ConsentCenterScreen extends StatefulWidget {
  const ConsentCenterScreen({
    super.key,
    required this.apiClient,
    required this.resolver,
    required this.sessionStore,
  });

  final ApiClient apiClient;
  final MobileFeatureFlagResolver resolver;
  final SessionStore sessionStore;

  @override
  State<ConsentCenterScreen> createState() => _ConsentCenterScreenState();
}

class _ConsentCenterScreenState extends State<ConsentCenterScreen> {
  Map<String, bool> _grants = const <String, bool>{};
  String? _policyVersion;
  _CompliancePurpose? _savingPurpose;
  bool _loading = true;
  bool _available = false;
  String? _error;

  bool get _english => Localizations.localeOf(context).languageCode == 'en';

  String _copy(String vi, String en) => _english ? en : vi;

  @override
  void initState() {
    super.initState();
    if (widget.resolver.consentCenterEnabled) {
      getAnalyticsClient().captureScreenView('mobile_consent_center_viewed');
      _load();
    } else {
      _loading = false;
    }
  }

  Future<void> _load() async {
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _available = false;
        _error = _copy(
          'Không thể kiểm tra trạng thái đồng ý. Vui lòng đăng nhập lại.',
          'We could not check consent status. Please sign in again.',
        );
      });
      return;
    }

    if (mounted) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      final payload = await widget.apiClient.getComplianceConsents(
        accessToken: token,
      );
      final rawGrants = payload['consents'];
      final grants = <String, bool>{
        for (final purpose in _CompliancePurpose.values)
          purpose.wireName:
              rawGrants is Map && rawGrants[purpose.wireName] == true,
      };
      if (!mounted) return;
      setState(() {
        _grants = grants;
        _policyVersion = payload['policy_version'] is String
            ? payload['policy_version'] as String
            : null;
        _available = payload['enabled'] == true;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _available = false;
        _error = _copy(
          'Không thể tải trạng thái đồng ý lúc này. Vui lòng thử lại.',
          'We could not load consent status. Please try again.',
        );
      });
    }
  }

  Future<void> _toggle(_CompliancePurpose purpose, bool nextGranted) async {
    if (purpose.isLocked) return;
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) {
      setState(() {
        _error = _copy(
          'Không thể thay đổi đồng ý. Vui lòng đăng nhập lại.',
          'We could not change consent. Please sign in again.',
        );
      });
      return;
    }

    setState(() {
      _savingPurpose = purpose;
      _error = null;
    });
    try {
      if (nextGranted) {
        await widget.apiClient.grantComplianceConsent(
          accessToken: token,
          purpose: purpose.wireName,
          policyVersion: _policyVersion,
        );
      } else {
        await widget.apiClient.withdrawComplianceConsent(
          accessToken: token,
          purpose: purpose.wireName,
        );
      }
      await _load();
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = _copy(
          'Không thể cập nhật đồng ý. Trạng thái hiện tại chưa thay đổi.',
          'We could not update consent. The current state has not changed.',
        );
      });
    } finally {
      if (mounted) setState(() => _savingPurpose = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_copy('Quyền riêng tư & đồng ý', 'Privacy & consent')),
      ),
      body: _buildBody(context),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (!widget.resolver.consentCenterEnabled || (!_available && !_loading)) {
      return _UnavailableNotice(
        message: _error ??
            _copy(
              'Tính năng này hiện chưa được bật cho môi trường này.',
              'This feature is not enabled for this environment.',
            ),
        onRetry: widget.resolver.consentCenterEnabled ? _load : null,
      );
    }
    if (_loading) return const Center(child: CircularProgressIndicator());

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
      children: <Widget>[
        if (_error != null) ...<Widget>[
          Semantics(
            liveRegion: true,
            child: Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ),
          const SizedBox(height: 12),
        ],
        Text(
          _copy(
              'Quản lý đồng ý theo từng mục đích', 'Manage consent by purpose'),
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 4),
        Text(
          _copy(
            'Bạn có thể bật hoặc rút lại từng mục đích không bắt buộc bất cứ lúc nào.',
            'You can grant or withdraw each optional purpose at any time.',
          ),
          style: Theme.of(context).textTheme.bodySmall,
        ),
        const SizedBox(height: 16),
        for (final purpose in _CompliancePurpose.values)
          _buildPurposeTile(purpose),
      ],
    );
  }

  Widget _buildPurposeTile(_CompliancePurpose purpose) {
    final granted = purpose.isLocked || _grants[purpose.wireName] == true;
    final busy = _savingPurpose == purpose;
    final stateLabel =
        granted ? _copy('Đã bật', 'Enabled') : _copy('Đã tắt', 'Disabled');
    return Card(
      child: A11yLabeled(
        label: '${purpose.title(_english)}. $stateLabel',
        child: SwitchListTile(
          value: granted,
          onChanged: purpose.isLocked || busy
              ? null
              : (value) => _toggle(purpose, value),
          title: Row(
            children: <Widget>[
              Expanded(child: Text(purpose.title(_english))),
              if (purpose.isLocked)
                Padding(
                  padding: const EdgeInsets.only(left: 8),
                  child: Text(
                    _copy('Bắt buộc', 'Required'),
                    style: Theme.of(context).textTheme.labelSmall,
                  ),
                ),
            ],
          ),
          subtitle: Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(purpose.description(_english)),
          ),
          isThreeLine: true,
        ),
      ),
    );
  }
}

class _UnavailableNotice extends StatelessWidget {
  const _UnavailableNotice({required this.message, this.onRetry});

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final english = Localizations.localeOf(context).languageCode == 'en';
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Text(message, textAlign: TextAlign.center),
            if (onRetry != null) ...<Widget>[
              const SizedBox(height: 12),
              OutlinedButton(
                onPressed: onRetry,
                child: Text(english ? 'Try again' : 'Thử lại'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
