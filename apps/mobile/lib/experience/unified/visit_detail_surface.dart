import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/consumer_terminology.dart';
import '../../core/session_store.dart';
import '../../theme/components/clara_button.dart';
import '../../theme/components/clara_card.dart';
import '../../theme/tokens.dart';
import '../../widgets/error_retry_view.dart';
import '../language_controller.dart';

List<Map<String, dynamic>> _maps(Object? value) {
  if (value is! List) return const <Map<String, dynamic>>[];
  return value
      .whereType<Map>()
      .map((item) => item.cast<String, dynamic>())
      .toList(growable: false);
}

String _text(Object? value) => value?.toString().trim() ?? '';

/// Full, owner-controlled Visit lifecycle for the unified mobile experience.
///
/// Mutations are deliberately online-only. Extracted instructions remain
/// review-only until the owner checks a clinician instruction with an exact
/// source quote. Model interpretation can be displayed but never confirmed.
class VisitDetailSurface extends StatefulWidget {
  const VisitDetailSurface({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    required this.visitId,
    required this.title,
    this.languageController,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;
  final String visitId;
  final String title;
  final LanguageController? languageController;

  @override
  State<VisitDetailSurface> createState() => _VisitDetailSurfaceState();
}

class _VisitDetailSurfaceState extends State<VisitDetailSurface> {
  final _concernController = TextEditingController();
  final _documentTitleController = TextEditingController();
  final _documentTextController = TextEditingController();
  bool _loading = true;
  bool _saving = false;
  bool _scribeConsented = false;
  String? _error;
  List<Map<String, dynamic>> _documents = const [];
  Map<String, dynamic> _options = const {};
  Map<String, dynamic>? _draft;
  Set<String> _candidateIds = <String>{};
  Set<String> _packIds = <String>{};
  Map<String, dynamic>? _pack;
  Map<String, dynamic>? _share;

  String? get _token {
    final token = widget.sessionStore.accessToken;
    return token == null || token.isEmpty ? null : token;
  }

  ConsumerTerminology get _copy => ConsumerTerminology.forLocale(
        widget.languageController?.languageCode,
      );

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _concernController.dispose();
    _documentTitleController.dispose();
    _documentTextController.dispose();
    super.dispose();
  }

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
    try {
      final results = await Future.wait(<Future<Map<String, dynamic>>>[
        widget.apiClient.getVisitDocuments(
          accessToken: token,
          visitId: widget.visitId,
        ),
        widget.apiClient.getVisitPackOptions(
          accessToken: token,
          visitId: widget.visitId,
        ),
      ]);
      if (!mounted) return;
      setState(() {
        _documents = _maps(results[0]['data'] ?? results[0]['documents']);
        _options = results[1];
        _packIds = <String>{};
      });
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) {
        setState(() => _error = _copy[ConsumerTerm.visitDetailLoadFailed]);
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _run(Future<void> Function(String token) action) async {
    final token = _token;
    if (token == null || _saving) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await action(token);
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) {
        setState(
          () => _error = _copy[ConsumerTerm.visitDetailActionFailed],
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _addConcern() => _run((token) async {
        final value = _concernController.text.trim();
        if (value.length < 2) {
          throw ApiException(
            message: _copy[ConsumerTerm.visitDetailConcernRequired],
          );
        }
        await widget.apiClient.addVisitConcern(
          accessToken: token,
          visitId: widget.visitId,
          payload: <String, dynamic>{'text': value, 'priority': 'routine'},
        );
        _concernController.clear();
        await _load();
      });

  Future<void> _addDocument() => _run((token) async {
        final title = _documentTitleController.text.trim();
        final body = _documentTextController.text.trim();
        if (title.isEmpty || body.isEmpty) {
          throw ApiException(
            message: _copy[ConsumerTerm.visitDetailDocumentRequired],
          );
        }
        await widget.apiClient.createVisitDocument(
          accessToken: token,
          visitId: widget.visitId,
          payload: <String, dynamic>{
            'title': title,
            'text_content': body,
            'media_type': 'text/plain',
            'metadata': const <String, dynamic>{
              'capture': 'user_selected',
              'client': 'clara_mobile',
            },
          },
        );
        _documentTitleController.clear();
        _documentTextController.clear();
        await _load();
      });

  Future<void> _extract(Map<String, dynamic> document) => _run((token) async {
        final result = await widget.apiClient.extractVisitPlan(
          accessToken: token,
          visitId: widget.visitId,
          documentId: _text(document['id']),
        );
        if (!mounted) return;
        setState(() {
          _draft = result;
          _candidateIds = <String>{};
        });
      });

  Future<void> _withdrawDocument(Map<String, dynamic> document) =>
      _run((token) async {
        await widget.apiClient.withdrawVisitDocument(
          accessToken: token,
          visitId: widget.visitId,
          documentId: _text(document['id']),
        );
        await _load();
      });

  Future<void> _deleteDocument(Map<String, dynamic> document) =>
      _run((token) async {
        await widget.apiClient.deleteVisitDocument(
          accessToken: token,
          visitId: widget.visitId,
          documentId: _text(document['id']),
        );
        await _load();
      });

  Future<void> _confirmPlan() => _run((token) async {
        final draft = _draft;
        if (draft == null || _candidateIds.isEmpty) return;
        final result = await widget.apiClient.confirmVisitPlan(
          accessToken: token,
          visitId: widget.visitId,
          draftId: _text(draft['id']),
          candidateIds: _candidateIds.toList(growable: false),
        );
        if (mounted) setState(() => _draft = result);
      });

  Future<void> _withdrawPlan() => _run((token) async {
        final draft = _draft;
        if (draft == null) return;
        final result = await widget.apiClient.withdrawVisitPlan(
          accessToken: token,
          visitId: widget.visitId,
          draftId: _text(draft['id']),
        );
        if (mounted) {
          setState(() {
            _draft = result;
            _candidateIds = <String>{};
          });
        }
      });

  Future<void> _createAndApprovePack() => _run((token) async {
        List<String> selected(String key) => _maps(_options[key])
            .map((item) => _text(item['id']))
            .where(_packIds.contains)
            .toList(growable: false);

        final created = await widget.apiClient.createVisitPack(
          accessToken: token,
          visitId: widget.visitId,
          selection: <String, dynamic>{
            'concern_ids': selected('concerns'),
            'episode_ids': selected('episodes'),
            'event_ids': selected('events'),
            'medication_course_ids': selected('medications'),
            'instruction_candidate_ids': selected('instructions'),
            'questions': const <String>[],
          },
        );
        final approved = await widget.apiClient.approveVisitPack(
          accessToken: token,
          packId: _text(created['id']),
        );
        if (mounted) {
          setState(() {
            _pack = approved;
            _share = null;
          });
        }
      });

  Future<void> _createShare() => _run((token) async {
        final pack = _pack;
        if (pack == null) return;
        final result = await widget.apiClient.shareVisitPack(
          accessToken: token,
          packId: _text(pack['id']),
          expiresAt: DateTime.now().toUtc().add(const Duration(days: 7)),
        );
        if (mounted) setState(() => _share = result);
      });

  Future<void> _revokeShare() => _run((token) async {
        final pack = _pack;
        final share = _share;
        if (pack == null || share == null) return;
        await widget.apiClient.revokeVisitShare(
          accessToken: token,
          packId: _text(pack['id']),
          shareId: _text(share['id']),
        );
        if (mounted) setState(() => _share = null);
      });

  Future<void> _toggleScribeConsent() => _run((token) async {
        if (_scribeConsented) {
          await widget.apiClient.revokeVisitScribeConsent(
            accessToken: token,
            visitId: widget.visitId,
          );
        } else {
          await widget.apiClient.grantVisitScribeConsent(
            accessToken: token,
            visitId: widget.visitId,
          );
        }
        if (mounted) {
          setState(() => _scribeConsented = !_scribeConsented);
        }
      });

  @override
  Widget build(BuildContext context) {
    final languageController = widget.languageController;
    if (languageController != null) {
      return AnimatedBuilder(
        animation: languageController,
        builder: (context, _) => _buildSurface(context),
      );
    }
    return _buildSurface(context);
  }

  Widget _buildSurface(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(
          widget.title.isEmpty
              ? _copy[ConsumerTerm.visitsPreparationTitle]
              : widget.title,
        ),
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading && _documents.isEmpty
            ? ListView(
                children: const <Widget>[
                  SizedBox(height: 160),
                  Center(child: CircularProgressIndicator()),
                ],
              )
            : ListView(
                padding: const EdgeInsets.all(ClaraTokens.spaceMd),
                children: <Widget>[
                  if (_error != null) ...<Widget>[
                    ErrorRetryView(message: _error!, onRetry: _load),
                    const SizedBox(height: ClaraTokens.spaceMd),
                  ],
                  _notice(context),
                  const SizedBox(height: ClaraTokens.spaceMd),
                  _concernSection(context),
                  const SizedBox(height: ClaraTokens.spaceMd),
                  _documentSection(context),
                  if (_draft != null) ...<Widget>[
                    const SizedBox(height: ClaraTokens.spaceMd),
                    _reviewSection(context),
                  ],
                  const SizedBox(height: ClaraTokens.spaceMd),
                  _packSection(context),
                  const SizedBox(height: ClaraTokens.spaceMd),
                  _scribeSection(context),
                  const SizedBox(height: ClaraTokens.spaceXl),
                ],
              ),
      ),
    );
  }

  Widget _notice(BuildContext context) => ClaraCard.static_(
        child: Text(
          _copy[ConsumerTerm.visitDetailPreparationNotice],
          style: Theme.of(context).textTheme.bodyMedium,
        ),
      );

  Widget _concernSection(BuildContext context) => ClaraCard.static_(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(_copy[ConsumerTerm.visitDetailConcernsTitle],
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: ClaraTokens.spaceSm),
            TextField(
              controller: _concernController,
              minLines: 2,
              maxLines: 4,
              decoration: InputDecoration(
                labelText: _copy[ConsumerTerm.visitDetailConcernLabel],
              ),
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            ClaraButton.secondary(
              label: _copy[ConsumerTerm.visitDetailSaveConcern],
              icon: Icons.add_comment_outlined,
              loading: _saving,
              onPressed: _addConcern,
            ),
          ],
        ),
      );

  Widget _documentSection(BuildContext context) => ClaraCard.static_(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(_copy[ConsumerTerm.visitDetailDocumentsTitle],
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: ClaraTokens.spaceXs),
            Text(
              _copy[ConsumerTerm.visitDetailDocumentsDescription],
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            TextField(
              controller: _documentTitleController,
              decoration: InputDecoration(
                labelText: _copy[ConsumerTerm.visitDetailDocumentTitle],
              ),
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            TextField(
              controller: _documentTextController,
              minLines: 3,
              maxLines: 8,
              decoration: InputDecoration(
                labelText: _copy[ConsumerTerm.visitDetailDocumentContent],
              ),
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            ClaraButton.secondary(
              label: _copy[ConsumerTerm.visitDetailSaveDocument],
              icon: Icons.note_add_outlined,
              loading: _saving,
              onPressed: _addDocument,
            ),
            ..._documents.map((document) => _documentTile(context, document)),
          ],
        ),
      );

  Widget _documentTile(
    BuildContext context,
    Map<String, dynamic> document,
  ) {
    final inactive =
        document['withdrawn_at'] != null || document['deleted_at'] != null;
    return Padding(
      padding: const EdgeInsets.only(top: ClaraTokens.spaceMd),
      child: DecoratedBox(
        decoration: BoxDecoration(
          border:
              Border.all(color: Theme.of(context).colorScheme.outlineVariant),
          borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
        ),
        child: Padding(
          padding: const EdgeInsets.all(ClaraTokens.spaceSm),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(_text(document['title']),
                  style: Theme.of(context).textTheme.titleSmall),
              Text(
                inactive
                    ? _copy[ConsumerTerm.visitDetailInactiveDocument]
                    : _copy[ConsumerTerm.visitDetailControlledDocument],
                style: Theme.of(context).textTheme.bodySmall,
              ),
              if (!inactive)
                Wrap(
                  spacing: ClaraTokens.spaceXs,
                  children: <Widget>[
                    TextButton(
                      onPressed: _saving ? null : () => _extract(document),
                      child: Text(_copy[ConsumerTerm.visitDetailCheckPlan]),
                    ),
                    TextButton(
                      onPressed:
                          _saving ? null : () => _withdrawDocument(document),
                      child: Text(
                        _copy[ConsumerTerm.visitDetailWithdrawDocument],
                      ),
                    ),
                    TextButton(
                      onPressed:
                          _saving ? null : () => _deleteDocument(document),
                      child: Text(_copy[ConsumerTerm.visitDetailDeleteDocument]),
                    ),
                  ],
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _reviewSection(BuildContext context) {
    final draft = _draft!;
    final candidates = _maps(draft['candidates']);
    final unavailable = draft['safe_unavailable'] == true || candidates.isEmpty;
    return ClaraCard.static_(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(_copy[ConsumerTerm.visitDetailReviewTitle],
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: ClaraTokens.spaceXs),
          Text(
            unavailable
                ? _copy[ConsumerTerm.visitDetailNoEvidence]
                : _copy[ConsumerTerm.visitDetailReviewGuidance],
            style: Theme.of(context).textTheme.bodySmall,
          ),
          ...candidates.map((candidate) {
            final id = _text(candidate['id']);
            final spans = _maps(candidate['source_spans']);
            final source = spans
                .map((span) => _text(span['text']))
                .where((value) => value.isNotEmpty)
                .join(' … ');
            final confirmable =
                candidate['classification'] == 'clinician_instruction' &&
                    source.isNotEmpty;
            return CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              value: _candidateIds.contains(id),
              onChanged: confirmable && !_saving
                  ? (checked) => setState(() {
                        checked == true
                            ? _candidateIds.add(id)
                            : _candidateIds.remove(id);
                      })
                  : null,
              title: Text(_text(candidate['title'] ?? candidate['text'])),
              subtitle: Text(
                confirmable
                    ? _copy.format(
                        ConsumerTerm.visitDetailSource,
                        <String, Object?>{'source': source},
                      )
                    : _copy[ConsumerTerm.visitDetailUnconfirmableCandidate],
              ),
            );
          }),
          if (!unavailable)
            Wrap(
              spacing: ClaraTokens.spaceSm,
              children: <Widget>[
                ClaraButton.primary(
                  label: _copy[ConsumerTerm.visitDetailConfirmSelected],
                  icon: Icons.verified_outlined,
                  loading: _saving,
                  onPressed: _candidateIds.isEmpty ? null : _confirmPlan,
                ),
                TextButton(
                  onPressed: _saving ? null : _withdrawPlan,
                  child: Text(_copy[ConsumerTerm.visitDetailWithdrawDraft]),
                ),
              ],
            ),
        ],
      ),
    );
  }

  Widget _packSection(BuildContext context) {
    final groups = <(String, ConsumerTerm)>[
      ('concerns', ConsumerTerm.visitDetailPackConcerns),
      ('medications', ConsumerTerm.visitDetailPackMedications),
      ('episodes', ConsumerTerm.visitDetailPackEpisodes),
      ('events', ConsumerTerm.visitDetailPackEvents),
      ('instructions', ConsumerTerm.visitDetailPackInstructions),
    ];
    return ClaraCard.static_(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(_copy[ConsumerTerm.visitDetailPackTitle],
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: ClaraTokens.spaceXs),
          Text(
            _copy[ConsumerTerm.visitDetailPackNotice],
            style: Theme.of(context).textTheme.bodySmall,
          ),
          for (final group in groups) ...<Widget>[
            const SizedBox(height: ClaraTokens.spaceSm),
            Text(
              _copy[group.$2],
              style: Theme.of(context).textTheme.titleSmall,
            ),
            if (_maps(_options[group.$1]).isEmpty)
              Text(_copy[ConsumerTerm.visitDetailNoMatchingItems],
                  style: Theme.of(context).textTheme.bodySmall)
            else
              ..._maps(_options[group.$1]).map((item) {
                final id = _text(item['id']);
                return CheckboxListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  value: _packIds.contains(id),
                  onChanged: _saving
                      ? null
                      : (checked) => setState(() {
                            checked == true
                                ? _packIds.add(id)
                                : _packIds.remove(id);
                          }),
                  title: Text(_text(item['label'])),
                );
              }),
          ],
          ClaraButton.primary(
            label: _pack == null
                ? _copy[ConsumerTerm.visitDetailCreatePack]
                : _copy[ConsumerTerm.visitDetailCreateNewPackVersion],
            icon: Icons.inventory_2_outlined,
            loading: _saving,
            onPressed: _packIds.isEmpty ? null : _createAndApprovePack,
          ),
          if (_pack != null) ...<Widget>[
            const SizedBox(height: ClaraTokens.spaceSm),
            Text(
              _copy.format(
                ConsumerTerm.visitDetailApprovedPackVersion,
                <String, Object?>{'version': _text(_pack!['version_no'])},
              ),
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            if (_share == null)
              TextButton(
                onPressed: _saving ? null : _createShare,
                child: Text(_copy[ConsumerTerm.visitDetailCreateShare]),
              )
            else ...<Widget>[
              SelectableText(
                '/api/v1/visit-packs/shared/${_text(_share!['token'])}',
              ),
              TextButton(
                onPressed: _saving ? null : _revokeShare,
                child: Text(_copy[ConsumerTerm.visitDetailRevokeShare]),
              ),
            ],
          ],
        ],
      ),
    );
  }

  Widget _scribeSection(BuildContext context) => ClaraCard.static_(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(_copy[ConsumerTerm.visitDetailScribeConsentTitle],
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: ClaraTokens.spaceXs),
            Text(
              _copy[ConsumerTerm.visitDetailScribeConsentDescription],
              style: Theme.of(context).textTheme.bodySmall,
            ),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              value: _scribeConsented,
              onChanged: _saving ? null : (_) => _toggleScribeConsent(),
              title: Text(_scribeConsented
                  ? _copy[ConsumerTerm.visitDetailScribeConsentGranted]
                  : _copy[ConsumerTerm.visitDetailScribeConsentNotGranted]),
            ),
          ],
        ),
      );
}
