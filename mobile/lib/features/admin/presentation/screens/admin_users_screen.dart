import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/admin_users_provider.dart';

class AdminUsersScreen extends ConsumerWidget {
  const AdminUsersScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(adminUsersProvider);
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('إدارة المستخدمين'),
        actions: [
          if (!state.isLoading)
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: Chip(
                label: Text('${state.users.length} مستخدم'),
                backgroundColor: cs.primaryContainer,
                labelStyle: TextStyle(color: cs.onPrimaryContainer),
              ),
            ),
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () =>
                ref.read(adminUsersProvider.notifier).loadUsers(),
          ),
        ],
      ),
      body: _Body(state: state),
    );
  }
}

class _Body extends ConsumerStatefulWidget {
  final AdminUsersState state;
  const _Body({required this.state});

  @override
  ConsumerState<_Body> createState() => _BodyState();
}

class _BodyState extends ConsumerState<_Body> {
  String _search = '';

  List<AdminUser> get _filtered => widget.state.users
      .where((u) =>
          u.email.toLowerCase().contains(_search.toLowerCase()) ||
          u.username.toLowerCase().contains(_search.toLowerCase()))
      .toList();

  void _toggleActive(AdminUser user) {
    ref.read(adminUsersProvider.notifier).toggleActive(user.id).then((_) {
      if (!mounted) return;
      final updated = ref
          .read(adminUsersProvider)
          .users
          .firstWhere((u) => u.id == user.id, orElse: () => user);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(updated.isActive
              ? 'تم تفعيل ${user.username}'
              : 'تم تعطيل ${user.username}'),
          behavior: SnackBarBehavior.floating,
          duration: const Duration(seconds: 2),
        ),
      );
    });
  }

  void _deleteUser(AdminUser user) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('حذف المستخدم'),
        content: Text('هل تريد حذف "${user.username}"؟'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('إلغاء'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
                backgroundColor: Theme.of(context).colorScheme.error),
            onPressed: () async {
              Navigator.pop(ctx);
              final success = await ref
                  .read(adminUsersProvider.notifier)
                  .deleteUser(user.id);
              if (mounted && !success) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                        ref.read(adminUsersProvider).error ?? 'فشل الحذف'),
                    backgroundColor: Theme.of(context).colorScheme.error,
                  ),
                );
              }
            },
            child: const Text('حذف'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final state = widget.state;

    if (state.isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (state.error != null && state.users.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline_rounded,
                size: 56, color: cs.error),
            const SizedBox(height: 12),
            Text('حدث خطأ أثناء تحميل المستخدمين',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            FilledButton.icon(
              onPressed: () =>
                  ref.read(adminUsersProvider.notifier).loadUsers(),
              icon: const Icon(Icons.refresh),
              label: const Text('إعادة المحاولة'),
            ),
          ],
        ),
      );
    }

    final filtered = _filtered;

    return Column(
      children: [
        // ── Search bar ────────────────────────────────────────────────────
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
          child: SearchBar(
            hintText: 'ابحث بالاسم أو البريد...',
            leading: const Icon(Icons.search_rounded),
            onChanged: (v) => setState(() => _search = v),
            elevation: const WidgetStatePropertyAll(0),
            backgroundColor:
                WidgetStatePropertyAll(cs.surfaceContainerHighest),
          ),
        ),

        // ── Stats row ─────────────────────────────────────────────────────
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
          child: Row(
            children: [
              _StatChip(
                icon: Icons.check_circle_outline,
                label:
                    '${state.users.where((u) => u.isActive).length} نشط',
                color: cs.tertiary,
              ),
              const SizedBox(width: 8),
              _StatChip(
                icon: Icons.cancel_outlined,
                label:
                    '${state.users.where((u) => !u.isActive).length} معطّل',
                color: cs.error,
              ),
              const SizedBox(width: 8),
              _StatChip(
                icon: Icons.admin_panel_settings_outlined,
                label:
                    '${state.users.where((u) => u.role == 'ADMIN').length} مدير',
                color: cs.primary,
              ),
            ],
          ),
        ),

        const Divider(height: 1),

        // ── List ──────────────────────────────────────────────────────────
        Expanded(
          child: filtered.isEmpty
              ? Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.search_off_rounded,
                          size: 56, color: cs.outlineVariant),
                      const SizedBox(height: 12),
                      Text('لا توجد نتائج',
                          style: Theme.of(context).textTheme.titleMedium),
                    ],
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 100),
                  itemCount: filtered.length,
                  itemBuilder: (ctx, i) {
                    final user = filtered[i];
                    return _UserCard(
                      user: user,
                      onToggle: () => _toggleActive(user),
                      onDelete: () => _deleteUser(user),
                    )
                        .animate(delay: (i * 40).ms)
                        .fadeIn(duration: 300.ms)
                        .slideY(begin: 0.1, end: 0, duration: 300.ms);
                  },
                ),
        ),
      ],
    );
  }
}

