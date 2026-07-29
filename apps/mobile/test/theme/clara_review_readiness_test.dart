import 'package:clara_mobile/theme/clara_theme.dart';
import 'package:clara_mobile/theme/components/clara_review_section.dart';
import 'package:clara_mobile/theme/components/feature_readiness_tile.dart';
import 'package:clara_mobile/theme/web_palette.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

const _reviewItems = <ClaraReviewItem>[
  ClaraReviewItem(
    label: 'Tên thuốc',
    value: 'Amoxicillin',
    kind: ClaraReviewValueKind.entered,
    kindLabel: 'Bạn đã nhập',
  ),
  ClaraReviewItem(
    label: 'Nguồn',
    value: 'Nhãn thuốc đã chọn',
    kind: ClaraReviewValueKind.source,
    kindLabel: 'Có nguồn',
    supportingText: 'Hãy kiểm tra lại trước khi xác nhận.',
  ),
  ClaraReviewItem(
    label: 'Liều dùng',
    value: 'Chưa rõ',
    kind: ClaraReviewValueKind.unknown,
    kindLabel: 'Cần bổ sung',
  ),
  ClaraReviewItem(
    label: 'Lịch dùng',
    value: 'Hai thông tin khác nhau',
    kind: ClaraReviewValueKind.conflict,
    kindLabel: 'Có xung đột',
  ),
];

Widget _wrap(
  Widget child, {
  required ThemeData theme,
  Size size = const Size(390, 844),
  double textScale = 1,
}) {
  return MaterialApp(
    theme: theme,
    home: MediaQuery(
      data: MediaQueryData(
        size: size,
        textScaler: TextScaler.linear(textScale),
      ),
      child: Scaffold(
        body: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: child,
        ),
      ),
    ),
  );
}

