// Family surface for the CLARA_Mobile unified experience
// (clara-mobile-unified).
//
// `FamilySurface` is where the user manages MINIMAL, consent-based sharing with
// the people who support them ("Chia sẻ tối thiểu với người hỗ trợ"). Sharing
// is always opt-in and revocable: the user invites a supporter, sees the active
// access grants, acknowledges notifications, and can revoke access at any time.
// No medical advice or diagnosis lives here — CLARA is a clinical assistant,
// not a doctor.
//
// It loads three regions independently (relationships, notifications, access
// grants). If a secondary region fails it is simply omitted; a combined error
// is shown only when the primary relationships call fails. Loading uses
// skeletons, failures reuse `ErrorRetryView`, and empty regions use
// `ClaraEmptyState`. All copy is Vietnamese-first and PII-free where possible.

import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/session_store.dart';
import '../../theme/components/clara_button.dart';
import '../../theme/components/clara_card.dart';
import '../../theme/components/section_header.dart';
import '../../theme/tokens.dart';
import '../../widgets/error_retry_view.dart';
import '../states/empty_state.dart';
import '../states/skeleton.dart';

String _str(Object? value) => value == null ? '' : value.toString();

/// Returns the first non-empty stringified value in [values], or `''`.
String _firstNonEmpty(List<Object?> values) {
  for (final value in values) {
    final s = _str(value).trim();
    if (s.isNotEmpty) return s;
  }
  return '';
}

/// Extracts a list of maps from a response that may nest the list under a
/// `data`/`items`/`results` key or expose it as a top-level array under one of
/// [keys]. Mirrors how the other unified surfaces parse defensively.
List<Map<String, dynamic>> _asMapList(
    Map<String, dynamic> data, List<String> keys) {
  Object? raw;
  for (final key in keys) {
    if (data[key] != null) {
      raw = data[key];
      break;
    }
  }
  raw ??= data['data'] ?? data['items'] ?? data['results'];
  final out = <Map<String, dynamic>>[];
  if (raw is List) {
    for (final item in raw) {
      if (item is Map) {
        out.add(item.cast<String, dynamic>());
      }
    }
  }
  return out;
}

/// A supporter the user shares with.
class _Relationship {
  const _Relationship({required this.title, required this.subtitle});

  factory _Relationship.fromJson(Map<String, dynamic> json) {
    final title = _firstNonEmpty(<Object?>[
      json['supporter_label'],
      json['display_name'],
      json['name'],
      json['relationship'],
      json['role'],
      json['email'],
    ]);
    final subtitle = _firstNonEmpty(<Object?>[
      json['object_type'],
      json['relationship'],
      json['role'],
      json['status'],
    ]);
    return _Relationship(
      title: title.isEmpty ? 'Người hỗ trợ' : title,
      subtitle: subtitle,
    );
  }

  final String title;
  final String subtitle;
}

/// A pending family notification awaiting acknowledgement.
class _FamilyNotification {
  const _FamilyNotification({
    required this.grantId,
    required this.taskId,
    required this.title,
    required this.purpose,
  });

  factory _FamilyNotification.fromJson(Map<String, dynamic> json) {
    final grantId = _firstNonEmpty(<Object?>[
      json['grant_id'],
      json['access_grant_id'],
      json['grantId'],
    ]);
    final taskId = _firstNonEmpty(<Object?>[
      json['task_id'],
      json['id'],
      json['taskId'],
    ]);
    final title = _firstNonEmpty(<Object?>[
      json['title'],
      json['message'],
      json['summary'],
      json['type'],
    ]);
    return _FamilyNotification(
      grantId: grantId,
      taskId: taskId,
      title: title.isEmpty ? 'Thông báo mới' : title,
      purpose: _str(json['purpose']),
    );
  }

  final String grantId;
  final String taskId;
  final String title;
  final String purpose;
}

/// An active access grant shared with a supporter.
class _AccessGrant {
  const _AccessGrant({
    required this.id,
    required this.title,
    required this.subtitle,
    required this.expiresAt,
  });

