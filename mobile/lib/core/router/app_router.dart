// ignore: unused_import
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/ai_assistant/presentation/screens/ai_chat_screen.dart';
import '../../features/auth/presentation/screens/biometric_screen.dart';
import '../../features/auth/presentation/screens/login_screen.dart';
import '../../features/auth/presentation/screens/pin_screen.dart';
import '../../features/auth/presentation/screens/register_screen.dart';
import '../../features/auth/presentation/providers/auth_provider.dart';
import '../../features/conversion/presentation/screens/conversion_screen.dart';
import '../../features/files/presentation/screens/file_detail_screen.dart';
import '../../features/files/presentation/screens/files_screen.dart';
import '../../features/home/presentation/screens/home_screen.dart';
import '../../features/notifications/presentation/screens/notifications_screen.dart';
import '../../features/account/presentation/screens/account_screen.dart';
import '../../features/admin/presentation/screens/admin_users_screen.dart';
import '../../features/search/presentation/screens/search_screen.dart';
import '../../features/splash/presentation/screens/splash_screen.dart';
import '../../shared/widgets/app_shell.dart';

// Route name constants — use these instead of raw strings.
class AppRoutes {
  static const splash = '/';
  static const login = '/login';
  static const register = '/register';
  static const pin = '/pin';
  static const biometric = '/biometric';
  static const home = '/home';
  static const files = '/files';
  static const fileDetail = '/files/:id';
  static const convert = '/convert';
  static const aiChat = '/ai';
  static const account = '/account';
  static const search = '/search';
  static const notifications = '/notifications';
  static const adminUsers = '/admin/users';
}

final appRouterProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    initialLocation: AppRoutes.splash,
    debugLogDiagnostics: true,
    redirect: (context, state) async {
      final isAuthenticated = ref.read(authStateProvider).isAuthenticated;
      final isOnAuthRoute = state.matchedLocation == AppRoutes.login ||
          state.matchedLocation == AppRoutes.register ||
          state.matchedLocation == AppRoutes.splash;

      if (!isAuthenticated && !isOnAuthRoute) {
        return AppRoutes.login;
      }
      return null;
    },
    routes: [
      GoRoute(
        path: AppRoutes.splash,
        builder: (_, __) => const SplashScreen(),
      ),
      GoRoute(
        path: AppRoutes.login,
        builder: (_, __) => const LoginScreen(),
      ),
      GoRoute(
        path: AppRoutes.register,
        builder: (_, __) => const RegisterScreen(),
      ),
      GoRoute(
        path: AppRoutes.pin,
        builder: (_, state) => PinScreen(
          mode: state.extra as PinMode? ?? PinMode.verify,
        ),
      ),
      GoRoute(
        path: AppRoutes.biometric,
        builder: (_, __) => const BiometricScreen(),
      ),

      // ── Main shell with bottom navigation ──────────────────────────────────
      ShellRoute(
        builder: (context, state, child) => AppShell(child: child),
        routes: [
          GoRoute(
            path: AppRoutes.home,
            builder: (_, __) => const HomeScreen(),
          ),
          GoRoute(
            path: AppRoutes.files,
            builder: (_, __) => const FilesScreen(),
            routes: [
              GoRoute(
                path: ':id',
                builder: (_, state) => FileDetailScreen(
                  fileId: int.parse(state.pathParameters['id']!),
                ),
              ),
            ],
          ),
          GoRoute(
            path: AppRoutes.convert,
            builder: (_, __) => const ConversionScreen(),
          ),
          GoRoute(
            path: AppRoutes.aiChat,
            builder: (_, __) => const AiChatScreen(),
          ),
          GoRoute(
            path: AppRoutes.account,
            builder: (_, __) => const AccountScreen(),
          ),
        ],
      ),

      // ── Full-screen routes (no bottom nav) ─────────────────────────────────
      GoRoute(
        path: AppRoutes.search,
        builder: (_, __) => const SearchScreen(),
      ),
      GoRoute(
        path: AppRoutes.notifications,
        builder: (_, __) => const NotificationsScreen(),
      ),
      GoRoute(
        path: AppRoutes.adminUsers,
        builder: (_, __) => const AdminUsersScreen(),
      ),
    ],
  );
});
