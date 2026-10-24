import 'package:clara_mobile/core/a11y.dart';
import 'package:clara_mobile/core/connectivity_service.dart';
import 'package:clara_mobile/core/lifemap_client_contract.dart';
import 'package:clara_mobile/core/lifemap_timeline_cache.dart';
import 'package:clara_mobile/core/lifemap_timeline_models.dart';
import 'package:clara_mobile/core/session_store.dart';
import 'package:clara_mobile/experience/language_controller.dart';
import 'package:clara_mobile/widgets/lifemap_timeline_widget.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes/fakes.dart';

Widget _buildTestApp(Widget child, {Size size = const Size(390, 844)}) {
  return MaterialApp(
    home: MediaQuery(
      data: MediaQueryData(size: size),
      child: Scaffold(body: child),
    ),
  );
}

void main() {
  group('LifeMapTimelineModels & Strings', () {
    test('LifeMapTimelinePerspective provides bitemporal vi/en metadata', () {
      expect(
        LifeMapTimelinePerspective.validTime.label('vi'),
        'Thời gian diễn ra',
      );
      expect(
        LifeMapTimelinePerspective.validTime.label('en'),
        'Occurred Time (Valid Time)',
      );
      expect(
        LifeMapTimelinePerspective.systemTime.label('vi'),
        'Thời gian ghi nhận',
      );
      expect(
        LifeMapTimelinePerspective.systemTime.label('en'),
        'Recorded Time (System Time)',
      );

      expect(
        LifeMapTimelinePerspective.validTime.description('vi'),
        contains('triệu chứng xuất hiện'),
      );
      expect(
        LifeMapTimelinePerspective.systemTime.description('vi'),
        contains('hệ thống hoặc cơ sở y tế'),
      );
    });

    test('LifeMapPeriodFilter matches dates correctly within thresholds', () {
      final now = DateTime.utc(2026, 10, 24, 12, 0, 0);

      expect(
        LifeMapPeriodFilter.recent.matches(
          now.subtract(const Duration(days: 3)),
          now,
        ),
        isTrue,
      );
      expect(
        LifeMapPeriodFilter.recent.matches(
          now.subtract(const Duration(days: 10)),
          now,
        ),
        isFalse,
      );

      expect(
        LifeMapPeriodFilter.month.matches(
          now.subtract(const Duration(days: 20)),
          now,
        ),
        isTrue,
      );
      expect(
        LifeMapPeriodFilter.month.matches(
          now.subtract(const Duration(days: 45)),
          now,
        ),
        isFalse,
      );

      expect(
        LifeMapPeriodFilter.all.matches(
          now.subtract(const Duration(days: 1000)),
          now,
        ),
        isTrue,
      );
    });

    test('LifeMapEventTypeFilter categorizes event kinds accurately', () {
      expect(LifeMapEventTypeFilter.medication.matches('medication'), isTrue);
      expect(LifeMapEventTypeFilter.medication.matches('prescription'), isTrue);
      expect(LifeMapEventTypeFilter.medication.matches('symptom'), isFalse);

      expect(LifeMapEventTypeFilter.symptom.matches('symptom'), isTrue);
      expect(LifeMapEventTypeFilter.symptom.matches('condition'), isTrue);
      expect(LifeMapEventTypeFilter.symptom.matches('diagnosis'), isTrue);

      expect(LifeMapEventTypeFilter.visit.matches('visit'), isTrue);
      expect(LifeMapEventTypeFilter.visit.matches('encounter'), isTrue);

      expect(LifeMapEventTypeFilter.result.matches('result'), isTrue);
      expect(LifeMapEventTypeFilter.result.matches('lab'), isTrue);

      expect(LifeMapEventTypeFilter.measurement.matches('measurement'), isTrue);
      expect(LifeMapEventTypeFilter.measurement.matches('vital'), isTrue);

      expect(LifeMapEventTypeFilter.document.matches('document'), isTrue);
      expect(LifeMapEventTypeFilter.all.matches('anything'), isTrue);
    });

    test('LifeMapTimelineEvent serialization and JSON parsing roundtrips', () {
      final event = LifeMapTimelineEvent(
        id: 'evt-100',
        eventType: 'medication',
        truthState: LifeMapClientState.confirmed,
        occurredAt: DateTime.utc(2026, 10, 24, 8, 30),
        recordedAt: DateTime.utc(2026, 10, 24, 8, 35),
        title: 'Metformin 500mg',
        summary: 'Uống sau ăn sáng',
        payload: const {'dosage': '500mg'},
        provenance: const {'source': 'prescription'},
        sourceKind: 'clinician',
        episodeId: 'ep-01',
        revisionNo: 2,
        revisions: const [
          {'revision_no': 1, 'reason': 'Initial ingestion'},
          {'revision_no': 2, 'reason': 'Dosage adjusted from 250mg'},
        ],
      );

      final json = event.toJson();
      expect(json['id'], 'evt-100');
      expect(json['event_type'], 'medication');
      expect(json['truth_state'], 'confirmed');
      expect(json['revision_no'], 2);

      final parsed = LifeMapTimelineEvent.fromJson(json);
      expect(parsed.id, event.id);
      expect(parsed.eventType, event.eventType);
      expect(parsed.truthState, event.truthState);
      expect(parsed.occurredAt, event.occurredAt);
      expect(parsed.recordedAt, event.recordedAt);
      expect(parsed.title, event.title);
      expect(parsed.summary, event.summary);
      expect(parsed.sourceKind, 'clinician');
      expect(parsed.episodeId, 'ep-01');
      expect(parsed.revisionNo, 2);
      expect(parsed.revisions.length, 2);
    });

    test('LifeMapTimelineStrings delivers Vietnamese-first localized text', () {
      expect(
        LifeMapTimelineStrings.timelineTitle('vi'),
        'Dòng thời gian sức khỏe',
      );
      expect(
        LifeMapTimelineStrings.timelineTitle('en'),
        'Health Timeline',
      );

      expect(
        LifeMapTimelineStrings.offlineBannerTitle('vi'),
        'Chế độ ngoại tuyến',
      );
      expect(
        LifeMapTimelineStrings.offlineBannerTitle('en'),
        'Offline Cached View',
      );

      expect(
        LifeMapTimelineStrings.revisionInspectorTitle('vi'),
        'Lịch sử sửa đổi bản ghi',
      );
      expect(
        LifeMapTimelineStrings.sourceKindLabel('vi', 'clinician'),
        'Bác sĩ',
      );
      expect(
        LifeMapTimelineStrings.sourceKindLabel('vi', 'patient'),
        'Bệnh nhân tự nhập',
      );
      expect(
        LifeMapTimelineStrings.sourceKindLabel('vi', 'ocr'),
        'Quét tài liệu (OCR)',
      );
    });
  });

  group('LifeMapTimelineReadCache', () {
    test('cache is default closed when enabled is false', () async {
      final storage = InMemorySessionSecureStorage();
      final cache = LifeMapTimelineReadCache(storage: storage, enabled: false);

      final event = LifeMapTimelineEvent(
        id: 'evt-1',
        eventType: 'observation',
        truthState: LifeMapClientState.confirmed,
        occurredAt: DateTime.utc(2026, 10, 24, 9, 0),
        recordedAt: DateTime.utc(2026, 10, 24, 9, 5),
        title: 'Huyết áp 120/80',
      );

      expect(await cache.save([event]), isFalse);
      expect(await cache.read(), isNull);
      expect(storage.isEmpty, isTrue);
    });

    test('persists sanitized events and enforces 15-minute TTL', () async {
      final storage = InMemorySessionSecureStorage();
      final cache = LifeMapTimelineReadCache(
        storage: storage,
        userId: 'patient-42',
        enabled: true,
      );

      final now = DateTime.utc(2026, 10, 24, 10, 0);
      final events = [
        LifeMapTimelineEvent(
          id: 'evt-1',
          eventType: 'medication',
          truthState: LifeMapClientState.confirmed,
          occurredAt: DateTime.utc(2026, 10, 24, 9, 0),
          recordedAt: DateTime.utc(2026, 10, 24, 9, 5),
          title: 'Amlodipine 5mg',
          summary: '1 viên mỗi sáng sau ăn',
          sourceKind: 'clinician',
          payload: const {'sensitive_credential': 'MUST_BE_DROPPED'},
        ),
      ];

      final saved = await cache.save(events, now: now);
      expect(saved, isTrue);

      final key = LifeMapTimelineReadCache.scopedStorageKey('patient-42');
      final rawPersisted = await storage.read(key);
      expect(rawPersisted, isNotNull);
      expect(rawPersisted, isNot(contains('MUST_BE_DROPPED')));
      expect(rawPersisted, contains('Amlodipine 5mg'));

      // Read within 14 minutes -> valid
      final cachedAt14m = await cache.read(now: now.add(const Duration(minutes: 14)));
      expect(cachedAt14m, isNotNull);
      expect(cachedAt14m!.events.length, 1);
      expect(cachedAt14m.events.first.title, 'Amlodipine 5mg');

      // Read after 16 minutes -> stale, returns null
      final cachedAt16m = await cache.read(now: now.add(const Duration(minutes: 16)));
      expect(cachedAt16m, isNull);
    });

    test('session store logout purges timeline cache', () async {
      final storage = InMemorySessionSecureStorage();
      final store = PersistentSessionStore(storage: storage);
      await store.setSession(
        accessToken: 'access-token',
        refreshToken: 'refresh-token',
        email: 'user@example.com',
        role: 'normal',
      );

      final cache = LifeMapTimelineReadCache(
        storage: storage,
        userId: 'user@example.com',
        enabled: true,
      );

      await cache.save([
        LifeMapTimelineEvent(
          id: 'e-1',
          eventType: 'symptom',
          truthState: LifeMapClientState.confirmed,
          occurredAt: DateTime.utc(2026, 10, 24, 8, 0),
          recordedAt: DateTime.utc(2026, 10, 24, 8, 5),
          title: 'Đau đầu nhẹ',
        )
      ]);

      final scopedKey = LifeMapTimelineReadCache.scopedStorageKey('user@example.com');
      expect(await storage.read(scopedKey), isNotNull);

      await store.clear();
      expect(await storage.read(scopedKey), isNull);
    });
  });

  group('LifeMapTimelineWidget', () {
    final sampleEvents = [
      LifeMapTimelineEvent(
        id: 'evt-1',
        eventType: 'medication',
        truthState: LifeMapClientState.confirmed,
        occurredAt: DateTime.utc(2026, 10, 24, 8, 0),
        recordedAt: DateTime.utc(2026, 10, 24, 8, 30),
        title: 'Paracetamol 500mg',
        summary: 'Uống giảm đau đầu',
        revisionNo: 1,
        sourceKind: 'clinician',
      ),
      LifeMapTimelineEvent(
        id: 'evt-2',
        eventType: 'symptom',
        truthState: LifeMapClientState.awaitingReview,
        occurredAt: DateTime.utc(2026, 10, 24, 7, 30),
        recordedAt: DateTime.utc(2026, 10, 24, 9, 0),
        title: 'Sốt 38.5 độ C',
        summary: 'Kèm ớn lạnh',
        revisionNo: 2,
        sourceKind: 'patient',
        revisions: const [
          {'revision_no': 1, 'reason': 'Tự khai báo lúc sáng'},
          {'revision_no': 2, 'reason': 'Cập nhật lại nhiệt độ thực tế'},
        ],
      ),
    ];

    testWidgets('renders phone layout with bitemporal selector and cards',
        (tester) async {
      final api = FakeApiClient();
      final store = await FakeSessionStore.authenticated(role: 'normal');
      final lang = LanguageController();

      await tester.pumpWidget(
        _buildTestApp(
          LifeMapTimelineWidget(
            apiClient: api,
            sessionStore: store,
            languageController: lang,
            initialEvents: sampleEvents,
          ),
          size: const Size(390, 844),
        ),
      );
      await tester.pumpAndSettle();

      // Title & Subtitle in Vietnamese
      expect(find.text('Dòng thời gian sức khỏe'), findsOneWidget);
      expect(find.text('Paracetamol 500mg'), findsOneWidget);
      expect(find.text('Sốt 38.5 độ C'), findsOneWidget);

      // Bitemporal Perspective controls
      expect(find.text('Thời gian diễn ra'), findsOneWidget);
      expect(find.text('Thời gian ghi nhận'), findsOneWidget);

      // Switch to System Time (\tau_k) perspective
      await tester.tap(find.text('Thời gian ghi nhận'));
      await tester.pumpAndSettle();

      // In System Time, evt-2 (recorded 09:00) comes before evt-1 (recorded 08:30)
      final titles = tester
          .widgetList<Text>(find.byType(Text))
          .map((t) => t.data)
          .where((data) => data == 'Paracetamol 500mg' || data == 'Sốt 38.5 độ C')
          .toList();
      expect(titles.first, 'Sốt 38.5 độ C');
    });

    testWidgets('renders tablet layout with sidebar when width >= 600dp',
        (tester) async {
      final api = FakeApiClient();
      final store = await FakeSessionStore.authenticated(role: 'normal');
      final lang = LanguageController();

      await tester.pumpWidget(
        _buildTestApp(
          LifeMapTimelineWidget(
            apiClient: api,
            sessionStore: store,
            languageController: lang,
            initialEvents: sampleEvents,
          ),
          size: const Size(800, 1024),
        ),
      );
      await tester.pumpAndSettle();

      // Sidebar header in tablet mode
      expect(find.text('Điều khiển dòng thời gian'), findsOneWidget);
      expect(find.text('Paracetamol 500mg'), findsOneWidget);
    });

    testWidgets('displays offline notice banner when offline', (tester) async {
      final api = FakeApiClient();
      final store = await FakeSessionStore.authenticated(role: 'normal');
      final lang = LanguageController();
      final conn = DefaultConnectivityService(initialValue: false);

      await tester.pumpWidget(
        _buildTestApp(
          LifeMapTimelineWidget(
            apiClient: api,
            sessionStore: store,
            languageController: lang,
            connectivityService: conn,
            initialEvents: sampleEvents,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('NGOẠI TUYẾN'), findsOneWidget);
      expect(find.text('Chế độ ngoại tuyến'), findsOneWidget);
    });

    testWidgets('opens revision inspector modal on card click', (tester) async {
      final api = FakeApiClient();
      final store = await FakeSessionStore.authenticated(role: 'normal');
      final lang = LanguageController();

      await tester.pumpWidget(
        _buildTestApp(
          LifeMapTimelineWidget(
            apiClient: api,
            sessionStore: store,
            languageController: lang,
            initialEvents: sampleEvents,
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Tap on the event card for 'Sốt 38.5 độ C'
      await tester.tap(find.text('Sốt 38.5 độ C'));
      await tester.pumpAndSettle();

      // Modal bottom sheet appears
      expect(find.text('Lịch sử sửa đổi bản ghi'), findsOneWidget);
      expect(find.text('Phiên bản 2'), findsAtLeastNWidgets(1));
      expect(find.textContaining('Căn cứ ghi nhận: Tự khai báo lúc sáng'), findsOneWidget);

      await tester.scrollUntilVisible(
        find.text('Đóng'),
        100,
        scrollable: find.byType(Scrollable).last,
      );
      expect(find.text('Đóng'), findsOneWidget);

      await tester.tap(find.text('Đóng'));
      await tester.pumpAndSettle();
      expect(find.text('Lịch sử sửa đổi bản ghi'), findsNothing);
    });

    testWidgets('all interactive touch targets enforce >= 48dp minimum dimension',
        (tester) async {
      final api = FakeApiClient();
      final store = await FakeSessionStore.authenticated(role: 'normal');

      await tester.pumpWidget(
        _buildTestApp(
          LifeMapTimelineWidget(
            apiClient: api,
            sessionStore: store,
            initialEvents: sampleEvents,
          ),
        ),
      );
      await tester.pumpAndSettle();

      final minTapTargets = find.byType(MinTapTarget);
      expect(minTapTargets, findsWidgets);

      for (final element in minTapTargets.evaluate()) {
        final renderBox = element.findRenderObject() as RenderBox?;
        if (renderBox != null && renderBox.hasSize) {
          final size = renderBox.size;
          expect(size.width >= 48.0 - 0.1, isTrue,
              reason: 'Width ${size.width} should be >= 48dp');
          expect(size.height >= 48.0 - 0.1, isTrue,
              reason: 'Height ${size.height} should be >= 48dp');
        }
      }
    });
  });
}
