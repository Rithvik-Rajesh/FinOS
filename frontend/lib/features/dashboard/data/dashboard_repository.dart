import 'dashboard_api.dart';
import 'dashboard_dto.dart';

/// Repository: serves the cached snapshot instantly (offline-first) and refreshes
/// from the API. The dashboard is a derived read model, so an in-memory snapshot
/// cache is sufficient; entity caches live in the local DB (see FRONTEND_ARCHITECTURE.md).
class DashboardRepository {
  DashboardRepository(this._api);
  final DashboardApi _api;

  DashboardData? _cache;

  DashboardData? get cached => _cache;

  Future<DashboardData> refresh({String currency = 'INR'}) async {
    final data = await _api.fetch(currency: currency);
    _cache = data;
    return data;
  }
}
