import 'package:clara_mobile/widgets/proposal_decision_sheet.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('ProposalDecisionSheet triggers onAdmit callback upon confirmation', (tester) async {
    bool admitted = false;
    String? rejectedReason;

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (context) => ElevatedButton(
              onPressed: () {
                ProposalDecisionSheet.show(
                  context,
                  proposalTitle: 'Điều chỉnh liều Metformin 850mg',
                  modelProvenance: 'deepseek-reasoner:v2.5',
                  attestationLevel: 'PROVIDER_EXECUTION_ATTESTED (L3)',
                  onAdmit: () => admitted = true,
                  onReject: (r) => rejectedReason = r,
                );
              },
              child: const Text('Review Proposal'),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('Review Proposal'));
    await tester.pumpAndSettle();

    expect(find.text('Xem xét Đề xuất Lâm sàng AI'), findsOneWidget);
    expect(find.textContaining('Điều chỉnh liều Metformin'), findsOneWidget);
    expect(find.textContaining('deepseek-reasoner'), findsOneWidget);

    await tester.tap(find.text('Chấp thuận (Admit)'));
    await tester.pumpAndSettle();

    expect(admitted, isTrue);
    expect(rejectedReason, isNull);
  });

  testWidgets('ProposalDecisionSheet triggers onReject callback upon rejection', (tester) async {
    bool admitted = false;
    String? rejectedReason;

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (context) => ElevatedButton(
              onPressed: () {
                ProposalDecisionSheet.show(
                  context,
                  proposalTitle: 'Kê đơn bổ sung kháng sinh',
                  modelProvenance: 'deepseek-chat',
                  attestationLevel: 'SERVER_PRE_DISPATCH (L0)',
                  onAdmit: () => admitted = true,
                  onReject: (r) => rejectedReason = r,
                );
              },
              child: const Text('Review Proposal'),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('Review Proposal'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Từ chối'));
    await tester.pumpAndSettle();

    expect(admitted, isFalse);
    expect(rejectedReason, equals('Từ chối bởi bác sĩ'));
  });
}
