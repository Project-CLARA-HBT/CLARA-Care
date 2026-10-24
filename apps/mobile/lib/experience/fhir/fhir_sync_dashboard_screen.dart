// Web Integration Status Dashboard and FHIR Sync Management (Phase PH11).
//
// Displays:
//   * Machine-readable FHIR R4 Conformance boundaries and capabilities.
//   * Non-accredited / summary-not-ips honest disclosure invariant.
//   * Connected health data connectors & sync status.
//   * Manual sync trigger with loading state.
//   * Navigation into consented health record export view.

import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/session_store.dart';
import '../../theme/tokens.dart';
import '../language_controller.dart';
import 'fhir_export_screen.dart';
import 'fhir_models.dart';

class FhirSyncDashboardScreen extends StatefulWidget {
  const FhirSyncDashboardScreen({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    this.languageController,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;
  final LanguageController? languageController;

  @override
  State<FhirSyncDashboardScreen> createState() => _FhirSyncDashboardScreenState();
}

class _FhirSyncDashboardScreenState extends State<FhirSyncDashboardScreen> {
  bool _loading = true;
  String? _errorMessage;
  FhirConformanceStatement? _conformance;
  List<ConnectorSyncItem> _connectors = const [];
  Map<String, dynamic>? _aggregateStatus;
  final Set<String> _syncingConnectorIds = {};

  String? get _token => widget.sessionStore.accessToken;
  String get _locale => widget.languageController?.languageCode ?? 'vi';
  bool get _isEn => _locale == 'en';

  @override
  void initState() {
    super.initState();
    _loadDashboardData();
  }

  Future<void> _loadDashboardData() async {
    final token = _token;
    if (token == null || token.isEmpty) {
      setState(() {
        _loading = false;
        _errorMessage = _isEn
            ? 'Authentication required. Please sign in.'
            : 'Vui lòng đăng nhập để xem trạng thái đồng bộ.';
      });
      return;
    }

    setState(() {
      _loading = true;
      _errorMessage = null;
    });

    try {
      // 1. Fetch Conformance Statement
      final conformanceMap = await widget.apiClient.getFhirConformance(
        accessToken: token,
      );
      final conformance = FhirConformanceStatement.fromJson(conformanceMap);

      // 2. Fetch Connectors
      final connectorsList = await widget.apiClient.listConnectedHealthSources(
        accessToken: token,
      );
      final connectors = connectorsList
          .map((m) => ConnectorSyncItem.fromJson(m))
          .toList();

      // 3. Optional status adapter (graceful fallback)
      Map<String, dynamic>? aggregate;
      try {
        aggregate = await widget.apiClient.getConnectorStatusAdapter(
          accessToken: token,
        );
      } catch (_) {
        // Fallback gracefully if endpoint is admin-restricted
      }

      if (mounted) {
        setState(() {
          _conformance = conformance;
          _connectors = connectors;
          _aggregateStatus = aggregate;
          _loading = false;
        });
      }
    } on ApiException catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = e.message;
          _loading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = _isEn
              ? 'Failed to load integration status.'
              : 'Không thể tải trạng thái tích hợp.';
          _loading = false;
        });
      }
    }
  }

  Future<void> _triggerSync(ConnectorSyncItem connector) async {
    final token = _token;
    if (token == null || token.isEmpty) return;

    setState(() {
      _syncingConnectorIds.add(connector.id);
    });

    try {
      await widget.apiClient.syncConnector(
        accessToken: token,
        connectorId: connector.id,
      );

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              _isEn
                  ? 'Sync initiated for ${connector.displayLabel}'
                  : 'Đã kích hoạt đồng bộ cho ${connector.displayLabel}',
            ),
            duration: const Duration(seconds: 2),
          ),
        );
      }

      // Reload connectors to update last synced timestamp
      await _loadDashboardData();
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(e.message),
            backgroundColor: Theme.of(context).colorScheme.error,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _syncingConnectorIds.remove(connector.id);
        });
      }
    }
  }

  void _navigateToExportScreen() {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => FhirExportScreen(
          apiClient: widget.apiClient,
          sessionStore: widget.sessionStore,
          languageController: widget.languageController,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final title = _isEn
        ? 'FHIR Interoperability & Sync'
        : 'Đồng bộ & Xuất chuẩn FHIR R4';

    return Scaffold(
      appBar: AppBar(
        title: Text(title),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_outlined),
            tooltip: _isEn ? 'Refresh' : 'Làm mới',
            onPressed: _loading ? null : _loadDashboardData,
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _loadDashboardData,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.all(ClaraTokens.spaceMd),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    if (_errorMessage != null) ...[
                      _buildErrorCard(_errorMessage!),
                      const SizedBox(height: ClaraTokens.spaceMd),
                    ],
                    _buildConformanceOverviewCard(),
                    const SizedBox(height: ClaraTokens.spaceMd),
                    _buildConsentedExportActionBanner(),
                    const SizedBox(height: ClaraTokens.spaceLg),
                    _buildConnectorsSection(),
                    const SizedBox(height: ClaraTokens.spaceLg),
                    _buildHonestDisclosureCard(),
                  ],
                ),
              ),
      ),
    );
  }

  Widget _buildConformanceOverviewCard() {
    final conformance = _conformance;
    final fhirVer = conformance?.fhirVersion ?? '4.0.1';
    final mappingVer = conformance?.mappingVersion ?? '1.0';
    final isExportEnabled = conformance?.exportEnabled ?? true;
    final isImportEnabled = conformance?.importEnabled ?? false;

    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
        side: BorderSide(color: Theme.of(context).colorScheme.outlineVariant),
      ),
      child: Padding(
        padding: const EdgeInsets.all(ClaraTokens.spaceMd),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.hub_outlined,
                  color: Theme.of(context).colorScheme.primary,
                  size: 26,
                ),
                const SizedBox(width: ClaraTokens.spaceSm),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _isEn ? 'FHIR R4 Conformance & Web Gateway' : 'Cổng tích hợp & Chuẩn HL7 FHIR R4',
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      Text(
                        'FHIR v$fhirVer • Mapping v$mappingVer',
                        style: TextStyle(
                          fontSize: 12,
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.green.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(ClaraTokens.radiusSm),
                    border: Border.all(color: Colors.green.shade400),
                  ),
                  child: Text(
                    _isEn ? 'ACTIVE' : 'HOẠT ĐỘNG',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                      color: Colors.green.shade800,
                    ),
                  ),
                ),
              ],
            ),
            const Divider(height: ClaraTokens.spaceLg),
            Text(
              _isEn ? 'Supported Integration Capabilities:' : 'Năng lực tích hợp liên thông:',
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: ClaraTokens.spaceXs),
            Wrap(
              spacing: ClaraTokens.spaceXs,
              runSpacing: ClaraTokens.spaceXs,
              children: [
                _buildCapabilityChip(
                  label: _isEn ? 'FHIR R4 Export' : 'Xuất FHIR R4',
                  enabled: isExportEnabled,
                  key: const Key('fhir-capability-export'),
                ),
                _buildCapabilityChip(
                  label: _isEn ? 'Draft Import' : 'Nhập dự thảo',
                  enabled: isImportEnabled,
                  key: const Key('fhir-capability-import'),
                ),
                _buildCapabilityChip(
                  label: 'HL7 IPS Roadmap',
                  enabled: false,
                  key: const Key('fhir-capability-ips'),
                ),
                _buildCapabilityChip(
                  label: 'Collection Bundle',
                  enabled: true,
                  key: const Key('fhir-capability-bundle'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCapabilityChip({
    required String label,
    required bool enabled,
    required Key key,
  }) {
    return Chip(
      key: key,
      visualDensity: VisualDensity.compact,
      avatar: Icon(
        enabled ? Icons.check_circle : Icons.schedule,
        size: 16,
        color: enabled ? Colors.green : Colors.grey,
      ),
      label: Text(label, style: const TextStyle(fontSize: 12)),
    );
  }

  Widget _buildConsentedExportActionBanner() {
    return Card(
      elevation: 0,
      color: Theme.of(context).colorScheme.primaryContainer.withOpacity(0.3),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
        side: BorderSide(
          color: Theme.of(context).colorScheme.primary.withOpacity(0.5),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(ClaraTokens.spaceMd),
        child: Row(
          children: [
            Icon(
              Icons.file_download_outlined,
              color: Theme.of(context).colorScheme.primary,
              size: 32,
            ),
            const SizedBox(width: ClaraTokens.spaceMd),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _isEn ? 'Consented Health Record Export' : 'Xuất hồ sơ y tế có đồng thuận',
                    style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: ClaraTokens.spaceXs),
                  Text(
                    _isEn
                        ? 'Generate standard HL7 FHIR R4 bundle for sharing with doctors or personal records.'
                        : 'Tạo gói dữ liệu HL7 FHIR R4 chuẩn để lưu trữ hoặc chia sẻ với cơ sở y tế.',
                    style: TextStyle(
                      fontSize: 12,
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: ClaraTokens.spaceSm),
            FilledButton(
              key: const Key('open-fhir-export-button'),
              onPressed: _navigateToExportScreen,
              child: Text(_isEn ? 'Export' : 'Xuất'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildConnectorsSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              _isEn ? 'Connected Sources & Sync' : 'Kết nối dữ liệu & Đồng bộ',
              style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold),
            ),
            if (_aggregateStatus != null)
              Text(
                '${_aggregateStatus!['active_connectors'] ?? 0}/${_aggregateStatus!['total_connectors'] ?? _connectors.length} active',
                style: TextStyle(
                  fontSize: 12,
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
          ],
        ),
        const SizedBox(height: ClaraTokens.spaceSm),
        if (_connectors.isEmpty)
          _buildEmptyConnectorsCard()
        else
          ..._connectors.map(_buildConnectorCard),
      ],
    );
  }

  Widget _buildEmptyConnectorsCard() {
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
        side: BorderSide(color: Theme.of(context).colorScheme.outlineVariant),
      ),
      child: Padding(
        padding: const EdgeInsets.all(ClaraTokens.spaceLg),
        child: Column(
          children: [
            Icon(
              Icons.sync_disabled_outlined,
              size: 40,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            Text(
              _isEn ? 'No connected health sources' : 'Chưa có kết nối dữ liệu sức khỏe',
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: ClaraTokens.spaceXs),
            Text(
              _isEn
                  ? 'Connect Apple Health, Google Health Connect, or hospital EHR sandbox to enable continuous synchronization.'
                  : 'Kết nối Apple Health, Health Connect hoặc cổng bệnh viện để đồng bộ dữ liệu liên tục.',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 12,
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildConnectorCard(ConnectorSyncItem connector) {
    final isSyncing = _syncingConnectorIds.contains(connector.id);
    final statusColor = connector.isConnected
        ? Colors.green
        : (connector.isPaused ? Colors.orange : Colors.grey);

    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: ClaraTokens.spaceSm),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
        side: BorderSide(color: Theme.of(context).colorScheme.outlineVariant),
      ),
      child: Padding(
        padding: const EdgeInsets.all(ClaraTokens.spaceMd),
        child: Row(
          children: [
            CircleAvatar(
              backgroundColor: statusColor.withOpacity(0.15),
              child: Icon(
                Icons.devices_other_outlined,
                color: statusColor,
                size: 20,
              ),
            ),
            const SizedBox(width: ClaraTokens.spaceMd),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Flexible(
                        child: Text(
                          connector.displayLabel,
                          style: const TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                      const SizedBox(width: ClaraTokens.spaceXs),
                      Container(
                        width: 8,
                        height: 8,
                        decoration: BoxDecoration(
                          color: statusColor,
                          shape: BoxShape.circle,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 2),
                  Text(
                    connector.lastSyncedAt != null
                        ? (_isEn
                            ? 'Last synced: ${connector.lastSyncedAt}'
                            : 'Đồng bộ lúc: ${connector.lastSyncedAt}')
                        : (_isEn ? 'Not synced yet' : 'Chưa đồng bộ'),
                    style: TextStyle(
                      fontSize: 11,
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
            IconButton(
              key: Key('sync-button-${connector.id}'),
              icon: isSyncing
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.sync),
              tooltip: _isEn ? 'Sync Now' : 'Đồng bộ ngay',
              onPressed: isSyncing ? null : () => _triggerSync(connector),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHonestDisclosureCard() {
    return Card(
      elevation: 0,
      color: Theme.of(context).colorScheme.surfaceContainerHighest.withOpacity(0.5),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(ClaraTokens.radiusSm),
      ),
      child: Padding(
        padding: const EdgeInsets.all(ClaraTokens.spaceMd),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.info_outline,
                  size: 16,
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
                const SizedBox(width: ClaraTokens.spaceXs),
                Text(
                  _isEn ? 'Regulatory & Technical Disclosure' : 'Quy chuẩn & Minh bạch kỹ thuật',
                  style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                ),
              ],
            ),
            const SizedBox(height: ClaraTokens.spaceXs),
            Text(
              _isEn
                  ? 'Conformance level: fhir-r4-summary-not-ips. CLARA LifeMap FHIR projection is an export/interoperability adapter and deliberately does NOT claim full general FHIR server certification. Clinical data requires licensed professional review.'
                  : 'Mức độ tuân thủ: fhir-r4-summary-not-ips. Bản chiếu FHIR của CLARA LifeMap là bộ chuyển đổi xuất dữ liệu phục vụ tương tác, không tuyên bố chứng nhận máy chủ FHIR toàn diện. Dữ liệu y tế luôn cần chuyên gia lâm sàng đánh giá.',
              style: TextStyle(
                fontSize: 11,
                color: Theme.of(context).colorScheme.onSurfaceVariant,
                height: 1.4,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildErrorCard(String error) {
    return Card(
      color: Theme.of(context).colorScheme.errorContainer,
      child: Padding(
        padding: const EdgeInsets.all(ClaraTokens.spaceSm),
        child: Row(
          children: [
            Icon(Icons.error_outline, color: Theme.of(context).colorScheme.error),
            const SizedBox(width: ClaraTokens.spaceSm),
            Expanded(
              child: Text(
                error,
                style: TextStyle(color: Theme.of(context).colorScheme.onErrorContainer),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
