// Accessibility + responsive sweep for the CLARA_Mobile unified experience
// (spec: .kiro/specs/clara-mobile-unified, Phase 7.4 — Req 7.x).
//
// This is the headless portion of the a11y/responsive sweep: it drives the
// unified surfaces that have no brittle initState network side-effects
// (OnboardingFlow, ProfileHub) across phone + tablet widths, a large text
// scaler (A11y clamps to 1.6), and reduced motion, asserting:
//
//   * No layout/build exception (no overflow) at either form factor or scale.
//   * The ≥48dp minimum tap-target invariant on the real rendered controls
//     (`ClaraButton`, `ListTile`).
//   * Stable Vietnamese semantics for the primary controls.
//
// Networked surfaces use deterministic fake clients. Hands-on screen-reader
// runtime QA on real devices remains a separate release task.

import 'dart:convert';

import 'package:clara_mobile/core/a11y.dart';
import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/experience/unified/lifemap_surface.dart';
import 'package:clara_mobile/experience/unified/onboarding_flow.dart';
import 'package:clara_mobile/experience/unified/profile_hub.dart';
import 'package:clara_mobile/theme/clara_theme.dart';
import 'package:clara_mobile/theme/components/clara_button.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_picker/image_picker.dart';

import 'fakes/fakes.dart';

/// Common phone / tablet logical sizes for the responsive sweep.
const Size _phone = Size(390, 844);
const Size _tablet = Size(834, 1112);

class _FakeImagePicker extends ImagePicker {
  @override
  Future<XFile?> pickImage({
    required ImageSource source,
    double? maxWidth,
    double? maxHeight,
    int? imageQuality,
    CameraDevice preferredCameraDevice = CameraDevice.rear,
    bool requestFullMetadata = true,
  }) async {
    return XFile.fromData(
      base64Decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4n'
        'GNgYAAAAAMAASsJTYQAAAAASUVORK5CYII=',
      ),
      name: 'nhan-thuoc.png',
      mimeType: 'image/png',
    );
  }
}

