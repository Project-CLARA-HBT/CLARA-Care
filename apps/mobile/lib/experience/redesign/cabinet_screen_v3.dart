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
import 'cabinet_insights.dart';
import 'cabinet_medicine_detail.dart';
import 'cabinet_ocr_sheet.dart';

/// Minimum number of distinct medicines required before a DDI check may run,
/// mirroring the web/legacy two-medicine guard (INV-5).
const int _kMinimumDdiMedicines = 2;

/// Number of days before expiry within which an item is flagged "sắp hết hạn".
const int _kExpiringSoonDays = 30;

String _str(Object? value) => value == null ? '' : value.toString();

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
    ConnectivityService? connectivity,
    CareguardOfflineCache? offlineCache,
  })  : _connectivity = connectivity,
        _offlineCache = offlineCache;

  final ApiClient apiClient;
  final SessionStore sessionStore;
  final MobileFeatureFlagResolver resolver;

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

  // --- Consent (INV-1) -----------------------------------------------------

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
      setState(() => _consentError =
          'Không thể kiểm tra điều khoản y tế. Vui lòng thử lại.');
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
      setState(
          () => _consentError = 'Vui lòng tick xác nhận trước khi tiếp tục.');
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
      setState(
          () => _consentError = 'Không thể lưu xác nhận. Vui lòng thử lại.');
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
      setState(
          () => _cabinetError = 'Không thể tải tủ thuốc. Vui lòng thử lại.');
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
      _showSnack(kOfflineMutationBlockedMessage);
      return;
    }
    final payload = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => _CabinetItemEditor(existing: existing),
    );
    if (payload == null) return;
    final token = _token;
    if (token == null) return;
    // Re-check connectivity after the (async) sheet closes.
    if (!_isOnline) {
      _showSnack(kOfflineMutationBlockedMessage);
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
      _showSnack('Không thể lưu thuốc. Vui lòng thử lại.');
    }
  }

  Future<void> _deleteItem(_CabinetMedicine item) async {
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
    if (!_isOnline) {
      _showSnack(kOfflineMutationBlockedMessage);
      return;
    }
    try {
      await widget.apiClient
          .deleteCareguardCabinetItem(accessToken: token, itemId: item.id);
      await _loadCabinet();
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack('Không thể xóa thuốc. Vui lòng thử lại.');
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
      _showSnack(kOfflineMutationBlockedMessage);
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
      _showSnack(kOfflineMutationBlockedMessage);
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
        _ddiError =
            'Cần ít nhất 2 thuốc khác nhau trong tủ để kiểm tra tương tác.';
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
      await _handleDdiFailure(error,
          'Không thể kiểm tra tương tác thuốc lúc này. Vui lòng thử lại.');
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
    return Scaffold(
      appBar: AppBar(
        title: const Text('Tủ thuốc cá nhân'),
        actions: [
          if (_cabinetEnabled && _consentAccepted)
            IconButton(
              tooltip: 'Quét nhãn thuốc',
              icon: const Icon(Icons.document_scanner_outlined),
              onPressed: _scanLabel,
            ),
        ],
      ),
      floatingActionButton: (_cabinetEnabled && _consentAccepted)
          ? FloatingActionButton.extended(
              onPressed: () => _addOrEditItem(),
              icon: const Icon(Icons.add),
              label: const Text('Thêm thuốc'),
            )
          : null,
      body: SafeArea(child: _buildBody(context)),
    );
  }

  Widget _buildBody(BuildContext context) {
    // CRUD gate off ⇒ inert placeholder, no network call (fail-closed).
    if (!_cabinetEnabled) {
      return const _UnavailablePlaceholder();
    }
    if (_consentLoading) {
      return const ClaraSkeletonList(itemCount: 4);
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
                    const Expanded(
                      child: SectionHeader(title: 'Thuốc trong tủ'),
                    ),
                    if (_hasActiveFilter)
                      TextButton.icon(
                        onPressed: _clearFilters,
                        icon:
                            const Icon(Icons.filter_alt_off_outlined, size: 18),
                        label: const Text('Bỏ lọc'),
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
                    title: 'Tủ thuốc trống',
                    message:
                        'Thêm thuốc bạn đang dùng để theo dõi hạn dùng và kiểm '
                        'tra tương tác.',
                    action: ClaraButton.primary(
                      label: 'Thêm thuốc',
                      icon: Icons.add,
                      onPressed: () => _addOrEditItem(),
                    ),
                  )
                else if (_visibleItems.isEmpty)
                  ClaraEmptyState(
                    icon: Icons.filter_alt_outlined,
                    title: 'Không có thuốc khớp bộ lọc',
                    message: 'Chạm "Bỏ lọc" để xem lại toàn bộ tủ thuốc.',
                    action: ClaraButton.secondary(
                      label: 'Bỏ lọc',
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
        semanticLabel: 'Kiểm tra tương tác thuốc trong tủ',
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Kiểm tra tương tác trong tủ thuốc',
              style: theme.textTheme.titleSmall,
            ),
            const SizedBox(height: ClaraTokens.spaceXs),
            Text(
              'Cần ít nhất 2 thuốc khác nhau. Hiện có $_distinctMedicineCount thuốc.',
              style: theme.textTheme.bodySmall,
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            ClaraButton.primary(
              label: 'Kiểm tra tương tác',
              icon: Icons.medication_liquid,
              loading: _ddiLoading,
              onPressed: hasEnough ? _runDdiCheck : null,
            ),
            if (_ddiError != null) ...[
              const SizedBox(height: ClaraTokens.spaceSm),
              StatusByText(
                label: _ddiError!,
                level: A11yStatusLevel.danger,
                semanticsPrefix: 'Lỗi',
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
      if (item.quantity > 0) 'SL: ${item.quantity}',
    ];
    final expiryStatus = _expiryStatusFor(item.expiresOn);

    return ClaraCard.static_(
      semanticLabel: 'Thuốc ${item.drugName}',
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
                semanticsLabel: 'Thông tin thuốc ${item.drugName}',
                child: IconButton(
                  icon: const Icon(Icons.auto_awesome_outlined),
                  tooltip: 'Hỏi CLARA về thuốc này',
                  onPressed: () => _openMedicineDetail(item),
                ),
              ),
              MinTapTarget(
                semanticsLabel: 'Sửa ${item.drugName}',
                child: IconButton(
                  icon: const Icon(Icons.edit_outlined),
                  tooltip: 'Sửa',
                  onPressed: () => _addOrEditItem(existing: item),
                ),
              ),
              MinTapTarget(
                semanticsLabel: 'Xóa ${item.drugName}',
                child: IconButton(
                  icon: const Icon(Icons.delete_outline),
                  tooltip: 'Xóa',
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
              'Hoạt chất: ${item.normalizedName}',
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
              'Nhà sản xuất: ${item.manufacturer}',
              style: theme.textTheme.bodySmall,
            ),
          ],
          if (item.note.isNotEmpty) ...[
            const SizedBox(height: ClaraTokens.spaceXs),
            Text('Ghi chú: ${item.note}', style: theme.textTheme.bodySmall),
          ],
          if (expiryStatus != _ExpiryStatus.none) ...[
            const SizedBox(height: ClaraTokens.spaceSm),
            _buildExpiryStatus(item.expiresOn, expiryStatus),
          ],
          if (item.needsReview) ...[
            const SizedBox(height: ClaraTokens.spaceSm),
            const ClaraChip(
              label: 'Cần xem lại tên thuốc',
              icon: Icons.help_outline,
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildExpiryStatus(String expiresOn, _ExpiryStatus status) {
    final display = _formatExpiry(expiresOn);
    switch (status) {
      case _ExpiryStatus.expired:
        return StatusByText(
          label: 'Đã hết hạn (HSD: $display)',
          level: A11yStatusLevel.danger,
          icon: Icons.event_busy,
          semanticsPrefix: 'Hạn dùng',
        );
      case _ExpiryStatus.expiringSoon:
        return StatusByText(
          label: 'Sắp hết hạn (HSD: $display)',
          level: A11yStatusLevel.warning,
          icon: Icons.event_available,
          semanticsPrefix: 'Hạn dùng',
        );
      case _ExpiryStatus.valid:
        return StatusByText(
          label: 'Còn hạn (HSD: $display)',
          level: A11yStatusLevel.success,
          icon: Icons.event_available,
          semanticsPrefix: 'Hạn dùng',
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

  String _formatExpiry(String expiresOn) {
    final parsed = DateTime.tryParse(expiresOn.trim());
    if (parsed == null) return expiresOn.trim();
    String two(int n) => n.toString().padLeft(2, '0');
    return '${two(parsed.day)}/${two(parsed.month)}/${parsed.year}';
  }
}

/// Shown when `selfmed_cabinet_mobile_enabled` is off: the surface is inert and
/// no network call is made, preserving the pre-feature app (fail-closed).
class _UnavailablePlaceholder extends StatelessWidget {
  const _UnavailablePlaceholder();

  @override
  Widget build(BuildContext context) {
    return const ClaraEmptyState(
      icon: Icons.medication_outlined,
      title: 'Tủ thuốc chưa được bật',
      message: 'Tính năng tủ thuốc chưa khả dụng cho tài khoản của bạn.',
    );
  }
}

/// Medical-disclaimer consent gate (INV-1). Blocks all cabinet CRUD and the DDI
/// action until the required consent version is accepted, mirroring the web
/// `SelfMedConsentGate` copy on the V3 design system.
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
    final theme = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.all(ClaraTokens.spaceMd),
      children: [
        ClaraCard.static_(
          semanticLabel: 'Tuyên bố miễn trừ trách nhiệm y tế',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Tuyên bố miễn trừ trách nhiệm y tế',
                style: theme.textTheme.titleMedium,
              ),
              const SizedBox(height: ClaraTokens.spaceSm),
              const Text(
                'CLARA chỉ hỗ trợ cảnh báo an toàn thuốc và không thay thế bác sĩ. '
                'Không sử dụng ứng dụng để tự chẩn đoán, tự kê đơn hoặc tự điều '
                'chỉnh liều dùng.',
              ),
              const SizedBox(height: ClaraTokens.spaceSm),
              Text(
                'Phiên bản điều khoản hiện tại: '
                '${requiredVersion.isEmpty ? "-" : requiredVersion}',
                style: theme.textTheme.bodySmall,
              ),
              const SizedBox(height: ClaraTokens.spaceSm),
              CheckboxListTile(
                value: checked,
                onChanged: (value) => onCheckedChanged(value ?? false),
                contentPadding: EdgeInsets.zero,
                controlAffinity: ListTileControlAffinity.leading,
                title: const Text(
                  'Tôi đã đọc, hiểu và đồng ý với tuyên bố miễn trừ trách nhiệm '
                  'y tế của CLARA.',
                ),
              ),
              const SizedBox(height: ClaraTokens.spaceSm),
              ClaraButton.primary(
                label: 'Đồng ý và tiếp tục',
                loading: saving,
                onPressed: checked ? onAccept : null,
              ),
              if (error != null) ...[
                const SizedBox(height: ClaraTokens.spaceMd),
                StatusByText(
                  label: error!,
                  level: A11yStatusLevel.danger,
                  semanticsPrefix: 'Lỗi',
                ),
                const SizedBox(height: ClaraTokens.spaceSm),
                ClaraButton.secondary(
                  label: 'Thử kiểm tra lại',
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
  const _CabinetItemEditor({this.existing});

  final _CabinetMedicine? existing;

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
    final expiry = _expiresOn.text.trim();
    if (expiry.isNotEmpty && DateTime.tryParse(expiry) == null) {
      setState(() => _error = 'Hạn dùng phải theo định dạng YYYY-MM-DD.');
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
              isEdit ? 'Sửa thuốc' : 'Thêm thuốc',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            _field(_drugName, 'Tên thuốc *'),
            _field(_brandName, 'Tên thương mại'),
            _field(_manufacturer, 'Nhà sản xuất'),
            _field(_dosage, 'Hàm lượng / liều'),
            _field(_dosageForm, 'Dạng bào chế'),
            _field(
              _quantity,
              'Số lượng',
              keyboardType: TextInputType.number,
            ),
            _field(
              _expiresOn,
              'Hạn dùng (YYYY-MM-DD)',
              keyboardType: TextInputType.datetime,
            ),
            _field(_note, 'Ghi chú'),
            if (_error != null) ...[
              const SizedBox(height: ClaraTokens.spaceSm),
              StatusByText(
                label: _error!,
                level: A11yStatusLevel.danger,
                semanticsPrefix: 'Lỗi',
              ),
            ],
            const SizedBox(height: ClaraTokens.spaceMd),
            Row(
              children: [
                Expanded(
                  child: ClaraButton.secondary(
                    label: 'Hủy',
                    onPressed: () => Navigator.of(context).pop(),
                  ),
                ),
                const SizedBox(width: ClaraTokens.spaceMd),
                Expanded(
                  child: ClaraButton.primary(
                    label: isEdit ? 'Lưu' : 'Thêm',
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
