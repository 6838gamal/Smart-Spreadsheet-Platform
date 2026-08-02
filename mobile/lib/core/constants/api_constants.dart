/// API endpoint path constants — combined with the base URL in DioClient.
class ApiConstants {
  ApiConstants._();

  // ── Auth ──────────────────────────────────────────────────────────────────────
  static const String login = '/auth/login';
  static const String register = '/auth/register';
  static const String logout = '/auth/logout';
  static const String me = '/auth/me';
  static const String googleLogin = '/auth/google';

  // ── Files ─────────────────────────────────────────────────────────────────────
  static const String files = '/files/';
  static String fileById(int id) => '/files/$id';
  static String fileDownload(int id) => '/files/$id/download';
  static const String fileUpload = '/files/upload';

  // ── Conversion ────────────────────────────────────────────────────────────────
  static const String convert = '/converter/convert';
  static String conversionStatus(String jobId) => '/converter/status/$jobId';
  static String conversionDownload(String jobId) => '/converter/download/$jobId';
  static const String conversionDownloadBase = '/converter/download';

  // ── Admin ─────────────────────────────────────────────────────────────────────
  static const String adminUsers = '/admin/users';
  static String adminToggleUser(int id) => '/admin/users/$id/toggle-active';
  static String adminDeleteUser(int id) => '/admin/users/$id';

  // ── Analysis / AI ─────────────────────────────────────────────────────────────
  static const String aiChat = '/ai/chat';
  static const String aiAnalyze = '/ai/analyze';
  static String fileAnalyses(int fileId) => '/ai/analyses/$fileId';

  // ── Hugging Face ───────────────────────────────────────────────────────────────
  static const String hfModels = '/hf/models';
  static const String hfChat   = '/hf/chat';
  static const String hfAsk    = '/hf/ask';
  static const String hfSummarize = '/hf/summarize';

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
