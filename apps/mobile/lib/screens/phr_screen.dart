import 'dart:convert';

import 'package:flutter/material.dart';

import '../core/analytics.dart';
import '../core/api_client.dart';
import '../core/feature_flags.dart';
import '../core/session_store.dart';

// =============================================================================
// Personal Health Record (PHR) mobile screen — personal-health-record Req 17.
//
//   * 17.1 View profile, allergies, conditions, medications.
//   * 17.2 Edit profile + entries against the same server-validated contract
//          (PUT /api/v1/phr/record). The server enforces field length/range and
//          the severity/status domains; failures surface as inline errors.
//   * 17.3 Display informationSource + verificationStatus badges per entry.
//   * 17.4 Persistent self-declared / decision-support-only disclaimer.
//   * 17.5 Vietnamese-first bilingual vi/en copy (toggleable, defaults to vi).
//
// The PHR is self-declared, decision-support data only — not an EMR/EHR and not
// legally binding (Requirement 18.4). The screen uses the legacy GET/PUT
// `/record` contract so it behaves identically regardless of the enhanced
// feature flag state (Requirement 18.1).
// =============================================================================

/// Supported interface languages. Vietnamese is first/default (Requirement 17.5).
enum PhrLang { vi, en }

/// Vietnamese-first bilingual copy. Each getter returns the string for the
/// active [lang]; Vietnamese is the default so the screen is Vietnamese-first.
class PhrStrings {
  const PhrStrings(this.lang);

  final PhrLang lang;

  String _t(String vi, String en) => lang == PhrLang.vi ? vi : en;

  String get title => _t('Hồ sơ sức khỏe', 'Health Record');
  String get languageToggle => _t('EN', 'VI');
  String get loadError => _t('Không thể tải hồ sơ. Vui lòng thử lại.',
      'Could not load the record. Please try again.');
  String get retry => _t('Thử lại', 'Retry');
  String get save => _t('Lưu', 'Save');
  String get saved => _t('Đã lưu hồ sơ.', 'Record saved.');
  String get saving => _t('Đang lưu...', 'Saving...');
  String get completenessTitle =>
      _t('Mức độ hoàn thiện hồ sơ', 'Profile completeness');
  String get completenessComplete => _t(
        'Hồ sơ của bạn đã đầy đủ thông tin quan trọng.',
        'Your profile includes the important details.',
      );
  String get completenessNextUp => _t('Nên bổ sung', 'Consider adding');

  // Disclaimer (Requirement 17.4 / 18.4).
  String get disclaimer => _t(
        'Hồ sơ do bạn tự khai, chỉ hỗ trợ ra quyết định — không phải bệnh án '
            '(EMR/EHR) và không có giá trị pháp lý. Hãy trao đổi với bác sĩ.',
        'Self-declared, decision-support only — not a medical record (EMR/EHR) '
            'and not legally binding. Please review with a clinician.',
      );

  // Profile fields.
  String get sectionProfile => _t('Thông tin cá nhân', 'Profile');
  String get fullName => _t('Họ và tên', 'Full name');
  String get dateOfBirth => _t('Ngày sinh', 'Date of birth');
  String get gender => _t('Giới tính', 'Gender');
  String get bloodType => _t('Nhóm máu', 'Blood type');
  String get heightCm => _t('Chiều cao (cm)', 'Height (cm)');
  String get weightKg => _t('Cân nặng (kg)', 'Weight (kg)');
  String get phone => _t('Điện thoại', 'Phone');
  String get address => _t('Địa chỉ', 'Address');
  String get emergencyContactName =>
      _t('Người liên hệ khẩn cấp', 'Emergency contact');
  String get emergencyContactPhone =>
      _t('SĐT liên hệ khẩn cấp', 'Emergency phone');
  String get insuranceId => _t('Mã bảo hiểm', 'Insurance ID');
  String get notes => _t('Ghi chú', 'Notes');

  // Sections.
  String get sectionAllergies => _t('Dị ứng', 'Allergies');
  String get sectionConditions => _t('Bệnh lý', 'Conditions');
  String get sectionMedications => _t('Thuốc', 'Medications');
  String get emptySection => _t('Chưa có dữ liệu.', 'No data yet.');
  String get add => _t('Thêm', 'Add');
  String get edit => _t('Sửa', 'Edit');
  String get delete => _t('Xóa', 'Delete');
  String get cancel => _t('Hủy', 'Cancel');
  String get done => _t('Xong', 'Done');

  // Entry fields.
  // Enhanced (flag-gated) read-only surfaces — export + emergency card (Req 5.6).
  String get exportAction => _t('Xuất hồ sơ', 'Export');
  String get emergencyCardAction => _t('Thẻ khẩn cấp', 'Emergency card');
  String get exportTitle => _t('Xuất hồ sơ (chỉ đọc)', 'Export (read-only)');
  String get emergencyCardTitle => _t('Thẻ khẩn cấp', 'Emergency card');
  String get close => _t('Đóng', 'Close');
  String get emergencyEmpty =>
      _t('Chưa có thông tin khẩn cấp.', 'No emergency information yet.');
  String get bloodTypeUnknown => _t('Chưa rõ', 'Unknown');
  String get noEmergencyContact =>
      _t('Chưa có người liên hệ khẩn cấp.', 'No emergency contact.');

  String get name => _t('Tên', 'Name');
  String get reaction => _t('Phản ứng', 'Reaction');
  String get severity => _t('Mức độ', 'Severity');
  String get clinicalStatus => _t('Tình trạng', 'Status');
  String get diagnosedOn => _t('Ngày chẩn đoán', 'Diagnosed on');
  String get dose => _t('Liều', 'Dose');
  String get frequency => _t('Tần suất', 'Frequency');
  String get startedOn => _t('Ngày bắt đầu', 'Started on');
  String get isCurrent => _t('Đang dùng', 'Currently taking');
  String get note => _t('Ghi chú', 'Note');
  String get nameRequired => _t('Vui lòng nhập tên.', 'Name is required.');

