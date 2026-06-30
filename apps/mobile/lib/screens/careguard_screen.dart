import 'package:flutter/material.dart';

import '../core/analytics.dart';
import '../core/api_client.dart';
import '../core/careguard_offline_cache.dart';
import '../core/ddi_user_view.dart';
import '../core/session_store.dart';
import 'ddi_result_view.dart';

/// Minimum number of distinct medicines required before a DDI check may run,
/// mirroring the web two-medicine guard (Requirement 3.5).
const int _minimumDdiMedicines = 2;

class CareguardScreen extends StatefulWidget {
  const CareguardScreen({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    this.offlineFallbackEnabled = kCareguardOfflineFallbackEnabled,
    this.offlineStorage,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  /// Client-readable gate (`CAREGUARD_OFFLINE_FALLBACK_ENABLED`). When false the
  /// last-known DDI caching/labeling is fully inert and behavior is unchanged
  /// (Requirement 6.3, 12.1).
  final bool offlineFallbackEnabled;

  /// Storage backing the offline cache. Defaults to platform secure storage;
  /// tests inject an in-memory double.
  final SessionSecureStorage? offlineStorage;

  @override
  State<CareguardScreen> createState() => _CareguardScreenState();
}

class _CareguardScreenState extends State<CareguardScreen> {
  final _medicinesController = TextEditingController();
  final _allergiesController = TextEditingController();

  bool _isLoading = false;
  String? _error;
  DdiUserView? _view;
  // Offline / last-known fallback state (Req 6.3): set when the on-screen result
  // was served from the device cache because the API was unreachable.
  DateTime? _offlineCachedAt;
  late final CareguardOfflineCache _offlineCache;

  @override
  void initState() {
    super.initState();
    _offlineCache = CareguardOfflineCache(
      storage: widget.offlineStorage ?? FlutterSecureSessionStorage(),
      enabled: widget.offlineFallbackEnabled,
    );
    getAnalyticsClient()
        .captureScreenView(MobileAnalyticsEvents.careguardViewed);
  }

  @override
  void dispose() {
    _medicinesController.dispose();
    _allergiesController.dispose();
    super.dispose();
  }

  /// Split a free-text field into a trimmed, non-empty list (newline/comma).
  List<String> _parseList(String value) {
    return value
        .split(RegExp(r'[\n,]'))
        .map((item) => item.trim())
        .where((item) => item.isNotEmpty)
        .toList();
  }

  /// Count distinct, case-insensitive medicine names.
  int _countDistinct(List<String> medicines) {
    return medicines.map((m) => m.toLowerCase()).toSet().length;
  }

  Future<void> _submit() async {
    final medicines = _parseList(_medicinesController.text);
    final token = widget.sessionStore.accessToken;

    // Two-medicine guard: do NOT call the analysis endpoint with fewer than
    // two distinct medicines; prompt the user instead (Requirement 3.5).
    if (_countDistinct(medicines) < _minimumDdiMedicines) {
      setState(() {
        _view = null;
        _error = 'Cần ít nhất 2 thuốc để kiểm tra tương tác.';
      });
      return;
    }

    if (token == null || token.isEmpty) {
      setState(() {
        _error = 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.';
      });
      return;
    }

    setState(() {
      _isLoading = true;
      _error = null;
      _view = null;
      _offlineCachedAt = null;
    });

    // Named product event for a DDI analysis. Only a non-PII count is attached;
    // the medicine list itself is never transmitted (stripped by the client).
    getAnalyticsClient().capture(
      AnalyticsEvent(
        MobileAnalyticsEvents.careguardAnalyzed,
        {'medicine_count': _countDistinct(medicines)},
      ),
    );

    try {
      final response = await widget.apiClient.analyzeCareguard(
        accessToken: token,
        payload: {
          'medications': medicines,
          'allergies': _parseList(_allergiesController.text),
          'symptoms': <String>[],
          'labs': <String, dynamic>{},
        },
      );

      if (!mounted) {
        return;
      }

      final view = DdiUserView.fromPayload(response);
      if (!mounted) {
        return;
      }
      setState(() {
        _view = view;
        _offlineCachedAt = null;
      });
      // Cache the last-known *projection* for offline fallback (Req 6.3).
      // No-op when CAREGUARD_OFFLINE_FALLBACK_ENABLED is off. Best-effort: a
      // storage write failure must never hijack a fresh, successful result.
      try {
        await _offlineCache.save(view.toCacheJson());
      } catch (_) {
        // Ignore cache-write failures; the fresh result is already shown.
      }
    } on ApiException catch (error) {
      if (await _tryServeOffline(error)) {
        return;
      }
      if (!mounted) {
        return;
      }
      setState(() {
        _error = error.message;
      });
    } catch (failure) {
      if (await _tryServeOffline(failure)) {
        return;
      }
      if (!mounted) {
        return;
      }
      setState(() {
        _error = 'Không thể kiểm tra tương tác thuốc lúc này. Vui lòng thử lại.';
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  /// Offline / degraded fallback (Req 6.3): when the flag is on and the failure
  /// looks like the device could not reach the API, show the last-known cached
  /// projection labeled stale. Returns true when a cached result was served.
  /// Never fabricates an all-clear — only a genuine cached result is shown.
  Future<bool> _tryServeOffline(Object failure) async {
    if (!_offlineCache.enabled || !isLikelyOfflineFailure(failure)) {
      return false;
    }
    final cached = await _offlineCache.read();
    if (cached == null || !mounted) {
      return false;
    }
    setState(() {
      _view = DdiUserView.fromCacheJson(cached.view);
      _offlineCachedAt = cached.cachedAt;
      _error = null;
      _isLoading = false;
    });
    return true;
  }

  @override
  Widget build(BuildContext context) {
    final view = _view;

    return Scaffold(
      appBar: AppBar(title: const Text('Kiểm tra tương tác thuốc')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            controller: _medicinesController,
            minLines: 3,
            maxLines: 6,
            enabled: !_isLoading,
            decoration: const InputDecoration(
              labelText: 'Danh sách thuốc',
              border: OutlineInputBorder(),
              hintText: 'Mỗi dòng một thuốc (ví dụ: Warfarin\nIbuprofen)',
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _allergiesController,
            minLines: 1,
            maxLines: 3,
            enabled: !_isLoading,
            decoration: const InputDecoration(
              labelText: 'Dị ứng (không bắt buộc)',
              border: OutlineInputBorder(),
              hintText: 'Mỗi dòng một dị ứng hoặc phân tách bằng dấu phẩy',
            ),
          ),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: _isLoading ? null : _submit,
            child: _isLoading
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Kiểm tra tương tác thuốc'),
          ),
          const SizedBox(height: 12),
          if (_error != null)
            Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          if (view != null) DdiResultView(view: view, offlineCachedAt: _offlineCachedAt),
        ],
      ),
    );
  }
}
