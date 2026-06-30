import 'package:flutter/material.dart';

import '../core/analytics.dart';
import '../core/api_client.dart';
import '../core/connectivity_service.dart';
import '../core/feature_flags.dart';
import '../core/session_store.dart';
import '../widgets/error_retry_view.dart';
import '../widgets/offline_banner.dart';

// =============================================================================
// SelfMedCabinetScreen — clara-mobile-feature-parity Task 5.2 (Req 3.1, 3.2, 3.5).
//
// The self-med-branded entry to the user's medicine cabinet. It lists, adds and
// deletes cabinet items against CLARA_API via the parity-named
// `ApiClient.getCabinet` / `addCabinetItem` / `deleteCabinetItem` ops (which
// delegate to the shared `/careguard/cabinet*` contract — no backend change,
// Req 15.5). It deliberately mirrors the consent-gate + list/add/delete pattern
// of the existing `CareguardCabinetScreen`; this is the self-med presentation of
// the same cabinet, so the two stay behaviorally consistent.
//
//   * 3.1 List cabinet items with their source (manual/OCR/barcode/imported)
//         and key fields (dosage, quantity, expiry).
//   * 3.2 Add and delete cabinet items against CLARA_API, behind the self-med
//         consent gate.
//   * 3.5 Where self-med consent has not been granted, gate the cabinet surface
//         behind the consent affordance (the medical-disclaimer consent, same
//         `GET /auth/consent-status` + `POST /auth/consent` gate as the web
//         self-med / CareGuard flow).
//
// Additionally gated by `selfmed_cabinet_mobile_enabled` (Req 15.1): when the
// flag is off the screen renders an unavailable placeholder and performs no
// network calls, preserving the pre-feature app. Offline mutations are blocked
// with preserved input via the shared OfflineMutationGuard (Req 9.5). No PII or
// free-text medicine names ever reach analytics.
// =============================================================================

String _str(Object? value) => value == null ? '' : value.toString();

/// Human-readable Vietnamese label for a cabinet item's provenance (Req 3.1).
String selfMedSourceLabel(String source) {
  switch (source.trim().toLowerCase()) {
    case 'ocr':
      return 'Quét ảnh (OCR)';
    case 'barcode':
      return 'Mã vạch';
    case 'imported':
      return 'Nhập từ hồ sơ';
    case 'manual':
      return 'Nhập thủ công';
    case '':
      return 'Nhập thủ công';
    default:
      return source;
  }
}

/// A self-med cabinet item. Parses the user-facing fields the screen renders,
/// including provenance (`source`) and expiry (`expires_on`) required by 3.1.
class SelfMedCabinetItem {
  SelfMedCabinetItem({
    required this.id,
    required this.drugName,
    this.source = 'manual',
    this.dosage = '',
    this.dosageForm = '',
    this.quantity = 0,
    this.expiresOn = '',
  });

  final int id;
  final String drugName;
  final String source;
  final String dosage;
  final String dosageForm;
  final num quantity;

  /// ISO date string (e.g. `2026-01-31`) or empty when not set.
  final String expiresOn;

  factory SelfMedCabinetItem.fromJson(Map<String, dynamic> json) {
    final quantityRaw = json['quantity'];
    return SelfMedCabinetItem(
      id: (json['id'] is num) ? (json['id'] as num).toInt() : 0,
      drugName: _str(json['drug_name']),
      source: _str(json['source']).isEmpty ? 'manual' : _str(json['source']),
      dosage: _str(json['dosage']),
      dosageForm: _str(json['dosage_form']),
      quantity: quantityRaw is num ? quantityRaw : 0,
      expiresOn: _str(json['expires_on']),
    );
  }
}

