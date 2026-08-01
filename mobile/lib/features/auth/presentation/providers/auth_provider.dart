import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:freezed_annotation/freezed_annotation.dart';

import '../../domain/entities/user_entity.dart';

part 'auth_provider.freezed.dart';

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
  return AuthNotifier();
});

// ── Local admin credentials ───────────────────────────────────────────────────
const _adminEmail = 'admin@spreadsheet.com';
const _adminPassword = 'Spreadsheet123';

class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier() : super(const AuthState.unauthenticated());

  Future<bool> login(String email, String password) async {
    state = const AuthState.loading();
    // Simulate a brief check
    await Future.delayed(const Duration(milliseconds: 300));

    if (email.trim().toLowerCase() == _adminEmail &&
        password == _adminPassword) {
      state = AuthState.authenticated(
        user: UserEntity(
          id: 1,
          email: _adminEmail,
          username: 'admin',
          role: 'ADMIN',
          isActive: true,
          language: 'ar',
          theme: 'dark',
          createdAt: DateTime(2024),
        ),
      );
      return true;
    }

    state = const AuthState.error(message: 'البريد الإلكتروني أو كلمة المرور غير صحيحة');
    return false;
  }

  Future<bool> loginWithGoogle() async {
    state = const AuthState.error(message: 'تسجيل الدخول عبر Google غير متاح حالياً');
    return false;
  }

  Future<bool> register(
      String email, String username, String password, String confirm) async {
    state = const AuthState.error(message: 'التسجيل غير متاح في هذا الإصدار');
    return false;
  }

  Future<void> logout() async {
    state = const AuthState.unauthenticated();
  }
}
