import 'package:clara_mobile/core/lifemap_client_contract.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('wire vocabulary is stable and unknown state fails to unavailable', () {
    expect(
      LifeMapClientState.values.map((state) => state.wireValue),
      <String>[
        'draft',
        'awaiting_review',
        'confirmed',
        'disputed',
        'stale',
        'unavailable',
        'offline',
      ],
    );
    expect(
      LifeMapClientState.parse('confirmed').truthAuthority,
      isTrue,
    );
    expect(
      LifeMapClientState.parse('future-unknown-state'),
      LifeMapClientState.unavailable,
    );
  });

  test('capability defaults closed and preserves online-only policy', () {
    expect(LifeMapCapability.fromJson(null).enabled, isFalse);
    final capability = LifeMapCapability.fromJson(<String, Object>{
      'enabled': true,
      'mutation_policy': 'online_only',
    });
    expect(capability.enabled, isTrue);
    expect(capability.onlineOnly, isTrue);
  });
}
