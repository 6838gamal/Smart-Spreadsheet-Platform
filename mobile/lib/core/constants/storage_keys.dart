/// Keys used for flutter_secure_storage and Hive settings box.
/// Centralising them prevents typos and collisions.
class StorageKeys {
  StorageKeys._();

  // ── Secure storage (JWT, PIN hash) ───────────────────────────────────────────
  static const String accessToken = 'access_token';
  static const String refreshToken = 'refresh_token';
  static const String pinHash = 'pin_hash';
  static const String biometricEnabled = 'biometric_enabled';

  // ── Hive settings box ────────────────────────────────────────────────────────
  static const String themeMode = 'theme_mode';
  static const String locale = 'locale';
  static const String apiBaseUrl = 'api_base_url';
  static const String notificationsEnabled = 'notifications_enabled';
  static const String lastSync = 'last_sync';
  static const String userId = 'user_id';
  static const String userEmail = 'user_email';
  static const String userName = 'user_name';
}
