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
import '../../theme/components/clara_status_badge.dart';
import '../../theme/components/empty_state.dart';
import '../../theme/components/section_header.dart';
import '../../theme/tokens.dart';
import '../../widgets/error_retry_view.dart';

const String _kSocialViewedEvent = 'mobile_social_feed_viewed';

enum _AuthorFilter { all, official, peers, bookmarks }

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
  List<Map<String, dynamic>> _bookmarks = const [];
  Set<int> _hiddenPostIds = {};

  int? _selectedCommunityId;
  _AuthorFilter _selectedAuthorFilter = _AuthorFilter.all;
  String _searchQuery = '';
  final TextEditingController _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    getAnalyticsClient().captureScreenView(_kSocialViewedEvent);
    _load();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
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
      
      List<Map<String, dynamic>> bookmarks = [];
      try {
        bookmarks = await widget.apiClient.getSocialBookmarks(accessToken: token);
      } catch (_) {
        bookmarks = [];
      }

      if (!mounted) return;
      setState(() {
        _consentGranted = consent['granted'] == true;
        _communities = communities;
        _feed = feed;
        _bookmarks = bookmarks;
        _loading = false;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
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
        initialCommunityId: _selectedCommunityId,
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

  List<Map<String, dynamic>> _filteredFeed() {
    List<Map<String, dynamic>> sourceList = _feed;
    if (_selectedAuthorFilter == _AuthorFilter.bookmarks) {
      sourceList = _bookmarks;
    }

    return sourceList.where((post) {
      final id = post['id'];
      if (id is int && _hiddenPostIds.contains(id)) {
        return false;
      }

      // Community filter
      if (_selectedCommunityId != null) {
        if (post['community_id'] != _selectedCommunityId) {
          return false;
        }
      }

      // Author filter
      final author = (post['author_handle'] ?? '').toString().toLowerCase();
      final isOfficial = post['is_verified_clinician'] == true ||
          author.startsWith('clara') ||
          author.startsWith('dr_') ||
          author.startsWith('bs_') ||
          author.startsWith('bacsi_');
      if (_selectedAuthorFilter == _AuthorFilter.official && !isOfficial) {
        return false;
      }
      if (_selectedAuthorFilter == _AuthorFilter.peers && isOfficial) {
        return false;
      }

      // Search query
      if (_searchQuery.trim().isNotEmpty) {
        final q = _searchQuery.trim().toLowerCase();
        final title = (post['title'] ?? '').toString().toLowerCase();
        final body = (post['body'] ?? '').toString().toLowerCase();
        if (!title.contains(q) && !body.contains(q) && !author.contains(q)) {
          return false;
        }
      }

      return true;
    }).toList();
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
          if (!_unavailable && !_loading) ...[
            if (_hiddenPostIds.isNotEmpty)
              IconButton(
                onPressed: () {
                  setState(() => _hiddenPostIds.clear());
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text(copy[ConsumerTerm.socialUnhidePosts])),
                  );
                },
                icon: const Icon(Icons.visibility_outlined),
                tooltip: copy[ConsumerTerm.socialUnhidePosts],
              ),
            IconButton(
              onPressed: _openProfile,
              icon: const Icon(Icons.account_circle_outlined),
              tooltip: copy[ConsumerTerm.socialProfileTooltip],
            ),
          ],
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

    final filtered = _filteredFeed();

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.only(bottom: ClaraTokens.spaceXl * 2),
        children: [
          Padding(
            padding: const EdgeInsets.all(ClaraTokens.spaceMd),
            child: _CommunityDisclaimer(copy: copy),
          ),
          
          // Search input
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
            child: TextField(
              controller: _searchController,
              decoration: InputDecoration(
                hintText: copy[ConsumerTerm.socialSearchPlaceholder],
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _searchQuery.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.close),
                        onPressed: () {
                          _searchController.clear();
                          setState(() => _searchQuery = '');
                        },
                      )
                    : null,
                contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
              ),
              onChanged: (val) {
                setState(() => _searchQuery = val);
              },
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceSm),

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

          // Community / Topics Filter Row
          if (_communities.isNotEmpty) ...[
            SectionHeader(title: copy[ConsumerTerm.socialCommunities]),
            SizedBox(
              height: 148,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                padding:
                    const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
                itemCount: _communities.length + 1,
                separatorBuilder: (_, __) =>
                    const SizedBox(width: ClaraTokens.spaceSm),
                itemBuilder: (_, i) {
                  if (i == 0) {
                    final isAllSelected = _selectedCommunityId == null;
                    return _AllTopicsCard(
                      isSelected: isAllSelected,
                      totalCount: _feed.length,
                      onTap: () {
                        setState(() => _selectedCommunityId = null);
                      },
                      copy: copy,
                    );
                  }
                  final comm = _communities[i - 1];
                  final isSelected = _selectedCommunityId == comm['id'];
                  return _CommunityChip(
                    community: comm,
                    isSelected: isSelected,
                    onTap: () {
                      setState(() {
                        if (_selectedCommunityId == comm['id']) {
                          _selectedCommunityId = null;
                        } else {
                          _selectedCommunityId = comm['id'] as int?;
                        }
                      });
                    },
                    onJoin: () => _joinCommunity(comm),
                    onLeave: () => _leaveCommunity(comm),
                    copy: copy,
                  );
                },
              ),
            ),
          ],

          // Author / Bookmarks Segmented Control
          Padding(
            padding: const EdgeInsets.fromLTRB(ClaraTokens.spaceMd, ClaraTokens.spaceMd, ClaraTokens.spaceMd, 0),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  _FilterSegmentChip(
                    label: copy[ConsumerTerm.socialFilterAll],
                    icon: Icons.view_agenda_outlined,
                    isSelected: _selectedAuthorFilter == _AuthorFilter.all,
                    onTap: () => setState(() => _selectedAuthorFilter = _AuthorFilter.all),
                  ),
                  const SizedBox(width: 8),
                  _FilterSegmentChip(
                    label: copy[ConsumerTerm.socialFilterOfficial],
                    icon: Icons.verified_user_outlined,
                    isSelected: _selectedAuthorFilter == _AuthorFilter.official,
                    onTap: () => setState(() => _selectedAuthorFilter = _AuthorFilter.official),
                  ),
                  const SizedBox(width: 8),
                  _FilterSegmentChip(
                    label: copy[ConsumerTerm.socialFilterPeers],
                    icon: Icons.people_outline,
                    isSelected: _selectedAuthorFilter == _AuthorFilter.peers,
                    onTap: () => setState(() => _selectedAuthorFilter = _AuthorFilter.peers),
                  ),
                  const SizedBox(width: 8),
                  _FilterSegmentChip(
                    label: copy[ConsumerTerm.socialBookmarksTab],
                    icon: Icons.bookmark_border,
                    badgeCount: _bookmarks.length,
                    isSelected: _selectedAuthorFilter == _AuthorFilter.bookmarks,
                    onTap: () => setState(() => _selectedAuthorFilter = _AuthorFilter.bookmarks),
                  ),
                ],
              ),
            ),
          ),

          SectionHeader(title: copy[ConsumerTerm.socialFeed]),

          if (filtered.isEmpty)
            Padding(
              padding: const EdgeInsets.all(ClaraTokens.spaceMd),
              child: ClaraEmptyState(
                title: copy[ConsumerTerm.socialEmptyFeed],
                description: _searchQuery.isNotEmpty
                    ? 'Không tìm thấy bài viết phù hợp với từ khóa.'
                    : 'Hãy là người đầu tiên chia sẻ kinh nghiệm trong cộng đồng.',
                primaryActionLabel: copy[ConsumerTerm.socialPost],
                onPrimaryAction: _openCompose,
              ),
            )
          else
            ...filtered.map((post) => Padding(
                  padding: const EdgeInsets.fromLTRB(ClaraTokens.spaceMd, 0,
                      ClaraTokens.spaceMd, ClaraTokens.spaceSm),
                  child: _PostCard(
                    post: post,
                    onReact: (kind) => _react(post, kind),
                    onToggleBookmark: () => _toggleBookmark(post),
                    onHide: () => _hidePost(post),
                    onDelete: () => _deletePost(post),
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

  Future<void> _leaveCommunity(Map<String, dynamic> community) async {
    final token = _token;
    if (token == null) return;
    final id = community['id'];
    if (id is! int) return;
    
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dlgContext) => AlertDialog(
        title: Text(_copy[ConsumerTerm.socialLeaveCommunity]),
        content: Text(_copy[ConsumerTerm.socialLeaveConfirm]),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dlgContext).pop(false),
            child: Text(_copy[ConsumerTerm.socialCancel]),
          ),
          TextButton(
            onPressed: () => Navigator.of(dlgContext).pop(true),
            child: Text(_copy[ConsumerTerm.socialLeaveCommunity]),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    try {
      await widget.apiClient
          .leaveSocialCommunity(accessToken: token, communityId: id);
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

  Future<void> _react(Map<String, dynamic> post, String kind) async {
    if (!_consentGranted) {
      await _showConsentSheet();
      if (!_consentGranted) return;
    }
    final token = _token;
    if (token == null) return;
    final id = post['id'];
    if (id is! int) return;
    try {
      await widget.apiClient
          .addSocialReaction(accessToken: token, postId: id, kind: kind);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(_copy[ConsumerTerm.socialReactionSent])),
      );
      await _load();
    } on ApiException catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(error.message)));
    }
  }

  Future<void> _toggleBookmark(Map<String, dynamic> post) async {
    final token = _token;
    if (token == null) return;
    final id = post['id'];
    if (id is! int) return;
    try {
      final res = await widget.apiClient.toggleSocialBookmark(accessToken: token, postId: id);
      final isBookmarked = res['bookmarked'] == true;
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(isBookmarked ? _copy[ConsumerTerm.socialBookmarkAdded] : _copy[ConsumerTerm.socialBookmarkRemoved])),
      );
      await _load();
    } on ApiException catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(error.message)));
    }
  }

  void _hidePost(Map<String, dynamic> post) {
    final id = post['id'];
    if (id is int) {
      setState(() => _hiddenPostIds.add(id));
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(_copy[ConsumerTerm.socialPostHidden])),
      );
    }
  }

  Future<void> _deletePost(Map<String, dynamic> post) async {
    final token = _token;
    if (token == null) return;
    final id = post['id'];
    if (id is! int) return;
    try {
      await widget.apiClient.deleteSocialPost(accessToken: token, postId: id);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Đã xóa bài viết.')),
      );
      await _load();
    } on ApiException catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(error.message)));
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
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: theme.colorScheme.outlineVariant.withOpacity(0.5)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.info_outline,
              size: 18, color: theme.colorScheme.onSurfaceVariant),
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

