// Widget tests for the medication-label OCR capture sheet
// (clara-mobile-liquid-glass, Task 4.2 — R4.4 safety invariants).
//
// These lock the manual-confirm gate and offline-write safety of
// `CabinetOcrSheet`:
//
//   * A low-confidence / manual-confirm detection starts UNCHECKED, and when it
//     is the only detection the "Thêm vào tủ thuốc" import button is DISABLED —
//     so `importCareguardDetections` is never called while nothing is checked
//     (R4.4: a checked low-confidence row IS its explicit confirmation).
//   * A high-confidence detection starts CHECKED.
//   * Only checked rows are imported, each carrying `confirmed: true`.
//   * When offline, capture is blocked (the picker is never opened, no scan).
//
// No platform channels, no live network I/O.
//
// Injection seams used here:
//   * The picker is faked via the `@visibleForTesting imagePicker` param on
//     `CabinetOcrSheet`, using a subclass of `ImagePicker` whose `pickImage`
//     returns an in-memory `XFile.fromData` (so `readAsBytes()` works with no
//     platform channel).
//   * The shared `FakeApiClient` does NOT override the two OCR endpoints
//     (`scanCareguardCabinetFile` / `importCareguardDetections`) — calling them
//     unstubbed would hit its unusable HTTP client. We therefore reuse the fake
//     via a thin subclass that overrides just those two methods with canned
//     responses and call recording, keeping the rest of the fake intact.
//
// Deviation note: the sheet's `connectivity` field is typed `ConnectivityService`
// (exposes `currentValue`). The shared `FakeConnectivityService` implements the
// separate `ConnectivityContract` (exposes `isOnlineNow`) and is NOT a
// `ConnectivityService`, so it cannot be injected here. We use the real
// `DefaultConnectivityService(initialValue: false)` for the offline case, which
// is the same seam the existing cabinet tests use.

import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_picker/image_picker.dart';

import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/core/connectivity_service.dart';
import 'package:clara_mobile/experience/redesign/cabinet_ocr_sheet.dart';
import 'package:clara_mobile/widgets/offline_banner.dart';

import 'fakes/fakes.dart';

/// A [FakeApiClient] extended with the two OCR endpoints the sheet calls. The
/// base fake leaves these to the real (unusable) HTTP path, so we override them
/// here with canned responses plus call recording.
class _OcrApiClient extends FakeApiClient {
  Map<String, dynamic> scanResponse = const <String, dynamic>{};
  Map<String, dynamic> importResponse = const <String, dynamic>{'inserted': 0};

  /// Raw byte payloads passed to each `scanCareguardCabinetFile` call.
  final List<List<int>> scanCalls = <List<int>>[];

  /// Detection payloads passed to each `importCareguardDetections` call.
  final List<List<Map<String, dynamic>>> importCalls =
      <List<Map<String, dynamic>>>[];

  @override
  Future<Map<String, dynamic>> scanCareguardCabinetFile({
    required String accessToken,
    required List<int> fileBytes,
    String? filename,
  }) async {
    scanCalls.add(fileBytes);
    return scanResponse;
  }

  @override
  Future<Map<String, dynamic>> importCareguardDetections({
    required String accessToken,
    required List<Map<String, dynamic>> detections,
  }) async {
    importCalls.add(detections);
    return importResponse;
  }
}

/// An [ImagePicker] whose `pickImage` returns a canned in-memory image (or null
/// to model a user cancel). Records how many times it was opened.
class _FakeImagePicker extends ImagePicker {
  _FakeImagePicker({this.file});

  final XFile? file;
  int pickCount = 0;

  @override
  Future<XFile?> pickImage({
    required ImageSource source,
    double? maxWidth,
    double? maxHeight,
    int? imageQuality,
    CameraDevice preferredCameraDevice = CameraDevice.rear,
    bool requestFullMetadata = true,
  }) async {
    pickCount++;
    return file;
  }
}

XFile _cannedImage() => XFile.fromData(
      Uint8List.fromList(const <int>[0x1, 0x2, 0x3, 0x4]),
      name: 'label.jpg',
      mimeType: 'image/jpeg',
    );

/// A scan envelope with one high-confidence and one low-confidence detection.
Map<String, dynamic> _mixedEnvelope() => <String, dynamic>{
      'confirm_gate': <String, dynamic>{'threshold': 0.6},
      'extracted_text': '',
      'detections': <Map<String, dynamic>>[
        <String, dynamic>{
          'drug_name': 'Paracetamol',
          'dosage': '500mg',
          'confidence': 0.95,
          'requires_manual_confirm': false,
        },
        <String, dynamic>{
          'drug_name': 'Amoxicillin',
          'dosage': '250mg',
          'confidence': 0.30,
          'requires_manual_confirm': true,
        },
      ],
    };

Widget _host(Widget child) => MaterialApp(home: Scaffold(body: child));

