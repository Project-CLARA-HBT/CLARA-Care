import 'package:clara_mobile/theme/clara_theme.dart';
import 'package:clara_mobile/theme/components/clara_flow_scaffold.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/experience_pump.dart';

Widget _flow({
  VoidCallback? onBack,
  VoidCallback? onSkip,
  VoidCallback? onNext,
  bool nextEnabled = true,
  bool nextLoading = false,
}) {
  return ClaraFlowScaffold(
    title: 'Thêm thuốc',
    description: 'Mỗi bước chỉ hỏi một nhóm thông tin.',
    stepTitle: 'Tên thuốc',
    step: 2,
    stepCount: 5,
    onBack: onBack,
    onSkip: onSkip,
    onNext: onNext,
    nextEnabled: nextEnabled,
    nextLoading: nextLoading,
    child: const TextField(
      decoration: InputDecoration(labelText: 'Tên thuốc'),
    ),
  );
}

void main() {
  testWidgets('phone renders one content card and stacked primary action',
      (tester) async {
    await pumpAtPhoneWidth(
      tester,
      _flow(onBack: () {}, onSkip: () {}, onNext: () {}),
      theme: ClaraTheme.light(polished: true),
    );
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    expect(find.byKey(const Key('clara-flow-content-card')), findsOneWidget);
    expect(find.byKey(const Key('clara-flow-content-card')), findsOneWidget);
    expect(find.text('Tiếp tục'), findsOneWidget);

    final next = tester.getRect(find.text('Tiếp tục'));
    final back = tester.getRect(find.text('Quay lại'));
    expect(next.top, lessThan(back.top));
  });

  testWidgets('tablet constrains content and lays actions out horizontally',
      (tester) async {
    await pumpAtTabletWidth(
      tester,
      _flow(onBack: () {}, onSkip: () {}, onNext: () {}),
      theme: ClaraTheme.light(polished: true),
    );
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    final cardWidth =
        tester.getSize(find.byKey(const Key('clara-flow-content-card'))).width;
    expect(cardWidth, lessThanOrEqualTo(kClaraFlowContentMaxWidth));

    final next = tester.getRect(find.text('Tiếp tục'));
    final back = tester.getRect(find.text('Quay lại'));
    expect((next.center.dy - back.center.dy).abs(), lessThan(2));
  });

  testWidgets('announces accessible progress and exposes all actions',
      (tester) async {
    final semantics = tester.ensureSemantics();
    var back = 0;
    var skip = 0;
    var next = 0;
    await pumpAtPhoneWidth(
      tester,
      _flow(
        onBack: () => back++,
        onSkip: () => skip++,
        onNext: () => next++,
      ),
      theme: ClaraTheme.light(polished: true),
    );
    await tester.pumpAndSettle();

    expect(
      find.bySemanticsLabel('Bước 2 trên 5: Tên thuốc'),
      findsOneWidget,
    );
    await tester.tap(find.text('Quay lại'));
    await tester.tap(find.text('Bỏ qua'));
    await tester.tap(find.text('Tiếp tục'));
    expect((back, skip, next), (1, 1, 1));

    semantics.dispose();
  });

  testWidgets('disabled and loading next actions cannot submit',
      (tester) async {
    var submissions = 0;
    await pumpAtPhoneWidth(
      tester,
      _flow(
        onNext: () => submissions++,
        nextEnabled: false,
      ),
      theme: ClaraTheme.light(polished: true),
    );
    await tester.tap(find.text('Tiếp tục'));
    expect(submissions, 0);

    await pumpAtPhoneWidth(
      tester,
      _flow(
        onNext: () => submissions++,
        nextLoading: true,
      ),
      theme: ClaraTheme.light(polished: true),
    );
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(submissions, 0);
  });

  for (final brightness in Brightness.values) {
    testWidgets('uses semantic theme surfaces in $brightness mode',
        (tester) async {
      final light = ClaraTheme.light(polished: true);
      final dark = ClaraTheme.dark(polished: true);
      await pumpAtPhoneWidth(
        tester,
        _flow(onNext: () {}),
        theme: light,
        darkTheme: dark,
        platformBrightness: brightness,
      );
      await tester.pumpAndSettle();

      final context = tester.element(find.byType(ClaraFlowScaffold));
      final scheme = Theme.of(context).colorScheme;
      expect(scheme.brightness, brightness);
      final footer =
          tester.widgetList<Material>(find.byType(Material)).firstWhere(
                (material) => material.elevation == 3,
              );
      expect(footer.color, scheme.surface);
    });
  }

  testWidgets('large text remains scrollable without overflow', (tester) async {
    await pumpAtPhoneWidth(
      tester,
      _flow(onBack: () {}, onSkip: () {}, onNext: () {}),
      theme: ClaraTheme.light(polished: true),
      textScaler: const TextScaler.linear(2),
    );
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    expect(find.byType(SingleChildScrollView), findsOneWidget);
  });
}
