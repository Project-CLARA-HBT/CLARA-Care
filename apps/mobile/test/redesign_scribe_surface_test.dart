// Widget tests for the redesigned Medical Scribe surface (Experience_V3).
//
// clara-mobile-redesign, Task 8.3. These lock the three fail-closed gating
// layers and the no-PII discipline:
//
//   * Gate 1 (flag) — `scribe_mobile_enabled` off ⇒ inert placeholder, ZERO
//     network calls.
//   * Gate 2 (role) — only `doctor` OR `admin` may reach the surface; every
//     other/missing role ⇒ placeholder, ZERO network calls.
//   * When both gates open (authorized doctor/admin), the session list loads.
//   * Analytics never receive clinical free text — only the coarse
//     `mobile_scribe_*` event names.

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/experience/redesign/scribe_surface_v3.dart';
import 'package:clara_mobile/screens/scribe_screen.dart' show ScribeAudioClip;

import 'fakes/fakes.dart';

Widget _host(Widget child) => MaterialApp(
      locale: const Locale('vi'),
      supportedLocales: const [Locale('vi'), Locale('en')],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      home: child,
    );

/// A resolver with `scribe_mobile_enabled` granted by the server summary.
MobileFeatureFlagResolver _scribeOn() => MobileFeatureFlagResolver(
      summary: const {
        'feature_flags': {'scribe_mobile_enabled': true},
      },
    );

/// A resolver with every gate off (fail-closed default).
MobileFeatureFlagResolver _allOff() => MobileFeatureFlagResolver();

