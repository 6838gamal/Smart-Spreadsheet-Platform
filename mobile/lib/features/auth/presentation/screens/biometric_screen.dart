import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/error/failures.dart';
import '../../../../core/router/app_router.dart';
import '../providers/auth_provider.dart';

class BiometricScreen extends ConsumerStatefulWidget {
  const BiometricScreen({super.key});

  @override
  ConsumerState<BiometricScreen> createState() => _BiometricScreenState();
}

class _BiometricScreenState extends ConsumerState<BiometricScreen> {
  bool _isAuthenticating = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _authenticate();
  }

  Future<void> _authenticate() async {
    setState(() {
      _isAuthenticating = true;
      _error = null;
    });

    final result = await ref
        .read(authRepositoryProvider)
        .authenticateWithBiometric();

    result.fold(
      (failure) => setState(() {
        _isAuthenticating = false;
        _error = failure.userMessage;
      }),
      (success) {
        if (success && mounted) {
          context.go(AppRoutes.home);
        } else {
          setState(() {
            _isAuthenticating = false;
            _error = 'فشل التحقق، حاول مجدداً';
          });
        }
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.fingerprint_rounded,
                size: 96,
                color: cs.primary,
              )
                  .animate(onPlay: (c) => c.repeat(reverse: true))
                  .scale(
                      begin: const Offset(0.95, 0.95),
                      end: const Offset(1.05, 1.05),
                      duration: 1.seconds),

              const SizedBox(height: 32),

              Text('التحقق البيومتري',
                  style: Theme.of(context).textTheme.headlineSmall),

              const SizedBox(height: 12),

              Text(
                'استخدم بصمة إصبعك أو معرف الوجه للدخول',
                textAlign: TextAlign.center,
                style: Theme.of(context)
                    .textTheme
                    .bodyMedium
                    ?.copyWith(color: cs.onSurfaceVariant),
              ),

              if (_error != null) ...[
                const SizedBox(height: 24),
                Text(_error!,
                    style: TextStyle(color: cs.error),
                    textAlign: TextAlign.center),
              ],

              const SizedBox(height: 40),

              FilledButton.icon(
                onPressed: _isAuthenticating ? null : _authenticate,
                icon: const Icon(Icons.fingerprint_rounded),
                label: const Text('إعادة المحاولة'),
              ),

              const SizedBox(height: 16),

              TextButton(
                onPressed: () => context.go(AppRoutes.pin),
                child: const Text('استخدام رمز PIN'),
              ),

              TextButton(
                onPressed: () async {
                  await ref.read(authStateProvider.notifier).logout();
                  if (mounted) context.go(AppRoutes.login);
                },
                child: const Text('تسجيل الخروج'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
