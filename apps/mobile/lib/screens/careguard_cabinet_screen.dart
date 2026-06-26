import 'package:flutter/material.dart';

import '../core/analytics.dart';
import '../core/api_client.dart';
import '../core/ddi_user_view.dart';
import '../core/session_store.dart';
import 'ddi_result_view.dart';

// =============================================================================
// CareGuard mobile cabinet CRUD — clara-selfmed-careguard-upgrade Task 9.1
// (Requirements 8.1–8.5).
//
//   * 8.2 List / add / update / delete cabinet items against the SAME API as
//         the web client (`/api/v1/careguard/cabinet*`).
//   * 8.3 Gated behind CAREGUARD_MOBILE_CABINET_ENABLED (default OFF). When off,
//         the screen is never exposed and the mobile app behaves as today
//         (manual-entry DDI check only).
//   * 8.1 / 8.4 The in-cabinet interaction check preserves the two-medicine
//         guard and renders the Vietnamese End_User DDI projection (shared
//         [DdiUserView]/[DdiResultView]) — runtime mode, fallback flags, and
//         `source_errors` are never surfaced.
//   * 8.5 Cabinet and interaction features are gated behind the SAME medical-
//         disclaimer consent requirement as the web client
//         (`GET /auth/consent-status` + `POST /auth/consent`).
// =============================================================================

/// Build-time, client-readable feature flag. Override with
/// `--dart-define=CAREGUARD_MOBILE_CABINET_ENABLED=true`. Defaults to OFF so the
/// cabinet screen is never exposed unless explicitly enabled (Requirement 8.3).
const bool kCareguardMobileCabinetEnabled =
    bool.fromEnvironment('CAREGUARD_MOBILE_CABINET_ENABLED', defaultValue: false);

/// Minimum number of distinct medicines required before a DDI check may run,
/// mirroring the web two-medicine guard (Requirements 8.1, 3.1).
const int _minimumDdiMedicines = 2;

String _str(Object? value) => value == null ? '' : value.toString();

/// A medicine-cabinet item mirroring `MedicineCabinetItemResponse`. Only the
/// user-facing fields the mobile screen renders/edits are kept.
class CabinetItem {
  CabinetItem({
    required this.id,
    required this.drugName,
    required this.normalizedName,
    this.brandName = '',
    this.manufacturer = '',
    this.dosage = '',
    this.dosageForm = '',
    this.quantity = 0,
    this.note = '',
    this.normalizationStatus,
    this.needsReview = false,
  });

  final int id;
  final String drugName;
  final String normalizedName;
  final String brandName;
  final String manufacturer;
  final String dosage;
  final String dosageForm;
  final num quantity;
  final String note;
  final String? normalizationStatus;
  final bool needsReview;

  factory CabinetItem.fromJson(Map<String, dynamic> json) {
    final quantityRaw = json['quantity'];
    return CabinetItem(
      id: (json['id'] is num) ? (json['id'] as num).toInt() : 0,
      drugName: _str(json['drug_name']),
      normalizedName: _str(json['normalized_name']),
      brandName: _str(json['brand_name']),
      manufacturer: _str(json['manufacturer']),
      dosage: _str(json['dosage']),
      dosageForm: _str(json['dosage_form']),
      quantity: quantityRaw is num ? quantityRaw : 0,
      note: _str(json['note']),
      normalizationStatus: (json['normalization_status'] == null)
          ? null
          : _str(json['normalization_status']),
      needsReview: json['needs_review'] == true,
    );
  }

  /// Effective key used for distinct-medicine counting (two-medicine guard):
  /// the normalized name when present, else the lower-cased display name.
  String get distinctKey {
    final normalized = normalizedName.trim();
    if (normalized.isNotEmpty) return normalized.toLowerCase();
    return drugName.trim().toLowerCase();
  }
}

