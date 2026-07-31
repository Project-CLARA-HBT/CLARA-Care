// CLARA Health Community ("Cộng đồng sức khỏe") surface for the mobile redesign
// (Experience_V3). Spec: .kiro/specs/clara-health-social.
//
// A peer-support community feed built on the shared V3 design system. It talks
// to the flag-gated `/api/v1/social/*` API via [ApiClient]; when the server
// feature flag is OFF every route returns 404, which this surface treats as
// "feature unavailable" and shows a friendly disabled state (fail-closed).
//
// Safety invariants preserved from the rest of CLARA:
//   * Consent-first — participation (posting/commenting/reacting/joining)
//     requires an active `social_participation_v1` grant; the compose action is
//     gated behind a consent prompt.
//   * Moderation — the server screens every body through the legal/emergency
//     guard before persisting, so a blocked post surfaces as a 422 the user can
//     correct. The client never bypasses that.
//   * Not-a-doctor — the persistent decision-support disclaimer is shown so the
//     community is framed as peer support, not medical advice.
//   * No-PII analytics — only a coarse screen-view event, never post content.

import 'package:flutter/material.dart';

import '../../core/analytics.dart';
import '../../core/api_client.dart';
import '../../core/consumer_terminology.dart';
import '../../core/session_store.dart';
import '../language_controller.dart';
import '../../theme/components/clara_button.dart';
import '../../theme/components/clara_card.dart';
import '../../theme/components/clara_input.dart';
import '../../theme/components/section_header.dart';
import '../../theme/tokens.dart';
import '../../widgets/error_retry_view.dart';

const String _kSocialViewedEvent = 'mobile_social_feed_viewed';

/// The redesigned Health Community surface. See file header.
class SocialSurfaceV3 extends StatefulWidget {
  const SocialSurfaceV3({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    this.languageController,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;
  final LanguageController? languageController;

  @override
  State<SocialSurfaceV3> createState() => _SocialSurfaceV3State();
}

class _SocialSurfaceV3State extends State<SocialSurfaceV3> {
  bool _loading = true;
  bool _unavailable = false;
  String? _error;
  bool _consentGranted = false;
  List<Map<String, dynamic>> _communities = const [];
  List<Map<String, dynamic>> _feed = const [];

  @override
  void initState() {
    super.initState();
    getAnalyticsClient().captureScreenView(_kSocialViewedEvent);
    _load();
  }

  String? get _token => widget.sessionStore.accessToken;

  ConsumerTerminology get _copy => ConsumerTerminology.forLocale(
        widget.languageController?.languageCode,
      );

  Future<void> _load() async {
    final token = _token;
    if (token == null || token.isEmpty) {
      setState(() {
        _loading = false;
        _error = _copy[ConsumerTerm.socialSessionExpired];
      });
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
      _unavailable = false;
    });
    try {
      final consent =
          await widget.apiClient.getSocialConsent(accessToken: token);
      final communities =
          await widget.apiClient.listSocialCommunities(accessToken: token);
      final feed = await widget.apiClient.getSocialFeed(accessToken: token);
      if (!mounted) return;
      setState(() {
        _consentGranted = consent['granted'] == true;
        _communities = communities;
        _feed = feed;
        _loading = false;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      // 404 ⇒ the server feature flag is off ⇒ show the disabled state.
      if (error.statusCode == 404) {
        setState(() {
          _unavailable = true;
          _loading = false;
        });
        return;
      }
      setState(() {
        _error = error.message;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = _copy[ConsumerTerm.socialLoadFailed];
        _loading = false;
      });
    }
  }

  Future<void> _grantConsent() async {
    final token = _token;
    if (token == null || token.isEmpty) return;
    try {
      await widget.apiClient.grantSocialConsent(accessToken: token);
      if (!mounted) return;
      setState(() => _consentGranted = true);
    } on ApiException catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(error.message)));
    }
  }

