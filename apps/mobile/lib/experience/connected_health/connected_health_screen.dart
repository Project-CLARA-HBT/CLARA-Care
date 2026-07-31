import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/consumer_terminology.dart';
import '../../core/session_store.dart';
import '../../theme/components/section_header.dart';
import '../../theme/tokens.dart';
import '../language_controller.dart';

/// Clear, ownership-first management for health sources already authorized on
/// the user's device. Native permission discovery/import lives behind the
/// Android connector bridge; this screen never fabricates a connected device.
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

  String? get _token => widget.sessionStore.accessToken;
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
    return Scaffold(
      appBar: AppBar(title: Text(copy[ConsumerTerm.connectedHealthTitle])),
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
                        onPauseResume: () => _changeState(source),
                        onDisconnect: () => _disconnect(source),
                        onDeleteData: () => _deleteImportedData(source),
                      ),
                  ],
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
    required this.onPauseResume,
    required this.onDisconnect,
    required this.onDeleteData,
  });

  final ConsumerTerminology copy;
  final Map<String, dynamic> source;
  final VoidCallback onPauseResume;
  final VoidCallback onDisconnect;
  final VoidCallback onDeleteData;

  @override
  Widget build(BuildContext context) {
    final status = source['status']?.toString() ?? 'unknown';
    final isPaused = status == 'paused';
    final title = source['display_label']?.toString().trim().isNotEmpty == true
        ? source['display_label'].toString()
        : source['provider']?.toString() ??
            copy[ConsumerTerm.connectedHealthFallbackSourceTitle];
    final types = (source['data_types'] as List? ?? const []).join(', ');
    return Card(
      margin: const EdgeInsets.only(bottom: ClaraTokens.spaceSm),
      child: Padding(
        padding: const EdgeInsets.all(ClaraTokens.spaceMd),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            const Icon(Icons.watch_outlined),
            const SizedBox(width: ClaraTokens.spaceSm),
            Expanded(
                child: Text(title,
                    style: const TextStyle(fontWeight: FontWeight.w700))),
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
          Wrap(
              spacing: ClaraTokens.spaceXs,
              runSpacing: ClaraTokens.spaceXs,
              children: [
                OutlinedButton(
                  onPressed: onPauseResume,
                  child: Text(
                    isPaused
                        ? copy[ConsumerTerm.connectedHealthResume]
                        : copy[ConsumerTerm.connectedHealthPause],
                  ),
                ),
                TextButton(
                  onPressed: onDisconnect,
                  child: Text(copy[ConsumerTerm.connectedHealthDisconnect]),
                ),
                TextButton(
                  onPressed: onDeleteData,
                  child: Text(
                    copy[ConsumerTerm.connectedHealthDeleteImportedData],
                    style:
                        TextStyle(color: Theme.of(context).colorScheme.error),
                  ),
                ),
              ]),
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
