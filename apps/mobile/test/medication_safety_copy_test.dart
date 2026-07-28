import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  final source =
      File('lib/experience/unified/medicines_hub.dart').readAsStringSync();

  test('ending a course is explicitly record-keeping, not stop advice', () {
    expect(source, contains('chỉ cập nhật hồ sơ của bạn'));
    expect(source, contains('không phải khuyến nghị dừng thuốc'));
    expect(source, contains('Không tự ý ngừng thuốc'));
  });

  test('the unified hub keeps the DrugBank check in the safety workflow', () {
    expect(source, contains('Việc kiểm tra tương tác thuốc (DDI)'));
    expect(source, contains('không thay thế bác sĩ'));
  });
}