// ── Widgets ───────────────────────────────────────────────────────────────────

class _StatChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;

  const _StatChip(
      {required this.icon, required this.label, required this.color});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: color),
        const SizedBox(width: 4),
        Text(label,
            style: Theme.of(context)
                .textTheme
                .bodySmall
                ?.copyWith(color: color)),
      ],
    );
  }
}

class _UserCard extends StatelessWidget {
  final AdminUser user;
  final VoidCallback onToggle;
  final VoidCallback onDelete;

  const _UserCard(
      {required this.user, required this.onToggle, required this.onDelete});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final isAdmin = user.role == 'ADMIN';

    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: BorderSide(
          color: user.isActive
              ? cs.outlineVariant.withOpacity(0.4)
              : cs.errorContainer,
          width: 1,
        ),
      ),
      child: ListTile(
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        leading: CircleAvatar(
          backgroundColor:
              isAdmin ? cs.primaryContainer : cs.secondaryContainer,
          child: Text(
            user.username.substring(0, 1).toUpperCase(),
            style: TextStyle(
              color:
                  isAdmin ? cs.onPrimaryContainer : cs.onSecondaryContainer,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
        title: Row(
          children: [
            Text(user.username,
                style: const TextStyle(fontWeight: FontWeight.w600)),
            const SizedBox(width: 8),
            if (isAdmin)
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                decoration: BoxDecoration(
                  color: cs.primaryContainer,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  'ADMIN',
                  style: TextStyle(
                      fontSize: 10, color: cs.onPrimaryContainer),
                ),
              ),
          ],
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(user.email,
                style:
                    TextStyle(color: cs.onSurfaceVariant, fontSize: 12)),
            const SizedBox(height: 2),
            Row(
              children: [
                Icon(
                  user.isActive ? Icons.circle : Icons.circle_outlined,
                  size: 8,
                  color: user.isActive ? cs.tertiary : cs.error,
                ),
                const SizedBox(width: 4),
                Text(
                  user.isActive ? 'نشط' : 'معطّل',
                  style: TextStyle(
                    fontSize: 11,
                    color: user.isActive ? cs.tertiary : cs.error,
                  ),
                ),
              ],
            ),
          ],
        ),
        trailing: isAdmin
            ? null
            : PopupMenuButton<String>(
                icon: const Icon(Icons.more_vert_rounded),
                itemBuilder: (_) => [
                  PopupMenuItem(
                    value: 'toggle',
                    child: Row(
                      children: [
                        Icon(
                          user.isActive
                              ? Icons.block_outlined
                              : Icons.check_circle_outline,
                          size: 18,
                        ),
                        const SizedBox(width: 8),
                        Text(user.isActive ? 'تعطيل' : 'تفعيل'),
                      ],
                    ),
                  ),
                  PopupMenuItem(
                    value: 'delete',
                    child: Row(
                      children: [
                        Icon(Icons.delete_outline,
                            size: 18, color: cs.error),
                        const SizedBox(width: 8),
                        Text('حذف', style: TextStyle(color: cs.error)),
                      ],
                    ),
                  ),
                ],
                onSelected: (v) {
                  if (v == 'toggle') onToggle();
                  if (v == 'delete') onDelete();
                },
              ),
      ),
    );
  }
}