  Future<void> _openCompose() async {
    if (!_consentGranted) {
      await _showConsentSheet();
      if (!_consentGranted) return;
    }
    if (!mounted) return;
    if (_communities.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(_copy[ConsumerTerm.socialNoCommunities])),
      );
      return;
    }
    final created = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _ComposeSheet(
        apiClient: widget.apiClient,
        accessToken: _token!,
        communities: _communities,
        copy: _copy,
      ),
    );
    if (created == true) {
      await _load();
    }
  }

  Future<void> _showConsentSheet() async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) => Padding(
        padding: EdgeInsets.fromLTRB(
          ClaraTokens.spaceMd,
          ClaraTokens.spaceMd,
          ClaraTokens.spaceMd,
          ClaraTokens.spaceMd + MediaQuery.of(sheetContext).viewInsets.bottom,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(_copy[ConsumerTerm.socialConsentTitle],
                style: Theme.of(sheetContext)
                    .textTheme
                    .titleMedium
                    ?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: ClaraTokens.spaceSm),
            Text(_copy[ConsumerTerm.socialConsentDescription]),
            const SizedBox(height: ClaraTokens.spaceMd),
            ClaraButton.primary(
              label: _copy[ConsumerTerm.socialConsentAgree],
              icon: Icons.check,
              onPressed: () async {
                Navigator.of(sheetContext).pop();
                await _grantConsent();
              },
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            ClaraButton.secondary(
              label: _copy[ConsumerTerm.socialLater],
              onPressed: () => Navigator.of(sheetContext).pop(),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final languageController = widget.languageController;
    if (languageController == null) return _buildLocalized(_copy);
    return AnimatedBuilder(
      animation: languageController,
      builder: (context, _) => _buildLocalized(_copy),
    );
  }

  Widget _buildLocalized(ConsumerTerminology copy) {
    return Scaffold(
      appBar: AppBar(
        title: Text(copy[ConsumerTerm.socialTitle]),
        actions: [
          if (!_unavailable && !_loading)
            IconButton(
              onPressed: _openProfile,
              icon: const Icon(Icons.account_circle_outlined),
              tooltip: copy[ConsumerTerm.socialProfileTooltip],
            ),
        ],
      ),
      floatingActionButton: (_unavailable || _loading)
          ? null
          : FloatingActionButton.extended(
              onPressed: _openCompose,
              icon: const Icon(Icons.edit_outlined),
              label: Text(copy[ConsumerTerm.socialPost]),
            ),
      body: SafeArea(child: _buildBody(copy)),
    );
  }

  Widget _buildBody(ConsumerTerminology copy) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_unavailable) {
      return _DisabledState(copy: copy);
    }
    if (_error != null) {
      return ErrorRetryView(message: _error!, onRetry: _load);
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.only(bottom: ClaraTokens.spaceXl * 2),
        children: [
          Padding(
            padding: EdgeInsets.all(ClaraTokens.spaceMd),
            child: _CommunityDisclaimer(copy: copy),
          ),
          if (!_consentGranted)
            Padding(
              padding:
                  const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
              child: ClaraCard.static_(
                semanticLabel:
                    copy[ConsumerTerm.socialConsentCardSemanticLabel],
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(copy[ConsumerTerm.socialConsentCardTitle],
                        style: Theme.of(context).textTheme.titleSmall),
                    const SizedBox(height: 4),
                    Text(copy[ConsumerTerm.socialConsentCardDescription]),
                    const SizedBox(height: ClaraTokens.spaceSm),
                    ClaraButton.primary(
                      label: copy[ConsumerTerm.socialJoin],
                      icon: Icons.group_add_outlined,
                      onPressed: _showConsentSheet,
                    ),
                  ],
                ),
              ),
            ),
          if (_communities.isNotEmpty) ...[
            SectionHeader(title: copy[ConsumerTerm.socialCommunities]),
            SizedBox(
              height: 148,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                padding:
                    const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
                itemCount: _communities.length,
                separatorBuilder: (_, __) =>
                    const SizedBox(width: ClaraTokens.spaceSm),
                itemBuilder: (_, i) => _CommunityChip(
                  community: _communities[i],
                  onJoin: () => _joinCommunity(_communities[i]),
                  copy: copy,
                ),
              ),
            ),
          ],
          SectionHeader(title: copy[ConsumerTerm.socialFeed]),
          if (_feed.isEmpty)
            Padding(
              padding: EdgeInsets.all(ClaraTokens.spaceMd),
              child: Text(copy[ConsumerTerm.socialEmptyFeed]),
            )
          else
            ..._feed.map((post) => Padding(
                  padding: const EdgeInsets.fromLTRB(ClaraTokens.spaceMd, 0,
                      ClaraTokens.spaceMd, ClaraTokens.spaceSm),
                  child: _PostCard(
                    post: post,
                    onReact: () => _react(post),
                    onOpen: () => _openPost(post),
                    copy: copy,
                  ),
                )),
        ],
      ),
    );
  }

  Future<void> _joinCommunity(Map<String, dynamic> community) async {
    if (!_consentGranted) {
      await _showConsentSheet();
      if (!_consentGranted) return;
    }
    final token = _token;
    if (token == null) return;
    final id = community['id'];
    if (id is! int) return;
    try {
      await widget.apiClient
          .joinSocialCommunity(accessToken: token, communityId: id);
      await _load();
    } on ApiException catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(error.message)));
    }
  }

  Future<void> _openPost(Map<String, dynamic> post) async {
    final token = _token;
    if (token == null) return;
    final id = post['id'];
    if (id is! int) return;
    if (!mounted) return;
    final mutated = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _PostDetailSheet(
        apiClient: widget.apiClient,
        accessToken: token,
        post: post,
        canParticipate: _consentGranted,
        copy: _copy,
      ),
    );
    if (mutated == true) await _load();
  }

  Future<void> _openProfile() async {
    final token = _token;
    if (token == null) return;
    if (!mounted) return;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _ProfileSheet(
        apiClient: widget.apiClient,
        accessToken: token,
        copy: _copy,
      ),
    );
  }

  Future<void> _react(Map<String, dynamic> post) async {
    final token = _token;
    if (token == null) return;
    final id = post['id'];
    if (id is! int) return;
    try {
      await widget.apiClient
          .addSocialReaction(accessToken: token, postId: id, kind: 'helpful');
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(_copy[ConsumerTerm.socialReactionSent])),
      );
    } on ApiException catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(error.message)));
    }
  }
}

