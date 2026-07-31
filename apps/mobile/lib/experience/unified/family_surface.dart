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
import '../../core/consumer_terminology.dart';
import '../../core/session_store.dart';
import '../../theme/components/clara_button.dart';
import '../../theme/components/clara_card.dart';
import '../../theme/components/section_header.dart';
import '../../theme/tokens.dart';
import '../../widgets/error_retry_view.dart';
import '../states/empty_state.dart';
import '../states/skeleton.dart';
import '../language_controller.dart';
import 'family_invitation_acceptance_flow.dart';

String _str(Object? value) => value == null ? '' : value.toString();

/// Returns the first non-empty stringified value in [values], or `''`.
String _firstNonEmpty(List<Object?> values) {
  for (final value in values) {
    final s = _str(value).trim();
    if (s.isNotEmpty) return s;
  }
  return '';
}

String _localizedDateTime(BuildContext context, String value) {
  final parsed = DateTime.tryParse(value);
  if (parsed == null) return value;
  final local = parsed.toLocal();
  final localizations = MaterialLocalizations.of(context);
  final date = localizations.formatShortDate(local);
  final time = localizations.formatTimeOfDay(TimeOfDay.fromDateTime(local));
  return '$date, $time';
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
      title: title,
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
      title: title,
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
      title: title,
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
    required this.actorCode,
    required this.action,
    required this.actionCode,
    required this.outcome,
    required this.outcomeCode,
    required this.createdAt,
  });

  factory _AccessLogEntry.fromJson(Map<String, dynamic> json) =>
      _AccessLogEntry(
        id: _str(json['id']),
        actor: _firstNonEmpty(<Object?>[json['actor_label']]),
        actorCode: _str(json['actor_code']),
        action: _str(json['action']),
        actionCode: _str(json['action_code']),
        outcome: _str(json['outcome']),
        outcomeCode: _str(json['outcome_code']),
        createdAt: _str(json['created_at']),
      );

  final String id;
  final String actor;
  final String actorCode;
  final String action;
  final String actionCode;
  final String outcome;
  final String outcomeCode;
  final String createdAt;
}

String _accessLogActorLabel(ConsumerTerminology copy, _AccessLogEntry entry) {
  switch (entry.actorCode) {
    case 'owner':
      return copy[ConsumerTerm.familyAccessLogActorOwner];
    case 'supporter':
      return copy[ConsumerTerm.familyAccessLogActorSupporter];
    case 'system':
      return copy[ConsumerTerm.familyAccessLogActorSystem];
    default:
      return entry.actor.isEmpty
          ? copy[ConsumerTerm.familyAccessLogActorOther]
          : entry.actor;
  }
}

String _accessLogActionLabel(ConsumerTerminology copy, _AccessLogEntry entry) {
  switch (entry.actionCode.isEmpty ? entry.action : entry.actionCode) {
    case 'view':
      return copy[ConsumerTerm.familyAccessLogActionView];
    case 'add_observation':
      return copy[ConsumerTerm.familyAccessLogActionAddObservation];
    case 'complete_task':
      return copy[ConsumerTerm.familyAccessLogActionCompleteTask];
    case 'invitation_accept':
    case 'invitation.accept':
      return copy[ConsumerTerm.familyAccessLogActionInvitationAccept];
    case 'grant_revoke':
    case 'grant.revoke':
      return copy[ConsumerTerm.familyAccessLogActionGrantRevoke];
    case 'grant_renewal_invited':
    case 'grant.renewal_invited':
      return copy[ConsumerTerm.familyAccessLogActionGrantRenewalInvited];
    case 'notification_acknowledged':
    case 'notification.acknowledged':
      return copy[ConsumerTerm.familyAccessLogActionNotificationAcknowledged];
    default:
      return copy[ConsumerTerm.familyAccessLogActionOther];
  }
}

String _accessLogOutcomeCode(_AccessLogEntry entry) {
  switch (entry.outcomeCode) {
    case 'allowed':
    case 'denied':
    case 'failed':
    case 'unknown':
      return entry.outcomeCode;
  }
  switch (entry.outcome) {
    case 'success':
    case 'allowed':
      return 'allowed';
    case 'denied':
      return 'denied';
    case 'failure':
    case 'failed':
      return 'failed';
    default:
      return 'unknown';
  }
}

String _accessLogOutcomeLabel(ConsumerTerminology copy, _AccessLogEntry entry) {
  switch (_accessLogOutcomeCode(entry)) {
    case 'allowed':
      return copy[ConsumerTerm.familyAccessLogOutcomeAllowed];
    case 'denied':
      return copy[ConsumerTerm.familyAccessLogOutcomeDenied];
    case 'failed':
      return copy[ConsumerTerm.familyAccessLogOutcomeFailed];
    default:
      return copy[ConsumerTerm.familyAccessLogOutcomeUnknown];
  }
}

