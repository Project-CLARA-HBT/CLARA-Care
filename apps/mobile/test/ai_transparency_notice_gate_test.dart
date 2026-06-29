// Feature: clara-mobile-feature-parity — Task 9.2 (Requirement 7).
//
// Covers the versioned AI Transparency Notice gate:
//   * Flag OFF -> child renders directly, store untouched (Req 7 gating /
//     Req 15.2 unchanged-when-off).
//   * Flag ON + unacknowledged -> notice shown, child hidden; acknowledging
//     persists the current version and reveals the child (Req 7.1, 7.2).
//   * Flag ON + current version already acknowledged -> child shown directly.
//   * Versioned re-prompt: acknowledging an OLD version still gates when a NEW
//     version is current.
//   * Pure versioning logic (needsAcknowledgement).
//
// An in-memory [SessionSecureStorage] backs the store so the test runs without
// platform channels or live network.

import 'package:clara_mobile/core/ai_transparency_notice.dart';
import 'package:clara_mobile/core/session_store.dart';
import 'package:clara_mobile/widgets/ai_transparency_notice_gate.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

class InMemorySessionSecureStorage implements SessionSecureStorage {
  final Map<String, String> data = {};

  @override
  Future<String?> read(String key) async => data[key];

  @override
  Future<void> write(String key, String value) async => data[key] = value;

  @override
  Future<void> delete(String key) async => data.remove(key);
}

const _notice = AiTransparencyNotice(
  version: 'test-v1',
  title: 'Thông báo minh bạch về AI',
  body: <String>['Bạn đang tương tác với trợ lý y tế AI.'],
);

Widget _harness({
  required bool enabled,
  required AiTransparencyNoticeStore store,
  AiTransparencyNotice notice = _notice,
}) {
  return MaterialApp(
    home: Scaffold(
      body: AiTransparencyNoticeGate(
        enabled: enabled,
        store: store,
        notice: notice,
        child: const Text('MEDICAL_CONTENT'),
      ),
    ),
  );
}

void main() {
  group('needsAcknowledgement (versioning logic)', () {
    test('null acknowledgement requires acknowledgement', () {
      expect(
        AiTransparencyNoticeStore.needsAcknowledgement(
          currentVersion: 'v1',
          acknowledgedVersion: null,
        ),
        isTrue,
      );
    });

    test('matching version does not require acknowledgement', () {
      expect(
        AiTransparencyNoticeStore.needsAcknowledgement(
          currentVersion: 'v1',
          acknowledgedVersion: 'v1',
        ),
        isFalse,
      );
    });

    test('stale (different) version re-prompts', () {
      expect(
        AiTransparencyNoticeStore.needsAcknowledgement(
          currentVersion: 'v2',
          acknowledgedVersion: 'v1',
        ),
        isTrue,
      );
    });

    test('empty current version never requires acknowledgement', () {
      expect(
        AiTransparencyNoticeStore.needsAcknowledgement(
          currentVersion: '',
          acknowledgedVersion: null,
        ),
        isFalse,
      );
    });
  });

  testWidgets('flag OFF renders child directly without touching the store',
      (tester) async {
    final storage = InMemorySessionSecureStorage();
    final store = AiTransparencyNoticeStore(storage: storage);

    await tester.pumpWidget(_harness(enabled: false, store: store));
    await tester.pumpAndSettle();

    expect(find.text('MEDICAL_CONTENT'), findsOneWidget);
    expect(find.text('Thông báo minh bạch về AI'), findsNothing);
    // Nothing was persisted.
    expect(storage.data, isEmpty);
  });

  testWidgets('flag ON + unacknowledged shows notice and gates child',
      (tester) async {
    final store =
        AiTransparencyNoticeStore(storage: InMemorySessionSecureStorage());

    await tester.pumpWidget(_harness(enabled: true, store: store));
    await tester.pumpAndSettle();

    expect(find.text('Thông báo minh bạch về AI'), findsOneWidget);
    expect(find.text('MEDICAL_CONTENT'), findsNothing);
  });

  testWidgets('acknowledging persists the version and reveals the child',
      (tester) async {
    final storage = InMemorySessionSecureStorage();
    final store = AiTransparencyNoticeStore(storage: storage);

    await tester.pumpWidget(_harness(enabled: true, store: store));
    await tester.pumpAndSettle();

    await tester.tap(find.text(_notice.acknowledgeLabel));
    await tester.pumpAndSettle();

    expect(find.text('MEDICAL_CONTENT'), findsOneWidget);
    expect(find.text('Thông báo minh bạch về AI'), findsNothing);
    expect(
      storage.data[AiTransparencyNoticeStore.acknowledgedVersionKey],
      'test-v1',
    );
  });

  testWidgets('flag ON + already acknowledged current version shows child',
      (tester) async {
    final storage = InMemorySessionSecureStorage();
    await storage.write(
        AiTransparencyNoticeStore.acknowledgedVersionKey, 'test-v1');
    final store = AiTransparencyNoticeStore(storage: storage);

    await tester.pumpWidget(_harness(enabled: true, store: store));
    await tester.pumpAndSettle();

    expect(find.text('MEDICAL_CONTENT'), findsOneWidget);
    expect(find.text('Thông báo minh bạch về AI'), findsNothing);
  });

  testWidgets('acknowledged OLD version re-prompts when a NEW version is current',
      (tester) async {
    final storage = InMemorySessionSecureStorage();
    await storage.write(
        AiTransparencyNoticeStore.acknowledgedVersionKey, 'old-version');
    final store = AiTransparencyNoticeStore(storage: storage);

    await tester.pumpWidget(_harness(enabled: true, store: store));
    await tester.pumpAndSettle();

    // Current notice version is 'test-v1' -> stale ack re-prompts.
    expect(find.text('Thông báo minh bạch về AI'), findsOneWidget);
    expect(find.text('MEDICAL_CONTENT'), findsNothing);
  });
}