class _CommunityDisclaimer extends StatelessWidget {
  const _CommunityDisclaimer({required this.copy});

  final ConsumerTerminology copy;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.info_outline,
              size: 16, color: theme.colorScheme.onSurfaceVariant),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              copy[ConsumerTerm.socialDisclaimer],
              style: theme.textTheme.bodySmall
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
          ),
        ],
      ),
    );
  }
}

class _CommunityChip extends StatelessWidget {
  const _CommunityChip({
    required this.community,
    required this.onJoin,
    required this.copy,
  });

  final Map<String, dynamic> community;
  final VoidCallback onJoin;
  final ConsumerTerminology copy;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final joined = community['joined'] == true;
    final name = (community['name'] ?? '').toString();
    final members = community['member_count'];
    return Container(
      width: 180,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: theme.colorScheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(name,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: theme.textTheme.titleSmall
                  ?.copyWith(fontWeight: FontWeight.w700)),
          const SizedBox(height: 4),
          Text(copy.format(ConsumerTerm.socialMembers, {'count': members ?? 0}),
              style: theme.textTheme.labelSmall
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
          const SizedBox(height: 6),
          SizedBox(
            width: double.infinity,
            child: joined
                ? OutlinedButton(
                    onPressed: null,
                    child: Text(copy[ConsumerTerm.socialJoined]),
                  )
                : FilledButton.tonal(
                    onPressed: onJoin,
                    child: Text(copy[ConsumerTerm.socialJoin]),
                  ),
          ),
        ],
      ),
    );
  }
}

class _PostCard extends StatelessWidget {
  const _PostCard({
    required this.post,
    required this.onReact,
    required this.onOpen,
    required this.copy,
  });

