import 'package:flutter/material.dart';

/// Racheeta design tokens, mirrored from `docs/DESIGN_SYSTEM.md` / `web/src/design-system/tokens`
/// (brand teal 600 is the primary action colour). No new branding is introduced here.
abstract final class RacheetaColors {
  static const primary50 = Color(0xFFEEF8F7);
  static const primary100 = Color(0xFFD5EFEC);
  static const primary300 = Color(0xFF7CCAC2);
  static const primary400 = Color(0xFF4DB1A8);
  static const primary600 = Color(0xFF1F7F77);
  static const primary700 = Color(0xFF196660);
  static const neutral0 = Color(0xFFFFFFFF);
  static const neutral50 = Color(0xFFF7F9F9);
  static const neutral200 = Color(0xFFE2E7E9);
  static const neutral300 = Color(0xFFCBD3D6);
  static const neutral500 = Color(0xFF6B7A80);
  static const neutral600 = Color(0xFF4A575C);
  static const neutral800 = Color(0xFF22302F);
  static const success = Color(0xFF1E8E5A);
  static const warning = Color(0xFFB7791F);
  static const error = Color(0xFFC4383B);
  static const info = Color(0xFF2F6FB7);
}

abstract final class RacheetaSpacing {
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 24;
  static const double xxl = 32;

  /// Forms and single-column pages stay readable on tablets.
  static const double maxContentWidth = 560;

  /// Minimum touch target (Material / WCAG 2.5.5).
  static const double minTouchTarget = 48;
}

ThemeData buildRacheetaTheme() {
  final scheme =
      ColorScheme.fromSeed(
        seedColor: RacheetaColors.primary600,
        brightness: Brightness.light,
      ).copyWith(
        primary: RacheetaColors.primary600,
        onPrimary: RacheetaColors.neutral0,
        primaryContainer: RacheetaColors.primary100,
        onPrimaryContainer: RacheetaColors.primary700,
        secondary: RacheetaColors.primary700,
        surface: RacheetaColors.neutral0,
        onSurface: RacheetaColors.neutral800,
        onSurfaceVariant: RacheetaColors.neutral600,
        outline: RacheetaColors.neutral300,
        outlineVariant: RacheetaColors.neutral200,
        error: RacheetaColors.error,
        onError: RacheetaColors.neutral0,
      );

  final inputBorder = OutlineInputBorder(
    borderRadius: BorderRadius.circular(12),
    borderSide: const BorderSide(color: RacheetaColors.neutral300),
  );

  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: RacheetaColors.neutral50,
    appBarTheme: const AppBarTheme(
      backgroundColor: RacheetaColors.neutral0,
      foregroundColor: RacheetaColors.neutral800,
      elevation: 0,
      scrolledUnderElevation: 1,
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: RacheetaColors.neutral0,
      border: inputBorder,
      enabledBorder: inputBorder,
      focusedBorder: inputBorder.copyWith(
        borderSide: const BorderSide(
          color: RacheetaColors.primary600,
          width: 2,
        ),
      ),
      errorBorder: inputBorder.copyWith(
        borderSide: const BorderSide(color: RacheetaColors.error),
      ),
      focusedErrorBorder: inputBorder.copyWith(
        borderSide: const BorderSide(color: RacheetaColors.error, width: 2),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size.fromHeight(RacheetaSpacing.minTouchTarget),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size.fromHeight(RacheetaSpacing.minTouchTarget),
        side: const BorderSide(color: RacheetaColors.primary600),
        foregroundColor: RacheetaColors.primary700,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    ),
    navigationBarTheme: const NavigationBarThemeData(
      backgroundColor: RacheetaColors.neutral0,
      indicatorColor: RacheetaColors.primary100,
    ),
    cardTheme: CardThemeData(
      color: RacheetaColors.neutral0,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: RacheetaColors.neutral200),
      ),
    ),
  );
}
