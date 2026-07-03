/// Runtime configuration. Override the API base URL at build time with
/// `--dart-define=FINOS_API_BASE_URL=https://api.finos.app`.
abstract final class AppConfig {
  static const String apiBaseUrl = String.fromEnvironment(
    'FINOS_API_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );

  static const String apiVersion = 'v1';

  static String get apiRoot => '$apiBaseUrl/$apiVersion';
}
