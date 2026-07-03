import '../../../core/network/api_client.dart';
import 'dashboard_dto.dart';

/// Remote data source for the dashboard BFF endpoint.
class DashboardApi {
  const DashboardApi(this._client);
  final ApiClient _client;

  Future<DashboardData> fetch({String currency = 'INR'}) async {
    final json = await _client.getJson('/dashboard', query: {'currency': currency});
    return DashboardData.fromJson(json);
  }
}
