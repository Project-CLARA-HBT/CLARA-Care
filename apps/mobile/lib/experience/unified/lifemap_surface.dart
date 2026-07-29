// LifeMap planning surface for the CLARA_Mobile unified experience
// (clara-mobile-unified).
//
// `LifeMapSurface` is where the user PLANS their personal care: they create
// care journeys ("hành trình"), propose tasks under them, and accept tasks so
// those tasks flow into the Today agenda. Completion of accepted tasks lives on
// the Today surface, not here (this list is read-only for accepted tasks).
//
// Framing is non-clinical throughout: this is "kế hoạch cá nhân, không phải
// chẩn đoán" (a personal plan, not a diagnosis). CLARA is a clinical assistant,
// not a doctor.
//
// It reads its data from `ApiClient.getLifeMapToday` (which returns episodes +
// accepted tasks), and reuses the same loading/error/empty/409 handling as the
// Today surface. All copy is Vietnamese-first and PII-free.

import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/session_store.dart';
import '../../theme/components/clara_button.dart';
import '../../theme/components/clara_card.dart';
import '../../theme/components/section_header.dart';
import '../../theme/tokens.dart';
import '../../theme/web_palette.dart';
import '../../widgets/error_retry_view.dart';
import '../states/empty_state.dart';
import '../states/skeleton.dart';

String _str(Object? value) => value == null ? '' : value.toString();
String _shortRevision(Object? value) {
  final text = _str(value);
  return text.length <= 8 ? text : text.substring(0, 8);
}

/// Supported episode priorities and their Vietnamese labels.
const Map<String, String> _kPriorityLabels = <String, String>{
  'routine': 'Khi thuận tiện',
  'soon': 'Sớm',
  'urgent': 'Cần ưu tiên',
};

/// An open care episode with its priority.
class _Episode {
  const _Episode({
    required this.id,
    required this.title,
    required this.priority,
  });

  factory _Episode.fromJson(Map<String, dynamic> json) => _Episode(
        id: _str(json['id']),
        title: _str(json['title']),
        priority:
            _str(json['priority']).isEmpty ? 'routine' : _str(json['priority']),
      );

  final String id;
  final String title;
  final String priority;
}

/// An accepted task (read-only on this surface).
class _AcceptedTask {
  const _AcceptedTask({required this.id, required this.title});

  factory _AcceptedTask.fromJson(Map<String, dynamic> json) => _AcceptedTask(
        id: _str(json['id']),
        title: _str(json['title']),
      );

  final String id;
  final String title;
}