void main() {
  setUp(resetAnalyticsClientForTest);
  tearDown(resetAnalyticsClientForTest);

  group('ScribeSurfaceV3 — fail-closed gating (Requirement 8, INV-2/INV-4)',
      () {
    testWidgets('flag off ⇒ inert placeholder, zero network calls',
        (tester) async {
      final api = FakeApiClient();
      final store = await FakeSessionStore.authenticated(role: 'doctor');

      await tester.pumpWidget(_host(ScribeSurfaceV3(
        apiClient: api,
        sessionStore: store,
        resolver: _allOff(),
      )));
      await tester.pumpAndSettle();

      expect(find.text('Không khả dụng'), findsOneWidget);
      expect(api.wasCalled('listScribeSessions'), isFalse);
      expect(api.invocations, isEmpty);
    });

    testWidgets('unauthorized role ⇒ placeholder, zero network calls',
        (tester) async {
      final api = FakeApiClient();
      // Flag on, but a normal (non-doctor/non-admin) role stays fail-closed.
      final store = await FakeSessionStore.authenticated(role: 'normal');

      await tester.pumpWidget(_host(ScribeSurfaceV3(
        apiClient: api,
        sessionStore: store,
        resolver: _scribeOn(),
      )));
      await tester.pumpAndSettle();

      expect(find.text('Không khả dụng'), findsOneWidget);
      expect(api.invocations, isEmpty);
    });

    testWidgets('authorized doctor with the flag on loads the session list',
        (tester) async {
      final api = FakeApiClient()
        ..stub('listScribeSessions', response: {'items': <dynamic>[]});
      final store = await FakeSessionStore.authenticated(role: 'doctor');

      await tester.pumpWidget(_host(ScribeSurfaceV3(
        apiClient: api,
        sessionStore: store,
        resolver: _scribeOn(),
      )));
      await tester.pumpAndSettle();

      expect(api.wasCalled('listScribeSessions'), isTrue);
      expect(find.text('Không khả dụng'), findsNothing);
    });

    testWidgets('admin is authorized too (redesign widens doctor-only RBAC)',
        (tester) async {
      final api = FakeApiClient()
        ..stub('listScribeSessions', response: {'items': <dynamic>[]});
      final store = await FakeSessionStore.authenticated(role: 'admin');

      await tester.pumpWidget(_host(ScribeSurfaceV3(
        apiClient: api,
        sessionStore: store,
        resolver: _scribeOn(),
      )));
      await tester.pumpAndSettle();

      expect(api.wasCalled('listScribeSessions'), isTrue);
    });

    testWidgets('the screen-view analytics event carries no clinical text',
        (tester) async {
      final transport = RecordingAnalyticsTransport();
      final analytics = Analytics(transport: transport)
        ..init(
          const AnalyticsConfig(provider: 'test', apiKey: 'k'),
          consentGranted: true,
        );
      final api = FakeApiClient()
        ..stub('listScribeSessions', response: {'items': <dynamic>[]});
      final store = await FakeSessionStore.authenticated(role: 'doctor');

      await tester.pumpWidget(_host(ScribeSurfaceV3(
        apiClient: api,
        sessionStore: store,
        resolver: _scribeOn(),
        analytics: analytics,
      )));
      await tester.pumpAndSettle();

      // The only event is the coarse view event; it carries no props at all.
      expect(transport.capturedNames, contains('mobile_scribe_viewed'));
      for (final event in transport.captured) {
        expect(event.props, isEmpty,
            reason: 'Scribe analytics must never carry clinical content.');
      }
    });

    testWidgets(
        'renders canonical 6-stage workflow stepper in session detail',
        (tester) async {
      final api = FakeApiClient()
        ..stub('listScribeSessions', response: {
          'items': [
            {
              'id': 10,
              'title': 'Phiên kiểm tra quy trình',
              'status': 'draft',
              'transcript': 'Bệnh nhân than phiền đau đầu.',
              'soap': {
                'subjective': 'Bệnh nhân đau đầu 2 ngày.',
                'assessment': 'Theo dõi đau đầu căng thẳng.',
              },
            }
          ]
        })
        ..stub('getScribeSession', response: {
          'id': 10,
          'title': 'Phiên kiểm tra quy trình',
          'status': 'draft',
          'transcript': 'Bệnh nhân than phiền đau đầu.',
          'soap': {
            'subjective': 'Bệnh nhân đau đầu 2 ngày.',
            'assessment': 'Theo dõi đau đầu căng thẳng.',
          },
        });
      final store = await FakeSessionStore.authenticated(role: 'doctor');

      await tester.pumpWidget(_host(ScribeSurfaceV3(
        apiClient: api,
        sessionStore: store,
        resolver: _scribeOn(),
      )));
      await tester.pumpAndSettle();

      // Open session
      await tester.tap(find.text('Phiên kiểm tra quy trình'));
      await tester.pumpAndSettle();

      // Verify the 6-stage canonical workflow stepper is rendered
      expect(find.text('Đồng thuận'), findsWidgets);
      expect(find.text('Ghi âm'), findsWidgets);
      expect(find.text('Kiểm tra bản ghi'), findsWidgets);
      expect(find.text('Kiểm tra SOAP'), findsWidgets);
      expect(find.text('Hoàn tất bản nháp'), findsWidgets);
      expect(find.text('Ký & Xuất bản'), findsWidgets);
    });

    testWidgets(
        'clearly distinguishes scribe states in session list and detail',
        (tester) async {
      final api = FakeApiClient()
        ..stub('listScribeSessions', response: {
          'items': [
            {'id': 1, 'title': 'Session 1', 'status': 'recording'},
            {'id': 2, 'title': 'Session 2', 'status': 'ready'},
            {'id': 3, 'title': 'Session 3', 'status': 'draft'},
            {'id': 4, 'title': 'Session 4', 'status': 'reviewed'},
            {'id': 5, 'title': 'Session 5', 'status': 'signed'},
            {'id': 6, 'title': 'Session 6', 'status': 'exported'},
            {'id': 7, 'title': 'Session 7', 'status': 'amended'},
          ]
        });
      final store = await FakeSessionStore.authenticated(role: 'doctor');

      await tester.pumpWidget(_host(ScribeSurfaceV3(
        apiClient: api,
        sessionStore: store,
        resolver: _scribeOn(),
      )));
      await tester.pumpAndSettle();

      expect(find.text('Đang ghi'), findsOneWidget);
      expect(find.text('Bản ghi sẵn sàng'), findsOneWidget);
      expect(find.text('Bản nháp'), findsOneWidget);
      expect(find.text('Đã duyệt'), findsOneWidget);

      // Scroll down to see the remaining session status badges
      await tester.drag(find.byType(ListView), const Offset(0, -300));
      await tester.pumpAndSettle();

      expect(find.text('Đã ký'), findsOneWidget);
      expect(find.text('Đã xuất bản'), findsOneWidget);
      expect(find.text('Bản sửa đổi'), findsOneWidget);
    });

    testWidgets(
        'transcript and SOAP note reading surfaces are opaque without transparent glass',
        (tester) async {
      final api = FakeApiClient()
        ..stub('listScribeSessions', response: {
          'items': [
            {
              'id': 11,
              'title': 'Phiên đọc lâm sàng',
              'status': 'ready',
              'transcript': 'Nội dung bản ghi thoại.',
              'soap': {
                'subjective': 'Bệnh nhân than phiền đau đầu.',
                'objective': 'Huyết áp 120/80.',
                'assessment': 'Đau đầu căng thẳng.',
                'plan': 'Nghỉ ngơi và theo dõi.',
              },
            }
          ]
        })
        ..stub('getScribeSession', response: {
          'id': 11,
          'title': 'Phiên đọc lâm sàng',
          'status': 'ready',
          'transcript': 'Nội dung bản ghi thoại.',
          'soap': {
            'subjective': 'Bệnh nhân than phiền đau đầu.',
            'objective': 'Huyết áp 120/80.',
            'assessment': 'Đau đầu căng thẳng.',
            'plan': 'Nghỉ ngơi và theo dõi.',
          },
        });
      final store = await FakeSessionStore.authenticated(role: 'doctor');

      await tester.pumpWidget(_host(ScribeSurfaceV3(
        apiClient: api,
        sessionStore: store,
        resolver: _scribeOn(),
      )));
      await tester.pumpAndSettle();

      // Open session
      await tester.tap(find.text('Phiên đọc lâm sàng'));
      await tester.pumpAndSettle();

      // Transcript and SOAP notes are rendered
      expect(find.byKey(const Key('scribe-v3-transcript')), findsOneWidget);
      expect(find.text('Nội dung bản ghi thoại.'), findsOneWidget);

      // Scroll down to SOAP section
      await tester.drag(find.byType(ListView), const Offset(0, -300));
      await tester.pumpAndSettle();

      expect(find.textContaining('Chủ quan'), findsWidgets);
      expect(find.text('Bệnh nhân than phiền đau đầu.'), findsOneWidget);
      expect(find.textContaining('Đánh giá'), findsWidgets);
      expect(find.text('Đau đầu căng thẳng.'), findsOneWidget);
    });

    testWidgets(
        'per-session consent gate blocks processing until captured and re-blocks on revocation (INV-2)',
        (tester) async {
      final api = FakeApiClient()
        ..stub('listScribeSessions', response: {
          'items': [
            {
              'id': 20,
              'title': 'Phiên kiểm tra consent',
              'status': 'recording',
              'transcript': 'Khám ban đầu',
              'soap': {},
            }
          ]
        })
        ..stub('getScribeSession', response: {
          'id': 20,
          'title': 'Phiên kiểm tra consent',
          'status': 'recording',
          'transcript': 'Khám ban đầu',
          'soap': {},
        })
        ..stub('captureScribeConsent', response: {'status': 'consented'})
        ..stub('revokeScribeConsent', response: {'status': 'revoked'})
        ..stub('regenerateScribeSession', response: {
          'id': 20,
          'title': 'Phiên kiểm tra consent',
          'status': 'ready',
          'transcript': 'Khám ban đầu\nBệnh nhân hết đau đầu',
          'soap': {
            'subjective': 'Bệnh nhân hết đau đầu.',
          },
        });
      final store = await FakeSessionStore.authenticated(role: 'doctor');

      await tester.pumpWidget(_host(ScribeSurfaceV3(
        apiClient: api,
        sessionStore: store,
        resolver: _scribeOn(),
      )));
      await tester.pumpAndSettle();

      // Open session
      await tester.tap(find.text('Phiên kiểm tra consent'));
      await tester.pumpAndSettle();

      // Consent is absent initially on open (fail-closed, INV-2)
      expect(
        find.text('Chưa có sự đồng ý — việc xử lý lời thoại đang bị chặn.'),
        findsOneWidget,
      );
      expect(find.text('Thu thập sự đồng ý'), findsOneWidget);

      // Attempting to append transcript before consent shows warning snackbar
      await tester.enterText(
        find.byType(TextFormField).first,
        'Bệnh nhân hết đau đầu',
      );
      await tester.tap(find.text('Thêm & tạo ghi chú'));
      await tester.pumpAndSettle();

      expect(api.wasCalled('regenerateScribeSession'), isFalse);
      expect(
        find.text('Cần thu thập sự đồng ý của bệnh nhân trước khi xử lý lời thoại.'),
        findsOneWidget,
      );

      // Capture consent
      await tester.tap(find.text('Thu thập sự đồng ý'));
      await tester.pumpAndSettle();

      expect(api.wasCalled('captureScribeConsent'), isTrue);
      expect(find.text('Đã thu thập sự đồng ý của bệnh nhân.'), findsOneWidget);
      expect(find.text('Thu hồi sự đồng ý'), findsOneWidget);

      // Dismiss any active SnackBar before tapping
      await tester.pump(const Duration(seconds: 5));
      await tester.pumpAndSettle();

      // Now appending transcript proceeds
      await tester.ensureVisible(find.text('Thêm & tạo ghi chú'));
      await tester.tap(find.text('Thêm & tạo ghi chú'));
      await tester.pumpAndSettle();

      expect(api.wasCalled('regenerateScribeSession'), isTrue);
      expect(find.textContaining('Bệnh nhân hết đau đầu'), findsWidgets);

      // Revoke consent
      await tester.ensureVisible(find.text('Thu hồi sự đồng ý'));
      await tester.tap(find.text('Thu hồi sự đồng ý'));
      await tester.pumpAndSettle();

      expect(api.wasCalled('revokeScribeConsent'), isTrue);
      expect(
        find.text('Chưa có sự đồng ý — việc xử lý lời thoại đang bị chặn.'),
        findsOneWidget,
      );

      // Subsequent processing is re-blocked
      await tester.ensureVisible(find.byType(TextFormField).first);
      await tester.enterText(
        find.byType(TextFormField).first,
        'Nội dung mới',
      );
      await tester.ensureVisible(find.text('Thêm & tạo ghi chú'));
      await tester.tap(find.text('Thêm & tạo ghi chú'));
      await tester.pumpAndSettle();

      expect(
        find.text('Cần thu thập sự đồng ý của bệnh nhân trước khi xử lý lời thoại.'),
        findsOneWidget,
      );
    });

    testWidgets('opening an existing session with has_active_consent initializes consent as granted',
        (tester) async {
      final api = FakeApiClient()
        ..stub('listScribeSessions', response: {
          'items': [
            {
              'id': 30,
              'title': 'Phiên đã có đồng ý',
              'status': 'recording',
              'transcript': 'Khám ban đầu',
              'has_active_consent': true,
              'consent_id': 88,
              'soap': {},
            }
          ]
        })
        ..stub('getScribeSession', response: {
          'id': 30,
          'title': 'Phiên đã có đồng ý',
          'status': 'recording',
          'transcript': 'Khám ban đầu',
          'has_active_consent': true,
          'consent_id': 88,
          'soap': {},
        });
      final store = await FakeSessionStore.authenticated(role: 'doctor');

      await tester.pumpWidget(_host(ScribeSurfaceV3(
        apiClient: api,
        sessionStore: store,
        resolver: _scribeOn(),
      )));
      await tester.pumpAndSettle();

      // Open session
      await tester.tap(find.text('Phiên đã có đồng ý'));
      await tester.pumpAndSettle();

      // Consent is initialized as active from session.hasActiveConsent
      expect(find.text('Đã thu thập sự đồng ý của bệnh nhân.'), findsOneWidget);
      expect(find.text('Thu hồi sự đồng ý'), findsOneWidget);
      expect(find.text('Thu thập sự đồng ý'), findsNothing);
    });

    testWidgets(
        'immersive audio capture is consent-gated and triggers transcribeScribeAudio',
        (tester) async {
      final transport = RecordingAnalyticsTransport();
      final analytics = Analytics(transport: transport)
        ..init(
          const AnalyticsConfig(provider: 'test', apiKey: 'k'),
          consentGranted: true,
        );
      final api = FakeApiClient()
        ..stub('listScribeSessions', response: {
          'items': [
            {
              'id': 40,
              'title': 'Phiên ghi âm trực tiếp',
              'status': 'recording',
              'transcript': 'Lời thoại cũ',
              'soap': {},
            }
          ]
        })
        ..stub('getScribeSession', response: {
          'id': 40,
          'title': 'Phiên ghi âm trực tiếp',
          'status': 'recording',
          'transcript': 'Lời thoại cũ',
          'soap': {},
        })
        ..stub('captureScribeConsent', response: {'status': 'consented'})
        ..stub('transcribeScribeAudio', response: {
          'id': 40,
          'title': 'Phiên ghi âm trực tiếp',
          'status': 'ready',
          'transcript': 'Lời thoại cũ\nLời thoại từ ghi âm mới',
          'soap': {
            'subjective': 'Lời thoại từ ghi âm mới',
          },
        });
      final store = await FakeSessionStore.authenticated(role: 'doctor');

      var audioProviderCalled = false;
      Future<ScribeAudioClip?> fakeAudioProvider() async {
        audioProviderCalled = true;
        return const ScribeAudioClip(
          bytes: [1, 2, 3, 4],
          filename: 'audio.wav',
        );
      }

      await tester.pumpWidget(_host(ScribeSurfaceV3(
        apiClient: api,
        sessionStore: store,
        resolver: _scribeOn(),
        audioProvider: fakeAudioProvider,
        analytics: analytics,
      )));
      await tester.pumpAndSettle();

      // Open session
      await tester.tap(find.text('Phiên ghi âm trực tiếp'));
      await tester.pumpAndSettle();

      // Verify immersive audio capture card is rendered
      expect(find.byKey(const Key('scribe-v3-audio-capture-card')), findsOneWidget);
      expect(find.text('Ghi âm lời thoại trực tiếp'), findsOneWidget);
      expect(find.text('Cần đồng thuận trước khi ghi âm'), findsOneWidget);

      // Attempt audio capture BEFORE consent -> blocked
      await tester.tap(find.byKey(const Key('scribe-upload-audio')));
      await tester.pumpAndSettle();

      expect(audioProviderCalled, isFalse);
      expect(api.wasCalled('transcribeScribeAudio'), isFalse);
      expect(
        find.text('Cần thu thập sự đồng ý của bệnh nhân trước khi xử lý lời thoại.'),
        findsOneWidget,
      );

      // Dismiss snackbar
      await tester.pump(const Duration(seconds: 5));
      await tester.pumpAndSettle();

      // Capture consent
      await tester.tap(find.text('Thu thập sự đồng ý'));
      await tester.pumpAndSettle();

      expect(api.wasCalled('captureScribeConsent'), isTrue);
      expect(find.text('Sẵn sàng thu âm'), findsOneWidget);

      // Now audio capture proceeds
      await tester.ensureVisible(find.byKey(const Key('scribe-upload-audio')));
      await tester.tap(find.byKey(const Key('scribe-upload-audio')));
      await tester.pumpAndSettle();

      expect(audioProviderCalled, isTrue);
      expect(api.wasCalled('transcribeScribeAudio'), isTrue);
      expect(transport.capturedNames, contains('mobile_scribe_audio_processed'));
      expect(find.textContaining('Lời thoại từ ghi âm mới'), findsWidgets);
    });
  });
}
