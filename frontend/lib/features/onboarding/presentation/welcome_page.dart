import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/router/app_router.dart';
import '../../../core/theme/app_colors.dart';
import '../../../shared/widgets/finos_logo.dart';

/// The opening page.
///
/// FinOS is a decision tool, not a ledger — so the first screen leads with the
/// promise ("understand your money"), not with features. Three value pillars map
/// to the product's spine: Track → Plan → Decide.
class WelcomePage extends StatelessWidget {
  const WelcomePage({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 16, 24, 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: 8),
              const FinosLogo(size: 44, showWordmark: true),
              const Spacer(flex: 2),

              // ---- Hero ----
              Text('Your money,\nunderstood.', style: theme.textTheme.displaySmall),
              const SizedBox(height: 16),
              Text(
                'Not another expense tracker. FinOS shows you where your '
                'money goes, whether you are on track, and what you can '
                'actually afford next.',
                style: theme.textTheme.bodyLarge?.copyWith(color: AppColors.inkMuted),
              ),
              const SizedBox(height: 32),

              // ---- Value pillars ----
              const _Pillar(
                icon: Icons.insights_rounded,
                title: 'Track with intelligence',
                subtitle: 'See growth, not just totals — “Food +18% vs last month”.',
              ),
              const SizedBox(height: 16),
              const _Pillar(
                icon: Icons.flag_rounded,
                title: 'Plan toward goals',
                subtitle: 'Budgets and goals that tell you what to save, and by when.',
              ),
              const SizedBox(height: 16),
              const _Pillar(
                icon: Icons.calculate_rounded,
                title: 'Decide with confidence',
                subtitle: '“Can I afford this?” — answered from your real numbers.',
              ),

              const Spacer(flex: 3),

              // ---- Calls to action ----
              FilledButton(
                onPressed: () => context.push(Routes.signIn),
                child: const Text('Get started'),
              ),
              const SizedBox(height: 12),
              OutlinedButton(
                onPressed: () => context.push(Routes.signIn),
                child: const Text('I already have an account'),
              ),
              const SizedBox(height: 16),
              Center(
                child: Text(
                  'Your data stays private. Informational only — not financial advice.',
                  textAlign: TextAlign.center,
                  style: theme.textTheme.bodyMedium?.copyWith(fontSize: 12.5),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Pillar extends StatelessWidget {
  const _Pillar({required this.icon, required this.title, required this.subtitle});

  final IconData icon;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            color: AppColors.emeraldSoft,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Icon(icon, color: AppColors.emeraldDark, size: 22),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: theme.textTheme.titleMedium),
              const SizedBox(height: 2),
              Text(
                subtitle,
                style: theme.textTheme.bodyMedium?.copyWith(fontSize: 13.5),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
