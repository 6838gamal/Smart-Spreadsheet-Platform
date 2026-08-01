import 'package:crypto/crypto.dart';
import 'package:dartz/dartz.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:local_auth/local_auth.dart';
import 'dart:convert';

import '../../../../core/constants/storage_keys.dart';
import '../../../../core/error/exceptions.dart';
import '../../../../core/error/failures.dart';
import '../../../../core/storage/secure_storage.dart';
import '../../domain/entities/user_entity.dart';
import '../../domain/repositories/auth_repository.dart';
import '../datasources/auth_remote_datasource.dart';

class AuthRepositoryImpl implements AuthRepository {
  final AuthRemoteDataSource remote;
  final LocalAuthentication localAuth;

  const AuthRepositoryImpl({
    required this.remote,
    required this.localAuth,
  });

  // ── Google Sign-In (v7 singleton API) ───────────────────────────────────────

  @override
  Future<Either<Failure, UserEntity>> loginWithGoogle() async {
    try {
      // Sign out first so the account picker always appears
      await GoogleSignIn.instance.signOut();
      final account = await GoogleSignIn.instance.authenticate();
      final idToken = account.authentication.idToken;
      if (idToken == null) {
        return const Left(Failure.auth(message: 'تعذّر الحصول على رمز Google'));
      }
      final model = await remote.loginWithGoogleIdToken(idToken);
      return Right(model.toEntity());
    } on GoogleSignInException catch (e) {
      if (e.code == GoogleSignInExceptionCode.canceled) {
        return const Left(Failure.auth(message: 'تم إلغاء تسجيل الدخول عبر Google'));
      }
      return Left(Failure.auth(message: e.toString()));
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
      await GoogleSignIn.instance.signOut();
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
