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

import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../../core/api_client.dart';
import '../../core/consumer_terminology.dart';
import '../../core/session_store.dart';
import '../../theme/components/clara_button.dart';
import '../../theme/components/clara_card.dart';
import '../../theme/components/section_header.dart';
import '../../theme/tokens.dart';
import '../../theme/web_palette.dart';
import '../../widgets/error_retry_view.dart';
import '../language_controller.dart';
import '../states/empty_state.dart';
import '../states/skeleton.dart';

String _str(Object? value) => value == null ? '' : value.toString();
String _shortRevision(Object? value) {
  final text = _str(value);
  return text.length <= 8 ? text : text.substring(0, 8);
}

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
    @visibleForTesting ImagePicker? imagePicker,
    this.languageController,
  }) : _imagePicker = imagePicker;

  final ApiClient apiClient;
  final SessionStore sessionStore;
  final ImagePicker? _imagePicker;

  /// Optional app-level language state. Direct/legacy embedding keeps the
  /// Vietnamese-first terminology fallback.
  final LanguageController? languageController;

  @override
  State<LifeMapSurface> createState() => _LifeMapSurfaceState();
}

class _LifeMapSurfaceState extends State<LifeMapSurface> {
  late final ImagePicker _imagePicker = widget._imagePicker ?? ImagePicker();
  bool _loading = true;
  String? _error;
  bool _needsOnboarding = false;

