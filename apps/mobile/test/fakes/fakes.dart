// Barrel export of the reusable CLARA mobile test fakes (spec task 1.1).
//
// Import this single file from a test to pull in the fake `ApiClient`,
// `SessionStore` helpers, `ConnectivityService`, and the recording analytics
// transport:
//
//   import 'fakes/fakes.dart';
//
// All fakes avoid platform channels and live network access (Requirement 14.6).

export 'fake_api_client.dart';
export 'fake_connectivity_service.dart';
export 'fake_session_store.dart';
export 'recording_analytics_transport.dart';
