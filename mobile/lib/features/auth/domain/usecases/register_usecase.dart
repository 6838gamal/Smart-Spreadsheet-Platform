import 'package:dartz/dartz.dart';
import 'package:equatable/equatable.dart';

import '../../../../core/error/failures.dart';
import '../entities/user_entity.dart';
import '../repositories/auth_repository.dart';

class RegisterUseCase {
  final AuthRepository _repository;
  const RegisterUseCase(this._repository);

  Future<Either<Failure, UserEntity>> call(RegisterParams params) async {
    if (params.username.length < 3) {
      return const Left(Failure.auth(
          message: 'اسم المستخدم يجب أن يكون 3 أحرف على الأقل'));
    }
    if (!params.email.contains('@')) {
      return const Left(
          Failure.auth(message: 'يرجى إدخال بريد إلكتروني صحيح'));
    }
    if (params.password.length < 8) {
      return const Left(Failure.auth(
          message: 'كلمة المرور يجب أن تكون 8 أحرف على الأقل'));
    }
    if (params.password != params.confirmPassword) {
      return const Left(
          Failure.auth(message: 'كلمتا المرور غير متطابقتين'));
    }
    return _repository.register(
      email: params.email,
      username: params.username,
      password: params.password,
    );
  }
}

class RegisterParams extends Equatable {
  final String email;
  final String username;
  final String password;
  final String confirmPassword;

  const RegisterParams({
    required this.email,
    required this.username,
    required this.password,
    required this.confirmPassword,
  });

  @override
  List<Object> get props => [email, username, password, confirmPassword];
}