  List<_Episode> _episodes = const [];
  List<_AcceptedTask> _tasks = const [];
  bool _captureEnabled = false;
  bool _questionEnabled = false;
  bool _askEnabled = false;
  bool _summaryEnabled = false;
  bool _reviewEnabled = false;
  List<Map<String, dynamic>> _baselines = const [];
  bool _capturing = false;
  Map<String, dynamic>? _captureSession;
  String _artifactKind = 'medication_label';
  String? _captureJobId;
  String? _captureJobStatus;
  Uint8List? _captureSourceBytes;
  String? _captureSourceName;
  final Map<String, Map<String, dynamic>?> _captureNormalizations =
      <String, Map<String, dynamic>?>{};
  final Set<String> _acceptedNormalizations = <String>{};
  final TextEditingController _captureController = TextEditingController();
  final TextEditingController _askController = TextEditingController();
  bool _asking = false;
  Map<String, dynamic>? _askAnswer;
  bool _summarizing = false;
  String _summaryLevel = 'day';
  Map<String, dynamic>? _lifeMapSummary;
  bool _reviewing = false;
  List<Map<String, dynamic>> _reviewFindings = const [];
  List<Map<String, dynamic>> _disputes = const [];

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
    _resumeCapture();
  }

  @override
  void dispose() {
    _episodeTitleController.dispose();
    _episodeGoalController.dispose();
    _taskTitleController.dispose();
    _captureController.dispose();
    _askController.dispose();
    _captureSourceBytes = null;
    _captureSourceName = null;
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

  Map<String, String> get _priorityLabels => <String, String>{
        'routine': _copy[ConsumerTerm.lifeMapPriorityRoutine],
        'soon': _copy[ConsumerTerm.lifeMapPrioritySoon],
        'urgent': _copy[ConsumerTerm.lifeMapPriorityUrgent],
      };

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
      final summaryEnabled =
          flags is Map && flags['lifemap_ai_summaries'] == true;
      final reviewEnabled =
          flags is Map && flags['lifemap_ai_review_findings'] == true;
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
      final disputes =
          await widget.apiClient.getLifeMapDisputes(accessToken: token);
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
        _summaryEnabled = summaryEnabled;
        _reviewEnabled = reviewEnabled;
        _baselines = baselines;
        _disputes = disputes;
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
      setState(() => _error = _copy[ConsumerTerm.lifeMapLoadFailed]);
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
      _showSnack(_copy[ConsumerTerm.lifeMapJourneyRequired]);
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
      _showSnack(_copy[ConsumerTerm.lifeMapCreateJourneyFailed]);
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
      _showSnack(_copy[ConsumerTerm.lifeMapJourneyRequiredForTask]);
      return;
    }
    final title = _taskTitleController.text.trim();
    if (title.isEmpty) {
      _showSnack(_copy[ConsumerTerm.lifeMapTaskNameRequired]);
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
      _showSnack(_copy[ConsumerTerm.lifeMapAddTaskFailed]);
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
      final sessionId = _str(session['id']);
      if (sessionId.isNotEmpty && session['persisted'] == true) {
        await widget.sessionStore.writeLifeMapCaptureSessionId(sessionId);
      }
      await _loadCaptureNormalizations(session);
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack(_copy[ConsumerTerm.lifeMapCaptureCreateFailed]);
    } finally {
      if (mounted) setState(() => _capturing = false);
    }
  }

  Future<void> _startArtifactCapture(ImageSource source) async {
    final token = _token;
    if (token == null || _capturing) return;
    final picked = await _imagePicker.pickImage(
      source: source,
      imageQuality: 90,
    );
    if (picked == null) return;
    final bytes = await picked.readAsBytes();
    if (bytes.isEmpty || bytes.length > 10 * 1024 * 1024) {
      _showSnack(_copy[ConsumerTerm.lifeMapCaptureImageInvalid]);
      return;
    }
    if (!mounted) return;
    setState(() {
      _capturing = true;
      _captureJobStatus = _copy[ConsumerTerm.lifeMapCaptureUploading];
      _captureSourceBytes = bytes;
      _captureSourceName = picked.name;
    });
    String? startedSessionId;
    try {
      final session = await widget.apiClient.startLifeMapArtifactCapture(
        accessToken: token,
        inputKind: _artifactKind,
      );
      final sessionId = _str(session['id']);
      if (sessionId.isEmpty) throw const FormatException();
      startedSessionId = sessionId;
      final uploaded = await widget.apiClient.uploadLifeMapCaptureArtifact(
        accessToken: token,
        sessionId: sessionId,
        bytes: bytes,
        filename: picked.name,
      );
      final rawJob = uploaded['job'];
      final job = rawJob is Map ? rawJob : const <String, dynamic>{};
      if (!mounted) return;
      setState(() {
        _captureSession = session;
        _captureJobId = _str(job['id']);
        _captureJobStatus = _copy[ConsumerTerm.lifeMapCaptureReading];
      });
      await widget.sessionStore.writeLifeMapCaptureSessionId(sessionId);
    } on ApiException catch (error) {
      if (startedSessionId != null) {
        try {
          await widget.apiClient.abandonLifeMapCaptureSession(
            accessToken: token,
            sessionId: startedSessionId,
          );
        } catch (_) {
          // The expiring server draft remains unconfirmed if cleanup is offline.
        }
      }
      if (mounted) {
        setState(() {
          _captureSourceBytes = null;
          _captureSourceName = null;
          _captureJobStatus = null;
        });
      }
      _showSnack(error.message);
    } catch (_) {
      if (startedSessionId != null) {
        try {
          await widget.apiClient.abandonLifeMapCaptureSession(
            accessToken: token,
            sessionId: startedSessionId,
          );
        } catch (_) {
          // The expiring server draft remains unconfirmed if cleanup is offline.
        }
      }
      if (mounted) {
        setState(() {
          _captureSourceBytes = null;
          _captureSourceName = null;
          _captureJobStatus = null;
        });
      }
      _showSnack(_copy[ConsumerTerm.lifeMapCaptureUploadFailed]);
    } finally {
      if (mounted) setState(() => _capturing = false);
    }
  }

  Future<void> _refreshArtifactCapture() async {
    final token = _token;
    final sessionId = _str(_captureSession?['id']);
    if (token == null || sessionId.isEmpty || _capturing) return;
    setState(() => _capturing = true);
    try {
      if (_captureJobId != null && _captureJobId!.isNotEmpty) {
        final job = await widget.apiClient.getLifeMapCaptureJob(
          accessToken: token,
          jobId: _captureJobId!,
        );
        final status = _str(job['status']);
        if (status == 'failed') {
          _showSnack(_copy[ConsumerTerm.lifeMapCaptureReadingFailed]);
          return;
        }
        if (status == 'escalated' || job['emergency'] == true) {
          if (mounted) {
            setState(() {
              _captureSession = <String, dynamic>{
                ...?_captureSession,
                'emergency': true,
                'message': _str(job['message']),
              };
              _captureJobStatus = null;
              _captureSourceBytes = null;
              _captureSourceName = null;
            });
          }
          return;
        }
        if (status != 'completed' && status != 'escalated') {
          if (mounted) {
            setState(() {
              _captureJobStatus = _copy[ConsumerTerm.lifeMapCaptureJobPending];
            });
          }
          return;
        }
      }
      final session = await widget.apiClient.getLifeMapCaptureSession(
        accessToken: token,
        sessionId: sessionId,
      );
      if (!mounted) return;
      setState(() {
        _captureSession = session;
        _captureJobStatus = null;
      });
      await _loadCaptureNormalizations(session);
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack(_copy[ConsumerTerm.lifeMapCaptureRefreshFailed]);
    } finally {
      if (mounted) setState(() => _capturing = false);
    }
  }

  Future<void> _resumeCapture() async {
    final token = _token;
    if (token == null) return;
    final sessionId = await widget.sessionStore.readLifeMapCaptureSessionId();
    if (sessionId == null || sessionId.isEmpty) return;
    try {
      final session = await widget.apiClient.getLifeMapCaptureSession(
        accessToken: token,
        sessionId: sessionId,
      );
      if (mounted) setState(() => _captureSession = session);
      await _loadCaptureNormalizations(session);
    } catch (_) {
      await widget.sessionStore.clearLifeMapCaptureSessionId();
    }
  }

  Future<void> _loadCaptureNormalizations(
    Map<String, dynamic> session,
  ) async {
    final token = _token;
    final candidates = session['candidates'];
    if (token == null || candidates is! List) return;
    for (final raw in candidates) {
      if (raw is! Map ||
          _str(raw['type']) != 'medication_label' ||
          _str(raw['status']) != 'draft') {
        continue;
      }
      final candidateId = _str(raw['id']);
      if (candidateId.isEmpty) continue;
      try {
        final proposal = await widget.apiClient.getLifeMapCaptureNormalization(
          accessToken: token,
          candidateId: candidateId,
        );
        if (!mounted) return;
        setState(() {
          _captureNormalizations[candidateId] = proposal;
          _acceptedNormalizations.remove(candidateId);
        });
      } catch (_) {
        if (!mounted) return;
        setState(() {
          _captureNormalizations[candidateId] = null;
          _acceptedNormalizations.remove(candidateId);
        });
      }
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
      _showSnack(_copy[ConsumerTerm.lifeMapAskLoadFailed]);
    } finally {
      if (mounted) setState(() => _asking = false);
    }
  }

  Future<void> _loadLifeMapSummary() async {
    final token = _token;
    if (token == null || _summarizing) return;
    setState(() => _summarizing = true);
    try {
      final result = await widget.apiClient.getLifeMapSummary(
        accessToken: token,
        level: _summaryLevel,
        episodeId: _summaryLevel == 'episode' ? _selectedEpisodeId : null,
      );
      if (!mounted) return;
      setState(() => _lifeMapSummary = result);
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack(_copy[ConsumerTerm.lifeMapSummaryLoadFailed]);
    } finally {
      if (mounted) setState(() => _summarizing = false);
    }
  }

  Future<void> _scanReviewFindings() async {
    final token = _token;
    if (token == null || _reviewing) return;
    setState(() => _reviewing = true);
    try {
      final response =
          await widget.apiClient.scanLifeMapReviewFindings(accessToken: token);
      final raw = response['data'];
      final findings = <Map<String, dynamic>>[];
      if (raw is List) {
        for (final item in raw) {
          if (item is Map) findings.add(item.cast<String, dynamic>());
        }
      }
      if (mounted) setState(() => _reviewFindings = findings);
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack(_copy[ConsumerTerm.lifeMapReviewLoadFailed]);
    } finally {
      if (mounted) setState(() => _reviewing = false);
    }
  }

  Future<void> _actOnFinding(
    Map<String, dynamic> finding,
    String action,
  ) async {
    final token = _token;
    if (token == null || _reviewing) return;
    setState(() => _reviewing = true);
    try {
      final updated = await widget.apiClient.actOnLifeMapReviewFinding(
        accessToken: token,
        findingId: _str(finding['id']),
        action: action,
        reason: action == 'resolved'
            ? 'Người dùng đã kiểm tra các bản ghi nguồn'
            : 'Người dùng xác nhận không cần xử lý',
      );
      if (!mounted) return;
      setState(() {
        _reviewFindings = _reviewFindings
            .map((item) => item['id'] == finding['id'] ? updated : item)
            .toList();
      });
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack('Không thể lưu lựa chọn. Vui lòng thử lại.');
    } finally {
      if (mounted) setState(() => _reviewing = false);
    }
  }

  Future<Map<String, dynamic>?> _editCaptureValue(
    Map<String, dynamic> value,
  ) async {
    final controllers = <String, TextEditingController>{
      for (final entry in value.entries)
        entry.key: TextEditingController(
          text: entry.value is Map || entry.value is List
              ? jsonEncode(entry.value)
              : _str(entry.value),
        ),
    };
    try {
      return await showDialog<Map<String, dynamic>>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: Text(_copy[ConsumerTerm.lifeMapCaptureEditTitle]),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: controllers.entries
                  .map(
                    (entry) => Padding(
                      padding: const EdgeInsets.only(
                        bottom: ClaraTokens.spaceMd,
                      ),
                      child: TextField(
                        controller: entry.value,
                        decoration: InputDecoration(
                          labelText: entry.key.replaceAll('_', ' '),
                        ),
                      ),
                    ),
                  )
                  .toList(),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(),
              child: Text(_copy[ConsumerTerm.medicinesCancel]),
            ),
            FilledButton(
              onPressed: () => Navigator.of(dialogContext).pop(
                <String, dynamic>{
                  for (final entry in controllers.entries)
                    entry.key: entry.value.text.trim(),
                },
              ),
              child: Text(_copy[ConsumerTerm.lifeMapCaptureEditSave]),
            ),
          ],
        ),
      );
    } finally {
      for (final controller in controllers.values) {
        controller.dispose();
      }
    }
  }

  Future<void> _reviewCapture(
    Map<String, dynamic> candidate,
    String action,
  ) async {
    final token = _token;
    if (token == null || _capturing) return;
    var value = candidate['value'];
    if (value is! Map) value = <String, dynamic>{};
    Map<String, dynamic>? reviewedValue = value.cast<String, dynamic>();
    if (action == 'edit') {
      reviewedValue = await _editCaptureValue(reviewedValue);
      if (reviewedValue == null) return;
    }
    setState(() => _capturing = true);
    try {
      final result = await widget.apiClient.reviewLifeMapCaptureCandidate(
        accessToken: token,
        candidateId: _str(candidate['id']),
        action: action,
        value: reviewedValue,
        acceptNormalization: action == 'confirm' &&
            _acceptedNormalizations.contains(
              _str(candidate['id']),
            ),
        reason: action == 'edit'
            ? 'Người dùng chỉnh sửa trường trích xuất'
            : action == 'reject'
                ? 'Người dùng từ chối bản nháp'
                : 'Người dùng đã kiểm tra bản ghi',
      );
      if (!mounted) return;
      setState(() {
        final session = Map<String, dynamic>.from(_captureSession ?? const {});
        final candidates = session['candidates'];
        if (candidates is List) {
          session['candidates'] = candidates.map((item) {
            if (item is Map && _str(item['id']) == _str(candidate['id'])) {
              final updated = result['candidate'];
              return updated is Map ? updated.cast<String, dynamic>() : item;
            }
            return item;
          }).toList();
        }
        if (action == 'confirm') session['status'] = 'completed';
        _captureSession = session;
      });
      await _loadCaptureNormalizations(
        Map<String, dynamic>.from(_captureSession ?? const {}),
      );
      if (action == 'confirm') {
        await widget.sessionStore.clearLifeMapCaptureSessionId();
        _captureSourceBytes = null;
        _captureSourceName = null;
        _captureJobId = null;
        _captureJobStatus = null;
        await _load();
      }
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack(_copy[ConsumerTerm.lifeMapCaptureConfirmFailed]);
    } finally {
      if (mounted) setState(() => _capturing = false);
    }
  }

  Future<void> _abandonCapture() async {
    final token = _token;
    final sessionId = _str(_captureSession?['id']);
    if (token == null || sessionId.isEmpty || _capturing) return;
    setState(() => _capturing = true);
    try {
      await widget.apiClient.abandonLifeMapCaptureSession(
        accessToken: token,
        sessionId: sessionId,
      );
      await widget.sessionStore.clearLifeMapCaptureSessionId();
      if (mounted) setState(() => _captureSession = null);
      _captureNormalizations.clear();
      _acceptedNormalizations.clear();
      _captureSourceBytes = null;
      _captureSourceName = null;
      _captureJobId = null;
      _captureJobStatus = null;
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack(_copy[ConsumerTerm.lifeMapCaptureAbandonOffline]);
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
              copy: _copy,
              onCorrect: (event) async {
                Navigator.of(sheetContext).pop();
                final changed = await _correctReplayEvent(event);
                if (changed && mounted) await _openReplay(episode);
              },
              onDispute: (event) async {
                Navigator.of(sheetContext).pop();
                final changed = await _disputeReplayEvent(event);
                if (changed && mounted) await _openReplay(episode);
              },
            ),
          ),
        ),
      );
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack(_copy[ConsumerTerm.lifeMapReplayLoadFailed]);
    }
  }

  Future<bool> _correctReplayEvent(Map<String, dynamic> event) async {
    final token = _token;
    if (token == null) return false;
    final controller = TextEditingController();
    final submitted = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(_copy[ConsumerTerm.lifeMapCorrectionTitle]),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(_copy[ConsumerTerm.lifeMapCorrectionNotice]),
            const SizedBox(height: ClaraTokens.spaceMd),
            TextField(
              controller: controller,
              minLines: 2,
              maxLines: 5,
              autofocus: true,
              decoration: InputDecoration(
                labelText: _copy[ConsumerTerm.lifeMapCorrectionLabel],
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: Text(_copy[ConsumerTerm.medicinesCancel]),
          ),
          FilledButton(
            onPressed: () {
              final value = controller.text.trim();
              if (value.isNotEmpty) Navigator.of(dialogContext).pop(value);
            },
            child: Text(_copy[ConsumerTerm.lifeMapCorrectionSave]),
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
      _showSnack(_copy[ConsumerTerm.lifeMapCorrectionSaved]);
      return true;
    } on ApiException catch (error) {
      _showSnack(error.message);
      return false;
    } catch (_) {
      _showSnack(_copy[ConsumerTerm.lifeMapMutationOffline]);
      return false;
    }
  }

  Future<bool> _disputeReplayEvent(Map<String, dynamic> event) async {
    final token = _token;
    if (token == null) return false;
    final controller = TextEditingController();
    final submitted = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(_copy[ConsumerTerm.lifeMapDisputeTitle]),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(_copy[ConsumerTerm.lifeMapDisputeNotice]),
            const SizedBox(height: ClaraTokens.spaceMd),
            TextField(
              controller: controller,
              minLines: 2,
              maxLines: 5,
              autofocus: true,
              decoration: InputDecoration(
                labelText: _copy[ConsumerTerm.lifeMapDisputeLabel],
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: Text(_copy[ConsumerTerm.medicinesCancel]),
          ),
          FilledButton(
            onPressed: () {
              final value = controller.text.trim();
              if (value.isNotEmpty) Navigator.of(dialogContext).pop(value);
            },
            child: Text(_copy[ConsumerTerm.lifeMapDisputeSubmit]),
          ),
        ],
      ),
    );
    controller.dispose();
    if (submitted == null || submitted.isEmpty) return false;
    try {
      await widget.apiClient.disputeLifeMapEvent(
        accessToken: token,
        eventId: _str(event['id']),
        revision: event['revision'] is int ? event['revision'] as int : 1,
        reason: submitted,
      );
      final disputes =
          await widget.apiClient.getLifeMapDisputes(accessToken: token);
      if (mounted) setState(() => _disputes = disputes);
      _showSnack(_copy[ConsumerTerm.lifeMapDisputeSubmitted]);
      return true;
    } on ApiException catch (error) {
      _showSnack(error.message);
      return false;
    } catch (_) {
      _showSnack(_copy[ConsumerTerm.lifeMapMutationOffline]);
      return false;
    }
  }

  Future<void> _resolveDispute(Map<String, dynamic> dispute) async {
    final token = _token;
    if (token == null) return;
    try {
      await widget.apiClient.resolveLifeMapEvent(
        accessToken: token,
        eventId: _str(dispute['event_id']),
        revision: dispute['revision'] is int ? dispute['revision'] as int : 1,
        reason: 'Đã kiểm tra lại nguồn và xác nhận phiên bản này',
      );
      final disputes =
          await widget.apiClient.getLifeMapDisputes(accessToken: token);
      if (mounted) setState(() => _disputes = disputes);
      _showSnack('Đã xử lý tranh chấp bằng một phiên bản mới.');
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack('Không thể xử lý khi ngoại tuyến.');
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
        _showSnack(_copy[ConsumerTerm.lifeMapQuestionNoneNeeded]);
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
              Text(
                _copy.format(
                  ConsumerTerm.lifeMapQuestionWhy,
                  <String, Object?>{'reason': _str(question['why'])},
                ),
              ),
              const SizedBox(height: ClaraTokens.spaceMd),
              TextField(
                controller: controller,
                minLines: 2,
                maxLines: 5,
                decoration: InputDecoration(
                  labelText: _copy[ConsumerTerm.lifeMapQuestionAnswerLabel],
                  helperText: _copy[ConsumerTerm.lifeMapQuestionAnswerHelp],
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
              child: Text(_copy[ConsumerTerm.lifeMapQuestionLater]),
            ),
            FilledButton(
              onPressed: () {
                final value = controller.text.trim();
                if (value.isNotEmpty) Navigator.of(dialogContext).pop(value);
              },
              child: Text(_copy[ConsumerTerm.lifeMapQuestionCreateDraft]),
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
      await _loadCaptureNormalizations(session);
      _showSnack(_copy[ConsumerTerm.lifeMapQuestionDraftCreated]);
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack(_copy[ConsumerTerm.lifeMapQuestionLoadFailed]);
    }
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
        builder: (context, _) => _buildRefreshableBody(context),
      );
    }
    return _buildRefreshableBody(context);
  }

  Widget _buildRefreshableBody(BuildContext context) {
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
                _copy[ConsumerTerm.lifeMapProfileRequiredTitle],
                style: theme.textTheme.titleMedium
                    ?.copyWith(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: ClaraTokens.spaceSm),
              Text(
                _copy[ConsumerTerm.lifeMapProfileRequiredDescription],
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
            _copy[ConsumerTerm.lifeMapPersonalPlanNotice],
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
              fontStyle: FontStyle.italic,
            ),
          ),
        ),
        const SizedBox(height: ClaraTokens.spaceSm),

        if (_askEnabled) ...[
          SectionHeader(title: _copy[ConsumerTerm.lifeMapAskSectionTitle]),
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

        if (_summaryEnabled) ...[
          SectionHeader(title: _copy[ConsumerTerm.lifeMapSummarySectionTitle]),
          Padding(
            padding: const EdgeInsets.fromLTRB(
              ClaraTokens.spaceMd,
              0,
              ClaraTokens.spaceMd,
              ClaraTokens.spaceMd,
            ),
            child: _buildSummaryCard(context),
          ),
          const SizedBox(height: ClaraTokens.spaceSm),
        ],

        if (_reviewEnabled) ...[
          SectionHeader(title: _copy[ConsumerTerm.lifeMapReviewSectionTitle]),
          Padding(
            padding: const EdgeInsets.fromLTRB(
              ClaraTokens.spaceMd,
              0,
              ClaraTokens.spaceMd,
              ClaraTokens.spaceMd,
            ),
            child: _buildReviewCard(context),
          ),
          const SizedBox(height: ClaraTokens.spaceSm),
        ],

        if (_disputes.isNotEmpty) ...[
          SectionHeader(
            title: _copy[ConsumerTerm.lifeMapDisputeQueueTitle],
          ),
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
                    _copy[ConsumerTerm.lifeMapDisputeQueueNotice],
                    style: theme.textTheme.bodyMedium,
                  ),
                  ..._disputes.map((item) {
                    final open = _str(item['status']) == 'open';
                    final clinical = item['requires_clinical_review'] == true;
                    final statusTerm = open
                        ? ConsumerTerm.lifeMapDisputeQueueOpen
                        : ConsumerTerm.lifeMapDisputeQueueResolved;
                    return Padding(
                      padding: const EdgeInsets.only(top: ClaraTokens.spaceMd),
                      child: DecoratedBox(
                        decoration: BoxDecoration(
                          border: Border.all(
                              color: theme.colorScheme.outlineVariant),
                          borderRadius:
                              BorderRadius.circular(ClaraTokens.radiusMd),
                        ),
                        child: Padding(
                          padding: const EdgeInsets.all(ClaraTokens.spaceMd),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                _copy.format(
                                  ConsumerTerm.lifeMapDisputeQueueVersion,
                                  <String, Object?>{
                                    'eventType': _str(item['event_type']),
                                    'revision': _str(item['revision']),
                                  },
                                ),
                                style: theme.textTheme.titleSmall?.copyWith(
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                              const SizedBox(height: ClaraTokens.spaceXs),
                              Text(_copy[statusTerm]),
                              if (open && clinical) ...[
                                const SizedBox(height: ClaraTokens.spaceSm),
                                Text(
                                  _copy[ConsumerTerm
                                      .lifeMapDisputeQueueClinicalReview],
                                  style: theme.textTheme.bodySmall?.copyWith(
                                    color: theme.colorScheme.error,
                                  ),
                                ),
                              ],
                              if (open && !clinical) ...[
                                const SizedBox(height: ClaraTokens.spaceSm),
                                ClaraButton.secondary(
                                  label: _copy[
                                      ConsumerTerm.lifeMapDisputeQueueResolve],
                                  icon: Icons.verified_outlined,
                                  onPressed: () => _resolveDispute(item),
                                ),
                              ],
                            ],
                          ),
                        ),
                      ),
                    );
                  }),
                ],
              ),
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceSm),
        ],

        if (_captureEnabled) ...[
          SectionHeader(title: _copy[ConsumerTerm.lifeMapCaptureSectionTitle]),
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
          SectionHeader(title: _copy[ConsumerTerm.lifeMapBaselineSectionTitle]),
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
                    _copy[ConsumerTerm.lifeMapBaselineNotice],
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
                        _copy.format(
                          ConsumerTerm.lifeMapBaselineSamples,
                          <String, Object?>{
                            'days': _str(item['sample_days']),
                            'version': _str(item['rule_version']),
                          },
                        ),
                      ),
                      trailing: Text(
                        item['status'] == 'ready'
                            ? '${_str(item['personal_median'])} ${_str(item['unit'])}'
                            : _copy[
                                ConsumerTerm.lifeMapBaselineInsufficientData],
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
            Expanded(
              child: SectionHeader(
                title: _copy[ConsumerTerm.lifeMapCareJourneys],
              ),
            ),
            TextButton.icon(
              onPressed: () =>
                  setState(() => _episodeFormOpen = !_episodeFormOpen),
              icon: Icon(_episodeFormOpen ? Icons.close : Icons.add, size: 18),
              label: Text(
                _episodeFormOpen
                    ? _copy[ConsumerTerm.lifeMapCloseForm]
                    : _copy[ConsumerTerm.lifeMapCreateJourney],
              ),
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
          ClaraEmptyState(
            icon: Icons.route_outlined,
            title: _copy[ConsumerTerm.lifeMapEmptyJourneysTitle],
            message: _copy[ConsumerTerm.lifeMapEmptyJourneysDescription],
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
            Expanded(
              child: SectionHeader(
                title: _copy[ConsumerTerm.lifeMapAcceptedTasks],
              ),
            ),
            TextButton.icon(
              onPressed: _episodes.isEmpty
                  ? null
                  : () => setState(() => _taskFormOpen = !_taskFormOpen),
              icon: Icon(_taskFormOpen ? Icons.close : Icons.add, size: 18),
              label: Text(
                _taskFormOpen
                    ? _copy[ConsumerTerm.lifeMapCloseForm]
                    : _copy[ConsumerTerm.lifeMapAddTask],
              ),
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
          ClaraEmptyState(
            icon: Icons.task_alt_outlined,
            title: _copy[ConsumerTerm.lifeMapEmptyTasksTitle],
            message: _copy[ConsumerTerm.lifeMapEmptyTasksDescription],
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
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Semantics(
              liveRegion: true,
              child: Text(
                _str(session?['message']).isNotEmpty
                    ? _str(session?['message'])
                    : _copy[ConsumerTerm.lifeMapCaptureEmergencyFallback],
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.error,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            if (_str(session?['id']).isNotEmpty) ...[
              const SizedBox(height: ClaraTokens.spaceMd),
              TextButton.icon(
                onPressed: _capturing ? null : _abandonCapture,
                icon: const Icon(Icons.delete_outline),
                label: Text(
                  _copy[ConsumerTerm.lifeMapCaptureDeleteSourceDraft],
                ),
              ),
            ],
          ],
        ),
      );
    }
    final rawCandidates = session?['candidates'];
    if (rawCandidates is List && rawCandidates.isNotEmpty) {
      final candidate = rawCandidates.first;
      if (candidate is Map) {
        final value = candidate['value'];
        final fields = value is Map
            ? value.entries.toList()
            : const <MapEntry<dynamic, dynamic>>[];
        final status = _str(candidate['status']);
        final rawMissing = candidate['missing_critical_fields'];
        final missing = rawMissing is List
            ? rawMissing.map(_str).where((v) => v.isNotEmpty).toList()
            : <String>[];
        final rawFindings = candidate['security_findings'];
        final findings = rawFindings is List
            ? rawFindings.map(_str).where((v) => v.isNotEmpty).toList()
            : <String>[];
        final rawConfidence = candidate['field_confidence'];
        final lowConfidence = rawConfidence is Map &&
            rawConfidence.values.any(
              (score) => score is num && score.toDouble() < 0.8,
            );
        final candidateId = _str(candidate['id']);
        final isMedication = _str(candidate['type']) == 'medication_label';
        final hasNormalization =
            _captureNormalizations.containsKey(candidateId);
        final normalization = _captureNormalizations[candidateId];
        final proposal = normalization?['proposal'];
        final proposalMap =
            proposal is Map ? proposal.cast<String, dynamic>() : null;
        return ClaraCard.static_(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Semantics(
                liveRegion: true,
                child: Text(
                  status == 'draft'
                      ? _copy[ConsumerTerm.lifeMapCaptureDraft]
                      : status == 'rejected'
                          ? _copy[ConsumerTerm.lifeMapCaptureRejected]
                          : _copy[ConsumerTerm.lifeMapCaptureConfirmed],
                  style: theme.textTheme.titleSmall,
                ),
              ),
              const SizedBox(height: ClaraTokens.spaceSm),
              _buildCaptureSourcePreview(context),
              if (_captureSourceBytes != null)
                const SizedBox(height: ClaraTokens.spaceSm),
              ...fields.map(
                (entry) => Padding(
                  padding: const EdgeInsets.only(bottom: ClaraTokens.spaceXs),
                  child: Text(
                    '${entry.key.toString().replaceAll('_', ' ')}: '
                    '${entry.value is Map || entry.value is List ? jsonEncode(entry.value) : _str(entry.value)}',
                    style: theme.textTheme.bodyLarge,
                  ),
                ),
              ),
              const SizedBox(height: ClaraTokens.spaceSm),
              Text(
                _copy[ConsumerTerm.lifeMapCaptureOnlineNotice],
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              if (lowConfidence) ...[
                const SizedBox(height: ClaraTokens.spaceSm),
                Text(
                  _copy[ConsumerTerm.lifeMapCaptureLowConfidence],
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.tertiary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
              if (missing.isNotEmpty) ...[
                const SizedBox(height: ClaraTokens.spaceSm),
                Text(
                  _copy.format(
                    ConsumerTerm.lifeMapCaptureMissingFields,
                    <String, Object?>{'fields': missing.join(', ')},
                  ),
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.error,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
              if (findings.isNotEmpty) ...[
                const SizedBox(height: ClaraTokens.spaceSm),
                Text(
                  _copy[ConsumerTerm.lifeMapCaptureUnsafe],
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.error,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
              if (isMedication && status == 'draft') ...[
                const SizedBox(height: ClaraTokens.spaceMd),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(ClaraTokens.spaceSm),
                  decoration: BoxDecoration(
                    color: theme.colorScheme.surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _copy[ConsumerTerm.lifeMapCaptureNormalizeTitle],
                        style: theme.textTheme.titleSmall,
                      ),
                      const SizedBox(height: ClaraTokens.spaceXs),
                      if (!hasNormalization)
                        Text(
                          _copy[ConsumerTerm.lifeMapCaptureNormalizeLoading],
                          style: theme.textTheme.bodySmall,
                        )
                      else if (proposalMap == null)
                        Text(
                          _copy[
                              ConsumerTerm.lifeMapCaptureNormalizeUnavailable],
                          style: theme.textTheme.bodySmall,
                        )
                      else ...[
                        Text(
                          _copy.format(
                            ConsumerTerm.lifeMapCaptureNormalizeProposal,
                            <String, Object?>{
                              'name': _str(proposalMap['display_name']),
                              'code': _str(proposalMap['code']),
                            },
                          ),
                          style: theme.textTheme.bodyMedium,
                        ),
                        CheckboxListTile(
                          contentPadding: EdgeInsets.zero,
                          controlAffinity: ListTileControlAffinity.leading,
                          value: _acceptedNormalizations.contains(candidateId),
                          onChanged: (checked) => setState(() {
                            if (checked == true) {
                              _acceptedNormalizations.add(candidateId);
                            } else {
                              _acceptedNormalizations.remove(candidateId);
                            }
                          }),
                          title: Text(
                            _copy[ConsumerTerm.lifeMapCaptureNormalizeUseCode],
                          ),
                          subtitle: Text(
                            _copy[ConsumerTerm
                                .lifeMapCaptureNormalizeUseCodeNotice],
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
              if (status == 'draft') ...[
                const SizedBox(height: ClaraTokens.spaceMd),
                Wrap(
                  spacing: ClaraTokens.spaceSm,
                  runSpacing: ClaraTokens.spaceSm,
                  children: [
                    OutlinedButton.icon(
                      onPressed: _capturing
                          ? null
                          : () => _reviewCapture(
                                candidate.cast<String, dynamic>(),
                                'edit',
                              ),
                      icon: const Icon(Icons.edit_outlined),
                      label: Text(_copy[ConsumerTerm.lifeMapCaptureEdit]),
                    ),
                    OutlinedButton.icon(
                      onPressed: _capturing
                          ? null
                          : () => _reviewCapture(
                                candidate.cast<String, dynamic>(),
                                'reject',
                              ),
                      icon: const Icon(Icons.delete_outline),
                      label: Text(_copy[ConsumerTerm.lifeMapCaptureReject]),
                    ),
                    FilledButton.icon(
                      onPressed: _capturing ||
                              missing.isNotEmpty ||
                              findings.isNotEmpty
                          ? null
                          : () => _reviewCapture(
                                candidate.cast<String, dynamic>(),
                                'confirm',
                              ),
                      icon: const Icon(Icons.verified_outlined),
                      label: Text(_copy[ConsumerTerm.lifeMapCaptureConfirm]),
                    ),
                  ],
                ),
              ],
              if (status != 'confirmed') ...[
                const SizedBox(height: ClaraTokens.spaceSm),
                TextButton.icon(
                  onPressed: _capturing ? null : _abandonCapture,
                  icon: const Icon(Icons.close),
                  label: Text(_copy[ConsumerTerm.lifeMapCaptureAbandon]),
                ),
              ],
            ],
          ),
        );
      }
    }
    if (_str(session?['id']).isNotEmpty) {
      return ClaraCard.static_(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              _copy[ConsumerTerm.lifeMapCaptureProcessing],
              style: theme.textTheme.titleSmall,
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            _buildCaptureSourcePreview(context),
            if (_captureJobStatus != null) ...[
              const SizedBox(height: ClaraTokens.spaceSm),
              Semantics(
                liveRegion: true,
                child: Text(
                  _captureJobStatus!,
                  style: theme.textTheme.bodyMedium,
                ),
              ),
            ],
            const SizedBox(height: ClaraTokens.spaceMd),
            Wrap(
              spacing: ClaraTokens.spaceSm,
              runSpacing: ClaraTokens.spaceSm,
              children: [
                OutlinedButton.icon(
                  onPressed: _capturing ? null : _refreshArtifactCapture,
                  icon: const Icon(Icons.refresh),
                  label: Text(_copy[ConsumerTerm.lifeMapCaptureCheckResult]),
                ),
                TextButton.icon(
                  onPressed: _capturing ? null : _abandonCapture,
                  icon: const Icon(Icons.close),
                  label: Text(_copy[ConsumerTerm.lifeMapCaptureAbandon]),
                ),
              ],
            ),
          ],
        ),
      );
    }
    return ClaraCard.static_(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            _copy[ConsumerTerm.lifeMapCaptureCreateDescription],
            style: theme.textTheme.bodyMedium,
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          TextField(
            controller: _captureController,
            minLines: 2,
            maxLines: 5,
            enabled: !_capturing,
            decoration: InputDecoration(
              labelText: _copy[ConsumerTerm.lifeMapCaptureInputLabel],
              hintText: _copy[ConsumerTerm.lifeMapCaptureInputHint],
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          Align(
            alignment: Alignment.centerRight,
            child: ClaraButton.primary(
              label: _copy[ConsumerTerm.lifeMapCaptureCreate],
              icon: Icons.note_add_outlined,
              loading: _capturing,
              onPressed: _startCapture,
            ),
          ),
          const Divider(height: ClaraTokens.spaceXl),
          Text(
            _copy[ConsumerTerm.lifeMapCaptureArtifactTitle],
            style: theme.textTheme.titleSmall,
          ),
          const SizedBox(height: ClaraTokens.spaceXs),
          Text(
            _copy[ConsumerTerm.lifeMapCaptureArtifactDescription],
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          DropdownButtonFormField<String>(
            key: ValueKey<String>(_artifactKind),
            initialValue: _artifactKind,
            isExpanded: true,
            decoration: InputDecoration(
              labelText: _copy[ConsumerTerm.lifeMapCaptureSourceType],
            ),
            items: [
              DropdownMenuItem(
                value: 'medication_label',
                child: Text(_copy[ConsumerTerm.lifeMapCaptureMedicationLabel]),
              ),
              DropdownMenuItem(
                value: 'visit_document',
                child: Text(_copy[ConsumerTerm.lifeMapCaptureVisitDocument]),
              ),
            ],
            onChanged: _capturing
                ? null
                : (value) {
                    if (value != null) {
                      setState(() => _artifactKind = value);
                    }
                  },
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          Wrap(
            spacing: ClaraTokens.spaceSm,
            runSpacing: ClaraTokens.spaceSm,
            children: [
              OutlinedButton.icon(
                onPressed: _capturing
                    ? null
                    : () => _startArtifactCapture(ImageSource.camera),
                icon: const Icon(Icons.photo_camera_outlined),
                label: Text(_copy[ConsumerTerm.lifeMapCaptureTakePhoto]),
              ),
              OutlinedButton.icon(
                onPressed: _capturing
                    ? null
                    : () => _startArtifactCapture(ImageSource.gallery),
                icon: const Icon(Icons.photo_library_outlined),
                label: Text(_copy[ConsumerTerm.lifeMapCaptureChoosePhoto]),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildCaptureSourcePreview(BuildContext context) {
    final theme = Theme.of(context);
    final bytes = _captureSourceBytes;
    final rawArtifacts = _captureSession?['artifacts'];
    final artifacts = rawArtifacts is List ? rawArtifacts : const <dynamic>[];
    if (bytes != null) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Semantics(
            label: _copy.format(
              ConsumerTerm.lifeMapCaptureSourceImageLabel,
              <String, Object?>{'name': _captureSourceName ?? ''},
            ),
            image: true,
            child: ClipRRect(
              borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxHeight: 240),
                child: Image.memory(
                  bytes,
                  width: double.infinity,
                  fit: BoxFit.contain,
                  errorBuilder: (context, error, stackTrace) => Text(
                    _copy[ConsumerTerm.lifeMapCaptureSourcePreviewError],
                    style: theme.textTheme.bodySmall,
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceXs),
          Text(
            _copy.format(
              ConsumerTerm.lifeMapCaptureSourcePreview,
              <String, Object?>{
                'name': _captureSourceName ??
                    _copy[ConsumerTerm.lifeMapCaptureChoosePhoto],
              },
            ),
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      );
    }
    if (artifacts.isNotEmpty) {
      final artifact = artifacts.first;
      if (artifact is Map) {
        return DecoratedBox(
          decoration: BoxDecoration(
            color: theme.colorScheme.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
          ),
          child: Padding(
            padding: const EdgeInsets.all(ClaraTokens.spaceSm),
            child: Text(
              '${_copy.format(
                ConsumerTerm.lifeMapCaptureSourcePreview,
                <String, Object?>{'name': _str(artifact['filename'])},
              )}\n${_copy[ConsumerTerm.lifeMapCaptureSourceUncached]}',
              style: theme.textTheme.bodySmall,
            ),
          ),
        );
      }
    }
    return Text(
      _copy[ConsumerTerm.lifeMapCaptureSourceUncached],
      style: theme.textTheme.bodySmall?.copyWith(
        color: theme.colorScheme.onSurfaceVariant,
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
            _copy[ConsumerTerm.lifeMapAskSafetyNotice],
            style: theme.textTheme.bodyMedium,
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          TextField(
            controller: _askController,
            minLines: 2,
            maxLines: 4,
            enabled: !_asking,
            decoration: InputDecoration(
              labelText: _copy[ConsumerTerm.lifeMapAskInputLabel],
              hintText: _copy[ConsumerTerm.lifeMapAskInputHint],
              helperText: _copy[ConsumerTerm.lifeMapAskInputHelp],
            ),
            onSubmitted: (_) => _askLifeMap(),
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          Align(
            alignment: Alignment.centerRight,
            child: ClaraButton.primary(
              label: _copy[ConsumerTerm.lifeMapAskSubmit],
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
                            _copy.format(
                              ConsumerTerm.lifeMapAskCitation,
                              <String, Object?>{
                                'source': _str(source['attribution']),
                                'revision': _shortRevision(
                                  source['revision_id'],
                                ),
                              },
                            ),
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
              _copy[ConsumerTerm.lifeMapAskAnswerSafetyNotice],
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildSummaryCard(BuildContext context) {
    final theme = Theme.of(context);
    final summary = _lifeMapSummary;
    final rawChildren = summary?['children'];
    final children = rawChildren is List ? rawChildren : const <dynamic>[];
    return ClaraCard.static_(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            _copy[ConsumerTerm.lifeMapSummaryDescription],
            style: theme.textTheme.bodyMedium,
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          DropdownButtonFormField<String>(
            key: ValueKey<String>(_summaryLevel),
            initialValue: _summaryLevel,
            isExpanded: true,
            decoration: InputDecoration(
              labelText: _copy[ConsumerTerm.lifeMapSummaryScope],
            ),
            items: <DropdownMenuItem<String>>[
              DropdownMenuItem(
                value: 'day',
                child: Text(_copy[ConsumerTerm.lifeMapSummaryDay]),
              ),
              DropdownMenuItem(
                value: 'week',
                child: Text(_copy[ConsumerTerm.lifeMapSummaryWeek]),
              ),
              DropdownMenuItem(
                value: 'episode',
                enabled: _selectedEpisodeId != null,
                child: Text(
                  _copy[ConsumerTerm.lifeMapSummarySelectedJourney],
                ),
              ),
            ],
            onChanged: _summarizing
                ? null
                : (value) {
                    if (value == null) return;
                    setState(() {
                      _summaryLevel = value;
                      _lifeMapSummary = null;
                    });
                  },
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          Align(
            alignment: Alignment.centerRight,
            child: ClaraButton.secondary(
              label: _copy[ConsumerTerm.lifeMapSummaryCreate],
              icon: Icons.summarize_outlined,
              loading: _summarizing,
              onPressed: _loadLifeMapSummary,
            ),
          ),
          if (summary != null) ...[
            const Divider(height: ClaraTokens.spaceXl),
            Semantics(
              liveRegion: true,
              child: Text(
                _str(summary['summary']),
                style: theme.textTheme.bodyLarge
                    ?.copyWith(fontWeight: FontWeight.w600),
              ),
            ),
            if (children.isEmpty)
              Padding(
                padding: const EdgeInsets.only(top: ClaraTokens.spaceSm),
                child: Text(
                  _copy[ConsumerTerm.lifeMapSummaryEmpty],
                  style: theme.textTheme.bodyMedium,
                ),
              ),
            ...children.map((rawGroup) {
              if (rawGroup is! Map) return const SizedBox.shrink();
              final rawClaims = rawGroup['claims'];
              final claims = rawClaims is List ? rawClaims : const <dynamic>[];
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
                        Text(
                          _str(rawGroup['group']),
                          style: theme.textTheme.labelLarge,
                        ),
                        ...claims.map((rawClaim) {
                          if (rawClaim is! Map) {
                            return const SizedBox.shrink();
                          }
                          final citationIds = rawClaim['citation_ids'];
                          final citations = citationIds is List
                              ? citationIds.map(_str).join(', ')
                              : '';
                          final truthState = _str(rawClaim['truth_state']);
                          return Padding(
                            padding: const EdgeInsets.only(
                              top: ClaraTokens.spaceSm,
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(_str(rawClaim['text'])),
                                Text(
                                  '${_str(rawClaim['attribution'])} · '
                                  '${_str(rawClaim['occurred_at'])} · '
                                  '${_copy.format(
                                    ConsumerTerm.lifeMapSummaryCitation,
                                    <String, Object?>{'citations': citations},
                                  )}',
                                  style: theme.textTheme.bodySmall?.copyWith(
                                    color: theme.colorScheme.onSurfaceVariant,
                                  ),
                                ),
                                if (truthState != 'confirmed')
                                  Text(
                                    truthState,
                                    style: theme.textTheme.labelSmall?.copyWith(
                                      color: theme.colorScheme.tertiary,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                              ],
                            ),
                          );
                        }),
                      ],
                    ),
                  ),
                ),
              );
            }),
            const SizedBox(height: ClaraTokens.spaceMd),
            Text(
              _copy[ConsumerTerm.lifeMapSummarySafetyNotice],
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildReviewCard(BuildContext context) {
    final theme = Theme.of(context);
    return ClaraCard.static_(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            _copy[ConsumerTerm.lifeMapReviewDescription],
            style: theme.textTheme.bodyMedium,
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          ClaraButton.secondary(
            label: _copy[ConsumerTerm.lifeMapReviewCheck],
            icon: Icons.fact_check_outlined,
            loading: _reviewing,
            onPressed: _scanReviewFindings,
          ),
          ..._reviewFindings.map((finding) {
            final status = _str(finding['status']);
            final kind = _str(finding['kind']);
            final label = kind == 'contradiction'
                ? _copy[ConsumerTerm.lifeMapReviewPossibleContradiction]
                : kind == 'duplicate'
                    ? _copy[ConsumerTerm.lifeMapReviewPossibleDuplicate]
                    : _copy[ConsumerTerm.lifeMapReviewNeedsMoreInformation];
            return Padding(
              padding: const EdgeInsets.only(top: ClaraTokens.spaceMd),
              child: DecoratedBox(
                decoration: BoxDecoration(
                  border: Border.all(color: theme.colorScheme.outlineVariant),
                  borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(ClaraTokens.spaceMd),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        label,
                        style: theme.textTheme.titleSmall
                            ?.copyWith(fontWeight: FontWeight.w600),
                      ),
                      const SizedBox(height: ClaraTokens.spaceXs),
                      Text(
                        _copy[ConsumerTerm.lifeMapReviewBasedOnSavedRecords],
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                      if (status == 'pending') ...[
                        const SizedBox(height: ClaraTokens.spaceMd),
                        Wrap(
                          spacing: ClaraTokens.spaceSm,
                          runSpacing: ClaraTokens.spaceSm,
                          children: [
                            ClaraButton.primary(
                              label: _copy[ConsumerTerm.lifeMapReviewResolved],
                              onPressed: () =>
                                  _actOnFinding(finding, 'resolved'),
                            ),
                            ClaraButton.secondary(
                              label: _copy[ConsumerTerm.lifeMapReviewDismiss],
                              onPressed: () =>
                                  _actOnFinding(finding, 'dismissed'),
                            ),
                          ],
                        ),
                      ] else
                        Text(
                          _copy[ConsumerTerm.lifeMapReviewRecorded],
                          style: theme.textTheme.bodySmall,
                        ),
                    ],
                  ),
                ),
              ),
            );
          }),
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
            decoration: InputDecoration(
              labelText: _copy[ConsumerTerm.lifeMapJourneyName],
              hintText: _copy[ConsumerTerm.lifeMapJourneyNameHint],
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          TextField(
            controller: _episodeGoalController,
            minLines: 2,
            maxLines: 4,
            decoration: InputDecoration(
              labelText: _copy[ConsumerTerm.lifeMapGoal],
              hintText: _copy[ConsumerTerm.lifeMapGoalHint],
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          DropdownButtonFormField<String>(
            initialValue: _episodePriority,
            decoration: InputDecoration(
              labelText: _copy[ConsumerTerm.lifeMapPriority],
            ),
            items: _priorityLabels.entries
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
              label: _copy[ConsumerTerm.lifeMapCreateJourney],
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
            decoration: InputDecoration(
              labelText: _copy[ConsumerTerm.lifeMapTaskJourney],
            ),
            items: _episodes
                .map(
                  (episode) => DropdownMenuItem<String>(
                    value: episode.id,
                    child: Text(
                      episode.title.isEmpty
                          ? _copy[ConsumerTerm.lifeMapUnnamedJourney]
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
            decoration: InputDecoration(
              labelText: _copy[ConsumerTerm.lifeMapTaskName],
              hintText: _copy[ConsumerTerm.lifeMapTaskNameHint],
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceLg),
          Align(
            alignment: Alignment.centerRight,
            child: ClaraButton.primary(
              label: _copy[ConsumerTerm.lifeMapAddTask],
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
                      ? _copy[ConsumerTerm.lifeMapUnnamedJourney]
                      : episode.title,
                  style: theme.textTheme.titleSmall
                      ?.copyWith(fontWeight: FontWeight.w600),
                ),
              ),
              const SizedBox(width: ClaraTokens.spaceSm),
              _PriorityChip(
                priority: episode.priority,
                labels: _priorityLabels,
              ),
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
                    label: Text(_copy[ConsumerTerm.lifeMapOneQuestion]),
                  ),
                TextButton.icon(
                  onPressed: () => _openReplay(episode),
                  icon: const Icon(Icons.history, size: 18),
                  label: Text(_copy[ConsumerTerm.lifeMapViewHistory]),
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
              task.title.isEmpty
                  ? _copy[ConsumerTerm.lifeMapUnnamedTask]
                  : task.title,
              style: theme.textTheme.bodyLarge,
            ),
          ),
        ],
      ),
    );
  }
}

class _ReplaySheet extends StatelessWidget {
  const _ReplaySheet({
    required this.replay,
    required this.copy,
    required this.onCorrect,
    required this.onDispute,
  });

  final Map<String, dynamic> replay;
  final ConsumerTerminology copy;
  final Future<void> Function(Map<String, dynamic>) onCorrect;
  final Future<void> Function(Map<String, dynamic>) onDispute;

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
          copy[ConsumerTerm.lifeMapReplayLabel],
          style: theme.textTheme.labelLarge?.copyWith(
            color: theme.colorScheme.primary,
          ),
        ),
        const SizedBox(height: ClaraTokens.spaceXs),
        Text(
          episode is Map
              ? _str(episode['title'])
              : copy[ConsumerTerm.lifeMapReplayFallbackTitle],
          style: theme.textTheme.headlineSmall
              ?.copyWith(fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: ClaraTokens.spaceSm),
        Text(
          copy[ConsumerTerm.lifeMapReplayDescription],
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
                copy[ConsumerTerm.lifeMapReplayStale],
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.error,
                ),
              ),
            ),
          ),
        ],
        const SizedBox(height: ClaraTokens.spaceLg),
        if (events.isEmpty)
          ClaraEmptyState(
            icon: Icons.history,
            title: copy[ConsumerTerm.lifeMapReplayEmptyTitle],
            message: copy[ConsumerTerm.lifeMapReplayEmptyDescription],
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
                          label: Text(copy.format(
                            ConsumerTerm.lifeMapReplayVersion,
                            <String, Object?>{
                              'revision': _str(event['revision']),
                            },
                          )),
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
                        copy.format(
                          ConsumerTerm.lifeMapReplayWhy,
                          <String, Object?>{'reason': _str(why['text'])},
                        ),
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                    const SizedBox(height: ClaraTokens.spaceSm),
                    Wrap(
                      alignment: WrapAlignment.end,
                      spacing: ClaraTokens.spaceSm,
                      children: [
                        TextButton.icon(
                          onPressed: () => onCorrect(event),
                          icon: const Icon(Icons.edit_outlined, size: 18),
                          label: Text(copy[ConsumerTerm.lifeMapReplayEdit]),
                        ),
                        if (_str(event['truth_state']) != 'disputed')
                          TextButton.icon(
                            onPressed: () => onDispute(event),
                            icon: const Icon(Icons.report_outlined, size: 18),
                            label: Text(
                              copy[ConsumerTerm.lifeMapReplayDispute],
                            ),
                          ),
                      ],
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
  const _PriorityChip({required this.priority, required this.labels});

  final String priority;
  final Map<String, String> labels;

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

    final label = labels[priority] ?? labels['routine']!;

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