  String severityLabel(String value) {
    switch (value) {
      case 'mild':
        return _t('Nhẹ', 'Mild');
      case 'moderate':
        return _t('Vừa', 'Moderate');
      case 'severe':
        return _t('Nặng', 'Severe');
      default:
        return _t('Không rõ', 'Unknown');
    }
  }

  String statusLabel(String value) {
    switch (value) {
      case 'active':
        return _t('Đang mắc', 'Active');
      case 'resolved':
        return _t('Đã khỏi', 'Resolved');
      case 'monitoring':
        return _t('Theo dõi', 'Monitoring');
      default:
        return _t('Không rõ', 'Unknown');
    }
  }

  /// Provenance badge label (Requirement 17.3).
  String sourceLabel(String value) {
    switch (value) {
      case 'ocr':
        return _t('OCR', 'OCR');
      case 'imported':
        return _t('Nhập khẩu', 'Imported');
      default:
        return _t('Tự khai', 'Self-declared');
    }
  }

  /// Verification badge label (Requirement 17.3).
  String verificationLabel(String value) {
    switch (value) {
      case 'confirmed':
        return _t('Đã xác minh', 'Confirmed');
      case 'provisional':
        return _t('Tạm thời', 'Provisional');
      case 'refuted':
        return _t('Bác bỏ', 'Refuted');
      case 'entered-in-error':
        return _t('Nhập sai', 'Entered in error');
      default:
        return _t('Chưa xác minh', 'Unconfirmed');
    }
  }
}

// =============================================================================
// Models — mirror the legacy GET/PUT /record contract plus optional provenance.
// Provenance fields (information_source / verification_status) default to
// `self-declared` / `unconfirmed` so badges render even when the legacy
// endpoint omits them (Requirement 17.3, 6.2).
// =============================================================================

const List<String> kAllergySeverities = [
  'mild',
  'moderate',
  'severe',
  'unknown'
];
const List<String> kConditionStatuses = [
  'active',
  'resolved',
  'monitoring',
  'unknown'
];

String _str(Object? value) => value == null ? '' : value.toString();

String _source(Map<String, dynamic> json) {
  final raw = _str(json['information_source']).trim();
  return raw.isEmpty ? 'self-declared' : raw;
}

String _verification(Map<String, dynamic> json) {
  final raw = _str(json['verification_status']).trim();
  return raw.isEmpty ? 'unconfirmed' : raw;
}

double? _toDouble(Object? value) {
  if (value is num) {
    return value.toDouble();
  }
  if (value is String && value.trim().isNotEmpty) {
    return double.tryParse(value.trim());
  }
  return null;
}

/// Generates a client-side entry id for newly added entries. The legacy
/// `PUT /record` contract requires a non-empty id per item (max 64 chars).
String _newEntryId(String prefix) =>
    '${prefix}_${DateTime.now().microsecondsSinceEpoch}';

class PhrAllergy {
  PhrAllergy({
    required this.id,
    required this.name,
    this.reaction = '',
    this.severity = 'unknown',
    this.note = '',
    this.informationSource = 'self-declared',
    this.verificationStatus = 'unconfirmed',
  });

  String id;
  String name;
  String reaction;
  String severity;
  String note;
  final String informationSource;
  final String verificationStatus;

  factory PhrAllergy.fromJson(Map<String, dynamic> json) {
    final severity = _str(json['severity']);
    return PhrAllergy(
      id: _str(json['id']),
      name: _str(json['name']),
      reaction: _str(json['reaction']),
      severity: kAllergySeverities.contains(severity) ? severity : 'unknown',
      note: _str(json['note']),
      informationSource: _source(json),
      verificationStatus: _verification(json),
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'reaction': reaction,
        'severity': severity,
        'note': note,
      };
}

class PhrCondition {
  PhrCondition({
    required this.id,
    required this.name,
    this.status = 'unknown',
    this.diagnosedOn,
    this.note = '',
    this.informationSource = 'self-declared',
    this.verificationStatus = 'unconfirmed',
  });

  String id;
  String name;
  String status;
  String? diagnosedOn;
  String note;
  final String informationSource;
  final String verificationStatus;

  factory PhrCondition.fromJson(Map<String, dynamic> json) {
    final status = _str(json['status']);
    final diagnosed = _str(json['diagnosed_on']);
    return PhrCondition(
      id: _str(json['id']),
      name: _str(json['name']),
      status: kConditionStatuses.contains(status) ? status : 'unknown',
      diagnosedOn: diagnosed.isEmpty ? null : diagnosed,
      note: _str(json['note']),
      informationSource: _source(json),
      verificationStatus: _verification(json),
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'status': status,
        'diagnosed_on': (diagnosedOn != null && diagnosedOn!.isNotEmpty)
            ? diagnosedOn
            : null,
        'note': note,
      };
}

class PhrMedication {
  PhrMedication({
    required this.id,
    required this.name,
    this.dose = '',
    this.frequency = '',
    this.startedOn,
    this.isCurrent = true,
    this.note = '',
    this.informationSource = 'self-declared',
    this.verificationStatus = 'unconfirmed',
  });

  String id;
  String name;
  String dose;
  String frequency;
  String? startedOn;
  bool isCurrent;
  String note;
  final String informationSource;
  final String verificationStatus;

  factory PhrMedication.fromJson(Map<String, dynamic> json) {
    final started = _str(json['started_on']);
    final current = json['is_current'];
    return PhrMedication(
      id: _str(json['id']),
      name: _str(json['name']),
      dose: _str(json['dose']),
      frequency: _str(json['frequency']),
      startedOn: started.isEmpty ? null : started,
      isCurrent: current is bool ? current : true,
      note: _str(json['note']),
      informationSource: _source(json),
      verificationStatus: _verification(json),
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'dose': dose,
        'frequency': frequency,
        'started_on':
            (startedOn != null && startedOn!.isNotEmpty) ? startedOn : null,
        'is_current': isCurrent,
        'note': note,
      };
}

/// Full PHR record mirroring the legacy `/record` contract.
class PhrRecordModel {
  PhrRecordModel({
    this.fullName = '',
    this.dateOfBirth,
    this.gender = '',
    this.bloodType = '',
    this.heightCm,
    this.weightKg,
    this.phone = '',
    this.address = '',
    this.emergencyContactName = '',
    this.emergencyContactPhone = '',
    this.insuranceId = '',
    this.notes = '',
    List<PhrAllergy>? allergies,
    List<PhrCondition>? conditions,
    List<PhrMedication>? medications,
  })  : allergies = allergies ?? <PhrAllergy>[],
        conditions = conditions ?? <PhrCondition>[],
        medications = medications ?? <PhrMedication>[];

