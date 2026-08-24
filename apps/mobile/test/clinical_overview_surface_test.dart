import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/core/api_client.dart';
import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/experience/language_controller.dart';
import 'package:clara_mobile/experience/states/empty_state.dart';
import 'package:clara_mobile/experience/unified/clinical_overview_surface.dart';
import 'package:clara_mobile/widgets/error_retry_view.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';

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

void main() {
  setUp(resetAnalyticsClientForTest);
  tearDown(resetAnalyticsClientForTest);

  group('ClinicalOverviewSurface', () {
    testWidgets('fetches patient roster and renders real queue items without static mocks',
        (tester) async {
      final api = FakeApiClient()
        ..stub('listCouncilCases', response: {'items': <dynamic>[]})
        ..stub('listScribeSessions', response: {'items': <dynamic>[]})
        ..stub('getDrugBankStatus', response: {
          'state': 'ready',
          'version': '5.1.10',
          'integrity_verified': true,
        })
        ..stub('getMobileSummary', response: {
          'api_health': {'status': 'ok'},
          'feature_flags': {},
        })
        ..stub('getClinicalPatientRoster', response: {
          'items': [
            {
              'patient_id': 'real-patient-999',
              'display_label': 'Trần Văn Thực (40 tuổi)',
              'attention': {
                'level': 'urgent',
                'reasons': ['Theo dõi sốt xuất huyết'],
              },
            }
          ],
          'total': 1,
        });

      final store = await FakeSessionStore.authenticated(role: 'doctor');
      final resolver = MobileFeatureFlagResolver();

      await tester.pumpWidget(_host(ClinicalOverviewSurface(
        apiClient: api,
        sessionStore: store,
        resolver: resolver,
      )));
      await tester.pumpAndSettle();

      expect(api.wasCalled('getClinicalPatientRoster'), isTrue);
      expect(find.text('Trần Văn Thực (40 tuổi)'), findsOneWidget);
      expect(find.text('Theo dõi sốt xuất huyết'), findsOneWidget);

      // Verify static mock pt-101 is NOT present
      expect(find.text('Nguyễn Văn An (58 tuổi)'), findsNothing);
      expect(find.text('pt-101'), findsNothing);
    });

    testWidgets('shows ClaraEmptyState when patient roster is empty',
        (tester) async {
      final api = FakeApiClient()
        ..stub('listCouncilCases', response: {'items': <dynamic>[]})
        ..stub('listScribeSessions', response: {'items': <dynamic>[]})
        ..stub('getDrugBankStatus', response: {
          'state': 'ready',
          'version': '5.1.10',
          'integrity_verified': true,
        })
        ..stub('getMobileSummary', response: {
          'api_health': {'status': 'ok'},
          'feature_flags': {},
        })
        ..stub('getClinicalPatientRoster', response: {
          'items': <dynamic>[],
          'total': 0,
        });

      final store = await FakeSessionStore.authenticated(role: 'doctor');
      final resolver = MobileFeatureFlagResolver();

      await tester.pumpWidget(_host(ClinicalOverviewSurface(
        apiClient: api,
        sessionStore: store,
        resolver: resolver,
      )));
      await tester.pumpAndSettle();

      expect(find.byType(ClaraEmptyState), findsOneWidget);
      expect(find.text('Hàng đợi trống'), findsOneWidget);
      expect(find.text('Hiện tại chưa có bệnh nhân nào trong hàng đợi khám.'), findsOneWidget);
    });

    testWidgets('shows ErrorRetryView when patient roster API fails',
        (tester) async {
      final api = FakeApiClient()
        ..stub('listCouncilCases', response: {'items': <dynamic>[]})
        ..stub('listScribeSessions', response: {'items': <dynamic>[]})
        ..stub('getDrugBankStatus', response: {
          'state': 'ready',
          'version': '5.1.10',
        })
        ..stub('getMobileSummary', response: {
          'api_health': {'status': 'ok'},
        })
        ..stub(
          'getClinicalPatientRoster',
          error: ApiException(message: 'Lỗi mạng khi tải danh sách bệnh nhân.'),
        );

      final store = await FakeSessionStore.authenticated(role: 'doctor');
      final resolver = MobileFeatureFlagResolver();

      await tester.pumpWidget(_host(ClinicalOverviewSurface(
        apiClient: api,
        sessionStore: store,
        resolver: resolver,
      )));
      await tester.pumpAndSettle();

      expect(find.byType(ErrorRetryView), findsOneWidget);
      expect(find.textContaining('Lỗi mạng'), findsOneWidget);
    });

    testWidgets('dynamically renders DrugBank and System health badges from API responses',
        (tester) async {
      final api = FakeApiClient()
        ..stub('listCouncilCases', response: {'items': <dynamic>[]})
        ..stub('listScribeSessions', response: {'items': <dynamic>[]})
        ..stub('getClinicalPatientRoster', response: {'items': <dynamic>[]})
        ..stub('getDrugBankStatus', response: {
          'state': 'disabled',
        })
        ..stub('getMobileSummary', response: {
          'api_health': {'status': 'degraded'},
        });

      final store = await FakeSessionStore.authenticated(role: 'doctor');
      final resolver = MobileFeatureFlagResolver();

      await tester.pumpWidget(_host(ClinicalOverviewSurface(
        apiClient: api,
        sessionStore: store,
        resolver: resolver,
      )));
      await tester.pumpAndSettle();

      expect(find.text('DrugBank: Đã tắt'), findsOneWidget);
      expect(find.text('Hệ thống: Gián đoạn'), findsOneWidget);
    });
  });
}
