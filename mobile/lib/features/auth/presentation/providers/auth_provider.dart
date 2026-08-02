import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:freezed_annotation/freezed_annotation.dart';
import 'package:google_sign_in/google_sign_in.dart';

import '../../../../core/services/remote_config_service.dart';
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

// ── Google Sign-In helper (v6 constructor API) ────────────────────────────────
GoogleSignIn _buildGoogleSignIn() {
  final clientId = RemoteConfigService.googleClientId;
  return GoogleSignIn(
    clientId: clientId.isNotEmpty ? clientId : null,
    scopes: ['email', 'profile'],
  );
}

class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier() : super(const AuthState.unauthenticated());

  /// Sign in with Google — the only supported login method.
  Future<bool> loginWithGoogle() async {
    if (!RemoteConfigService.googleEnabled) {
      state = const AuthState.error(
          message: 'تسجيل الدخول عبر Google غير مفعّل — يرجى ضبط GOOGLE_CLIENT_ID');
      return false;
    }
    state = const AuthState.loading();
    try {
      final googleSignIn = _buildGoogleSignIn();
      // Sign out first so the account picker always appears
      await googleSignIn.signOut();

      // 30-second timeout — prevents the spinner from hanging forever
      final googleUser = await googleSignIn
          .signIn()
          .timeout(const Duration(seconds: 30));

      if (googleUser == null) {
        // User cancelled the picker
        state = const AuthState.unauthenticated();
        return false;
      }

      state = AuthState.authenticated(
        user: UserEntity(
          id: 0,
          email: googleUser.email,
          username: googleUser.displayName ?? googleUser.email.split('@').first,
          role: 'USER',
          isActive: true,
          avatarUrl: googleUser.photoUrl,
          language: 'ar',
          theme: 'dark',
          createdAt: DateTime.now(),
        ),
      );
      return true;
    } catch (e) {
      final msg = e.toString();
      state = AuthState.error(
        message: msg.contains('TimeoutException')
            ? 'انتهت مهلة تسجيل الدخول، حاول مجدداً'
            : msg.contains('canceled') || msg.contains('cancel')
                ? 'تم إلغاء تسجيل الدخول'
                : 'فشل تسجيل الدخول: $msg',
      );
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
      await _buildGoogleSignIn().signOut();
    } catch (_) {}
    state = const AuthState.unauthenticated();
  }
}