  factory _AccessGrant.fromJson(Map<String, dynamic> json) {
    final id = _firstNonEmpty(<Object?>[
      json['id'],
      json['grant_id'],
      json['grantId'],
    ]);
    final title = _firstNonEmpty(<Object?>[
      json['display_name'],
      json['grantee_name'],
      json['name'],
      json['email'],
      json['relationship'],
    ]);
    final subtitle = _firstNonEmpty(<Object?>[
      json['scope'],
      json['relationship'],
      json['status'],
    ]);
    return _AccessGrant(
      id: id,
      title: title.isEmpty ? 'Quyền truy cập' : title,
      subtitle: subtitle,
      expiresAt: _str(json['expires_at']),
    );
  }

  final String id;
  final String title;
  final String subtitle;
  final String expiresAt;
}

class _AccessLogEntry {
  const _AccessLogEntry({
    required this.id,
    required this.actor,
    required this.action,
    required this.outcome,
    required this.createdAt,
  });

  factory _AccessLogEntry.fromJson(Map<String, dynamic> json) =>
      _AccessLogEntry(
        id: _str(json['id']),
        actor: _firstNonEmpty(<Object?>[json['actor_label'], 'Người hỗ trợ']),
        action: _str(json['action']),
        outcome: _str(json['outcome']),
        createdAt: _str(json['created_at']),
      );

  final String id;
  final String actor;
  final String action;
  final String outcome;
  final String createdAt;
}

/// The Family surface: minimal, consent-based sharing with supporters.
class FamilySurface extends StatefulWidget {
  const FamilySurface({
    super.key,
    required this.apiClient,
    required this.sessionStore,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  @override
  State<FamilySurface> createState() => _FamilySurfaceState();
}

class _FamilySurfaceState extends State<FamilySurface> {
  bool _loading = true;

  /// Non-null only when the primary (relationships) load fails.
  String? _error;

  List<_Relationship> _relationships = const [];
  List<_FamilyNotification> _notifications = const [];
  List<_AccessGrant> _grants = const [];
  List<_AccessLogEntry> _accessLog = const [];
  Map<String, List<Map<String, dynamic>>> _shareOptions =
      const <String, List<Map<String, dynamic>>>{
    'episode': <Map<String, dynamic>>[],
    'visit': <Map<String, dynamic>>[],
  };

  // --- "Mời người thân" (invite) form state --------------------------------
  bool _formOpen = false;
  bool _inviting = false;
  final TextEditingController _emailController = TextEditingController();
  String _objectType = 'episode';
  String _objectId = '';
  String _purpose = 'care_coordination';
  String _createdToken = '';

  /// Ids of in-flight acknowledge/revoke actions, keyed for busy state.
  final Set<String> _acking = <String>{};
  final Set<String> _revoking = <String>{};
  final Set<String> _renewing = <String>{};

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _emailController.dispose();
    super.dispose();
  }

  String? get _token {
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) return null;
    return token;
  }

  Future<void> _load() async {
    final token = _token;
    if (token == null) {
      setState(() {
        _loading = false;
        _error = 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.';
      });
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });

