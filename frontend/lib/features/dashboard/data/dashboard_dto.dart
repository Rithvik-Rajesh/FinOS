import '../../../core/money/money.dart';

/// DTOs mapping the backend `GET /v1/dashboard` payload to immutable entities.
/// Spending slices carry ids (not names); the client maps names from its local catalog.
class DashboardData {
  const DashboardData({
    required this.currency,
    required this.generatedAt,
    required this.overview,
    required this.insights,
    required this.upcoming,
    required this.goals,
    required this.spendingByCategory,
    required this.spendingByMerchant,
    required this.forecast,
  });

  final String currency;
  final DateTime generatedAt;
  final OverviewData overview;
  final List<InsightData> insights;
  final List<UpcomingData> upcoming;
  final List<GoalData> goals;
  final List<SpendingSlice> spendingByCategory;
  final List<SpendingSlice> spendingByMerchant;
  final ForecastData forecast;

  factory DashboardData.fromJson(Map<String, dynamic> j) => DashboardData(
        currency: j['currency'] as String,
        generatedAt: DateTime.parse(j['generated_at'] as String),
        overview: OverviewData.fromJson(j['overview'] as Map<String, dynamic>),
        insights: (j['insights'] as List).map((e) => InsightData.fromJson(e as Map<String, dynamic>)).toList(),
        upcoming: (j['upcoming'] as List).map((e) => UpcomingData.fromJson(e as Map<String, dynamic>)).toList(),
        goals: (j['goals'] as List).map((e) => GoalData.fromJson(e as Map<String, dynamic>)).toList(),
        spendingByCategory:
            (j['spending_by_category'] as List).map((e) => SpendingSlice.fromJson(e as Map<String, dynamic>)).toList(),
        spendingByMerchant:
            (j['spending_by_merchant'] as List).map((e) => SpendingSlice.fromJson(e as Map<String, dynamic>)).toList(),
        forecast: ForecastData.fromJson(j['forecast'] as Map<String, dynamic>),
      );
}

class OverviewData {
  const OverviewData({
    required this.currentBalance,
    required this.netCashflow,
    required this.savingsRatePct,
    required this.activeGoals,
    required this.avgGoalProgress,
  });

  final Money currentBalance;
  final Money netCashflow;
  final num? savingsRatePct;
  final int activeGoals;
  final double avgGoalProgress;

  factory OverviewData.fromJson(Map<String, dynamic> j) => OverviewData(
        currentBalance: Money.fromJson(j['current_balance'] as Map<String, dynamic>),
        netCashflow: Money.fromJson(j['net_cashflow'] as Map<String, dynamic>),
        savingsRatePct: j['savings_rate_pct'] == null ? null : num.parse(j['savings_rate_pct'].toString()),
        activeGoals: j['active_goals'] as int,
        avgGoalProgress: (j['avg_goal_progress'] as num).toDouble(),
      );
}

class InsightData {
  const InsightData({required this.category, required this.severity, required this.title, required this.detail});
  final String category;
  final String severity;
  final String title;
  final String detail;

  factory InsightData.fromJson(Map<String, dynamic> j) => InsightData(
        category: j['category'] as String,
        severity: j['severity'] as String,
        title: j['title'] as String,
        detail: j['detail'] as String,
      );
}

class UpcomingData {
  const UpcomingData({required this.type, required this.title, required this.occursAt, required this.direction, this.amount});
  final String type;
  final String title;
  final DateTime occursAt;
  final String direction;
  final Money? amount;

  factory UpcomingData.fromJson(Map<String, dynamic> j) => UpcomingData(
        type: j['type'] as String,
        title: j['title'] as String,
        occursAt: DateTime.parse(j['occurs_at'] as String),
        direction: j['direction'] as String,
        amount: j['amount'] == null ? null : Money.fromJson(j['amount'] as Map<String, dynamic>),
      );
}

class GoalData {
  const GoalData({
    required this.goalId,
    required this.name,
    required this.progressRatio,
    required this.health,
    required this.target,
    required this.current,
    this.projectedCompletion,
  });

  final String goalId;
  final String name;
  final double progressRatio;
  final String health;
  final Money target;
  final Money current;
  final DateTime? projectedCompletion;

  factory GoalData.fromJson(Map<String, dynamic> j) => GoalData(
        goalId: j['goal_id'] as String,
        name: j['name'] as String,
        progressRatio: (j['progress_ratio'] as num).toDouble(),
        health: j['health'] as String,
        target: Money.fromJson(j['target'] as Map<String, dynamic>),
        current: Money.fromJson(j['current'] as Map<String, dynamic>),
        projectedCompletion:
            j['projected_completion'] == null ? null : DateTime.parse(j['projected_completion'] as String),
      );
}

class SpendingSlice {
  const SpendingSlice({required this.key, required this.total, required this.count});
  final String? key;
  final Money total;
  final int count;

  factory SpendingSlice.fromJson(Map<String, dynamic> j) => SpendingSlice(
        key: j['key'] as String?,
        total: Money.fromJson(j['total'] as Map<String, dynamic>),
        count: j['count'] as int,
      );
}

class ForecastData {
  const ForecastData({
    required this.endingBalance,
    required this.minBalance,
    required this.projectedNegative,
    required this.timeline,
  });

  final Money endingBalance;
  final Money minBalance;
  final bool projectedNegative;
  final List<double> timeline;

  factory ForecastData.fromJson(Map<String, dynamic> j) => ForecastData(
        endingBalance: Money.fromJson(j['ending_balance'] as Map<String, dynamic>),
        minBalance: Money.fromJson(j['min_balance'] as Map<String, dynamic>),
        projectedNegative: j['projected_negative'] as bool,
        timeline: (j['timeline'] as List)
            .map((e) => (Money.fromJson((e as Map<String, dynamic>)['balance'] as Map<String, dynamic>)).major)
            .toList(),
      );
}
