import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/session_store.dart';
import '../../theme/components/section_header.dart';
import '../../theme/tokens.dart';

/// Clear, ownership-first management for health sources already authorized on
/// the user's device. Native permission discovery/import lives behind the
/// Android connector bridge; this screen never fabricates a connected device.
class ConnectedHealthScreen extends StatefulWidget {
  const ConnectedHealthScreen({
    super.key,
    required this.apiClient,
    required this.sessionStore,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  @override
  State<ConnectedHealthScreen> createState() => _ConnectedHealthScreenState();
}

class _ConnectedHealthScreenState extends State<ConnectedHealthScreen> {
  bool _loading = true;
  String? _error;
  List<Map<String, dynamic>> _sources = const [];

  String? get _token => widget.sessionStore.accessToken;

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
      title: 'Ngắt kết nối nguồn này?',
      body: 'Dữ liệu đã nhập vẫn được giữ lại. Bạn có thể xóa riêng dữ liệu đó bên dưới.',
      confirmLabel: 'Ngắt kết nối',
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
      title: 'Xóa dữ liệu đã nhập?',
      body: 'Việc này xóa các quan sát và tổng hợp từ nguồn này. Không thể hoàn tác.',
      confirmLabel: 'Xóa dữ liệu',
      destructive: true,
    );
    if (!confirmed) return;
    try {
      await widget.apiClient.deleteConnectedHealthImportedData(
        accessToken: token,
        connectorId: id,
      );
      await _load();
      if (mounted) _showMessage('Đã xóa dữ liệu đã nhập từ nguồn này.');
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
                child: const Text('Hủy'),
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
    return Scaffold(
      appBar: AppBar(title: const Text('Dữ liệu sức khỏe')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : ListView(
                padding: const EdgeInsets.all(ClaraTokens.spaceMd),
                children: [
                  const Text(
                    'Kết nối khi bạn muốn',
                    style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: ClaraTokens.spaceXs),
                  const Text(
                    'CLARA chỉ đọc các nhóm dữ liệu bạn cho phép. Bạn có thể tạm dừng, ngắt kết nối hoặc xóa dữ liệu bất cứ lúc nào.',
                  ),
                  const SizedBox(height: ClaraTokens.spaceLg),
                  if (_error != null)
                    _RetryCard(message: _error!, onRetry: _load)
                  else if (_sources.isEmpty)
                    const _EmptySources()
                  else ...[
                    const SectionHeader(title: 'Nguồn đã kết nối'),
                    for (final source in _sources)
                      _SourceCard(
                        source: source,
                        onPauseResume: () => _changeState(source),
                        onDisconnect: () => _disconnect(source),
                        onDeleteData: () => _deleteImportedData(source),
                      ),
                  ],
                  const SizedBox(height: ClaraTokens.spaceLg),
                  const SectionHeader(title: 'Trước khi kết nối'),
                  const _InfoCard(
                    icon: Icons.health_and_safety_outlined,
                    title: 'Bạn chọn dữ liệu được dùng',
                    body: 'Ví dụ: bước chân, giấc ngủ hoặc nhịp tim. CLARA không suy đoán khi dữ liệu thiếu.',
                  ),
                  const _InfoCard(
                    icon: Icons.privacy_tip_outlined,
                    title: 'Dữ liệu cá nhân không tự động gửi vào chat',
                    body: 'Bạn cần cho phép mục đích hỗ trợ sức khỏe trước khi dữ liệu được đưa vào gợi ý cá nhân.',
                  ),
                ],
              ),
      ),
    );
  }
}

class _EmptySources extends StatelessWidget {
  const _EmptySources();

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(ClaraTokens.spaceLg),
          child: const Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.watch_outlined, size: 32),
              SizedBox(height: ClaraTokens.spaceSm),
              Text('Chưa có nguồn nào được kết nối',
                  style: TextStyle(fontWeight: FontWeight.w700)),
              SizedBox(height: ClaraTokens.spaceXs),
              Text('Khi tính năng kết nối trên thiết bị sẵn sàng, CLARA sẽ luôn hỏi quyền trước khi đọc dữ liệu.'),
            ],
          ),
        ),
      );
}

class _SourceCard extends StatelessWidget {
  const _SourceCard({
    required this.source,
    required this.onPauseResume,
    required this.onDisconnect,
    required this.onDeleteData,
  });

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
        : source['provider']?.toString() ?? 'Nguồn sức khỏe';
    final types = (source['data_types'] as List? ?? const []).join(', ');
    return Card(
      margin: const EdgeInsets.only(bottom: ClaraTokens.spaceSm),
      child: Padding(
        padding: const EdgeInsets.all(ClaraTokens.spaceMd),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            const Icon(Icons.watch_outlined),
            const SizedBox(width: ClaraTokens.spaceSm),
            Expanded(child: Text(title, style: const TextStyle(fontWeight: FontWeight.w700))),
            Chip(label: Text(_statusLabel(status))),
          ]),
          if (types.isNotEmpty) ...[
            const SizedBox(height: ClaraTokens.spaceXs),
            Text('Được phép: $types'),
          ],
          const SizedBox(height: ClaraTokens.spaceSm),
          Wrap(spacing: ClaraTokens.spaceXs, runSpacing: ClaraTokens.spaceXs, children: [
            OutlinedButton(
              onPressed: onPauseResume,
              child: Text(isPaused ? 'Tiếp tục' : 'Tạm dừng'),
            ),
            TextButton(onPressed: onDisconnect, child: const Text('Ngắt kết nối')),
            TextButton(
              onPressed: onDeleteData,
              child: Text('Xóa dữ liệu', style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ),
          ]),
        ]),
      ),
    );
  }

  String _statusLabel(String status) => switch (status) {
        'healthy' => 'Đã cập nhật',
        'connected' => 'Sẵn sàng',
        'paused' => 'Đang tạm dừng',
        'needs_reauth' => 'Cần cấp quyền lại',
        'disconnected' => 'Đã ngắt kết nối',
        _ => 'Chưa rõ',
      };
}

class _InfoCard extends StatelessWidget {
  const _InfoCard({required this.icon, required this.title, required this.body});
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
  const _RetryCard({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;
  @override
  Widget build(BuildContext context) => Card(
        child: ListTile(
          leading: const Icon(Icons.error_outline),
          title: const Text('Chưa thể tải nguồn sức khỏe'),
          subtitle: Text(message),
          trailing: TextButton(onPressed: onRetry, child: const Text('Thử lại')),
        ),
      );
}
