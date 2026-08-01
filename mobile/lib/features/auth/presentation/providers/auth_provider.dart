import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:freezed_annotation/freezed_annotation.dart';
import 'package:google_sign_in/google_sign_in.dart';

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

class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier() : super(const AuthState.unauthenticated());

  /// Sign in with Google — the only supported login method.
  Future<bool> loginWithGoogle() async {
    state = const AuthState.loading();
    try {
      await GoogleSignIn.instance.signOut();
      final account = await GoogleSignIn.instance.authenticate();
      state = AuthState.authenticated(
        user: UserEntity(
          id: 0,
          email: account.email,
          username: account.displayName ?? account.email.split('@').first,
          role: 'USER',
          isActive: true,
          avatarUrl: account.photoUrl,
          language: 'ar',
          theme: 'dark',
          createdAt: DateTime.now(),
        ),
      );
      return true;
    } on GoogleSignInException catch (e) {
      if (e.code == GoogleSignInExceptionCode.canceled) {
        state = const AuthState.unauthenticated();
      } else {
        state = AuthState.error(message: 'فشل تسجيل الدخول: ${e.description ?? e.code.name}');
      }
      return false;
    } catch (e) {
      state = AuthState.error(message: 'حدث خطأ غير متوقع');
      return false;
    }
  }

  // Keep for compatibility with pin/biometric screens
  Future<bool> login(String email, String password) async {
    state = const AuthState.error(message: 'يُرجى تسجيل الدخول عبر Google');
    return false;
  }

  Future<void> logout() async {
    try {
      await GoogleSignIn.instance.signOut();
    } catch (_) {}
    state = const AuthState.unauthenticated();
  }
}
