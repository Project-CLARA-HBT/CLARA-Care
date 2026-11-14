import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/consumer_terminology.dart';
import '../../core/session_store.dart';
import '../../theme/components/section_header.dart';
import '../../theme/tokens.dart';
import '../fhir/fhir_sync_dashboard_screen.dart';
import '../language_controller.dart';

/// Supported external health/wearable provider catalog.
class SupportedProviderInfo {
  const SupportedProviderInfo({
    required this.id,
    required this.name,
    required this.title,
    required this.descriptionVi,
    required this.descriptionEn,
    required this.icon,
    required this.isDeviceAdapter,
    this.defaultTypes = const ['steps', 'heart_rate', 'sleep'],
  });

  final String id;
  final String name;
  final String title;
  final String descriptionVi;
  final String descriptionEn;
  final IconData icon;
  final bool isDeviceAdapter;
  final List<String> defaultTypes;
}

const List<SupportedProviderInfo> kSupportedProviders = [
  SupportedProviderInfo(
    id: 'health_connect',
    name: 'health_connect',
    title: 'Health Connect',
    descriptionVi:
        'Cổng chuẩn Google Health Connect cho Android (bước chân, nhịp tim, giấc ngủ).',
    descriptionEn:
        'Android Health Connect platform bridge for steps, vitals, and sleep.',
    icon: Icons.android_outlined,
    isDeviceAdapter: true,
  ),
  SupportedProviderInfo(
    id: 'huawei_health',
    name: 'huawei_health',
    title: 'Huawei Health',
    descriptionVi:
        'Đồng bộ dữ liệu thiết bị đeo thông minh Huawei Health Kit trên điện thoại.',
    descriptionEn:
        'On-device health and vitals synchronization from Huawei Health Kit.',
    icon: Icons.watch_outlined,
    isDeviceAdapter: true,
  ),
  SupportedProviderInfo(
    id: 'fitbit',
    name: 'fitbit',
    title: 'Fitbit',
    descriptionVi:
        'Đồng bộ đám mây thiết bị Fitbit và tài khoản Google Fit qua API an toàn.',
    descriptionEn:
        'Cloud-to-cloud secure sync for Fitbit wearable trackers and scales.',
    icon: Icons.directions_walk_outlined,
    isDeviceAdapter: false,
  ),
  SupportedProviderInfo(
    id: 'garmin',
    name: 'garmin',
    title: 'Garmin Connect',
    descriptionVi:
        'Dữ liệu biến thiên nhịp tim HRV, thể lực và theo dõi Garmin Health API.',
    descriptionEn:
        'Continuous HRV, training load, and activity from Garmin Health API.',
    icon: Icons.speed_outlined,
    isDeviceAdapter: false,
  ),
];