  String fullName;
  String? dateOfBirth;
  String gender;
  String bloodType;
  double? heightCm;
  double? weightKg;
  String phone;
  String address;
  String emergencyContactName;
  String emergencyContactPhone;
  String insuranceId;
  String notes;
  List<PhrAllergy> allergies;
  List<PhrCondition> conditions;
  List<PhrMedication> medications;

  static List<Map<String, dynamic>> _objectList(Object? value) {
    if (value is! List) return const [];
    return value
        .whereType<Map>()
        .map((e) => e.cast<String, dynamic>())
        .toList();
  }

  factory PhrRecordModel.fromJson(Map<String, dynamic> json) {
    final dob = _str(json['date_of_birth']);
    return PhrRecordModel(
      fullName: _str(json['full_name']),
      dateOfBirth: dob.isEmpty ? null : dob,
      gender: _str(json['gender']),
      bloodType: _str(json['blood_type']),
      heightCm: _toDouble(json['height_cm']),
      weightKg: _toDouble(json['weight_kg']),
      phone: _str(json['phone']),
      address: _str(json['address']),
      emergencyContactName: _str(json['emergency_contact_name']),
      emergencyContactPhone: _str(json['emergency_contact_phone']),
      insuranceId: _str(json['insurance_id']),
      notes: _str(json['notes']),
      allergies:
          _objectList(json['allergies']).map(PhrAllergy.fromJson).toList(),
      conditions:
          _objectList(json['conditions']).map(PhrCondition.fromJson).toList(),
      medications:
          _objectList(json['medications']).map(PhrMedication.fromJson).toList(),
    );
  }

  /// Serializes to the server-validated `PUT /record` payload (Requirement 17.2).
  Map<String, dynamic> toJson() => {
        'full_name': fullName,
        'date_of_birth': (dateOfBirth != null && dateOfBirth!.isNotEmpty)
            ? dateOfBirth
            : null,
        'gender': gender,
        'blood_type': bloodType,
        'height_cm': heightCm,
        'weight_kg': weightKg,
        'phone': phone,
        'address': address,
        'emergency_contact_name': emergencyContactName,
        'emergency_contact_phone': emergencyContactPhone,
        'insurance_id': insuranceId,
        'notes': notes,
        'allergies': allergies.map((e) => e.toJson()).toList(),
        'conditions': conditions.map((e) => e.toJson()).toList(),
        'medications': medications.map((e) => e.toJson()).toList(),
      };
}

// =============================================================================
// Read-only enhanced projections (flag-gated behind phr_enhanced_mobile_enabled)
//
// These are pure, client-side, read-only projections of the already-loaded
// record (no new API call) used by the enhanced PHR surfaces (Requirement 5.6):
//   * The export view shows the full record serialized as JSON (read-only).
//   * The emergency card mirrors the web `/phr/emergency-card` shape
//     (allergies, current medications, conditions, blood type, emergency
//     contact). Only currently-taken medications are included.
// Both surfaces are additive and never alter the legacy GET/PUT behavior; when
// the flag is off they are not constructed at all.
// =============================================================================

/// A single emergency-card allergy line (name + severity + reaction).
class PhrEmergencyAllergy {
  const PhrEmergencyAllergy({
    required this.name,
    required this.severity,
    required this.reaction,
  });
  final String name;
  final String severity;
  final String reaction;
}

/// A single emergency-card medication line (name + dose).
class PhrEmergencyMedication {
  const PhrEmergencyMedication({required this.name, required this.dose});
  final String name;
  final String dose;
}

/// A single emergency-card condition line (name + status).
class PhrEmergencyCondition {
  const PhrEmergencyCondition({required this.name, required this.status});
  final String name;
  final String status;
}

/// A read-only emergency-card projection of a loaded [PhrRecordModel], mirroring
/// the web `/phr/emergency-card` field shape (Requirement 5.6). Pure — derived
/// entirely from the in-memory record, so it can be unit tested and never makes
/// a network call.
class PhrEmergencyCardProjection {
  PhrEmergencyCardProjection({
    required this.allergies,
    required this.currentMedications,
    required this.conditions,
    required this.bloodType,
    required this.emergencyContactName,
    required this.emergencyContactPhone,
  });

  final List<PhrEmergencyAllergy> allergies;
  final List<PhrEmergencyMedication> currentMedications;
  final List<PhrEmergencyCondition> conditions;
  final String bloodType;
  final String emergencyContactName;
  final String emergencyContactPhone;

  /// Whether the card carries any displayable emergency information.
  bool get isEmpty =>
      allergies.isEmpty &&
      currentMedications.isEmpty &&
      conditions.isEmpty &&
      bloodType.trim().isEmpty &&
      emergencyContactName.trim().isEmpty &&
      emergencyContactPhone.trim().isEmpty;

