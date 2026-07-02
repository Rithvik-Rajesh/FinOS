import 'package:flutter/material.dart';

import 'app_colors.dart';

/// Material 3 themes for FinOS. Kept in one place so the whole app stays visually
/// consistent as features are added.
abstract final class AppTheme {
  static ThemeData light() {
    final scheme = ColorScheme.fromSeed(
      seedColor: AppColors.emerald,
      primary: AppColors.emerald,
      surface: AppColors.surface,
    ).copyWith(onSurface: AppColors.ink);

    return _base(scheme).copyWith(
      scaffoldBackgroundColor: AppColors.background,
    );
  }

  static ThemeData dark() {
    final scheme = ColorScheme.fromSeed(
      seedColor: AppColors.emerald,
      brightness: Brightness.dark,
      primary: AppColors.emerald,
      surface: AppColors.darkSurface,
    ).copyWith(onSurface: AppColors.darkInk);

    return _base(scheme).copyWith(
      scaffoldBackgroundColor: AppColors.darkBackground,
    );
  }

  static ThemeData _base(ColorScheme scheme) {
    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      textTheme: _textTheme(scheme.onSurface),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size.fromHeight(54),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size.fromHeight(54),
          side: const BorderSide(color: AppColors.line),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
        ),
      ),
    );
  }

  static TextTheme _textTheme(Color ink) {
    final muted = ink.withValues(alpha: 0.65);
    return TextTheme(
      displaySmall: TextStyle(
        fontSize: 34,
        height: 1.12,
        fontWeight: FontWeight.w700,
        letterSpacing: -0.5,
        color: ink,
      ),
      headlineSmall: TextStyle(
        fontSize: 22,
        fontWeight: FontWeight.w700,
        color: ink,
      ),
      titleMedium: TextStyle(
        fontSize: 16,
        fontWeight: FontWeight.w600,
        color: ink,
      ),
      bodyLarge: TextStyle(fontSize: 16, height: 1.45, color: ink),
      bodyMedium: TextStyle(fontSize: 14.5, height: 1.45, color: muted),
      labelLarge: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: ink),
    );
  }
}
