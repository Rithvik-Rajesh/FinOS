import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/widgets/dashboard_cards.dart';
import '../../../shared/widgets/finos_card.dart';
import '../../../shared/widgets/state_views.dart';
import '../application/dashboard_controller.dart';
import '../data/dashboard_dto.dart';

/// The home dashboard — the heart of the app. Composes the building-block cards
/// from a single BFF payload (see DASHBOARD_ARCHITECTURE.md).
class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(dashboardControllerProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Dashboard'), scrolledUnderElevation: 0),
      body: state.when(
        loading: () => const LoadingView(label: 'Loading your finances…'),
        error: (error, _) => ErrorView(
          message: error is ApiException ? error.message : 'Could not load the dashboard.',
          onRetry: () => ref.read(dashboardControllerProvider.notifier).refresh(),
        ),
        data: (data) => RefreshIndicator(
          onRefresh: () => ref.read(dashboardControllerProvider.notifier).refresh(),
          child: _DashboardBody(data: data),
        ),
      ),
    );
  }
}

class _DashboardBody extends StatelessWidget {
  const _DashboardBody({required this.data});
  final DashboardData data;

  @override
  Widget build(BuildContext context) {
    final o = data.overview;
    return ListView(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.screenPadding, AppSpacing.md, AppSpacing.screenPadding, AppSpacing.xxl,
      ),
      children: [
        BalanceCard(
          balance: o.currentBalance,
          netCashflow: o.netCashflow,
          savingsRatePct: o.savingsRatePct,
        ),
        if (data.insights.isNotEmpty) ...[
          const SectionHeader('Insights'),
          for (final i in data.insights)
            Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.sm),
              child: InsightCard(title: i.title, detail: i.detail, severity: i.severity),
            ),
        ],
        if (data.goals.isNotEmpty) ...[
          const SectionHeader('Goals'),
          for (final g in data.goals)
            Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.sm),
              child: GoalCard(
                name: g.name,
                progressRatio: g.progressRatio,
                health: g.health,
                current: g.current,
                target: g.target,
                projectedCompletion: g.projectedCompletion,
              ),
            ),
        ],
        const SectionHeader('Forecast'),
        ForecastCard(
          endingBalance: data.forecast.endingBalance,
          minBalance: data.forecast.minBalance,
          projectedNegative: data.forecast.projectedNegative,
          points: data.forecast.timeline,
        ),
        if (data.upcoming.isNotEmpty) ...[
          const SectionHeader('Upcoming'),
          for (final u in data.upcoming.take(5))
            Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.sm),
              child: CalendarCard(
                title: u.title,
                occursAt: u.occursAt,
                direction: u.direction,
                amount: u.amount,
              ),
            ),
        ],
        if (data.spendingByCategory.isNotEmpty) ...[
          const SectionHeader('Top spending'),
          FinosCard(
            child: Column(
              children: [
                for (final s in data.spendingByCategory)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text('${s.count} txns', style: Theme.of(context).textTheme.bodyMedium),
                        Text(s.total.format(compact: true),
                            style: Theme.of(context).textTheme.titleMedium?.copyWith(fontSize: 15)),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}