  factory PhrEmergencyCardProjection.fromRecord(PhrRecordModel record) {
    return PhrEmergencyCardProjection(
      allergies: record.allergies
          .map((a) => PhrEmergencyAllergy(
                name: a.name,
                severity: a.severity,
                reaction: a.reaction,
              ))
          .toList(),
      // Only currently-taken medications belong on the emergency card.
      currentMedications: record.medications
          .where((m) => m.isCurrent)
          .map((m) => PhrEmergencyMedication(name: m.name, dose: m.dose))
          .toList(),
      conditions: record.conditions
          .map((c) => PhrEmergencyCondition(name: c.name, status: c.status))
          .toList(),
      bloodType: record.bloodType,
      emergencyContactName: record.emergencyContactName,
      emergencyContactPhone: record.emergencyContactPhone,
    );
  }
}

// =============================================================================
// Screen
// =============================================================================

class PhrScreen extends StatefulWidget {
  const PhrScreen({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    this.featureFlags,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  /// Resolved mobile feature gates. When omitted (or when
  /// `phr_enhanced_mobile_enabled` is off) the screen behaves exactly as the
  /// legacy PHR surface — the enhanced export/emergency-card affordances are
  /// not rendered (Requirement 5.6, fail-closed default).
  final MobileFeatureFlagResolver? featureFlags;

  @override
  State<PhrScreen> createState() => _PhrScreenState();
}

class _PhrScreenState extends State<PhrScreen> {
  PhrLang _lang = PhrLang.vi;
  bool _loading = false;
  bool _saving = false;
  String? _loadError;
  String? _saveError;
  PhrRecordModel? _record;

  /// Whether the flag-gated enhanced PHR reads (export + emergency card) are
  /// enabled. Defaults to a fail-closed resolver when none was injected, so the
  /// screen behaves as the legacy PHR surface unless the flag is explicitly on
  /// (Requirement 5.6).
  bool get _phrEnhancedEnabled =>
      (widget.featureFlags ?? MobileFeatureFlagResolver()).phrEnhancedEnabled;

  // Profile text controllers (created once the record is loaded).
  final _fullName = TextEditingController();
  final _gender = TextEditingController();
  final _bloodType = TextEditingController();
  final _height = TextEditingController();
  final _weight = TextEditingController();
  final _phone = TextEditingController();
  final _address = TextEditingController();
  final _emName = TextEditingController();
  final _emPhone = TextEditingController();
  final _insurance = TextEditingController();
  final _notes = TextEditingController();
  final _dob = TextEditingController();

  @override
  void initState() {
    super.initState();
    getAnalyticsClient().captureScreenView(MobileAnalyticsEvents.phrViewed);
    _load();
  }

  @override
  void dispose() {
    for (final c in [
      _fullName,
      _gender,
      _bloodType,
      _height,
      _weight,
      _phone,
      _address,
      _emName,
      _emPhone,
      _insurance,
      _notes,
      _dob,
    ]) {
      c.dispose();
    }
    super.dispose();
  }

  void _bindControllers(PhrRecordModel record) {
    _fullName.text = record.fullName;
    _gender.text = record.gender;
    _bloodType.text = record.bloodType;
    _height.text = record.heightCm?.toString() ?? '';
    _weight.text = record.weightKg?.toString() ?? '';
    _phone.text = record.phone;
    _address.text = record.address;
    _emName.text = record.emergencyContactName;
    _emPhone.text = record.emergencyContactPhone;
    _insurance.text = record.insuranceId;
    _notes.text = record.notes;
    _dob.text = record.dateOfBirth ?? '';
  }

  Future<void> _load() async {
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) {
      setState(() => _loadError = const PhrStrings(PhrLang.vi).loadError);
      return;
    }
    setState(() {
      _loading = true;
      _loadError = null;
      _saveError = null;
    });
    try {
      final data = await widget.apiClient.getPhrRecord(accessToken: token);
      final record = PhrRecordModel.fromJson(data);
      if (!mounted) return;
      setState(() => _record = record);
      _bindControllers(record);
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _loadError = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(() => _loadError = PhrStrings(_lang).loadError);
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  /// Folds the profile text controllers back into the record before saving.
  void _captureProfile(PhrRecordModel record) {
    record.fullName = _fullName.text.trim();
    record.gender = _gender.text.trim();
    record.bloodType = _bloodType.text.trim();
    record.heightCm = _toDouble(_height.text.trim());
    record.weightKg = _toDouble(_weight.text.trim());
    record.phone = _phone.text.trim();
    record.address = _address.text.trim();
    record.emergencyContactName = _emName.text.trim();
    record.emergencyContactPhone = _emPhone.text.trim();
    record.insuranceId = _insurance.text.trim();
    record.notes = _notes.text.trim();
    final dob = _dob.text.trim();
    record.dateOfBirth = dob.isEmpty ? null : dob;
  }

  Future<void> _save() async {
    final record = _record;
    final token = widget.sessionStore.accessToken;
    if (record == null) return;
    if (token == null || token.isEmpty) {
      setState(() => _saveError = PhrStrings(_lang).loadError);
      return;
    }
    _captureProfile(record);

    setState(() {
      _saving = true;
      _saveError = null;
    });
    try {
      final data = await widget.apiClient.updatePhrRecord(
        accessToken: token,
        payload: record.toJson(),
      );
      // Non-PII analytics: a single total entry count only, never names or
      // free text. (Category-specific keys like "allergy_count" would be
      // stripped by the PII filter, so a generic total is used.)
      getAnalyticsClient().capture(AnalyticsEvent(
        MobileAnalyticsEvents.phrSaved,
        {
          'entry_count': record.allergies.length +
              record.conditions.length +
              record.medications.length,
        },
      ));
      final updated = PhrRecordModel.fromJson(data);
      if (!mounted) return;
      setState(() => _record = updated);
      _bindControllers(updated);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(PhrStrings(_lang).saved)),
      );
    } on ApiException catch (error) {
      if (!mounted) return;
      // The server enforces the validated contract; surface its message inline.
      setState(() => _saveError = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(() => _saveError = PhrStrings(_lang).loadError);
    } finally {
      if (mounted) {
        setState(() => _saving = false);
      }
    }
  }

  void _toggleLang() {
    setState(() => _lang = _lang == PhrLang.vi ? PhrLang.en : PhrLang.vi);
  }

  @override
  Widget build(BuildContext context) {
    final s = PhrStrings(_lang);
    final record = _record;

    return Scaffold(
      appBar: AppBar(
        title: Text(s.title),
        actions: [
          TextButton(
            onPressed: _toggleLang,
            child: Text(
              s.languageToggle,
              style: TextStyle(color: Theme.of(context).colorScheme.onPrimary),
            ),
          ),
        ],
      ),
      floatingActionButton: (record == null)
          ? null
          : FloatingActionButton.extended(
              onPressed: _saving ? null : _save,
              icon: _saving
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.save),
              label: Text(_saving ? s.saving : s.save),
            ),
      body: _buildBody(context, s, record),
    );
  }

  Widget _buildBody(
      BuildContext context, PhrStrings s, PhrRecordModel? record) {
    if (_loading && record == null) {
      // Keep the self-declared disclaimer present even while loading so it is
      // persistent on every PHR surface (Requirement 5.3 / 17.4).
      return Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: PhrDisclaimerBanner(text: s.disclaimer),
          ),
          const Expanded(child: Center(child: CircularProgressIndicator())),
        ],
      );
    }
    if (_loadError != null && record == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              PhrDisclaimerBanner(text: s.disclaimer),
              const SizedBox(height: 16),
              Text(
                _loadError!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 12),
              FilledButton(onPressed: _load, child: Text(s.retry)),
            ],
          ),
        ),
      );
    }
    if (record == null) {
      return const SizedBox.shrink();
    }

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
      children: [
        // Persistent disclaimer on every PHR surface (Requirement 17.4).
        PhrDisclaimerBanner(text: s.disclaimer),
        const SizedBox(height: 16),
        // Flag-gated read-only enhanced surfaces — export + emergency card
        // (Requirement 5.6). Hidden entirely when the flag is off so legacy
        // behavior is unchanged.
        if (_phrEnhancedEnabled) ...[
          _enhancedActions(s, record),
          const SizedBox(height: 16),
        ],
        if (_saveError != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Text(
              _saveError!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ),
        _profileSection(s, record),
        const SizedBox(height: 16),
        _allergiesSection(s, record),
        const SizedBox(height: 16),
        _conditionsSection(s, record),
        const SizedBox(height: 16),
        _medicationsSection(s, record),
      ],
    );
  }

  /// Flag-gated read-only affordances opening the export + emergency-card
  /// surfaces (Requirement 5.6). Both views are read-only projections of the
  /// already-loaded record — no additional API calls.
  Widget _enhancedActions(PhrStrings s, PhrRecordModel record) {
    return Card(
      key: const Key('phr-enhanced-actions'),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Wrap(
          spacing: 12,
          runSpacing: 8,
          children: [
            OutlinedButton.icon(
              key: const Key('phr-export-action'),
              onPressed: () => _openExport(s, record),
              icon: const Icon(Icons.download_outlined, size: 18),
              label: Text(s.exportAction),
            ),
            FilledButton.tonalIcon(
              key: const Key('phr-emergency-card-action'),
              onPressed: () => _openEmergencyCard(s, record),
              icon: const Icon(Icons.local_hospital_outlined, size: 18),
              label: Text(s.emergencyCardAction),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _openExport(PhrStrings s, PhrRecordModel record) {
    return Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => _PhrExportView(strings: s, record: record),
      ),
    );
  }

  Future<void> _openEmergencyCard(PhrStrings s, PhrRecordModel record) {
    return Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => _PhrEmergencyCardView(
          strings: s,
          card: PhrEmergencyCardProjection.fromRecord(record),
        ),
      ),
    );
  }

  Widget _profileSection(PhrStrings s, PhrRecordModel record) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(s.sectionProfile,
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            _field(_fullName, s.fullName),
            _field(_dob, s.dateOfBirth, hint: 'YYYY-MM-DD'),
            _field(_gender, s.gender),
            _field(_bloodType, s.bloodType),
            _field(_height, s.heightCm, keyboardType: TextInputType.number),
            _field(_weight, s.weightKg, keyboardType: TextInputType.number),
            _field(_phone, s.phone, keyboardType: TextInputType.phone),
            _field(_address, s.address),
            _field(_emName, s.emergencyContactName),
            _field(_emPhone, s.emergencyContactPhone,
                keyboardType: TextInputType.phone),
            _field(_insurance, s.insuranceId),
            _field(_notes, s.notes, maxLines: 3),
          ],
        ),
      ),
    );
  }

  Widget _field(
    TextEditingController controller,
    String label, {
    String? hint,
    TextInputType? keyboardType,
    int maxLines = 1,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: TextField(
        controller: controller,
        keyboardType: keyboardType,
        maxLines: maxLines,
        decoration: InputDecoration(
          labelText: label,
          hintText: hint,
          border: const OutlineInputBorder(),
          isDense: true,
        ),
      ),
    );
  }

  // --- Allergies ---
  Widget _allergiesSection(PhrStrings s, PhrRecordModel record) {
    return _EntrySection(
      title: s.sectionAllergies,
      addLabel: s.add,
      emptyLabel: s.emptySection,
      onAdd: () => _editAllergy(s, record, null),
      itemCount: record.allergies.length,
      itemBuilder: (i) {
        final a = record.allergies[i];
        final details = <String>[
          if (a.reaction.isNotEmpty) a.reaction,
          s.severityLabel(a.severity),
        ];
        return _EntryTile(
          title: a.name,
          subtitle: details.join(' • '),
          source: s.sourceLabel(a.informationSource),
          verification: s.verificationLabel(a.verificationStatus),
          onEdit: () => _editAllergy(s, record, i),
          onDelete: () => setState(() => record.allergies.removeAt(i)),
        );
      },
    );
  }

  Future<void> _editAllergy(
      PhrStrings s, PhrRecordModel record, int? index) async {
    final existing = index == null ? null : record.allergies[index];
    final result = await showModalBottomSheet<PhrAllergy>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _AllergyEditor(strings: s, existing: existing),
    );
    if (result == null) return;
    setState(() {
      if (index == null) {
        record.allergies.add(result);
      } else {
        record.allergies[index] = result;
      }
    });
  }

  // --- Conditions ---
  Widget _conditionsSection(PhrStrings s, PhrRecordModel record) {
    return _EntrySection(
      title: s.sectionConditions,
      addLabel: s.add,
      emptyLabel: s.emptySection,
      onAdd: () => _editCondition(s, record, null),
      itemCount: record.conditions.length,
      itemBuilder: (i) {
        final c = record.conditions[i];
        final details = <String>[
          s.statusLabel(c.status),
          if (c.diagnosedOn != null && c.diagnosedOn!.isNotEmpty)
            c.diagnosedOn!,
        ];
        return _EntryTile(
          title: c.name,
          subtitle: details.join(' • '),
          source: s.sourceLabel(c.informationSource),
          verification: s.verificationLabel(c.verificationStatus),
          onEdit: () => _editCondition(s, record, i),
          onDelete: () => setState(() => record.conditions.removeAt(i)),
        );
      },
    );
  }

  Future<void> _editCondition(
      PhrStrings s, PhrRecordModel record, int? index) async {
    final existing = index == null ? null : record.conditions[index];
    final result = await showModalBottomSheet<PhrCondition>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _ConditionEditor(strings: s, existing: existing),
    );
    if (result == null) return;
    setState(() {
      if (index == null) {
        record.conditions.add(result);
      } else {
        record.conditions[index] = result;
      }
    });
  }

  // --- Medications ---
  Widget _medicationsSection(PhrStrings s, PhrRecordModel record) {
    return _EntrySection(
      title: s.sectionMedications,
      addLabel: s.add,
      emptyLabel: s.emptySection,
      onAdd: () => _editMedication(s, record, null),
      itemCount: record.medications.length,
      itemBuilder: (i) {
        final m = record.medications[i];
        final details = <String>[
          if (m.dose.isNotEmpty) m.dose,
          if (m.frequency.isNotEmpty) m.frequency,
        ];
        return _EntryTile(
          title: m.name,
          subtitle: details.join(' • '),
          source: s.sourceLabel(m.informationSource),
          verification: s.verificationLabel(m.verificationStatus),
          onEdit: () => _editMedication(s, record, i),
          onDelete: () => setState(() => record.medications.removeAt(i)),
        );
      },
    );
  }

  Future<void> _editMedication(
      PhrStrings s, PhrRecordModel record, int? index) async {
    final existing = index == null ? null : record.medications[index];
    final result = await showModalBottomSheet<PhrMedication>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _MedicationEditor(strings: s, existing: existing),
    );
    if (result == null) return;
    setState(() {
      if (index == null) {
        record.medications.add(result);
      } else {
        record.medications[index] = result;
      }
    });
  }
}

