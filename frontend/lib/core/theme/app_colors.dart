import 'package:flutter/material.dart';

/// FinOS palette. Emerald signals growth/money; deep navy ink keeps figures
/// legible and serious. Amber is reserved for highlights and attention.
abstract final class AppColors {
  // Brand
  static const Color emerald = Color(0xFF0E9F6E);
  static const Color emeraldDark = Color(0xFF05603A);
  static const Color emeraldSoft = Color(0xFFE6F6EF);

  // Ink / neutrals
  static const Color ink = Color(0xFF0B1B2B);
  static const Color inkMuted = Color(0xFF5B6B7B);
  static const Color line = Color(0xFFE4E9ED);
  static const Color surface = Color(0xFFFFFFFF);
  static const Color background = Color(0xFFF6F8F9);

  // Accents / semantics
  static const Color amber = Color(0xFFF59E0B);
  static const Color positive = Color(0xFF0E9F6E);
  static const Color negative = Color(0xFFDC2626);

  // Dark theme
  static const Color darkBackground = Color(0xFF0B1B2B);
  static const Color darkSurface = Color(0xFF12293D);
  static const Color darkInk = Color(0xFFEAF1F6);
  static const Color darkInkMuted = Color(0xFF9DB0BF);
}