    // Primary region: relationships. A failure here surfaces a combined error.
    List<_Relationship> relationships;
    try {
      final data =
          await widget.apiClient.getFamilyRelationships(accessToken: token);
      relationships = _asMapList(data, <String>['relationships'])
          .map(_Relationship.fromJson)
          .toList();
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.message;
        _loading = false;
      });
      return;
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Không thể tải thông tin chia sẻ. Vui lòng thử lại.';
        _loading = false;
      });
      return;
    }

    // Secondary regions: resilient — a failure just leaves the region empty.
    var notifications = const <_FamilyNotification>[];
    try {
      final data =
          await widget.apiClient.getFamilyNotifications(accessToken: token);
      notifications = _asMapList(data, <String>['notifications'])
          .map(_FamilyNotification.fromJson)
          .toList();
    } catch (_) {
      // Ignore — the notifications region is optional.
    }

    var grants = const <_AccessGrant>[];
    try {
      final data =
          await widget.apiClient.getFamilyAccessGrants(accessToken: token);
      grants = _asMapList(data, <String>['access_grants', 'grants'])
          .map(_AccessGrant.fromJson)
          .toList();
    } catch (_) {
      // Ignore — the access-grants region is optional.
    }

    var accessLog = const <_AccessLogEntry>[];
    try {
      final data =
          await widget.apiClient.getFamilyAccessLog(accessToken: token);
      accessLog = _asMapList(data, <String>['access_log', 'logs'])
          .map(_AccessLogEntry.fromJson)
          .toList();
    } catch (_) {
      // Optional owner audit region.
    }

    var shareOptions = _shareOptions;
    try {
      final data =
          await widget.apiClient.getFamilyShareOptions(accessToken: token);
      shareOptions = <String, List<Map<String, dynamic>>>{
        'episode': _asMapList(data, <String>['episodes']),
        'visit': _asMapList(data, <String>['visits']),
      };
    } catch (_) {
      // Invitation remains disabled when no authorized options can be loaded.
    }

    if (!mounted) return;
    setState(() {
      _relationships = relationships;
      _notifications = notifications;
      _grants = grants;
      _accessLog = accessLog;
      _shareOptions = shareOptions;
      final available = shareOptions[_objectType] ?? const [];
      if (!available.any((item) => _str(item['id']) == _objectId)) {
        _objectId = available.isEmpty ? '' : _str(available.first['id']);
      }
      _loading = false;
    });
  }

  Future<void> _invite() async {
    final token = _token;
    if (token == null || _inviting) return;
    final email = _emailController.text.trim();
    if (email.isEmpty) {
      _showSnack('Vui lòng nhập email người thân.');
      return;
    }
    setState(() => _inviting = true);
    try {
      if (_objectId.isEmpty) {
        _showSnack('Hãy chọn đúng hành trình hoặc buổi khám để chia sẻ.');
        return;
      }
      final result = await widget.apiClient.createFamilyInvitation(
        accessToken: token,
        payload: <String, dynamic>{
          'recipient_email': email,
          'scope': <String, dynamic>{
            'object_type': _objectType,
            'object_id': _objectId,
            'allowed_actions': _objectType == 'episode'
                ? <String>['view', 'add_observation']
                : <String>['view'],
          },
          'purpose': _purpose,
          'expires_at': DateTime.now()
              .toUtc()
              .add(const Duration(days: 7))
              .toIso8601String(),
        },
      );
      _emailController.clear();
      if (mounted) {
        setState(() => _createdToken = _str(result['token']));
      }
      _showSnack('Đã tạo mã mời. CLARA chưa tự gửi email.');
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack('Không thể gửi lời mời. Vui lòng thử lại.');
    } finally {
      if (mounted) {
        setState(() => _inviting = false);
      }
    }
  }

  Future<void> _acknowledge(_FamilyNotification notification) async {
    final token = _token;
    final key = '${notification.grantId}/${notification.taskId}';
    if (token == null || _acking.contains(key)) return;
    if (notification.grantId.isEmpty || notification.taskId.isEmpty) {
      _showSnack('Thông báo này không thể xác nhận.');
      return;
    }
    setState(() => _acking.add(key));
    try {
      await widget.apiClient.acknowledgeFamilyNotification(
        accessToken: token,
        grantId: notification.grantId,
        taskId: notification.taskId,
        purpose: notification.purpose,
      );
      await _load();
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack('Không thể xác nhận. Vui lòng thử lại.');
    } finally {
      if (mounted) {
        setState(() => _acking.remove(key));
      }
    }
  }

  Future<void> _revoke(_AccessGrant grant) async {
    final token = _token;
    if (token == null || _revoking.contains(grant.id)) return;
    if (grant.id.isEmpty) {
      _showSnack('Quyền truy cập này không thể thu hồi.');
      return;
    }
    final confirmed = await _confirmRevoke(grant);
    if (confirmed != true) return;
    setState(() => _revoking.add(grant.id));
    try {
      await widget.apiClient
          .revokeFamilyAccessGrant(accessToken: token, grantId: grant.id);
      _showSnack('Đã thu hồi quyền truy cập.');
      await _load();
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack('Không thể thu hồi. Vui lòng thử lại.');
    } finally {
      if (mounted) {
        setState(() => _revoking.remove(grant.id));
      }
    }
  }

  Future<void> _renew(_AccessGrant grant) async {
    final token = _token;
    if (token == null || _renewing.contains(grant.id)) return;
    setState(() => _renewing.add(grant.id));
    try {
      final result = await widget.apiClient.renewFamilyAccessGrant(
        accessToken: token,
        grantId: grant.id,
        expiresAt: DateTime.now().toUtc().add(const Duration(days: 30)),
      );
      if (mounted) {
        setState(() {
          _createdToken = _str(result['token']);
          _formOpen = true;
        });
      }
      _showSnack('Đã tạo mã gia hạn; người nhận cần chấp nhận lại.');
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack('Không thể tạo lời mời gia hạn.');
    } finally {
      if (mounted) setState(() => _renewing.remove(grant.id));
    }
  }

  Future<bool?> _confirmRevoke(_AccessGrant grant) {
    return showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Thu hồi quyền truy cập?'),
        content: Text(
          'Sau khi thu hồi, "${grant.title}" sẽ không còn xem được thông tin '
          'bạn đã chia sẻ. Bạn có thể mời lại sau này.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Hủy'),
          ),
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Thu hồi'),
          ),
        ],
      ),
    );
  }

  void _showSnack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: _load,
      child: _buildBody(context),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (_loading && _relationships.isEmpty && _error == null) {
      return ListView(
        children: const [
          SizedBox(height: ClaraTokens.spaceLg),
          ClaraSkeletonList(itemCount: 4),
        ],
      );
    }
    if (_error != null) {
      // Keep the error scrollable so pull-to-refresh still works.
      return ListView(
        children: [
          const SizedBox(height: ClaraTokens.spaceXl),
          ErrorRetryView(message: _error!, onRetry: _load),
        ],
      );
    }
    return _buildLoaded(context);
  }

  Widget _buildLoaded(BuildContext context) {
    final children = <Widget>[
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
        child: Row(
          children: [
            const Expanded(
              child: SectionHeader(title: 'Người thân', emphasize: true),
            ),
            ClaraButton.secondary(
              label: _formOpen ? 'Đóng' : 'Mời người thân',
              icon: _formOpen ? Icons.close : Icons.person_add_alt,
              onPressed: () => setState(() => _formOpen = !_formOpen),
            ),
          ],
        ),
      ),
      const SizedBox(height: ClaraTokens.spaceSm),
      _buildStandingNote(context),
      const SizedBox(height: ClaraTokens.spaceMd),
    ];

    if (_formOpen) {
      children
        ..add(
          Padding(
            padding:
                const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
            child: _buildInviteForm(context),
          ),
        )
        ..add(const SizedBox(height: ClaraTokens.spaceLg));
    }

    if (_loading) {
      children.add(
        const Padding(
          padding: EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
          child: LinearProgressIndicator(),
        ),
      );
      children.add(const SizedBox(height: ClaraTokens.spaceSm));
    }

    // --- Relationships -------------------------------------------------------
    children.add(const SectionHeader(title: 'Người bạn đang chia sẻ'));
    if (_relationships.isEmpty) {
      children.add(
        const ClaraEmptyState(
          icon: Icons.diversity_3_outlined,
          title: 'Chưa chia sẻ với ai',
          message:
              'Mời một người thân để họ có thể hỗ trợ bạn. Bạn kiểm soát những '
              'gì được chia sẻ và có thể thu hồi bất cứ lúc nào.',
        ),
      );
    } else {
      children.addAll(
        _relationships.map(
          (relationship) => Padding(
            padding: const EdgeInsets.fromLTRB(
              ClaraTokens.spaceMd,
              0,
              ClaraTokens.spaceMd,
              ClaraTokens.spaceMd,
            ),
            child: _buildRelationshipCard(context, relationship),
          ),
        ),
      );
    }

    // --- Notifications -------------------------------------------------------
    if (_notifications.isNotEmpty) {
      children
        ..add(const SizedBox(height: ClaraTokens.spaceSm))
        ..add(const SectionHeader(title: 'Thông báo cần xem'))
        ..addAll(
          _notifications.map(
            (notification) => Padding(
              padding: const EdgeInsets.fromLTRB(
                ClaraTokens.spaceMd,
                0,
                ClaraTokens.spaceMd,
                ClaraTokens.spaceMd,
              ),
              child: _buildNotificationCard(context, notification),
            ),
          ),
        );
    }

    // --- Access grants -------------------------------------------------------
    if (_grants.isNotEmpty) {
      children
        ..add(const SizedBox(height: ClaraTokens.spaceSm))
        ..add(const SectionHeader(title: 'Quyền truy cập đang mở'))
        ..addAll(
          _grants.map(
            (grant) => Padding(
              padding: const EdgeInsets.fromLTRB(
                ClaraTokens.spaceMd,
                0,
                ClaraTokens.spaceMd,
                ClaraTokens.spaceMd,
              ),
              child: _buildGrantCard(context, grant),
            ),
          ),
        );
    }

    if (_accessLog.isNotEmpty) {
      children
        ..add(const SizedBox(height: ClaraTokens.spaceSm))
        ..add(const SectionHeader(title: 'Nhật ký truy cập gần đây'))
        ..addAll(
          _accessLog.take(20).map(
                (entry) => Padding(
                  padding: const EdgeInsets.fromLTRB(
                    ClaraTokens.spaceMd,
                    0,
                    ClaraTokens.spaceMd,
                    ClaraTokens.spaceMd,
                  ),
                  child: ClaraCard.static_(
                    child: Text(
                      '${entry.actor} · ${entry.action} · ${entry.outcome}'
                      '${entry.createdAt.isEmpty ? '' : '\n${entry.createdAt}'}',
                    ),
                  ),
                ),
              ),
        );
    }

    return ListView(
      padding: const EdgeInsets.only(
        top: ClaraTokens.spaceMd,
        bottom: ClaraTokens.spaceXl,
      ),
      children: children,
    );
  }

  Widget _buildStandingNote(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
      child: ClaraCard.static_(
        semanticLabel: 'Lưu ý về chia sẻ với người hỗ trợ',
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(
              Icons.lock_outline,
              size: 20,
              color: theme.colorScheme.primary,
            ),
            const SizedBox(width: ClaraTokens.spaceSm),
            Expanded(
              child: Text(
                'Chia sẻ tối thiểu với người hỗ trợ. Bạn chỉ chia sẻ khi đồng '
                'ý và có thể thu hồi bất cứ lúc nào.',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildInviteForm(BuildContext context) {
    return ClaraCard.static_(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          TextField(
            controller: _emailController,
            keyboardType: TextInputType.emailAddress,
            textInputAction: TextInputAction.next,
            decoration: const InputDecoration(
              labelText: 'Email người thân',
              hintText: 'vidu@email.com',
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          DropdownButtonFormField<String>(
            initialValue: _objectType,
            decoration: const InputDecoration(labelText: 'Chỉ chia sẻ'),
            items: const <DropdownMenuItem<String>>[
              DropdownMenuItem(
                value: 'episode',
                child: Text('Một hành trình'),
              ),
              DropdownMenuItem(
                value: 'visit',
                child: Text('Một buổi khám'),
              ),
            ],
            onChanged: (value) {
              if (value == null) return;
              final choices = _shareOptions[value] ?? const [];
              setState(() {
                _objectType = value;
                _objectId = choices.isEmpty ? '' : _str(choices.first['id']);
              });
            },
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          DropdownButtonFormField<String>(
            initialValue: _objectId.isEmpty ? null : _objectId,
            decoration: const InputDecoration(labelText: 'Mục được chia sẻ'),
            items: (_shareOptions[_objectType] ?? const [])
                .map(
                  (item) => DropdownMenuItem<String>(
                    value: _str(item['id']),
                    child: Text(_str(item['label'])),
                  ),
                )
                .toList(growable: false),
            onChanged: (value) => setState(() => _objectId = value ?? ''),
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          DropdownButtonFormField<String>(
            initialValue: _purpose,
            decoration: const InputDecoration(labelText: 'Mục đích'),
            items: const <DropdownMenuItem<String>>[
              DropdownMenuItem(
                value: 'care_coordination',
                child: Text('Phối hợp chăm sóc'),
              ),
              DropdownMenuItem(
                value: 'visit_support',
                child: Text('Hỗ trợ đi khám'),
              ),
            ],
            onChanged: (value) => setState(() => _purpose = value ?? _purpose),
          ),
          const SizedBox(height: ClaraTokens.spaceLg),
          Align(
            alignment: Alignment.centerRight,
            child: ClaraButton.primary(
              label: 'Gửi lời mời',
              icon: Icons.send_outlined,
              loading: _inviting,
              onPressed: _invite,
            ),
          ),
          if (_createdToken.isNotEmpty) ...<Widget>[
            const SizedBox(height: ClaraTokens.spaceMd),
            const Text(
              'Mã chỉ hiển thị lần này. Gửi mã qua kênh bạn tin cậy:',
            ),
            const SizedBox(height: ClaraTokens.spaceXs),
            SelectableText(_createdToken),
          ],
        ],
      ),
    );
  }

  Widget _buildRelationshipCard(
      BuildContext context, _Relationship relationship) {
    final theme = Theme.of(context);
    return ClaraCard.static_(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            Icons.person_outline,
            size: 20,
            color: theme.colorScheme.primary,
          ),
          const SizedBox(width: ClaraTokens.spaceSm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  relationship.title,
                  style: theme.textTheme.titleSmall
                      ?.copyWith(fontWeight: FontWeight.w600),
                ),
                if (relationship.subtitle.isNotEmpty) ...[
                  const SizedBox(height: ClaraTokens.spaceXs),
                  Text(
                    relationship.subtitle,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNotificationCard(
      BuildContext context, _FamilyNotification notification) {
    final theme = Theme.of(context);
    final key = '${notification.grantId}/${notification.taskId}';
    final busy = _acking.contains(key);
    return ClaraCard.static_(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Text(
              notification.title,
              style: theme.textTheme.bodyLarge,
            ),
          ),
          const SizedBox(width: ClaraTokens.spaceSm),
          ClaraButton.secondary(
            label: 'Đã xem',
            icon: Icons.check,
            loading: busy,
            onPressed: () => _acknowledge(notification),
          ),
        ],
      ),
    );
  }

  Widget _buildGrantCard(BuildContext context, _AccessGrant grant) {
    final theme = Theme.of(context);
    final busy = _revoking.contains(grant.id);
    final renewing = _renewing.contains(grant.id);
    return ClaraCard.static_(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  grant.title,
                  style: theme.textTheme.titleSmall
                      ?.copyWith(fontWeight: FontWeight.w600),
                ),
                if (grant.subtitle.isNotEmpty) ...[
                  const SizedBox(height: ClaraTokens.spaceXs),
                  Text(
                    grant.subtitle,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
                if (grant.expiresAt.isNotEmpty)
                  Text(
                    'Hết hạn: ${grant.expiresAt}',
                    style: theme.textTheme.bodySmall,
                  ),
              ],
            ),
          ),
          const SizedBox(width: ClaraTokens.spaceSm),
          Column(
            children: <Widget>[
              ClaraButton.secondary(
                label: 'Gia hạn',
                icon: Icons.update,
                loading: renewing,
                onPressed: () => _renew(grant),
              ),
              const SizedBox(height: ClaraTokens.spaceXs),
              ClaraButton.secondary(
                label: 'Thu hồi',
                icon: Icons.link_off,
                loading: busy,
                onPressed: () => _revoke(grant),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
