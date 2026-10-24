import 'lifemap_client_contract.dart';

/// Bitemporal timeline perspectives for longitudinal health tracking.
enum LifeMapTimelinePerspective {
  validTime('valid_time', 'Thời gian diễn ra', 'Occurred Time (Valid Time)',
      'Trật tự theo thời điểm triệu chứng xuất hiện hoặc dùng thuốc thực tế.',
      'Order based on real-world clinical occurrence or medication administration.'),
  systemTime('system_time', 'Thời gian ghi nhận', 'Recorded Time (System Time)',
      'Trật tự theo thời điểm hệ thống hoặc cơ sở y tế ghi nhận dữ liệu.',
      'Order based on when the record was ingested or synchronized into the system.');

  const LifeMapTimelinePerspective(
    this.key,
    this.viLabel,
    this.enLabel,
    this.viDescription,
    this.enDescription,
  );

  final String key;
  final String viLabel;
  final String enLabel;
  final String viDescription;
  final String enDescription;

  String label(String locale) =>
      locale.toLowerCase().startsWith('en') ? enLabel : viLabel;

  String description(String locale) =>
      locale.toLowerCase().startsWith('en') ? enDescription : viDescription;
}

/// Period filter options for the longitudinal timeline.
enum LifeMapPeriodFilter {
  recent('recent', 'Gần đây (7 ngày)', 'Recent (7 days)', Duration(days: 7)),
  month('month', 'Tháng này', 'This Month', Duration(days: 30)),
  year('year', 'Năm nay', 'This Year', Duration(days: 365)),
  all('all', 'Tất cả', 'All History', null);

  const LifeMapPeriodFilter(
    this.key,
    this.viLabel,
    this.enLabel,
    this.duration,
  );

  final String key;
  final String viLabel;
  final String enLabel;
  final Duration? duration;

  String label(String locale) =>
      locale.toLowerCase().startsWith('en') ? enLabel : viLabel;

  bool matches(DateTime? dateTime, DateTime now) {
    if (duration == null || dateTime == null) return true;
    final threshold = now.subtract(duration!);
    return dateTime.isAfter(threshold) || dateTime.isAtSameMomentAs(threshold);
  }
}

/// Event category filter options for the timeline.
enum LifeMapEventTypeFilter {
  all('all', 'Tất cả', 'All', null),
  medication('medication', 'Thuốc', 'Medications', {'medication', 'medication_change', 'prescription'}),
  symptom('symptom', 'Triệu chứng & Bệnh', 'Symptoms & Conditions', {'symptom', 'condition', 'diagnosis'}),
  visit('visit', 'Lịch khám', 'Visits', {'visit', 'encounter', 'appointment'}),
  result('result', 'Kết quả xét nghiệm', 'Lab & Test Results', {'result', 'lab', 'diagnostic'}),
  measurement('measurement', 'Chỉ số sinh hiệu', 'Measurements', {'measurement', 'vital', 'observation'}),
  document('document', 'Tài liệu y tế', 'Documents', {'document', 'report', 'attachment'});

  const LifeMapEventTypeFilter(
    this.key,
    this.viLabel,
    this.enLabel,
    this.matchingKinds,
  );

  final String key;
  final String viLabel;
  final String enLabel;
  final Set<String>? matchingKinds;

  String label(String locale) =>
      locale.toLowerCase().startsWith('en') ? enLabel : viLabel;

  bool matches(String? kind) {
    if (matchingKinds == null) return true;
    if (kind == null) return false;
    final normalized = kind.toLowerCase().trim();
    return matchingKinds!.contains(normalized);
  }
}

/// A structured longitudinal timeline event.
class LifeMapTimelineEvent {
  const LifeMapTimelineEvent({
    required this.id,
    required this.eventType,
    required this.truthState,
    required this.occurredAt,
    required this.recordedAt,
    required this.title,
    this.summary,
    this.payload = const <String, dynamic>{},
    this.provenance = const <String, dynamic>{},
    this.sourceKind,
    this.episodeId,
    this.revisionNo = 1,
    this.revisions = const <Map<String, dynamic>>[],
  });