  final Map<String, dynamic> post;
  final VoidCallback onReact;
  final VoidCallback onOpen;
  final ConsumerTerminology copy;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final title = (post['title'] ?? '').toString();
    final body = (post['body'] ?? '').toString();
    final author = (post['author_handle'] ?? copy[ConsumerTerm.socialAnonymous])
        .toString();
    final comments = post['comment_count'] ?? 0;
    return ClaraCard(
      semanticLabel: title,
      onTap: onOpen,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              CircleAvatar(
                radius: 14,
                backgroundColor: theme.colorScheme.primaryContainer,
                child: Text(
                  author.isNotEmpty
                      ? author.substring(0, 1).toUpperCase()
                      : '?',
                  style: theme.textTheme.labelSmall,
                ),
              ),
              const SizedBox(width: 8),
              Text('@$author', style: theme.textTheme.labelMedium),
            ],
          ),
          const SizedBox(height: 8),
          Text(title,
              style: theme.textTheme.titleSmall
                  ?.copyWith(fontWeight: FontWeight.w700)),
          const SizedBox(height: 4),
          Text(body,
              maxLines: 5,
              overflow: TextOverflow.ellipsis,
              style: theme.textTheme.bodyMedium),
          const SizedBox(height: 8),
          Row(
            children: [
              TextButton.icon(
                onPressed: onReact,
                icon: const Icon(Icons.volunteer_activism_outlined, size: 18),
                label: Text(copy[ConsumerTerm.socialReactionHelpful]),
              ),
              const SizedBox(width: 8),
              Icon(Icons.mode_comment_outlined,
                  size: 16, color: theme.colorScheme.onSurfaceVariant),
              const SizedBox(width: 4),
              Text('$comments',
                  style: theme.textTheme.labelSmall
                      ?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
            ],
          ),
        ],
      ),
    );
  }
}

class _DisabledState extends StatelessWidget {
  const _DisabledState({required this.copy});

  final ConsumerTerminology copy;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(ClaraTokens.spaceLg),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.groups_outlined,
                size: 48, color: theme.colorScheme.onSurfaceVariant),
            const SizedBox(height: ClaraTokens.spaceSm),
            Text(copy[ConsumerTerm.socialUnavailableTitle],
                style: theme.textTheme.titleMedium),
            const SizedBox(height: 4),
            Text(
              copy[ConsumerTerm.socialUnavailableDescription],
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
          ],
        ),
      ),
    );
  }
}

class _ComposeSheet extends StatefulWidget {
  const _ComposeSheet({
    required this.apiClient,
    required this.accessToken,
    required this.communities,
    required this.copy,
  });

  final ApiClient apiClient;
  final String accessToken;
  final List<Map<String, dynamic>> communities;
  final ConsumerTerminology copy;

  @override
  State<_ComposeSheet> createState() => _ComposeSheetState();
}

