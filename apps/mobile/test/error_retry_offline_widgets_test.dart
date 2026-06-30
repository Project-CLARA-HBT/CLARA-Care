// Widget tests for the shared offline/error primitives added in task 12.1:
//   * [ErrorRetryView] — the retry control invokes the supplied callback
//     (Requirement 9.1).
//   * [OfflineBanner] — appears only while offline and follows connectivity
//     transitions (Requirement 9.1, 9.5).
//   * [OfflineMutationGuard] — while offline a mutation is blocked, the user is
//     informed, and entered input is preserved for retry (Requirement 9.4, 9.5;
//     Property P12).
//
// The real [DefaultConnectivityService] backs the tests (it owns no platform
// plugin), so connectivity is driven deterministically via `setOnline` with no
// platform channels or live network (Requirement 14.6).

import 'package:clara_mobile/core/connectivity_service.dart';
import 'package:clara_mobile/widgets/error_retry_view.dart';
import 'package:clara_mobile/widgets/offline_banner.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// A minimal data surface that mirrors how a real screen wires the primitives:
/// an [OfflineBanner], a text input, and a save button guarded by an
/// [OfflineMutationGuard].
class _GuardedForm extends StatefulWidget {
  const _GuardedForm({required this.connectivity, required this.onMutate});

  final ConnectivityService connectivity;
  final Future<void> Function() onMutate;

  @override
  State<_GuardedForm> createState() => _GuardedFormState();
}

class _GuardedFormState extends State<_GuardedForm> {
  static const _guard = OfflineMutationGuard();
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    await _guard.run(
      isOnline: widget.connectivity.currentValue,
      mutate: widget.onMutate,
      onBlocked: (message) => ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(message))),
    );
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: Scaffold(
        body: Column(
          children: [
            OfflineBanner(connectivity: widget.connectivity),
            TextField(
              controller: _controller,
              decoration: const InputDecoration(labelText: 'Ghi chú'),
            ),
            FilledButton(onPressed: _save, child: const Text('Lưu')),
          ],
        ),
      ),
    );
  }
}

void main() {
  testWidgets('ErrorRetryView retry control invokes the callback',
      (tester) async {
    var retried = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ErrorRetryView(
            message: 'Không thể tải dữ liệu.',
            onRetry: () => retried++,
          ),
        ),
      ),
    );

    expect(find.text('Không thể tải dữ liệu.'), findsOneWidget);
    expect(find.byKey(const Key('error-retry-view')), findsOneWidget);

    await tester.tap(find.text(kDefaultRetryLabel));
    await tester.pump();

    expect(retried, 1);
  });

  testWidgets('OfflineBanner is hidden online and shows when offline',
      (tester) async {
    final connectivity = DefaultConnectivityService(initialValue: true);
    addTearDown(connectivity.dispose);

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: OfflineBanner(connectivity: connectivity)),
      ),
    );
    await tester.pump();

    // Online: banner collapsed.
    expect(find.byKey(const Key('offline-banner')), findsNothing);

    // Go offline: banner appears with non-PII Vietnamese copy.
    connectivity.setOnline(false);
    await tester.pump();
    expect(find.byKey(const Key('offline-banner')), findsOneWidget);
    expect(find.text(kDefaultOfflineMessage), findsOneWidget);

    // Reconnect: banner collapses again.
    connectivity.setOnline(true);
    await tester.pump();
    expect(find.byKey(const Key('offline-banner')), findsNothing);
  });

  testWidgets(
      'offline blocks the mutation, informs the user, and preserves input',
      (tester) async {
    final connectivity = DefaultConnectivityService(initialValue: false);
    addTearDown(connectivity.dispose);

    var mutateCalls = 0;
    await tester.pumpWidget(_GuardedForm(
      connectivity: connectivity,
      onMutate: () async => mutateCalls++,
    ));
    await tester.pump();

    // User enters input while offline.
    await tester.enterText(find.byType(TextField), 'liều 5mg');

    // Tap save while offline.
    await tester.tap(find.text('Lưu'));
    await tester.pump();

    // The mutation was NOT invoked (blocked), the user is informed, and the
    // entered input is preserved (Property P12, Req 9.5).
    expect(mutateCalls, 0);
    expect(find.text(kOfflineMutationBlockedMessage), findsOneWidget);
    expect(find.text('liều 5mg'), findsOneWidget);

    // Reconnect, then retry: the mutation now runs and input is still intact.
    connectivity.setOnline(true);
    await tester.pump();
    await tester.tap(find.text('Lưu'));
    await tester.pump();

    expect(mutateCalls, 1);
    expect(find.text('liều 5mg'), findsOneWidget);
  });

  test('OfflineMutationGuard.evaluate gates strictly on connectivity', () {
    const guard = OfflineMutationGuard();
    expect(guard.evaluate(isOnline: true).allowed, isTrue);
    expect(guard.evaluate(isOnline: true).message, isNull);

    final blocked = guard.evaluate(isOnline: false);
    expect(blocked.allowed, isFalse);
    expect(blocked.blocked, isTrue);
    expect(blocked.message, kOfflineMutationBlockedMessage);
  });
}
