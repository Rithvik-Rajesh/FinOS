import 'package:dio/dio.dart';

import '../auth/token_store.dart';
import '../config/app_config.dart';

/// Thin wrapper over Dio: base URL, JSON, and an auth interceptor that attaches
/// the access JWT (validated server-side via JWKS). Maps errors to [ApiException].
class ApiClient {
  ApiClient({required TokenStore tokenStore, Dio? dio})
      : _dio = dio ?? Dio() {
    _dio.options
      ..baseUrl = AppConfig.apiRoot
      ..connectTimeout = const Duration(seconds: 15)
      ..receiveTimeout = const Duration(seconds: 20)
      ..headers['Content-Type'] = 'application/json';
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await tokenStore.readAccessToken();
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
      ),
    );
  }

  final Dio _dio;

  Future<Map<String, dynamic>> getJson(String path, {Map<String, dynamic>? query}) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(path, queryParameters: query);
      return response.data ?? const {};
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Map<String, dynamic>> postJson(String path, {Object? body}) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(path, data: body);
      return response.data ?? const {};
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}

/// A typed, UI-friendly error surfaced from the API's consistent error envelope.
class ApiException implements Exception {
  const ApiException({required this.code, required this.message, this.statusCode});

  final String code;
  final String message;
  final int? statusCode;

  factory ApiException.fromDio(DioException e) {
    final data = e.response?.data;
    if (data is Map && data['error'] is Map) {
      final error = data['error'] as Map;
      return ApiException(
        code: (error['code'] as String?) ?? 'error',
        message: (error['message'] as String?) ?? 'Something went wrong.',
        statusCode: e.response?.statusCode,
      );
    }
    return ApiException(
      code: 'network_error',
      message: e.message ?? 'Network error. Check your connection.',
      statusCode: e.response?.statusCode,
    );
  }

  bool get isUnauthorized => statusCode == 401;

  @override
  String toString() => 'ApiException($code, $message)';
}
