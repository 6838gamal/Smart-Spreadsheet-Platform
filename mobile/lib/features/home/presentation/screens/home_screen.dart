import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../../core/router/app_router.dart';
import '../../../auth/presentation/providers/auth_provider.dart';
import '../../../files/presentation/providers/files_provider.dart';
import '../../../../shared/widgets/file_card.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authStateProvider);
    final files = ref.watch(filesProvider);
    final cs = Theme.of(context).colorScheme;
    final user = auth.user;

    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'مرحباً، ${user?.username ?? ''}',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            Text(
              'Smart Spreadsheet',
              style: Theme.of(context)
                  .textTheme
                  .bodySmall
                  ?.copyWith(color: cs.onSurfaceVariant),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.search_rounded),
            onPressed: () => context.push(AppRoutes.search),
          ),
          IconButton(
            icon: const Icon(Icons.notifications_outlined),
            onPressed: () => context.push(AppRoutes.notifications),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () => ref.read(filesProvider.notifier).loadFiles(refresh: true),
        child: CustomScrollView(
          slivers: [
            SliverPadding(
              padding: const EdgeInsets.all(16),
              sliver: SliverList(
                delegate: SliverChildListDelegate([
                  // ── Usage stats card ──────────────────────────────────────
                  _StatsCard().animate().fadeIn(duration: 400.ms),
                  const SizedBox(height: 20),

                  // ── Quick actions ─────────────────────────────────────────
                  Text('إجراءات سريعة',
                      style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 12),
                  _QuickActionsRow()
                      .animate()
                      .slideY(begin: 0.2, duration: 400.ms, delay: 100.ms)
                      .fadeIn(duration: 400.ms, delay: 100.ms),
                  const SizedBox(height: 24),

                  // ── Recent files ──────────────────────────────────────────
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('الملفات الأخيرة',
                          style: Theme.of(context).textTheme.titleMedium),
                      TextButton(
                        onPressed: () => context.go(AppRoutes.files),
                        child: const Text('عرض الكل'),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                ]),
              ),
            ),

            // Recent files horizontal list
            if (files.isLoading)
              const SliverToBoxAdapter(
                child: SizedBox(
                  height: 160,
                  child: Center(child: CircularProgressIndicator()),
                ),
              )
            else if (files.files.isEmpty)
              SliverToBoxAdapter(
                child: _EmptyFilesState(),
              )
            else
              SliverToBoxAdapter(
                child: SizedBox(
                  height: 160,
                  child: ListView.separated(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    scrollDirection: Axis.horizontal,
                    itemCount: files.files.take(10).length,
                    separatorBuilder: (_, __) => const SizedBox(width: 12),
                    itemBuilder: (ctx, i) {
                      final file = files.files[i];
                      return FileCard(
                        file: file,
                        compact: true,
                      )
                          .animate(delay: (i * 50).ms)
                          .fadeIn(duration: 300.ms)
                          .slideX(begin: 0.1, duration: 300.ms);
                    },
                  ),
                ),
              ),

            const SliverToBoxAdapter(child: SizedBox(height: 24)),
          ],
        ),
      ),
    );
  }
}

// ── Stats Card ────────────────────────────────────────────────────────────────

class _StatsCard extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cs = Theme.of(context).colorScheme;
    final files = ref.watch(filesProvider);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Row(
              children: [
                Expanded(
                  child: _StatTile(
                    icon: Icons.folder_rounded,
                    value: files.files.length.toString(),
                    label: 'الملفات',
                    color: cs.primary,
                  ),
                ),
                Expanded(
                  child: _StatTile(
                    icon: Icons.transform_rounded,
                    value: '0',
                    label: 'تحويلات اليوم',
                    color: cs.secondary,
                  ),
                ),
                Expanded(
                  child: _StatTile(
                    icon: Icons.analytics_rounded,
                    value: '0',
                    label: 'تحليلات',
                    color: cs.tertiary,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            const Divider(height: 1),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('التخزين المستخدم',
                          style: Theme.of(context).textTheme.bodySmall),
                      const SizedBox(height: 4),
                      LinearProgressIndicator(
                        value: 0.3,
                        borderRadius: BorderRadius.circular(4),
                        backgroundColor: cs.surfaceContainerHighest,
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 16),
                Text(
                  '150 MB / 500 MB',
                  style: Theme.of(context)
                      .textTheme
                      .bodySmall
                      ?.copyWith(color: cs.onSurfaceVariant),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _StatTile extends StatelessWidget {
  final IconData icon;
  final String value;
  final String label;
  final Color color;

  const _StatTile({
    required this.icon,
    required this.value,
    required this.label,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.15),
            shape: BoxShape.circle,
          ),
          child: Icon(icon, color: color, size: 22),
        ),
        const SizedBox(height: 6),
        Text(value,
            style: Theme.of(context)
                .textTheme
                .titleMedium
                ?.copyWith(fontWeight: FontWeight.bold)),
        Text(label,
            style: Theme.of(context).textTheme.bodySmall,
            textAlign: TextAlign.center),
      ],
    );
  }
}

// ── Quick Actions ─────────────────────────────────────────────────────────────

class _QuickActionsRow extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final actions = [
      _QuickAction(
        icon: Icons.transform_rounded,
        label: 'تحويل',
        onTap: () => context.go(AppRoutes.convert),
      ),
      _QuickAction(
        icon: Icons.document_scanner_rounded,
        label: 'OCR',
        onTap: () => context.go(AppRoutes.convert),
      ),
      _QuickAction(
        icon: Icons.analytics_outlined,
        label: 'تحليل',
        onTap: () => context.go(AppRoutes.aiChat),
      ),
      _QuickAction(
        icon: Icons.chat_rounded,
        label: 'AI Chat',
        onTap: () => context.go(AppRoutes.aiChat),
      ),
    ];

    return Row(
      children: actions
          .map((a) => Expanded(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: a,
                ),
              ))
          .toList(),
    );
  }
}

class _QuickAction extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  const _QuickAction(
      {required this.icon, required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: BoxDecoration(
          color: cs.secondaryContainer,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          children: [
            Icon(icon, color: cs.onSecondaryContainer, size: 26),
            const SizedBox(height: 6),
            Text(
              label,
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: cs.onSecondaryContainer,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Empty state ───────────────────────────────────────────────────────────────

class _EmptyFilesState extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        children: [
          Icon(Icons.upload_file_rounded, size: 64, color: cs.outlineVariant),
          const SizedBox(height: 16),
          Text('لا توجد ملفات بعد',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          Text('ارفع ملفك الأول للبدء',
              style: Theme.of(context)
                  .textTheme
                  .bodyMedium
                  ?.copyWith(color: cs.onSurfaceVariant)),
        ],
      ),
    );
  }
}