/// The Family surface: minimal, consent-based sharing with supporters.
class FamilySurface extends StatefulWidget {
  const FamilySurface({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    this.languageController,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  /// Optional app-level language state. Direct embedding remains
  /// Vietnamese-first when it is not supplied.
  final LanguageController? languageController;

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

  ConsumerTerminology get _copy => ConsumerTerminology.forLocale(
        widget.languageController?.languageCode,
      );

  Future<void> _load() async {
    final token = _token;
    if (token == null) {
      setState(() {
        _loading = false;
        _error = _copy[ConsumerTerm.sessionExpired];
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
        _error = _copy[ConsumerTerm.familyLoadFailed];
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
      _showSnack(_copy[ConsumerTerm.familyEmailRequired]);
      return;
    }
    setState(() => _inviting = true);
    try {
      if (_objectId.isEmpty) {
        _showSnack(_copy[ConsumerTerm.familySharedItemRequired]);
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
      _showSnack(_copy[ConsumerTerm.familyInvitationCreated]);
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack(_copy[ConsumerTerm.familyInvitationFailed]);
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
      _showSnack(_copy[ConsumerTerm.familyNotificationUnavailable]);
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
      _showSnack(_copy[ConsumerTerm.familyAcknowledgeFailed]);
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
      _showSnack(_copy[ConsumerTerm.familyGrantUnavailable]);
      return;
    }
    final confirmed = await _confirmRevoke(grant);
    if (confirmed != true) return;
    setState(() => _revoking.add(grant.id));
    try {
      await widget.apiClient
          .revokeFamilyAccessGrant(accessToken: token, grantId: grant.id);
      _showSnack(_copy[ConsumerTerm.familyRevoked]);
      await _load();
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack(_copy[ConsumerTerm.familyRevokeFailed]);
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
      _showSnack(_copy[ConsumerTerm.familyRenewed]);
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack(_copy[ConsumerTerm.familyRenewFailed]);
    } finally {
      if (mounted) setState(() => _renewing.remove(grant.id));
    }
  }

  Future<void> _openInvitationAcceptance() async {
    final accepted = await Navigator.of(context).push<bool>(
      MaterialPageRoute<bool>(
        builder: (_) => FamilyInvitationAcceptanceFlow(
          apiClient: widget.apiClient,
          sessionStore: widget.sessionStore,
          languageController: widget.languageController,
        ),
      ),
    );
    if (!mounted || accepted != true) return;
    _showSnack(_copy[ConsumerTerm.familyInvitationAccepted]);
    await _load();
  }

  Future<bool?> _confirmRevoke(_AccessGrant grant) {
    return showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(_copy[ConsumerTerm.familyRevokeConfirmTitle]),
        content: Text(_copy.format(
          ConsumerTerm.familyRevokeConfirmDescription,
          <String, Object?>{
            'name': grant.title.isEmpty
                ? _copy[ConsumerTerm.familySupporter]
                : grant.title,
          },
        )),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: Text(_copy[ConsumerTerm.familyCancel]),
          ),
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: Text(_copy[ConsumerTerm.familyRevoke]),
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
    final languageController = widget.languageController;
    if (languageController != null) {
      return AnimatedBuilder(
        animation: languageController,
        builder: (context, _) => _buildRefreshable(context),
      );
    }
    return _buildRefreshable(context);
  }

  Widget _buildRefreshable(BuildContext context) {
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
    final copy = _copy;
    final children = <Widget>[
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
        child: Row(
          children: [
            Expanded(
              child: SectionHeader(
                title: copy[ConsumerTerm.familyTitle],
                emphasize: true,
              ),
            ),
            ClaraButton.secondary(
              label: _formOpen
                  ? copy[ConsumerTerm.familyClose]
                  : copy[ConsumerTerm.familyInvite],
              icon: _formOpen ? Icons.close : Icons.person_add_alt,
              onPressed: () => setState(() => _formOpen = !_formOpen),
            ),
          ],
        ),
      ),
      const SizedBox(height: ClaraTokens.spaceSm),
      _buildStandingNote(context),
      const SizedBox(height: ClaraTokens.spaceMd),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
        child: _buildInvitationAcceptanceCard(context),
      ),
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
    children.add(SectionHeader(title: copy[ConsumerTerm.familySharedWith]));
    if (_relationships.isEmpty) {
      children.add(
        ClaraEmptyState(
          icon: Icons.diversity_3_outlined,
          title: copy[ConsumerTerm.familyEmptyTitle],
          message: copy[ConsumerTerm.familyEmptyDescription],
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
        ..add(SectionHeader(title: copy[ConsumerTerm.familyNotifications]))
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
        ..add(SectionHeader(title: copy[ConsumerTerm.familyActiveGrants]))
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
        ..add(SectionHeader(title: copy[ConsumerTerm.familyAccessLog]))
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
                      '${_accessLogActorLabel(copy, entry)}'
                      ' · ${_accessLogActionLabel(copy, entry)}'
                      ' · ${_accessLogOutcomeLabel(copy, entry)}'
                      '${entry.createdAt.isEmpty ? '' : '\n${_localizedDateTime(context, entry.createdAt)}'}',
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
    final copy = _copy;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
      child: ClaraCard.static_(
        semanticLabel: copy[ConsumerTerm.familySharingNoteSemanticLabel],
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
                copy[ConsumerTerm.familySharingNote],
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

  Widget _buildInvitationAcceptanceCard(BuildContext context) {
    final theme = Theme.of(context);
    final copy = _copy;
    return ClaraCard.static_(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            Icons.mark_email_read_outlined,
            size: 20,
            color: theme.colorScheme.primary,
          ),
          const SizedBox(width: ClaraTokens.spaceSm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  copy[ConsumerTerm.familyUseInvitationCode],
                  style: theme.textTheme.titleSmall
                      ?.copyWith(fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: ClaraTokens.spaceXs),
                Text(
                  copy[ConsumerTerm.familyInvitationAcceptDescription],
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: ClaraTokens.spaceSm),
                ClaraButton.secondary(
                  label: copy[ConsumerTerm.familyUseInvitationCode],
                  icon: Icons.arrow_forward,
                  onPressed: _openInvitationAcceptance,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInviteForm(BuildContext context) {
    final copy = _copy;
    return ClaraCard.static_(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          TextField(
            controller: _emailController,
            keyboardType: TextInputType.emailAddress,
            textInputAction: TextInputAction.next,
            decoration: InputDecoration(
              labelText: copy[ConsumerTerm.familyEmailLabel],
              hintText: copy[ConsumerTerm.familyEmailHint],
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          DropdownButtonFormField<String>(
            initialValue: _objectType,
            decoration: InputDecoration(
              labelText: copy[ConsumerTerm.familyScopeLabel],
            ),
            items: <DropdownMenuItem<String>>[
              DropdownMenuItem(
                value: 'episode',
                child: Text(copy[ConsumerTerm.familyScopeJourney]),
              ),
              DropdownMenuItem(
                value: 'visit',
                child: Text(copy[ConsumerTerm.familyScopeVisit]),
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
            decoration: InputDecoration(
              labelText: copy[ConsumerTerm.familySharedItemLabel],
            ),
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
            decoration: InputDecoration(
              labelText: copy[ConsumerTerm.familyPurposeLabel],
            ),
            items: <DropdownMenuItem<String>>[
              DropdownMenuItem(
                value: 'care_coordination',
                child: Text(copy[ConsumerTerm.familyPurposeCareCoordination]),
              ),
              DropdownMenuItem(
                value: 'visit_support',
                child: Text(copy[ConsumerTerm.familyPurposeVisitSupport]),
              ),
            ],
            onChanged: (value) => setState(() => _purpose = value ?? _purpose),
          ),
          const SizedBox(height: ClaraTokens.spaceLg),
          Align(
            alignment: Alignment.centerRight,
            child: ClaraButton.primary(
              label: copy[ConsumerTerm.familySendInvitation],
              icon: Icons.send_outlined,
              loading: _inviting,
              onPressed: _invite,
            ),
          ),
          if (_createdToken.isNotEmpty) ...<Widget>[
            const SizedBox(height: ClaraTokens.spaceMd),
            Text(copy[ConsumerTerm.familyInvitationTokenNotice]),
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
    final copy = _copy;
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
                  relationship.title.isEmpty
                      ? copy[ConsumerTerm.familySupporter]
                      : relationship.title,
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
    final copy = _copy;
    final key = '${notification.grantId}/${notification.taskId}';
    final busy = _acking.contains(key);
    return ClaraCard.static_(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Text(
              notification.title.isEmpty
                  ? copy[ConsumerTerm.familyNewNotification]
                  : notification.title,
              style: theme.textTheme.bodyLarge,
            ),
          ),
          const SizedBox(width: ClaraTokens.spaceSm),
          ClaraButton.secondary(
            label: copy[ConsumerTerm.familyAcknowledge],
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
    final copy = _copy;
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
                  grant.title.isEmpty
                      ? copy[ConsumerTerm.familyAccessGrant]
                      : grant.title,
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
                    copy.format(
                      ConsumerTerm.familyExpiresAt,
                      <String, Object?>{
                        'date': _localizedDateTime(context, grant.expiresAt),
                      },
                    ),
                    style: theme.textTheme.bodySmall,
                  ),
              ],
            ),
          ),
          const SizedBox(width: ClaraTokens.spaceSm),
          Column(
            children: <Widget>[
              ClaraButton.secondary(
                label: copy[ConsumerTerm.familyRenew],
                icon: Icons.update,
                loading: renewing,
                onPressed: () => _renew(grant),
              ),
              const SizedBox(height: ClaraTokens.spaceXs),
              ClaraButton.secondary(
                label: copy[ConsumerTerm.familyRevoke],
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
