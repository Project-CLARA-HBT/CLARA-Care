import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/core/api_client.dart';
import 'package:clara_mobile/screens/council_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes/fakes.dart';

void main() {
  setUp(resetAnalyticsClientForTest);
  tearDown(resetAnalyticsClientForTest);

  Map<String, dynamic> sampleDivergentResponse() => {
        'consensus_summary': 'Đồng thuận cần theo dõi và làm thêm xét nghiệm.',
        'final_recommendation': 'Khuyến nghị nhập viện để theo dõi.',
        'divergence_notes': [
          'Chuyên khoa Tim mạch đề nghị chụp mạch vành.',
        ],
        'conflict_list': [
          {'note': 'Khác biệt về thứ tự ưu tiên chẩn đoán.'},
        ],
        'requested_specialists': ['Tim mạch', 'Nội thần kinh'],
      };

  Map<String, dynamic> sampleConsensusResponse() => {
        'consensus_summary': 'Thống nhất phác đồ điều trị nội khoa.',
        'final_recommendation': 'Uống thuốc theo đơn và tái khám sau 7 ngày.',
        'divergence_notes': <String>[],
        'conflict_list': <dynamic>[],
        'requested_specialists': ['Nội tổng quát', 'Tiêu hóa'],
      };

  Future<void> pumpScreen(
    WidgetTester tester, {
    required FakeApiClient api,
    bool authenticated = true,
  }) async {
    final session = authenticated
        ? await FakeSessionStore.authenticated(role: 'doctor')
        : FakeSessionStore.empty();

    await tester.pumpWidget(MaterialApp(
      home: CouncilScreen(
        apiClient: api,
        sessionStore: session,
      ),
    ));
    await tester.pumpAndSettle();
  }

  testWidgets('renders CouncilScreen with input fields and submit button',
      (tester) async {
    final api = FakeApiClient();
    await pumpScreen(tester, api: api);

    expect(find.text('Hội chẩn AI'), findsOneWidget);
    expect(find.widgetWithText(TextField, 'Triệu chứng'), findsOneWidget);
    expect(find.widgetWithText(TextField, 'Thuốc đang dùng (không bắt buộc)'),
        findsOneWidget);
    expect(find.widgetWithText(TextField, 'Bệnh sử / tóm tắt ca'),
        findsOneWidget);
    expect(find.text('Số chuyên khoa'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'Chạy hội chẩn'), findsOneWidget);
  });

  testWidgets('validates required symptoms or history before submit',
      (tester) async {
    final api = FakeApiClient();
    await pumpScreen(tester, api: api);

    await tester.tap(find.widgetWithText(FilledButton, 'Chạy hội chẩn'));
    await tester.pumpAndSettle();

    expect(
      find.text('Vui lòng nhập triệu chứng hoặc bệnh sử để hội chẩn.'),
      findsOneWidget,
    );
    expect(api.wasCalled('runCouncil'), isFalse);
  });

  testWidgets('shows error when session is not authenticated', (tester) async {
    final api = FakeApiClient();
    await pumpScreen(tester, api: api, authenticated: false);

    await tester.enterText(
      find.widgetWithText(TextField, 'Triệu chứng'),
      'Đau tức ngực',
    );
    await tester.tap(find.widgetWithText(FilledButton, 'Chạy hội chẩn'));
    await tester.pumpAndSettle();

    expect(
      find.text('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.'),
      findsOneWidget,
    );
    expect(api.wasCalled('runCouncil'), isFalse);
  });

  testWidgets('runs council and displays divergent results', (tester) async {
    final api = FakeApiClient()
      ..stub('runCouncil', response: sampleDivergentResponse());
    await pumpScreen(tester, api: api);

    await tester.enterText(
      find.widgetWithText(TextField, 'Triệu chứng'),
      'Đau ngực, Khó thở',
    );
    await tester.enterText(
      find.widgetWithText(TextField, 'Thuốc đang dùng (không bắt buộc)'),
      'Aspirin',
    );
    await tester.enterText(
      find.widgetWithText(TextField, 'Bệnh sử / tóm tắt ca'),
      'Bệnh nhân có tiền sử tăng huyết áp',
    );

    await tester.tap(find.widgetWithText(FilledButton, 'Chạy hội chẩn'));
    await tester.pumpAndSettle();

    expect(api.wasCalled('runCouncil'), isTrue);
    final call = api.callsTo('runCouncil').single;
    final payload = call.args['payload'] as Map<String, dynamic>;
    expect(payload['symptoms'], ['Đau ngực', 'Khó thở']);
    expect(payload['medications'], ['Aspirin']);
    expect(payload['history'], 'Bệnh nhân có tiền sử tăng huyết áp');
    expect(payload['specialist_count'], 3);

    // Results check
    expect(
      find.text('Có điểm khác biệt giữa các chuyên khoa'),
      findsOneWidget,
    );
    expect(find.text('Tóm tắt đồng thuận'), findsOneWidget);
    expect(
      find.text('Đồng thuận cần theo dõi và làm thêm xét nghiệm.'),
      findsOneWidget,
    );
    expect(find.text('Khuyến nghị cuối cùng'), findsOneWidget);
    expect(find.text('Khuyến nghị nhập viện để theo dõi.'), findsOneWidget);
    expect(find.text('Điểm cần lưu ý'), findsOneWidget);
    expect(
      find.text('• Chuyên khoa Tim mạch đề nghị chụp mạch vành.'),
      findsOneWidget,
    );
    expect(
      find.text('• Khác biệt về thứ tự ưu tiên chẩn đoán.'),
      findsOneWidget,
    );
    expect(find.text('Chuyên khoa tham gia'), findsOneWidget);
    expect(find.text('Tim mạch, Nội thần kinh'), findsOneWidget);
  });

  testWidgets('runs council and displays consensus results', (tester) async {
    final api = FakeApiClient()
      ..stub('runCouncil', response: sampleConsensusResponse());
    await pumpScreen(tester, api: api);

    await tester.enterText(
      find.widgetWithText(TextField, 'Triệu chứng'),
      'Đau thượng vị',
    );

    await tester.tap(find.widgetWithText(FilledButton, 'Chạy hội chẩn'));
    await tester.pumpAndSettle();

    expect(api.wasCalled('runCouncil'), isTrue);
    expect(find.text('Các chuyên khoa đồng thuận'), findsOneWidget);
    expect(
      find.text('Thống nhất phác đồ điều trị nội khoa.'),
      findsOneWidget,
    );
    expect(
      find.text('Uống thuốc theo đơn và tái khám sau 7 ngày.'),
      findsOneWidget,
    );
    expect(find.text('Điểm cần lưu ý'), findsNothing);
    expect(find.text('Nội tổng quát, Tiêu hóa'), findsOneWidget);
  });

  testWidgets('handles ApiException cleanly', (tester) async {
    final api = FakeApiClient()
      ..stub(
        'runCouncil',
        error: ApiException(message: 'Lỗi từ máy chủ', statusCode: 500),
      );
    await pumpScreen(tester, api: api);

    await tester.enterText(
      find.widgetWithText(TextField, 'Triệu chứng'),
      'Đau đầu',
    );
    await tester.tap(find.widgetWithText(FilledButton, 'Chạy hội chẩn'));
    await tester.pumpAndSettle();

    expect(find.text('Lỗi từ máy chủ'), findsOneWidget);
  });

  testWidgets('handles generic error cleanly', (tester) async {
    final api = FakeApiClient()
      ..stub(
        'runCouncil',
        error: Exception('Network timeout'),
      );
    await pumpScreen(tester, api: api);

    await tester.enterText(
      find.widgetWithText(TextField, 'Triệu chứng'),
      'Đau đầu',
    );
    await tester.tap(find.widgetWithText(FilledButton, 'Chạy hội chẩn'));
    await tester.pumpAndSettle();

    expect(
      find.text('Không thể chạy hội chẩn lúc này. Vui lòng thử lại.'),
      findsOneWidget,
    );
  });
}