/// Clear, ownership-first management for health sources already authorized on
/// the user's device or cloud integrations. Native permission discovery/import
/// lives behind the platform connector bridge; this screen never fabricates a connected device.
class ConnectedHealthScreen extends StatefulWidget {
  const ConnectedHealthScreen({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    this.languageController,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  /// Optional app-level language state. Direct embedding remains
  /// Vietnamese-first when it is not supplied.
  final LanguageController? languageController;

  @override
  State<ConnectedHealthScreen> createState() => _ConnectedHealthScreenState();
}

class _ConnectedHealthScreenState extends State<ConnectedHealthScreen> {
  bool _loading = true;
  String? _error;
  List<Map<String, dynamic>> _sources = const [];
  final Set<String> _syncingIds = <String>{};

  String? get _token => widget.sessionStore.accessToken;
  bool get _isEn => widget.languageController?.languageCode == 'en';
  ConsumerTerminology get _copy => ConsumerTerminology.forLocale(
        widget.languageController?.languageCode,
      );

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final token = _token;
    if (token == null || token.isEmpty) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final sources = await widget.apiClient.listConnectedHealthSources(
        accessToken: token,
      );
      if (!mounted) return;
      setState(() => _sources = sources);
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _changeState(Map<String, dynamic> source) async {
    final token = _token;
    if (token == null || token.isEmpty) return;
    final id = source['id']?.toString() ?? '';
    final isPaused = source['status'] == 'paused';
    try {
      if (isPaused) {
        await widget.apiClient.resumeConnectedHealthSource(
          accessToken: token,
          connectorId: id,
        );
      } else {
        await widget.apiClient.pauseConnectedHealthSource(
          accessToken: token,
          connectorId: id,
        );
      }
      await _load();
    } on ApiException catch (error) {
      if (mounted) _showMessage(error.message);
    }
  }

  Future<void> _triggerSync(Map<String, dynamic> source) async {
    final token = _token;
    if (token == null || token.isEmpty) return;
    final id = source['id']?.toString() ?? '';
    if (id.isEmpty) return;

    setState(() => _syncingIds.add(id));
    try {
      await widget.apiClient.syncConnector(
        accessToken: token,
        connectorId: id,
      );
      if (mounted) {
        final label = source['display_label']?.toString() ??
            source['provider']?.toString() ??
            '';
        _showMessage(
          _isEn
              ? 'Data sync triggered for $label'
              : 'Đã kích hoạt đồng bộ dữ liệu cho $label',
        );
      }
      await _load();
    } on ApiException catch (error) {
      if (mounted) _showMessage(error.message);
    } finally {
      if (mounted) {
        setState(() => _syncingIds.remove(id));
      }
    }
  }

  Future<void> _connectProvider(SupportedProviderInfo provider) async {
    final token = _token;
    if (token == null || token.isEmpty) return;

    try {
      await widget.apiClient.createDeviceConnector(
        accessToken: token,
        provider: provider.id,
        externalSubjectRef: '${provider.id}-mobile-ref',
        displayLabel: provider.title,
        purposes: const ['personal_health_assistance'],
        dataTypes: provider.defaultTypes,
      );
      if (mounted) {
        _showMessage(
          _isEn
              ? '${provider.title} connected successfully.'
              : 'Đã kết nối thành công với ${provider.title}.',
        );
      }
      await _load();
    } on ApiException catch (error) {
      if (mounted) _showMessage(error.message);
    }
  }

  Future<void> _disconnect(Map<String, dynamic> source) async {
    final token = _token;
    if (token == null || token.isEmpty) return;
    final id = source['id']?.toString() ?? '';
    final confirmed = await _confirm(
      title: _copy[ConsumerTerm.connectedHealthDisconnectConfirmTitle],
      body: _copy[ConsumerTerm.connectedHealthDisconnectConfirmDescription],
      confirmLabel: _copy[ConsumerTerm.connectedHealthDisconnectConfirmAction],
    );
    if (!confirmed) return;
    try {
      await widget.apiClient.disconnectConnectedHealthSource(
        accessToken: token,
        connectorId: id,
      );
      await _load();
    } on ApiException catch (error) {
      if (mounted) _showMessage(error.message);
    }
  }

  Future<void> _deleteImportedData(Map<String, dynamic> source) async {
    final token = _token;
    if (token == null || token.isEmpty) return;
    final id = source['id']?.toString() ?? '';
    final confirmed = await _confirm(
      title: _copy[ConsumerTerm.connectedHealthDeleteConfirmTitle],
      body: _copy[ConsumerTerm.connectedHealthDeleteConfirmDescription],
      confirmLabel: _copy[ConsumerTerm.connectedHealthDeleteConfirmAction],
      destructive: true,
    );
    if (!confirmed) return;
    try {
      await widget.apiClient.deleteConnectedHealthImportedData(
        accessToken: token,
        connectorId: id,
      );
      await _load();
      if (mounted) {
        _showMessage(_copy[ConsumerTerm.connectedHealthDeleteSuccess]);
      }
    } on ApiException catch (error) {
      if (mounted) _showMessage(error.message);
    }
  }

  Future<bool> _confirm({
    required String title,
    required String body,
    required String confirmLabel,
    bool destructive = false,
  }) async {
    return await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: Text(title),
            content: Text(body),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: Text(_copy[ConsumerTerm.connectedHealthCancel]),
              ),
              FilledButton(
                style: destructive
                    ? FilledButton.styleFrom(
                        backgroundColor: Theme.of(context).colorScheme.error,
                      )
                    : null,
                onPressed: () => Navigator.pop(context, true),
                child: Text(confirmLabel),
              ),
            ],
          ),
        ) ??
        false;
  }

  void _showMessage(String text) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
  }

  @override
  Widget build(BuildContext context) {
    final languageController = widget.languageController;
    if (languageController == null) {
      return _buildLocalized(context, _copy);
    }
    return AnimatedBuilder(
      animation: languageController,
      builder: (context, _) => _buildLocalized(context, _copy),
    );
  }

  Widget _buildLocalized(BuildContext context, ConsumerTerminology copy) {
    // Determine which supported providers are already connected
    final connectedProviders = _sources
        .map((s) => s['provider']?.toString().toLowerCase() ?? '')
        .where((p) => p.isNotEmpty)
        .toSet();

    final availableProviders = kSupportedProviders
        .where((p) => !connectedProviders.contains(p.id))
        .toList();

    return Scaffold(
      appBar: AppBar(
        title: Text(copy[ConsumerTerm.connectedHealthTitle]),
        actions: [
          IconButton(
            key: const Key('connected-health-fhir-sync-action'),
            icon: const Icon(Icons.sync_alt_outlined),
            tooltip: copy.locale == 'en'
                ? 'FHIR Interoperability & Sync'
                : 'Đồng bộ & Xuất chuẩn FHIR R4',
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (_) => FhirSyncDashboardScreen(
                    apiClient: widget.apiClient,
                    sessionStore: widget.sessionStore,
                    languageController: widget.languageController,
                  ),
                ),
              );
            },
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : ListView(
                padding: const EdgeInsets.all(ClaraTokens.spaceMd),
                children: [
                  Text(
                    copy[ConsumerTerm.connectedHealthIntroTitle],
                    style: const TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: ClaraTokens.spaceXs),
                  Text(
                    copy[ConsumerTerm.connectedHealthIntroDescription],
                  ),
                  const SizedBox(height: ClaraTokens.spaceLg),
                  if (_error != null)
                    _RetryCard(
                      copy: copy,
                      message: _error!,
                      onRetry: _load,
                    )
                  else if (_sources.isEmpty)
                    _EmptySources(copy: copy)
                  else ...[
                    SectionHeader(
                      title: copy[ConsumerTerm.connectedHealthSourcesTitle],
                    ),
                    for (final source in _sources)
                      _SourceCard(
                        copy: copy,
                        source: source,
                        isSyncing: _syncingIds.contains(source['id']?.toString()),
                        onPauseResume: () => _changeState(source),
                        onSyncNow: () => _triggerSync(source),
                        onDisconnect: () => _disconnect(source),
                        onDeleteData: () => _deleteImportedData(source),
                        isEn: _isEn,
                      ),
                  ],
                  const SizedBox(height: ClaraTokens.spaceLg),
                  SectionHeader(
                    title: _isEn
                        ? 'Available Health Providers'
                        : 'Nguồn sức khỏe có thể kết nối',
                  ),
                  const SizedBox(height: ClaraTokens.spaceXs),
                  Text(
                    _isEn
                        ? 'Connect wearable platforms (Health Connect, Huawei Health, Fitbit, Garmin) to sync steps, heart rate, and sleep.'
                        : 'Kết nối nền tảng thiết bị đeo (Health Connect, Huawei Health, Fitbit, Garmin) để đồng bộ bước chân, nhịp tim và giấc ngủ.',
                    style: const TextStyle(fontSize: 13, color: Colors.black54),
                  ),
                  const SizedBox(height: ClaraTokens.spaceSm),
                  if (availableProviders.isEmpty)
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(ClaraTokens.spaceMd),
                        child: Text(
                          _isEn
                              ? 'All supported providers are currently connected.'
                              : 'Tất cả các nguồn được hỗ trợ hiện đã được kết nối.',
                          style: const TextStyle(fontWeight: FontWeight.w500),
                        ),
                      ),
                    )
                  else
                    for (final provider in availableProviders)
                      _AvailableProviderCard(
                        provider: provider,
                        isEn: _isEn,
                        onConnect: () => _connectProvider(provider),
                      ),
                  const SizedBox(height: ClaraTokens.spaceLg),
                  SectionHeader(
                    title:
                        copy[ConsumerTerm.connectedHealthBeforeConnectingTitle],
                  ),
                  _InfoCard(
                    icon: Icons.health_and_safety_outlined,
                    title: copy[ConsumerTerm.connectedHealthChooseDataTitle],
                    body:
                        copy[ConsumerTerm.connectedHealthChooseDataDescription],
                  ),
                  _InfoCard(
                    icon: Icons.privacy_tip_outlined,
                    title: copy[ConsumerTerm.connectedHealthPrivateDataTitle],
                    body: copy[
                        ConsumerTerm.connectedHealthPrivateDataDescription],
                  ),
                ],
              ),
      ),
    );
  }
}

