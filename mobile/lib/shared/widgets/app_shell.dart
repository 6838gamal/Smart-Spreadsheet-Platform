import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/router/app_router.dart';
import '../../features/auth/presentation/providers/auth_provider.dart';
import '../providers/connectivity_banner_provider.dart';

/// Persistent shell that wraps all main-tab screens.
/// Provides bottom navigation, a side drawer, an AI FAB, and the offline banner.
class AppShell extends ConsumerWidget {
  const AppShell({required this.child, super.key});
  final Widget child;

  int _selectedIndex(BuildContext context) {
    final location = GoRouterState.of(context).matchedLocation;
    if (location.startsWith(AppRoutes.files)) return 1;
    if (location.startsWith(AppRoutes.convert)) return 2;
    if (location.startsWith(AppRoutes.account)) return 3;
    return 0; // home
  }

  void _onDestinationTap(BuildContext context, int index) {
    const routes = [
      AppRoutes.home,
      AppRoutes.files,
      AppRoutes.convert,
      AppRoutes.account,
    ];
    context.go(routes[index]);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isOffline = ref.watch(showOfflineBannerProvider);
    final selectedIndex = _selectedIndex(context);
    final cs = Theme.of(context).colorScheme;
    final user = ref.watch(authStateProvider).user;

    return Scaffold(
      drawer: _AppDrawer(user: user),
      body: Column(
        children: [
          // Offline banner
          AnimatedSize(
            duration: 300.ms,
            child: isOffline
                ? Container(
                    width: double.infinity,
                    color: cs.errorContainer,
                    padding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 8),
                    child: SafeArea(
                      bottom: false,
                      child: Row(
                        children: [
                          Icon(Icons.wifi_off_rounded,
                              size: 16, color: cs.onErrorContainer),
                          const SizedBox(width: 8),
                          Text(
                            'لا يوجد اتصال بالإنترنت',
                            style: TextStyle(
                                color: cs.onErrorContainer, fontSize: 13),
                          ),
                        ],
                      ),
                    ),
                  )
                    .animate()
                    .slideY(begin: -1, end: 0, duration: 300.ms)
                : const SizedBox.shrink(),
          ),

          // Main content
          Expanded(child: child),
        ],
      ),

      // AI floating action button
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.push(AppRoutes.aiChat),
        icon: const Icon(Icons.smart_toy_rounded),
        label: const Text('الذكاء الاصطناعي'),
        tooltip: 'المساعد الذكي',
      ).animate().scale(
            delay: 300.ms,
            duration: 400.ms,
            curve: Curves.elasticOut,
          ),

      // Material 3 NavigationBar — 4 tabs (AI moved to FAB)
      bottomNavigationBar: NavigationBar(
        selectedIndex: selectedIndex,
        onDestinationSelected: (i) => _onDestinationTap(context, i),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.home_outlined),
            selectedIcon: Icon(Icons.home_rounded),
            label: 'الرئيسية',
          ),
          NavigationDestination(
            icon: Icon(Icons.folder_outlined),
            selectedIcon: Icon(Icons.folder_rounded),
            label: 'ملفاتي',
          ),
          NavigationDestination(
            icon: Icon(Icons.transform_outlined),
            selectedIcon: Icon(Icons.transform_rounded),
            label: 'تحويل',
          ),
          NavigationDestination(
            icon: Icon(Icons.person_outline_rounded),
            selectedIcon: Icon(Icons.person_rounded),
            label: 'حسابي',
          ),
        ],
      ),
    );
  }
}

// ── Side Drawer ───────────────────────────────────────────────────────────────

class _AppDrawer extends StatelessWidget {
  const _AppDrawer({this.user});
  final dynamic user; // UserEntity?

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final location = GoRouterState.of(context).matchedLocation;

