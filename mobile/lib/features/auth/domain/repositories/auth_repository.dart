import 'package:dartz/dartz.dart';

import '../../../../core/error/failures.dart';
import '../entities/user_entity.dart';

/// Abstract contract — the data layer implements this, the domain uses it.
/// Returning `Either<Failure, T>` forces callers to handle errors explicitly.
abstract class AuthRepository {
  Future<Either<Failure, UserEntity>> login({
    required String email,
    required String password,
  });

  Future<Either<Failure, UserEntity>> loginWithGoogle();

  Future<Either<Failure, UserEntity>> register({
    required String email,
    required String username,
    required String password,
  });

  Future<Either<Failure, void>> logout();

  Future<Either<Failure, UserEntity>> getCurrentUser();

  Future<Either<Failure, bool>> verifyPin(String pin);

  Future<Either<Failure, void>> setPin(String pin);

  Future<Either<Failure, bool>> checkBiometricAvailability();

  Future<Either<Failure, bool>> authenticateWithBiometric();
}
