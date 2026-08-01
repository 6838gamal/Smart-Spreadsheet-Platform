import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/constants/storage_keys.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/storage/secure_storage.dart';
import '../../../auth/presentation/providers/auth_provider.dart';

class SplashScreen extends ConsumerStatefulWidget {
  const SplashScreen({super.key});

  @override
  ConsumerState<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends ConsumerState<SplashScreen> {
  @override
  void initState() {
    super.initState();
    _navigate();
  }

  Future<void> _navigate() async {
    // Minimum splash duration for brand visibility
    await Future.delayed(const Duration(milliseconds: 1800));
    if (!mounted) return;

    final authState = ref.read(authStateProvider);

    authState.when(
      initial: () => _navigate(), // still loading
      loading: () => _navigate(),
      authenticated: (_) async {
        // Check if biometric is enabled
        final biometricEnabled =
            await SecureStorage.read(StorageKeys.biometricEnabled);
        if (biometricEnabled == 'true' && mounted) {
          context.go(AppRoutes.biometric);
        } else if (mounted) {
          context.go(AppRoutes.home);
        }
      },
      unauthenticated: () => context.go(AppRoutes.login),
      error: (_) => context.go(AppRoutes.login),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      backgroundColor: cs.surface,
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // App icon with scale animation
            Container(
              width: 100,
              height: 100,
              decoration: BoxDecoration(
                color: cs.primaryContainer,
                borderRadius: BorderRadius.circular(28),
              ),
              child: Icon(
                Icons.table_chart_rounded,
                size: 56,
                color: cs.onPrimaryContainer,
              ),
            )
                .animate()
                .scale(
                    begin: const Offset(0.5, 0.5),
                    end: const Offset(1, 1),
                    duration: 600.ms,
                    curve: Curves.elasticOut)
                .fadeIn(duration: 400.ms),

            const SizedBox(height: 24),

            // App name
            Text(
              'Smart Spreadsheet',
              style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                    color: cs.primary,
                    fontWeight: FontWeight.bold,
                  ),
            )
                .animate(delay: 300.ms)
                .slideY(begin: 0.3, end: 0, duration: 500.ms)
                .fadeIn(duration: 500.ms),

            const SizedBox(height: 8),

            Text(
              'منصة إدارة ومعالجة البيانات الاحترافية',
              style: Theme.of(context)
                  .textTheme
                  .bodyMedium
                  ?.copyWith(color: cs.onSurfaceVariant),
            )
                .animate(delay: 500.ms)
                .slideY(begin: 0.3, end: 0, duration: 500.ms)
                .fadeIn(duration: 500.ms),

            const SizedBox(height: 64),

            // Loading indicator
            SizedBox(
              width: 32,
              height: 32,
              child: CircularProgressIndicator(
                strokeWidth: 3,
                color: cs.primary,
              ),
            ).animate(delay: 800.ms).fadeIn(duration: 400.ms),
          ],
        ),
      ),
    );
  }
}
