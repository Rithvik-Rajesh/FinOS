import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/auth/presentation/sign_in_page.dart';
import '../../features/onboarding/presentation/splash_page.dart';
import '../../features/onboarding/presentation/welcome_page.dart';

/// App routes. Kept as constants so navigation is refactor-safe.
abstract final class Routes {
  static const splash = '/';
  static const welcome = '/welcome';
  static const signIn = '/sign-in';
}

/// GoRouter, exposed through Riverpod so guards can later react to auth state
/// (e.g. redirect to /welcome when signed out). See ARCHITECTURE.md §5.
final routerProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    initialLocation: Routes.splash,
    routes: [
      GoRoute(
        path: Routes.splash,
        builder: (context, state) => const SplashPage(),
      ),
      GoRoute(
        path: Routes.welcome,
        builder: (context, state) => const WelcomePage(),
      ),
      GoRoute(
        path: Routes.signIn,
        builder: (context, state) => const SignInPage(),
      ),
    ],
  );
});
