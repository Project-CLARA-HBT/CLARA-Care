import 'package:clara_mobile/core/dispatch_lifecycle.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('DispatchLifecycleRecord State Progression', () {
    test('initializes in pending state and is non-terminal', () {
      final record = DispatchLifecycleRecord(
        attemptId: 'att-123',
        status: DispatchStatus.pending,
        startTime: DateTime.now(),
      );
      expect(record.isTerminal, isFalse);
      expect(record.hasValidReceipt, isFalse);
    });

    test('transitions to timedOut with clean localized error and terminal state', () {
      final start = DateTime.now();
      final record = DispatchLifecycleRecord(
        attemptId: 'att-123',
        status: DispatchStatus.dispatched,
        startTime: start,
      );

      final timedOut = record.toTimedOut();
      expect(timedOut.isTerminal, isTrue);
      expect(timedOut.status, equals(DispatchStatus.timedOut));
      expect(timedOut.errorMessage, contains('Quá thời gian phản hồi'));
      expect(timedOut.endTime, isNotNull);
    });

    test('transitions to completed with provider receipt digest', () {
      final start = DateTime.now();
      final record = DispatchLifecycleRecord(
        attemptId: 'att-123',
        status: DispatchStatus.dispatched,
        startTime: start,
      );

      final completed = record.toCompleted(receiptDigest: 'receipt-sha256-hex');
      expect(completed.isTerminal, isTrue);
      expect(completed.status, equals(DispatchStatus.completed));
      expect(completed.hasValidReceipt, isTrue);
      expect(completed.providerReceiptDigest, equals('receipt-sha256-hex'));
    });
  });
}
