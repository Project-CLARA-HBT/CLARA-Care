import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/session_store.dart';
import '../../theme/components/clara_button.dart';
import '../../theme/components/clara_card.dart';
import '../../theme/tokens.dart';
import '../../widgets/error_retry_view.dart';

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
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;
  final String visitId;
  final String title;

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
        _error = 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.';
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
        setState(() => _error = 'Không thể tải dữ liệu buổi khám.');
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
            () => _error = 'Không thể hoàn tất thao tác. Vui lòng thử lại.');
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _addConcern() => _run((token) async {
        final value = _concernController.text.trim();
        if (value.length < 2) {
          throw ApiException(message: 'Hãy nhập điều bạn muốn hỏi bác sĩ.');
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
            message: 'Hãy đặt tên và dán nội dung tài liệu bạn đã chọn.',
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
    return Scaffold(
      appBar: AppBar(title: Text(widget.title)),
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
          'CLARA giúp chuẩn bị cho cuộc trao đổi với bác sĩ, không chẩn đoán '
          'hay kê đơn. Chỉ nội dung bạn tự chọn và duyệt mới được sử dụng.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
      );

  Widget _concernSection(BuildContext context) => ClaraCard.static_(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text('1. Điều cần hỏi',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: ClaraTokens.spaceSm),
            TextField(
              controller: _concernController,
              minLines: 2,
              maxLines: 4,
              decoration: const InputDecoration(
                labelText: 'Điều bạn muốn trao đổi với bác sĩ',
              ),
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            ClaraButton.secondary(
              label: 'Lưu điều cần hỏi',
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
            Text('2. Tài liệu bạn chọn',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: ClaraTokens.spaceXs),
            Text(
              'Dán nội dung đã chọn. CLARA không tự mở liên kết hay tự nhập hồ sơ.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            TextField(
              controller: _documentTitleController,
              decoration: const InputDecoration(labelText: 'Tên tài liệu'),
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            TextField(
              controller: _documentTextController,
              minLines: 3,
              maxLines: 8,
              decoration:
                  const InputDecoration(labelText: 'Nội dung văn bản đã chọn'),
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            ClaraButton.secondary(
              label: 'Lưu tài liệu',
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
                    ? 'Đã rút hoặc xoá khỏi xử lý'
                    : 'Đang do bạn kiểm soát',
                style: Theme.of(context).textTheme.bodySmall,
              ),
              if (!inactive)
                Wrap(
                  spacing: ClaraTokens.spaceXs,
                  children: <Widget>[
                    TextButton(
                      onPressed: _saving ? null : () => _extract(document),
                      child: const Text('Kiểm tra kế hoạch'),
                    ),
                    TextButton(
                      onPressed:
                          _saving ? null : () => _withdrawDocument(document),
                      child: const Text('Rút khỏi xử lý'),
                    ),
                    TextButton(
                      onPressed:
                          _saving ? null : () => _deleteDocument(document),
                      child: const Text('Xoá nội dung'),
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
          Text('3. Rà soát có căn cứ',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: ClaraTokens.spaceXs),
          Text(
            unavailable
                ? 'Không có mục đủ căn cứ để đề xuất. Hãy kiểm tra lại với bác sĩ.'
                : 'Chỉ xác nhận chỉ dẫn của bác sĩ có đoạn nguồn nguyên văn.',
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
              subtitle: Text(confirmable
                  ? 'Nguồn: “$source”'
                  : 'Diễn giải AI hoặc thiếu nguồn — không thể xác nhận.'),
            );
          }),
          if (!unavailable)
            Wrap(
              spacing: ClaraTokens.spaceSm,
              children: <Widget>[
                ClaraButton.primary(
                  label: 'Xác nhận mục đã chọn',
                  icon: Icons.verified_outlined,
                  loading: _saving,
                  onPressed: _candidateIds.isEmpty ? null : _confirmPlan,
                ),
                TextButton(
                  onPressed: _saving ? null : _withdrawPlan,
                  child: const Text('Rút bản nháp'),
                ),
              ],
            ),
        ],
      ),
    );
  }

  Widget _packSection(BuildContext context) {
    const groups = <(String, String)>[
      ('concerns', 'Điều cần hỏi'),
      ('medications', 'Thuốc đã xác nhận'),
      ('episodes', 'Hành trình liên quan'),
      ('events', 'Diễn biến đã xác nhận'),
      ('instructions', 'Chỉ dẫn bác sĩ bạn đã xác nhận'),
    ];
    return ClaraCard.static_(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text('4. Chọn và duyệt Visit Pack',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: ClaraTokens.spaceXs),
          Text(
            'Không có mục nào được tự động thêm hoặc chia sẻ.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          for (final group in groups) ...<Widget>[
            const SizedBox(height: ClaraTokens.spaceSm),
            Text(group.$2, style: Theme.of(context).textTheme.titleSmall),
            if (_maps(_options[group.$1]).isEmpty)
              Text('Chưa có mục phù hợp.',
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
            label: _pack == null ? 'Tạo và duyệt gói' : 'Tạo phiên bản mới',
            icon: Icons.inventory_2_outlined,
            loading: _saving,
            onPressed: _packIds.isEmpty ? null : _createAndApprovePack,
          ),
          if (_pack != null) ...<Widget>[
            const SizedBox(height: ClaraTokens.spaceSm),
            Text(
              'Phiên bản ${_text(_pack!['version_no'])} đã được bạn duyệt.',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            if (_share == null)
              TextButton(
                onPressed: _saving ? null : _createShare,
                child: const Text('Tạo liên kết 7 ngày'),
              )
            else ...<Widget>[
              SelectableText(
                '/api/v1/visit-packs/shared/${_text(_share!['token'])}',
              ),
              TextButton(
                onPressed: _saving ? null : _revokeShare,
                child: const Text('Thu hồi liên kết'),
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
            Text('Đồng ý ghi âm riêng cho buổi này',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: ClaraTokens.spaceXs),
            Text(
              'Bạn có thể rút lại ngay. Chưa có đồng ý thì Scribe không được xử lý.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              value: _scribeConsented,
              onChanged: _saving ? null : (_) => _toggleScribeConsent(),
              title: Text(_scribeConsented
                  ? 'Đã đồng ý cho buổi này'
                  : 'Chưa đồng ý ghi âm'),
            ),
          ],
        ),
      );
}
