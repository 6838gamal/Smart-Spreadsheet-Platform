import 'package:flutter/material.dart';

/// Builds Material 3 ThemeData objects.
/// Dynamic color (Android 12+ / Material You) is handled in app.dart via
/// DynamicColorBuilder; this class just receives the resolved ColorScheme.
class AppTheme {
  AppTheme._();

  /// Seed color used when no dynamic color is available (iOS + older Android).
  static const Color seedColor = Color(0xFF6750A4);

  static ColorScheme buildColorScheme({
    ColorScheme? dynamic,
    required Brightness brightness,
  }) {
    // harmonized() is only available in newer Flutter versions.
    // Use the dynamic scheme directly if provided, otherwise fall back to seed.
    return dynamic ??
        ColorScheme.fromSeed(seedColor: seedColor, brightness: brightness);
  }

  static ThemeData light(ColorScheme scheme) => _build(scheme);
  static ThemeData dark(ColorScheme scheme) => _build(scheme);

  static ThemeData _build(ColorScheme scheme) {
    final isDark = scheme.brightness == Brightness.dark;

    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,

      // Typography — Cairo supports Arabic + Latin
      fontFamily: 'Cairo',
      textTheme: _textTheme(scheme),

      // AppBar
      appBarTheme: AppBarTheme(
        centerTitle: true,
        elevation: 0,
        scrolledUnderElevation: 1,
        backgroundColor: scheme.surface,
        foregroundColor: scheme.onSurface,
      ),

      // Navigation bar (bottom nav)
      navigationBarTheme: NavigationBarThemeData(
        height: 72,
        elevation: 3,
        indicatorColor: scheme.secondaryContainer,
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      ),

      // Cards
      cardTheme: CardThemeData(
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: scheme.outlineVariant, width: 0.5),
        ),
        color: scheme.surface,
      ),

      // Filled buttons
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(double.infinity, 52),
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        ),
      ),

      // Outlined buttons
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(double.infinity, 52),
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        ),
      ),

      // Input decoration
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: scheme.surfaceContainerHighest.withValues(alpha: isDark ? 0.3 : 0.5),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: scheme.primary, width: 2),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: scheme.error, width: 1),
        ),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      ),

      // Chips
      chipTheme: ChipThemeData(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),

      // Snackbar
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        shape:
            RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),

      // Dialog
      dialogTheme: DialogThemeData(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        elevation: 3,
      ),

      // Bottom sheet
      bottomSheetTheme: const BottomSheetThemeData(
        showDragHandle: true,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
        ),
      ),
    );
  }

  static TextTheme _textTheme(ColorScheme scheme) {
    return TextTheme(
      displayLarge: TextStyle(
          fontSize: 57, fontWeight: FontWeight.w400, color: scheme.onSurface),
      displayMedium: TextStyle(
          fontSize: 45, fontWeight: FontWeight.w400, color: scheme.onSurface),
      displaySmall: TextStyle(
          fontSize: 36, fontWeight: FontWeight.w400, color: scheme.onSurface),
      headlineLarge: TextStyle(
          fontSize: 32, fontWeight: FontWeight.w600, color: scheme.onSurface),
      headlineMedium: TextStyle(
          fontSize: 28, fontWeight: FontWeight.w600, color: scheme.onSurface),
      headlineSmall: TextStyle(
          fontSize: 24, fontWeight: FontWeight.w600, color: scheme.onSurface),
      titleLarge: TextStyle(
          fontSize: 22, fontWeight: FontWeight.w600, color: scheme.onSurface),
      titleMedium: TextStyle(
          fontSize: 16, fontWeight: FontWeight.w600, color: scheme.onSurface),
      titleSmall: TextStyle(
          fontSize: 14, fontWeight: FontWeight.w600, color: scheme.onSurface),
      bodyLarge: TextStyle(
          fontSize: 16, fontWeight: FontWeight.w400, color: scheme.onSurface),
      bodyMedium: TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w400,
          color: scheme.onSurfaceVariant),
      bodySmall: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w400,
          color: scheme.onSurfaceVariant),
      labelLarge: TextStyle(
          fontSize: 14, fontWeight: FontWeight.w600, color: scheme.onSurface),
      labelMedium: TextStyle(
          fontSize: 12, fontWeight: FontWeight.w500, color: scheme.onSurface),
      labelSmall: TextStyle(
          fontSize: 11, fontWeight: FontWeight.w500, color: scheme.onSurface),
    );
  }
}