class _FilterSegmentChip extends StatelessWidget {
  const _FilterSegmentChip({
    required this.label,
    required this.icon,
    required this.isSelected,
    required this.onTap,
    this.badgeCount,
  });

  final String label;
  final IconData icon;
  final bool isSelected;
  final VoidCallback onTap;
  final int? badgeCount;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(20),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected
              ? theme.colorScheme.primaryContainer
              : theme.colorScheme.surface,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isSelected
                ? theme.colorScheme.primary
                : theme.colorScheme.outlineVariant,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 16,
              color: isSelected
                  ? theme.colorScheme.onPrimaryContainer
                  : theme.colorScheme.onSurfaceVariant,
            ),
            const SizedBox(width: 6),
            Text(
              label,
              style: theme.textTheme.labelMedium?.copyWith(
                fontWeight: isSelected ? FontWeight.w700 : FontWeight.normal,
                color: isSelected
                    ? theme.colorScheme.onPrimaryContainer
                    : theme.colorScheme.onSurface,
              ),
            ),
            if (badgeCount != null && badgeCount! > 0) ...[
              const SizedBox(width: 6),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: isSelected
                      ? theme.colorScheme.primary
                      : theme.colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  '$badgeCount',
                  style: theme.textTheme.labelSmall?.copyWith(
                    color: isSelected ? Colors.white : theme.colorScheme.onSurface,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _AllTopicsCard extends StatelessWidget {
  const _AllTopicsCard({
    required this.isSelected,
    required this.totalCount,
    required this.onTap,
    required this.copy,
  });

  final bool isSelected;
  final int totalCount;
  final VoidCallback onTap;
  final ConsumerTerminology copy;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        width: 150,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: isSelected ? theme.colorScheme.primaryContainer.withOpacity(0.4) : theme.colorScheme.surface,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isSelected ? theme.colorScheme.primary : theme.colorScheme.outlineVariant,
            width: isSelected ? 2 : 1,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.hub_outlined, color: isSelected ? theme.colorScheme.primary : theme.colorScheme.onSurfaceVariant),
                const SizedBox(height: 6),
                Text(
                  copy[ConsumerTerm.socialAllTopics],
                  style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700),
                ),
              ],
            ),
            Text(
              '$totalCount bài viết',
              style: theme.textTheme.labelSmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
          ],
        ),
      ),
    );
  }
}