void main() {
  setUp(resetAnalyticsClientForTest);
  tearDown(resetAnalyticsClientForTest);

  group('CabinetOcrSheet — manual-confirm gate (R4.4)', () {
    testWidgets(
        'high-confidence starts CHECKED, low-confidence starts UNCHECKED',
        (tester) async {
      final api = _OcrApiClient()..scanResponse = _mixedEnvelope();
      final picker = _FakeImagePicker(file: _cannedImage());

      await tester.pumpWidget(_host(CabinetOcrSheet(
        apiClient: api,
        accessToken: 'test-access-token',
        connectivity: DefaultConnectivityService(initialValue: true),
        imagePicker: picker,
      )));
      await tester.pumpAndSettle();

      // Drive capture → review.
      await tester.tap(find.text('Chụp ảnh nhãn thuốc'));
      await tester.pumpAndSettle();

      expect(api.scanCalls, hasLength(1));
      final checkboxes =
          tester.widgetList<Checkbox>(find.byType(Checkbox)).toList();
      expect(checkboxes, hasLength(2));
      // Order mirrors the detection list: [high, low].
      expect(checkboxes[0].value, isTrue, reason: 'high-confidence ⇒ checked');
      expect(checkboxes[1].value, isFalse,
          reason: 'low-confidence / manual-confirm ⇒ unchecked');
    });

    testWidgets(
        'low-confidence ONLY ⇒ import button disabled, import never called',
        (tester) async {
      final api = _OcrApiClient()
        ..scanResponse = <String, dynamic>{
          'confirm_gate': <String, dynamic>{'threshold': 0.6},
          'detections': <Map<String, dynamic>>[
            <String, dynamic>{
              'drug_name': 'Amoxicillin',
              'confidence': 0.20,
              'requires_manual_confirm': true,
            },
          ],
        };
      final picker = _FakeImagePicker(file: _cannedImage());

      await tester.pumpWidget(_host(CabinetOcrSheet(
        apiClient: api,
        accessToken: 'test-access-token',
        connectivity: DefaultConnectivityService(initialValue: true),
        imagePicker: picker,
      )));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Chụp ảnh nhãn thuốc'));
      await tester.pumpAndSettle();

      // The sole row is unchecked, so the primary import button is disabled.
      final checkboxes =
          tester.widgetList<Checkbox>(find.byType(Checkbox)).toList();
      expect(checkboxes, hasLength(1));
      expect(checkboxes[0].value, isFalse);

      final importButton =
          tester.widget<FilledButton>(find.byType(FilledButton));
      expect(importButton.onPressed, isNull,
          reason: 'nothing checked ⇒ import disabled');

      // Tapping the disabled control does nothing — no import fires.
      await tester.tap(find.text('Thêm vào tủ thuốc'));
      await tester.pumpAndSettle();
      expect(api.importCalls, isEmpty);
    });

    testWidgets('only checked rows are imported, each with confirmed: true',
        (tester) async {
      final api = _OcrApiClient()
        ..scanResponse = _mixedEnvelope()
        ..importResponse = const <String, dynamic>{'inserted': 1};
      final picker = _FakeImagePicker(file: _cannedImage());

      await tester.pumpWidget(_host(CabinetOcrSheet(
        apiClient: api,
        accessToken: 'test-access-token',
        connectivity: DefaultConnectivityService(initialValue: true),
        imagePicker: picker,
      )));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Chụp ảnh nhãn thuốc'));
      await tester.pumpAndSettle();

      // High-confidence row is pre-checked; low-confidence row stays unchecked.
      // Import should send exactly the checked (high-confidence) row.
      final importButton =
          tester.widget<FilledButton>(find.byType(FilledButton));
      expect(importButton.onPressed, isNotNull,
          reason: 'a checked row ⇒ import enabled');

      await tester.tap(find.text('Thêm vào tủ thuốc'));
      await tester.pumpAndSettle();

      expect(api.importCalls, hasLength(1));
      final sent = api.importCalls.single;
      expect(sent, hasLength(1), reason: 'only the checked row is sent');
      expect(sent.single['drug_name'], 'Paracetamol');
      expect(sent.single['confirmed'], isTrue);
      // The low-confidence row was never included.
      expect(
        sent.any((d) => d['drug_name'] == 'Amoxicillin'),
        isFalse,
      );
    });
  });

  group('CabinetOcrSheet — offline write safety', () {
    testWidgets('offline ⇒ capture blocked (picker never opens, no scan)',
        (tester) async {
      final api = _OcrApiClient()..scanResponse = _mixedEnvelope();
      final picker = _FakeImagePicker(file: _cannedImage());

      await tester.pumpWidget(_host(CabinetOcrSheet(
        apiClient: api,
        accessToken: 'test-access-token',
        connectivity: DefaultConnectivityService(initialValue: false),
        imagePicker: picker,
      )));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Chụp ảnh nhãn thuốc'));
      await tester.pumpAndSettle();

      // The picker is never opened and no scan is attempted while offline.
      expect(picker.pickCount, 0);
      expect(api.scanCalls, isEmpty);
      // The shared offline message is surfaced.
      expect(find.text(kOfflineMutationBlockedMessage), findsOneWidget);
    });
  });
}
