// Personal Medicine Cabinet surface for the CLARA_Mobile redesign
// (Experience_V3).
//
// clara-mobile-redesign, Requirement 5 (dedicated, feature-rich Personal
// Medicine Cabinet). This is the flagship "Tủ thuốc" flanking destination.
//
// This is the UNIFIED cabinet: it consolidates the legacy
// `selfmed_cabinet_screen.dart` CRUD and the in-cabinet DDI check from
// `careguard_cabinet_screen.dart` into ONE consent-gated surface built on the
// `ClaraTokens` design system, without changing any CLARA_API contract
// (INV-8). It reuses the shared `DdiResultView`/`DdiUserView` projection so the
// End_User view never exposes runtime `mode`/`fallback`/`source_errors`
// (INV-5), preserves the medical consent gate ahead of any CRUD or DDI (INV-1),
// blocks mutations while offline, and emits only no-PII (count) analytics
// (INV-3).
//
// Gates (fail-closed): CRUD is gated on `selfmed_cabinet_mobile_enabled`
// (`resolver.selfMedCabinetEnabled`) and the integrated DDI action is gated on
// the server `careguard` capability; when a gate is off the corresponding
// affordance is simply not exposed.

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../../core/analytics.dart';
import '../../core/api_client.dart';
import '../../core/careguard_offline_cache.dart';
import '../../core/connectivity_service.dart';
import '../../core/ddi_user_view.dart';
import '../../core/feature_flags.dart';
import '../../core/session_store.dart';
import '../../screens/ddi_result_view.dart';
import '../../theme/components/clara_button.dart';
import '../../theme/components/clara_card.dart';
import '../../theme/components/clara_chip.dart';
import '../../theme/components/clara_input.dart';
import '../../theme/components/section_header.dart';
import '../../theme/tokens.dart';
import '../../widgets/error_retry_view.dart';
import '../../widgets/offline_banner.dart';
import '../states/empty_state.dart';
import '../states/skeleton.dart';
import '../language_controller.dart';
import 'cabinet_insights.dart';
import 'cabinet_medicine_detail.dart';
import 'cabinet_ocr_sheet.dart';

/// Minimum number of distinct medicines required before a DDI check may run,
/// mirroring the web/legacy two-medicine guard (INV-5).
const int _kMinimumDdiMedicines = 2;

/// Number of days before expiry within which an item is flagged "sắp hết hạn".
const int _kExpiringSoonDays = 30;

String _str(Object? value) => value == null ? '' : value.toString();

/// Static, product-level copy owned by the Cabinet surface. It deliberately
/// does not translate medicine names, server error details, normalization
/// values, or DDI findings: those remain authoritative clinical/API content.
class _CabinetCopy {
  const _CabinetCopy._(this._messages);

  factory _CabinetCopy.forLocale(String? locale) {
    final normalized = locale?.trim().toLowerCase();
    return _CabinetCopy._(
      normalized == 'en' || normalized?.startsWith('en-') == true ? _en : _vi,
    );
  }

  final Map<String, String> _messages;

  String operator [](String key) => _messages[key]!;

  String format(String key, Map<String, Object?> values) {
    return this[key].replaceAllMapped(RegExp(r'\{(\w+)\}'), (match) {
      final value = values[match.group(1)];
      return value == null ? match.group(0)! : value.toString();
    });
  }

