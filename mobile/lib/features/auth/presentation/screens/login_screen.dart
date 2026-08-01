import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/router/app_router.dart';
import '../providers/auth_provider.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailCtrl = TextEditingController();
  final _passwordCtrl = TextEditingController();
  bool _obscurePassword = true;

  @override
  void dispose() {
    _emailCtrl.dispose();
    _passwordCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final success = await ref.read(authStateProvider.notifier).login(
          _emailCtrl.text.trim(),
          _passwordCtrl.text,
        );
    if (success && mounted) context.go(AppRoutes.home);
  }

  Future<void> _signInWithGoogle() async {
    final success =
        await ref.read(authStateProvider.notifier).loginWithGoogle();
    if (success && mounted) context.go(AppRoutes.home);
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final auth = ref.watch(authStateProvider);
    final isLoading = auth.isLoading;
    final error = auth.maybeMap(error: (e) => e.message, orElse: () => null);

    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                const SizedBox(height: 24),

                // Logo
                Container(
                  width: 80,
                  height: 80,
                  decoration: BoxDecoration(
                    color: cs.primaryContainer,
                    borderRadius: BorderRadius.circular(22),
                  ),
                  child: Icon(Icons.table_chart_rounded,
                      size: 44, color: cs.onPrimaryContainer),
                ).animate().scale(duration: 500.ms, curve: Curves.elasticOut),

                const SizedBox(height: 20),

                Text('تسجيل الدخول',
                    style: Theme.of(context).textTheme.headlineSmall),
                const SizedBox(height: 8),
                Text(
                  'مرحباً بعودتك',
                  style: Theme.of(context)
                      .textTheme
                      .bodyMedium
                      ?.copyWith(color: cs.onSurfaceVariant),
                ),

                const SizedBox(height: 32),

                // ── Google Sign-In button ─────────────────────────────────────
                _GoogleSignInButton(
                  isLoading: isLoading,
                  onPressed: _signInWithGoogle,
                ).animate().fadeIn(delay: 100.ms),

                const SizedBox(height: 20),

                // ── Divider ───────────────────────────────────────────────────
                Row(
                  children: [
                    Expanded(child: Divider(color: cs.outlineVariant)),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      child: Text(
                        'أو',
                        style: Theme.of(context)
                            .textTheme
                            .bodySmall
                            ?.copyWith(color: cs.onSurfaceVariant),
                      ),
                    ),
                    Expanded(child: Divider(color: cs.outlineVariant)),
                  ],
                ),

                const SizedBox(height: 20),

                // ── Error banner ──────────────────────────────────────────────
                if (error != null) ...[
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: cs.errorContainer,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      children: [
                        Icon(Icons.error_outline,
                            color: cs.onErrorContainer, size: 18),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(error,
                              style: TextStyle(color: cs.onErrorContainer)),
                        ),
                      ],
                    ),
                  ).animate().shakeX(duration: 400.ms),
                  const SizedBox(height: 16),
                ],

                // ── Email field ───────────────────────────────────────────────
                TextFormField(
                  controller: _emailCtrl,
                  keyboardType: TextInputType.emailAddress,
                  textDirection: TextDirection.ltr,
                  decoration: const InputDecoration(
                    labelText: 'البريد الإلكتروني',
                    prefixIcon: Icon(Icons.email_outlined),
                  ),
                  validator: (v) =>
                      v == null || !v.contains('@') ? 'بريد إلكتروني غير صحيح' : null,
                ),

                const SizedBox(height: 16),

                // ── Password field ────────────────────────────────────────────
                TextFormField(
                  controller: _passwordCtrl,
                  obscureText: _obscurePassword,
                  textDirection: TextDirection.ltr,
                  decoration: InputDecoration(
                    labelText: 'كلمة المرور',
                    prefixIcon: const Icon(Icons.lock_outline),
                    suffixIcon: IconButton(
                      icon: Icon(_obscurePassword
                          ? Icons.visibility_outlined
                          : Icons.visibility_off_outlined),
                      onPressed: () =>
                          setState(() => _obscurePassword = !_obscurePassword),
                    ),
                  ),
                  validator: (v) =>
                      v == null || v.length < 6 ? 'كلمة المرور قصيرة جداً' : null,
                ),

                const SizedBox(height: 8),

                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton(
                    onPressed: () {}, // TODO: forgot password
                    child: const Text('نسيت كلمة المرور؟'),
                  ),
                ),

                const SizedBox(height: 24),

                // ── Login button ──────────────────────────────────────────────
                FilledButton(
                  onPressed: isLoading ? null : _submit,
                  child: isLoading
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(
                              strokeWidth: 2.5, color: Colors.white),
                        )
                      : const Text('تسجيل الدخول'),
                ),

                const SizedBox(height: 16),

                // ── Register link ─────────────────────────────────────────────
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text('ليس لديك حساب؟',
                        style: Theme.of(context).textTheme.bodyMedium),
                    TextButton(
                      onPressed: () => context.go(AppRoutes.register),
                      child: const Text('إنشاء حساب'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ── Google Sign-In button widget ──────────────────────────────────────────────

class _GoogleSignInButton extends StatelessWidget {
  final bool isLoading;
  final VoidCallback onPressed;

  const _GoogleSignInButton({
    required this.isLoading,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return SizedBox(
      width: double.infinity,
      height: 52,
      child: OutlinedButton(
        onPressed: isLoading ? null : onPressed,
        style: OutlinedButton.styleFrom(
          side: BorderSide(color: cs.outline),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
        child: isLoading
            ? SizedBox(
                height: 20,
                width: 20,
                child: CircularProgressIndicator(
                    strokeWidth: 2.5, color: cs.primary),
              )
            : Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  _GoogleLogo(),
                  const SizedBox(width: 12),
                  const Text(
                    'تسجيل الدخول عبر Google',
                    style: TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
                  ),
                ],
              ),
      ),
    );
  }
}

class _GoogleLogo extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 22,
      height: 22,
      child: CustomPaint(painter: _GoogleLogoPainter()),
    );
  }
}

