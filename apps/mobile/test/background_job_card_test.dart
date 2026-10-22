import 'package:clara_mobile/widgets/background_job_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('BackgroundJobCard renders running state with linear progress indicator', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: BackgroundJobCard(
            jobTitle: 'Phân tích Đơn thuốc OCR',
            jobState: BackgroundJobState.running,
            progress: 0.65,
          ),
        ),
      ),
    );

    expect(find.text('Phân tích Đơn thuốc OCR'), findsOneWidget);
    expect(find.text('Đang xử lý'), findsOneWidget);
    expect(find.byType(LinearProgressIndicator), findsOneWidget);
  });

  testWidgets('BackgroundJobCard renders failed state with retry button', (tester) async {
    bool retried = false;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: BackgroundJobCard(
            jobTitle: 'Hội chẩn Ca bệnh Council',
            jobState: BackgroundJobState.failed,
            errorMessage: 'Lỗi kết nối máy chủ',
            onRetry: () => retried = true,
          ),
        ),
      ),
    );

    expect(find.text('Hội chẩn Ca bệnh Council'), findsOneWidget);
    expect(find.text('Thất bại'), findsOneWidget);
    expect(find.text('Lỗi kết nối máy chủ'), findsOneWidget);
    expect(find.text('Thử lại'), findsOneWidget);

    await tester.tap(find.text('Thử lại'));
    expect(retried, isTrue);
  });
}
