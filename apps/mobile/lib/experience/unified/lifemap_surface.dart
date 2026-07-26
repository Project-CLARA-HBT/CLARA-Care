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
        priority: _str(json['priority']).isEmpty
            ? 'routine'
            : _str(json['priority']),
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
        // Keep the task-form selection valid against the freshly loaded set.
        if (_selectedEpisodeId != null &&
            !episodes.any((e) => e.id == _selectedEpisodeId)) {
          _selectedEpisodeId = null;
        }
        _selectedEpisodeId ??=
            episodes.isNotEmpty ? episodes.first.id : null;
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
      child: Row(
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