    return Drawer(
      child: SafeArea(
        child: Column(
          children: [
            // ── Header ──────────────────────────────────────────────────────
            Container(
              width: double.infinity,
              padding: const EdgeInsets.fromLTRB(20, 24, 20, 20),
              decoration: BoxDecoration(
                color: cs.primaryContainer,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  CircleAvatar(
                    radius: 32,
                    backgroundColor: cs.primary,
                    backgroundImage: user?.avatarUrl != null
                        ? NetworkImage(user!.avatarUrl as String)
                        : null,
                    child: user?.avatarUrl == null
                        ? Icon(Icons.person_rounded,
                            size: 32, color: cs.onPrimary)
                        : null,
                  ),
                  const SizedBox(height: 12),
                  Text(
                    user?.username ?? 'مرحباً',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: cs.onPrimaryContainer,
                    ),
                  ),
                  if (user?.email != null) ...[
                    const SizedBox(height: 2),
                    Text(
                      user!.email as String,
                      style: TextStyle(
                        fontSize: 12,
                        color: cs.onPrimaryContainer.withOpacity(0.7),
                      ),
                    ),
                  ],
                ],
              ),
            ),

            const SizedBox(height: 8),

            // ── Navigation items ─────────────────────────────────────────────
            Expanded(
              child: ListView(
                padding: EdgeInsets.zero,
                children: [
                  _DrawerItem(
                    icon: Icons.home_outlined,
                    selectedIcon: Icons.home_rounded,
                    label: 'الرئيسية',
                    selected: location == AppRoutes.home,
                    onTap: () {
                      Navigator.of(context).pop();
                      context.go(AppRoutes.home);
                    },
                  ),
                  _DrawerItem(
                    icon: Icons.folder_outlined,
                    selectedIcon: Icons.folder_rounded,
                    label: 'ملفاتي',
                    selected: location.startsWith(AppRoutes.files),
                    onTap: () {
                      Navigator.of(context).pop();
                      context.go(AppRoutes.files);
                    },
                  ),
                  _DrawerItem(
                    icon: Icons.transform_outlined,
                    selectedIcon: Icons.transform_rounded,
                    label: 'تحويل الملفات',
                    selected: location.startsWith(AppRoutes.convert),
                    onTap: () {
                      Navigator.of(context).pop();
                      context.go(AppRoutes.convert);
                    },
                  ),
                  _DrawerItem(
                    icon: Icons.smart_toy_outlined,
                    selectedIcon: Icons.smart_toy_rounded,
                    label: 'المساعد الذكي',
                    selected: location.startsWith(AppRoutes.aiChat),
                    onTap: () {
                      Navigator.of(context).pop();
                      context.push(AppRoutes.aiChat);
                    },
                  ),
                  _DrawerItem(
                    icon: Icons.search_outlined,
                    selectedIcon: Icons.search_rounded,
                    label: 'البحث',
                    selected: location.startsWith(AppRoutes.search),
                    onTap: () {
                      Navigator.of(context).pop();
                      context.push(AppRoutes.search);
                    },
                  ),
                  _DrawerItem(
                    icon: Icons.notifications_outlined,
                    selectedIcon: Icons.notifications_rounded,
                    label: 'الإشعارات',
                    selected: location.startsWith(AppRoutes.notifications),
                    onTap: () {
                      Navigator.of(context).pop();
                      context.push(AppRoutes.notifications);
                    },
                  ),

                  const Divider(indent: 16, endIndent: 16),

                  _DrawerItem(
                    icon: Icons.person_outline_rounded,
                    selectedIcon: Icons.person_rounded,
                    label: 'حسابي',
                    selected: location.startsWith(AppRoutes.account),
                    onTap: () {
                      Navigator.of(context).pop();
                      context.go(AppRoutes.account);
                    },
                  ),

                  // Admin section — only shown to admins
                  if (user?.role == 'ADMIN') ...[
                    const Divider(indent: 16, endIndent: 16),
                    _DrawerItem(
                      icon: Icons.admin_panel_settings_outlined,
                      selectedIcon: Icons.admin_panel_settings_rounded,
                      label: 'إدارة المستخدمين',
                      selected: location.startsWith(AppRoutes.adminUsers),
                      onTap: () {
                        Navigator.of(context).pop();
                        context.push(AppRoutes.adminUsers);
                      },
                    ),
                  ],
                ],
              ),
            ),

            // ── Footer ───────────────────────────────────────────────────────
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              child: ListTile(
                leading: const Icon(Icons.info_outline_rounded),
                title: const Text('Smart Spreadsheet'),
                subtitle: const Text('v1.0.0'),
                dense: true,
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Single drawer item ────────────────────────────────────────────────────────

class _DrawerItem extends StatelessWidget {
  const _DrawerItem({
    required this.icon,
    required this.selectedIcon,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final IconData icon;
  final IconData selectedIcon;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      child: ListTile(
        leading: Icon(
          selected ? selectedIcon : icon,
          color: selected ? cs.primary : null,
        ),
        title: Text(
          label,
          style: TextStyle(
            color: selected ? cs.primary : null,
            fontWeight: selected ? FontWeight.w600 : FontWeight.normal,
          ),
        ),
        selected: selected,
        selectedTileColor: cs.primaryContainer.withOpacity(0.5),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        onTap: onTap,
        dense: true,
      ),
    );
  }
}
