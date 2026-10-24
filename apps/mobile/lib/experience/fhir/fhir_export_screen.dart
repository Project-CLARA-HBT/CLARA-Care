// Screen for consented health record export in HL7 FHIR R4 format (Phase PH11).
//
// Safety-critical invariants:
//   * Consent Gate: Must obtain explicit user consent before releasing PHI.
//   * Purpose-bound: Export requires explicit declaration of purpose-of-use.
//   * Data minimization: Users can toggle resource categories.
//   * Audit logging: Every export action is logged server-side.
//   * No PHI leakage in telemetry or error banners.

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../core/api_client.dart';
import '../../core/session_store.dart';
import '../../theme/tokens.dart';
import '../language_controller.dart';
import 'fhir_models.dart';

class FhirExportScreen extends StatefulWidget {
  const FhirExportScreen({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    this.languageController,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;
  final LanguageController? languageController;

  @override
  State<FhirExportScreen> createState() => _FhirExportScreenState();
}

class _FhirExportScreenState extends State<FhirExportScreen> {
  FhirExportPurpose _selectedPurpose = FhirExportPurpose.selfDownload;
  bool _consentAgreed = false;
  final Set<FhirResourceType> _selectedResources = {
    FhirResourceType.patient,
    FhirResourceType.condition,
    FhirResourceType.observation,
    FhirResourceType.medicationStatement,
    FhirResourceType.allergyIntolerance,
    FhirResourceType.encounter,
    FhirResourceType.documentReference,
  };

  bool _isExporting = false;
  String? _errorMessage;
  FhirExportResult? _exportResult;
  bool _showRawJson = false;

  String? get _token => widget.sessionStore.accessToken;
  String get _locale => widget.languageController?.languageCode ?? 'vi';
  bool get _isEn => _locale == 'en';

  Future<void> _handleExport() async {
    final token = _token;
    if (token == null || token.isEmpty) {
      setState(() {
        _errorMessage = _isEn
            ? 'Authentication required. Please log in.'
            : 'Yêu cầu đăng nhập để xuất hồ sơ.';
      });
      return;
    }

    if (!_consentAgreed) {
      setState(() {
        _errorMessage = _isEn
            ? 'You must confirm consent before exporting health records.'
            : 'Vui lòng xác nhận đồng thuận trước khi xuất hồ sơ.';
      });
      return;
    }

    if (_selectedResources.isEmpty) {
      setState(() {
        _errorMessage = _isEn
            ? 'Please select at least one resource category.'
            : 'Vui lòng chọn ít nhất một danh mục dữ liệu.';
      });
      return;
    }

    setState(() {
      _isExporting = true;
      _errorMessage = null;
    });

    final includeString = _selectedResources
        .map((r) => r.resourceName)
        .join(',');

    try {
      final response = await widget.apiClient.exportFhirR4Summary(
        accessToken: token,
        purpose: _selectedPurpose.wireValue,
        include: includeString,
      );

      final result = FhirExportResult.fromBundleJson(
        response,
        _selectedPurpose.wireValue,
      );

      if (mounted) {
        setState(() {
          _exportResult = result;
          _isExporting = false;
        });
      }
    } on ApiException catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = e.message;
          _isExporting = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = _isEn
              ? 'An unexpected error occurred during export.'
              : 'Có lỗi xảy ra trong quá trình xuất hồ sơ.';
          _isExporting = false;
        });
      }
    }
  }

  void _copyToClipboard() {
    final result = _exportResult;
    if (result == null) return;
    Clipboard.setData(ClipboardData(text: result.rawJson));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          _isEn
              ? 'FHIR R4 JSON bundle copied to clipboard'
              : 'Đã sao chép gói FHIR R4 JSON vào bộ nhớ tạm',
        ),
        duration: const Duration(seconds: 2),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final title = _isEn
        ? 'Consented FHIR R4 Export'
        : 'Xuất hồ sơ chuẩn FHIR R4';

    return Scaffold(
      appBar: AppBar(
        title: Text(title),
        actions: [
          if (_exportResult != null)
            IconButton(
              icon: const Icon(Icons.copy_outlined),
              tooltip: _isEn ? 'Copy JSON' : 'Sao chép JSON',
              onPressed: _copyToClipboard,
            ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(ClaraTokens.spaceMd),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _buildIntroductionCard(),
            const SizedBox(height: ClaraTokens.spaceMd),
            _buildPurposeSelectionSection(),
            const SizedBox(height: ClaraTokens.spaceMd),
            _buildResourceSelectionSection(),
            const SizedBox(height: ClaraTokens.spaceMd),
            _buildConsentGateCard(),
            const SizedBox(height: ClaraTokens.spaceLg),
            if (_errorMessage != null) ...[
              _buildErrorBanner(_errorMessage!),
              const SizedBox(height: ClaraTokens.spaceMd),
            ],
            _buildExportActionButton(),
            if (_exportResult != null) ...[
              const SizedBox(height: ClaraTokens.spaceLg),
              _buildExportResultCard(_exportResult!),
            ],
            const SizedBox(height: ClaraTokens.spaceXl),
            _buildAuditNotice(),
          ],
        ),
      ),
    );
  }

  Widget _buildIntroductionCard() {
    return Card(
      elevation: 0,
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
      ),
      child: Padding(
        padding: const EdgeInsets.all(ClaraTokens.spaceMd),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(
              Icons.shield_outlined,
              color: Theme.of(context).colorScheme.primary,
              size: 28,
            ),
            const SizedBox(width: ClaraTokens.spaceSm),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _isEn
                        ? 'HL7 FHIR R4 Standardized Health Export'
                        : 'Xuất hồ sơ y tế chuẩn HL7 FHIR R4',
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: ClaraTokens.spaceXs),
                  Text(
                    _isEn
                        ? 'Export your personal health records into an interoperable HL7 FHIR R4 Collection Bundle. Protected by explicit consent, purpose binding, and audit lineage.'
                        : 'Xuất toàn bộ dữ liệu sức khỏe cá nhân theo gói HL7 FHIR R4 chuẩn hóa quốc tế. Quá trình xuất được bảo vệ nghiêm ngặt bằng đồng thuận y tế và nhật ký kiểm toán.',
                    style: TextStyle(
                      fontSize: 13,
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPurposeSelectionSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          _isEn ? '1. Purpose of Export' : '1. Mục đích xuất hồ sơ',
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: ClaraTokens.spaceXs),
        Text(
          _isEn
              ? 'Select the explicit purpose for which this medical record will be used (GDPR/PDPD principle):'
              : 'Chọn mục đích cụ thể sử dụng gói hồ sơ (nguyên tắc giới hạn mục đích PDPD/GDPR):',
          style: TextStyle(
            fontSize: 12,
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: ClaraTokens.spaceSm),
        Card(
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
            side: BorderSide(
              color: Theme.of(context).colorScheme.outlineVariant,
            ),
          ),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceSm),
            child: DropdownButtonHideUnderline(
              child: DropdownButton<FhirExportPurpose>(
                isExpanded: true,
                value: _selectedPurpose,
                key: const Key('fhir-export-purpose-dropdown'),
                items: FhirExportPurpose.values.map((purpose) {
                  return DropdownMenuItem<FhirExportPurpose>(
                    value: purpose,
                    child: Text(purpose.localized(_locale)),
                  );
                }).toList(),
                onChanged: (newPurpose) {
                  if (newPurpose != null) {
                    setState(() => _selectedPurpose = newPurpose);
                  }
                },
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildResourceSelectionSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Expanded(
              child: Text(
                _isEn ? '2. Data Minimization (Resources)' : '2. Danh mục tài nguyên (Giảm thiểu dữ liệu)',
                style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
              ),
            ),
            TextButton(
              onPressed: () {
                setState(() {
                  if (_selectedResources.length == FhirResourceType.values.length) {
                    _selectedResources.clear();
                  } else {
                    _selectedResources.addAll(FhirResourceType.values);
                  }
                });
              },
              child: Text(
                _selectedResources.length == FhirResourceType.values.length
                    ? (_isEn ? 'Deselect All' : 'Bỏ chọn hết')
                    : (_isEn ? 'Select All' : 'Chọn tất cả'),
                style: const TextStyle(fontSize: 12),
              ),
            ),
          ],
        ),
        Card(
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
            side: BorderSide(
              color: Theme.of(context).colorScheme.outlineVariant,
            ),
          ),
          child: Column(
            children: FhirResourceType.values.map((resource) {
              final isChecked = _selectedResources.contains(resource);
              return CheckboxListTile(
                value: isChecked,
                key: Key('fhir-resource-checkbox-${resource.resourceName}'),
                dense: true,
                title: Text(
                  '${resource.resourceName} (${resource.localized(_locale)})',
                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
                ),
                onChanged: (val) {
                  setState(() {
                    if (val == true) {
                      _selectedResources.add(resource);
                    } else {
                      _selectedResources.remove(resource);
                    }
                  });
                },
              );
            }).toList(),
          ),
        ),
      ],
    );
  }

  Widget _buildConsentGateCard() {
    final borderColor = _consentAgreed
        ? Theme.of(context).colorScheme.primary
        : Theme.of(context).colorScheme.error;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          _isEn ? '3. Medical Consent & Disclaimer' : '3. Xác nhận đồng thuận y tế (Bắt buộc)',
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: ClaraTokens.spaceSm),
        Container(
          decoration: BoxDecoration(
            color: _consentAgreed
                ? Theme.of(context).colorScheme.primaryContainer.withOpacity(0.2)
                : Theme.of(context).colorScheme.errorContainer.withOpacity(0.1),
            borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
            border: Border.all(color: borderColor, width: 1.5),
          ),
          padding: const EdgeInsets.all(ClaraTokens.spaceSm),
          child: Column(
            children: [
              CheckboxListTile(
                key: const Key('fhir-export-consent-checkbox'),
                value: _consentAgreed,
                onChanged: (bool? val) {
                  setState(() {
                    _consentAgreed = val ?? false;
                    if (_consentAgreed) {
                      _errorMessage = null;
                    }
                  });
                },
                title: Text(
                  _isEn
                      ? 'I explicitly confirm my informed consent to export my Protected Health Information (PHI) in HL7 FHIR R4 format for the declared purpose.'
                      : 'Tôi xác nhận đồng ý xuất thông tin sức khỏe cá nhân (PHI) theo chuẩn HL7 FHIR R4 cho mục đích đã chọn và tự chịu trách nhiệm lưu trữ an toàn.',
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                subtitle: Padding(
                  padding: const EdgeInsets.only(top: ClaraTokens.spaceXs),
                  child: Text(
                    _isEn
                        ? 'Notice: This export contains longitudinal clinical records. CLARA enforces strict access control; you are responsible for keeping downloaded bundles confidential.'
                        : 'Lưu ý: Bản sao này chứa dữ liệu bệnh án đầy đủ. Bạn cần bảo mật tệp xuất ra và không chia sẻ qua các kênh không mã hóa.',
                    style: TextStyle(
                      fontSize: 11,
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildErrorBanner(String error) {
    return Container(
      padding: const EdgeInsets.all(ClaraTokens.spaceSm),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.errorContainer,
        borderRadius: BorderRadius.circular(ClaraTokens.radiusSm),
      ),
      child: Row(
        children: [
          Icon(
            Icons.error_outline,
            color: Theme.of(context).colorScheme.error,
            size: 20,
          ),
          const SizedBox(width: ClaraTokens.spaceSm),
          Expanded(
            child: Text(
              error,
              style: TextStyle(
                color: Theme.of(context).colorScheme.onErrorContainer,
                fontSize: 13,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildExportActionButton() {
    return SizedBox(
      height: 48,
      child: FilledButton.icon(
        key: const Key('fhir-export-submit-button'),
        icon: _isExporting
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
              )
            : const Icon(Icons.download_for_offline_outlined),
        label: Text(
          _isExporting
              ? (_isEn ? 'Generating FHIR Bundle...' : 'Đang tạo gói FHIR R4...')
              : (_isEn ? 'Generate & Export FHIR R4 Bundle' : 'Tạo gói hồ sơ chuẩn FHIR R4'),
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        onPressed: (_isExporting || !_consentAgreed) ? null : _handleExport,
      ),
    );
  }

  Widget _buildExportResultCard(FhirExportResult result) {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
      ),
      child: Padding(
        padding: const EdgeInsets.all(ClaraTokens.spaceMd),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.check_circle_outline, color: Colors.green, size: 24),
                const SizedBox(width: ClaraTokens.spaceSm),
                Expanded(
                  child: Text(
                    _isEn ? 'FHIR R4 Bundle Exported Successfully' : 'Xuất gói FHIR R4 thành công',
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ),
            const Divider(height: ClaraTokens.spaceLg),
            Text(
              'Bundle ID: ${result.bundleId}',
              key: const Key('fhir-export-bundle-id'),
              style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
            ),
            const SizedBox(height: ClaraTokens.spaceXs),
            Text(
              'Type: ${result.bundleType} | Total Resources: ${result.totalEntries}',
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
            ),
            const SizedBox(height: ClaraTokens.spaceXs),
            Wrap(
              spacing: ClaraTokens.spaceXs,
              runSpacing: ClaraTokens.spaceXs,
              children: result.resourceBreakdown.entries.map((entry) {
                return Chip(
                  labelPadding: const EdgeInsets.symmetric(horizontal: 4),
                  visualDensity: VisualDensity.compact,
                  label: Text(
                    '${entry.key}: ${entry.value}',
                    style: const TextStyle(fontSize: 11),
                  ),
                );
              }).toList(),
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            Row(
              children: [
                OutlinedButton.icon(
                  icon: const Icon(Icons.copy_outlined, size: 16),
                  label: Text(_isEn ? 'Copy JSON' : 'Sao chép JSON'),
                  onPressed: _copyToClipboard,
                ),
                const SizedBox(width: ClaraTokens.spaceSm),
                TextButton.icon(
                  icon: Icon(
                    _showRawJson ? Icons.visibility_off_outlined : Icons.visibility_outlined,
                    size: 16,
                  ),
                  label: Text(
                    _showRawJson
                        ? (_isEn ? 'Hide JSON' : 'Ẩn xem trước')
                        : (_isEn ? 'Preview JSON' : 'Xem trước JSON'),
                  ),
                  onPressed: () {
                    setState(() => _showRawJson = !_showRawJson);
                  },
                ),
              ],
            ),
            if (_showRawJson) ...[
              const SizedBox(height: ClaraTokens.spaceSm),
              Container(
                key: const Key('fhir-export-json-preview'),
                height: 240,
                width: double.infinity,
                padding: const EdgeInsets.all(ClaraTokens.spaceSm),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(ClaraTokens.radiusSm),
                  border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
                ),
                child: SingleChildScrollView(
                  child: SelectableText(
                    result.rawJson,
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 11,
                    ),
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildAuditNotice() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Icon(
          Icons.verified_user_outlined,
          size: 14,
          color: Theme.of(context).colorScheme.onSurfaceVariant,
        ),
        const SizedBox(width: ClaraTokens.spaceXs),
        Flexible(
          child: Text(
            _isEn
                ? 'Audited by CLARA Lineage (entity=lifemap_fhir_r4, action=export)'
                : 'Được ghi nhận kiểm toán tự động bởi CLARA Lineage (entity=lifemap_fhir_r4)',
            style: TextStyle(
              fontSize: 11,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            textAlign: TextAlign.center,
          ),
        ),
      ],
    );
  }
}
