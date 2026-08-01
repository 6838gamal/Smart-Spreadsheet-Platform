import 'package:dynamic_color/dynamic_color.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/router/app_router.dart';
import 'core/theme/app_theme.dart';
import 'shared/providers/locale_provider.dart';
import 'shared/providers/theme_provider.dart';

class SmartSpreadsheetApp extends ConsumerWidget {
  const SmartSpreadsheetApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(appRouterProvider);
    final themeMode = ref.watch(themeModeProvider);
    final locale = ref.watch(localeProvider);

    // DynamicColorBuilder adapts the seed color to the device's
    // wallpaper-based dynamic color system (Android 12+ / Material You).
    // Falls back to our static seed color on older devices / iOS.
    return DynamicColorBuilder(
      builder: (ColorScheme? lightDynamic, ColorScheme? darkDynamic) {
        final lightScheme = AppTheme.buildColorScheme(
          dynamic: lightDynamic,
          brightness: Brightness.light,
        );
        final darkScheme = AppTheme.buildColorScheme(
          dynamic: darkDynamic,
          brightness: Brightness.dark,
        );

        return MaterialApp.router(
          title: 'Smart Spreadsheet',
          debugShowCheckedModeBanner: false,

          // Routing
          routerConfig: router,

          // Theming
          theme: AppTheme.light(lightScheme),
          darkTheme: AppTheme.dark(darkScheme),
          themeMode: themeMode,

          // Localization (AR + EN with RTL support)
          locale: locale,
          supportedLocales: const [
            Locale('ar'),
            Locale('en'),
          ],
          localizationsDelegates: const [
            GlobalMaterialLocalizations.delegate,
            GlobalWidgetsLocalizations.delegate,
            GlobalCupertinoLocalizations.delegate,
          ],
        );
      },
    );
  }
}
