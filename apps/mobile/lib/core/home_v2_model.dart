/// Read models for CLARA /api/v2/home endpoint.
library;

String _str(Object? v) => v?.toString() ?? '';

/// A top next-action card item on Home.
class HomeNextAction {
  const HomeNextAction({
    required this.id,
    required this.title,
    this.description,
    this.kind = 'task',
    this.severity = 'normal',
    this.href,
    this.actionLabel,
    this.sourceIds = const <String>[],
  });

  final String id;
  final String title;
  final String? description;
  final String kind;
  final String severity;
  final String? href;
  final String? actionLabel;
  final List<String> sourceIds;

  factory HomeNextAction.fromJson(Map<String, dynamic> json) {
    final rawSources = json['source_ids'];
    return HomeNextAction(
      id: _str(json['id']),
      title: _str(json['title'] ?? json['title_key'] ?? json['name']),
      description:
          json['description'] == null ? null : _str(json['description']),
      kind: _str(json['kind'] ?? 'task'),
      severity: _str(json['severity'] ?? 'normal').toLowerCase(),
      href: json['href'] == null ? null : _str(json['href']),
      actionLabel:
          json['action_label'] == null ? null : _str(json['action_label']),
      sourceIds: rawSources is List
          ? rawSources.map(_str).toList(growable: false)
          : const <String>[],
    );
  }

  bool get isUrgent => severity == 'urgent' || severity == 'critical';
  bool get isAttention =>
      severity == 'attention' || severity == 'warning' || severity == 'high';
}

/// A schedule item (medication, visit, or care task) for Today.
class HomeScheduleItem {
  const HomeScheduleItem({
    required this.id,
    required this.title,
    required this.kind,
    this.time,
    this.status = 'pending',
    this.subtitle,
    this.dueAt,
    this.completed = false,
    this.extra = const <String, dynamic>{},
  });

  final String id;
  final String title;
  final String kind; // 'medication' | 'visit' | 'task'
  final String? time;
  final String status;
  final String? subtitle;
  final String? dueAt;
  final bool completed;
  final Map<String, dynamic> extra;

  factory HomeScheduleItem.fromJson(Map<String, dynamic> json) {
    final rawStatus = _str(json['status'] ?? 'pending').toLowerCase();
    final isCompleted = rawStatus == 'completed' || json['completed'] == true;
    return HomeScheduleItem(
      id: _str(json['id']),
      title: _str(json['title'] ?? json['name'] ?? json['medication_name']),
      kind: _str(json['kind'] ??
          (json['medication_name'] != null ? 'medication' : 'task')),
      time: json['time'] == null ? null : _str(json['time']),
      status: rawStatus,
      subtitle: json['subtitle'] != null
          ? _str(json['subtitle'])
          : json['dose_text'] != null
              ? _str(json['dose_text'])
              : json['description'] != null
                  ? _str(json['description'])
                  : null,
      dueAt: json['due_at'] != null
          ? _str(json['due_at'])
          : json['scheduled_at'] != null
              ? _str(json['scheduled_at'])
              : null,
      completed: isCompleted,
      extra: json['extra'] is Map
          ? (json['extra'] as Map).cast<String, dynamic>()
          : const <String, dynamic>{},
    );
  }

  HomeScheduleItem copyWith({
    bool? completed,
    String? status,
  }) {
    return HomeScheduleItem(
      id: id,
      title: title,
      kind: kind,
      time: time,
      status: status ?? this.status,
      subtitle: subtitle,
      dueAt: dueAt,
      completed: completed ?? this.completed,
      extra: extra,
    );
  }
}

/// A recent change from verified real source records.
class HomeRecentChange {
  const HomeRecentChange({
    required this.id,
    required this.title,
    this.kind = 'record',
    this.summary,
    this.occurredAt,
    this.source,
  });

  final String id;
  final String title;
  final String kind;
  final String? summary;
  final String? occurredAt;
  final String? source;