class SelfMedCabinetScreen extends StatefulWidget {
  const SelfMedCabinetScreen({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    required this.featureFlags,
    this.connectivity,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  /// Resolver for `selfmed_cabinet_mobile_enabled` (Req 3, 15.1). When the gate
  /// is closed the screen is inert and shows an unavailable placeholder.
  final MobileFeatureFlagResolver featureFlags;

  /// Optional connectivity signal; when supplied, an offline banner is shown
  /// and mutating ops (add/delete) are blocked offline (Req 9.5).
  final ConnectivityService? connectivity;

  @override
  State<SelfMedCabinetScreen> createState() => _SelfMedCabinetScreenState();
}

class _SelfMedCabinetScreenState extends State<SelfMedCabinetScreen> {
  static const _mutationGuard = OfflineMutationGuard();

  // Consent gate state (Req 3.5).
  bool _consentLoading = true;
  bool _consentAccepted = false;
  bool _consentChecked = false;
  bool _consentSaving = false;
  String _requiredVersion = '';
  String? _consentError;

  // Cabinet state.
  bool _cabinetLoading = false;
  String? _cabinetError;
  List<SelfMedCabinetItem> _items = const [];

  bool get _enabled => widget.featureFlags.selfMedCabinetEnabled;

  @override
  void initState() {
    super.initState();
    if (_enabled) {
      // Reuse the existing cabinet screen-view event (no-PII): the self-med and
      // CareGuard cabinets are the same underlying surface.
      getAnalyticsClient()
          .captureScreenView(MobileAnalyticsEvents.careguardCabinetViewed);
      _loadConsent();
    } else {
      _consentLoading = false;
    }
  }

  String? get _token {
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) return null;
    return token;
  }

  bool get _isOnline => widget.connectivity?.currentValue ?? true;

  // --- Consent (Req 3.5) ---------------------------------------------------

  Future<void> _loadConsent() async {
    final token = _token;
    if (token == null) {
      setState(() {
        _consentLoading = false;
        _consentError = 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.';
      });
      return;
    }
    setState(() {
      _consentLoading = true;
      _consentError = null;
    });
    try {
      final status = await widget.apiClient.getConsentStatus(accessToken: token);
      final accepted = status['accepted'] == true;
      if (!mounted) return;
      setState(() {
        _requiredVersion = _str(status['required_version']);
        _consentAccepted = accepted;
      });
      if (accepted) {
        await _loadCabinet();
      }
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _consentError = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(() =>
          _consentError = 'Không thể kiểm tra điều khoản y tế. Vui lòng thử lại.');
    } finally {
      if (mounted) {
        setState(() => _consentLoading = false);
      }
    }
  }

  Future<void> _acceptConsent() async {
    final token = _token;
    if (token == null || _requiredVersion.isEmpty) return;
    if (!_consentChecked) {
      setState(() => _consentError = 'Vui lòng tick xác nhận trước khi tiếp tục.');
      return;
    }
    setState(() {
      _consentSaving = true;
      _consentError = null;
    });
    try {
      await widget.apiClient
          .acceptConsent(accessToken: token, consentVersion: _requiredVersion);
      if (!mounted) return;
      setState(() => _consentAccepted = true);
      await _loadCabinet();
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _consentError = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(() => _consentError = 'Không thể lưu xác nhận. Vui lòng thử lại.');
    } finally {
      if (mounted) {
        setState(() => _consentSaving = false);
      }
    }
  }

  // --- Cabinet CRUD (Req 3.1, 3.2) -----------------------------------------

  Future<void> _loadCabinet() async {
    final token = _token;
    if (token == null) return;
    setState(() {
      _cabinetLoading = true;
      _cabinetError = null;
    });
    try {
      final data = await widget.apiClient.getCabinet(accessToken: token);
      final rawItems = data['items'];
      final items = <SelfMedCabinetItem>[];
      if (rawItems is List) {
        for (final item in rawItems) {
          if (item is Map) {
            items.add(SelfMedCabinetItem.fromJson(item.cast<String, dynamic>()));
          }
        }
      }
      if (!mounted) return;
      setState(() => _items = items);
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _cabinetError = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(() => _cabinetError = 'Không thể tải tủ thuốc. Vui lòng thử lại.');
    } finally {
      if (mounted) {
        setState(() => _cabinetLoading = false);
      }
    }
  }

  Future<void> _addItem() async {
    // Block the add mutation while offline; the editor sheet is never opened so
    // there is no input to lose (Req 9.5).
    if (!_isOnline) {
      _showSnack(kOfflineMutationBlockedMessage);
      return;
    }
    final payload = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      builder: (_) => const _SelfMedItemEditor(),
    );
    if (payload == null) return;
    final token = _token;
    if (token == null) return;

    await _mutationGuard.run(
      isOnline: _isOnline,
      mutate: () async {
        await widget.apiClient.addCabinetItem(accessToken: token, payload: payload);
        await _loadCabinet();
      },
      onBlocked: _showSnack,
    );
  }

