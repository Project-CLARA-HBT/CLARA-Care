/// Staleness Rejection Taxonomy & User Feedback Codes for CLARA Mobile.
///
/// Categorizes server conflict responses to present structured guidance
/// without losing offline drafts or patient notes.
enum StalenessReason {
  concurrentEdit,
  consultationLeaseExpired,
  consentWithdrawn,
  clinicalPolicyUpdated,
  unknownConflict,
}

class StalenessFeedback {
  const StalenessFeedback({
    required this.reason,
    required this.messageVi,
    required this.messageEn,
    required this.canAutoRefresh,
  });

  final StalenessReason reason;
  final String messageVi;
  final String messageEn;
  final bool canAutoRefresh;

  factory StalenessFeedback.fromServerCode(String? code, int statusCode) {
    final c = (code ?? '').toLowerCase();
    if (statusCode == 403 || c.contains('consent')) {
      return const StalenessFeedback(
        reason: StalenessReason.consentWithdrawn,
        messageVi: 'Bệnh nhân đã thay đổi sự đồng ý xử lý dữ liệu.',
        messageEn: 'Patient consent for data processing has been withdrawn.',
        canAutoRefresh: false,
      );
    }
    if (c.contains('lease')) {
      return const StalenessFeedback(
        reason: StalenessReason.consultationLeaseExpired,
        messageVi: 'Phiên khám độc quyền đã hết hạn.',
        messageEn: 'Consultation lease expired.',
        canAutoRefresh: false,
      );
    }
    if (c.contains('policy')) {
      return const StalenessFeedback(
        reason: StalenessReason.clinicalPolicyUpdated,
        messageVi: 'Chính sách an toàn lâm sàng đã cập nhật phiên bản mới.',
        messageEn: 'Clinical safety policy has been updated.',
        canAutoRefresh: true,
      );
    }
    if (statusCode == 409 || c.contains('version') || c.contains('stale')) {
      return const StalenessFeedback(
        reason: StalenessReason.concurrentEdit,
        messageVi: 'Dữ liệu đã được cập nhật bởi bác sĩ khác. Đang tải lại...',
        messageEn: 'Data updated concurrently by another clinician. Reloading...',
        canAutoRefresh: true,
      );
    }
    return const StalenessFeedback(
      reason: StalenessReason.unknownConflict,
      messageVi: 'Xảy ra xung đột dữ liệu. Vui lòng thử lại.',
      messageEn: 'Data conflict encountered. Please try again.',
      canAutoRefresh: false,
    );
  }
}
