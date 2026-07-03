import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../core/money/money.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import 'finos_card.dart';

Color _severityColor(String severity) => switch (severity) {
      'critical' => AppColors.negative,
      'warning' => AppColors.amber,
      'positive' => AppColors.emerald,
      _ => AppColors.inkMuted,
    };

Color _healthColor(String health) => switch (health) {
      'over' || 'behind_schedule' || 'at_risk' => AppColors.negative,
      'warning' => AppColors.amber,
      'achieved' || 'ahead' || 'under' || 'on_track' => AppColors.emerald,
      _ => AppColors.inkMuted,
    };

final _dateFmt = DateFormat('d MMM');

/// Hero overview card: balance, net cashflow, savings rate.
class BalanceCard extends StatelessWidget {
  const BalanceCard({
    super.key,
    required this.balance,
    required this.netCashflow,
    required this.savingsRatePct,
  });

  final Money balance;
  final Money netCashflow;
  final num? savingsRatePct;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return FinosCard(
      padding: const EdgeInsets.all(AppSpacing.xl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Total balance', style: theme.textTheme.bodyMedium),
          const SizedBox(height: AppSpacing.xs),
          Text(balance.format(), style: theme.textTheme.displaySmall),
          const SizedBox(height: AppSpacing.lg),
          Row(
            children: [
              _Metric(
                label: 'Net this month',
                value: netCashflow.format(compact: true),
                color: netCashflow.isNegative ? AppColors.negative : AppColors.emerald,
              ),
              const SizedBox(width: AppSpacing.xl),
              _Metric(
                label: 'Savings rate',
                value: savingsRatePct == null ? '—' : '${savingsRatePct!.toStringAsFixed(1)}%',
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  const _Metric({required this.label, required this.value, this.color});
  final String label;
  final String value;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: theme.textTheme.bodyMedium?.copyWith(fontSize: 12.5)),
        const SizedBox(height: 2),
        Text(
          value,
          style: theme.textTheme.titleMedium?.copyWith(color: color ?? AppColors.ink),
        ),
      ],
    );
  }
}

/// Goal progress card with a progress bar and forecast completion.
class GoalCard extends StatelessWidget {
  const GoalCard({
    super.key,
    required this.name,
    required this.progressRatio,
    required this.health,
    required this.current,
    required this.target,
    this.projectedCompletion,
    this.onTap,
  });

  final String name;
  final double progressRatio;
  final String health;
  final Money current;
  final Money target;
  final DateTime? projectedCompletion;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return FinosCard(
      onTap: onTap,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: Text(name, style: theme.textTheme.titleMedium)),
              _Pill(text: health.replaceAll('_', ' '), color: _healthColor(health)),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: LinearProgressIndicator(
              value: progressRatio.clamp(0.0, 1.0),
              minHeight: 8,
              backgroundColor: AppColors.line,
              valueColor: AlwaysStoppedAnimation(_healthColor(health)),
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('${current.format(compact: true)} / ${target.format(compact: true)}',
                  style: theme.textTheme.bodyMedium),
              if (projectedCompletion != null)
                Text('~${_dateFmt.format(projectedCompletion!)}',
                    style: theme.textTheme.bodyMedium?.copyWith(fontSize: 12.5)),
            ],
          ),
        ],
      ),
    );
  }
}

/// Insight feed card — colored accent by severity.
class InsightCard extends StatelessWidget {
  const InsightCard({super.key, required this.title, required this.detail, required this.severity});

