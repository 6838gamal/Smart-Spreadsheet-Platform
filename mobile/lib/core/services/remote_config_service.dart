import 'dart:convert';
import 'package:http/http.dart' as http;

import '../constants/app_constants.dart';
import '../constants/storage_keys.dart';
import '../storage/hive_storage.dart';

/// Fetches public configuration from the backend at runtime.
/// This lets secrets like GOOGLE_CLIENT_ID be set as server env vars
/// without needing a rebuild of the Flutter app.
class RemoteConfigService {
  RemoteConfigService._();

  static String _googleClientId = AppConstants.googleClientId; // compile-time fallback
  static bool _googleEnabled = AppConstants.googleClientId.isNotEmpty;

  static String get googleClientId => _googleClientId;
  static bool get googleEnabled => _googleEnabled;

  /// Fetch `/api/v1/config/public` from the backend and cache the result.
  /// Silently falls back to compile-time constants on any error.
  static Future<void> fetch() async {
    try {
      final baseUrl = HiveStorage.get<String>(StorageKeys.apiBaseUrl) ??
          AppConstants.defaultApiBaseUrl;

      // Strip /api/v1 suffix to get the root URL, then call /api/v1/config/public
      final root = baseUrl.replaceAll(RegExp(r'/api/v\d+/?$'), '');
      final uri = Uri.parse('$root/api/v1/config/public');

      final response = await http
          .get(uri, headers: {'Accept': 'application/json'})
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = json.decode(response.body) as Map<String, dynamic>;
        final id = (data['google_client_id'] as String? ?? '').trim();
        final enabled = data['google_enabled'] as bool? ?? id.isNotEmpty;
        if (id.isNotEmpty) {
          _googleClientId = id;
          _googleEnabled = enabled;
        }
      }
    } catch (_) {
      // Network unavailable or backend down — use compile-time fallback.
    }
  }
}