void main() {
  setUp(resetAnalyticsClientForTest);
  tearDown(resetAnalyticsClientForTest);

  /// Wraps [surface] in the polished light theme, at an optional [textScale]
  /// and [reduceMotion] (disableAnimations) MediaQuery.
  Widget wrap(
    Widget surface, {
    double? textScale,
    bool reduceMotion = false,
  }) {
    return MaterialApp(
      theme: ClaraTheme.light(polished: true),
      home: Builder(
        builder: (context) {
          final base = MediaQuery.of(context);
          return MediaQuery(
            data: base.copyWith(
              textScaler:
                  textScale != null ? TextScaler.linear(textScale) : null,
              disableAnimations: reduceMotion,
            ),
            child: surface,
          );
        },
      ),
    );
  }

  List<double> heightsOf(WidgetTester tester, Finder finder) => finder
      .evaluate()
      .map((element) => tester.getSize(find.byWidget(element.widget)).height)
      .toList(growable: false);

  Future<void> setSurface(WidgetTester tester, Size size) async {
    tester.view.physicalSize = size;
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
  }

  group('Unified onboarding — a11y + responsive (Phase 7.4)', () {
    testWidgets('welcome step renders cleanly on phone with ≥48dp actions',
        (tester) async {
      final semantics = tester.ensureSemantics();
      await setSurface(tester, _phone);
      final api = FakeApiClient();
      final session = await FakeSessionStore.authenticated(role: 'normal');

      await tester.pumpWidget(
        wrap(OnboardingFlow(
          apiClient: api,
          sessionStore: session,
          onDone: () {},
        )),
      );
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      // Welcome copy + both primary/secondary actions are present.
      expect(find.text('Chào mừng bạn đến với CLARA'), findsOneWidget);
      expect(find.text('Bắt đầu'), findsOneWidget);
      expect(find.text('Bỏ qua, để sau'), findsOneWidget);

      // Every ClaraButton meets the ≥48dp tap-target minimum.
      final buttons = find.byType(ClaraButton);
      expect(buttons, findsWidgets);
      for (final height in heightsOf(tester, buttons)) {
        expect(height, greaterThanOrEqualTo(A11y.minTapTargetDimension));
      }

      semantics.dispose();
    });

    testWidgets('welcome step renders cleanly on tablet width', (tester) async {
      await setSurface(tester, _tablet);
      final api = FakeApiClient();
      final session = await FakeSessionStore.authenticated(role: 'normal');

      await tester.pumpWidget(
        wrap(OnboardingFlow(
          apiClient: api,
          sessionStore: session,
          onDone: () {},
        )),
      );
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('Chào mừng bạn đến với CLARA'), findsOneWidget);
    });

    testWidgets('onboarding renders without overflow at large text scale',
        (tester) async {
      await setSurface(tester, _phone);
      final api = FakeApiClient();
      final session = await FakeSessionStore.authenticated(role: 'normal');

      await tester.pumpWidget(
        wrap(
          OnboardingFlow(
            apiClient: api,
            sessionStore: session,
            onDone: () {},
          ),
          textScale: 1.6,
        ),
      );
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('Chào mừng bạn đến với CLARA'), findsOneWidget);
    });

    testWidgets('reduced motion: advancing to basics settles with no exception',
        (tester) async {
      await setSurface(tester, _phone);
      final api = FakeApiClient();
      final session = await FakeSessionStore.authenticated(role: 'normal');

      await tester.pumpWidget(
        wrap(
          OnboardingFlow(
            apiClient: api,
            sessionStore: session,
            onDone: () {},
          ),
          reduceMotion: true,
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Bắt đầu'));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      // Step 2 (basics) is now shown.
      expect(find.text('Một vài thông tin cơ bản'), findsOneWidget);
    });
  });

  group('Unified Profile hub — a11y + responsive (Phase 7.4)', () {
    testWidgets('renders entries on phone with ≥48dp list rows',
        (tester) async {
      await setSurface(tester, _phone);
      final session = await FakeSessionStore.authenticated(role: 'normal');

      await tester.pumpWidget(
        wrap(ProfileHub(
          apiClient: FakeApiClient(),
          sessionStore: session,
          resolver: MobileFeatureFlagResolver(summary: const {
            'feature_flags': {},
          }),
          role: 'normal',
          phrBody: const SizedBox(height: 40, child: Text('PHR_BODY')),
        )),
      );
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      // Core consumer entries are always listed for a normal user.
      expect(find.text('Chuẩn bị đi khám'), findsOneWidget);
      expect(find.text('Người thân & chia sẻ'), findsOneWidget);
      expect(find.text('Cài đặt'), findsOneWidget);

      // Every ListTile row meets the ≥48dp minimum tap target.
      final tiles = find.byType(ListTile);
      expect(tiles, findsWidgets);
      for (final height in heightsOf(tester, tiles)) {
        expect(height, greaterThanOrEqualTo(A11y.minTapTargetDimension));
      }
    });

    testWidgets('renders on tablet width without overflow', (tester) async {
      await setSurface(tester, _tablet);
      final session = await FakeSessionStore.authenticated(role: 'normal');

      await tester.pumpWidget(
        wrap(ProfileHub(
          apiClient: FakeApiClient(),
          sessionStore: session,
          resolver: MobileFeatureFlagResolver(summary: const {
            'feature_flags': {},
          }),
          role: 'normal',
          phrBody: const SizedBox(height: 40, child: Text('PHR_BODY')),
        )),
      );
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('Cài đặt'), findsOneWidget);
    });

    testWidgets('renders without overflow at large text scale', (tester) async {
      await setSurface(tester, _phone);
      final session = await FakeSessionStore.authenticated(role: 'normal');

      await tester.pumpWidget(
        wrap(
          ProfileHub(
            apiClient: FakeApiClient(),
            sessionStore: session,
            resolver: MobileFeatureFlagResolver(summary: const {
              'feature_flags': {},
            }),
            role: 'normal',
            phrBody: const SizedBox(height: 40, child: Text('PHR_BODY')),
          ),
          textScale: 1.6,
        ),
      );
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('Cài đặt'), findsOneWidget);
    });
  });

  group('Unified LifeMap — a11y + responsive (Phase 12.3)', () {
    Future<void> pumpLifeMap(
      WidgetTester tester, {
      required Size size,
      double? textScale,
      bool reduceMotion = false,
      ImagePicker? imagePicker,
    }) async {
      await setSurface(tester, size);
      final api = FakeApiClient()
        ..stub('getMobileSummary', response: {
          'feature_flags': {
            'lifemap_capture': true,
            'lifemap_next_question_v2': true,
            'lifemap_ask_ai': true,
            'lifemap_ai_summaries': true,
            'lifemap_ai_review_findings': true,
            'lifemap_baselines_v2': true,
          },
        })
        ..stub('startLifeMapArtifactCapture', response: {
          'id': 'capture-session-1',
          'status': 'draft',
          'candidates': [],
        })
        ..stub('uploadLifeMapCaptureArtifact', response: {
          'id': 'artifact-1',
          'job': {'id': 'job-1', 'status': 'queued'},
        })
        ..stub('getLifeMapBaselines', response: {'data': []})
        ..stub('getLifeMapToday', response: {
          'episodes': [
            {
              'id': 'episode-1',
              'title': 'Theo dõi giấc ngủ',
              'priority': 'routine',
            },
          ],
          'tasks': [
            {'id': 'task-1', 'title': 'Ghi lại giờ đi ngủ'},
          ],
        })
        ..stub('getLifeMapDisputes', response: {'data': []});
      final session = await FakeSessionStore.authenticated(role: 'normal');
      await tester.pumpWidget(
        wrap(
          LifeMapSurface(
            apiClient: api,
            sessionStore: session,
            imagePicker: imagePicker,
          ),
          textScale: textScale,
          reduceMotion: reduceMotion,
        ),
      );
      await tester.pumpAndSettle();
    }

    testWidgets('phone exposes labelled Ask and Capture controls',
        (tester) async {
      final semantics = tester.ensureSemantics();
      await pumpLifeMap(tester, size: _phone);

      expect(tester.takeException(), isNull);
      expect(find.bySemanticsLabel('Bạn muốn tìm điều gì?'), findsOneWidget);
      expect(find.text('Nhìn lại LifeMap'), findsOneWidget);
      expect(find.text('Tạo tóm tắt'), findsOneWidget);
      await tester.scrollUntilVisible(
        find.text('Ghi nhận nhanh'),
        500,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      expect(find.bySemanticsLabel('Điều bạn muốn ghi lại'), findsOneWidget);
      expect(find.text('Chụp ảnh'), findsOneWidget);
      expect(find.text('Chọn ảnh'), findsOneWidget);
      expect(tester.takeException(), isNull);
      semantics.dispose();
    });

    testWidgets('image capture remains a reviewable in-memory draft',
        (tester) async {
      final semantics = tester.ensureSemantics();
      await pumpLifeMap(
        tester,
        size: _phone,
        imagePicker: _FakeImagePicker(),
      );
      await tester.scrollUntilVisible(
        find.text('Chọn ảnh'),
        500,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.ensureVisible(find.text('Chọn ảnh'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Chọn ảnh'));
      await tester.pumpAndSettle();

      expect(find.text('Bản nháp nguồn đang xử lý'), findsOneWidget);
      expect(
        find.textContaining('chỉ giữ tạm trong bộ nhớ khi xem xét'),
        findsOneWidget,
      );
      expect(
        find.text(
          'Nguồn đang được đọc. Chưa có dữ liệu nào được xác nhận.',
        ),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
      semantics.dispose();
    });

    testWidgets('tablet and 1.6x text render without overflow', (tester) async {
      await pumpLifeMap(tester, size: _tablet, textScale: 1.6);

      expect(tester.takeException(), isNull);
      await tester.scrollUntilVisible(
        find.text('Theo dõi giấc ngủ'),
        500,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      expect(find.text('Theo dõi giấc ngủ'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('reduced-motion phone flow remains stable', (tester) async {
      await pumpLifeMap(tester, size: _phone, reduceMotion: true);

      expect(tester.takeException(), isNull);
      await tester.scrollUntilVisible(
        find.text('Ghi nhận nhanh'),
        500,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      expect(find.text('Ghi nhận nhanh'), findsOneWidget);
    });
  });
}