  final String title;
  final String detail;
  final String severity;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = _severityColor(severity);
    return FinosCard(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(width: 4, height: 40, decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(2))),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: theme.textTheme.titleMedium?.copyWith(fontSize: 15)),
                const SizedBox(height: 2),
                Text(detail, style: theme.textTheme.bodyMedium?.copyWith(fontSize: 13.5)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Forecast card with a compact balance sparkline.
class ForecastCard extends StatelessWidget {
  const ForecastCard({
    super.key,
    required this.endingBalance,
    required this.minBalance,
    required this.projectedNegative,
    required this.points,
  });

  final Money endingBalance;
  final Money minBalance;
  final bool projectedNegative;
  final List<double> points;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return FinosCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: Text('30-day forecast', style: theme.textTheme.titleMedium)),
              if (projectedNegative) _Pill(text: 'low balance', color: AppColors.negative),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          SizedBox(
            height: 48,
            width: double.infinity,
            child: CustomPaint(
              painter: _SparklinePainter(points, projectedNegative ? AppColors.negative : AppColors.emerald),
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _Metric(label: 'Projected end', value: endingBalance.format(compact: true)),
              _Metric(
                label: 'Lowest point',
                value: minBalance.format(compact: true),
                color: minBalance.isNegative ? AppColors.negative : null,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _SparklinePainter extends CustomPainter {
  _SparklinePainter(this.points, this.color);
  final List<double> points;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    if (points.length < 2) return;
    final minV = points.reduce((a, b) => a < b ? a : b);
    final maxV = points.reduce((a, b) => a > b ? a : b);
    final range = (maxV - minV).abs() < 1 ? 1 : (maxV - minV);
    final dx = size.width / (points.length - 1);
    final path = Path();
    for (var i = 0; i < points.length; i++) {
      final x = dx * i;
      final y = size.height - ((points[i] - minV) / range) * size.height;
      i == 0 ? path.moveTo(x, y) : path.lineTo(x, y);
    }
    canvas.drawPath(
      path,
      Paint()
        ..color = color
        ..strokeWidth = 2
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round,
    );
  }

  @override
  bool shouldRepaint(_SparklinePainter old) => old.points != points || old.color != color;
}

/// Budget card: spent vs allocated with a utilization bar.
class BudgetCard extends StatelessWidget {
  const BudgetCard({
    super.key,
    required this.name,
    required this.spent,
    required this.allocated,
    required this.utilizationRatio,
    required this.health,
    this.onTap,
  });

  final String name;
  final Money spent;
  final Money allocated;
  final double? utilizationRatio;
  final String health;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return FinosCard(
      onTap: onTap,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: Text(name, style: theme.textTheme.titleMedium)),
              Text(
                utilizationRatio == null ? '—' : '${(utilizationRatio! * 100).round()}%',
                style: theme.textTheme.titleMedium?.copyWith(color: _healthColor(health)),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: LinearProgressIndicator(
              value: (utilizationRatio ?? 0).clamp(0.0, 1.0),
              minHeight: 8,
              backgroundColor: AppColors.line,
              valueColor: AlwaysStoppedAnimation(_healthColor(health)),
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          Text('${spent.format(compact: true)} of ${allocated.format(compact: true)}',
              style: theme.textTheme.bodyMedium),
        ],
      ),
    );
  }
}

/// Subscription card: name + normalized monthly cost.
class SubscriptionCard extends StatelessWidget {
  const SubscriptionCard({super.key, required this.name, required this.monthly, this.vendor, this.onTap});

  final String name;
  final Money monthly;
  final String? vendor;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return FinosCard(
      onTap: onTap,
      child: Row(
        children: [
          const Icon(Icons.subscriptions_outlined, color: AppColors.emeraldDark),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(name, style: theme.textTheme.titleMedium?.copyWith(fontSize: 15)),
                if (vendor != null) Text(vendor!, style: theme.textTheme.bodyMedium?.copyWith(fontSize: 12.5)),
              ],
            ),
          ),
          Text('${monthly.format(compact: true)}/mo', style: theme.textTheme.titleMedium),
        ],
      ),
    );
  }
}

/// Calendar card: one upcoming financial event.
class CalendarCard extends StatelessWidget {
  const CalendarCard({
    super.key,
    required this.title,
    required this.occursAt,
    required this.direction,
    this.amount,
  });

  final String title;
  final DateTime occursAt;
  final String direction; // inflow | outflow | neutral
  final Money? amount;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final inflow = direction == 'inflow';
    return FinosCard(
      child: Row(
        children: [
          Container(
            width: 44,
            padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
            decoration: BoxDecoration(
              color: AppColors.emeraldSoft,
              borderRadius: BorderRadius.circular(AppSpacing.radiusSm),
            ),
            child: Column(
              children: [
                Text(DateFormat('d').format(occursAt),
                    style: theme.textTheme.titleMedium?.copyWith(color: AppColors.emeraldDark)),
                Text(DateFormat('MMM').format(occursAt).toUpperCase(),
                    style: theme.textTheme.bodyMedium?.copyWith(fontSize: 11, color: AppColors.emeraldDark)),
              ],
            ),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(child: Text(title, style: theme.textTheme.titleMedium?.copyWith(fontSize: 15))),
          if (amount != null)
            Text(
              '${inflow ? '+' : '-'}${amount!.format(compact: true)}',
              style: theme.textTheme.titleMedium?.copyWith(
                color: inflow ? AppColors.emerald : AppColors.ink,
              ),
            ),
        ],
      ),
    );
  }
}

/// Review card: a period snapshot summary.
class ReviewCard extends StatelessWidget {
  const ReviewCard({
    super.key,
    required this.period,
    required this.periodStart,
    required this.totalSpent,
    required this.savingsRatePct,
    this.onTap,
  });

  final String period;
  final DateTime periodStart;
  final Money totalSpent;
  final num? savingsRatePct;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return FinosCard(
      onTap: onTap,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text('${period[0].toUpperCase()}${period.substring(1)} review',
                    style: theme.textTheme.titleMedium),
              ),
              Text(_dateFmt.format(periodStart), style: theme.textTheme.bodyMedium?.copyWith(fontSize: 12.5)),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          Row(
            children: [
              _Metric(label: 'Spent', value: totalSpent.format(compact: true)),
              const SizedBox(width: AppSpacing.xl),
              _Metric(
                label: 'Savings rate',
                value: savingsRatePct == null ? '—' : '${savingsRatePct!.toStringAsFixed(1)}%',
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _Pill extends StatelessWidget {
  const _Pill({required this.text, required this.color});
  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        text,
        style: TextStyle(color: color, fontSize: 11.5, fontWeight: FontWeight.w600),
      ),
    );
  }
}