class _ComposeSheetState extends State<_ComposeSheet> {
  final _title = TextEditingController();
  final _body = TextEditingController();
  int? _communityId;
  bool _submitting = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    final first = widget.communities.first['id'];
    if (first is int) _communityId = first;
  }

  @override
  void dispose() {
    _title.dispose();
    _body.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final title = _title.text.trim();
    final body = _body.text.trim();
    if (title.isEmpty || body.isEmpty || _communityId == null) {
      setState(() => _error = widget.copy[ConsumerTerm.socialComposeRequired]);
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await widget.apiClient.createSocialPost(
        accessToken: widget.accessToken,
        communityId: _communityId!,
        title: title,
        body: body,
      );
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } on ApiException catch (error) {
      if (!mounted) return;
      // 422 ⇒ moderation blocked the content; show the server's guidance.
      setState(() {
        _error = error.message;
        _submitting = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(
        ClaraTokens.spaceMd,
        ClaraTokens.spaceMd,
        ClaraTokens.spaceMd,
        ClaraTokens.spaceMd + MediaQuery.of(context).viewInsets.bottom,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(widget.copy[ConsumerTerm.socialComposeTitle],
                style: Theme.of(context)
                    .textTheme
                    .titleMedium
                    ?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: ClaraTokens.spaceSm),
            DropdownButtonFormField<int>(
              initialValue: _communityId,
              decoration: InputDecoration(
                  labelText: widget.copy[ConsumerTerm.socialCommunityLabel]),
              items: [
                for (final c in widget.communities)
                  if (c['id'] is int)
                    DropdownMenuItem<int>(
                      value: c['id'] as int,
                      child: Text((c['name'] ?? '').toString()),
                    ),
              ],
              onChanged: (v) => setState(() => _communityId = v),
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            ClaraInput(
                label: widget.copy[ConsumerTerm.socialPostTitleLabel],
                controller: _title),
            const SizedBox(height: ClaraTokens.spaceSm),
            ClaraInput(
                label: widget.copy[ConsumerTerm.socialPostBodyLabel],
                controller: _body,
                maxLines: 5),
            if (_error != null) ...[
              const SizedBox(height: ClaraTokens.spaceSm),
              Text(_error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ],
            const SizedBox(height: ClaraTokens.spaceMd),
            ClaraButton.primary(
              label: widget.copy[ConsumerTerm.socialPost],
              icon: Icons.send,
              loading: _submitting,
              onPressed: _submitting ? null : _submit,
            ),
          ],
        ),
      ),
    );
  }
}

/// A modal sheet showing a post in full with its comments, a supportive
/// reaction, and (for participating members) a moderated comment composer.
/// Pops `true` when the user added a comment/reaction so the feed can refresh.
class _PostDetailSheet extends StatefulWidget {
  const _PostDetailSheet({
    required this.apiClient,
    required this.accessToken,
    required this.post,
    required this.canParticipate,
    required this.copy,
  });

  final ApiClient apiClient;
  final String accessToken;
  final Map<String, dynamic> post;
  final bool canParticipate;
  final ConsumerTerminology copy;

  @override
  State<_PostDetailSheet> createState() => _PostDetailSheetState();
}

class _PostDetailSheetState extends State<_PostDetailSheet> {
  final _comment = TextEditingController();
  List<Map<String, dynamic>> _comments = const [];
  bool _loading = true;
  bool _submitting = false;
  bool _mutated = false;
  String? _error;
  String? _commentError;

  int get _postId => widget.post['id'] as int;

  @override
  void initState() {
    super.initState();
    _loadComments();
  }

  @override
  void dispose() {
    _comment.dispose();
    super.dispose();
  }

  Future<void> _loadComments() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final comments = await widget.apiClient.getSocialComments(
        accessToken: widget.accessToken,
        postId: _postId,
      );
      if (!mounted) return;
      setState(() {
        _comments = comments;
        _loading = false;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.message;
        _loading = false;
      });
    }
  }

  Future<void> _submitComment() async {
    final body = _comment.text.trim();
    if (body.isEmpty) return;
    setState(() {
      _submitting = true;
      _commentError = null;
    });
    try {
      await widget.apiClient.addSocialComment(
        accessToken: widget.accessToken,
        postId: _postId,
        body: body,
      );
      _comment.clear();
      _mutated = true;
      await _loadComments();
    } on ApiException catch (error) {
      if (!mounted) return;
      // 422 ⇒ moderation block (prescribing/diagnosis/dosage or emergency).
      setState(() {
        _commentError = error.statusCode == 422
            ? widget.copy[ConsumerTerm.socialModerationBlocked]
            : error.message;
      });
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _react() async {
    try {
      await widget.apiClient.addSocialReaction(
        accessToken: widget.accessToken,
        postId: _postId,
        kind: 'helpful',
      );
      _mutated = true;
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(widget.copy[ConsumerTerm.socialReactionSent])),
      );
    } on ApiException catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(error.message)));
    }
  }

  Future<void> _report() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(widget.copy[ConsumerTerm.socialReportTitle]),
        content: Text(widget.copy[ConsumerTerm.socialReportDescription]),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(widget.copy[ConsumerTerm.socialCancel]),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(widget.copy[ConsumerTerm.socialReport]),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await widget.apiClient.reportSocialContent(
        accessToken: widget.accessToken,
        targetType: 'post',
        targetId: _postId,
        reason: 'user_report',
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(widget.copy[ConsumerTerm.socialReportSent])),
      );
    } on ApiException catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(error.message)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final title = (widget.post['title'] ?? '').toString();
    final body = (widget.post['body'] ?? '').toString();
    final author = (widget.post['author_handle'] ??
            widget.copy[ConsumerTerm.socialAnonymous])
        .toString();
    final viewInsets = MediaQuery.of(context).viewInsets.bottom;
    return PopScope(
      canPop: true,
      onPopInvokedWithResult: (didPop, _) {},
      child: DraggableScrollableSheet(
        initialChildSize: 0.8,
        minChildSize: 0.5,
        maxChildSize: 0.95,
        expand: false,
        builder: (context, scrollController) => Padding(
          padding: EdgeInsets.fromLTRB(ClaraTokens.spaceMd, ClaraTokens.spaceMd,
              ClaraTokens.spaceMd, viewInsets),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text('@$author',
                        style: theme.textTheme.labelMedium?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant)),
                  ),
                  IconButton(
                    onPressed: _report,
                    icon: const Icon(Icons.flag_outlined),
                    tooltip: widget.copy[ConsumerTerm.socialReport],
                  ),
                  IconButton(
                    onPressed: () => Navigator.of(context).pop(_mutated),
                    icon: const Icon(Icons.close),
                    tooltip: widget.copy[ConsumerTerm.socialClose],
                  ),
                ],
              ),
              Expanded(
                child: ListView(
                  controller: scrollController,
                  children: [
                    Text(title,
                        style: theme.textTheme.titleMedium
                            ?.copyWith(fontWeight: FontWeight.w700)),
                    const SizedBox(height: ClaraTokens.spaceSm),
                    Text(body, style: theme.textTheme.bodyMedium),
                    const SizedBox(height: ClaraTokens.spaceSm),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: TextButton.icon(
                        onPressed: widget.canParticipate ? _react : null,
                        icon: const Icon(Icons.volunteer_activism_outlined,
                            size: 18),
                        label: Text(
                            widget.copy[ConsumerTerm.socialReactionHelpful]),
                      ),
                    ),
                    const Divider(),
                    Text(widget.copy[ConsumerTerm.socialComments],
                        style: theme.textTheme.titleSmall
                            ?.copyWith(fontWeight: FontWeight.w700)),
                    const SizedBox(height: ClaraTokens.spaceSm),
                    if (_loading)
                      const Padding(
                        padding: EdgeInsets.all(ClaraTokens.spaceMd),
                        child: Center(child: CircularProgressIndicator()),
                      )
                    else if (_error != null)
                      Text(_error!,
                          style: TextStyle(color: theme.colorScheme.error))
                    else if (_comments.isEmpty)
                      Text(widget.copy[ConsumerTerm.socialEmptyComments],
                          style: theme.textTheme.bodySmall?.copyWith(
                              color: theme.colorScheme.onSurfaceVariant))
                    else
                      ..._comments.map((c) => Padding(
                            padding: const EdgeInsets.only(
                                bottom: ClaraTokens.spaceSm),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                    '@${(c['author_handle'] ?? '').toString()}',
                                    style: theme.textTheme.labelSmall?.copyWith(
                                        color: theme
                                            .colorScheme.onSurfaceVariant)),
                                Text((c['body'] ?? '').toString(),
                                    style: theme.textTheme.bodyMedium),
                              ],
                            ),
                          )),
                  ],
                ),
              ),
              if (widget.canParticipate) ...[
                if (_commentError != null)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Text(_commentError!,
                        style: TextStyle(
                            color: theme.colorScheme.error, fontSize: 12)),
                  ),
                Row(
                  children: [
                    Expanded(
                      child: ClaraInput(
                        label: widget.copy[ConsumerTerm.socialCommentLabel],
                        controller: _comment,
                        maxLines: 2,
                      ),
                    ),
                    const SizedBox(width: ClaraTokens.spaceSm),
                    IconButton.filled(
                      onPressed: _submitting ? null : _submitComment,
                      icon: _submitting
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.send),
                    ),
                  ],
                ),
              ] else
                Text(widget.copy[ConsumerTerm.socialCommentJoinRequired],
                    style: theme.textTheme.bodySmall
                        ?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
            ],
          ),
        ),
      ),
    );
  }
}