class _CommunityChip extends StatelessWidget {
  const _CommunityChip({
    required this.community,
    required this.isSelected,
    required this.onTap,
    required this.onJoin,
    required this.onLeave,
    required this.copy,
  });

  final Map<String, dynamic> community;
  final bool isSelected;
  final VoidCallback onTap;
  final VoidCallback onJoin;
  final VoidCallback onLeave;
  final ConsumerTerminology copy;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final joined = community['joined'] == true;
    final name = (community['name'] ?? '').toString();
    final members = community['member_count'];

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        width: 180,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: isSelected ? theme.colorScheme.primaryContainer.withOpacity(0.35) : theme.colorScheme.surface,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isSelected ? theme.colorScheme.primary : theme.colorScheme.outlineVariant,
            width: isSelected ? 2 : 1,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  name,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 4),
                Text(
                  copy.format(ConsumerTerm.socialMembers, {'count': members ?? 0}),
                  style: theme.textTheme.labelSmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                ),
              ],
            ),
            SizedBox(
              width: double.infinity,
              height: 32,
              child: joined
                  ? OutlinedButton(
                      onPressed: onLeave,
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(horizontal: 8),
                      ),
                      child: Text(copy[ConsumerTerm.socialJoined], style: const TextStyle(fontSize: 12)),
                    )
                  : FilledButton.tonal(
                      onPressed: onJoin,
                      style: FilledButton.styleFrom(
                        padding: const EdgeInsets.symmetric(horizontal: 8),
                      ),
                      child: Text(copy[ConsumerTerm.socialJoin], style: const TextStyle(fontSize: 12)),
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PostCard extends StatelessWidget {
  const _PostCard({
    required this.post,
    required this.onReact,
    required this.onToggleBookmark,
    required this.onHide,
    required this.onDelete,
    required this.onOpen,
    required this.copy,
  });

  final Map<String, dynamic> post;
  final Function(String kind) onReact;
  final VoidCallback onToggleBookmark;
  final VoidCallback onHide;
  final VoidCallback onDelete;
  final VoidCallback onOpen;
  final ConsumerTerminology copy;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final title = (post['title'] ?? '').toString();
    final body = (post['body'] ?? '').toString();
    final author = (post['author_handle'] ?? copy[ConsumerTerm.socialAnonymous]).toString();
    final displayName = (post['author_display_name'] ?? author).toString();
    final isVerified = post['is_verified_clinician'] == true;
    final isBookmarked = post['is_bookmarked'] == true;
    final comments = post['comment_count'] ?? 0;
    final reactionCount = post['reaction_count'] ?? 0;
    final userReaction = post['user_reaction']?.toString();

    return ClaraCard(
      semanticLabel: title,
      onTap: onOpen,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              CircleAvatar(
                radius: 16,
                backgroundColor: isVerified
                    ? theme.colorScheme.primary
                    : theme.colorScheme.primaryContainer,
                child: Text(
                  displayName.isNotEmpty
                      ? displayName.substring(0, 1).toUpperCase()
                      : '?',
                  style: TextStyle(
                    color: isVerified ? Colors.white : theme.colorScheme.onPrimaryContainer,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Flexible(
                          child: Text(
                            displayName,
                            overflow: TextOverflow.ellipsis,
                            style: theme.textTheme.labelMedium?.copyWith(fontWeight: FontWeight.w700),
                          ),
                        ),
                        if (isVerified) ...[
                          const SizedBox(width: 4),
                          ClaraStatusBadge(
                            label: copy[ConsumerTerm.socialOfficialBadge],
                            tone: ClaraStatusTone.info,
                          ),
                        ],
                      ],
                    ),
                    Text('@$author', style: theme.textTheme.labelSmall?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
                  ],
                ),
              ),
              IconButton(
                key: Key('post-bookmark-${post['id']}'),
                icon: Icon(
                  isBookmarked ? Icons.bookmark : Icons.bookmark_border,
                  color: isBookmarked ? theme.colorScheme.primary : theme.colorScheme.onSurfaceVariant,
                  size: 20,
                ),
                onPressed: onToggleBookmark,
                tooltip: isBookmarked ? copy[ConsumerTerm.socialBookmarkRemoved] : copy[ConsumerTerm.socialBookmarkAdded],
              ),
              PopupMenuButton<String>(
                icon: Icon(Icons.more_vert, size: 20, color: theme.colorScheme.onSurfaceVariant),
                onSelected: (val) {
                  if (val == 'hide') onHide();
                  if (val == 'delete') onDelete();
                },
                itemBuilder: (_) => [
                  PopupMenuItem(
                    value: 'hide',
                    child: Row(
                      children: [
                        const Icon(Icons.visibility_off_outlined, size: 18),
                        const SizedBox(width: 8),
                        Text(copy[ConsumerTerm.socialHideAction]),
                      ],
                    ),
                  ),
                  const PopupMenuItem(
                    value: 'delete',
                    child: Row(
                      children: [
                        Icon(Icons.delete_outline, size: 18, color: Colors.red),
                        SizedBox(width: 8),
                        Text('Xóa bài viết', style: TextStyle(color: Colors.red)),
                      ],
                    ),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(title,
              style: theme.textTheme.titleMedium
                  ?.copyWith(fontWeight: FontWeight.w700)),
          const SizedBox(height: 4),
          Text(body,
              maxLines: 5,
              overflow: TextOverflow.ellipsis,
              style: theme.textTheme.bodyMedium),
          const SizedBox(height: 12),
          
          // Reactions and Comments Row
          Wrap(
            spacing: 8,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              _ReactionButton(
                label: copy[ConsumerTerm.socialReactionHelpful],
                icon: Icons.thumb_up_alt_outlined,
                isActive: userReaction == 'helpful',
                onTap: () => onReact('helpful'),
              ),
              _ReactionButton(
                label: copy[ConsumerTerm.socialReactionRelate],
                icon: Icons.favorite_border,
                isActive: userReaction == 'relate',
                onTap: () => onReact('relate'),
              ),
              _ReactionButton(
                label: copy[ConsumerTerm.socialReactionThanks],
                icon: Icons.handshake_outlined,
                isActive: userReaction == 'thanks',
                onTap: () => onReact('thanks'),
              ),
              if (reactionCount > 0)
                Text(
                  '$reactionCount',
                  style: theme.textTheme.labelSmall?.copyWith(fontWeight: FontWeight.bold),
                ),
              const SizedBox(width: 8),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
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
        ],
      ),
    );
  }
}

class _ReactionButton extends StatelessWidget {
  const _ReactionButton({
    required this.label,
    required this.icon,
    required this.isActive,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final bool isActive;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: isActive ? theme.colorScheme.primaryContainer : Colors.transparent,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: isActive ? theme.colorScheme.primary : theme.colorScheme.outlineVariant.withOpacity(0.5),
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 14, color: isActive ? theme.colorScheme.primary : theme.colorScheme.onSurfaceVariant),
            const SizedBox(width: 4),
            Text(
              label,
              style: TextStyle(
                fontSize: 11,
                fontWeight: isActive ? FontWeight.bold : FontWeight.normal,
                color: isActive ? theme.colorScheme.onPrimaryContainer : theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
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
    this.initialCommunityId,
  });

  final ApiClient apiClient;
  final String accessToken;
  final List<Map<String, dynamic>> communities;
  final ConsumerTerminology copy;
  final int? initialCommunityId;

  @override
  State<_ComposeSheet> createState() => _ComposeSheetState();
}

class _ComposeSheetState extends State<_ComposeSheet> {
  int? _communityId;
  final _titleController = TextEditingController();
  final _bodyController = TextEditingController();
  bool _submitting = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _communityId = widget.initialCommunityId ?? (widget.communities.isNotEmpty ? widget.communities.first['id'] as int? : null);
  }

  @override
  void dispose() {
    _titleController.dispose();
    _bodyController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final id = _communityId;
    if (id == null) return;
    final title = _titleController.text.trim();
    final body = _bodyController.text.trim();
    if (title.isEmpty || body.isEmpty) {
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
        communityId: id,
        title: title,
        body: body,
      );
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        if (error.statusCode == 422) {
          _error = widget.copy[ConsumerTerm.socialModerationBlocked];
        } else {
          _error = error.message;
        }
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _error = widget.copy[ConsumerTerm.socialLoadFailed];
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
                style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),

            // Safety Guidelines Box
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.amber.withOpacity(0.12),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.amber.withOpacity(0.4)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.shield_outlined, color: Colors.amber, size: 20),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      widget.copy[ConsumerTerm.socialSafetyGuidelinesText],
                      style: const TextStyle(fontSize: 11),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: ClaraTokens.spaceMd),

            DropdownButtonFormField<int>(
              value: _communityId,
              decoration: InputDecoration(
                labelText: widget.copy[ConsumerTerm.socialCommunityLabel],
                border: const OutlineInputBorder(),
              ),
              items: widget.communities
                  .map((c) => DropdownMenuItem<int>(
                        value: c['id'] as int,
                        child: Text((c['name'] ?? '').toString()),
                      ))
                  .toList(),
              onChanged: (v) => setState(() => _communityId = v),
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            ClaraInput(
              controller: _titleController,
              label: widget.copy[ConsumerTerm.socialPostTitleLabel],
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            ClaraInput(
              controller: _bodyController,
              label: widget.copy[ConsumerTerm.socialPostBodyLabel],
              maxLines: 5,
            ),
            if (_error != null) ...[
              const SizedBox(height: ClaraTokens.spaceSm),
              Text(_error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ],
            const SizedBox(height: ClaraTokens.spaceMd),
            SizedBox(
              width: double.infinity,
              child: ClaraButton.primary(
                label: widget.copy[ConsumerTerm.socialPost],
                icon: Icons.send,
                onPressed: _submitting ? null : _submit,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

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
  bool _loading = true;
  String? _error;
  List<Map<String, dynamic>> _comments = const [];
  final _commentController = TextEditingController();
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    _loadComments();
  }

  @override
  void dispose() {
    _commentController.dispose();
    super.dispose();
  }

  int get _postId => widget.post['id'] as int;

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
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = widget.copy[ConsumerTerm.socialLoadFailed];
        _loading = false;
      });
    }
  }

  Future<void> _submitComment() async {
    final text = _commentController.text.trim();
    if (text.isEmpty) return;
    setState(() => _submitting = true);
    try {
      await widget.apiClient.addSocialComment(
        accessToken: widget.accessToken,
        postId: _postId,
        body: text,
      );
      _commentController.clear();
      await _loadComments();
    } on ApiException catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(error.statusCode == 422
              ? widget.copy[ConsumerTerm.socialModerationBlocked]
              : error.message),
        ),
      );
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _report(String targetType, int targetId) async {
    final reason = await showDialog<String>(
      context: context,
      builder: (dlgContext) => SimpleDialog(
        title: Text(widget.copy[ConsumerTerm.socialReport]),
        children: [
          SimpleDialogOption(
            onPressed: () => Navigator.pop(dlgContext, 'misinformation'),
            child: Text(widget.copy[ConsumerTerm.socialReportReasonMisinformation]),
          ),
          SimpleDialogOption(
            onPressed: () => Navigator.pop(dlgContext, 'unauthorized_prescribing'),
            child: Text(widget.copy[ConsumerTerm.socialReportReasonPrescribing]),
          ),
          SimpleDialogOption(
            onPressed: () => Navigator.pop(dlgContext, 'pii_disclosure'),
            child: Text(widget.copy[ConsumerTerm.socialReportReasonPii]),
          ),
          SimpleDialogOption(
            onPressed: () => Navigator.pop(dlgContext, 'harassment_spam'),
            child: Text(widget.copy[ConsumerTerm.socialReportReasonSpam]),
          ),
        ],
      ),
    );
    if (reason == null) return;

    try {
      await widget.apiClient.reportSocialContent(
        accessToken: widget.accessToken,
        targetType: targetType,
        targetId: targetId,
        reason: reason,
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
    final author = (widget.post['author_handle'] ?? widget.copy[ConsumerTerm.socialAnonymous]).toString();

    return Padding(
      padding: EdgeInsets.fromLTRB(
        ClaraTokens.spaceMd,
        ClaraTokens.spaceMd,
        ClaraTokens.spaceMd,
        ClaraTokens.spaceMd + MediaQuery.of(context).viewInsets.bottom,
      ),
      child: SizedBox(
        height: MediaQuery.of(context).size.height * 0.85,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(title,
                      style: theme.textTheme.titleMedium
                          ?.copyWith(fontWeight: FontWeight.w700)),
                ),
                IconButton(
                  onPressed: () => _report('post', _postId),
                  icon: const Icon(Icons.flag_outlined, size: 20),
                  tooltip: widget.copy[ConsumerTerm.socialReport],
                ),
                IconButton(
                  onPressed: () => Navigator.of(context).pop(true),
                  icon: const Icon(Icons.close),
                ),
              ],
            ),
            Text('@$author',
                style: theme.textTheme.labelMedium
                    ?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
            const SizedBox(height: ClaraTokens.spaceSm),
            Text(body, style: theme.textTheme.bodyMedium),
            const Divider(height: ClaraTokens.spaceLg),
            Text(widget.copy[ConsumerTerm.socialComments],
                style: theme.textTheme.titleSmall),
            const SizedBox(height: ClaraTokens.spaceSm),
            Expanded(
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : _error != null
                      ? Center(child: Text(_error!))
                      : _comments.isEmpty
                          ? Center(child: Text(widget.copy[ConsumerTerm.socialEmptyComments]))
                          : ListView.separated(
                              itemCount: _comments.length,
                              separatorBuilder: (_, __) => const Divider(height: 12),
                              itemBuilder: (_, i) {
                                final c = _comments[i];
                                final cAuthor = (c['author_handle'] ?? '').toString();
                                final cBody = (c['body'] ?? '').toString();
                                final cId = c['id'] as int? ?? 0;
                                final isClinician = c['is_verified_clinician'] == true;

                                return Padding(
                                  padding: const EdgeInsets.symmetric(vertical: 4),
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Row(
                                        children: [
                                          Text('@$cAuthor',
                                              style: theme.textTheme.labelMedium?.copyWith(fontWeight: FontWeight.w700)),
                                          if (isClinician) ...[
                                            const SizedBox(width: 4),
                                            ClaraStatusBadge(
                                              label: widget.copy[ConsumerTerm.socialOfficialBadge],
                                              tone: ClaraStatusTone.info,
                                            ),
                                          ],
                                          const Spacer(),
                                          IconButton(
                                            icon: const Icon(Icons.flag_outlined, size: 16),
                                            padding: EdgeInsets.zero,
                                            constraints: const BoxConstraints(),
                                            onPressed: () => _report('comment', cId),
                                          ),
                                        ],
                                      ),
                                      const SizedBox(height: 2),
                                      Text(cBody, style: theme.textTheme.bodySmall),
                                    ],
                                  ),
                                );
                              },
                            ),
            ),
            if (widget.canParticipate) ...[
              const SizedBox(height: ClaraTokens.spaceSm),
              Row(
                children: [
                  Expanded(
                    child: ClaraInput(
                      controller: _commentController,
                      label: widget.copy[ConsumerTerm.socialCommentLabel],
                    ),
                  ),
                  const SizedBox(width: ClaraTokens.spaceSm),
                  IconButton.filled(
                    onPressed: _submitting ? null : _submitComment,
                    icon: const Icon(Icons.send, size: 18),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

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
  bool _loading = true;
  bool _saving = false;
  String? _error;
  String? _handle;
  String? _roleBadge;
  final _displayNameController = TextEditingController();
  final _bioController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _displayNameController.dispose();
    _bioController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final profile = await widget.apiClient
          .getSocialProfile(accessToken: widget.accessToken);
      if (!mounted) return;
      setState(() {
        _handle = profile['handle']?.toString();
        _roleBadge = profile['role_badge']?.toString();
        _displayNameController.text =
            (profile['display_name'] ?? '').toString();
        _bioController.text = (profile['bio'] ?? '').toString();
        _loading = false;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.message;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = widget.copy[ConsumerTerm.socialLoadFailed];
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
        displayName: _displayNameController.text.trim(),
        bio: _bioController.text.trim(),
      );
      if (!mounted) return;
      Navigator.of(context).pop();
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = error.message;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = widget.copy[ConsumerTerm.socialLoadFailed];
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: EdgeInsets.fromLTRB(
        ClaraTokens.spaceMd,
        ClaraTokens.spaceMd,
        ClaraTokens.spaceMd,
        ClaraTokens.spaceMd + MediaQuery.of(context).viewInsets.bottom,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(widget.copy[ConsumerTerm.socialProfileTitle],
              style: theme.textTheme.titleMedium
                  ?.copyWith(fontWeight: FontWeight.w700)),
          const SizedBox(height: ClaraTokens.spaceSm),
          if (_loading)
            const Center(
              child: Padding(
                padding: EdgeInsets.all(ClaraTokens.spaceLg),
                child: CircularProgressIndicator(),
              ),
            )
          else ...[
            if (_handle != null) ...[
              Row(
                children: [
                  Text('@$_handle', style: theme.textTheme.titleSmall),
                  if (_roleBadge != null && _roleBadge!.isNotEmpty) ...[
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: theme.colorScheme.primaryContainer,
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        _roleBadge!,
                        style: theme.textTheme.labelSmall?.copyWith(
                            color: theme.colorScheme.onPrimaryContainer),
                      ),
                    ),
                  ],
                ],
              ),
              const SizedBox(height: ClaraTokens.spaceSm),
            ],
            ClaraInput(
              controller: _displayNameController,
              label: widget.copy[ConsumerTerm.socialDisplayNameLabel],
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            ClaraInput(
              controller: _bioController,
              label: widget.copy[ConsumerTerm.socialBioLabel],
              maxLines: 3,
            ),
            if (_error != null) ...[
              const SizedBox(height: ClaraTokens.spaceSm),
              Text(_error!, style: TextStyle(color: theme.colorScheme.error)),
            ],
            const SizedBox(height: ClaraTokens.spaceMd),
            SizedBox(
              width: double.infinity,
              child: ClaraButton.primary(
                label: widget.copy[ConsumerTerm.socialSaveProfile],
                icon: Icons.save_outlined,
                onPressed: _saving ? null : _save,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