  factory HomeRecentChange.fromJson(Map<String, dynamic> json) {
    String? sourceText;
    if (json['source'] is Map) {
      sourceText = _str((json['source'] as Map)['label']);
    } else if (json['source'] != null) {
      sourceText = _str(json['source']);
    }

    return HomeRecentChange(
      id: _str(json['id']),
      title: _str(json['title'] ?? json['name']),
      kind: _str(json['kind'] ?? 'record'),
      summary: json['summary'] != null
          ? _str(json['summary'])
          : json['description'] != null
              ? _str(json['description'])
              : null,
      occurredAt: json['occurred_at'] != null
          ? _str(json['occurred_at'])
          : json['recorded_at'] != null
              ? _str(json['recorded_at'])
              : null,
      source: sourceText,
    );
  }
}

/// Aggregated read model for /api/v2/home.
class HomeV2Model {
  const HomeV2Model({
    this.profileId,
    this.displayName,
    this.topAction,
    this.schedule = const <HomeScheduleItem>[],
    this.recentChanges = const <HomeRecentChange>[],
    this.alerts = const <Map<String, dynamic>>[],
    this.generatedAt,
    this.contextVersion,
    this.hasConnectedHealth = false,
  });

  final String? profileId;
  final String? displayName;
  final HomeNextAction? topAction;
  final List<HomeScheduleItem> schedule;
  final List<HomeRecentChange> recentChanges;
  final List<Map<String, dynamic>> alerts;
  final DateTime? generatedAt;
  final String? contextVersion;
  final bool hasConnectedHealth;

  factory HomeV2Model.fromJson(Map<String, dynamic> json) {
    final root = json['data'] is Map<String, dynamic>
        ? json['data'] as Map<String, dynamic>
        : json;

    final profile = root['profile'] is Map ? root['profile'] as Map : null;
    final rawTopAction = root['top_action'];
    final rawToday = root['today'] ?? root['schedule'] ?? root['tasks'];
    final rawRecent = root['recent_changes'] ?? root['recent_activity'];
    final rawAlerts = root['alerts'];
    final rawIntegration = root['integration_state'];

    final scheduleList = <HomeScheduleItem>[];
    if (rawToday is List) {
      for (final item in rawToday) {
        if (item is Map) {
          scheduleList
              .add(HomeScheduleItem.fromJson(item.cast<String, dynamic>()));
        }
      }
    }

    final recentList = <HomeRecentChange>[];
    if (rawRecent is List) {
      for (final item in rawRecent) {
        if (item is Map) {
          recentList
              .add(HomeRecentChange.fromJson(item.cast<String, dynamic>()));
        }
      }
    }

    final alertsList = <Map<String, dynamic>>[];
    if (rawAlerts is List) {
      for (final item in rawAlerts) {
        if (item is Map) {
          alertsList.add(item.cast<String, dynamic>());
        }
      }
    }

    return HomeV2Model(
      profileId: profile?['id'] == null ? null : _str(profile!['id']),
      displayName: profile?['display_name'] == null
          ? null
          : _str(profile!['display_name']),
      topAction: rawTopAction is Map
          ? HomeNextAction.fromJson(rawTopAction.cast<String, dynamic>())
          : null,
      schedule: scheduleList,
      recentChanges: recentList,
      alerts: alertsList,
      generatedAt: root['generated_at'] != null
          ? DateTime.tryParse(_str(root['generated_at']))
          : null,
      contextVersion:
          root['context_version'] == null ? null : _str(root['context_version']),
      hasConnectedHealth: rawIntegration is Map
          ? rawIntegration['has_connected_health'] == true
          : false,
    );
  }

  bool get isCaughtUp =>
      schedule.isNotEmpty &&
      schedule.every((item) => item.completed) &&
      (topAction == null || (!topAction!.isUrgent && !topAction!.isAttention));
}