void main() {
  group('ClaraReviewSection', () {
    testWidgets('groups review values and states into stable semantics',
        (tester) async {
      final semantics = tester.ensureSemantics();
      var edits = 0;

      await tester.pumpWidget(
        _wrap(
          ClaraReviewSection(
            title: 'Kiểm tra thông tin',
            description: 'Chỉ lưu sau khi bạn xác nhận.',
            items: _reviewItems,
            editLabel: 'Chỉnh sửa',
            onEdit: () => edits++,
          ),
          theme: ClaraTheme.light(polished: true),
        ),
      );

      expect(
        find.bySemanticsLabel('Kiểm tra thông tin'),
        findsAtLeastNWidgets(1),
      );
      expect(
        find.bySemanticsLabel(
          'Tên thuốc: Amoxicillin. Bạn đã nhập',
        ),
        findsOneWidget,
      );
      expect(
        find.bySemanticsLabel(
          'Nguồn: Nhãn thuốc đã chọn. Có nguồn. '
          'Hãy kiểm tra lại trước khi xác nhận.',
        ),
        findsOneWidget,
      );
      expect(
        find.bySemanticsLabel(
          'Lịch dùng: Hai thông tin khác nhau. Có xung đột',
        ),
        findsOneWidget,
      );

      await tester.tap(find.text('Chỉnh sửa'));
      expect(edits, 1);
      expect(tester.getSize(find.byType(TextButton)).height,
          greaterThanOrEqualTo(48));
      semantics.dispose();
    });

    for (final entry in <(String, ThemeData)>[
      ('light', ClaraTheme.light(polished: true)),
      ('dark', ClaraTheme.dark(polished: true)),
    ]) {
      testWidgets('uses semantic $entry theme roles and reflows at large text',
          (tester) async {
        await tester.pumpWidget(
          _wrap(
            const ClaraReviewSection(
              title: 'Kiểm tra thông tin',
              description: 'Thông tin hiển thị do người dùng kiểm soát.',
              items: _reviewItems,
            ),
            theme: entry.$2,
            size: const Size(834, 1112),
            textScale: 2,
          ),
        );

        expect(tester.takeException(), isNull);
        final context = tester.element(find.byType(ClaraReviewSection));
        final scheme = Theme.of(context).colorScheme;
        expect(
          tester.widget<Icon>(find.byIcon(Icons.compare_arrows_outlined)).color,
          scheme.onErrorContainer,
        );
        expect(
          tester.widget<Icon>(find.byIcon(Icons.help_outline)).color,
          scheme.onSurfaceVariant,
        );
      });
    }
  });

  group('FeatureReadinessTile', () {
    testWidgets('explains readiness, responsibilities, fallback, and action',
        (tester) async {
      final semantics = tester.ensureSemantics();
      var actions = 0;

      await tester.pumpWidget(
        _wrap(
          FeatureReadinessTile(
            title: 'Kết nối dữ liệu sức khỏe',
            status: FeatureReadinessStatus.actionRequired,
            statusLabel: 'Cần bạn thiết lập',
            safeExplanation:
                'Chưa có nguồn dữ liệu nào được bạn cho phép kết nối.',
            userAction: 'Chọn một nguồn và xem quyền truy cập.',
            administratorAction: 'Bật nhà cung cấp đã được phê duyệt.',
            safeFallback: 'Bạn vẫn có thể nhập thông tin thủ công.',
            actionLabel: 'Xem cách thiết lập',
            onAction: () => actions++,
          ),
          theme: ClaraTheme.light(polished: true),
        ),
      );

      expect(
        find.bySemanticsLabel(
          'Kết nối dữ liệu sức khỏe. Cần bạn thiết lập. '
          'Chưa có nguồn dữ liệu nào được bạn cho phép kết nối.',
        ),
        findsOneWidget,
      );
      expect(
        find.bySemanticsLabel(
          'Bạn có thể làm: Chọn một nguồn và xem quyền truy cập.',
        ),
        findsOneWidget,
      );
      expect(
        find.bySemanticsLabel(
          'Quản trị viên cần làm: Bật nhà cung cấp đã được phê duyệt.',
        ),
        findsOneWidget,
      );
      expect(
        find.bySemanticsLabel(
          'Trong lúc chờ: Bạn vẫn có thể nhập thông tin thủ công.',
        ),
        findsOneWidget,
      );
      expect(find.textContaining('Traceback'), findsNothing);
      expect(find.textContaining('API key'), findsNothing);

      await tester.tap(find.text('Xem cách thiết lập'));
      expect(actions, 1);
      expect(
        tester.getSize(find.byType(FilledButton)).height,
        greaterThanOrEqualTo(48),
      );
      semantics.dispose();
    });

    for (final entry in <(String, ThemeData)>[
      ('light', ClaraTheme.light(polished: true)),
      ('dark', ClaraTheme.dark(polished: true)),
    ]) {
      testWidgets('uses $entry semantic status colors without raw color values',
          (tester) async {
        await tester.pumpWidget(
          _wrap(
            const Column(
              children: <Widget>[
                FeatureReadinessTile(
                  title: 'Tìm kiếm bằng chứng',
                  status: FeatureReadinessStatus.ready,
                  statusLabel: 'Sẵn sàng',
                  safeExplanation: 'Nguồn đã được kiểm tra.',
                ),
                SizedBox(height: 16),
                FeatureReadinessTile(
                  title: 'Nhận dạng tài liệu',
                  status: FeatureReadinessStatus.unavailable,
                  statusLabel: 'Chưa sẵn sàng',
                  safeExplanation: 'Bạn có thể thử lại sau.',
                ),
              ],
            ),
            theme: entry.$2,
            textScale: 2,
          ),
        );

        expect(tester.takeException(), isNull);
        final context = tester.element(find.byType(FeatureReadinessTile).first);
        final theme = Theme.of(context);
        final readyIcon =
            tester.widget<Icon>(find.byIcon(Icons.check_circle_outline));
        final unavailableIcon =
            tester.widget<Icon>(find.byIcon(Icons.block_outlined));
        expect(
          readyIcon.color,
          theme.extension<ClaraStatusColors>()!.onSuccess,
        );
        expect(unavailableIcon.color, theme.colorScheme.onError);
      });
    }
  });
}
