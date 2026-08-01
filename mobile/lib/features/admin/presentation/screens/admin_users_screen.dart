import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';

// ── Mock user data ────────────────────────────────────────────────────────────

class _UserItem {
  final int id;
  final String email;
  final String username;
  final String role;
  bool isActive;
  final DateTime createdAt;

  _UserItem({
    required this.id,
    required this.email,
    required this.username,
    required this.role,
    required this.isActive,
    required this.createdAt,
  });
}

final _mockUsers = [
  _UserItem(
    id: 1,
    email: 'admin@spreadsheet.com',
    username: 'admin',
    role: 'ADMIN',
    isActive: true,
    createdAt: DateTime(2024, 1, 1),
  ),
  _UserItem(
    id: 2,
    email: 'sara@example.com',
    username: 'sara',
    role: 'USER',
    isActive: true,
    createdAt: DateTime(2024, 3, 15),
  ),
  _UserItem(
    id: 3,
    email: 'ahmed@example.com',
    username: 'ahmed',
    role: 'USER',
    isActive: true,
    createdAt: DateTime(2024, 5, 20),
  ),
  _UserItem(
    id: 4,
    email: 'mona@example.com',
    username: 'mona',
    role: 'USER',
    isActive: false,
    createdAt: DateTime(2024, 6, 10),
  ),
  _UserItem(
    id: 5,
    email: 'khalid@example.com',
    username: 'khalid',
    role: 'USER',
    isActive: true,
    createdAt: DateTime(2024, 7, 1),
  ),
];

// ── Screen ────────────────────────────────────────────────────────────────────

class AdminUsersScreen extends StatefulWidget {
  const AdminUsersScreen({super.key});

  @override
  State<AdminUsersScreen> createState() => _AdminUsersScreenState();
}

class _AdminUsersScreenState extends State<AdminUsersScreen> {
  final List<_UserItem> _users = List.from(_mockUsers);
  String _search = '';

  List<_UserItem> get _filtered => _users
      .where((u) =>
          u.email.toLowerCase().contains(_search.toLowerCase()) ||
          u.username.toLowerCase().contains(_search.toLowerCase()))
      .toList();

  void _toggleActive(_UserItem user) {
    setState(() => user.isActive = !user.isActive);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(user.isActive
            ? 'تم تفعيل ${user.username}'
            : 'تم تعطيل ${user.username}'),
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 2),
      ),
    );
  }

  void _deleteUser(_UserItem user) {
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
            onPressed: () {
              setState(() => _users.removeWhere((u) => u.id == user.id));
              Navigator.pop(ctx);
            },
            child: const Text('حذف'),
          ),
        ],
      ),
    );
  }

  void _showAddUserDialog() {
    final emailCtrl = TextEditingController();
    final nameCtrl = TextEditingController();
    final formKey = GlobalKey<FormState>();

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('إضافة مستخدم'),
        content: Form(
          key: formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                controller: emailCtrl,
                decoration: const InputDecoration(
                  labelText: 'البريد الإلكتروني',
                  prefixIcon: Icon(Icons.email_outlined),
                ),
                keyboardType: TextInputType.emailAddress,
                validator: (v) =>
                    (v == null || !v.contains('@')) ? 'بريد غير صالح' : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: nameCtrl,
                decoration: const InputDecoration(
                  labelText: 'اسم المستخدم',
                  prefixIcon: Icon(Icons.person_outline),
                ),
                validator: (v) =>
                    (v == null || v.trim().isEmpty) ? 'الحقل مطلوب' : null,
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('إلغاء'),
          ),
          FilledButton(
            onPressed: () {
              if (!formKey.currentState!.validate()) return;
              setState(() {
                _users.add(_UserItem(
                  id: _users.isEmpty ? 1 : _users.last.id + 1,
                  email: emailCtrl.text.trim(),
                  username: nameCtrl.text.trim(),
                  role: 'USER',
                  isActive: true,
                  createdAt: DateTime.now(),
                ));
              });
              Navigator.pop(ctx);
            },
            child: const Text('إضافة'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final filtered = _filtered;

    return Scaffold(
      appBar: AppBar(
        title: const Text('إدارة المستخدمين'),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: Chip(
              label: Text('${_users.length} مستخدم'),
              backgroundColor: cs.primaryContainer,
              labelStyle: TextStyle(color: cs.onPrimaryContainer),
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showAddUserDialog,
        icon: const Icon(Icons.person_add_outlined),
        label: const Text('إضافة مستخدم'),
      ),
      body: Column(
        children: [
          // ── Search bar ──────────────────────────────────────────────────
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: SearchBar(
              hintText: 'ابحث بالاسم أو البريد...',
              leading: const Icon(Icons.search_rounded),
              onChanged: (v) => setState(() => _search = v),
              elevation: const WidgetStatePropertyAll(0),
              backgroundColor: WidgetStatePropertyAll(cs.surfaceContainerHighest),
            ),
          ),

          // ── Stats row ───────────────────────────────────────────────────
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            child: Row(
              children: [
                _StatChip(
                  icon: Icons.check_circle_outline,
                  label: '${_users.where((u) => u.isActive).length} نشط',
                  color: cs.tertiary,
                ),
                const SizedBox(width: 8),
                _StatChip(
                  icon: Icons.cancel_outlined,
                  label: '${_users.where((u) => !u.isActive).length} معطّل',
                  color: cs.error,
                ),
                const SizedBox(width: 8),
                _StatChip(
                  icon: Icons.admin_panel_settings_outlined,
                  label: '${_users.where((u) => u.role == 'ADMIN').length} مدير',
                  color: cs.primary,
                ),
              ],
            ),
          ),

          const Divider(height: 1),

          // ── List ────────────────────────────────────────────────────────
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
      ),
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
  final _UserItem user;
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
              color: isAdmin ? cs.onPrimaryContainer : cs.onSecondaryContainer,
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
                  style:
                      TextStyle(fontSize: 10, color: cs.onPrimaryContainer),
                ),
              ),
          ],
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(user.email,
                style: TextStyle(color: cs.onSurfaceVariant, fontSize: 12)),
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
