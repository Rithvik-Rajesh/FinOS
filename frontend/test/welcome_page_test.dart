import 'package:finos/features/onboarding/presentation/welcome_page.dart';
import 'package:finos/core/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

/// Smoke test for the opening page: it renders the hero and both CTAs.
void main() {
  testWidgets('WelcomePage shows hero and calls to action', (tester) async {
    final router = GoRouter(
      routes: [
        GoRoute(path: '/', builder: (_, __) => const WelcomePage()),
        GoRoute(path: '/sign-in', builder: (_, __) => const SizedBox()),
      ],
    );

    await tester.pumpWidget(
      MaterialApp.router(theme: AppTheme.light(), routerConfig: router),
    );
    await tester.pumpAndSettle();

    expect(find.text('Your money,\nunderstood.'), findsOneWidget);
    expect(find.text('Get started'), findsOneWidget);
    expect(find.text('I already have an account'), findsOneWidget);
    expect(find.text('Track with intelligence'), findsOneWidget);
  });
}
