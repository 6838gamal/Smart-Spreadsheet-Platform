import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/constants/storage_keys.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/storage/hive_storage.dart';
import '../../../../shared/providers/locale_provider.dart';
import '../../../../shared/providers/theme_provider.dart';
import '../../../auth/presentation/providers/auth_provider.dart';

class AccountScreen extends ConsumerWidget {
  const AccountScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authStateProvider);
    final user = auth.user;
    final cs = Theme.of(context).colorScheme;
    final themeMode = ref.watch(themeModeProvider);
    final locale = ref.watch(localeProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('حسابي')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // ── Profile section ──────────────────────────────────────────────
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  CircleAvatar(
                    radius: 32,
                    backgroundColor: cs.primaryContainer,
                    child: Text(
                      (user?.username ?? 'U').substring(0, 1).toUpperCase(),
                      style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                            color: cs.onPrimaryContainer,
                          ),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          user?.username ?? '',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        Text(
                          user?.email ?? '',
                          style: Theme.of(context)
                              .textTheme
                              .bodyMedium
                              ?.copyWith(color: cs.onSurfaceVariant),
                        ),
                        const SizedBox(height: 4),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: cs.primaryContainer,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            user?.role ?? 'USER',
                            style: TextStyle(
                                color: cs.onPrimaryContainer, fontSize: 11),
                          ),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.edit_outlined),
                    onPressed: () {}, // TODO: edit profile
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // ── Subscription card ────────────────────────────────────────────
          Card(
            color: cs.primaryContainer,
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('الاشتراك',
                          style: Theme.of(context)
                              .textTheme
                              .titleMedium
                              ?.copyWith(color: cs.onPrimaryContainer)),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: cs.primary,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text('مجاني',
                            style:
                                TextStyle(color: cs.onPrimary, fontSize: 12)),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  LinearProgressIndicator(
                    value: 0.3,
                    backgroundColor: cs.primary.withValues(alpha: 0.2),
                    color: cs.primary,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    '3 / 10 تحويلات اليوم',
                    style: TextStyle(
                        color: cs.onPrimaryContainer, fontSize: 12),
                  ),
                  const SizedBox(height: 12),
                  OutlinedButton(
                    onPressed: () {},
                    style: OutlinedButton.styleFrom(
                      foregroundColor: cs.onPrimaryContainer,
                      side: BorderSide(color: cs.onPrimaryContainer),
                    ),
                    child: const Text('ترقية الاشتراك'),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // ── Preferences ──────────────────────────────────────────────────
          const _SectionHeader('التفضيلات'),

          ListTile(
            leading: const Icon(Icons.language_rounded),
            title: const Text('اللغة'),
            trailing: DropdownButton<String>(
              value: locale.languageCode,
              underline: const SizedBox(),
              onChanged: (lang) {
                if (lang != null) {
                  ref.read(localeProvider.notifier)
                      .setLocale(Locale(lang));
                }
              },
              items: const [
                DropdownMenuItem(value: 'ar', child: Text('العربية')),
                DropdownMenuItem(value: 'en', child: Text('English')),
              ],
            ),
          ),

          ListTile(
            leading: const Icon(Icons.palette_rounded),
            title: const Text('المظهر'),
            trailing: DropdownButton<ThemeMode>(
              value: themeMode,
              underline: const SizedBox(),
              onChanged: (mode) {
                if (mode != null) {
                  ref.read(themeModeProvider.notifier).setTheme(mode);
                }
              },
              items: const [
                DropdownMenuItem(
                    value: ThemeMode.system, child: Text('تلقائي')),
                DropdownMenuItem(
                    value: ThemeMode.light, child: Text('فاتح')),
                DropdownMenuItem(
                    value: ThemeMode.dark, child: Text('داكن')),
              ],
            ),
          ),

          // ── Security ──────────────────────────────────────────────────────
          const SizedBox(height: 8),
          const _SectionHeader('الأمان'),

          ListTile(
            leading: const Icon(Icons.fingerprint_rounded),
            title: const Text('التحقق البيومتري'),
            trailing: Switch(
              value: false,
              onChanged: (v) async {
                await HiveStorage.set(StorageKeys.biometricEnabled, v.toString());
              },
            ),
          ),

          ListTile(
            leading: const Icon(Icons.pin_rounded),
            title: const Text('رمز PIN'),
            onTap: () => context.push(AppRoutes.pin),
            trailing: const Icon(Icons.chevron_right_rounded),
          ),

          ListTile(
            leading: const Icon(Icons.devices_rounded),
            title: const Text('الأجهزة المسجلة'),
            onTap: () {},
            trailing: const Icon(Icons.chevron_right_rounded),
          ),

          // ── Storage ───────────────────────────────────────────────────────
          const SizedBox(height: 8),
          const _SectionHeader('التخزين'),

          ListTile(
            leading: const Icon(Icons.cleaning_services_rounded),
            title: const Text('مسح الكاش'),
            subtitle: const Text('سيحرر مساحة على الجهاز'),
            onTap: () async {
              await HiveStorage.clearAll();
              if (context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('تم مسح الكاش')),
                );
              }
            },
          ),

          // ── Logout ────────────────────────────────────────────────────────
          const SizedBox(height: 16),
          OutlinedButton.icon(
            onPressed: () async {
              await ref.read(authStateProvider.notifier).logout();
              if (context.mounted) context.go(AppRoutes.login);
            },
            icon: const Icon(Icons.logout_rounded),
            label: const Text('تسجيل الخروج'),
            style: OutlinedButton.styleFrom(
              foregroundColor: cs.error,
              side: BorderSide(color: cs.error),
            ),
          ),
          const SizedBox(height: 32),
        ],
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  const _SectionHeader(this.title);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 4),
      child: Text(
        title,
        style: Theme.of(context).textTheme.labelLarge?.copyWith(
              color: Theme.of(context).colorScheme.primary,
            ),
      ),
    );
  }
}
