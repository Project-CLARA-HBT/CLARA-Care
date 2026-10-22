/// Model dispatch lifecycle state machine for CLARA Mobile.
///
/// Ensures failed, stalled, or timed-out model dispatches surface
/// clean recoverable errors without manufacturing synthetic results.
enum DispatchStatus {
  idle,
  pending,
  dispatched,
  completed,
  timedOut,
  failed,
}

class DispatchLifecycleRecord {
  const DispatchLifecycleRecord({
    required this.attemptId,
    required this.status,
    required this.startTime,
    this.errorMessage,
    this.endTime,
    this.providerReceiptDigest,
  });

  final String attemptId;
  final DispatchStatus status;
  final DateTime startTime;
  final DateTime? endTime;
  final String? errorMessage;
  final String? providerReceiptDigest;

  bool get isTerminal =>
      status == DispatchStatus.completed ||
      status == DispatchStatus.timedOut ||
      status == DispatchStatus.failed;

  bool get hasValidReceipt =>
      providerReceiptDigest != null && providerReceiptDigest!.isNotEmpty;

  DispatchLifecycleRecord toTimedOut() {
    return DispatchLifecycleRecord(
      attemptId: attemptId,
      status: DispatchStatus.timedOut,
      startTime: startTime,
      endTime: DateTime.now(),
      errorMessage: 'Quá thời gian phản hồi từ mô hình AI. Vui lòng thử lại.',
    );
  }

  DispatchLifecycleRecord toFailed(String message) {
    return DispatchLifecycleRecord(
      attemptId: attemptId,
      status: DispatchStatus.failed,
      startTime: startTime,
      endTime: DateTime.now(),
      errorMessage: message,
    );
  }

  DispatchLifecycleRecord toCompleted({required String receiptDigest}) {
    return DispatchLifecycleRecord(
      attemptId: attemptId,
      status: DispatchStatus.completed,
      startTime: startTime,
      endTime: DateTime.now(),
      providerReceiptDigest: receiptDigest,
    );
  }
}