// =============================================================================
// Reusable widgets
// =============================================================================

/// Persistent self-declared / decision-support-only disclaimer banner
/// (Requirement 17.4 / 18.4). Rendered on every PHR surface.
class PhrDisclaimerBanner extends StatelessWidget {
  const PhrDisclaimerBanner({super.key, required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      key: const Key('phr-disclaimer'),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: scheme.secondaryContainer,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.info_outline,
              size: 18, color: scheme.onSecondaryContainer),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: TextStyle(
                color: scheme.onSecondaryContainer,
                fontSize: 12,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// A labelled card section with an add action and an empty-state message.
class _EntrySection extends StatelessWidget {
  const _EntrySection({
    required this.title,
    required this.addLabel,
    required this.emptyLabel,
    required this.onAdd,
    required this.itemCount,
    required this.itemBuilder,
  });

  final String title;
  final String addLabel;
  final String emptyLabel;
  final VoidCallback onAdd;
  final int itemCount;
  final Widget Function(int index) itemBuilder;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(title,
                      style: Theme.of(context).textTheme.titleMedium),
                ),
                TextButton.icon(
                  onPressed: onAdd,
                  icon: const Icon(Icons.add, size: 18),
                  label: Text(addLabel),
                ),
              ],
            ),
            if (itemCount == 0)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Text(emptyLabel),
              )
            else
              ...List.generate(itemCount, itemBuilder),
          ],
        ),
      ),
    );
  }
}

