// Data-layer exceptions — converted to Failures at the repository boundary.
// We use typed exceptions so repositories can distinguish failure causes.

class NetworkException implements Exception {
  final String message;
  final int? statusCode;
  const NetworkException({required this.message, this.statusCode});

  @override
  String toString() => 'NetworkException($statusCode): $message';
}

class AuthException implements Exception {
  final String message;
  final bool sessionExpired;
  const AuthException({required this.message, this.sessionExpired = false});

  @override
  String toString() => 'AuthException: $message';
}

class ServerException implements Exception {
  final String message;
  final int? statusCode;
  const ServerException({required this.message, this.statusCode});

  @override
  String toString() => 'ServerException($statusCode): $message';
}

class CacheException implements Exception {
  final String message;
  const CacheException({required this.message});

  @override
  String toString() => 'CacheException: $message';
}

class FileException implements Exception {
  final String message;
  const FileException({required this.message});

  @override
  String toString() => 'FileException: $message';
}