  factory LifeMapTimelineEvent.fromJson(Map<String, dynamic> json) {
    DateTime parseDate(Object? raw) {
      if (raw == null) return DateTime.now().toUtc();
      if (raw is DateTime) return raw.toUtc();
      try {
        return DateTime.parse(raw.toString()).toUtc();
      } catch (_) {
        return DateTime.now().toUtc();
      }
    }

    final payload = json['payload'];
    final provenance = json['provenance'];
    final rawRevisions = json['revisions'];

    String extractTitle() {
      if (json['title'] != null && json['title'].toString().isNotEmpty) {
        return json['title'].toString();
      }
      if (payload is Map && payload['title'] != null) {
        return payload['title'].toString();
      }
      if (payload is Map && payload['text'] != null) {
        final text = payload['text'].toString();
        return text.length > 60 ? '${text.substring(0, 60)}...' : text;
      }
      final type = json['event_type']?.toString() ?? 'Sự kiện y tế';
      return type;
    }

    String? extractSummary() {
      if (json['summary'] != null && json['summary'].toString().isNotEmpty) {
        return json['summary'].toString();
      }
      if (payload is Map && payload['summary'] != null) {
        return payload['summary'].toString();
      }
      if (payload is Map && payload['description'] != null) {
        return payload['description'].toString();
      }
      return null;
    }

    final revisionsList = <Map<String, dynamic>>[];
    if (rawRevisions is List) {
      for (final r in rawRevisions) {
        if (r is Map) revisionsList.add(r.cast<String, dynamic>());
      }
    }

    int parseRevision(Object? raw) {
      if (raw is int) return raw;
      if (raw == null) return 1;
      try {
        return int.parse(raw.toString());
      } catch (_) {
        return 1;
      }
    }

    final revNo = parseRevision(json['revision_no']);

    return LifeMapTimelineEvent(
      id: json['id']?.toString() ?? '',
      eventType: json['event_type']?.toString() ?? 'observation',
      truthState: LifeMapClientState.parse(json['truth_state']),
      occurredAt: parseDate(json['occurred_at'] ?? json['effective_at']),
      recordedAt: parseDate(json['recorded_at'] ?? json['created_at']),
      title: extractTitle(),
      summary: extractSummary(),
      payload: payload is Map ? payload.cast<String, dynamic>() : const <String, dynamic>{},
      provenance: provenance is Map ? provenance.cast<String, dynamic>() : const <String, dynamic>{},
      sourceKind: json['source_kind']?.toString() ?? (provenance is Map ? provenance['source_kind']?.toString() : null),
      episodeId: json['episode_id']?.toString(),
      revisionNo: revNo,
      revisions: revisionsList,
    );
  }

  final String id;
  final String eventType;
  final LifeMapClientState truthState;
  final DateTime occurredAt; // Valid Time (\tau_v)
  final DateTime recordedAt; // Transaction Time (\tau_k)
  final String title;
  final String? summary;
  final Map<String, dynamic> payload;
  final Map<String, dynamic> provenance;
  final String? sourceKind;
  final String? episodeId;
  final int revisionNo;
  final List<Map<String, dynamic>> revisions;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'id': id,
        'event_type': eventType,
        'truth_state': truthState.wireValue,
        'occurred_at': occurredAt.toIso8601String(),
        'recorded_at': recordedAt.toIso8601String(),
        'title': title,
        if (summary != null) 'summary': summary,
        'payload': payload,
        'provenance': provenance,
        if (sourceKind != null) 'source_kind': sourceKind,
        if (episodeId != null) 'episode_id': episodeId,
        'revision_no': revisionNo,
        'revisions': revisions,
      };
}

/// Vietnamese-first strings dictionary for the LifeMap longitudinal timeline.
class LifeMapTimelineStrings {
  const LifeMapTimelineStrings._();

