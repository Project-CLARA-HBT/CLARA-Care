// Models for FHIR R4 interoperability, conformance, and export (Phase PH11).
//
// These data models represent HL7 FHIR R4 resources and metadata exchanged
// between the CLARA mobile client and the CLARA API gateway.

import 'dart:convert';

/// Represents the machine-readable FHIR R4 capability statement returned by
/// `GET /api/v1/lifemap/v2/fhir/conformance`.
class FhirConformanceStatement {
  const FhirConformanceStatement({
    required this.name,
    required this.fhirVersion,
    required this.mappingVersion,
    required this.conformance,
    required this.bundleTypes,
    required this.exportEnabled,
    required this.exportPath,
    required this.importEnabled,
    required this.importPath,
    required this.ipsPackageCandidate,
    required this.isGeneralFhirServer,
  });

  factory FhirConformanceStatement.fromJson(Map<String, dynamic> json) {
    final operations = json['operations'] as Map<String, dynamic>? ?? const {};
    final exportOp = operations['export'] as Map<String, dynamic>? ?? const {};
    final importOp = operations['import'] as Map<String, dynamic>? ?? const {};
    final ipsOp = operations['ips_export'] as Map<String, dynamic>? ?? const {};

    final rawBundleTypes = json['bundle_types'];
    final bundleTypes = rawBundleTypes is List
        ? rawBundleTypes.map((e) => e.toString()).toList()
        : <String>[];

    return FhirConformanceStatement(
      name: json['name']?.toString() ?? 'CLARA LifeMap FHIR R4 projection',
      fhirVersion: json['fhir_version']?.toString() ?? '4.0.1',
      mappingVersion: json['mapping_version']?.toString() ?? '1.0',
      conformance: json['conformance']?.toString() ?? 'fhir-r4-summary-not-ips',
      bundleTypes: bundleTypes,
      exportEnabled: exportOp['enabled'] == true,
      exportPath: exportOp['path']?.toString() ?? '/api/v1/lifemap/v2/export/fhir-r4',
      importEnabled: importOp['enabled'] == true,
      importPath: importOp['path']?.toString() ?? '/api/v1/lifemap/v2/import/fhir-r4',
      ipsPackageCandidate: ipsOp['package_candidate']?.toString() ?? 'hl7.fhir.uv.ips#2.0.1',
      isGeneralFhirServer: json['general_fhir_server'] == true,
    );
  }

  final String name;
  final String fhirVersion;
  final String mappingVersion;
  final String conformance;
  final List<String> bundleTypes;
  final bool exportEnabled;
  final String exportPath;
  final bool importEnabled;
  final String importPath;
  final String ipsPackageCandidate;
  final bool isGeneralFhirServer;
}

/// Permitted purposes of use for consented health data export under GDPR/HIPAA/PDPD.
enum FhirExportPurpose {
  selfDownload('self_download', 'Tự lưu trữ cá nhân', 'Personal Record Archive'),
  clinicalConsult('clinical_consult', 'Hội chẩn / Tư vấn bác sĩ', 'Clinical Consultation'),
  secondOpinion('second_opinion', 'Ý kiến y khoa độc lập', 'Second Medical Opinion'),
  recordTransfer('record_transfer', 'Chuyển viện / Hồ sơ liên thông', 'Health Record Transfer');

  const FhirExportPurpose(this.wireValue, this.vietnameseLabel, this.englishLabel);

  final String wireValue;
  final String vietnameseLabel;
  final String englishLabel;

  String localized(String? locale) {
    return (locale == 'en') ? englishLabel : vietnameseLabel;
  }
}

/// Standard HL7 FHIR R4 resource types selectable for data minimization.
enum FhirResourceType {
  patient('Patient', 'Thông tin bệnh nhân', 'Patient Demographics'),
  condition('Condition', 'Chẩn đoán & Vấn đề sức khỏe', 'Conditions & Diagnoses'),
  observation('Observation', 'Chỉ số sinh tồn & Xét nghiệm', 'Observations & Vitals'),
  medicationStatement('MedicationStatement', 'Đơn thuốc & Phác đồ điều trị', 'Medication Statements'),
  allergyIntolerance('AllergyIntolerance', 'Dị ứng & Cảnh báo phản ứng', 'Allergies & Intolerances'),
  encounter('Encounter', 'Lần khám & Tiếp xúc y tế', 'Clinical Encounters'),
  documentReference('DocumentReference', 'Tài liệu & Hồ sơ đính kèm', 'Document References');

  const FhirResourceType(this.resourceName, this.vietnameseLabel, this.englishLabel);

  final String resourceName;
  final String vietnameseLabel;
  final String englishLabel;

  String localized(String? locale) {
    return (locale == 'en') ? englishLabel : vietnameseLabel;
  }
}

/// Summary of an exported FHIR R4 Bundle.
class FhirExportResult {
  const FhirExportResult({
    required this.bundleId,
    required this.bundleType,
    required this.totalEntries,
    required this.resourceBreakdown,
    required this.rawJson,
    required this.exportedAt,
    required this.purpose,
  });

  factory FhirExportResult.fromBundleJson(Map<String, dynamic> json, String purpose) {
    final bundleId = json['id']?.toString() ?? 'unknown-id';
    final bundleType = json['type']?.toString() ?? 'collection';
    final entries = json['entry'] as List? ?? const [];

    final breakdown = <String, int>{};
    for (final item in entries) {
      if (item is Map) {
        final resource = item['resource'];
        if (resource is Map) {
          final resType = resource['resourceType']?.toString() ?? 'Unknown';
          breakdown.update(resType, (val) => val + 1, ifAbsent: () => 1);
        }
      }
    }

    final encoder = JsonEncoder.withIndent('  ');
    final formattedJson = encoder.convert(json);

    return FhirExportResult(
      bundleId: bundleId,
      bundleType: bundleType,
      totalEntries: entries.length,
      resourceBreakdown: breakdown,
      rawJson: formattedJson,
      exportedAt: DateTime.now(),
      purpose: purpose,
    );
  }

  final String bundleId;
  final String bundleType;
  final int totalEntries;
  final Map<String, int> resourceBreakdown;
  final String rawJson;
  final DateTime exportedAt;
  final String purpose;
}

/// Model representing a connected health data source connector for sync operations.
class ConnectorSyncItem {
  const ConnectorSyncItem({
    required this.id,
    required this.provider,
    required this.displayLabel,
    required this.status,
    required this.lastSyncedAt,
    required this.dataTypes,
  });

  factory ConnectorSyncItem.fromJson(Map<String, dynamic> json) {
    final rawTypes = json['data_types'];
    final dataTypes = rawTypes is List
        ? rawTypes.map((e) => e.toString()).toList()
        : <String>[];

    return ConnectorSyncItem(
      id: json['id']?.toString() ?? '',
      provider: json['provider']?.toString() ?? 'generic',
      displayLabel: json['display_label']?.toString() ?? 'Thiết bị sức khỏe',
      status: json['status']?.toString() ?? 'disconnected',
      lastSyncedAt: json['last_synced_at']?.toString(),
      dataTypes: dataTypes,
    );
  }

  final String id;
  final String provider;
  final String displayLabel;
  final String status;
  final String? lastSyncedAt;
  final List<String> dataTypes;

  bool get isConnected => status == 'connected';
  bool get isPaused => status == 'paused';
}
