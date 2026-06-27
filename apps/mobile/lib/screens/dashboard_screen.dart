import 'package:flutter/material.dart';

import '../core/analytics.dart';
import '../core/api_client.dart';
import '../core/session_store.dart';
import 'careguard_screen.dart';
import 'careguard_cabinet_screen.dart';
import 'council_screen.dart';
import 'council_case_screen.dart';
import 'phr_screen.dart';
import 'research_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({
    super.key,
    required this.apiClient,
    required this.sessionStore,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  bool _loadingSummary = false;
  String? _summaryError;
  Map<String, dynamic>? _summary;

  bool _loadingMetrics = false;
  String? _metricsError;
  Map<String, dynamic>? _metrics;

  @override
  void initState() {
    super.initState();
    getAnalyticsClient()
        .captureScreenView(MobileAnalyticsEvents.dashboardViewed);
    _loadSummary();
  }

  /// Whether the role-scoped `mobile/summary` was successfully loaded.
  ///
  /// All privileged tiles and the admin-only system-monitor surface are gated
  /// on this so the dashboard fails CLOSED (Requirement 13.4): a null summary
  /// (load failed, in-flight, or no session) ⇒ no privileged tools are derived.
  bool get _summaryLoaded => _summary != null;

  /// The authenticated role, defaulting to the least-privileged `normal`.
  String get _role => widget.sessionStore.role ?? 'normal';

  /// Defense-in-depth role check for admin-only surfaces (Requirement 13.5).
  bool get _isAdmin => _role == 'admin';

  /// Whether the admin-only system-monitor surface may be shown. Requires a
  /// loaded summary, the admin role, AND the role-scoped `system_monitor`
  /// flag. Combining the role check with the server flag guarantees the
  /// surface is NEVER exposed to a non-admin role even if the flag were
  /// mis-scoped server-side (Requirement 13.5).
  bool get _canSystemMonitor =>
      _summaryLoaded && _isAdmin && _featureEnabled('system_monitor');

  bool _featureEnabled(String key) {
    final summary = _summary;
    if (summary == null) {
      // Fail closed: an unloadable summary grants no capability.
      return false;
    }

    final flags = summary['feature_flags'];
    if (flags is! Map<String, dynamic>) {
      return false;
    }
    return flags[key] == true;
  }

  Future<void> _loadSummary() async {
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) {
      return;
    }

    setState(() {
      _loadingSummary = true;
      _summaryError = null;
    });

    try {
      final data = await widget.apiClient.getMobileSummary(accessToken: token);
      if (!mounted) {
        return;
      }

      setState(() {
        _summary = data;
      });

      if (_canSystemMonitor) {
        await _loadMetrics();
      } else if (mounted) {
        setState(() {
          _metrics = null;
          _metricsError = null;
        });
      }
    } on ApiException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _summaryError = error.message;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _summaryError = 'Không thể tải dữ liệu trang chính. Vui lòng thử lại.';
      });
    } finally {
      if (mounted) {
        setState(() {
          _loadingSummary = false;
        });
      }
    }
  }

  Future<void> _loadMetrics() async {
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) {
      return;
    }

    setState(() {
      _loadingMetrics = true;
      _metricsError = null;
    });

    try {
      final data = await widget.apiClient.getSystemMetrics(accessToken: token);
      if (!mounted) {
        return;
      }
      setState(() {
        _metrics = data;
      });
    } on ApiException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _metricsError = error.message;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _metricsError = 'Không thể tải chỉ số hệ thống. Vui lòng thử lại.';
      });
    } finally {
      if (mounted) {
        setState(() {
          _loadingMetrics = false;
        });
      }
    }
  }

  Future<void> _openScreen(Widget screen) {
    return Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => screen),
    );
  }

  /// Signs the user out by clearing all persisted credentials from the
  /// Session_Store (Requirement 10.5). Clearing notifies listeners, so the
  /// app shell routes back to the login screen.
  Future<void> _signOut() async {
    await widget.sessionStore.clear();
  }

  int? _metricInt(String key) {
    final value = _metrics?[key];
    if (value is int) return value;
    if (value is num) return value.round();
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final role = _role;
    final summaryLoaded = _summaryLoaded;
    // Privileged tiles are derived ONLY from a successfully loaded, role-scoped
    // summary (Requirement 13.1). When the summary is unavailable we fail
    // closed and render none of them (Requirement 13.4).
    final canResearch = _featureEnabled('research');
    final canCareguard = _featureEnabled('careguard');
    final canCouncil = _featureEnabled('council');
    final canSystemMonitor = _canSystemMonitor;
    // Show the fail-closed retry affordance once a load attempt has settled
    // without yielding a summary (Requirement 13.4).
    final showSummaryRetry = !summaryLoaded && !_loadingSummary;

    return Scaffold(
      appBar: AppBar(
        title: const Text('CLARA'),
        actions: [
          IconButton(
            onPressed: _signOut,
            icon: const Icon(Icons.logout),
            tooltip: 'Đăng xuất',
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _loadSummary,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      widget.sessionStore.email ?? '-',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 4),
                    Text('Vai trò: $role'),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text('Công cụ', style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 8),
            // Privileged / feature-gated tiles. These are rendered only when the
            // role-scoped summary loaded; otherwise we fail closed and show the
            // retry affordance below instead (Requirement 13.4).
            if (summaryLoaded) ...[
              _FeatureTile(
                icon: Icons.science,
                title: 'Nghiên cứu y khoa',
                subtitle: 'Tìm hiểu sâu với dẫn chứng',
                enabled: canResearch,
                onTap: () => _openScreen(
                  ResearchScreen(
                    apiClient: widget.apiClient,
                    sessionStore: widget.sessionStore,
                    deepResearchEnabled:
                        _featureEnabled('research_mobile_deep'),
                  ),
                ),
              ),
              _FeatureTile(
                icon: Icons.medication,
                title: 'Kiểm tra tương tác thuốc',
                subtitle: 'Phân tích an toàn cho tủ thuốc',
                enabled: canCareguard,
                onTap: () => _openScreen(
                  CareguardScreen(
                    apiClient: widget.apiClient,
                    sessionStore: widget.sessionStore,
                  ),
                ),
              ),
              // Cabinet CRUD parity (clara-selfmed-careguard-upgrade Req 8.2,
              // 8.3). Exposed only when CAREGUARD_MOBILE_CABINET_ENABLED is on
              // AND the role has CareGuard access; default OFF keeps today's
              // behavior.
              if (kCareguardMobileCabinetEnabled)
                _FeatureTile(
                  icon: Icons.medical_services_outlined,
                  title: 'Tủ thuốc',
                  subtitle: 'Quản lý danh sách thuốc của bạn',
                  enabled: canCareguard,
                  onTap: () => _openScreen(
                    CareguardCabinetScreen(
                      apiClient: widget.apiClient,
                      sessionStore: widget.sessionStore,
                    ),
                  ),
                ),
              _FeatureTile(
                icon: Icons.groups,
                title: 'Hội chẩn AI',
                subtitle: 'Tổng hợp ý kiến nhiều chuyên khoa',
                enabled: canCouncil,
                onTap: () => _openScreen(
                  // Council mobile parity (clara-council-upgrade Req 8.5): when
                  // COUNCIL_MOBILE_PARITY_ENABLED is on AND the `council`
                  // feature flag is enabled, route to the case-based parity
                  // flow. With the build flag off, fall back to today's
                  // direct-run screen so existing behavior is preserved
                  // byte-for-byte.
                  kCouncilMobileParityEnabled
                      ? CouncilCaseScreen(
                          apiClient: widget.apiClient,
                          sessionStore: widget.sessionStore,
                        )
                      : CouncilScreen(
                          apiClient: widget.apiClient,
                          sessionStore: widget.sessionStore,
                        ),
                ),
              ),
            ],
            // PHR is available to every authenticated role (RBAC normal/
            // researcher/doctor/admin — Requirement 13.3), independent of the
            // summary, so the tile is always enabled (personal-health-record
            // Requirement 17.1).
            _FeatureTile(
              icon: Icons.folder_shared,
              title: 'Hồ sơ sức khỏe',
              subtitle: 'Xem và cập nhật hồ sơ tự khai',
              enabled: true,
              onTap: () => _openScreen(
                PhrScreen(
                  apiClient: widget.apiClient,
                  sessionStore: widget.sessionStore,
                ),
              ),
            ),
            // Fail-closed retry: when the role-scoped summary could not be
            // loaded, no privileged tiles are shown and the user is offered a
            // retry (Requirement 13.4).
            if (showSummaryRetry) ...[
              const SizedBox(height: 8),
              _SummaryUnavailableView(
                message: _summaryError ??
                    'Không thể tải danh sách công cụ. Vui lòng thử lại.',
                onRetry: _loadSummary,
              ),
            ],
            const SizedBox(height: 16),
            if (_loadingSummary) const LinearProgressIndicator(),
            // Admin-only system-monitor surface (Requirement 13.5). The entire
            // section — header, refresh control, and metrics — is hidden for
            // any non-admin role and whenever the summary is unavailable, so
            // its very existence is never disclosed to unauthorized roles.
            if (canSystemMonitor) ...[
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: Text(
                      'Chỉ số hệ thống',
                      style: Theme.of(context).textTheme.titleSmall,
                    ),
                  ),
                  OutlinedButton(
                    onPressed: _loadingSummary || _loadingMetrics
                        ? null
                        : _loadSummary,
                    child: const Text('Làm mới'),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              if (_loadingMetrics)
                const Center(child: CircularProgressIndicator())
              else if (_metricsError != null)
                Text(
                  _metricsError!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                )
              else if (_metrics != null)
                _MetricsView(
                  requestsTotal: _metricInt('requests_total'),
                  avgLatencyMs: _metrics!['avg_latency_ms'],
                )
              else
                const Text('Chưa có chỉ số nào được tải.'),
            ],
          ],
        ),
      ),
    );
  }
}

