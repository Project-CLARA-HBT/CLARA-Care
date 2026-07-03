// Medication-label OCR capture sheet for the CLARA_Mobile redesign
// (clara-mobile-liquid-glass, Task 4.2 — R4).
//
// A modal bottom sheet that runs the 3-phase CareGuard OCR flow:
//
//   1. Capture — pick a photo of a medication label (camera or gallery) and
//      send its raw bytes to the server for OCR extraction. No OCR runs
//      client-side.
//   2. Review — render each server detection on an OPAQUE (`clinical: true`)
//      glass card with a color-independent confidence indicator and a
//      confirm/include checkbox. High-confidence detections start checked;
//      low-confidence / manual-confirm detections start UNCHECKED so the user
//      must opt in (mirroring the server-side manual-confirm gate, R4.4).
//   3. Import — send only the checked detections (each carrying
//      `confirmed: true`) to the cabinet, then pop `true` so the caller can
//      reload.
//
// Safety-first invariants preserved here: the manual-confirm gate is honoured
// client-side (a checked low-confidence row IS its confirmation), mutations are
// blocked while offline with the shared offline message, and analytics carry
// only a coarse no-PII detection count — never drug names or extracted text.

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../../core/a11y.dart';
import '../../core/analytics.dart';
import '../../core/api_client.dart';
import '../../core/connectivity_service.dart';
import '../../theme/components/clara_button.dart';
import '../../theme/glass/glass_surface.dart';
import '../../theme/glass/glass_tokens.dart';
import '../../theme/tokens.dart';
import '../../widgets/offline_banner.dart';

/// The default confidence threshold used to classify a detection when the
/// server envelope omits `confirm_gate.threshold`.
const double _kDefaultConfirmThreshold = 0.6;

/// Coarse, no-PII analytics event fired once per successful scan (R4, INV-3).
const String _kOcrScannedEvent = 'mobile_careguard_ocr_scanned';

String _str(Object? value) => value is String ? value : '';

double? _asDouble(Object? value) {
  if (value is num) return value.toDouble();
  if (value is String) return double.tryParse(value);
  return null;
}

/// The phase the sheet is currently in.
enum _OcrPhase { capture, review }

/// A single server detection paired with its local include/confirm state.
class _ReviewDetection {
  _ReviewDetection({
    required this.raw,
    required this.checked,
  });

  /// The original server detection map (`CabinetScanDetection` shape).
  final Map<String, dynamic> raw;

  /// Whether the user has opted to include (and thereby confirm) this row.
  bool checked;

  String get drugName => _str(raw['drug_name']);
  String get dosage => _str(raw['dosage']);
  String get brandName => _str(raw['brand_name']);
  String get manufacturer => _str(raw['manufacturer']);
  double get confidence => _asDouble(raw['confidence']) ?? 0.0;
  bool get requiresManualConfirm => raw['requires_manual_confirm'] == true;
}

/// A modal bottom sheet driving the medication-label OCR capture flow.
///
/// Pop value semantics: pops `true` when at least one detection was imported
/// (so the caller reloads the cabinet), otherwise `null`/`false`.
class CabinetOcrSheet extends StatefulWidget {
  const CabinetOcrSheet({
    super.key,
    required this.apiClient,
    required this.accessToken,
    required this.connectivity,
    @visibleForTesting ImagePicker? imagePicker,
  }) : _imagePicker = imagePicker;

  final ApiClient apiClient;
  final String accessToken;
  final ConnectivityService connectivity;

  /// Injectable picker for tests; production uses a default [ImagePicker].
  final ImagePicker? _imagePicker;

  @override
  State<CabinetOcrSheet> createState() => _CabinetOcrSheetState();
}

class _CabinetOcrSheetState extends State<CabinetOcrSheet> {
  late final ImagePicker _picker = widget._imagePicker ?? ImagePicker();

  _OcrPhase _phase = _OcrPhase.capture;
  bool _scanning = false;
  bool _importing = false;
  String? _error;

  List<_ReviewDetection> _detections = const [];
  String _extractedText = '';
  double _threshold = _kDefaultConfirmThreshold;
  bool _showExtractedText = false;

  bool get _isOnline => widget.connectivity.currentValue;

  // --- Capture (R4.1) -------------------------------------------------------

