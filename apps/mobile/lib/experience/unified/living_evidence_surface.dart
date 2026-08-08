// Living Evidence for the unified CLARA mobile experience.
//
// New search results never become consumer notifications by themselves. The
// API exposes only reviewed material changes, and this surface keeps
// applicability/contradiction states visibly separate from medical advice.

import 'dart:async';

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

List<Map<String, dynamic>> _rows(Map<String, dynamic> response) {
  final raw = response['data'] ?? response['items'] ?? response['results'];
  if (raw is! List) return const <Map<String, dynamic>>[];
  return raw
      .whereType<Map>()
      .map((item) => item.cast<String, dynamic>())
      .toList();
}

String _text(Object? value) => value?.toString() ?? '';

class LivingEvidenceSurface extends StatefulWidget {
  const LivingEvidenceSurface({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    this.languageController,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;
  final LanguageController? languageController;

  @override
  State<LivingEvidenceSurface> createState() => _LivingEvidenceSurfaceState();
}

class _LivingEvidenceSurfaceState extends State<LivingEvidenceSurface> {
  final _question = TextEditingController();
  final _context = TextEditingController();
  bool _loading = true;
  bool _working = false;
  String? _error;
  String? _episodeId;
  List<Map<String, dynamic>> _episodes = const [];
  List<Map<String, dynamic>> _subscriptions = const [];
  List<Map<String, dynamic>> _notifications = const [];
  final Map<String, Map<String, dynamic>> _applicability = {};
  final Map<String, Map<String, dynamic>> _contradictions = {};

  ConsumerTerminology get _copy => ConsumerTerminology.forLocale(
        widget.languageController?.languageCode,
      );

  String? get _token {
    final value = widget.sessionStore.accessToken;
    return value == null || value.isEmpty ? null : value;
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _question.dispose();
    _context.dispose();
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
        widget.apiClient.getLifeMapToday(accessToken: token),
        widget.apiClient.getEvidenceSubscriptions(accessToken: token),
        widget.apiClient.getEvidenceChangeNotifications(accessToken: token),
      ]);
      final episodes = _rows(<String, dynamic>{
        'data': results[0]['episodes'],
      });
      final subscriptions = _rows(results[1]);
      final notifications = _rows(results[2]);
      _applicability.clear();
      _contradictions.clear();
      for (final subscription in subscriptions) {
        if (_text(subscription['status']) != 'active') continue;
        final runId = _text(subscription['evidence_run_id']);
        if (runId.isEmpty) continue;
        final detail = await Future.wait(<Future<Map<String, dynamic>>>[
          widget.apiClient.getEvidenceApplicability(
            accessToken: token,
            runId: runId,
          ),
          widget.apiClient.getEvidenceContradictions(
            accessToken: token,
            runId: runId,
          ),
        ]);
        _applicability[runId] = detail[0];
        _contradictions[runId] = detail[1];
      }
      if (!mounted) return;
      setState(() {
        _episodes = episodes;
        _episodeId = _episodeId ??
            (episodes.isEmpty ? null : _text(episodes.first['id']));
        _subscriptions = subscriptions;
        _notifications = notifications;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = error is ApiException
            ? error.message
            : _copy[ConsumerTerm.livingEvidenceLoadFailed];
      });
    }
  }

  Future<void> _createAndRun() async {
    final token = _token;
    final episodeId = _episodeId;
    final prompt = _question.text.trim();
    if (token == null || episodeId == null || prompt.length < 8) return;
    setState(() {
      _working = true;
      _error = null;
    });
    try {
      final created = await widget.apiClient.createEvidenceQuestion(
        accessToken: token,
        episodeId: episodeId,
        question: prompt,
        populationContext: _context.text.trim(),
      );
      final questionId = _text(created['id']);
      await widget.apiClient.confirmEvidenceQuestion(
        accessToken: token,
        questionId: questionId,
      );
      var run = await widget.apiClient.runEvidenceQuestion(
        accessToken: token,
        questionId: questionId,
      );
      final runId = _text(run['id']);
      for (var attempt = 0;
          attempt < 60 &&
              !const {'completed', 'failed', 'cancelled'}
                  .contains(_text(run['status']));
          attempt += 1) {
        await Future<void>.delayed(const Duration(seconds: 2));
        run = await widget.apiClient.getEvidenceRun(
          accessToken: token,
          runId: runId,
        );
      }
      if (_text(run['status']) != 'completed') {
        throw ApiException(
          message: _copy[ConsumerTerm.livingEvidenceRunIncomplete],
        );
      }
      await widget.apiClient.subscribeToEvidenceRun(
        accessToken: token,
        runId: runId,
      );
      _question.clear();
      _context.clear();
      await _load();
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error is ApiException
            ? error.message
            : _copy[ConsumerTerm.livingEvidenceCreateFailed];
      });
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  Future<void> _setInterval(Map<String, dynamic> item, int hours) async {
    final token = _token;
    if (token == null) return;
    setState(() => _working = true);
    try {
      await widget.apiClient.updateEvidenceSubscription(
        accessToken: token,
        subscriptionId: _text(item['id']),
        intervalHours: hours,
      );
      await _load();
    } catch (error) {
      if (mounted) {
        setState(() => _error = error is ApiException
            ? error.message
            : _copy[ConsumerTerm.livingEvidenceIntervalFailed]);
      }
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  Future<void> _revoke(Map<String, dynamic> item) async {
    final token = _token;
    if (token == null) return;
    setState(() => _working = true);
    try {
      await widget.apiClient.revokeEvidenceSubscription(
        accessToken: token,
        subscriptionId: _text(item['id']),
      );
      await _load();
    } catch (error) {
      if (mounted) {
        setState(() => _error = error is ApiException
            ? error.message
            : _copy[ConsumerTerm.livingEvidenceStopFailed]);
      }
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  Future<void> _read(Map<String, dynamic> item) async {
    final token = _token;
    if (token == null || _text(item['status']) == 'read') return;
    await widget.apiClient.readEvidenceChangeNotification(
      accessToken: token,
      notificationId: _text(item['id']),
    );
    await _load();
  }

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
      appBar: AppBar(title: Text(_copy[ConsumerTerm.livingEvidenceTitle])),
      body: SafeArea(
        child: _loading
            ? const ClaraSkeletonList(itemCount: 4)
            : _error != null && _subscriptions.isEmpty
                ? ErrorRetryView(message: _error!, onRetry: _load)
                : RefreshIndicator(
                    onRefresh: _load,
                    child: ListView(
                      padding: const EdgeInsets.all(ClaraTokens.spaceMd),
                      children: [
                        if (_error != null)
                          Padding(
                            padding: const EdgeInsets.only(
                                bottom: ClaraTokens.spaceMd),
                            child: Text(
                              _error!,
                              style: TextStyle(
                                  color: Theme.of(context).colorScheme.error),
                            ),
                          ),
                        Text(
                          _copy[ConsumerTerm.livingEvidenceSafetyNotice],
                        ),
                        const SizedBox(height: ClaraTokens.spaceMd),
                        if (_notifications.isNotEmpty) ...[
                          SectionHeader(
                            title: _copy[
                                ConsumerTerm.livingEvidenceReviewedChanges],
                          ),
                          for (final item in _notifications)
                            Padding(
                              padding: const EdgeInsets.only(
                                  bottom: ClaraTokens.spaceSm),
                              child: ClaraCard(
                                semanticLabel: _copy[ConsumerTerm
                                    .livingEvidenceNotificationSemanticLabel],
                                onTap: () => _read(item),
                                child: ListTile(
                                  contentPadding: EdgeInsets.zero,
                                  leading: const Icon(Icons.verified_outlined),
                                  title: Text(
                                    _text(
                                        (item['payload'] as Map?)?['message']),
                                  ),
                                  subtitle: Text(
                                    _text(item['status']) == 'read'
                                        ? _copy[ConsumerTerm.livingEvidenceRead]
                                        : _copy[ConsumerTerm
                                            .livingEvidenceMarkRead],
                                  ),
                                ),
                              ),
                            ),
                        ],
                        SectionHeader(
                          title:
                              _copy[ConsumerTerm.livingEvidenceSubscriptions],
                        ),
                        if (_subscriptions
                            .where((item) => _text(item['status']) == 'active')
                            .isEmpty)
                          ClaraEmptyState(
                            icon: Icons.fact_check_outlined,
                            title: _copy[ConsumerTerm.livingEvidenceEmptyTitle],
                            message: _copy[
                                ConsumerTerm.livingEvidenceEmptyDescription],
                          )
                        else
                          for (final item in _subscriptions.where(
                            (entry) => _text(entry['status']) == 'active',
                          ))
                            _subscriptionCard(item),
                        const SizedBox(height: ClaraTokens.spaceMd),
                        SectionHeader(
                          title: _copy[ConsumerTerm.livingEvidenceNewQuestion],
                        ),
                        ClaraCard.static_(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              if (_episodes.isNotEmpty)
                                DropdownButtonFormField<String>(
                                  initialValue: _episodeId,
                                  decoration: InputDecoration(
                                    labelText: _copy[ConsumerTerm
                                        .livingEvidenceJourneyLabel],
                                  ),
                                  items: _episodes.map((episode) {
                                    return DropdownMenuItem<String>(
                                      value: _text(episode['id']),
                                      child: Text(_text(episode['title'])),
                                    );
                                  }).toList(),
                                  onChanged: _working
                                      ? null
                                      : (value) =>
                                          setState(() => _episodeId = value),
                                ),
                              const SizedBox(height: ClaraTokens.spaceSm),
                              TextField(
                                controller: _question,
                                minLines: 2,
                                maxLines: 5,
                                decoration: InputDecoration(
                                  labelText: _copy[
                                      ConsumerTerm.livingEvidenceQuestionLabel],
                                ),
                              ),
                              const SizedBox(height: ClaraTokens.spaceSm),
                              TextField(
                                controller: _context,
                                minLines: 1,
                                maxLines: 3,
                                decoration: InputDecoration(
                                  labelText: _copy[
                                      ConsumerTerm.livingEvidenceContextLabel],
                                ),
                              ),
                              const SizedBox(height: ClaraTokens.spaceMd),
                              ClaraButton.primary(
                                label: _copy[
                                    ConsumerTerm.livingEvidenceCreateAndFollow],
                                loading: _working,
                                onPressed:
                                    _episodes.isEmpty ? null : _createAndRun,
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
      ),
    );
  }

  Widget _subscriptionCard(Map<String, dynamic> item) {
    final runId = _text(item['evidence_run_id']);
    final applicability = _applicability[runId];
    final contradictions = _contradictions[runId];
    final contradictionItems = contradictions?['items'];
    final contradictionCount =
        contradictionItems is List ? contradictionItems.length : 0;
    final interval = (item['interval_hours'] as num?)?.toInt() ?? 168;
    return Padding(
      padding: const EdgeInsets.only(bottom: ClaraTokens.spaceSm),
      child: ClaraCard.static_(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              _copy[ConsumerTerm.livingEvidenceSubscriptionTitle],
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: ClaraTokens.spaceXs),
            Text(
              applicability?['safe_message']?.toString() ??
                  _copy[ConsumerTerm.livingEvidenceApplicabilityPending],
            ),
            const SizedBox(height: ClaraTokens.spaceXs),
            Text(
              contradictionCount == 0
                  ? _copy[ConsumerTerm.livingEvidenceNoContradictions]
                  : _copy.format(
                      ConsumerTerm.livingEvidenceContradictionsCount,
                      <String, Object?>{'count': contradictionCount},
                    ),
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            DropdownButtonFormField<int>(
              initialValue: interval,
              decoration: InputDecoration(
                labelText: _copy[ConsumerTerm.livingEvidenceIntervalLabel],
              ),
              items: [
                DropdownMenuItem(
                  value: 24,
                  child: Text(_copy[ConsumerTerm.livingEvidenceEveryDay]),
                ),
                DropdownMenuItem(
                  value: 168,
                  child: Text(_copy[ConsumerTerm.livingEvidenceEveryWeek]),
                ),
                DropdownMenuItem(
                  value: 720,
                  child: Text(
                    _copy[ConsumerTerm.livingEvidenceEveryThirtyDays],
                  ),
                ),
              ],
              onChanged: _working
                  ? null
                  : (value) {
                      if (value != null) _setInterval(item, value);
                    },
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            ClaraButton.secondary(
              label: _copy[ConsumerTerm.livingEvidenceStopFollowing],
              onPressed: _working ? null : () => _revoke(item),
            ),
          ],
        ),
      ),
    );
  }
}