/// Bottom sheet to view + edit the current user's community profile
/// (display name + bio). PHR-isolated: no medical-record data is ever shown or
/// editable here (spec R2/R10).
class _ProfileSheet extends StatefulWidget {
  const _ProfileSheet({
    required this.apiClient,
    required this.accessToken,
    required this.copy,
  });

  final ApiClient apiClient;
  final String accessToken;
  final ConsumerTerminology copy;

  @override
  State<_ProfileSheet> createState() => _ProfileSheetState();
}

class _ProfileSheetState extends State<_ProfileSheet> {
  final _displayName = TextEditingController();
  final _bio = TextEditingController();
  bool _loading = true;
  bool _saving = false;
  String _handle = '';
  String _roleBadge = '';
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _displayName.dispose();
    _bio.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final p = await widget.apiClient
          .getSocialProfile(accessToken: widget.accessToken);
      if (!mounted) return;
      setState(() {
        _handle = (p['handle'] ?? '').toString();
        _roleBadge = (p['role_badge'] ?? '').toString();
        _displayName.text = (p['display_name'] ?? '').toString();
        _bio.text = (p['bio'] ?? '').toString();
        _loading = false;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.message;
        _loading = false;
      });
    }
  }

  Future<void> _save() async {
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.apiClient.updateSocialProfile(
        accessToken: widget.accessToken,
        displayName: _displayName.text.trim(),
        bio: _bio.text.trim(),
      );
      if (!mounted) return;
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(widget.copy[ConsumerTerm.socialProfileSaved])),
      );
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.message;
        _saving = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final viewInsets = MediaQuery.of(context).viewInsets.bottom;
    return Padding(
      padding: EdgeInsets.fromLTRB(ClaraTokens.spaceMd, ClaraTokens.spaceMd,
          ClaraTokens.spaceMd, ClaraTokens.spaceMd + viewInsets),
      child: _loading
          ? const Padding(
              padding: EdgeInsets.all(ClaraTokens.spaceLg),
              child: Center(child: CircularProgressIndicator()),
            )
          : Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(widget.copy[ConsumerTerm.socialProfileTitle],
                    style: theme.textTheme.titleMedium
                        ?.copyWith(fontWeight: FontWeight.w700)),
                if (_handle.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      Text('@$_handle',
                          style: theme.textTheme.labelMedium?.copyWith(
                              color: theme.colorScheme.onSurfaceVariant)),
                      if (_roleBadge.isNotEmpty) ...[
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: theme.colorScheme.primaryContainer,
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(
                            _roleBadge == 'doctor'
                                ? widget.copy[ConsumerTerm.socialDoctor]
                                : _roleBadge == 'researcher'
                                    ? widget.copy[ConsumerTerm.socialResearcher]
                                    : _roleBadge,
                            style: theme.textTheme.labelSmall,
                          ),
                        ),
                      ],
                    ],
                  ),
                ],
                const SizedBox(height: ClaraTokens.spaceMd),
                ClaraInput(
                    label: widget.copy[ConsumerTerm.socialDisplayNameLabel],
                    controller: _displayName),
                const SizedBox(height: ClaraTokens.spaceSm),
                ClaraInput(
                    label: widget.copy[ConsumerTerm.socialBioLabel],
                    controller: _bio,
                    maxLines: 3),
                if (_error != null) ...[
                  const SizedBox(height: ClaraTokens.spaceSm),
                  Text(_error!,
                      style: TextStyle(color: theme.colorScheme.error)),
                ],
                const SizedBox(height: ClaraTokens.spaceMd),
                ClaraButton.primary(
                  label: widget.copy[ConsumerTerm.socialSaveProfile],
                  icon: Icons.save_outlined,
                  loading: _saving,
                  onPressed: _saving ? null : _save,
                ),
              ],
            ),
    );
  }
}