/// The LifeMap planning surface: create journeys, propose + accept tasks, and
/// review accepted tasks.
class LifeMapSurface extends StatefulWidget {
  const LifeMapSurface({
    super.key,
    required this.apiClient,
    required this.sessionStore,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  @override
  State<LifeMapSurface> createState() => _LifeMapSurfaceState();
}

class _LifeMapSurfaceState extends State<LifeMapSurface> {
  bool _loading = true;
  String? _error;
  bool _needsOnboarding = false;

  List<_Episode> _episodes = const [];
  List<_AcceptedTask> _tasks = const [];
  bool _captureEnabled = false;
  bool _questionEnabled = false;
  bool _askEnabled = false;
  List<Map<String, dynamic>> _baselines = const [];
  bool _capturing = false;
  Map<String, dynamic>? _captureSession;
  final TextEditingController _captureController = TextEditingController();
  final TextEditingController _askController = TextEditingController();
  bool _asking = false;
  Map<String, dynamic>? _askAnswer;

  // --- "Tạo hành trình" (create episode) form state ------------------------
  bool _episodeFormOpen = false;
  bool _creatingEpisode = false;
  final TextEditingController _episodeTitleController = TextEditingController();
  final TextEditingController _episodeGoalController = TextEditingController();
  String _episodePriority = 'routine';

  // --- "Thêm việc" (add task) form state -----------------------------------
  bool _taskFormOpen = false;
  bool _creatingTask = false;
  final TextEditingController _taskTitleController = TextEditingController();
  String? _selectedEpisodeId;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _episodeTitleController.dispose();
    _episodeGoalController.dispose();
    _taskTitleController.dispose();
    _captureController.dispose();
    _askController.dispose();
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
      _needsOnboarding = false;
    });
    try {
      final summary =
          await widget.apiClient.getMobileSummary(accessToken: token);
      final flags = summary['feature_flags'];
      final captureEnabled = flags is Map && flags['lifemap_capture'] == true;
      final questionEnabled =
          flags is Map && flags['lifemap_next_question_v2'] == true;
      final askEnabled = flags is Map && flags['lifemap_ask_ai'] == true;
      final baselineEnabled =
          flags is Map && flags['lifemap_baselines_v2'] == true;
      final baselinePayload = baselineEnabled
          ? await widget.apiClient.getLifeMapBaselines(accessToken: token)
          : const <String, dynamic>{};
      final baselines = <Map<String, dynamic>>[];
      final rawBaselines = baselinePayload['data'];
      if (rawBaselines is List) {
        for (final item in rawBaselines) {
          if (item is Map) baselines.add(item.cast<String, dynamic>());
        }
      }
      final data = await widget.apiClient.getLifeMapToday(accessToken: token);
      final episodes = <_Episode>[];
      final rawEpisodes = data['episodes'];
      if (rawEpisodes is List) {
        for (final item in rawEpisodes) {
          if (item is Map) {
            episodes.add(_Episode.fromJson(item.cast<String, dynamic>()));
          }
        }
      }
      final tasks = <_AcceptedTask>[];
      final rawTasks = data['tasks'];
      if (rawTasks is List) {
        for (final item in rawTasks) {
          if (item is Map) {
            tasks.add(_AcceptedTask.fromJson(item.cast<String, dynamic>()));
          }
        }
      }
      if (!mounted) return;
      setState(() {
        _episodes = episodes;
        _tasks = tasks;
        _captureEnabled = captureEnabled;
        _questionEnabled = questionEnabled;
        _askEnabled = askEnabled;
        _baselines = baselines;
        // Keep the task-form selection valid against the freshly loaded set.
        if (_selectedEpisodeId != null &&
            !episodes.any((e) => e.id == _selectedEpisodeId)) {
          _selectedEpisodeId = null;
        }
        _selectedEpisodeId ??= episodes.isNotEmpty ? episodes.first.id : null;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      if (error.statusCode == 409) {
        setState(() => _needsOnboarding = true);
        return;
      }
      setState(() => _error = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = 'Không thể tải LifeMap. Vui lòng thử lại.');
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _createEpisode() async {
    final token = _token;
    if (token == null || _creatingEpisode) return;
    final title = _episodeTitleController.text.trim();
    if (title.isEmpty) {
      _showSnack('Vui lòng nhập tên hành trình.');
      return;
    }
    setState(() => _creatingEpisode = true);
    try {
      await widget.apiClient.createLifeMapEpisode(
        accessToken: token,
        title: title,
        goal: _episodeGoalController.text.trim(),
        priority: _episodePriority,
      );
      _episodeTitleController.clear();
      _episodeGoalController.clear();
      if (mounted) {
        setState(() {
          _episodePriority = 'routine';
          _episodeFormOpen = false;
        });
      }
      await _load();
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack('Không thể tạo hành trình. Vui lòng thử lại.');
    } finally {
      if (mounted) {
        setState(() => _creatingEpisode = false);
      }
    }
  }

  Future<void> _createTask() async {
    final token = _token;
    if (token == null || _creatingTask) return;
    final episodeId = _selectedEpisodeId;
    if (episodeId == null || episodeId.isEmpty) {
      _showSnack('Vui lòng chọn một hành trình.');
      return;
    }
    final title = _taskTitleController.text.trim();
    if (title.isEmpty) {
      _showSnack('Vui lòng nhập tên việc.');
      return;
    }
    setState(() => _creatingTask = true);
    try {
      final created = await widget.apiClient.createLifeMapTask(
        accessToken: token,
        episodeId: episodeId,
        title: title,
      );
      final taskId = _str(created['id']);
      if (taskId.isNotEmpty) {
        await widget.apiClient
            .acceptLifeMapTask(accessToken: token, taskId: taskId);
      }
      _taskTitleController.clear();
      if (mounted) {
        setState(() => _taskFormOpen = false);
      }
      await _load();
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack('Không thể thêm việc. Vui lòng thử lại.');
    } finally {
      if (mounted) {
        setState(() => _creatingTask = false);
      }
    }
  }

  Future<void> _startCapture() async {
    final token = _token;
    final text = _captureController.text.trim();
    if (token == null || text.isEmpty || _capturing) return;
    setState(() => _capturing = true);
    try {
      final session = await widget.apiClient.startLifeMapTextCapture(
        accessToken: token,
        text: text,
      );
      if (!mounted) return;
      setState(() {
        _captureSession = session;
        if (session['persisted'] == true) _captureController.clear();
      });
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack('Không thể tạo bản nháp. Vui lòng thử lại.');
    } finally {
      if (mounted) setState(() => _capturing = false);
    }
  }

  Future<void> _askLifeMap() async {
    final token = _token;
    final query = _askController.text.trim();
    if (token == null || query.isEmpty || _asking) return;
    setState(() => _asking = true);
    try {
      final result = await widget.apiClient.askLifeMap(
        accessToken: token,
        query: query,
        episodeId: _selectedEpisodeId,
      );
      if (!mounted) return;
      setState(() => _askAnswer = result);
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack('Không thể tra cứu LifeMap. Vui lòng thử lại.');
    } finally {
      if (mounted) setState(() => _asking = false);
    }
  }

  Future<void> _confirmCapture(String candidateId) async {
    final token = _token;
    if (token == null || _capturing) return;
    setState(() => _capturing = true);
    try {
      await widget.apiClient.reviewLifeMapCaptureCandidate(
        accessToken: token,
        candidateId: candidateId,
        action: 'confirm',
        reason: 'Người dùng đã kiểm tra bản ghi',
      );
      if (!mounted) return;
      setState(() {
        final session = Map<String, dynamic>.from(_captureSession ?? const {});
        final candidates = session['candidates'];
        if (candidates is List) {
          session['candidates'] = candidates.map((candidate) {
            if (candidate is Map && _str(candidate['id']) == candidateId) {
              return <String, dynamic>{
                ...candidate.cast<String, dynamic>(),
                'status': 'confirmed',
              };
            }
            return candidate;
          }).toList();
        }
        session['status'] = 'completed';
        _captureSession = session;
      });
      await _load();
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack('Không thể xác nhận bản ghi. Vui lòng thử lại.');
    } finally {
      if (mounted) setState(() => _capturing = false);
    }
  }

  Future<void> _openReplay(_Episode episode) async {
    final token = _token;
    if (token == null) return;
    try {
      final replay = await widget.apiClient.getLifeMapReplay(
        accessToken: token,
        episodeId: episode.id,
      );
      if (!mounted) return;
      await showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        showDragHandle: true,
        builder: (sheetContext) => SafeArea(
          child: FractionallySizedBox(
            heightFactor: .85,
            child: _ReplaySheet(
              replay: replay,
              onCorrect: (event) async {
                Navigator.of(sheetContext).pop();
                final changed = await _correctReplayEvent(event);
                if (changed && mounted) await _openReplay(episode);
              },
            ),
          ),
        ),
      );
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack('Không thể tải lịch sử. Vui lòng thử lại khi có mạng.');
    }
  }

  Future<bool> _correctReplayEvent(Map<String, dynamic> event) async {
    final token = _token;
    if (token == null) return false;
    final controller = TextEditingController();
    final submitted = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Sửa thông tin'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Thao tác này cần kết nối mạng và tạo một phiên bản mới. '
              'Phiên bản cũ vẫn được giữ trong lịch sử.',
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            TextField(
              controller: controller,
              minLines: 2,
              maxLines: 5,
              autofocus: true,
              decoration: const InputDecoration(labelText: 'Thông tin đúng'),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: const Text('Hủy'),
          ),
          FilledButton(
            onPressed: () {
              final value = controller.text.trim();
              if (value.isNotEmpty) Navigator.of(dialogContext).pop(value);
            },
            child: const Text('Lưu phiên bản mới'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (submitted == null || submitted.isEmpty) return false;
    try {
      await widget.apiClient.correctLifeMapEvent(
        accessToken: token,
        eventId: _str(event['id']),
        revision: event['revision'] is int ? event['revision'] as int : 1,
        payload: <String, dynamic>{'text': submitted},
        reason: 'Người dùng sửa thông tin trong Replay',
      );
      _showSnack('Đã lưu phiên bản mới.');
      return true;
    } on ApiException catch (error) {
      _showSnack(error.message);
      return false;
    } catch (_) {
      _showSnack(
          'Không thể lưu. Thay đổi sức khỏe không được xếp hàng offline.');
      return false;
    }
  }

  Future<void> _askOneQuestion(_Episode episode) async {
    final token = _token;
    if (token == null) return;
    try {
      final question = await widget.apiClient.getLifeMapNextQuestion(
        accessToken: token,
        episodeId: episode.id,
      );
      if (question['ask'] != true || _str(question['question_id']).isEmpty) {
        _showSnack(
            'Hiện chưa có câu hỏi cần thiết. CLARA ưu tiên hỏi ít nhất có thể.');
        return;
      }
      final questionId = _str(question['question_id']);
      await widget.apiClient.recordLifeMapQuestionInteraction(
        accessToken: token,
        episodeId: episode.id,
        questionId: questionId,
        action: 'presented',
      );
      if (!mounted) return;
      final controller = TextEditingController();
      final answer = await showDialog<String>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: Text(_str(question['question'])),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Vì sao CLARA hỏi: ${_str(question['why'])}'),
              const SizedBox(height: ClaraTokens.spaceMd),
              TextField(
                controller: controller,
                minLines: 2,
                maxLines: 5,
                decoration: const InputDecoration(
                  labelText: 'Câu trả lời của bạn',
                  helperText: 'Sẽ tạo bản nháp để bạn kiểm tra trước.',
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () async {
                await widget.apiClient.recordLifeMapQuestionInteraction(
                  accessToken: token,
                  episodeId: episode.id,
                  questionId: questionId,
                  action: 'dismissed',
                  reason: 'Để sau',
                );
                if (dialogContext.mounted) Navigator.of(dialogContext).pop();
              },
              child: const Text('Để sau'),
            ),
            FilledButton(
              onPressed: () {
                final value = controller.text.trim();
                if (value.isNotEmpty) Navigator.of(dialogContext).pop(value);
              },
              child: const Text('Tạo bản nháp'),
            ),
          ],
        ),
      );
      controller.dispose();
      if (answer == null || answer.isEmpty) return;
      final session = await widget.apiClient.startLifeMapGuidedAnswer(
        accessToken: token,
        episodeId: episode.id,
        questionId: questionId,
        answer: <String, dynamic>{'value': answer},
      );
      if (!mounted) return;
      setState(() => _captureSession = session);
      _showSnack('Đã tạo bản nháp. Hãy kiểm tra rồi xác nhận.');
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack('Không thể tải câu hỏi. Vui lòng thử lại khi có mạng.');
    }
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
    if (_loading && _episodes.isEmpty && _tasks.isEmpty && !_needsOnboarding) {
      return ListView(
        children: const [
          SizedBox(height: ClaraTokens.spaceLg),
          ClaraSkeletonList(itemCount: 4),
        ],
      );
    }
    if (_needsOnboarding) {
      return _buildOnboardingPrompt(context);
    }
    if (_error != null) {
      return ListView(
        children: [
          const SizedBox(height: ClaraTokens.spaceXl),
          ErrorRetryView(message: _error!, onRetry: _load),
        ],
      );
    }
    return _buildLoaded(context);
  }

  Widget _buildOnboardingPrompt(BuildContext context) {
    final theme = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.all(ClaraTokens.spaceMd),
      children: [
        ClaraCard.static_(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                Icons.assignment_ind_outlined,
                size: 40,
                color: theme.colorScheme.primary,
              ),
              const SizedBox(height: ClaraTokens.spaceMd),
              Text(
                'Hãy tạo hồ sơ sức khỏe trước',
                style: theme.textTheme.titleMedium
                    ?.copyWith(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: ClaraTokens.spaceSm),
              Text(
                'Bạn cần tạo hồ sơ sức khỏe trước khi lập kế hoạch chăm sóc '
                'trong LifeMap. Đây là kế hoạch cá nhân, không phải chẩn đoán.',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildLoaded(BuildContext context) {
    final theme = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.only(
        top: ClaraTokens.spaceMd,
        bottom: ClaraTokens.spaceXl,
      ),
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
          child: Text(
            'Đây là kế hoạch cá nhân, không phải chẩn đoán.',
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
              fontStyle: FontStyle.italic,
            ),
          ),
        ),
        const SizedBox(height: ClaraTokens.spaceSm),

        if (_askEnabled) ...[
          const SectionHeader(title: 'Hỏi LifeMap của tôi'),
          Padding(
            padding: const EdgeInsets.fromLTRB(
              ClaraTokens.spaceMd,
              0,
              ClaraTokens.spaceMd,
              ClaraTokens.spaceMd,
            ),
            child: _buildAskCard(context),
          ),
          const SizedBox(height: ClaraTokens.spaceSm),
        ],

        if (_captureEnabled) ...[
          const SectionHeader(title: 'Ghi nhận nhanh'),
          Padding(
            padding: const EdgeInsets.fromLTRB(
              ClaraTokens.spaceMd,
              0,
              ClaraTokens.spaceMd,
              ClaraTokens.spaceMd,
            ),
            child: _buildCaptureCard(context),
          ),
          const SizedBox(height: ClaraTokens.spaceSm),
        ],

        if (_baselines.isNotEmpty) ...[
          const SectionHeader(title: 'Thay đổi so với chính bạn'),
          Padding(
            padding: const EdgeInsets.fromLTRB(
              ClaraTokens.spaceMd,
              0,
              ClaraTokens.spaceMd,
              ClaraTokens.spaceMd,
            ),
            child: ClaraCard.static_(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Không phải mức bình thường lâm sàng hay chẩn đoán.',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: ClaraTokens.spaceMd),
                  ..._baselines.map(
                    (item) => ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(_str(item['signal_key'])),
                      subtitle: Text(
                        '${_str(item['sample_days'])} ngày dữ liệu · '
                        '${_str(item['rule_version'])}',
                      ),
                      trailing: Text(
                        item['status'] == 'ready'
                            ? '${_str(item['personal_median'])} ${_str(item['unit'])}'
                            : 'Chưa đủ dữ liệu',
                        style: theme.textTheme.labelLarge,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],

        // --- Journeys (episodes) -------------------------------------------
        Row(
          children: [
            const Expanded(
              child: SectionHeader(title: 'Hành trình chăm sóc'),
            ),
            TextButton.icon(
              onPressed: () =>
                  setState(() => _episodeFormOpen = !_episodeFormOpen),
              icon: Icon(_episodeFormOpen ? Icons.close : Icons.add, size: 18),
              label: Text(_episodeFormOpen ? 'Đóng' : 'Tạo hành trình'),
            ),
          ],
        ),
        if (_episodeFormOpen)
          Padding(
            padding: const EdgeInsets.fromLTRB(
              ClaraTokens.spaceMd,
              0,
              ClaraTokens.spaceMd,
              ClaraTokens.spaceMd,
            ),
            child: _buildEpisodeForm(context),
          ),
        if (_episodes.isEmpty)
          const ClaraEmptyState(
            icon: Icons.route_outlined,
            title: 'Chưa có hành trình nào',
            message:
                'Tạo một hành trình chăm sóc để nhóm các việc bạn muốn theo '
                'dõi. Đây là kế hoạch cá nhân, không phải chẩn đoán.',
          )
        else
          ..._episodes.map(
            (episode) => Padding(
              padding: const EdgeInsets.fromLTRB(
                ClaraTokens.spaceMd,
                0,
                ClaraTokens.spaceMd,
                ClaraTokens.spaceMd,
              ),
              child: _buildEpisodeCard(context, episode),
            ),
          ),

        const SizedBox(height: ClaraTokens.spaceMd),

        // --- Tasks ----------------------------------------------------------
        Row(
          children: [
            const Expanded(
              child: SectionHeader(title: 'Việc đã chấp nhận'),
            ),
            TextButton.icon(
              onPressed: _episodes.isEmpty
                  ? null
                  : () => setState(() => _taskFormOpen = !_taskFormOpen),
              icon: Icon(_taskFormOpen ? Icons.close : Icons.add, size: 18),
              label: Text(_taskFormOpen ? 'Đóng' : 'Thêm việc'),
            ),
          ],
        ),
        if (_taskFormOpen && _episodes.isNotEmpty)
          Padding(
            padding: const EdgeInsets.fromLTRB(
              ClaraTokens.spaceMd,
              0,
              ClaraTokens.spaceMd,
              ClaraTokens.spaceMd,
            ),
            child: _buildTaskForm(context),
          ),
        if (_tasks.isEmpty)
          const ClaraEmptyState(
            icon: Icons.task_alt_outlined,
            title: 'Chưa có việc nào',
            message:
                'Thêm một việc dưới một hành trình. Sau khi chấp nhận, việc sẽ '
                'xuất hiện trong mục Hôm nay để bạn hoàn tất.',
          )
        else
          ..._tasks.map(
            (task) => Padding(
              padding: const EdgeInsets.fromLTRB(
                ClaraTokens.spaceMd,
                0,
                ClaraTokens.spaceMd,
                ClaraTokens.spaceMd,
              ),
              child: _buildTaskCard(context, task),
            ),
          ),
      ],
    );
  }

  Widget _buildCaptureCard(BuildContext context) {
    final theme = Theme.of(context);
    final session = _captureSession;
    if (session?['emergency'] == true) {
      return ClaraCard.static_(
        child: Semantics(
          liveRegion: true,
          child: Text(
            _str(session?['message']),
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.error,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      );
    }
    final rawCandidates = session?['candidates'];
    if (rawCandidates is List && rawCandidates.isNotEmpty) {
      final candidate = rawCandidates.first;
      if (candidate is Map) {
        final value = candidate['value'];
        final text = value is Map ? _str(value['text']) : '';
        final status = _str(candidate['status']);
        return ClaraCard.static_(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(text, style: theme.textTheme.bodyLarge),
              const SizedBox(height: ClaraTokens.spaceSm),
              Text(
                'Bản nháp do bạn kiểm tra; CLARA không tự xác nhận.',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              if (status == 'draft') ...[
                const SizedBox(height: ClaraTokens.spaceMd),
                ClaraButton.primary(
                  label: 'Tôi đã xem và xác nhận',
                  icon: Icons.verified_outlined,
                  loading: _capturing,
                  onPressed: () => _confirmCapture(_str(candidate['id'])),
                ),
              ] else ...[
                const SizedBox(height: ClaraTokens.spaceSm),
                Text(
                  'Đã xác nhận',
                  style: theme.textTheme.labelLarge?.copyWith(
                    color: theme.colorScheme.primary,
                  ),
                ),
              ],
            ],
          ),
        );
      }
    }
    return ClaraCard.static_(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Tạo bản nháp để xem lại trước khi đưa vào LifeMap.',
            style: theme.textTheme.bodyMedium,
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          TextField(
            controller: _captureController,
            minLines: 2,
            maxLines: 5,
            enabled: !_capturing,
            decoration: const InputDecoration(
              labelText: 'Điều bạn muốn ghi lại',
              hintText: 'Ví dụ: Tối qua tôi ngủ khoảng 7 giờ',
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          Align(
            alignment: Alignment.centerRight,
            child: ClaraButton.primary(
              label: 'Tạo bản nháp',
              icon: Icons.note_add_outlined,
              loading: _capturing,
              onPressed: _startCapture,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAskCard(BuildContext context) {
    final theme = Theme.of(context);
    final answer = _askAnswer;
    final rawClaims = answer?['claims'];
    final claims = rawClaims is List ? rawClaims : const <dynamic>[];
    final rawEvidence = answer?['evidence'];
    final evidence = rawEvidence is List ? rawEvidence : const <dynamic>[];
    return ClaraCard.static_(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Chỉ tra cứu dữ liệu bạn được phép xem. CLARA không chẩn đoán, '
            'kê đơn hay tự thay đổi LifeMap.',
            style: theme.textTheme.bodyMedium,
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          TextField(
            controller: _askController,
            minLines: 2,
            maxLines: 4,
            enabled: !_asking,
            decoration: const InputDecoration(
              labelText: 'Bạn muốn tìm điều gì?',
              hintText: 'Ví dụ: Các ghi nhận đau đầu gần đây?',
              helperText:
                  'Câu trả lời chỉ ra đúng bản ghi và phiên bản đã dùng.',
            ),
            onSubmitted: (_) => _askLifeMap(),
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          Align(
            alignment: Alignment.centerRight,
            child: ClaraButton.primary(
              label: 'Tra cứu',
              icon: Icons.search,
              loading: _asking,
              onPressed: _askLifeMap,
            ),
          ),
          if (answer != null) ...[
            const Divider(height: ClaraTokens.spaceXl),
            Semantics(
              liveRegion: true,
              child: Text(
                _str(answer['answer']),
                style: theme.textTheme.bodyLarge
                    ?.copyWith(fontWeight: FontWeight.w600),
              ),
            ),
            ...claims.map((claim) {
              if (claim is! Map) return const SizedBox.shrink();
              final citationIds = claim['citation_ids'];
              Map<dynamic, dynamic>? source;
              if (citationIds is List) {
                for (final candidate in evidence) {
                  if (candidate is Map &&
                      citationIds.contains(candidate['evidence_id'])) {
                    source = candidate;
                    break;
                  }
                }
              }
              return Padding(
                padding: const EdgeInsets.only(top: ClaraTokens.spaceMd),
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    color: theme.colorScheme.surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(ClaraTokens.spaceMd),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(_str(claim['text'])),
                        if (source != null) ...[
                          const SizedBox(height: ClaraTokens.spaceXs),
                          Text(
                            'Nguồn: ${_str(source['attribution'])} · '
                            'phiên bản ${_shortRevision(source['revision_id'])}',
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: theme.colorScheme.onSurfaceVariant,
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
              );
            }),
            const SizedBox(height: ClaraTokens.spaceMd),
            Text(
              'AI có dẫn nguồn · Chỉ đọc · Không phải tư vấn y tế.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildEpisodeForm(BuildContext context) {
    return ClaraCard.static_(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          TextField(
            controller: _episodeTitleController,
            textInputAction: TextInputAction.next,
            decoration: const InputDecoration(
              labelText: 'Tên hành trình',
              hintText: 'Ví dụ: Theo dõi huyết áp',
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          TextField(
            controller: _episodeGoalController,
            minLines: 2,
            maxLines: 4,
            decoration: const InputDecoration(
              labelText: 'Mục tiêu (không bắt buộc)',
              hintText: 'Điều bạn mong muốn đạt được',
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          DropdownButtonFormField<String>(
            initialValue: _episodePriority,
            decoration: const InputDecoration(labelText: 'Mức ưu tiên'),
            items: _kPriorityLabels.entries
                .map(
                  (entry) => DropdownMenuItem<String>(
                    value: entry.key,
                    child: Text(entry.value),
                  ),
                )
                .toList(),
            onChanged: _creatingEpisode
                ? null
                : (value) {
                    if (value != null) {
                      setState(() => _episodePriority = value);
                    }
                  },
          ),
          const SizedBox(height: ClaraTokens.spaceLg),
          Align(
            alignment: Alignment.centerRight,
            child: ClaraButton.primary(
              label: 'Tạo hành trình',
              icon: Icons.check,
              loading: _creatingEpisode,
              onPressed: _createEpisode,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTaskForm(BuildContext context) {
    return ClaraCard.static_(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          DropdownButtonFormField<String>(
            initialValue: _selectedEpisodeId,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'Thuộc hành trình'),
            items: _episodes
                .map(
                  (episode) => DropdownMenuItem<String>(
                    value: episode.id,
                    child: Text(
                      episode.title.isEmpty
                          ? 'Hành trình chưa đặt tên'
                          : episode.title,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                )
                .toList(),
            onChanged: _creatingTask
                ? null
                : (value) => setState(() => _selectedEpisodeId = value),
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          TextField(
            controller: _taskTitleController,
            textInputAction: TextInputAction.done,
            decoration: const InputDecoration(
              labelText: 'Tên việc',
              hintText: 'Ví dụ: Đo huyết áp buổi sáng',
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceLg),
          Align(
            alignment: Alignment.centerRight,
            child: ClaraButton.primary(
              label: 'Thêm việc',
              icon: Icons.check,
              loading: _creatingTask,
              onPressed: _createTask,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEpisodeCard(BuildContext context, _Episode episode) {
    final theme = Theme.of(context);
    return ClaraCard.static_(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Text(
                  episode.title.isEmpty
                      ? 'Hành trình chưa đặt tên'
                      : episode.title,
                  style: theme.textTheme.titleSmall
                      ?.copyWith(fontWeight: FontWeight.w600),
                ),
              ),
              const SizedBox(width: ClaraTokens.spaceSm),
              _PriorityChip(priority: episode.priority),
            ],
          ),
          const SizedBox(height: ClaraTokens.spaceSm),
          Align(
            alignment: Alignment.centerRight,
            child: Wrap(
              spacing: ClaraTokens.spaceSm,
              children: [
                if (_questionEnabled)
                  TextButton.icon(
                    onPressed: () => _askOneQuestion(episode),
                    icon: const Icon(Icons.help_outline, size: 18),
                    label: const Text('Một câu hỏi'),
                  ),
                TextButton.icon(
                  onPressed: () => _openReplay(episode),
                  icon: const Icon(Icons.history, size: 18),
                  label: const Text('Xem lịch sử'),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTaskCard(BuildContext context, _AcceptedTask task) {
    final theme = Theme.of(context);
    return ClaraCard.static_(
      child: Row(
        children: [
          Icon(
            Icons.check_circle_outline,
            size: 20,
            color: theme.colorScheme.primary,
          ),
          const SizedBox(width: ClaraTokens.spaceSm),
          Expanded(
            child: Text(
              task.title.isEmpty ? 'Việc chưa đặt tên' : task.title,
              style: theme.textTheme.bodyLarge,
            ),
          ),
        ],
      ),
    );
  }
}

class _ReplaySheet extends StatelessWidget {
  const _ReplaySheet({required this.replay, required this.onCorrect});

  final Map<String, dynamic> replay;
  final Future<void> Function(Map<String, dynamic>) onCorrect;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final episode = replay['episode'];
    final events = replay['events'] is List
        ? replay['events'] as List<dynamic>
        : const <dynamic>[];
    final decisions = replay['decisions'] is List
        ? replay['decisions'] as List<dynamic>
        : const <dynamic>[];
    final hasStale = decisions.any(
      (item) => item is Map && item['stale'] == true,
    );
    return ListView(
      padding: const EdgeInsets.fromLTRB(
        ClaraTokens.spaceMd,
        0,
        ClaraTokens.spaceMd,
        ClaraTokens.spaceXl,
      ),
      children: [
        Text(
          'Health Replay',
          style: theme.textTheme.labelLarge?.copyWith(
            color: theme.colorScheme.primary,
          ),
        ),
        const SizedBox(height: ClaraTokens.spaceXs),
        Text(
          episode is Map ? _str(episode['title']) : 'Lịch sử LifeMap',
          style: theme.textTheme.headlineSmall
              ?.copyWith(fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: ClaraTokens.spaceSm),
        Text(
          'Mỗi mục hiển thị đúng phiên bản và quy tắc đã dùng. '
          'Chỉnh sửa cần mạng và không được xếp hàng offline.',
          style: theme.textTheme.bodyMedium?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        if (hasStale) ...[
          const SizedBox(height: ClaraTokens.spaceMd),
          Semantics(
            liveRegion: true,
            child: ClaraCard.static_(
              child: Text(
                'Một số kết quả cũ đang được tính lại vì thông tin nguồn đã thay đổi.',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.error,
                ),
              ),
            ),
          ),
        ],
        const SizedBox(height: ClaraTokens.spaceLg),
        if (events.isEmpty)
          const ClaraEmptyState(
            icon: Icons.history,
            title: 'Chưa có bản ghi',
            message: 'Hành trình này chưa có thông tin để xem lại.',
          )
        else
          ...events.whereType<Map>().map((raw) {
            final event = raw.cast<String, dynamic>();
            final why = event['why'];
            return Padding(
              padding: const EdgeInsets.only(bottom: ClaraTokens.spaceMd),
              child: ClaraCard.static_(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Wrap(
                      spacing: ClaraTokens.spaceSm,
                      runSpacing: ClaraTokens.spaceXs,
                      children: [
                        Chip(label: Text(_str(event['truth_state']))),
                        Chip(
                          label: Text('Phiên bản ${_str(event['revision'])}'),
                        ),
                      ],
                    ),
                    const SizedBox(height: ClaraTokens.spaceSm),
                    Text(
                      _str(event['type']),
                      style: theme.textTheme.titleSmall
                          ?.copyWith(fontWeight: FontWeight.w600),
                    ),
                    if (why is Map) ...[
                      const SizedBox(height: ClaraTokens.spaceXs),
                      Text(
                        'Vì sao có mục này: ${_str(why['text'])}',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                    const SizedBox(height: ClaraTokens.spaceSm),
                    Align(
                      alignment: Alignment.centerRight,
                      child: TextButton.icon(
                        onPressed: () => onCorrect(event),
                        icon: const Icon(Icons.edit_outlined, size: 18),
                        label: const Text('Sửa thông tin'),
                      ),
                    ),
                  ],
                ),
              ),
            );
          }),
      ],
    );
  }
}

/// A colored chip conveying an episode's priority, paired with a text label so
/// meaning is never carried by color alone.
class _PriorityChip extends StatelessWidget {
  const _PriorityChip({required this.priority});

  final String priority;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final status = theme.extension<ClaraStatusColors>();

    final Color background;
    final Color foreground;
    switch (priority) {
      case 'urgent':
        background = scheme.error;
        foreground = scheme.onError;
        break;
      case 'soon':
        background = status?.warning ?? scheme.tertiary;
        foreground = status?.onWarning ?? scheme.onTertiary;
        break;
      case 'routine':
      default:
        background = scheme.primary;
        foreground = scheme.onPrimary;
        break;
    }

    final label = _kPriorityLabels[priority] ?? _kPriorityLabels['routine']!;

    return Container(
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(ClaraTokens.radiusSm),
      ),
      padding: const EdgeInsets.symmetric(
        horizontal: ClaraTokens.spaceSm,
        vertical: ClaraTokens.spaceXs,
      ),
      child: Text(
        label,
        style: theme.textTheme.labelSmall
            ?.copyWith(color: foreground, fontWeight: FontWeight.w600),
      ),
    );
  }
}