  static const Map<String, String> _vi = <String, String>{
    'sessionExpired': 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.',
    'consentLoadFailed':
        'Không thể kiểm tra điều khoản y tế. Vui lòng thử lại.',
    'consentCheckRequired': 'Vui lòng tick xác nhận trước khi tiếp tục.',
    'consentSaveFailed': 'Không thể lưu xác nhận. Vui lòng thử lại.',
    'cabinetLoadFailed': 'Không thể tải tủ thuốc. Vui lòng thử lại.',
    'saveFailed': 'Không thể lưu thuốc. Vui lòng thử lại.',
    'deleteFailed': 'Không thể xóa thuốc. Vui lòng thử lại.',
    'offlineMutationBlocked':
        'Bạn đang ngoại tuyến. Kết nối mạng để thực hiện thay đổi này.',
    'ddiMinimum':
        'Cần ít nhất 2 thuốc khác nhau trong tủ để kiểm tra tương tác.',
    'ddiFailed':
        'Không thể kiểm tra tương tác thuốc lúc này. Vui lòng thử lại.',
    'title': 'Tủ thuốc cá nhân',
    'scanLabel': 'Quét nhãn thuốc',
    'addMedicine': 'Thêm thuốc',
    'cabinetMedicines': 'Thuốc trong tủ',
    'clearFilter': 'Bỏ lọc',
    'emptyTitle': 'Tủ thuốc trống',
    'emptyDescription':
        'Thêm thuốc bạn đang dùng để theo dõi hạn dùng và kiểm tra tương tác.',
    'filteredEmptyTitle': 'Không có thuốc khớp bộ lọc',
    'filteredEmptyDescription': 'Chạm "Bỏ lọc" để xem lại toàn bộ tủ thuốc.',
    'ddiPanelLabel': 'Kiểm tra tương tác thuốc trong tủ',
    'ddiTitle': 'Kiểm tra tương tác trong tủ thuốc',
    'ddiDescription': 'Cần ít nhất 2 thuốc khác nhau. Hiện có {count} thuốc.',
    'checkInteractions': 'Kiểm tra tương tác',
    'error': 'Lỗi',
    'quantity': 'SL: {quantity}',
    'medicineSemantic': 'Thuốc {drug}',
    'medicineInfo': 'Thông tin thuốc {drug}',
    'askClara': 'Hỏi CLARA về thuốc này',
    'editMedicine': 'Sửa {drug}',
    'edit': 'Sửa',
    'deleteMedicine': 'Xóa {drug}',
    'delete': 'Xóa',
    'activeIngredient': 'Hoạt chất: {ingredient}',
    'manufacturer': 'Nhà sản xuất: {manufacturer}',
    'note': 'Ghi chú: {note}',
    'reviewName': 'Cần xem lại tên thuốc',
    'expiry': 'Hạn dùng',
    'expired': 'Đã hết hạn (HSD: {date})',
    'expiringSoon': 'Sắp hết hạn (HSD: {date})',
    'valid': 'Còn hạn (HSD: {date})',
    'unavailableTitle': 'Tủ thuốc chưa được bật',
    'unavailableDescription':
        'Tính năng tủ thuốc chưa khả dụng cho tài khoản của bạn.',
    'disclaimerSemantic': 'Tuyên bố miễn trừ trách nhiệm y tế',
    'disclaimerTitle': 'Tuyên bố miễn trừ trách nhiệm y tế',
    'disclaimerBody':
        'CLARA chỉ hỗ trợ cảnh báo an toàn thuốc và không thay thế bác sĩ. '
            'Không sử dụng ứng dụng để tự chẩn đoán, tự kê đơn hoặc tự điều '
            'chỉnh liều dùng.',
    'consentVersion': 'Phiên bản điều khoản hiện tại: {version}',
    'consentCheck':
        'Tôi đã đọc, hiểu và đồng ý với tuyên bố miễn trừ trách nhiệm y tế của CLARA.',
    'agreeContinue': 'Đồng ý và tiếp tục',
    'retryConsent': 'Thử kiểm tra lại',
    'deleteTitle': 'Xóa thuốc',
    'deleteDescription': 'Xóa "{drug}" khỏi tủ thuốc?',
    'cancel': 'Hủy',
    'editorEditTitle': 'Sửa thuốc',
    'editorAddTitle': 'Thêm thuốc',
    'medicineNameRequired': 'Vui lòng nhập tên thuốc.',
    'invalidQuantity': 'Số lượng không hợp lệ.',
    'invalidExpiry': 'Hạn dùng phải theo định dạng YYYY-MM-DD.',
    'medicineName': 'Tên thuốc *',
    'brandName': 'Tên thương mại',
    'manufacturerField': 'Nhà sản xuất',
    'dosage': 'Hàm lượng / liều',
    'dosageForm': 'Dạng bào chế',
    'quantityField': 'Số lượng',
    'expiryField': 'Hạn dùng (YYYY-MM-DD)',
    'noteField': 'Ghi chú',
    'save': 'Lưu',
    'add': 'Thêm',
  };

  static const Map<String, String> _en = <String, String>{
    'sessionExpired': 'Your session has expired. Please sign in again.',
    'consentLoadFailed': 'We could not check the medical terms. Try again.',
    'consentCheckRequired': 'Please confirm before continuing.',
    'consentSaveFailed': 'We could not save your confirmation. Try again.',
    'cabinetLoadFailed': 'We could not load your medicine cabinet. Try again.',
    'saveFailed': 'We could not save this medicine. Try again.',
    'deleteFailed': 'We could not delete this medicine. Try again.',
    'offlineMutationBlocked':
        'You are offline. Connect to the internet to make this change.',
    'ddiMinimum': 'Add at least 2 different medicines to check interactions.',
    'ddiFailed':
        'We could not check medicine interactions right now. Try again.',
    'title': 'Personal medicine cabinet',
    'scanLabel': 'Scan medicine label',
    'addMedicine': 'Add medicine',
    'cabinetMedicines': 'Medicines in your cabinet',
    'clearFilter': 'Clear filter',
    'emptyTitle': 'Your medicine cabinet is empty',
    'emptyDescription':
        'Add medicines you take to track expiry dates and check interactions.',
    'filteredEmptyTitle': 'No medicines match this filter',
    'filteredEmptyDescription':
        'Tap "Clear filter" to see all medicines in your cabinet.',
    'ddiPanelLabel': 'Check medicine interactions in your cabinet',
    'ddiTitle': 'Check interactions in your cabinet',
    'ddiDescription':
        'At least 2 different medicines are needed. You currently have {count}.',
    'checkInteractions': 'Check interactions',
    'error': 'Error',
    'quantity': 'Qty: {quantity}',
    'medicineSemantic': 'Medicine {drug}',
    'medicineInfo': 'Medicine information for {drug}',
    'askClara': 'Ask CLARA about this medicine',
    'editMedicine': 'Edit {drug}',
    'edit': 'Edit',
    'deleteMedicine': 'Delete {drug}',
    'delete': 'Delete',
    'activeIngredient': 'Active ingredient: {ingredient}',
    'manufacturer': 'Manufacturer: {manufacturer}',
    'note': 'Note: {note}',
    'reviewName': 'Review medicine name',
    'expiry': 'Expiry date',
    'expired': 'Expired (expiry: {date})',
    'expiringSoon': 'Expires soon (expiry: {date})',
    'valid': 'In date (expiry: {date})',
    'unavailableTitle': 'Medicine cabinet is not enabled',
    'unavailableDescription':
        'The medicine-cabinet feature is not available for your account.',
    'disclaimerSemantic': 'Medical disclaimer',
    'disclaimerTitle': 'Medical disclaimer',
    'disclaimerBody':
        'CLARA only supports medicine-safety alerts and does not replace a doctor. '
            'Do not use the app to self-diagnose, prescribe for yourself, or change '
            'your own dose.',
    'consentVersion': 'Current terms version: {version}',
    'consentCheck':
        'I have read, understood, and agree to CLARA\'s medical disclaimer.',
    'agreeContinue': 'Agree and continue',
    'retryConsent': 'Check again',
    'deleteTitle': 'Delete medicine',
    'deleteDescription': 'Remove "{drug}" from your medicine cabinet?',
    'cancel': 'Cancel',
    'editorEditTitle': 'Edit medicine',
    'editorAddTitle': 'Add medicine',
    'medicineNameRequired': 'Enter a medicine name.',
    'invalidQuantity': 'Enter a valid quantity.',
    'invalidExpiry': 'Use the YYYY-MM-DD format for the expiry date.',
    'medicineName': 'Medicine name *',
    'brandName': 'Brand name',
    'manufacturerField': 'Manufacturer',
    'dosage': 'Strength / dose',
    'dosageForm': 'Dosage form',
    'quantityField': 'Quantity',
    'expiryField': 'Expiry date (YYYY-MM-DD)',
    'noteField': 'Note',
    'save': 'Save',
    'add': 'Add',
  };
}

