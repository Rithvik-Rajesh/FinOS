import 'package:finos/core/money/money.dart';
import 'package:finos/core/theme/app_theme.dart';
import 'package:finos/shared/widgets/dashboard_cards.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Widget tests for the building-block cards. Run with `flutter test` on a machine
/// with the Flutter SDK.
void main() {
  Widget wrap(Widget child) => MaterialApp(
        theme: AppTheme.light(),
        home: Scaffold(body: child),
      );

  testWidgets('BalanceCard shows formatted balance and savings rate', (tester) async {
    await tester.pumpWidget(
      wrap(
        const BalanceCard(
          balance: Money(12500000, 'INR'), // ₹1,25,000.00
          netCashflow: Money(4200000, 'INR'),
          savingsRatePct: 32.0,
        ),
      ),
    );
    expect(find.text('Total balance'), findsOneWidget);
    expect(find.textContaining('32.0%'), findsOneWidget);
  });

  testWidgets('GoalCard renders a progress bar and health pill', (tester) async {
    await tester.pumpWidget(
      wrap(
        GoalCard(
          name: 'Masters Abroad',
          progressRatio: 0.18,
          health: 'behind_schedule',
          current: const Money(27500000, 'INR'),
          target: const Money(150000000, 'INR'),
          projectedCompletion: DateTime(2028, 10),
        ),
      ),
    );
    expect(find.text('Masters Abroad'), findsOneWidget);
    expect(find.byType(LinearProgressIndicator), findsOneWidget);
    expect(find.textContaining('behind'), findsOneWidget);
  });

  testWidgets('InsightCard shows the explainable driver detail', (tester) async {
    await tester.pumpWidget(
      wrap(
        const InsightCard(
          title: 'Spending up 23%',
          detail: 'Primary driver: Swiggy (+₹1400).',
          severity: 'warning',
        ),
      ),
    );
    expect(find.textContaining('Swiggy'), findsOneWidget);
  });
}