class CareguardCabinetScreen extends StatefulWidget {
  const CareguardCabinetScreen({
    super.key,
    required this.apiClient,
    required this.sessionStore,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  @override
  State<CareguardCabinetScreen> createState() => _CareguardCabinetScreenState();
}

class _CareguardCabinetScreenState extends State<CareguardCabinetScreen> {
  // Consent gate state (Requirement 8.5).
  bool _consentLoading = true;
  bool _consentAccepted = false;
  bool _consentChecked = false;
  bool _consentSaving = false;
  String _requiredVersion = '';
  String? _consentError;

  // Cabinet state.
  bool _cabinetLoading = false;
  String? _cabinetError;
  List<CabinetItem> _items = const [];

  // In-cabinet DDI check state.
  bool _ddiLoading = false;
  String? _ddiError;
  DdiUserView? _ddiView;

  @override
  void initState() {
    super.initState();
    getAnalyticsClient()
        .captureScreenView(MobileAnalyticsEvents.careguardCabinetViewed);
    _loadConsent();
  }

  String? get _token {
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) return null;
    return token;
  }

  // --- Consent (Req 8.5) ---------------------------------------------------

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
      setState(() => _consentError = 'Không thể kiểm tra điều khoản y tế. Vui lòng thử lại.');
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

  // --- Cabinet CRUD (Req 8.2) ----------------------------------------------

  Future<void> _loadCabinet() async {
    final token = _token;
    if (token == null) return;
    setState(() {
      _cabinetLoading = true;
      _cabinetError = null;
    });
    try {
      final data = await widget.apiClient.getCareguardCabinet(accessToken: token);
      final rawItems = data['items'];
      final items = <CabinetItem>[];
      if (rawItems is List) {
        for (final item in rawItems) {
          if (item is Map) {
            items.add(CabinetItem.fromJson(item.cast<String, dynamic>()));
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

  Future<void> _addOrEditItem({CabinetItem? existing}) async {
    final payload = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _CabinetItemEditor(existing: existing),
    );
    if (payload == null) return;
    final token = _token;
    if (token == null) return;

    try {
      if (existing == null) {
        await widget.apiClient
            .addCareguardCabinetItem(accessToken: token, payload: payload);
      } else {
        await widget.apiClient.updateCareguardCabinetItem(
          accessToken: token,
          itemId: existing.id,
          payload: payload,
        );
      }
      await _loadCabinet();
    } on ApiException catch (error) {
      if (!mounted) return;
      // Surface server-side validation/duplicate (409) messages inline.
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(error.message)));
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Không thể lưu thuốc. Vui lòng thử lại.')),
      );
    }
  }

  Future<void> _deleteItem(CabinetItem item) async {
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
    try {
      await widget.apiClient
          .deleteCareguardCabinetItem(accessToken: token, itemId: item.id);
      await _loadCabinet();
    } on ApiException catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(error.message)));
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Không thể xóa thuốc. Vui lòng thử lại.')),
      );
    }
  }

  // --- In-cabinet DDI check (Req 8.1, 8.4) ---------------------------------

  int get _distinctMedicineCount =>
      _items.map((item) => item.distinctKey).where((k) => k.isNotEmpty).toSet().length;

  Future<void> _runDdiCheck() async {
    final token = _token;
    if (token == null) return;

    // Two-medicine guard: do NOT call the analysis endpoint with fewer than
    // two distinct medicines; prompt the user instead (Requirement 8.1, 3.1).
    if (_distinctMedicineCount < _minimumDdiMedicines) {
      setState(() {
        _ddiView = null;
        _ddiError = 'Cần ít nhất 2 thuốc trong tủ để kiểm tra tương tác.';
      });
      return;
    }

    final medicines = _items
        .map((item) => item.drugName.trim())
        .where((name) => name.isNotEmpty)
        .toList();

    setState(() {
      _ddiLoading = true;
      _ddiError = null;
      _ddiView = null;
    });

    // Non-PII count only; the medicine list itself is never sent to analytics.
    getAnalyticsClient().capture(
      AnalyticsEvent(
        MobileAnalyticsEvents.careguardAnalyzed,
        {'medicine_count': _distinctMedicineCount},
      ),
    );

    try {
      final response = await widget.apiClient.analyzeCareguard(
        accessToken: token,
        payload: {
          'medications': medicines,
          'allergies': <String>[],
          'symptoms': <String>[],
          'labs': <String, dynamic>{},
        },
      );
      if (!mounted) return;
      setState(() => _ddiView = DdiUserView.fromPayload(response));
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _ddiError = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(() =>
          _ddiError = 'Không thể kiểm tra tương tác thuốc lúc này. Vui lòng thử lại.');
    } finally {
      if (mounted) {
        setState(() => _ddiLoading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Tủ thuốc')),
      floatingActionButton: (_consentAccepted)
          ? FloatingActionButton.extended(
              onPressed: () => _addOrEditItem(),
              icon: const Icon(Icons.add),
              label: const Text('Thêm thuốc'),
            )
          : null,
      body: _buildBody(context),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (_consentLoading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (!_consentAccepted) {
      return _ConsentGate(
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
    return RefreshIndicator(
      onRefresh: _loadCabinet,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
        children: [
          // Interaction check controls (two-medicine guard + projection).
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Kiểm tra tương tác trong tủ thuốc',
                      style: Theme.of(context).textTheme.titleSmall),
                  const SizedBox(height: 4),
                  Text(
                    'Cần ít nhất 2 thuốc khác nhau. Hiện có '
                    '$_distinctMedicineCount thuốc.',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  const SizedBox(height: 8),
                  FilledButton.icon(
                    onPressed: (_ddiLoading ||
                            _distinctMedicineCount < _minimumDdiMedicines)
                        ? null
                        : _runDdiCheck,
                    icon: _ddiLoading
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.medication),
                    label: const Text('Kiểm tra tương tác'),
                  ),
                  if (_ddiError != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 8),
                      child: Text(
                        _ddiError!,
                        style:
                            TextStyle(color: Theme.of(context).colorScheme.error),
                      ),
                    ),
                ],
              ),
            ),
          ),
          if (_ddiView != null) DdiResultView(view: _ddiView!),
          const SizedBox(height: 12),
          if (_cabinetLoading) const LinearProgressIndicator(),
          if (_cabinetError != null)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Text(
                _cabinetError!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ),
          if (!_cabinetLoading && _items.isEmpty && _cabinetError == null)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 24),
              child: Center(child: Text('Tủ thuốc trống. Thêm thuốc để bắt đầu.')),
            ),
          ..._items.map(_buildItemTile),
        ],
      ),
    );
  }

  Widget _buildItemTile(CabinetItem item) {
    final details = <String>[
      if (item.brandName.isNotEmpty) item.brandName,
      if (item.dosage.isNotEmpty) item.dosage,
      if (item.dosageForm.isNotEmpty) item.dosageForm,
      if (item.quantity > 0) 'SL: ${item.quantity}',
    ];
    return Card(
      child: ListTile(
        title: Text(item.drugName),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (details.isNotEmpty) Text(details.join(' • ')),
            if (item.needsReview)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  'Cần xem lại tên thuốc',
                  style: TextStyle(
                    color: Colors.orange.shade800,
                    fontWeight: FontWeight.w600,
                    fontSize: 12,
                  ),
                ),
              ),
          ],
        ),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            IconButton(
              icon: const Icon(Icons.edit),
              tooltip: 'Sửa',
              onPressed: () => _addOrEditItem(existing: item),
            ),
            IconButton(
              icon: const Icon(Icons.delete_outline),
              tooltip: 'Xóa',
              onPressed: () => _deleteItem(item),
            ),
          ],
        ),
      ),
    );
  }
}