  Future<void> _capture(ImageSource source) async {
    if (!_isOnline) {
      _showSnack(kOfflineMutationBlockedMessage);
      return;
    }
    final XFile? file = await _picker.pickImage(source: source);
    if (file == null) return; // User cancelled — no state change.
    // Re-check connectivity after the (async) picker closes.
    if (!_isOnline) {
      _showSnack(kOfflineMutationBlockedMessage);
      return;
    }
    if (!mounted) return;
    setState(() {
      _scanning = true;
      _error = null;
    });
    try {
      final bytes = await file.readAsBytes();
      final envelope = await widget.apiClient.scanCareguardCabinetFile(
        accessToken: widget.accessToken,
        fileBytes: bytes,
        filename: file.name,
      );
      if (!mounted) return;
      _applyScanResult(envelope);
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _error = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = 'Không thể quét nhãn thuốc. Vui lòng thử lại.');
    } finally {
      if (mounted) {
        setState(() => _scanning = false);
      }
    }
  }

  void _applyScanResult(Map<String, dynamic> envelope) {
    final gate = envelope['confirm_gate'];
    final threshold = gate is Map
        ? (_asDouble(gate['threshold']) ?? _kDefaultConfirmThreshold)
        : _kDefaultConfirmThreshold;

    final rawDetections = envelope['detections'];
    final detections = <_ReviewDetection>[];
    if (rawDetections is List) {
      for (final entry in rawDetections) {
        if (entry is Map) {
          final map = entry.cast<String, dynamic>();
          final confidence = _asDouble(map['confidence']) ?? 0.0;
          final needsConfirm =
              map['requires_manual_confirm'] == true || confidence < threshold;
          detections.add(
            _ReviewDetection(
              raw: map,
              // High-confidence rows start checked; low-confidence /
              // manual-confirm rows start UNCHECKED so the user opts in (R4.4).
              checked: !needsConfirm,
            ),
          );
        }
      }
    }

    // Coarse, no-PII analytics: only the count of detections (INV-3).
    getAnalyticsClient().capture(
      AnalyticsEvent(_kOcrScannedEvent, {'detection_count': detections.length}),
    );

    setState(() {
      _threshold = threshold;
      _detections = detections;
      _extractedText = _str(envelope['extracted_text']);
      _phase = _OcrPhase.review;
    });
  }

  // --- Import (R4.4) --------------------------------------------------------

  /// The confirm-gate is satisfied when at least one row is checked. A checked
  /// low-confidence row counts as its explicit confirmation, so any checked set
  /// is importable; the guard simply requires a non-empty selection.
  bool get _canImport =>
      !_importing && _detections.any((detection) => detection.checked);

  Future<void> _import() async {
    if (!_isOnline) {
      _showSnack(kOfflineMutationBlockedMessage);
      return;
    }
    final selected =
        _detections.where((detection) => detection.checked).toList();
    if (selected.isEmpty) return;

    final payload = selected.map((detection) {
      // Send the original detection fields plus an explicit confirmation so the
      // server-side manual-confirm gate accepts low-confidence rows (R4.4).
      return <String, dynamic>{
        ...detection.raw,
        'confirmed': true,
        'requires_manual_confirm': false,
      };
    }).toList();

    setState(() {
      _importing = true;
      _error = null;
    });
    try {
      final result = await widget.apiClient.importCareguardDetections(
        accessToken: widget.accessToken,
        detections: payload,
      );
      if (!mounted) return;
      final inserted =
          (_asDouble(result['inserted']) ?? selected.length).round();
      _showSnack('Đã thêm $inserted thuốc vào tủ thuốc.');
      Navigator.of(context).pop(true);
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _importing = false;
        _error = error.message;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _importing = false;
        _error = 'Không thể thêm thuốc vào tủ. Vui lòng thử lại.';
      });
    }
  }

  void _showSnack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  // --- Build ----------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    final viewInsets = MediaQuery.of(context).viewInsets.bottom;
    return Padding(
      padding: EdgeInsets.only(bottom: viewInsets),
      child: SafeArea(
        top: false,
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxHeight: MediaQuery.of(context).size.height * 0.9,
          ),
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(ClaraTokens.spaceMd),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              mainAxisSize: MainAxisSize.min,
              children: [
                _header(context),
                const SizedBox(height: ClaraTokens.spaceMd),
                if (_error != null) ...[
                  StatusByText(
                    label: _error!,
                    level: A11yStatusLevel.danger,
                    semanticsPrefix: 'Lỗi',
                  ),
                  const SizedBox(height: ClaraTokens.spaceMd),
                ],
                if (_phase == _OcrPhase.capture)
                  _buildCapture(context)
                else
                  _buildReview(context),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _header(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      children: [
        Expanded(
          child: Text(
            'Quét nhãn thuốc',
            style: theme.textTheme.titleLarge,
          ),
        ),
        IconButton(
          tooltip: 'Đóng',
          onPressed: () => Navigator.of(context).maybePop(),
          icon: const Icon(Icons.close),
        ),
      ],
    );
  }

  // --- Phase 1: capture -----------------------------------------------------

  Widget _buildCapture(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Chụp hoặc chọn ảnh nhãn thuốc để CLARA nhận dạng tên thuốc và liều '
          'lượng. Bạn sẽ xác nhận thông tin trước khi thêm vào tủ thuốc.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        const SizedBox(height: ClaraTokens.spaceLg),
        ClaraButton.primary(
          label: 'Chụp ảnh nhãn thuốc',
          icon: Icons.photo_camera_outlined,
          loading: _scanning,
          onPressed: _scanning ? null : () => _capture(ImageSource.camera),
        ),
        const SizedBox(height: ClaraTokens.spaceMd),
        ClaraButton.secondary(
          label: 'Chọn từ thư viện',
          icon: Icons.photo_library_outlined,
          onPressed: _scanning ? null : () => _capture(ImageSource.gallery),
        ),
        if (_scanning) ...[
          const SizedBox(height: ClaraTokens.spaceMd),
          Text(
            'Đang nhận dạng nhãn thuốc…',
            style: Theme.of(context).textTheme.bodySmall,
            textAlign: TextAlign.center,
          ),
        ],
      ],
    );
  }

  // --- Phase 2: review + Phase 3: import ------------------------------------

  Widget _buildReview(BuildContext context) {
    if (_detections.isEmpty) {
      return _buildEmptyReview(context);
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Kiểm tra thông tin nhận dạng, tick chọn các thuốc muốn thêm rồi nhấn '
          '"Thêm vào tủ thuốc". Các mục có độ tin cậy thấp cần bạn xác nhận thủ '
          'công trước khi thêm.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        const SizedBox(height: ClaraTokens.spaceMd),
        for (final detection in _detections) ...[
          _buildDetectionCard(context, detection),
          const SizedBox(height: ClaraTokens.spaceSm),
        ],
        if (_extractedText.isNotEmpty) ...[
          const SizedBox(height: ClaraTokens.spaceXs),
          _buildExtractedText(context),
        ],
        const SizedBox(height: ClaraTokens.spaceLg),
        ClaraButton.primary(
          label: 'Thêm vào tủ thuốc',
          icon: Icons.add,
          loading: _importing,
          onPressed: _canImport ? _import : null,
        ),
        const SizedBox(height: ClaraTokens.spaceSm),
        ClaraButton.secondary(
          label: 'Chụp lại',
          icon: Icons.refresh,
          onPressed: _importing
              ? null
              : () => setState(() {
                    _phase = _OcrPhase.capture;
                    _detections = const [];
                    _extractedText = '';
                    _error = null;
                  }),
        ),
      ],
    );
  }

  Widget _buildEmptyReview(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        StatusByText(
          label: 'Không nhận được thông tin thuốc từ ảnh. Thử chụp lại rõ hơn.',
          level: A11yStatusLevel.warning,
          semanticsPrefix: 'Trạng thái',
        ),
        const SizedBox(height: ClaraTokens.spaceLg),
        ClaraButton.primary(
          label: 'Chụp lại',
          icon: Icons.photo_camera_outlined,
          onPressed: () => setState(() {
            _phase = _OcrPhase.capture;
            _error = null;
          }),
        ),
      ],
    );
  }

  Widget _buildDetectionCard(
    BuildContext context,
    _ReviewDetection detection,
  ) {
    final theme = Theme.of(context);
    final highConfidence = detection.confidence >= _threshold;
    final details = <String>[
      if (detection.dosage.isNotEmpty) 'Liều lượng: ${detection.dosage}',
      if (detection.brandName.isNotEmpty)
        'Tên thương mại: ${detection.brandName}',
      if (detection.manufacturer.isNotEmpty)
        'Nhà sản xuất: ${detection.manufacturer}',
    ];
    final percent = (detection.confidence * 100).round();

    // Clinical-adjacent medical content ⇒ force the opaque glass path (R11).
    return GlassSurface(
      clinical: true,
      radius: GlassTokens.radiusCard,
      padding: const EdgeInsets.all(ClaraTokens.spaceMd),
      child: InkWell(
        borderRadius: BorderRadius.circular(GlassTokens.radiusCard * 0.5),
        onTap: () => setState(() => detection.checked = !detection.checked),
        child: ConstrainedBox(
          constraints: const BoxConstraints(
            minHeight: A11y.minTapTargetDimension,
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Semantics(
                checked: detection.checked,
                label: 'Chọn ${detection.drugName}',
                child: Checkbox(
                  value: detection.checked,
                  onChanged: (value) =>
                      setState(() => detection.checked = value ?? false),
                ),
              ),
              const SizedBox(width: ClaraTokens.spaceSm),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      detection.drugName.isEmpty
                          ? 'Không rõ tên thuốc'
                          : detection.drugName,
                      style: theme.textTheme.titleMedium,
                    ),
                    for (final line in details) ...[
                      const SizedBox(height: ClaraTokens.spaceXs),
                      Text(line, style: theme.textTheme.bodyMedium),
                    ],
                    const SizedBox(height: ClaraTokens.spaceSm),
                    StatusByText(
                      label: highConfidence
                          ? 'Độ tin cậy cao ($percent%)'
                          : 'Cần xác nhận ($percent%)',
                      level: highConfidence
                          ? A11yStatusLevel.success
                          : A11yStatusLevel.warning,
                      semanticsPrefix: 'Độ tin cậy',
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildExtractedText(BuildContext context) {
    return Theme(
      data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
      child: ExpansionTile(
        tilePadding: EdgeInsets.zero,
        childrenPadding: const EdgeInsets.only(bottom: ClaraTokens.spaceSm),
        initiallyExpanded: _showExtractedText,
        onExpansionChanged: (value) =>
            setState(() => _showExtractedText = value),
        title: const Text('Văn bản nhận dạng'),
        children: [
          SelectableText(
            _extractedText,
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}
