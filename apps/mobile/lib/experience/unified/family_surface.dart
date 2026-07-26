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
List<Map<String, dynamic>> _asMapList(Map<String, dynamic> data, List<String> keys) {
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
      json['display_name'],
      json['name'],
      json['relationship'],
      json['role'],
      json['email'],
    ]);
    final subtitle = _firstNonEmpty(<Object?>[
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
    );
  }

  final String grantId;
  final String taskId;
  final String title;
}

/// An active access grant shared with a supporter.
class _AccessGrant {
  const _AccessGrant({
    required this.id,
    required this.title,
    required this.subtitle,
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
    );
  }

  final String id;
  final String title;
  final String subtitle;
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

  // --- "Mời người thân" (invite) form state --------------------------------
  bool _formOpen = false;
  bool _inviting = false;
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _relationshipController = TextEditingController();

  /// Ids of in-flight acknowledge/revoke actions, keyed for busy state.
  final Set<String> _acking = <String>{};
  final Set<String> _revoking = <String>{};

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _emailController.dispose();
    _relationshipController.dispose();
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

    if (!mounted) return;
    setState(() {
      _relationships = relationships;
      _notifications = notifications;
      _grants = grants;
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
      final relationship = _relationshipController.text.trim();
      await widget.apiClient.createFamilyInvitation(
        accessToken: token,
        payload: <String, dynamic>{
          'email': email,
          if (relationship.isNotEmpty) 'relationship': relationship,
        },
      );
      _emailController.clear();
      _relationshipController.clear();
      if (mounted) {
        setState(() => _formOpen = false);
      }
      _showSnack('Đã gửi lời mời chia sẻ.');
      await _load();
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
          TextField(
            controller: _relationshipController,
            textInputAction: TextInputAction.done,
            decoration: const InputDecoration(
              labelText: 'Mối quan hệ (không bắt buộc)',
              hintText: 'Ví dụ: Con gái, người chăm sóc',
            ),
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
              ],
            ),
          ),
          const SizedBox(width: ClaraTokens.spaceSm),
          ClaraButton.secondary(
            label: 'Thu hồi',
            icon: Icons.link_off,
            loading: busy,
            onPressed: () => _revoke(grant),
          ),
        ],
      ),
    );
  }
}