  Future<void> _deleteItem(SelfMedCabinetItem item) async {
    if (!_isOnline) {
      _showSnack(kOfflineMutationBlockedMessage);
      return;
    }
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Xóa thuốc'),
        content: Text('Xóa "${item.drugName}" khỏi tủ thuốc?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Hủy'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Xóa'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    final token = _token;
    if (token == null) return;

    await _mutationGuard.run(
      isOnline: _isOnline,
      mutate: () async {
        await widget.apiClient
            .deleteCabinetItem(accessToken: token, itemId: item.id);
        await _loadCabinet();
      },
      onBlocked: _showSnack,
    );
  }

  void _showSnack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  // --- Build ---------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Tủ thuốc của tôi')),
      floatingActionButton: (_enabled && _consentAccepted)
          ? FloatingActionButton.extended(
              onPressed: _addItem,
              icon: const Icon(Icons.add),
              label: const Text('Thêm thuốc'),
            )
          : null,
      body: _buildBody(context),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (!_enabled) {
      return const _UnavailablePlaceholder();
    }
    final connectivity = widget.connectivity;
    final content = _buildGatedContent(context);
    if (connectivity == null) {
      return content;
    }
    return Column(
      children: [
        OfflineBanner(connectivity: connectivity),
        Expanded(child: content),
      ],
    );
  }

  Widget _buildGatedContent(BuildContext context) {
    if (_consentLoading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (!_consentAccepted) {
      return _SelfMedConsentGate(
        requiredVersion: _requiredVersion,
        checked: _consentChecked,
        saving: _consentSaving,
        error: _consentError,
        onCheckedChanged: (value) => setState(() => _consentChecked = value),
        onAccept: _acceptConsent,
        onRetry: _loadConsent,
      );
    }
    return _buildCabinet(context);
  }

  Widget _buildCabinet(BuildContext context) {
    if (_cabinetError != null) {
      return ErrorRetryView(message: _cabinetError!, onRetry: _loadCabinet);
    }
    return RefreshIndicator(
      onRefresh: _loadCabinet,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
        children: [
          if (_cabinetLoading) const LinearProgressIndicator(),
          if (!_cabinetLoading && _items.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 24),
              child: Center(
                child: Text('Tủ thuốc trống. Thêm thuốc để bắt đầu.'),
              ),
            ),
          ..._items.map(_buildItemTile),
        ],
      ),
    );
  }

  Widget _buildItemTile(SelfMedCabinetItem item) {
    final details = <String>[
      if (item.dosage.isNotEmpty) item.dosage,
      if (item.dosageForm.isNotEmpty) item.dosageForm,
      if (item.quantity > 0) 'SL: ${item.quantity}',
      if (item.expiresOn.isNotEmpty) 'HSD: ${item.expiresOn}',
    ];
    return Card(
      child: ListTile(
        title: Text(item.drugName),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (details.isNotEmpty) Text(details.join(' • ')),
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                'Nguồn: ${selfMedSourceLabel(item.source)}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
          ],
        ),
        trailing: Semantics(
          button: true,
          label: 'Xóa ${item.drugName}',
          child: IconButton(
            icon: const Icon(Icons.delete_outline),
            tooltip: 'Xóa',
            onPressed: () => _deleteItem(item),
          ),
        ),
      ),
    );
  }
}

/// Shown when `selfmed_cabinet_mobile_enabled` is off (Req 15.1): the surface is
/// inert and no network call is made, preserving the pre-feature app.
class _UnavailablePlaceholder extends StatelessWidget {
  const _UnavailablePlaceholder();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Padding(
        padding: EdgeInsets.all(24),
        child: Text(
          'Tính năng tủ thuốc chưa được bật.',
          textAlign: TextAlign.center,
        ),
      ),
    );
  }
}

/// Medical-disclaimer consent gate for the self-med cabinet (Req 3.5). Mirrors
/// the CareGuard flow's gate: blocks the cabinet until the caller accepts the
/// required consent version.
class _SelfMedConsentGate extends StatelessWidget {
  const _SelfMedConsentGate({
    required this.requiredVersion,
    required this.checked,
    required this.saving,
    required this.error,
    required this.onCheckedChanged,
    required this.onAccept,
    required this.onRetry,
  });

