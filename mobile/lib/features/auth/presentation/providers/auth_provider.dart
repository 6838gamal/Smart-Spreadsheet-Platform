import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:freezed_annotation/freezed_annotation.dart';
import 'package:local_auth/local_auth.dart';

import '../../../../core/constants/storage_keys.dart';
import '../../../../core/error/failures.dart';
import '../../../../core/storage/hive_storage.dart';
import '../../../../core/storage/secure_storage.dart';
import '../../data/datasources/auth_remote_datasource.dart';
import '../../data/repositories/auth_repository_impl.dart';
import '../../domain/entities/user_entity.dart';
import '../../domain/repositories/auth_repository.dart';
import '../../domain/usecases/login_usecase.dart';
import '../../domain/usecases/register_usecase.dart';
import '../../../../core/network/dio_client.dart';

part 'auth_provider.freezed.dart';

// ── Repository provider ───────────────────────────────────────────────────────

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  final client = ref.watch(dioClientProvider);
  return AuthRepositoryImpl(
    remote: AuthRemoteDataSourceImpl(client),
    localAuth: LocalAuthentication(),
  );
});

// ── Use case providers ────────────────────────────────────────────────────────

final loginUseCaseProvider = Provider<LoginUseCase>((ref) {
  return LoginUseCase(ref.watch(authRepositoryProvider));
});

final registerUseCaseProvider = Provider<RegisterUseCase>((ref) {
  return RegisterUseCase(ref.watch(authRepositoryProvider));
});

// ── Auth state ────────────────────────────────────────────────────────────────

@freezed
class AuthState with _$AuthState {
  const factory AuthState.initial() = _Initial;
  const factory AuthState.loading() = _Loading;
  const factory AuthState.authenticated({required UserEntity user}) =
      _Authenticated;
  const factory AuthState.unauthenticated() = _Unauthenticated;
  const factory AuthState.error({required String message}) = _Error;
}

extension AuthStateX on AuthState {
  bool get isAuthenticated => this is _Authenticated;
  bool get isLoading => this is _Loading;
  UserEntity? get user => maybeMap(
        authenticated: (s) => s.user,
        orElse: () => null,
      );
}

final authStateProvider =
    StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  return AuthNotifier(ref);
});

class AuthNotifier extends StateNotifier<AuthState> {
  final Ref _ref;

  AuthNotifier(this._ref) : super(const AuthState.initial()) {
    _checkExistingSession();
  }

  Future<void> _checkExistingSession() async {
    final token = await SecureStorage.read(StorageKeys.accessToken);
    if (token == null) {
      state = const AuthState.unauthenticated();
      return;
    }
    // Token exists — fetch current user to validate it
    final result =
        await _ref.read(authRepositoryProvider).getCurrentUser();
    result.fold(
      (failure) => state = const AuthState.unauthenticated(),
      (user) {
        _cacheUserLocally(user);
        state = AuthState.authenticated(user: user);
      },
    );
  }

  Future<bool> loginWithGoogle() async {
    state = const AuthState.loading();
    final result =
        await _ref.read(authRepositoryProvider).loginWithGoogle();
    return result.fold(
      (failure) {
        state = AuthState.error(message: failure.userMessage);
        return false;
      },
      (user) {
        _cacheUserLocally(user);
        state = AuthState.authenticated(user: user);
        return true;
      },
    );
  }

  Future<bool> login(String email, String password) async {
    state = const AuthState.loading();
    final result = await _ref
        .read(loginUseCaseProvider)
        .call(LoginParams(email: email, password: password));

    return result.fold(
      (failure) {
        state = AuthState.error(message: failure.userMessage);
        return false;
      },
      (user) {
        _cacheUserLocally(user);
        state = AuthState.authenticated(user: user);
        return true;
      },
    );
  }

  Future<bool> register(
      String email, String username, String password, String confirm) async {
    state = const AuthState.loading();
    final result = await _ref.read(registerUseCaseProvider).call(
          RegisterParams(
              email: email,
              username: username,
              password: password,
              confirmPassword: confirm),
        );
    return result.fold(
      (failure) {
        state = AuthState.error(message: failure.userMessage);
        return false;
      },
      (user) {
        _cacheUserLocally(user);
        state = AuthState.authenticated(user: user);
        return true;
      },
    );
  }

  Future<void> logout() async {
    await _ref.read(authRepositoryProvider).logout();
    await HiveStorage.clearAll();
    state = const AuthState.unauthenticated();
  }

  void _cacheUserLocally(UserEntity user) {
    HiveStorage.set(StorageKeys.userId, user.id);
    HiveStorage.set(StorageKeys.userEmail, user.email);
    HiveStorage.set(StorageKeys.userName, user.username);
  }
}
