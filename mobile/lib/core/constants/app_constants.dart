/// Central place for all application-wide constants.
/// Keeping them here avoids magic strings scattered across the codebase.
class AppConstants {
  AppConstants._();

  // ── App meta ────────────────────────────────────────────────────────────────
  static const String appName = 'Smart Spreadsheet';
  static const String appVersion = '1.0.0';

  // ── API ─────────────────────────────────────────────────────────────────────
  /// Override this at runtime (e.g. from env config) for staging/prod.
  static const String defaultApiBaseUrl = 'https://your-replit-domain.replit.dev/api/v1';

  static const Duration connectTimeout = Duration(seconds: 30);
  static const Duration receiveTimeout = Duration(seconds: 60);
  static const Duration sendTimeout = Duration(seconds: 120);

  // ── Pagination ───────────────────────────────────────────────────────────────
  static const int defaultPageSize = 20;

  // ── Auth ─────────────────────────────────────────────────────────────────────
  static const Duration tokenExpiry = Duration(hours: 24);
  static const Duration autoLogoutIdle = Duration(minutes: 15);
  static const int pinLength = 6;

  // ── Files ────────────────────────────────────────────────────────────────────
  static const int maxFileSizeMb = 500;
  static const List<String> supportedExtensions = [
    'pdf', 'xlsx', 'xls', 'xlsb', 'xlsm',
    'csv', 'docx', 'doc', 'pptx', 'ppt',
    'odt', 'ods', 'odp',
    'jpg', 'jpeg', 'png', 'tiff', 'bmp', 'webp',
    'txt',
  ];

  // ── Cache ─────────────────────────────────────────────────────────────────────
  static const Duration cacheExpiry = Duration(hours: 1);

  // ── Hive box names ────────────────────────────────────────────────────────────
  static const String settingsBox = 'settings';
  static const String filesBox = 'files';
  static const String offlineQueueBox = 'offline_queue';
  static const String analyticsBox = 'analytics';
}
