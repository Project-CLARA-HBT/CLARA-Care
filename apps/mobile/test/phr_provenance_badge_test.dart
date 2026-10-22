import 'package:clara_mobile/widgets/phr_provenance_badge.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('PhrProvenanceBadge renders hospital EMR verified badge', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: PhrProvenanceBadge(
            sourceType: 'EMR',
            isVerified: true,
            sourceName: 'Bệnh viện Bạch Mai',
          ),
        ),
      ),
    );

    expect(find.text('Bệnh viện Bạch Mai'), findsOneWidget);
    expect(find.byIcon(Icons.verified), findsOneWidget);
  });

  testWidgets('PhrProvenanceBadge renders self-reported warning badge', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: PhrProvenanceBadge(
            sourceType: 'SELF',
            isVerified: false,
          ),
        ),
      ),
    );

    expect(find.text('Tự khai báo'), findsOneWidget);
    expect(find.byIcon(Icons.person_outline), findsOneWidget);
  });
}
