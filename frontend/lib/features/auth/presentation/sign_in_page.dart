import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';
import '../../../shared/widgets/finos_logo.dart';

/// Placeholder sign-in screen.
///
/// Phase 0 stops here: real authentication uses Supabase Auth (email/phone OTP +
/// Google), wired in the Phase 0 auth spike. See SECURITY.md#authentication.
class SignInPage extends StatelessWidget {
  const SignInPage({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(backgroundColor: Colors.transparent, elevation: 0),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const FinosLogo(size: 40),
              const SizedBox(height: 28),
              Text('Sign in', style: theme.textTheme.displaySmall),
              const SizedBox(height: 8),
              Text(
                'Continue with your phone or email. Authentication arrives in the '
                'Phase 0 Supabase auth spike.',
                style: theme.textTheme.bodyLarge?.copyWith(color: AppColors.inkMuted),
              ),
              const SizedBox(height: 32),
              FilledButton.icon(
                onPressed: null,
                icon: const Icon(Icons.phone_iphone_rounded),
                label: const Text('Continue with phone'),
              ),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: null,
                icon: const Icon(Icons.mail_outline_rounded),
                label: const Text('Continue with email'),
              ),
              const Spacer(),
              Center(
                child: Text(
                  'Coming in Phase 0 — see MILESTONES.md',
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
