// Feature: clara-mobile-feature-parity — Task 11.1 (Req 12.1, 12.2, 12.3).
//
// Widget tests for the read-only shared-resource viewer:
//   * A valid token renders the end-user-safe view (Req 12.1, 12.3) and does
//     NOT leak internal runtime fields (mode/retrieval/source_errors/policy).
//   * An invalid / expired token surfaces a clear, NON-PII error rather than
//     partial content (Req 12.2).
//   * With the `sharing_mobile_enabled` gate off, no network call is made and a
//     disabled state is shown (Req 12.4).
//
// A fake [SharedResourceFetcher] is injected directly, so the tests run without
// platform channels or a live server.

import 'package:clara_mobile/core/api_client.dart';
import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/screens/shared_resource_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

MobileFeatureFlagResolver _flags({required bool sharing}) {
  return MobileFeatureFlagResolver(
    summary: {
      'feature_flags': {
        MobileFeatureFlags.sharingMobileEnabled: sharing,
      },
    },
    // Force build-defaults off so the test controls the gate purely via the
    // server flag.
    buildDefaults: const {},
  );
}

void main() {
  testWidgets('valid token renders the end-user-safe shared view', (
    tester,
  ) async {
    var called = 0;
    Future<Map<String, dynamic>> fetcher(String token) async {
      called += 1;
      expect(token, 'good-token');
      return <String, dynamic>{
        'scope': 'full',
        'record': {
          'profile': {
            'full_name': 'Nguyen Van A',
            'blood_type': 'O+',
            'gender': 'nam',
          },
          'allergies': [
            {'name': 'Penicillin', 'severity': 'high', 'reaction': 'phát ban'},
          ],
          'conditions': [
            {'name': 'Tăng huyết áp', 'status': 'active'},
          ],
          'medications': [
            {'name': 'Amlodipine', 'dose': '5mg'},
          ],
          // Internal runtime fields that MUST NOT be rendered (Req 12.3).
          'mode': 'deep_research',
          'retrieval': {'k': 8},
          'source_errors': ['connector-x timeout'],
          'policy': {'verdict': 'allow'},
        },
        'hedge': 'hedge text',
      };
    }

    await tester.pumpWidget(MaterialApp(
      home: SharedResourceScreen(
        token: 'good-token',
        fetcher: fetcher,
        flags: _flags(sharing: true),
      ),
    ));
    await tester.pumpAndSettle();

    expect(called, 1);

    // Safe content is rendered (Req 12.1, 12.3).
    expect(find.text('Hồ sơ sức khỏe được chia sẻ'), findsOneWidget);
    expect(find.textContaining('Nguyen Van A'), findsOneWidget);
    expect(find.textContaining('Penicillin'), findsOneWidget);
    expect(find.textContaining('Amlodipine'), findsOneWidget);
    expect(find.text('Chỉ xem'), findsOneWidget);

    // Internal runtime fields never reach the rendered tree (Req 12.3).
    expect(find.textContaining('deep_research'), findsNothing);
    expect(find.textContaining('source_errors'), findsNothing);
    expect(find.textContaining('connector-x'), findsNothing);
    expect(find.textContaining('verdict'), findsNothing);
    expect(find.textContaining('retrieval'), findsNothing);
  });

  testWidgets('invalid/expired token shows a clear non-PII error', (
    tester,
  ) async {
    Future<Map<String, dynamic>> fetcher(String token) async {
      throw ApiException(
        statusCode: 410,
        message: kSharedResourceUnavailableMessage,
      );
    }

    await tester.pumpWidget(MaterialApp(
      home: SharedResourceScreen(
        token: 'expired-token',
        fetcher: fetcher,
        flags: _flags(sharing: true),
      ),
    ));
    await tester.pumpAndSettle();

    // The error state is shown, with no partial shared content (Req 12.2).
    expect(find.text(kSharedResourceUnavailableMessage), findsOneWidget);
    expect(find.byKey(const Key('shared-resource-body')), findsNothing);
    // The retry affordance is present (Req 9.1).
    expect(find.byKey(const Key('error-retry-view')), findsOneWidget);
  });

  testWidgets('emergency-card scope renders only whitelisted fields', (
    tester,
  ) async {
    Future<Map<String, dynamic>> fetcher(String token) async =>
        <String, dynamic>{
          'scope': 'emergency_card',
          'emergency_card': {
            'disclaimer': {'vi': 'Thẻ tự khai.', 'en': 'Self declared.'},
            'allergies': [
              {'name': 'Aspirin', 'severity': 'high', 'reaction': ''},
            ],
            'current_medications': [
              {'name': 'Metformin', 'dose': '500mg'},
            ],
            'blood_type': 'A+',
            'emergency_contact': {'name': 'Tran B', 'phone': '0900000000'},
          },
        };

    await tester.pumpWidget(MaterialApp(
      home: SharedResourceScreen(
        token: 'card-token',
        fetcher: fetcher,
        flags: _flags(sharing: true),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Thẻ khẩn cấp được chia sẻ'), findsOneWidget);
    expect(find.textContaining('Aspirin'), findsOneWidget);
    expect(find.textContaining('Metformin'), findsOneWidget);
    expect(find.textContaining('A+'), findsOneWidget);
    expect(find.textContaining('Tran B'), findsOneWidget);
  });

  testWidgets('gate off: no fetch and disabled state shown (Req 12.4)', (
    tester,
  ) async {
    var called = 0;
    Future<Map<String, dynamic>> fetcher(String token) async {
      called += 1;
      return <String, dynamic>{'scope': 'full', 'record': {}};
    }

    await tester.pumpWidget(MaterialApp(
      home: SharedResourceScreen(
        token: 'any-token',
        fetcher: fetcher,
        flags: _flags(sharing: false),
      ),
    ));
    await tester.pumpAndSettle();

    expect(called, 0);
    expect(find.byKey(const Key('sharing-disabled')), findsOneWidget);
    expect(find.byKey(const Key('shared-resource-body')), findsNothing);
  });
}
