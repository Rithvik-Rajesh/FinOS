import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/di/providers.dart';
import '../data/dashboard_dto.dart';

/// Loads the dashboard: serves the cached snapshot immediately (if present) then
/// refreshes. UI watches this AsyncNotifier and rebuilds reactively.
class DashboardController extends AsyncNotifier<DashboardData> {
  @override
  Future<DashboardData> build() async {
    final repo = ref.read(dashboardRepositoryProvider);
    return repo.cached ?? await repo.refresh();
  }

  Future<void> refresh() async {
    state = const AsyncLoading<DashboardData>().copyWithPrevious(state);
    state = await AsyncValue.guard(() => ref.read(dashboardRepositoryProvider).refresh());
  }
}

final dashboardControllerProvider =
    AsyncNotifierProvider<DashboardController, DashboardData>(DashboardController.new);
