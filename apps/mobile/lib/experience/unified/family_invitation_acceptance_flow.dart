// Recipient-side Family invitation flow.
//
// A Family invitation is a bearer capability. This screen deliberately keeps
// the code only in its TextEditingController while the route is open, sends it
// exclusively in the API request header, and never puts it in a URL, log,
// route argument, durable store, or analytics event. Preview is read-only;
// accepting remains a second, explicit user action.

import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/consumer_terminology.dart';
import '../../core/session_store.dart';
import '../../theme/components/clara_button.dart';
import '../../theme/components/clara_card.dart';
import '../../theme/tokens.dart';
import '../language_controller.dart';

class _InvitationPreview {
  const _InvitationPreview({
    required this.objectType,
    required this.allowedActions,
    required this.purpose,
    required this.expiresAt,
  });

  factory _InvitationPreview.fromJson(Map<String, dynamic> json) {
    final rawActions = json['allowed_actions'];
    return _InvitationPreview(
      objectType: (json['object_type'] ?? '').toString(),
      allowedActions: rawActions is List
          ? rawActions
              .map((value) => value.toString().trim())
              .where((value) => value.isNotEmpty)
              .toList(growable: false)
          : const <String>[],
      purpose: (json['purpose'] ?? '').toString(),
      expiresAt: (json['expires_at'] ?? '').toString(),
    );
  }

  final String objectType;
  final List<String> allowedActions;
  final String purpose;
  final String expiresAt;
}