class _EmptySources extends StatelessWidget {
  const _EmptySources({required this.copy});

  final ConsumerTerminology copy;

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(ClaraTokens.spaceLg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(Icons.watch_outlined, size: 32),
              const SizedBox(height: ClaraTokens.spaceSm),
              Text(copy[ConsumerTerm.connectedHealthEmptyTitle],
                  style: const TextStyle(fontWeight: FontWeight.w700)),
              const SizedBox(height: ClaraTokens.spaceXs),
              Text(copy[ConsumerTerm.connectedHealthEmptyDescription]),
            ],
          ),
        ),
      );
}

class _SourceCard extends StatelessWidget {
  const _SourceCard({
    required this.copy,
    required this.source,
    required this.isSyncing,
    required this.onPauseResume,
    required this.onSyncNow,
    required this.onDisconnect,
    required this.onDeleteData,
    required this.isEn,
  });

  final ConsumerTerminology copy;
  final Map<String, dynamic> source;
  final bool isSyncing;
  final VoidCallback onPauseResume;
  final VoidCallback onSyncNow;
  final VoidCallback onDisconnect;
  final VoidCallback onDeleteData;
  final bool isEn;

  @override
  Widget build(BuildContext context) {
    final status = source['status']?.toString() ?? 'unknown';
    final isPaused = status == 'paused';
    final title = source['display_label']?.toString().trim().isNotEmpty == true
        ? source['display_label'].toString()
        : source['provider']?.toString() ??
            copy[ConsumerTerm.connectedHealthFallbackSourceTitle];
    final types = (source['data_types'] as List? ?? const []).join(', ');
    final lastSynced = source['last_synced_at']?.toString();

    return Card(
      key: Key('source-card-${source['id'] ?? source['provider']}'),
      margin: const EdgeInsets.only(bottom: ClaraTokens.spaceSm),
      child: Padding(
        padding: const EdgeInsets.all(ClaraTokens.spaceMd),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            const Icon(Icons.watch_outlined),
            const SizedBox(width: ClaraTokens.spaceSm),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                  if (lastSynced != null && lastSynced.isNotEmpty)
                    Text(
                      isEn
                          ? 'Last sync: $lastSynced'
                          : 'Đồng bộ lần cuối: $lastSynced',
                      style: const TextStyle(
                        fontSize: 11,
                        color: Colors.black54,
                      ),
                    ),
                ],
              ),
            ),
            Chip(label: Text(_statusLabel(status))),
          ]),
          if (types.isNotEmpty) ...[
            const SizedBox(height: ClaraTokens.spaceXs),
            Text(
              copy.format(
                ConsumerTerm.connectedHealthAllowedData,
                <String, Object?>{'types': types},
              ),
            ),
          ],
          const SizedBox(height: ClaraTokens.spaceSm),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                isEn ? 'Sync toggle' : 'Bật/Tắt đồng bộ',
                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
              ),
              Switch(
                key: Key('sync-toggle-${source['id'] ?? source['provider']}'),
                value: !isPaused,
                onChanged: (_) => onPauseResume(),
              ),
            ],
          ),
          const SizedBox(height: ClaraTokens.spaceXs),
          Wrap(
            spacing: ClaraTokens.spaceXs,
            runSpacing: ClaraTokens.spaceXs,
            children: [
              OutlinedButton.icon(
                key: Key('sync-now-button-${source['id'] ?? source['provider']}'),
                onPressed: isSyncing || isPaused ? null : onSyncNow,
                icon: isSyncing
                    ? const SizedBox(
                        width: 14,
                        height: 14,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.sync, size: 16),
                label: Text(
                  isSyncing
                      ? (isEn ? 'Syncing...' : 'Đang đồng bộ...')
                      : (isEn ? 'Sync now' : 'Đồng bộ ngay'),
                ),
              ),
              OutlinedButton(
                key: Key('pause-resume-button-${source['id'] ?? source['provider']}'),
                onPressed: onPauseResume,
                child: Text(
                  isPaused
                      ? copy[ConsumerTerm.connectedHealthResume]
                      : copy[ConsumerTerm.connectedHealthPause],
                ),
              ),
              TextButton(
                key: Key('disconnect-button-${source['id'] ?? source['provider']}'),
                onPressed: onDisconnect,
                child: Text(copy[ConsumerTerm.connectedHealthDisconnect]),
              ),
              TextButton(
                key: Key('delete-data-button-${source['id'] ?? source['provider']}'),
                onPressed: onDeleteData,
                child: Text(
                  copy[ConsumerTerm.connectedHealthDeleteImportedData],
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            ],
          ),
        ]),
      ),
    );
  }

  String _statusLabel(String status) => switch (status) {
        'healthy' => copy[ConsumerTerm.connectedHealthStatusHealthy],
        'connected' => copy[ConsumerTerm.connectedHealthStatusConnected],
        'paused' => copy[ConsumerTerm.connectedHealthStatusPaused],
        'needs_reauth' => copy[ConsumerTerm.connectedHealthStatusNeedsReauth],
        'disconnected' => copy[ConsumerTerm.connectedHealthStatusDisconnected],
        _ => copy[ConsumerTerm.connectedHealthStatusUnknown],
      };
}