class _FeatureTile extends StatelessWidget {
  const _FeatureTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.enabled,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final bool enabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        leading: Icon(icon),
        title: Text(title),
        subtitle: Text(enabled ? subtitle : 'Không khả dụng với vai trò này'),
        trailing: const Icon(Icons.chevron_right),
        enabled: enabled,
        onTap: enabled ? onTap : null,
      ),
    );
  }
}

/// Fail-closed placeholder shown when the role-scoped `mobile/summary` could
/// not be loaded. It surfaces a non-PII message and a retry control, and is
/// rendered IN PLACE OF the privileged tiles so no gated tool leaks while the
/// summary is unavailable (Requirement 13.4).
class _SummaryUnavailableView extends StatelessWidget {
  const _SummaryUnavailableView({
    required this.message,
    required this.onRetry,
  });

  final String message;
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.cloud_off,
                  color: Theme.of(context).colorScheme.error,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    message,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Align(
              alignment: Alignment.centerLeft,
              child: FilledButton.icon(
                onPressed: () => onRetry(),
                icon: const Icon(Icons.refresh),
                label: const Text('Thử lại'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MetricsView extends StatelessWidget {
  const _MetricsView({this.requestsTotal, this.avgLatencyMs});

  final int? requestsTotal;
  final dynamic avgLatencyMs;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (requestsTotal != null)
              Text('Tổng số request: $requestsTotal'),
            if (avgLatencyMs != null)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text('Độ trễ trung bình: $avgLatencyMs ms'),
              ),
            if (requestsTotal == null && avgLatencyMs == null)
              const Text('Đã tải chỉ số hệ thống.'),
          ],
        ),
      ),
    );
  }
}