class _GoogleLogoPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2;
    final cy = size.height / 2;
    final r = size.width / 2;

    // Red (top-right arc)
    canvas.drawArc(
      Rect.fromCircle(center: Offset(cx, cy), radius: r),
      -1.05, 1.57, false,
      Paint()
        ..color = const Color(0xFFEA4335)
        ..style = PaintingStyle.stroke
        ..strokeWidth = size.width * 0.18,
    );
    // Blue (right → bottom arc)
    canvas.drawArc(
      Rect.fromCircle(center: Offset(cx, cy), radius: r),
      0.52, 1.57, false,
      Paint()
        ..color = const Color(0xFF4285F4)
        ..style = PaintingStyle.stroke
        ..strokeWidth = size.width * 0.18,
    );
    // Yellow (bottom → left arc)
    canvas.drawArc(
      Rect.fromCircle(center: Offset(cx, cy), radius: r),
      2.09, 1.57, false,
      Paint()
        ..color = const Color(0xFFFBBC05)
        ..style = PaintingStyle.stroke
        ..strokeWidth = size.width * 0.18,
    );
    // Green (left → top arc)
    canvas.drawArc(
      Rect.fromCircle(center: Offset(cx, cy), radius: r),
      3.66, 1.14, false,
      Paint()
        ..color = const Color(0xFF34A853)
        ..style = PaintingStyle.stroke
        ..strokeWidth = size.width * 0.18,
    );

    // Horizontal bar of the "G"
    canvas.drawLine(
      Offset(cx, cy),
      Offset(cx + r * 0.9, cy),
      Paint()
        ..color = const Color(0xFF4285F4)
        ..strokeWidth = size.width * 0.17,
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
