import 'package:clara_mobile/widgets/consent_explanation_sheet.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('ConsentExplanationSheet renders title, explanation, and dismiss button in Vietnamese', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (context) => ElevatedButton(
              onPressed: () {
                ConsentExplanationSheet.show(
                  context,
                  purposeTitle: 'Minh bạch AI',
                  purposeKey: 'ai_transparency',
                  isEnglish: false,
                );
              },
              child: const Text('Open'),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('Open'));
    await tester.pumpAndSettle();

    expect(find.text('Minh bạch AI'), findsOneWidget);
    expect(find.textContaining('Làm rõ rằng CLARA sử dụng mô hình trí tuệ nhân tạo'), findsOneWidget);
    expect(find.text('Đã hiểu'), findsOneWidget);

    await tester.tap(find.text('Đã hiểu'));
    await tester.pumpAndSettle();

    expect(find.text('Minh bạch AI'), findsNothing);
  });

  testWidgets('ConsentExplanationSheet renders in English when requested', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (context) => ElevatedButton(
              onPressed: () {
                ConsentExplanationSheet.show(
                  context,
                  purposeTitle: 'AI Transparency',
                  purposeKey: 'ai_transparency',
                  isEnglish: true,
                );
              },
              child: const Text('Open'),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('Open'));
    await tester.pumpAndSettle();

    expect(find.text('AI Transparency'), findsOneWidget);
    expect(find.textContaining('Explains that CLARA uses AI language models'), findsOneWidget);
    expect(find.text('Understood'), findsOneWidget);
  });
}