/// A single entry row showing its provenance + verification badges
/// (Requirement 17.3) and edit/delete actions.
class _EntryTile extends StatelessWidget {
  const _EntryTile({
    required this.title,
    required this.subtitle,
    required this.source,
    required this.verification,
    required this.onEdit,
    required this.onDelete,
  });

  final String title;
  final String subtitle;
  final String source;
  final String verification;
  final VoidCallback onEdit;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
              ),
              IconButton(
                onPressed: onEdit,
                icon: const Icon(Icons.edit, size: 18),
                visualDensity: VisualDensity.compact,
              ),
              IconButton(
                onPressed: onDelete,
                icon: const Icon(Icons.delete_outline, size: 18),
                visualDensity: VisualDensity.compact,
              ),
            ],
          ),
          if (subtitle.isNotEmpty)
            Text(subtitle, style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 4),
          Wrap(
            spacing: 6,
            children: [
              _Badge(label: source, icon: Icons.source_outlined),
              _Badge(label: verification, icon: Icons.verified_outlined),
            ],
          ),
          const Divider(height: 16),
        ],
      ),
    );
  }
}

class _Badge extends StatelessWidget {
  const _Badge({required this.label, required this.icon});

  final String label;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: scheme.outlineVariant),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: scheme.onSurfaceVariant),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(fontSize: 11, color: scheme.onSurfaceVariant),
          ),
        ],
      ),
    );
  }
}

// =============================================================================
// Entry editors (bottom sheets)
// =============================================================================

class _AllergyEditor extends StatefulWidget {
  const _AllergyEditor({required this.strings, this.existing});

  final PhrStrings strings;
  final PhrAllergy? existing;

  @override
  State<_AllergyEditor> createState() => _AllergyEditorState();
}

class _AllergyEditorState extends State<_AllergyEditor> {
  late final TextEditingController _name =
      TextEditingController(text: widget.existing?.name ?? '');
  late final TextEditingController _reaction =
      TextEditingController(text: widget.existing?.reaction ?? '');
  late final TextEditingController _note =
      TextEditingController(text: widget.existing?.note ?? '');
  late String _severity = widget.existing?.severity ?? 'unknown';
  String? _error;

