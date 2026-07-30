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

/// Locale-specific chrome for the OCR entry flow. Extracted text, medicine
/// names, dosage, and server errors remain authoritative and are never altered.
class _CabinetOcrCopy {
  const _CabinetOcrCopy._(this._english);

  factory _CabinetOcrCopy.forContext(BuildContext context) {
    final language = Localizations.localeOf(context).languageCode.toLowerCase();
    return _CabinetOcrCopy._(language == 'en');
  }

  final bool _english;

  String get offlineMutationBlocked => _english
      ? 'You are offline. This change is paused and your input is kept. Try again when connected.'
      : 'Không có kết nối mạng. Thao tác đã được tạm dừng — dữ liệu bạn nhập vẫn được giữ lại. Vui lòng thử lại khi có mạng.';
  String get scanFailed => _english
      ? 'We could not scan the medicine label. Try again.'
      : 'Không thể quét nhãn thuốc. Vui lòng thử lại.';
  String get importFailed => _english
      ? 'We could not add the medicine to your cabinet. Try again.'
      : 'Không thể thêm thuốc vào tủ. Vui lòng thử lại.';
  String imported(int count) => _english
      ? 'Added $count medicine${count == 1 ? '' : 's'} to your cabinet.'
      : 'Đã thêm $count thuốc vào tủ thuốc.';
  String get errorPrefix => _english ? 'Error' : 'Lỗi';
  String get title => _english ? 'Scan medicine label' : 'Quét nhãn thuốc';
  String get close => _english ? 'Close' : 'Đóng';
  String get captureDescription => _english
      ? 'Take or choose a medicine-label photo so CLARA can identify the medicine name and dose. You confirm the information before it is added to your cabinet.'
      : 'Chụp hoặc chọn ảnh nhãn thuốc để CLARA nhận dạng tên thuốc và liều lượng. Bạn sẽ xác nhận thông tin trước khi thêm vào tủ thuốc.';
  String get takePhoto => _english ? 'Take medicine-label photo' : 'Chụp ảnh nhãn thuốc';
  String get choosePhoto => _english ? 'Choose from library' : 'Chọn từ thư viện';
  String get scanning => _english ? 'Reading medicine label…' : 'Đang nhận dạng nhãn thuốc…';
  String get reviewDescription => _english
      ? 'Check the identified information, select medicines to add, then choose “Add to cabinet”. Low-confidence items need your manual confirmation before they are added.'
      : 'Kiểm tra thông tin nhận dạng, tick chọn các thuốc muốn thêm rồi nhấn “Thêm vào tủ thuốc”. Các mục có độ tin cậy thấp cần bạn xác nhận thủ công trước khi thêm.';
  String get addToCabinet => _english ? 'Add to cabinet' : 'Thêm vào tủ thuốc';
  String get retake => _english ? 'Take another photo' : 'Chụp lại';
  String get noDetection => _english
      ? 'No medicine information was found in the photo. Try a clearer photo.'
      : 'Không nhận được thông tin thuốc từ ảnh. Thử chụp lại rõ hơn.';
  String selectMedicine(String name) =>
      _english ? 'Select $name' : 'Chọn $name';
  String get unknownMedicine => _english ? 'Medicine name unavailable' : 'Không rõ tên thuốc';
  String dosage(String value) => _english ? 'Dose: $value' : 'Liều lượng: $value';
  String brand(String value) => _english ? 'Brand: $value' : 'Tên thương mại: $value';
  String manufacturer(String value) =>
      _english ? 'Manufacturer: $value' : 'Nhà sản xuất: $value';
  String confidence(bool high, int percent) => _english
      ? (high ? 'Higher-confidence detection ($percent%)' : 'Manual confirmation needed ($percent%)')
      : (high ? 'Độ tin cậy cao ($percent%)' : 'Cần xác nhận ($percent%)');
  String get confidencePrefix => _english ? 'Detection confidence' : 'Độ tin cậy';
  String get statusPrefix => _english ? 'Status' : 'Trạng thái';
  String get extractedText => _english ? 'Recognized text' : 'Văn bản nhận dạng';
}

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
  _CabinetOcrCopy get _copy => _CabinetOcrCopy.forContext(context);

  // --- Capture (R4.1) -------------------------------------------------------

  Future<void> _capture(ImageSource source) async {
    if (!_isOnline) {
      _showSnack(_copy.offlineMutationBlocked);
      return;
    }
    final XFile? file = await _picker.pickImage(source: source);
    if (file == null) return; // User cancelled — no state change.
    // Re-check connectivity after the (async) picker closes.
    if (!_isOnline) {
      _showSnack(_copy.offlineMutationBlocked);
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
      setState(() => _error = _copy.scanFailed);
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
      _showSnack(_copy.offlineMutationBlocked);
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
      _showSnack(_copy.imported(inserted));
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
        _error = _copy.importFailed;
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
    final copy = _CabinetOcrCopy.forContext(context);
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
                    semanticsPrefix: copy.errorPrefix,
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
    final copy = _CabinetOcrCopy.forContext(context);
    return Row(
      children: [
        Expanded(
          child: Text(
            copy.title,
            style: theme.textTheme.titleLarge,
          ),
        ),
        IconButton(
          tooltip: copy.close,
          onPressed: () => Navigator.of(context).maybePop(),
          icon: const Icon(Icons.close),
        ),
      ],
    );
  }

  // --- Phase 1: capture -----------------------------------------------------

  Widget _buildCapture(BuildContext context) {
    final copy = _CabinetOcrCopy.forContext(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          copy.captureDescription,
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        const SizedBox(height: ClaraTokens.spaceLg),
        ClaraButton.primary(
          label: copy.takePhoto,
          icon: Icons.photo_camera_outlined,
          loading: _scanning,
          onPressed: _scanning ? null : () => _capture(ImageSource.camera),
        ),
        const SizedBox(height: ClaraTokens.spaceMd),
        ClaraButton.secondary(
          label: copy.choosePhoto,
          icon: Icons.photo_library_outlined,
          onPressed: _scanning ? null : () => _capture(ImageSource.gallery),
        ),
        if (_scanning) ...[
          const SizedBox(height: ClaraTokens.spaceMd),
          Text(
            copy.scanning,
            style: Theme.of(context).textTheme.bodySmall,
            textAlign: TextAlign.center,
          ),
        ],
      ],
    );
  }

  // --- Phase 2: review + Phase 3: import ------------------------------------

  Widget _buildReview(BuildContext context) {
    final copy = _CabinetOcrCopy.forContext(context);
    if (_detections.isEmpty) {
      return _buildEmptyReview(context);
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          copy.reviewDescription,
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
          label: copy.addToCabinet,
          icon: Icons.add,
          loading: _importing,
          onPressed: _canImport ? _import : null,
        ),
        const SizedBox(height: ClaraTokens.spaceSm),
        ClaraButton.secondary(
          label: copy.retake,
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
    final copy = _CabinetOcrCopy.forContext(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        StatusByText(
          label: copy.noDetection,
          level: A11yStatusLevel.warning,
          semanticsPrefix: copy.statusPrefix,
        ),
        const SizedBox(height: ClaraTokens.spaceLg),
        ClaraButton.primary(
          label: copy.retake,
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
    final copy = _CabinetOcrCopy.forContext(context);
    final highConfidence = detection.confidence >= _threshold;
    final details = <String>[
      if (detection.dosage.isNotEmpty) copy.dosage(detection.dosage),
      if (detection.brandName.isNotEmpty)
        copy.brand(detection.brandName),
      if (detection.manufacturer.isNotEmpty)
        copy.manufacturer(detection.manufacturer),
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
                label: copy.selectMedicine(detection.drugName),
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
                          ? copy.unknownMedicine
                          : detection.drugName,
                      style: theme.textTheme.titleMedium,
                    ),
                    for (final line in details) ...[
                      const SizedBox(height: ClaraTokens.spaceXs),
                      Text(line, style: theme.textTheme.bodyMedium),
                    ],
                    const SizedBox(height: ClaraTokens.spaceSm),
                    StatusByText(
                      label: copy.confidence(highConfidence, percent),
                      level: highConfidence
                          ? A11yStatusLevel.success
                          : A11yStatusLevel.warning,
                      semanticsPrefix: copy.confidencePrefix,
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
    final copy = _CabinetOcrCopy.forContext(context);
    return Theme(
      data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
      child: ExpansionTile(
        tilePadding: EdgeInsets.zero,
        childrenPadding: const EdgeInsets.only(bottom: ClaraTokens.spaceSm),
        initiallyExpanded: _showExtractedText,
        onExpansionChanged: (value) =>
            setState(() => _showExtractedText = value),
        title: Text(copy.extractedText),
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
