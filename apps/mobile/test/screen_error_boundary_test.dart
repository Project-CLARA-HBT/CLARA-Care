// Widget tests for screen-level exception containment added in task 12.5:
//   * [ScreenErrorBoundary] — a child that throws during build is contained in
//     place: the clean, non-PII [ErrorRetryView] fallback is shown, the app
//     does not crash, and no raw stack trace text is leaked to the user
//     (Requirement 11.4).
//   * Retry reconstructs the guarded subtree so a transient failure recovers.
//   * [ScreenErrorBoundary.guard] contains thrown async errors.
//
// No platform channels or live network are used (Requirement 14.6).

import 'package:clara_mobile/widgets/error_retry_view.dart';
import 'package:clara_mobile/widgets/screen_error_boundary.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// A widget whose build throws unless [shouldThrow] reports false. The error
/// message embeds a recognizable token so the test can assert it never reaches
/// the UI.
const String _secretStackToken = 'INTERNAL_STACK_TRACE_SECRET';

class _Bomb extends StatelessWidget {
  const _Bomb({required this.shouldThrow});

  final bool Function() shouldThrow;

  @override
  Widget build(BuildContext context) {
    if (shouldThrow()) {
      throw StateError(_secretStackToken);
    }
    return const Text('recovered-body');
  }
}

void main() {
  setUpAll(ScreenErrorBoundary.install);
  tearDownAll(ScreenErrorBoundary.debugReset);

  testWidgets(
      'throwing child renders the fallback without crashing or leaking a stack '
      'trace', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ScreenErrorBoundary(
            onRetry: () {},
            child: _Bomb(shouldThrow: () => true),
          ),
        ),
      ),
    );

    // The framework records the contained exception; consume it so the harness
    // does not fail the test (in production this never reaches the user).
    expect(tester.takeException(), isA<StateError>());

    // The clean fallback is shown in place of the failed subtree.
    expect(find.byKey(const Key('error-retry-view')), findsOneWidget);
    expect(find.text(kDefaultErrorMessage), findsOneWidget);
    expect(find.text(kDefaultRetryLabel), findsOneWidget);

    // No raw stack trace / exception detail is leaked to the user.
    expect(find.textContaining(_secretStackToken), findsNothing);
    expect(find.textContaining('StateError'), findsNothing);
  });

  testWidgets('retry reconstructs the subtree so a transient failure recovers',
      (tester) async {
    var fail = true;
    var retries = 0;

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ScreenErrorBoundary(
            onRetry: () {
              retries++;
              fail = false; // the transient condition clears
            },
            child: _Bomb(shouldThrow: () => fail),
          ),
        ),
      ),
    );

    expect(tester.takeException(), isA<StateError>());
    expect(find.byKey(const Key('error-retry-view')), findsOneWidget);
    expect(find.text('recovered-body'), findsNothing);

    // Tap retry: onRetry runs and the subtree is rebuilt from scratch.
    await tester.tap(find.text(kDefaultRetryLabel));
    await tester.pumpAndSettle();

    expect(retries, 1);
    expect(find.text('recovered-body'), findsOneWidget);
    expect(find.byKey(const Key('error-retry-view')), findsNothing);
  });

  testWidgets('a custom, sanitized message is shown when provided',
      (tester) async {
    const customMessage = 'Không thể hiển thị màn hình này.';
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ScreenErrorBoundary(
            message: customMessage,
            onRetry: () {},
            child: _Bomb(shouldThrow: () => true),
          ),
        ),
      ),
    );

    expect(tester.takeException(), isA<StateError>());
    expect(find.text(customMessage), findsOneWidget);
    expect(find.textContaining(_secretStackToken), findsNothing);
  });

  testWidgets('install() is idempotent and reports installed state',
      (tester) async {
    expect(ScreenErrorBoundary.isInstalled, isTrue);
    ScreenErrorBoundary.install();
    ScreenErrorBoundary.install();
    expect(ScreenErrorBoundary.isInstalled, isTrue);
  });

  test('guard contains a thrown async error and reports it for logging',
      () async {
    Object? logged;
    final result = await ScreenErrorBoundary.guard<int>(
      () async => throw StateError(_secretStackToken),
      onError: (error, _) => logged = error,
    );

    expect(result, isNull);
    expect(logged, isA<StateError>());
  });

  test('guard returns the value when no error is thrown', () async {
    final result = await ScreenErrorBoundary.guard<int>(() async => 42);
    expect(result, 42);
  });
}
