// Widget tests for the unified MedicinesHub covering the 3 distinct concepts:
// 1. MY MEDICINES (Thuốc của tôi): Confirmed / current active courses
// 2. CABINET (Tủ thuốc): Scanned / OCR'd / inventory items
// 3. SAFETY (An toàn & Tương tác): Interaction checking & DDI analysis

import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/experience/unified/medicines_hub.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes/fakes.dart';

Widget _host(Widget child) => MaterialApp(home: child);

void main() {
  setUp(resetAnalyticsClientForTest);

  group('MedicinesHub — 3 distinct concepts', () {
    testWidgets('renders all three distinct tabs in navigation',
        (tester) async {
      final api = FakeApiClient();
      final store = await FakeSessionStore.authenticated(role: 'normal');

      api.stub('getMedicationCourses', response: const {
        'data': [
          {
            'id': 'med-1',
            'medication_name': 'Amlodipine',
            'dose_text': '5mg',
            'schedule_text': '1 viên sáng',
            'route_text': 'Uống',
            'form_text': 'Viên nén',
            'status': 'active',
            'reconciliation_status': 'matched',
            'version': 1,
          },
        ],
      });

      api.stub('getConsentStatus', response: const {
        'accepted': true,
        'required_version': 'v1',
      });

      api.stub('getCareguardCabinet', response: const {
        'items': [
          {
            'id': 1,
            'drug_name': 'Aspirin',
            'normalized_name': 'aspirin',
          },
          {
            'id': 2,
            'drug_name': 'Warfarin',
            'normalized_name': 'warfarin',
          },
        ],
      });

      await tester.pumpWidget(_host(MedicinesHub(
        apiClient: api,
        sessionStore: store,
        resolver: MobileFeatureFlagResolver(summary: const {}),
      )));
      await tester.pumpAndSettle();

      // Three distinct tab titles
      expect(find.text('Thuốc của tôi'), findsOneWidget);
      expect(find.text('Tủ thuốc'), findsOneWidget);
      expect(find.text('An toàn'), findsOneWidget);

      // Tab 1: Confirmed courses
      expect(find.text('Amlodipine'), findsOneWidget);
      expect(find.textContaining('5mg • 1 viên sáng'), findsOneWidget);
      expect(find.text('Đang dùng'), findsOneWidget);
      expect(find.text('Đã khớp nguồn'), findsOneWidget);
    });

    testWidgets(
        'Safety tab enforces two-medicine guard and preserves DrugBank authority',
        (tester) async {
      final api = FakeApiClient();
      final store = await FakeSessionStore.authenticated(role: 'normal');

      api.stub('getMedicationCourses', response: const {'data': []});
      api.stub('getConsentStatus', response: const {
        'accepted': true,
        'required_version': 'v1',
      });

      // 2 distinct medicines in cabinet
      api.stub('getCareguardCabinet', response: const {
        'items': [
          {
            'id': 1,
            'drug_name': 'Warfarin',
            'normalized_name': 'warfarin',
          },
          {
            'id': 2,
            'drug_name': 'Ibuprofen',
            'normalized_name': 'ibuprofen',
          },
        ],
      });

      api.stub('autoCheckCareguardCabinet', response: const {
        'risk_tier': 'high',
        'ddi_alerts': [
          {
            'title': 'Nguy cơ xuất huyết tăng cao',
            'severity': 'high',
            'medications': ['Warfarin', 'Ibuprofen'],
            'details': 'NSAIDs làm tăng tác dụng chống đông của Warfarin.',
          },
        ],
        'recommendations': [
          'Tham khảo ý kiến bác sĩ trước khi phối hợp.',
        ],
        'attribution': {
          'sources': [
            {'name': 'DrugBank v5.1'},
          ],
        },
      });

      await tester.pumpWidget(_host(MedicinesHub(
        apiClient: api,
        sessionStore: store,
        resolver: MobileFeatureFlagResolver(summary: const {}),
      )));
      await tester.pumpAndSettle();

      // Switch to Safety tab (Tab 3)
      await tester.tap(find.text('An toàn'));
      await tester.pumpAndSettle();

      expect(find.text('Kiểm tra tương tác từ Tủ thuốc'), findsOneWidget);
      expect(find.textContaining('2 thuốc'), findsWidgets);

      // Tap Check Interactions
      final checkButton = find.text('Kiểm tra tương tác thuốc trong tủ');
      expect(checkButton, findsOneWidget);
      await tester.ensureVisible(checkButton);
      await tester.tap(checkButton);
      await tester.pumpAndSettle();

      // Verified DDI results appear
      await tester.drag(find.text('Kiểm tra tương tác thuốc trong tủ'), const Offset(0, -300));
      await tester.pumpAndSettle();

      expect(find.text('Nguy cơ xuất huyết tăng cao'), findsOneWidget);
      expect(find.textContaining('DrugBank v5.1'), findsOneWidget);
    });

    testWidgets(
        'Safety tab prompts when cabinet has fewer than 2 distinct medicines',
        (tester) async {
      final api = FakeApiClient();
      final store = await FakeSessionStore.authenticated(role: 'normal');

      api.stub('getMedicationCourses', response: const {'data': []});
      api.stub('getConsentStatus', response: const {
        'accepted': true,
        'required_version': 'v1',
      });

      // Only 1 medicine in cabinet
      api.stub('getCareguardCabinet', response: const {
        'items': [
          {
            'id': 1,
            'drug_name': 'Paracetamol',
            'normalized_name': 'paracetamol',
          },
        ],
      });

      await tester.pumpWidget(_host(MedicinesHub(
        apiClient: api,
        sessionStore: store,
        resolver: MobileFeatureFlagResolver(summary: const {}),
      )));
      await tester.pumpAndSettle();

      // Switch to Safety tab
      await tester.tap(find.text('An toàn'));
      await tester.pumpAndSettle();

      expect(
        find.textContaining('Cần ít nhất 2 thuốc khác nhau'),
        findsOneWidget,
      );
      expect(find.text('Mở Tủ thuốc'), findsOneWidget);
    });
  });
}
