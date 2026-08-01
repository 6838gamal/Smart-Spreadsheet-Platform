import 'package:freezed_annotation/freezed_annotation.dart';

part 'failures.freezed.dart';

/// Sealed class hierarchy for domain-level failures.
/// Using freezed gives us exhaustive pattern matching in the presentation layer.
@freezed
class Failure with _$Failure {
  /// Network / HTTP errors
  const factory Failure.network({
    required String message,
    int? statusCode,
  }) = NetworkFailure;

  /// Authentication / authorization errors
  const factory Failure.auth({
    required String message,
    @Default(false) bool sessionExpired,
  }) = AuthFailure;

  /// Server-side errors (5xx)
  const factory Failure.server({
    required String message,
    int? statusCode,
  }) = ServerFailure;

  /// Local cache / storage errors
  const factory Failure.cache({required String message}) = CacheFailure;

  /// File-related errors (too large, unsupported format, etc.)
  const factory Failure.file({required String message}) = FileFailure;

  /// Generic / unexpected errors
  const factory Failure.unknown({required String message}) = UnknownFailure;
}

extension FailureMessage on Failure {
  String get userMessage => when(
        network: (msg, _) => msg,
        auth: (msg, _) => msg,
        server: (msg, _) => msg,
        cache: (msg) => msg,
        file: (msg) => msg,
        unknown: (msg) => msg,
      );
}
