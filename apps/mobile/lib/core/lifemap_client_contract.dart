/// Shared LifeMap state vocabulary. The API remains authoritative; this enum
/// prevents screen-specific aliases from changing the meaning of health state.
enum LifeMapClientState {
  draft('draft', 'Bản nháp', 'Draft', false),
  awaitingReview('awaiting_review', 'Chờ xem lại', 'Awaiting review', false),
  confirmed('confirmed', 'Đã xác nhận', 'Confirmed', true),
  disputed('disputed', 'Đang có tranh chấp', 'Disputed', false),
  stale('stale', 'Có thể đã cũ', 'May be stale', false),
  unavailable('unavailable', 'Không khả dụng', 'Unavailable', false),
  offline('offline', 'Ngoại tuyến', 'Offline', false);

  const LifeMapClientState(
    this.wireValue,
    this.viLabel,
    this.enLabel,
    this.truthAuthority,
  );

  final String wireValue;
  final String viLabel;
  final String enLabel;
  final bool truthAuthority;

  String label(String locale) =>
      locale.toLowerCase().startsWith('en') ? enLabel : viLabel;

  static LifeMapClientState parse(Object? value) {
    final wire = value?.toString();
    return LifeMapClientState.values.firstWhere(
      (state) => state.wireValue == wire,
      orElse: () => LifeMapClientState.unavailable,
    );
  }
}

class LifeMapCapability {
  const LifeMapCapability({
    required this.enabled,
    required this.onlineOnly,
  });

  factory LifeMapCapability.fromJson(Object? value) {
    if (value is! Map) {
      return const LifeMapCapability(enabled: false, onlineOnly: true);
    }
    return LifeMapCapability(
      enabled: value['enabled'] == true,
      onlineOnly: value['mutation_policy'] == 'online_only',
    );
  }

  final bool enabled;
  final bool onlineOnly;
}
