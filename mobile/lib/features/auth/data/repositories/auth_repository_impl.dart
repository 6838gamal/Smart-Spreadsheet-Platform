import 'package:crypto/crypto.dart';
import 'package:dartz/dartz.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:local_auth/local_auth.dart';
import 'dart:convert';

import '../../../../core/constants/storage_keys.dart';
import '../../../../core/error/exceptions.dart';
import '../../../../core/error/failures.dart';
import '../../../../core/services/remote_config_service.dart';
import '../../../../core/storage/secure_storage.dart';
import '../../domain/entities/user_entity.dart';
import '../../domain/repositories/auth_repository.dart';
import '../datasources/auth_remote_datasource.dart';

// ── Google Sign-In instance (v6 constructor API) ────────────────────────────
// Client ID is resolved at call time from RemoteConfigService (runtime fetch
// from backend) with a compile-time --dart-define=GOOGLE_CLIENT_ID=... fallback.
GoogleSignIn _buildGoogleSignIn() {
  final clientId = RemoteConfigService.googleClientId;
  return GoogleSignIn(
    clientId: clientId.isNotEmpty ? clientId : null,
    scopes: ['email', 'profile'],
  );
}

class AuthRepositoryImpl implements AuthRepository {
  final AuthRemoteDataSource remote;
  final LocalAuthentication localAuth;

  const AuthRepositoryImpl({
    required this.remote,
    required this.localAuth,
  });

  // ── Google Sign-In (v6 constructor API) ─────────────────────────────────────

  @override
  Future<Either<Failure, UserEntity>> loginWithGoogle() async {
    try {
      final googleSignIn = _buildGoogleSignIn();
      // Sign out first so the account picker always appears
      await googleSignIn.signOut();
      final googleUser = await googleSignIn.signIn();
      if (googleUser == null) {
        // User cancelled the picker
        return const Left(Failure.auth(message: 'تم إلغاء تسجيل الدخول عبر Google'));
      }
      final googleAuth = await googleUser.authentication;
      // On web, prefer idToken; fall back to accessToken
      final idToken     = googleAuth.idToken;
      final accessToken = googleAuth.accessToken;
      final token = idToken ?? accessToken;
      if (token == null) {
        return const Left(Failure.auth(message: 'تعذّر الحصول على رمز Google'));
      }
      final model = await remote.loginWithGoogleIdToken(token);
      return Right(model.toEntity());
    } on AuthException catch (e) {
      return Left(Failure.auth(message: e.message));
    } on NetworkException catch (e) {
      return Left(Failure.network(message: e.message, statusCode: e.statusCode));
    } on ServerException catch (e) {
      return Left(Failure.server(message: e.message, statusCode: e.statusCode));
    } catch (e) {
      return Left(Failure.unknown(message: e.toString()));
    }
  }

  // ── Email / password ────────────────────────────────────────────────────────

  @override
  Future<Either<Failure, UserEntity>> login({
    required String email,
    required String password,
  }) async {
    try {
      final model = await remote.login(email: email, password: password);
      return Right(model.toEntity());
    } on AuthException catch (e) {
      return Left(Failure.auth(message: e.message, sessionExpired: e.sessionExpired));
    } on NetworkException catch (e) {
      return Left(Failure.network(message: e.message, statusCode: e.statusCode));
    } on ServerException catch (e) {
      return Left(Failure.server(message: e.message, statusCode: e.statusCode));
    } catch (e) {
      return Left(Failure.unknown(message: e.toString()));
    }
  }

  @override
  Future<Either<Failure, UserEntity>> register({
    required String email,
    required String username,
    required String password,
  }) async {
    try {
      final model = await remote.register(
          email: email, username: username, password: password);
      return Right(model.toEntity());
    } on AuthException catch (e) {
      return Left(Failure.auth(message: e.message));
    } on NetworkException catch (e) {
      return Left(Failure.network(message: e.message, statusCode: e.statusCode));
    } on ServerException catch (e) {
      return Left(Failure.server(message: e.message, statusCode: e.statusCode));
    } catch (e) {
      return Left(Failure.unknown(message: e.toString()));
    }
  }

  @override
  Future<Either<Failure, void>> logout() async {
    try {
      await remote.logout();
      await _buildGoogleSignIn().signOut();
      return const Right(null);
    } catch (_) {
      await SecureStorage.delete(StorageKeys.accessToken);
      return const Right(null);
    }
  }

  @override
  Future<Either<Failure, UserEntity>> getCurrentUser() async {
    try {
      final model = await remote.getCurrentUser();
      return Right(model.toEntity());
    } on AuthException catch (e) {
      return Left(Failure.auth(message: e.message, sessionExpired: e.sessionExpired));
    } on NetworkException catch (e) {
      return Left(Failure.network(message: e.message, statusCode: e.statusCode));
    } catch (e) {
      return Left(Failure.unknown(message: e.toString()));
    }
  }

  // ── PIN & Biometric ─────────────────────────────────────────────────────────

  @override
  Future<Either<Failure, bool>> verifyPin(String pin) async {
    try {
      final stored = await SecureStorage.read(StorageKeys.pinHash);
      if (stored == null) return const Right(false);
      final hash = sha256.convert(utf8.encode(pin)).toString();
      return Right(hash == stored);
    } catch (e) {
      return Left(Failure.cache(message: e.toString()));
    }
  }

  @override
  Future<Either<Failure, void>> setPin(String pin) async {
    try {
      final hash = sha256.convert(utf8.encode(pin)).toString();
      await SecureStorage.write(StorageKeys.pinHash, hash);
      return const Right(null);
    } catch (e) {
      return Left(Failure.cache(message: e.toString()));
    }
  }

  @override
  Future<Either<Failure, bool>> checkBiometricAvailability() async {
    try {
      return Right(await localAuth.canCheckBiometrics);
    } catch (e) {
      return Left(Failure.unknown(message: e.toString()));
    }
  }

  @override
  Future<Either<Failure, bool>> authenticateWithBiometric() async {
    try {
      final ok = await localAuth.authenticate(
        localizedReason: 'Verify your identity',
        options: const AuthenticationOptions(biometricOnly: true),
      );
      return Right(ok);
    } catch (e) {
      return Left(Failure.unknown(message: e.toString()));
    }
  }
}
