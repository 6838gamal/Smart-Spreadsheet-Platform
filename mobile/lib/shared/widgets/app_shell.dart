import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/router/app_router.dart';
import '../providers/connectivity_banner_provider.dart';

/// Persistent shell that wraps all main-tab screens.
/// Provides bottom navigation and the offline connectivity banner.
class AppShell extends ConsumerWidget {
  const AppShell({required this.child, super.key});
  final Widget child;

  int _selectedIndex(BuildContext context) {
    final location = GoRouterState.of(context).matchedLocation;
    if (location.startsWith(AppRoutes.files)) return 1;
    if (location.startsWith(AppRoutes.convert)) return 2;
    if (location.startsWith(AppRoutes.aiChat)) return 3;
    if (location.startsWith(AppRoutes.account)) return 4;
    return 0; // home
  }

  void _onDestinationTap(BuildContext context, int index) {
    final routes = [
      AppRoutes.home,
      AppRoutes.files,
      AppRoutes.convert,
      AppRoutes.aiChat,
      AppRoutes.account,
    ];
    context.go(routes[index]);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isOffline = ref.watch(showOfflineBannerProvider);
    final selectedIndex = _selectedIndex(context);
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
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

      // Material 3 NavigationBar
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
            icon: Icon(Icons.smart_toy_outlined),
            selectedIcon: Icon(Icons.smart_toy_rounded),
            label: 'الذكاء',
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