  static bool _isEn(String locale) => locale.toLowerCase().startsWith('en');

  static String timelineTitle(String locale) =>
      _isEn(locale) ? 'Health Timeline' : 'Dòng thời gian sức khỏe';

  static String timelineSubtitle(String locale) => _isEn(locale)
      ? 'Longitudinal health history tracking clinical events, care episodes, and medical records.'
      : 'Dòng thời gian sức khỏe kết hợp mốc hành trình, đơn thuốc, lịch khám và xét nghiệm.';

  static String perspectiveLabel(String locale) =>
      _isEn(locale) ? 'Time Axis:' : 'Trục thời gian:';

  static String periodFilterLabel(String locale) =>
      _isEn(locale) ? 'Time Period:' : 'Khoảng thời gian:';

  static String categoryFilterLabel(String locale) =>
      _isEn(locale) ? 'Event Types:' : 'Loại sự kiện:';

  static String searchPlaceholder(String locale) =>
      _isEn(locale) ? 'Search timeline events...' : 'Tìm kiếm sự kiện, thuốc, triệu chứng...';

  static String emptyTitle(String locale) =>
      _isEn(locale) ? 'No timeline events found' : 'Không có sự kiện nào';

  static String emptyDescription(String locale) => _isEn(locale)
      ? 'No health records match your selected filters or search query.'
      : 'Không có bản ghi y tế nào phù hợp với bộ lọc hoặc từ khóa tìm kiếm đã chọn.';

  static String offlineBannerTitle(String locale) =>
      _isEn(locale) ? 'Offline Cached View' : 'Chế độ ngoại tuyến';

  static String offlineBannerDescription(String locale, String cachedAtFormatted) =>
      _isEn(locale)
          ? 'Showing cached data saved at $cachedAtFormatted. Modifications require an active connection.'
          : 'Hiển thị bản sao lưu tạm lúc $cachedAtFormatted. Các thao tác chỉnh sửa chỉ khả dụng khi có kết nối mạng.';

  static String revisionInspectorTitle(String locale) =>
      _isEn(locale) ? 'Revision History' : 'Lịch sử sửa đổi bản ghi';

  static String revisionInspectorDescription(String locale) => _isEn(locale)
      ? 'Inspect exact fact revisions, clinical reasons, and audit trails.'
      : 'Xem các phiên bản sửa đổi, căn cứ ghi nhận và lịch sử kiểm toán.';

  static String revisionBadge(String locale, int revision) =>
      _isEn(locale) ? 'Revision $revision' : 'Phiên bản $revision';

  static String reasonLabel(String locale) =>
      _isEn(locale) ? 'Reason / Basis:' : 'Căn cứ ghi nhận:';

  static String correctAction(String locale) =>
      _isEn(locale) ? 'Correct Record' : 'Chỉnh sửa đính chính';

  static String disputeAction(String locale) =>
      _isEn(locale) ? 'Dispute' : 'Mở khiếu nại';

  static String close(String locale) =>
      _isEn(locale) ? 'Close' : 'Đóng';

  static String sourceKindLabel(String locale, String? sourceKind) {
    if (sourceKind == null || sourceKind.isEmpty) {
      return _isEn(locale) ? 'System' : 'Hệ thống';
    }
    switch (sourceKind.toLowerCase()) {
      case 'clinician':
      case 'doctor':
        return _isEn(locale) ? 'Clinician' : 'Bác sĩ';
      case 'patient':
      case 'self_reported':
        return _isEn(locale) ? 'Patient' : 'Bệnh nhân tự nhập';
      case 'ocr':
      case 'document_scan':
        return _isEn(locale) ? 'Document OCR' : 'Quét tài liệu (OCR)';
      case 'device':
      case 'connected_health':
        return _isEn(locale) ? 'Connected Device' : 'Thiết bị đo';
      case 'council':
        return _isEn(locale) ? 'Medical Council' : 'Hội chẩn AI';
      default:
        return sourceKind;
    }
  }
}
