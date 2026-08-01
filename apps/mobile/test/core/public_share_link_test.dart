import 'package:clara_mobile/core/public_share_link.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('phrShareTokenFromLink', () {
    test('accepts canonical HTTPS public-share URLs and relative paths', () {
      expect(
        phrShareTokenFromLink(
          'https://theclaracare.com/phr/shared/opaque-token_123',
        ),
        'opaque-token_123',
      );
      expect(
        phrShareTokenFromLink('/phr/shared/opaque-token_123'),
        'opaque-token_123',
      );
    });

    test('rejects foreign, non-HTTPS and non-PHR-share links', () {
      expect(
        phrShareTokenFromLink('https://example.test/phr/shared/opaque-token'),
        isNull,
      );
      expect(
        phrShareTokenFromLink(
            'http://theclaracare.com/phr/shared/opaque-token'),
        isNull,
      );
      expect(
        phrShareTokenFromLink('https://theclaracare.com/share/opaque-token'),
        isNull,
      );
    });

    test('closing the viewer clears the in-memory public capability', () {
      final controller = PublicShareLinkController.withInitialLink(
        'https://theclaracare.com/phr/shared/opaque-token',
      );
      expect(controller.token, 'opaque-token');

      controller.clear();

      expect(controller.token, isNull);
    });
  });
}
