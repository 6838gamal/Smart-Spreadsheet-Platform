import 'package:dartz/dartz.dart';
import 'package:equatable/equatable.dart';

import '../../../../core/error/failures.dart';
import '../entities/user_entity.dart';
import '../repositories/auth_repository.dart';

/// Single-responsibility use case: validate inputs, delegate to repository.
/// Having this separate from the provider makes it independently testable.
class LoginUseCase {
  final AuthRepository _repository;
  const LoginUseCase(this._repository);

  Future<Either<Failure, UserEntity>> call(LoginParams params) async {
    if (params.email.isEmpty || !params.email.contains('@')) {
      return Left(
          const Failure.auth(message: 'يرجى إدخال بريد إلكتروني صحيح'));
    }
    if (params.password.length < 6) {
      return Left(const Failure.auth(
          message: 'كلمة المرور يجب أن تكون 6 أحرف على الأقل'));
    }
    return _repository.login(
        email: params.email, password: params.password);
  }
}

class LoginParams extends Equatable {
  final String email;
  final String password;
  const LoginParams({required this.email, required this.password});

  @override
  List<Object> get props => [email, password];
}
