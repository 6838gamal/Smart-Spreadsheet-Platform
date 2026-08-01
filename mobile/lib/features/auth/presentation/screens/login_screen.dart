import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/router/app_router.dart';
import '../../../../core/services/remote_config_service.dart';
import '../providers/auth_provider.dart';

class LoginScreen extends ConsumerWidget {
  const LoginScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cs = Theme.of(context).colorScheme;
    final auth = ref.watch(authStateProvider);
    final isLoading = auth.isLoading;
    final error = auth.maybeMap(error: (e) => e.message, orElse: () => null);

    // No Google Client ID configured (checked at runtime from backend)
    final clientIdMissing = !RemoteConfigService.googleEnabled;

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 40),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                // ── Logo ───────────────────────────────────────────────────
                Container(
                  width: 90,
                  height: 90,
                  decoration: BoxDecoration(
                    color: cs.primaryContainer,
                    borderRadius: BorderRadius.circular(24),
                  ),
                  child: Icon(Icons.table_chart_rounded,
                      size: 50, color: cs.onPrimaryContainer),
                )
                    .animate()
                    .scale(duration: 500.ms, curve: Curves.elasticOut),

                const SizedBox(height: 24),

                Text(
                  'Smart Spreadsheet',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                ).animate(delay: 200.ms).fadeIn(),

                const SizedBox(height: 8),

                Text(
                  'منصة إدارة ومعالجة البيانات الاحترافية',
                  textAlign: TextAlign.center,
                  style: Theme.of(context)
                      .textTheme
                      .bodyMedium
                      ?.copyWith(color: cs.onSurfaceVariant),
                ).animate(delay: 300.ms).fadeIn(),

                const SizedBox(height: 48),

                // ── Error banner ───────────────────────────────────────────
                if (error != null)
                  Container(
                    width: double.infinity,
                    margin: const EdgeInsets.only(bottom: 20),
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: cs.errorContainer,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      children: [
                        Icon(Icons.error_outline,
                            color: cs.onErrorContainer, size: 18),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(error,
                              style:
                                  TextStyle(color: cs.onErrorContainer)),
                        ),
                      ],
                    ),
                  ).animate().fadeIn().slideY(begin: -0.2),

                // ── No Client ID warning ───────────────────────────────────
                if (clientIdMissing)
                  Container(
                    width: double.infinity,
                    margin: const EdgeInsets.only(bottom: 20),
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: cs.tertiaryContainer,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      children: [
                        Icon(Icons.warning_amber_rounded,
                            color: cs.onTertiaryContainer, size: 18),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            'GOOGLE_CLIENT_ID غير مضبوط.\nشغّل التطبيق مع:\n--dart-define=GOOGLE_CLIENT_ID=...',
                            style: TextStyle(
                                color: cs.onTertiaryContainer,
                                fontSize: 12),
                          ),
                        ),
                      ],
                    ),
                  ).animate().fadeIn(),

                // ── Google Sign-In button ──────────────────────────────────
                SizedBox(
                  width: double.infinity,
                  height: 52,
                  child: FilledButton.icon(
                    onPressed: (isLoading || clientIdMissing)
                        ? null
                        : () async {
                            final ok = await ref
                                .read(authStateProvider.notifier)
                                .loginWithGoogle();
                            if (ok && context.mounted) {
                              context.go(AppRoutes.home);
                            }
                          },
                    icon: isLoading
                        ? SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: cs.onPrimary,
                            ),
                          )
                        : const _GoogleIcon(),
                    label: Text(
                      isLoading ? 'جارٍ تسجيل الدخول...' : 'تسجيل الدخول عبر Google',
                      style: const TextStyle(fontSize: 15),
                    ),
                  ),
                ).animate(delay: 400.ms).fadeIn().slideY(begin: 0.2),

                const SizedBox(height: 40),

                Text(
                  'بتسجيل دخولك توافق على سياسة الخصوصية وشروط الاستخدام',
                  textAlign: TextAlign.center,
                  style: Theme.of(context)
                      .textTheme
                      .bodySmall
                      ?.copyWith(color: cs.outline),
                ).animate(delay: 500.ms).fadeIn(),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ── Google coloured "G" icon ──────────────────────────────────────────────────

class _GoogleIcon extends StatelessWidget {
  const _GoogleIcon();

  @override
  Widget build(BuildContext context) {
    return CustomPaint(size: const Size(20, 20), painter: _GooglePainter());
  }
}

class _GooglePainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2, cy = size.height / 2, r = size.width * 0.38;
    for (final e in [
      (-1.05, 1.57, const Color(0xFFEA4335)),
      (0.52, 1.57, const Color(0xFF4285F4)),
      (2.09, 1.57, const Color(0xFFFBBC05)),
      (3.66, 1.14, const Color(0xFF34A853)),
    ]) {
      canvas.drawArc(
        Rect.fromCircle(center: Offset(cx, cy), radius: r),
        e.$1, e.$2, false,
        Paint()
          ..color = e.$3
          ..style = PaintingStyle.stroke
          ..strokeWidth = size.width * 0.18,
      );
    }
    canvas.drawLine(Offset(cx, cy), Offset(cx + r * 0.9, cy),
        Paint()
          ..color = const Color(0xFF4285F4)
          ..strokeWidth = size.width * 0.17);
  }

  @override
  bool shouldRepaint(covariant CustomPainter _) => false;
}
