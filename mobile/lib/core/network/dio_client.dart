import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../constants/app_constants.dart';
import '../constants/storage_keys.dart';
import '../error/exceptions.dart';
import '../storage/hive_storage.dart';
import '../storage/secure_storage.dart';

/// Provider for the configured Dio HTTP client.
/// All features inject this instead of creating their own Dio instance,
/// ensuring auth headers and error handling are applied consistently.
final dioClientProvider = Provider<DioClient>((ref) {
  return DioClient(ref);
});

class DioClient {
  late final Dio _dio;
  final Ref _ref;

  DioClient(this._ref) {
    final baseUrl = HiveStorage.get<String>(StorageKeys.apiBaseUrl) ??
        AppConstants.defaultApiBaseUrl;

    _dio = Dio(BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: AppConstants.connectTimeout,
      receiveTimeout: AppConstants.receiveTimeout,
      sendTimeout: AppConstants.sendTimeout,
      headers: {'Content-Type': 'application/json'},
    ));

    _dio.interceptors.addAll([
      _AuthInterceptor(_ref),
      _ErrorInterceptor(),
      LogInterceptor(
        requestBody: false,
        responseBody: false,
        logPrint: (obj) => debugPrint('[DIO] $obj'),
      ),
    ]);
  }

  Dio get dio => _dio;

  // Convenience helpers so features don't import Dio directly.
  Future<Response<T>> get<T>(
    String path, {
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) =>
      _dio.get<T>(path,
          queryParameters: queryParameters, options: options);

  Future<Response<T>> post<T>(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) =>
      _dio.post<T>(path,
          data: data, queryParameters: queryParameters, options: options);

  Future<Response<T>> put<T>(
    String path, {
    dynamic data,
    Options? options,
  }) =>
      _dio.put<T>(path, data: data, options: options);

  Future<Response<T>> delete<T>(String path, {Options? options}) =>
      _dio.delete<T>(path, options: options);

  Future<Response<T>> postFormData<T>(
    String path,
    FormData formData, {
    ProgressCallback? onSendProgress,
    CancelToken? cancelToken,
  }) =>
      _dio.post<T>(
        path,
        data: formData,
        onSendProgress: onSendProgress,
        cancelToken: cancelToken,
        options: Options(contentType: 'multipart/form-data'),
      );
}

// ── Auth interceptor ──────────────────────────────────────────────────────────

class _AuthInterceptor extends Interceptor {
  final Ref _ref;
  _AuthInterceptor(this._ref);

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final token = await SecureStorage.read(StorageKeys.accessToken);
    if (token != null) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }
}

// ── Error interceptor — maps HTTP errors to typed exceptions ─────────────────

class _ErrorInterceptor extends Interceptor {
  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    final statusCode = err.response?.statusCode;
    final body = err.response?.data;
    final message = _extractMessage(body) ?? err.message ?? 'Unknown error';

    if (err.type == DioExceptionType.connectionTimeout ||
        err.type == DioExceptionType.receiveTimeout ||
        err.type == DioExceptionType.sendTimeout ||
        err.type == DioExceptionType.connectionError) {
      throw NetworkException(
          message: 'No internet connection or server unreachable');
    }

    if (statusCode == 401) {
      throw AuthException(message: message, sessionExpired: true);
    }

    if (statusCode != null && statusCode >= 500) {
      throw ServerException(message: message, statusCode: statusCode);
    }

    throw NetworkException(message: message, statusCode: statusCode);
  }

  String? _extractMessage(dynamic body) {
    if (body is Map) {
      return body['detail']?.toString() ??
          body['message']?.toString() ??
          body['error']?.toString();
    }
    return null;
  }
}

void debugPrint(String msg) {
  // ignore: avoid_print
  print(msg);
}