  @override
  void dispose() {
    _name.dispose();
    _reaction.dispose();
    _note.dispose();
    super.dispose();
  }

  void _submit() {
    final name = _name.text.trim();
    if (name.isEmpty) {
      setState(() => _error = widget.strings.nameRequired);
      return;
    }
    Navigator.of(context).pop(
      PhrAllergy(
        id: widget.existing?.id ?? _newEntryId('a'),
        name: name,
        reaction: _reaction.text.trim(),
        severity: _severity,
        note: _note.text.trim(),
        informationSource:
            widget.existing?.informationSource ?? 'self-declared',
        verificationStatus:
            widget.existing?.verificationStatus ?? 'unconfirmed',
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.strings;
    return _EditorScaffold(
      title: s.sectionAllergies,
      doneLabel: s.done,
      cancelLabel: s.cancel,
      error: _error,
      onDone: _submit,
      children: [
        _EditorField(controller: _name, label: s.name),
        _EditorField(controller: _reaction, label: s.reaction),
        _Dropdown(
          label: s.severity,
          value: _severity,
          options: kAllergySeverities,
          labelFor: s.severityLabel,
          onChanged: (v) => setState(() => _severity = v),
        ),
        _EditorField(controller: _note, label: s.note, maxLines: 2),
      ],
    );
  }
}

class _ConditionEditor extends StatefulWidget {
  const _ConditionEditor({required this.strings, this.existing});

  final PhrStrings strings;
  final PhrCondition? existing;

  @override
  State<_ConditionEditor> createState() => _ConditionEditorState();
}

class _ConditionEditorState extends State<_ConditionEditor> {
  late final TextEditingController _name =
      TextEditingController(text: widget.existing?.name ?? '');
  late final TextEditingController _diagnosedOn =
      TextEditingController(text: widget.existing?.diagnosedOn ?? '');
  late final TextEditingController _note =
      TextEditingController(text: widget.existing?.note ?? '');
  late String _status = widget.existing?.status ?? 'unknown';
  String? _error;

  @override
  void dispose() {
    _name.dispose();
    _diagnosedOn.dispose();
    _note.dispose();
    super.dispose();
  }

  void _submit() {
    final name = _name.text.trim();
    if (name.isEmpty) {
      setState(() => _error = widget.strings.nameRequired);
      return;
    }
    final diagnosed = _diagnosedOn.text.trim();
    Navigator.of(context).pop(
      PhrCondition(
        id: widget.existing?.id ?? _newEntryId('c'),
        name: name,
        status: _status,
        diagnosedOn: diagnosed.isEmpty ? null : diagnosed,
        note: _note.text.trim(),
        informationSource:
            widget.existing?.informationSource ?? 'self-declared',
        verificationStatus:
            widget.existing?.verificationStatus ?? 'unconfirmed',
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.strings;
    return _EditorScaffold(
      title: s.sectionConditions,
      doneLabel: s.done,
      cancelLabel: s.cancel,
      error: _error,
      onDone: _submit,
      children: [
        _EditorField(controller: _name, label: s.name),
        _Dropdown(
          label: s.clinicalStatus,
          value: _status,
          options: kConditionStatuses,
          labelFor: s.statusLabel,
          onChanged: (v) => setState(() => _status = v),
        ),
        _EditorField(
            controller: _diagnosedOn, label: s.diagnosedOn, hint: 'YYYY-MM-DD'),
        _EditorField(controller: _note, label: s.note, maxLines: 2),
      ],
    );
  }
}

class _MedicationEditor extends StatefulWidget {
  const _MedicationEditor({required this.strings, this.existing});

  final PhrStrings strings;
  final PhrMedication? existing;

  @override
  State<_MedicationEditor> createState() => _MedicationEditorState();
}

class _MedicationEditorState extends State<_MedicationEditor> {
  late final TextEditingController _name =
      TextEditingController(text: widget.existing?.name ?? '');
  late final TextEditingController _dose =
      TextEditingController(text: widget.existing?.dose ?? '');
  late final TextEditingController _frequency =
      TextEditingController(text: widget.existing?.frequency ?? '');
  late final TextEditingController _startedOn =
      TextEditingController(text: widget.existing?.startedOn ?? '');
  late final TextEditingController _note =
      TextEditingController(text: widget.existing?.note ?? '');
  late bool _isCurrent = widget.existing?.isCurrent ?? true;
  String? _error;

  @override
  void dispose() {
    _name.dispose();
    _dose.dispose();
    _frequency.dispose();
    _startedOn.dispose();
    _note.dispose();
    super.dispose();
  }

  void _submit() {
    final name = _name.text.trim();
    if (name.isEmpty) {
      setState(() => _error = widget.strings.nameRequired);
      return;
    }
    final started = _startedOn.text.trim();
    Navigator.of(context).pop(
      PhrMedication(
        id: widget.existing?.id ?? _newEntryId('m'),
        name: name,
        dose: _dose.text.trim(),
        frequency: _frequency.text.trim(),
        startedOn: started.isEmpty ? null : started,
        isCurrent: _isCurrent,
        note: _note.text.trim(),
        informationSource:
            widget.existing?.informationSource ?? 'self-declared',
        verificationStatus:
            widget.existing?.verificationStatus ?? 'unconfirmed',
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.strings;
    return _EditorScaffold(
      title: s.sectionMedications,
      doneLabel: s.done,
      cancelLabel: s.cancel,
      error: _error,
      onDone: _submit,
      children: [
        _EditorField(controller: _name, label: s.name),
        _EditorField(controller: _dose, label: s.dose),
        _EditorField(controller: _frequency, label: s.frequency),
        _EditorField(
            controller: _startedOn, label: s.startedOn, hint: 'YYYY-MM-DD'),
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: Text(s.isCurrent),
          value: _isCurrent,
          onChanged: (v) => setState(() => _isCurrent = v),
        ),
        _EditorField(controller: _note, label: s.note, maxLines: 2),
      ],
    );
  }
}

/// Shared editor bottom-sheet chrome: title, scrollable body, error, actions.
class _EditorScaffold extends StatelessWidget {
  const _EditorScaffold({
    required this.title,
    required this.doneLabel,
    required this.cancelLabel,
    required this.onDone,
    required this.children,
    this.error,
  });

  final String title;
  final String doneLabel;
  final String cancelLabel;
  final VoidCallback onDone;
  final List<Widget> children;
  final String? error;

  @override
  Widget build(BuildContext context) {
    final bottomInset = MediaQuery.of(context).viewInsets.bottom;
    return Padding(
      padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + bottomInset),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 12),
            ...children,
            if (error != null)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(
                  error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: Text(cancelLabel),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child:
                      FilledButton(onPressed: onDone, child: Text(doneLabel)),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _EditorField extends StatelessWidget {
  const _EditorField({
    required this.controller,
    required this.label,
    this.hint,
    this.maxLines = 1,
  });

  final TextEditingController controller;
  final String label;
  final String? hint;
  final int maxLines;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: TextField(
        controller: controller,
        maxLines: maxLines,
        decoration: InputDecoration(
          labelText: label,
          hintText: hint,
          border: const OutlineInputBorder(),
          isDense: true,
        ),
      ),
    );
  }
}

class _Dropdown extends StatelessWidget {
  const _Dropdown({
    required this.label,
    required this.value,
    required this.options,
    required this.labelFor,
    required this.onChanged,
  });

  final String label;
  final String value;
  final List<String> options;
  final String Function(String) labelFor;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: DropdownButtonFormField<String>(
        initialValue: value,
        decoration: InputDecoration(
          labelText: label,
          border: const OutlineInputBorder(),
          isDense: true,
        ),
        items: options
            .map((o) =>
                DropdownMenuItem<String>(value: o, child: Text(labelFor(o))))
            .toList(),
        onChanged: (v) {
          if (v != null) onChanged(v);
        },
      ),
    );
  }
}

// =============================================================================
// Flag-gated read-only surfaces (phr_enhanced_mobile_enabled) — Requirement 5.6
// =============================================================================

/// Read-only export view: renders the loaded record serialized to pretty JSON
/// in a selectable, copyable text block. This is a client-side projection of
/// the already-loaded record — it performs no network call and cannot mutate
/// the record. The persistent self-declared disclaimer remains present.
class _PhrExportView extends StatelessWidget {
  const _PhrExportView({required this.strings, required this.record});

  final PhrStrings strings;
  final PhrRecordModel record;

  @override
  Widget build(BuildContext context) {
    final s = strings;
    final pretty = const JsonEncoder.withIndent('  ').convert(record.toJson());
    return Scaffold(
      appBar: AppBar(title: Text(s.exportTitle)),
      body: ListView(
        key: const Key('phr-export-view'),
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
        children: [
          PhrDisclaimerBanner(text: s.disclaimer),
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: SelectableText(
                pretty,
                key: const Key('phr-export-json'),
                style: const TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 12,
                  height: 1.4,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Read-only emergency-card view rendering the [PhrEmergencyCardProjection]
/// (allergies, current medications, conditions, blood type, emergency contact),
/// mirroring the web emergency-card field shape (Requirement 5.6). All status
/// is conveyed by text labels (not color alone). The persistent self-declared
/// disclaimer remains present.
class _PhrEmergencyCardView extends StatelessWidget {
  const _PhrEmergencyCardView({required this.strings, required this.card});

  final PhrStrings strings;
  final PhrEmergencyCardProjection card;

  @override
  Widget build(BuildContext context) {
    final s = strings;
    return Scaffold(
      appBar: AppBar(title: Text(s.emergencyCardTitle)),
      body: ListView(
        key: const Key('phr-emergency-card-view'),
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
        children: [
          PhrDisclaimerBanner(text: s.disclaimer),
          const SizedBox(height: 16),
          if (card.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Text(s.emergencyEmpty),
            )
          else ...[
            _EmergencyBlock(
              title: s.bloodType,
              children: [
                Text(card.bloodType.trim().isEmpty
                    ? s.bloodTypeUnknown
                    : card.bloodType),
              ],
            ),
            _EmergencyBlock(
              title: s.sectionAllergies,
              children: card.allergies.isEmpty
                  ? [Text(s.emptySection)]
                  : card.allergies
                      .map((a) => Text(
                            [
                              a.name,
                              s.severityLabel(a.severity),
                              if (a.reaction.trim().isNotEmpty) a.reaction,
                            ].where((e) => e.trim().isNotEmpty).join(' • '),
                          ))
                      .toList(),
            ),
            _EmergencyBlock(
              title: s.sectionMedications,
              children: card.currentMedications.isEmpty
                  ? [Text(s.emptySection)]
                  : card.currentMedications
                      .map((m) => Text(
                            [
                              m.name,
                              if (m.dose.trim().isNotEmpty) m.dose,
                            ].where((e) => e.trim().isNotEmpty).join(' • '),
                          ))
                      .toList(),
            ),
            _EmergencyBlock(
              title: s.sectionConditions,
              children: card.conditions.isEmpty
                  ? [Text(s.emptySection)]
                  : card.conditions
                      .map((c) => Text(
                            '${c.name} • ${s.statusLabel(c.status)}',
                          ))
                      .toList(),
            ),
            _EmergencyBlock(
              title: s.emergencyContactName,
              children: [
                if (card.emergencyContactName.trim().isEmpty &&
                    card.emergencyContactPhone.trim().isEmpty)
                  Text(s.noEmergencyContact)
                else ...[
                  if (card.emergencyContactName.trim().isNotEmpty)
                    Text(card.emergencyContactName),
                  if (card.emergencyContactPhone.trim().isNotEmpty)
                    Text(card.emergencyContactPhone),
                ],
              ],
            ),
          ],
        ],
      ),
    );
  }
}

/// A titled block of read-only emergency-card lines.
class _EmergencyBlock extends StatelessWidget {
  const _EmergencyBlock({required this.title, required this.children});

  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 6),
            ...children,
          ],
        ),
      ),
    );
  }
}