/// Lets an invited recipient preview a bounded Family scope before accepting.
///
/// This remains separate from the owner invitation form: the first request is
/// always preview-only and the access grant can be created only by tapping the
/// later, explicit accept button after the returned scope is rendered.
class FamilyInvitationAcceptanceFlow extends StatefulWidget {
  const FamilyInvitationAcceptanceFlow({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    this.languageController,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;
  final LanguageController? languageController;

  @override
  State<FamilyInvitationAcceptanceFlow> createState() =>
      _FamilyInvitationAcceptanceFlowState();
}

class _FamilyInvitationAcceptanceFlowState
    extends State<FamilyInvitationAcceptanceFlow> {
  final TextEditingController _codeController = TextEditingController();
  _InvitationPreview? _preview;
  String? _error;
  bool _previewing = false;
  bool _accepting = false;

  ConsumerTerminology get _copy => ConsumerTerminology.forLocale(
        widget.languageController?.languageCode,
      );

  String? get _accessToken {
    final value = widget.sessionStore.accessToken;
    return value == null || value.isEmpty ? null : value;
  }

  @override
  void dispose() {
    // The code never leaves this in-memory controller and is discarded when
    // the route closes, including a back navigation.
    _codeController.dispose();
    super.dispose();
  }

  void _onCodeChanged(String _) {
    if (_preview == null && _error == null) return;
    setState(() {
      _preview = null;
      _error = null;
    });
  }

  Future<void> _previewInvitation() async {
    final accessToken = _accessToken;
    final invitationToken = _codeController.text.trim();
    if (invitationToken.isEmpty) {
      setState(() => _error = _copy[ConsumerTerm.familyInvitationCodeRequired]);
      return;
    }
    if (accessToken == null || _previewing || _accepting) {
      setState(() => _error = _copy[ConsumerTerm.sessionExpired]);
      return;
    }

    setState(() {
      _previewing = true;
      _preview = null;
      _error = null;
    });
    try {
      final data = await widget.apiClient.previewFamilyInvitation(
        accessToken: accessToken,
        invitationToken: invitationToken,
      );
      if (!mounted) return;
      setState(() => _preview = _InvitationPreview.fromJson(data));
    } on ApiException {
      if (!mounted) return;
      // Do not surface capability-state detail: it could reveal whether the
      // code is known, expired, or for a different recipient.
      setState(
        () => _error = _copy[ConsumerTerm.familyInvitationPreviewFailed],
      );
    } catch (_) {
      if (!mounted) return;
      setState(
        () => _error = _copy[ConsumerTerm.familyInvitationPreviewFailed],
      );
    } finally {
      if (mounted) setState(() => _previewing = false);
    }
  }

  Future<void> _acceptInvitation() async {
    final accessToken = _accessToken;
    final invitationToken = _codeController.text.trim();
    if (_preview == null || invitationToken.isEmpty || _accepting) return;
    if (accessToken == null) {
      setState(() => _error = _copy[ConsumerTerm.sessionExpired]);
      return;
    }

    setState(() {
      _accepting = true;
      _error = null;
    });
    try {
      await widget.apiClient.acceptFamilyInvitation(
        accessToken: accessToken,
        invitationToken: invitationToken,
      );
      // Clear the bearer capability before leaving the route. The parent uses
      // only this boolean result to refresh its grant list; no token escapes.
      _codeController.clear();
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } on ApiException {
      if (!mounted) return;
      setState(
        () => _error = _copy[ConsumerTerm.familyInvitationAcceptFailed],
      );
    } catch (_) {
      if (!mounted) return;
      setState(
        () => _error = _copy[ConsumerTerm.familyInvitationAcceptFailed],
      );
    } finally {
      if (mounted) setState(() => _accepting = false);
    }
  }

  String _scopeLabel(String objectType) {
    switch (objectType) {
      case 'episode':
        return _copy[ConsumerTerm.familyScopeJourney];
      case 'visit':
        return _copy[ConsumerTerm.familyScopeVisit];
      case 'care_task':
        return _copy[ConsumerTerm.familyInvitationScopeCareTask];
      default:
        return _copy[ConsumerTerm.familyInvitationScopeLabel];
    }
  }

  String _purposeLabel(String purpose) {
    switch (purpose) {
      case 'care_coordination':
        return _copy[ConsumerTerm.familyPurposeCareCoordination];
      case 'visit_support':
        return _copy[ConsumerTerm.familyPurposeVisitSupport];
      default:
        return _copy[ConsumerTerm.familyPurposeLabel];
    }
  }

  String _actionLabel(String action) {
    switch (action) {
      case 'view':
        return _copy[ConsumerTerm.familyInvitationActionView];
      case 'add_observation':
        return _copy[ConsumerTerm.familyInvitationActionAddObservation];
      case 'complete_task':
        return _copy[ConsumerTerm.familyInvitationActionCompleteTask];
      default:
        return _copy[ConsumerTerm.familyInvitationActionOther];
    }
  }

  String _formatDate(BuildContext context, String source) {
    final parsed = DateTime.tryParse(source);
    if (parsed == null) {
      return _copy[ConsumerTerm.familyInvitationExpiryUnavailable];
    }
    final local = parsed.toLocal();
    final localizations = MaterialLocalizations.of(context);
    return '${localizations.formatShortDate(local)}, '
        '${localizations.formatTimeOfDay(TimeOfDay.fromDateTime(local))}';
  }

  @override
  Widget build(BuildContext context) {
    final controller = widget.languageController;
    if (controller == null) return _buildPage(context);
    return AnimatedBuilder(
      animation: controller,
      builder: (context, _) => _buildPage(context),
    );
  }

  Widget _buildPage(BuildContext context) {
    final copy = _copy;
    final preview = _preview;
    final busy = _previewing || _accepting;
    return Scaffold(
      appBar:
          AppBar(title: Text(copy[ConsumerTerm.familyInvitationAcceptTitle])),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(ClaraTokens.spaceMd),
          children: [
            Text(
              copy[ConsumerTerm.familyInvitationAcceptDescription],
              style: Theme.of(context).textTheme.bodyLarge,
            ),
            const SizedBox(height: ClaraTokens.spaceLg),
            ClaraCard.static_(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  TextField(
                    controller: _codeController,
                    enabled: !busy,
                    autocorrect: false,
                    enableSuggestions: false,
                    obscureText: true,
                    textInputAction: TextInputAction.done,
                    onChanged: _onCodeChanged,
                    onSubmitted: (_) => _previewInvitation(),
                    decoration: InputDecoration(
                      labelText: copy[ConsumerTerm.familyInvitationCodeLabel],
                      hintText: copy[ConsumerTerm.familyInvitationCodeHint],
                    ),
                  ),
                  const SizedBox(height: ClaraTokens.spaceMd),
                  SizedBox(
                    width: double.infinity,
                    child: ClaraButton.primary(
                      label: _previewing
                          ? copy[ConsumerTerm.familyPreviewingInvitation]
                          : copy[ConsumerTerm.familyPreviewInvitation],
                      icon: Icons.visibility_outlined,
                      loading: _previewing,
                      onPressed: busy ? null : _previewInvitation,
                    ),
                  ),
                ],
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: ClaraTokens.spaceMd),
              Semantics(
                liveRegion: true,
                child: Text(
                  _error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            ],
            if (preview != null) ...[
              const SizedBox(height: ClaraTokens.spaceLg),
              ClaraCard.static_(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      copy[ConsumerTerm.familyInvitationPreviewTitle],
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: ClaraTokens.spaceMd),
                    _PreviewRow(
                      label: copy[ConsumerTerm.familyInvitationScopeLabel],
                      value: _scopeLabel(preview.objectType),
                    ),
                    _PreviewRow(
                      label: copy[ConsumerTerm.familyPurposeLabel],
                      value: _purposeLabel(preview.purpose),
                    ),
                    _PreviewRow(
                      label: copy[ConsumerTerm.familyExpiresAt]
                          .replaceFirst('{date}', ''),
                      value: _formatDate(context, preview.expiresAt),
                    ),
                    const SizedBox(height: ClaraTokens.spaceSm),
                    Text(
                      copy[ConsumerTerm.familyInvitationActionsLabel],
                      style: Theme.of(context).textTheme.labelLarge,
                    ),
                    const SizedBox(height: ClaraTokens.spaceXs),
                    ...preview.allowedActions.map(
                      (action) => Padding(
                        padding: const EdgeInsets.only(
                          bottom: ClaraTokens.spaceXs,
                        ),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Icon(Icons.check, size: 18),
                            const SizedBox(width: ClaraTokens.spaceXs),
                            Expanded(child: Text(_actionLabel(action))),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: ClaraTokens.spaceMd),
                    Text(
                      copy[ConsumerTerm.familyInvitationPreviewNotice],
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                    const SizedBox(height: ClaraTokens.spaceLg),
                    SizedBox(
                      width: double.infinity,
                      child: ClaraButton.primary(
                        label: _accepting
                            ? copy[ConsumerTerm.familyAcceptingInvitation]
                            : copy[ConsumerTerm.familyInvitationAccept],
                        icon: Icons.verified_user_outlined,
                        loading: _accepting,
                        onPressed: busy ? null : _acceptInvitation,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _PreviewRow extends StatelessWidget {
  const _PreviewRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: ClaraTokens.spaceSm),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: theme.textTheme.labelLarge),
          const SizedBox(height: ClaraTokens.spaceXs),
          Text(value, style: theme.textTheme.bodyMedium),
        ],
      ),
    );
  }
}
