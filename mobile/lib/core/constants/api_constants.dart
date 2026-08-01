/// API endpoint path constants — combined with the base URL in DioClient.
class ApiConstants {
  ApiConstants._();

  // ── Auth ──────────────────────────────────────────────────────────────────────
  static const String login = '/auth/login';
  static const String register = '/auth/register';
  static const String logout = '/auth/logout';
  static const String me = '/auth/me';

  // ── Files ─────────────────────────────────────────────────────────────────────
  static const String files = '/files/';
  static String fileById(int id) => '/files/$id';
  static String fileDownload(int id) => '/files/$id/download';
  static const String fileUpload = '/files/upload';

  // ── Conversion ────────────────────────────────────────────────────────────────
  static const String convert = '/conversion/convert';
  static String conversionStatus(String jobId) => '/conversion/status/$jobId';
  static String conversionDownload(String jobId) => '/conversion/download/$jobId';

  // ── Analysis / AI ─────────────────────────────────────────────────────────────
  static const String aiChat = '/ai/chat';
  static const String aiAnalyze = '/ai/analyze';
  static String fileAnalyses(int fileId) => '/ai/analyses/$fileId';

  // ── Search ────────────────────────────────────────────────────────────────────
  static const String search = '/search/';

  // ── User ──────────────────────────────────────────────────────────────────────
  static const String updateProfile = '/users/me';
  static const String changePassword = '/users/me/password';
  static const String userDevices = '/users/me/devices';
  static String revokeDevice(int deviceId) => '/users/me/devices/$deviceId';

  // ── Subscription ──────────────────────────────────────────────────────────────
  static const String subscription = '/subscription/';
  static const String plans = '/subscription/plans';
}
