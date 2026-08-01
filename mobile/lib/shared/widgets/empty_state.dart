import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';

/// Generic empty state widget — reused across all feature screens.
class EmptyState extends StatelessWidget {
  const EmptyState({
    required this.icon,
    required this.title,
    this.subtitle,
    this.action,
    this.actionLabel,
    super.key,
  });

  final IconData icon;
  final String title;
  final String? subtitle;
  final VoidCallback? action;
  final String? actionLabel;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 72, color: cs.outlineVariant)
                .animate()
                .scale(duration: 400.ms, curve: Curves.elasticOut),
            const SizedBox(height: 20),
            Text(
              title,
              style: Theme.of(context).textTheme.titleMedium,
              textAlign: TextAlign.center,
            ).animate(delay: 100.ms).fadeIn(duration: 300.ms),
            if (subtitle != null) ...[
              const SizedBox(height: 8),
              Text(
                subtitle!,
                style: Theme.of(context)
                    .textTheme
                    .bodyMedium
                    ?.copyWith(color: cs.onSurfaceVariant),
                textAlign: TextAlign.center,
              ).animate(delay: 150.ms).fadeIn(duration: 300.ms),
            ],
            if (action != null && actionLabel != null) ...[
              const SizedBox(height: 24),
              FilledButton(
                onPressed: action,
                child: Text(actionLabel!),
              ).animate(delay: 200.ms).fadeIn(duration: 300.ms),
            ],
          ],
        ),
      ),
    );
  }
}