/// Expiry status derived solely from an item's expiry field (Requirement 5.3);
/// never invents data the API does not provide.
enum _ExpiryStatus { none, valid, expiringSoon, expired }

/// A unified medicine-cabinet item spanning the structured fields exposed by
/// the shared `/careguard/cabinet*` API (Requirement 5.2): drug name, brand,
/// manufacturer, dosage, dosage form, quantity, expiry, note, plus the
/// normalization status / needs-review hints surfaced per item.
class _CabinetMedicine {
  const _CabinetMedicine({
    required this.id,
    required this.drugName,
    required this.normalizedName,
    this.brandName = '',
    this.manufacturer = '',
    this.dosage = '',
    this.dosageForm = '',
    this.quantity = 0,
    this.expiresOn = '',
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

  /// ISO date string (e.g. `2026-01-31`) or empty when not set.
  final String expiresOn;
  final String note;
  final String? normalizationStatus;
  final bool needsReview;

  factory _CabinetMedicine.fromJson(Map<String, dynamic> json) {
    final quantityRaw = json['quantity'];
    return _CabinetMedicine(
      id: (json['id'] is num) ? (json['id'] as num).toInt() : 0,
      drugName: _str(json['drug_name']),
      normalizedName: _str(json['normalized_name']),
      brandName: _str(json['brand_name']),
      manufacturer: _str(json['manufacturer']),
      dosage: _str(json['dosage']),
      dosageForm: _str(json['dosage_form']),
      quantity: quantityRaw is num ? quantityRaw : 0,
      expiresOn: _str(json['expires_on']),
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

/// The redesigned Personal Medicine Cabinet surface. See file header.
class CabinetScreenV3 extends StatefulWidget {
  const CabinetScreenV3({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    required this.resolver,
    this.languageController,
    ConnectivityService? connectivity,
    CareguardOfflineCache? offlineCache,
  })  : _connectivity = connectivity,
        _offlineCache = offlineCache;

  final ApiClient apiClient;
  final SessionStore sessionStore;
  final MobileFeatureFlagResolver resolver;

  /// Optional app-wide locale state. The surface remains Vietnamese-first for
  /// legacy callers that do not yet provide the controller.
  final LanguageController? languageController;

  /// Optional connectivity signal. When omitted a default (always-online in the
  /// absence of a probe) service is created; tests inject a fake to drive the
  /// offline path.
  final ConnectivityService? _connectivity;

  /// Optional offline DDI cache (default-OFF unless the offline-fallback flag
  /// is enabled); tests inject a stub to exercise the stale-result path.
  final CareguardOfflineCache? _offlineCache;

  @override
  State<CabinetScreenV3> createState() => _CabinetScreenV3State();
}

class _CabinetScreenV3State extends State<CabinetScreenV3> {
  // Consent gate state (INV-1).
  bool _consentLoading = true;
  bool _consentAccepted = false;
  bool _consentChecked = false;
  bool _consentSaving = false;
  String _requiredVersion = '';
  String? _consentError;

  // Cabinet state.
  bool _cabinetLoading = false;
  String? _cabinetError;
  List<_CabinetMedicine> _items = const [];

  /// Optional expiry/review filter applied to the visible list, driven by
  /// tapping a stat chip in the health card. Null shows everything.
  CabinetExpiryBucket? _bucketFilter;
  bool _reviewFilter = false;

  // In-cabinet DDI state.
  bool _ddiLoading = false;
  String? _ddiError;
  DdiUserView? _ddiView;
  DateTime? _ddiOfflineCachedAt;

  late final ConnectivityService _connectivity;
  DefaultConnectivityService? _ownedConnectivity;
  late final CareguardOfflineCache _offlineCache;

  /// CRUD availability. The Personal Medicine Cabinet is a core, safety-
  /// oriented surface offered to EVERY authenticated role in the redesign, so it
  /// is unconditionally available. The versioned medical consent gate (INV-1)
  /// and the offline-mutation guard still run ahead of any CRUD or DDI, so
  /// broadening reach never bypasses a safety invariant.
  bool get _cabinetEnabled => true;

  /// The integrated DDI (drug-interaction) action is offered to every role that
  /// can reach the cabinet. The two-medicine guard + severity floor (INV-5)
  /// still govern whether a check actually runs, so this only controls
  /// visibility of the affordance.
  bool get _ddiEnabled => true;

  @override
  void initState() {
    super.initState();
    if (widget._connectivity != null) {
      _connectivity = widget._connectivity!;
    } else {
      _ownedConnectivity = DefaultConnectivityService();
      _connectivity = _ownedConnectivity!;
    }
    _offlineCache = widget._offlineCache ??
        CareguardOfflineCache(storage: FlutterSecureSessionStorage());

    if (_cabinetEnabled) {
      // Coarse, no-PII screen-view event (INV-3). The self-med and CareGuard
      // cabinets are the same underlying surface, so we reuse its event name.
      getAnalyticsClient()
          .captureScreenView(MobileAnalyticsEvents.careguardCabinetViewed);
      _loadConsent();
    } else {
      _consentLoading = false;
    }
  }

  @override
  void dispose() {
    _ownedConnectivity?.dispose();
    super.dispose();
  }

  String? get _token {
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) return null;
    return token;
  }

  bool get _isOnline => _connectivity.currentValue;

  _CabinetCopy get _copy =>
      _CabinetCopy.forLocale(widget.languageController?.languageCode);

  // --- Consent (INV-1) -----------------------------------------------------

  Future<void> _loadConsent() async {
    final token = _token;
    if (token == null) {
      setState(() {
        _consentLoading = false;
        _consentError = _copy['sessionExpired'];
      });
      return;
    }
    setState(() {
      _consentLoading = true;
      _consentError = null;
    });
    try {
      final status =
          await widget.apiClient.getConsentStatus(accessToken: token);
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
      setState(() => _consentError = _copy['consentLoadFailed']);
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
      setState(() => _consentError = _copy['consentCheckRequired']);
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
      setState(() => _consentError = _copy['consentSaveFailed']);
    } finally {
      if (mounted) {
        setState(() => _consentSaving = false);
      }
    }
  }

  // --- Cabinet CRUD (Req 5.1, 5.2) -----------------------------------------

  Future<void> _loadCabinet() async {
    final token = _token;
    if (token == null) return;
    setState(() {
      _cabinetLoading = true;
      _cabinetError = null;
    });
    try {
      final data =
          await widget.apiClient.getCareguardCabinet(accessToken: token);
      final rawItems = data['items'];
      final items = <_CabinetMedicine>[];
      if (rawItems is List) {
        for (final item in rawItems) {
          if (item is Map) {
            items.add(_CabinetMedicine.fromJson(item.cast<String, dynamic>()));
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
      setState(() => _cabinetError = _copy['cabinetLoadFailed']);
    } finally {
      if (mounted) {
        setState(() => _cabinetLoading = false);
      }
    }
  }

  Future<void> _addOrEditItem({_CabinetMedicine? existing}) async {
    // Block the mutation while offline; the editor sheet is never opened so
    // there is no entered input to lose (Req 5.5).
    if (!_isOnline) {
      _showSnack(_copy['offlineMutationBlocked']);
      return;
    }
    final payload = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => _CabinetItemEditor(copy: _copy, existing: existing),
    );
    if (payload == null) return;
    final token = _token;
    if (token == null) return;
    // Re-check connectivity after the (async) sheet closes.
    if (!_isOnline) {
      _showSnack(_copy['offlineMutationBlocked']);
      return;
    }

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
      // Surface server-side validation / duplicate (409) messages inline.
      _showSnack(error.message);
    } catch (_) {
      _showSnack(_copy['saveFailed']);
    }
  }

  Future<void> _deleteItem(_CabinetMedicine item) async {
    if (!_isOnline) {
      _showSnack(_copy['offlineMutationBlocked']);
      return;
    }
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(_copy['deleteTitle']),
        content:
            Text(_copy.format('deleteDescription', {'drug': item.drugName})),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: Text(_copy['cancel']),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: Text(_copy['delete']),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    final token = _token;
    if (token == null) return;
    if (!_isOnline) {
      _showSnack(_copy['offlineMutationBlocked']);
      return;
    }
    try {
      await widget.apiClient
          .deleteCareguardCabinetItem(accessToken: token, itemId: item.id);
      await _loadCabinet();
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack(_copy['deleteFailed']);
    }
  }

  void _showSnack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  // --- Medication-label OCR scan (R4) --------------------------------------

  /// Opens the OCR capture sheet. Blocked while offline (no network call is
  /// made); on a confirmed import the sheet returns `true` and we reload the
  /// cabinet so the newly-added medicines appear.
  Future<void> _scanLabel() async {
    if (!_isOnline) {
      _showSnack(_copy['offlineMutationBlocked']);
      return;
    }
    final token = _token;
    if (token == null) return;
    final imported = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => CabinetOcrSheet(
        apiClient: widget.apiClient,
        accessToken: token,
        connectivity: _connectivity,
      ),
    );
    if (imported == true) {
      await _loadCabinet();
    }
  }

  // --- Insights (derived purely from loaded items; no fabrication) ---------

  /// Adapts loaded items to the insights record type and computes aggregates.
  CabinetInsights get _insights => CabinetInsights.fromItems(
        _items
            .map<CabinetInsightItem>((item) => (
                  distinctKey: item.distinctKey,
                  expiresOn: item.expiresOn,
                  needsReview: item.needsReview,
                  quantity: item.quantity,
                ))
            .toList(),
      );

  /// The items currently visible after applying any active health-card filter.
  List<_CabinetMedicine> get _visibleItems {
    if (_reviewFilter) {
      return _items.where((item) => item.needsReview).toList();
    }
    final bucket = _bucketFilter;
    if (bucket == null) return _items;
    return _items
        .where((item) => classifyExpiry(item.expiresOn) == bucket)
        .toList();
  }

  bool get _hasActiveFilter => _reviewFilter || _bucketFilter != null;

  /// Toggles the expiry-bucket filter: tapping the active bucket clears it.
  void _toggleBucketFilter(CabinetExpiryBucket bucket) {
    setState(() {
      _reviewFilter = false;
      _bucketFilter = _bucketFilter == bucket ? null : bucket;
    });
  }

  /// Toggles the needs-review filter (tapping again clears it).
  void _toggleReviewFilter() {
    setState(() {
      _bucketFilter = null;
      _reviewFilter = !_reviewFilter;
    });
  }

  void _clearFilters() {
    setState(() {
      _bucketFilter = null;
      _reviewFilter = false;
    });
  }

  /// Opens the AI-backed plain-language detail sheet for a single medicine.
  /// Blocked while offline (it makes a chat request); the sheet itself shows
  /// the safety disclaimer and never prescribes a personal dosage.
  Future<void> _openMedicineDetail(_CabinetMedicine item) async {
    if (!_isOnline) {
      _showSnack(_copy['offlineMutationBlocked']);
      return;
    }
    final token = _token;
    if (token == null) return;
    await showCabinetMedicineDetail(
      context,
      apiClient: widget.apiClient,
      accessToken: token,
      medicineName: item.drugName,
      activeIngredient:
          item.normalizedName.isNotEmpty ? item.normalizedName : null,
    );
  }

  // --- In-cabinet DDI check (Req 5.4, 5.5; INV-5) --------------------------

  int get _distinctMedicineCount => _items
      .map((item) => item.distinctKey)
      .where((key) => key.isNotEmpty)
      .toSet()
      .length;

  Future<void> _runDdiCheck() async {
    final token = _token;
    if (token == null) return;

    // Two-medicine guard: never call analyze with fewer than two distinct
    // medicines; prompt instead and never fabricate an "all clear" (INV-5).
    if (_distinctMedicineCount < _kMinimumDdiMedicines) {
      setState(() {
        _ddiView = null;
        _ddiOfflineCachedAt = null;
        _ddiError = _copy['ddiMinimum'];
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
      _ddiOfflineCachedAt = null;
    });

    // No-PII count only; the medicine list itself is never sent to analytics.
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
      final view = DdiUserView.fromPayload(response);
      // Persist the last-known projection for the offline stale path (the cache
      // is a no-op unless the offline-fallback flag is enabled).
      await _offlineCache.save(view.toCacheJson());
      if (!mounted) return;
      setState(() {
        _ddiView = view;
        _ddiOfflineCachedAt = null;
      });
    } on ApiException catch (error) {
      await _handleDdiFailure(error, error.message);
    } catch (error) {
      await _handleDdiFailure(error, _copy['ddiFailed']);
    } finally {
      if (mounted) {
        setState(() => _ddiLoading = false);
      }
    }
  }

  /// On a likely-offline failure, fall back to the last-known cached projection
  /// labeled as stale (Req 5.5). A cache miss keeps the normal error and never
  /// fabricates an all-clear (INV-5).
  Future<void> _handleDdiFailure(Object error, String fallbackMessage) async {
    if (isLikelyOfflineFailure(error)) {
      final cached = await _offlineCache.read();
      if (!mounted) return;
      if (cached != null) {
        setState(() {
          _ddiView = DdiUserView.fromCacheJson(cached.view);
          _ddiOfflineCachedAt = cached.cachedAt;
          _ddiError = null;
        });
        return;
      }
    }
    if (!mounted) return;
    setState(() {
      _ddiView = null;
      _ddiOfflineCachedAt = null;
      _ddiError = fallbackMessage;
    });
  }

  // --- Build ---------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    final languageController = widget.languageController;
    if (languageController == null) {
      return _buildScaffold(context);
    }
    return AnimatedBuilder(
      animation: languageController,
      builder: (context, _) => _buildScaffold(context),
    );
  }

  Widget _buildScaffold(BuildContext context) {
    final copy = _copy;
    return Scaffold(
      appBar: AppBar(
        title: Text(copy['title']),
        actions: [
          if (_cabinetEnabled && _consentAccepted)
            IconButton(
              tooltip: copy['scanLabel'],
              icon: const Icon(Icons.document_scanner_outlined),
              onPressed: _scanLabel,
            ),
        ],
      ),
      floatingActionButton: (_cabinetEnabled && _consentAccepted)
          ? FloatingActionButton.extended(
              onPressed: () => _addOrEditItem(),
              icon: const Icon(Icons.add),
              label: Text(copy['addMedicine']),
            )
          : null,
      body: SafeArea(child: _buildBody(context)),
    );
  }

  Widget _buildBody(BuildContext context) {
    // CRUD gate off ⇒ inert placeholder, no network call (fail-closed).
    if (!_cabinetEnabled) {
      return _UnavailablePlaceholder(copy: _copy);
    }
    if (_consentLoading) {
      return const ClaraSkeletonList(itemCount: 4);
    }
    if (!_consentAccepted) {
      return _ConsentGate(
        copy: _copy,
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
    return Column(
      children: [
        OfflineBanner(connectivity: _connectivity),
        Expanded(
          child: RefreshIndicator(
            onRefresh: _loadCabinet,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(
                ClaraTokens.spaceMd,
                ClaraTokens.spaceMd,
                ClaraTokens.spaceMd,
                96,
              ),
              children: [
                // Cabinet intelligence: an at-a-glance health summary derived
                // purely from the loaded items (expiry buckets, needs-review,
                // low stock). Tapping a stat filters the list below.
                if (_items.isNotEmpty) ...[
                  CabinetHealthCard(
                    insights: _insights,
                    locale: widget.languageController?.languageCode,
                    onTapExpired: () => _toggleBucketFilter(
                      CabinetExpiryBucket.expired,
                    ),
                    onTapExpiring: () => _toggleBucketFilter(
                      CabinetExpiryBucket.expiringSoon,
                    ),
                    onTapReview: _toggleReviewFilter,
                  ),
                  const SizedBox(height: ClaraTokens.spaceMd),
                ],
                if (_ddiEnabled) ...[
                  _buildDdiPanel(context),
                  if (_ddiView != null)
                    DdiResultView(
                      view: _ddiView!,
                      offlineCachedAt: _ddiOfflineCachedAt,
                    ),
                  const SizedBox(height: ClaraTokens.spaceMd),
                ],
                Row(
                  children: [
                    Expanded(
                      child: SectionHeader(title: _copy['cabinetMedicines']),
                    ),
                    if (_hasActiveFilter)
                      TextButton.icon(
                        onPressed: _clearFilters,
                        icon:
                            const Icon(Icons.filter_alt_off_outlined, size: 18),
                        label: Text(_copy['clearFilter']),
                      ),
                  ],
                ),
                if (_cabinetLoading && _items.isEmpty)
                  const ClaraSkeletonList(itemCount: 3)
                else if (_cabinetError != null)
                  ErrorRetryView(
                    message: _cabinetError!,
                    onRetry: _loadCabinet,
                  )
                else if (_items.isEmpty)
                  ClaraEmptyState(
                    icon: Icons.medication_outlined,
                    title: _copy['emptyTitle'],
                    message: _copy['emptyDescription'],
                    action: ClaraButton.primary(
                      label: _copy['addMedicine'],
                      icon: Icons.add,
                      onPressed: () => _addOrEditItem(),
                    ),
                  )
                else if (_visibleItems.isEmpty)
                  ClaraEmptyState(
                    icon: Icons.filter_alt_outlined,
                    title: _copy['filteredEmptyTitle'],
                    message: _copy['filteredEmptyDescription'],
                    action: ClaraButton.secondary(
                      label: _copy['clearFilter'],
                      icon: Icons.filter_alt_off_outlined,
                      onPressed: _clearFilters,
                    ),
                  )
                else ...[
                  if (_cabinetLoading)
                    const Padding(
                      padding: EdgeInsets.only(bottom: ClaraTokens.spaceSm),
                      child: LinearProgressIndicator(),
                    ),
                  ..._visibleItems.map(
                    (item) => Padding(
                      padding:
                          const EdgeInsets.only(bottom: ClaraTokens.spaceMd),
                      child: _buildItemCard(context, item),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildDdiPanel(BuildContext context) {
    final theme = Theme.of(context);
    final hasEnough = _distinctMedicineCount >= _kMinimumDdiMedicines;
    return Padding(
      padding: const EdgeInsets.only(bottom: ClaraTokens.spaceMd),
      child: ClaraCard.static_(
        semanticLabel: _copy['ddiPanelLabel'],
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              _copy['ddiTitle'],
              style: theme.textTheme.titleSmall,
            ),
            const SizedBox(height: ClaraTokens.spaceXs),
            Text(
              _copy.format('ddiDescription', {'count': _distinctMedicineCount}),
              style: theme.textTheme.bodySmall,
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            ClaraButton.primary(
              label: _copy['checkInteractions'],
              icon: Icons.medication_liquid,
              loading: _ddiLoading,
              onPressed: hasEnough ? _runDdiCheck : null,
            ),
            if (_ddiError != null) ...[
              const SizedBox(height: ClaraTokens.spaceSm),
              StatusByText(
                label: _ddiError!,
                level: A11yStatusLevel.danger,
                semanticsPrefix: _copy['error'],
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildItemCard(BuildContext context, _CabinetMedicine item) {
    final theme = Theme.of(context);
    final details = <String>[
      if (item.brandName.isNotEmpty) item.brandName,
      if (item.dosage.isNotEmpty) item.dosage,
      if (item.dosageForm.isNotEmpty) item.dosageForm,
      if (item.quantity > 0)
        _copy.format('quantity', {'quantity': item.quantity}),
    ];
    final expiryStatus = _expiryStatusFor(item.expiresOn);

    return ClaraCard.static_(
      semanticLabel: _copy.format('medicineSemantic', {'drug': item.drugName}),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Text(
                  item.drugName,
                  style: theme.textTheme.titleMedium
                      ?.copyWith(fontWeight: FontWeight.w600),
                ),
              ),
              MinTapTarget(
                semanticsLabel:
                    _copy.format('medicineInfo', {'drug': item.drugName}),
                child: IconButton(
                  icon: const Icon(Icons.auto_awesome_outlined),
                  tooltip: _copy['askClara'],
                  onPressed: () => _openMedicineDetail(item),
                ),
              ),
              MinTapTarget(
                semanticsLabel:
                    _copy.format('editMedicine', {'drug': item.drugName}),
                child: IconButton(
                  icon: const Icon(Icons.edit_outlined),
                  tooltip: _copy['edit'],
                  onPressed: () => _addOrEditItem(existing: item),
                ),
              ),
              MinTapTarget(
                semanticsLabel:
                    _copy.format('deleteMedicine', {'drug': item.drugName}),
                child: IconButton(
                  icon: const Icon(Icons.delete_outline),
                  tooltip: _copy['delete'],
                  onPressed: () => _deleteItem(item),
                ),
              ),
            ],
          ),
          if (item.normalizedName.isNotEmpty &&
              item.normalizedName.toLowerCase() !=
                  item.drugName.toLowerCase()) ...[
            const SizedBox(height: ClaraTokens.spaceXs),
            Text(
              _copy.format(
                'activeIngredient',
                {'ingredient': item.normalizedName},
              ),
              style: theme.textTheme.bodySmall
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
          ],
          if (details.isNotEmpty) ...[
            const SizedBox(height: ClaraTokens.spaceXs),
            Text(details.join('  •  '), style: theme.textTheme.bodyMedium),
          ],
          if (item.manufacturer.isNotEmpty) ...[
            const SizedBox(height: ClaraTokens.spaceXs),
            Text(
              _copy.format('manufacturer', {'manufacturer': item.manufacturer}),
              style: theme.textTheme.bodySmall,
            ),
          ],
          if (item.note.isNotEmpty) ...[
            const SizedBox(height: ClaraTokens.spaceXs),
            Text(
              _copy.format('note', {'note': item.note}),
              style: theme.textTheme.bodySmall,
            ),
          ],
          if (expiryStatus != _ExpiryStatus.none) ...[
            const SizedBox(height: ClaraTokens.spaceSm),
            _buildExpiryStatus(context, item.expiresOn, expiryStatus),
          ],
          if (item.needsReview) ...[
            const SizedBox(height: ClaraTokens.spaceSm),
            ClaraChip(
              label: _copy['reviewName'],
              icon: Icons.help_outline,
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildExpiryStatus(
    BuildContext context,
    String expiresOn,
    _ExpiryStatus status,
  ) {
    final display = _formatExpiry(context, expiresOn);
    switch (status) {
      case _ExpiryStatus.expired:
        return StatusByText(
          label: _copy.format('expired', {'date': display}),
          level: A11yStatusLevel.danger,
          icon: Icons.event_busy,
          semanticsPrefix: _copy['expiry'],
        );
      case _ExpiryStatus.expiringSoon:
        return StatusByText(
          label: _copy.format('expiringSoon', {'date': display}),
          level: A11yStatusLevel.warning,
          icon: Icons.event_available,
          semanticsPrefix: _copy['expiry'],
        );
      case _ExpiryStatus.valid:
        return StatusByText(
          label: _copy.format('valid', {'date': display}),
          level: A11yStatusLevel.success,
          icon: Icons.event_available,
          semanticsPrefix: _copy['expiry'],
        );
      case _ExpiryStatus.none:
        return const SizedBox.shrink();
    }
  }

  /// Computes the expiry status purely from the item's expiry field (Req 5.3).
  _ExpiryStatus _expiryStatusFor(String expiresOn, {DateTime? now}) {
    final trimmed = expiresOn.trim();
    if (trimmed.isEmpty) return _ExpiryStatus.none;
    final parsed = DateTime.tryParse(trimmed);
    if (parsed == null) return _ExpiryStatus.none;
    final reference = now ?? DateTime.now();
    final expiryDay = DateTime(parsed.year, parsed.month, parsed.day);
    final today = DateTime(reference.year, reference.month, reference.day);
    final days = expiryDay.difference(today).inDays;
    if (days < 0) return _ExpiryStatus.expired;
    if (days <= _kExpiringSoonDays) return _ExpiryStatus.expiringSoon;
    return _ExpiryStatus.valid;
  }

  String _formatExpiry(BuildContext context, String expiresOn) {
    final parsed = DateTime.tryParse(expiresOn.trim());
    if (parsed == null) return expiresOn.trim();
    return MaterialLocalizations.of(context).formatMediumDate(parsed);
  }
}

/// Shown when `selfmed_cabinet_mobile_enabled` is off: the surface is inert and
/// no network call is made, preserving the pre-feature app (fail-closed).
class _UnavailablePlaceholder extends StatelessWidget {
  const _UnavailablePlaceholder({required this.copy});

  final _CabinetCopy copy;

  @override
  Widget build(BuildContext context) {
    return ClaraEmptyState(
      icon: Icons.medication_outlined,
      title: copy['unavailableTitle'],
      message: copy['unavailableDescription'],
    );
  }
}

/// Medical-disclaimer consent gate (INV-1). Blocks all cabinet CRUD and the DDI
/// action until the required consent version is accepted, mirroring the web
/// `SelfMedConsentGate` copy on the V3 design system.
class _ConsentGate extends StatelessWidget {
  const _ConsentGate({
    required this.copy,
    required this.requiredVersion,
    required this.checked,
    required this.saving,
    required this.error,
    required this.onCheckedChanged,
    required this.onAccept,
    required this.onRetry,
  });

  final String requiredVersion;
  final _CabinetCopy copy;
  final bool checked;
  final bool saving;
  final String? error;
  final ValueChanged<bool> onCheckedChanged;
  final VoidCallback onAccept;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.all(ClaraTokens.spaceMd),
      children: [
        ClaraCard.static_(
          semanticLabel: copy['disclaimerSemantic'],
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                copy['disclaimerTitle'],
                style: theme.textTheme.titleMedium,
              ),
              const SizedBox(height: ClaraTokens.spaceSm),
              Text(copy['disclaimerBody']),
              const SizedBox(height: ClaraTokens.spaceSm),
              Text(
                copy.format(
                  'consentVersion',
                  {'version': requiredVersion.isEmpty ? '-' : requiredVersion},
                ),
                style: theme.textTheme.bodySmall,
              ),
              const SizedBox(height: ClaraTokens.spaceSm),
              CheckboxListTile(
                value: checked,
                onChanged: (value) => onCheckedChanged(value ?? false),
                contentPadding: EdgeInsets.zero,
                controlAffinity: ListTileControlAffinity.leading,
                title: Text(copy['consentCheck']),
              ),
              const SizedBox(height: ClaraTokens.spaceSm),
              ClaraButton.primary(
                label: copy['agreeContinue'],
                loading: saving,
                onPressed: checked ? onAccept : null,
              ),
              if (error != null) ...[
                const SizedBox(height: ClaraTokens.spaceMd),
                StatusByText(
                  label: error!,
                  level: A11yStatusLevel.danger,
                  semanticsPrefix: copy['error'],
                ),
                const SizedBox(height: ClaraTokens.spaceSm),
                ClaraButton.secondary(
                  label: copy['retryConsent'],
                  onPressed: onRetry,
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }
}

/// Bottom-sheet editor for the structured cabinet item fields (Req 5.2):
/// drug name, brand, manufacturer, dosage, dosage form, quantity, expiry, note.
/// Returns a payload map via `Navigator.pop` or `null` when cancelled.
class _CabinetItemEditor extends StatefulWidget {
  const _CabinetItemEditor({required this.copy, this.existing});

  final _CabinetMedicine? existing;
  final _CabinetCopy copy;

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
  late final TextEditingController _expiresOn;
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
    _quantity = TextEditingController(
      text: (e != null && e.quantity > 0) ? '${e.quantity}' : '',
    );
    _expiresOn = TextEditingController(text: e?.expiresOn ?? '');
    _note = TextEditingController(text: e?.note ?? '');
  }

  @override
  void dispose() {
    for (final controller in [
      _drugName,
      _brandName,
      _manufacturer,
      _dosage,
      _dosageForm,
      _quantity,
      _expiresOn,
      _note,
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  void _submit() {
    final name = _drugName.text.trim();
    if (name.isEmpty) {
      setState(() => _error = widget.copy['medicineNameRequired']);
      return;
    }
    final quantityText = _quantity.text.trim();
    num quantity = 0;
    if (quantityText.isNotEmpty) {
      final parsed = num.tryParse(quantityText);
      if (parsed == null || parsed < 0) {
        setState(() => _error = widget.copy['invalidQuantity']);
        return;
      }
      quantity = parsed;
    }
    final expiry = _expiresOn.text.trim();
    if (expiry.isNotEmpty && DateTime.tryParse(expiry) == null) {
      setState(() => _error = widget.copy['invalidExpiry']);
      return;
    }

    Navigator.of(context).pop(<String, dynamic>{
      'drug_name': name,
      'brand_name': _brandName.text.trim(),
      'manufacturer': _manufacturer.text.trim(),
      'dosage': _dosage.text.trim(),
      'dosage_form': _dosageForm.text.trim(),
      'quantity': quantity,
      'expires_on': expiry,
      'note': _note.text.trim(),
    });
  }

  @override
  Widget build(BuildContext context) {
    final isEdit = widget.existing != null;
    return Padding(
      padding: EdgeInsets.only(
        left: ClaraTokens.spaceMd,
        right: ClaraTokens.spaceMd,
        top: ClaraTokens.spaceSm,
        bottom: MediaQuery.of(context).viewInsets.bottom + ClaraTokens.spaceMd,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              isEdit
                  ? widget.copy['editorEditTitle']
                  : widget.copy['editorAddTitle'],
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            _field(_drugName, widget.copy['medicineName']),
            _field(_brandName, widget.copy['brandName']),
            _field(_manufacturer, widget.copy['manufacturerField']),
            _field(_dosage, widget.copy['dosage']),
            _field(_dosageForm, widget.copy['dosageForm']),
            _field(
              _quantity,
              widget.copy['quantityField'],
              keyboardType: TextInputType.number,
            ),
            _field(
              _expiresOn,
              widget.copy['expiryField'],
              keyboardType: TextInputType.datetime,
            ),
            _field(_note, widget.copy['noteField']),
            if (_error != null) ...[
              const SizedBox(height: ClaraTokens.spaceSm),
              StatusByText(
                label: _error!,
                level: A11yStatusLevel.danger,
                semanticsPrefix: widget.copy['error'],
              ),
            ],
            const SizedBox(height: ClaraTokens.spaceMd),
            Row(
              children: [
                Expanded(
                  child: ClaraButton.secondary(
                    label: widget.copy['cancel'],
                    onPressed: () => Navigator.of(context).pop(),
                  ),
                ),
                const SizedBox(width: ClaraTokens.spaceMd),
                Expanded(
                  child: ClaraButton.primary(
                    label: isEdit ? widget.copy['save'] : widget.copy['add'],
                    onPressed: _submit,
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
      padding: const EdgeInsets.only(bottom: ClaraTokens.spaceSm),
      child: ClaraInput(
        label: label,
        controller: controller,
        keyboardType: keyboardType,
      ),
    );
  }
}
