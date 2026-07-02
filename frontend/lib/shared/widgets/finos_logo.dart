import 'package:flutter/material.dart';

import '../../core/theme/app_colors.dart';

/// The FinOS brand mark: a rounded emerald tile with an upward "growth" glyph,
/// optionally followed by the wordmark. Drawn in code so there is no asset
/// dependency for the very first screen.
class FinosLogo extends StatelessWidget {
  const FinosLogo({super.key, this.size = 56, this.showWordmark = false});

  final double size;
  final bool showWordmark;

  @override
  Widget build(BuildContext context) {
    final mark = Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [AppColors.emerald, AppColors.emeraldDark],
        ),
        borderRadius: BorderRadius.circular(size * 0.28),
        boxShadow: [
          BoxShadow(
            color: AppColors.emerald.withValues(alpha: 0.35),
            blurRadius: size * 0.35,
            offset: Offset(0, size * 0.12),
          ),
        ],
      ),
      child: Icon(
        Icons.trending_up_rounded,
        color: Colors.white,
        size: size * 0.56,
      ),
    );

    if (!showWordmark) return mark;

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        mark,
        SizedBox(width: size * 0.28),
        Text(
          'FinOS',
          style: TextStyle(
            fontSize: size * 0.5,
            fontWeight: FontWeight.w800,
            letterSpacing: -0.5,
            color: Theme.of(context).colorScheme.onSurface,
          ),
        ),
      ],
    );
  }
}
