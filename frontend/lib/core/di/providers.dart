import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../auth/token_store.dart';
import '../network/api_client.dart';
import '../../features/dashboard/data/dashboard_api.dart';
import '../../features/dashboard/data/dashboard_repository.dart';

/// Central dependency wiring. Overridable in tests via ProviderScope overrides.
final tokenStoreProvider = Provider<TokenStore>((ref) => const TokenStore(FlutterSecureStorage()));

final apiClientProvider = Provider<ApiClient>(
  (ref) => ApiClient(tokenStore: ref.read(tokenStoreProvider)),
);

final dashboardApiProvider = Provider<DashboardApi>(
  (ref) => DashboardApi(ref.read(apiClientProvider)),
);

final dashboardRepositoryProvider = Provider<DashboardRepository>(
  (ref) => DashboardRepository(ref.read(dashboardApiProvider)),
);