class _AvailableProviderCard extends StatelessWidget {
  const _AvailableProviderCard({
    required this.provider,
    required this.isEn,
    required this.onConnect,
  });

  final SupportedProviderInfo provider;
  final bool isEn;
  final VoidCallback onConnect;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: Key('available-provider-${provider.id}'),
      margin: const EdgeInsets.only(bottom: ClaraTokens.spaceSm),
      child: ListTile(
        leading: Icon(provider.icon, size: 28),
        title: Text(
          provider.title,
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        subtitle: Text(
          isEn ? provider.descriptionEn : provider.descriptionVi,
          style: const TextStyle(fontSize: 12),
        ),
        trailing: FilledButton.tonal(
          key: Key('connect-button-${provider.id}'),
          onPressed: onConnect,
          child: Text(isEn ? 'Connect' : 'Kết nối'),
        ),
      ),
    );
  }
}

class _InfoCard extends StatelessWidget {
  const _InfoCard(
      {required this.icon, required this.title, required this.body});
  final IconData icon;
  final String title;
  final String body;
  @override
  Widget build(BuildContext context) => ListTile(
        contentPadding: EdgeInsets.zero,
        leading: Icon(icon),
        title: Text(title),
        subtitle: Text(body),
      );
}

class _RetryCard extends StatelessWidget {
  const _RetryCard({
    required this.copy,
    required this.message,
    required this.onRetry,
  });
  final ConsumerTerminology copy;
  final String message;
  final VoidCallback onRetry;
  @override
  Widget build(BuildContext context) => Card(
        child: ListTile(
          leading: const Icon(Icons.error_outline),
          title: Text(copy[ConsumerTerm.connectedHealthLoadFailedTitle]),
          subtitle: Text(message),
          trailing: TextButton(
            onPressed: onRetry,
            child: Text(copy[ConsumerTerm.actionRetry]),
          ),
        ),
      );
}