/// Medical-disclaimer consent gate, mirroring the web `SelfMedConsentGate`
/// (Requirement 8.5). Blocks all cabinet/interaction features until the caller
/// accepts the required consent version.
class _ConsentGate extends StatelessWidget {
  const _ConsentGate({
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

/// Add / edit form for a cabinet item. Returns the create/update payload map
/// (matching `MedicineCabinetItemCreate` / `MedicineCabinetItemUpdate`) on save,
/// or `null` when cancelled.
class _CabinetItemEditor extends StatefulWidget {
  const _CabinetItemEditor({this.existing});

  final CabinetItem? existing;

  @override
  State<_CabinetItemEditor> createState() => _CabinetItemEditorState();
}

class _CabinetItemEditorState extends State<_CabinetItemEditor> {
  late final TextEditingController _drugName;
  late final TextEditingController _brandName;
  late final TextEditingController _manufacturer;
  late final TextEditingController _dosage;
  late final TextEditingController _dosageForm;
  late final TextEditingController _quantity;
  late final TextEditingController _note;
  String? _error;

  @override
  void initState() {
    super.initState();
    final e = widget.existing;
    _drugName = TextEditingController(text: e?.drugName ?? '');
    _brandName = TextEditingController(text: e?.brandName ?? '');
    _manufacturer = TextEditingController(text: e?.manufacturer ?? '');
    _dosage = TextEditingController(text: e?.dosage ?? '');
    _dosageForm = TextEditingController(text: e?.dosageForm ?? '');
    _quantity =
        TextEditingController(text: (e != null && e.quantity > 0) ? '${e.quantity}' : '');
    _note = TextEditingController(text: e?.note ?? '');
  }

  @override
  void dispose() {
    for (final c in [
      _drugName,
      _brandName,
      _manufacturer,
      _dosage,
      _dosageForm,
      _quantity,
      _note,
    ]) {
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

    Navigator.of(context).pop(<String, dynamic>{
      'drug_name': name,
      'brand_name': _brandName.text.trim(),
      'manufacturer': _manufacturer.text.trim(),
      'dosage': _dosage.text.trim(),
      'dosage_form': _dosageForm.text.trim(),
      'quantity': quantity,
      'note': _note.text.trim(),
    });
  }

  @override
  Widget build(BuildContext context) {
    final isEdit = widget.existing != null;
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
            Text(isEdit ? 'Sửa thuốc' : 'Thêm thuốc',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            _field(_drugName, 'Tên thuốc *'),
            _field(_brandName, 'Tên thương mại'),
            _field(_manufacturer, 'Nhà sản xuất'),
            _field(_dosage, 'Hàm lượng / liều'),
            _field(_dosageForm, 'Dạng bào chế'),
            _field(_quantity, 'Số lượng', keyboardType: TextInputType.number),
            _field(_note, 'Ghi chú', maxLines: 2),
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
                    child: Text(isEdit ? 'Lưu' : 'Thêm'),
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
    int maxLines = 1,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: TextField(
        controller: controller,
        keyboardType: keyboardType,
        maxLines: maxLines,
        decoration: InputDecoration(
          labelText: label,
          border: const OutlineInputBorder(),
          isDense: true,
        ),
      ),
    );
  }
}