  final String requiredVersion;
  final bool checked;
  final bool saving;
  final String? error;
  final ValueChanged<bool> onCheckedChanged;
  final VoidCallback onAccept;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Tuyên bố miễn trừ trách nhiệm y tế',
                    style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 8),
                const Text(
                  'CLARA chỉ hỗ trợ cảnh báo an toàn thuốc và không thay thế bác sĩ. '
                  'Không sử dụng ứng dụng để tự chẩn đoán, tự kê đơn hoặc tự điều chỉnh '
                  'liều dùng.',
                ),
                const SizedBox(height: 8),
                Text(
                  'Phiên bản điều khoản hiện tại: '
                  '${requiredVersion.isEmpty ? "-" : requiredVersion}',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const SizedBox(height: 12),
                CheckboxListTile(
                  value: checked,
                  onChanged: (value) => onCheckedChanged(value ?? false),
                  contentPadding: EdgeInsets.zero,
                  controlAffinity: ListTileControlAffinity.leading,
                  title: const Text(
                    'Tôi đã đọc, hiểu và đồng ý với tuyên bố miễn trừ trách nhiệm y '
                    'tế của CLARA.',
                  ),
                ),
                const SizedBox(height: 8),
                FilledButton(
                  onPressed: (saving || !checked) ? null : onAccept,
                  child: saving
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Đồng ý và tiếp tục'),
                ),
                if (error != null) ...[
                  const SizedBox(height: 12),
                  Text(
                    error!,
                    style: TextStyle(color: Theme.of(context).colorScheme.error),
                  ),
                  const SizedBox(height: 8),
                  OutlinedButton(
                    onPressed: onRetry,
                    child: const Text('Thử kiểm tra lại'),
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

/// Add form for a self-med cabinet item. Returns the create payload map
/// (matching `MedicineCabinetItemCreate`) on save, or `null` when cancelled.
class _SelfMedItemEditor extends StatefulWidget {
  const _SelfMedItemEditor();

  @override
  State<_SelfMedItemEditor> createState() => _SelfMedItemEditorState();
}

class _SelfMedItemEditorState extends State<_SelfMedItemEditor> {
  final _drugName = TextEditingController();
  final _dosage = TextEditingController();
  final _dosageForm = TextEditingController();
  final _quantity = TextEditingController();
  final _expiresOn = TextEditingController();
  String? _error;

  @override
  void dispose() {
    for (final c in [_drugName, _dosage, _dosageForm, _quantity, _expiresOn]) {
      c.dispose();
    }
    super.dispose();
  }

  void _submit() {
    final name = _drugName.text.trim();
    if (name.isEmpty) {
      setState(() => _error = 'Vui lòng nhập tên thuốc.');
      return;
    }
    final quantityText = _quantity.text.trim();
    num quantity = 0;
    if (quantityText.isNotEmpty) {
      final parsed = num.tryParse(quantityText);
      if (parsed == null || parsed < 0) {
        setState(() => _error = 'Số lượng không hợp lệ.');
        return;
      }
      quantity = parsed;
    }

    final payload = <String, dynamic>{
      'drug_name': name,
      'dosage': _dosage.text.trim(),
      'dosage_form': _dosageForm.text.trim(),
      'quantity': quantity,
      'source': 'manual',
    };
    final expires = _expiresOn.text.trim();
    if (expires.isNotEmpty) {
      payload['expires_on'] = expires;
    }
    Navigator.of(context).pop(payload);
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        left: 16,
        right: 16,
        top: 16,
        bottom: MediaQuery.of(context).viewInsets.bottom + 16,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Thêm thuốc', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            _field(_drugName, 'Tên thuốc *'),
            _field(_dosage, 'Hàm lượng / liều'),
            _field(_dosageForm, 'Dạng bào chế'),
            _field(_quantity, 'Số lượng', keyboardType: TextInputType.number),
            _field(_expiresOn, 'Hạn sử dụng (YYYY-MM-DD)'),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(
                  _error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: const Text('Hủy'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: FilledButton(
                    onPressed: _submit,
                    child: const Text('Thêm'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _field(
    TextEditingController controller,
    String label, {
    TextInputType? keyboardType,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: TextField(
        controller: controller,
        keyboardType: keyboardType,
        decoration: InputDecoration(
          labelText: label,
          border: const OutlineInputBorder(),
          isDense: true,
        ),
      ),
    );
  }
}
