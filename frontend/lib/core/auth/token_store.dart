import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Holds the Supabase access/refresh tokens in the OS secure enclave
/// (Keychain / Keystore). Never stored in the local DB or shared prefs.
class TokenStore {
  const TokenStore(this._storage);

  final FlutterSecureStorage _storage;

  static const _accessKey = 'finos.access_token';
  static const _refreshKey = 'finos.refresh_token';

  Future<String?> readAccessToken() => _storage.read(key: _accessKey);

  Future<void> saveSession({required String access, required String refresh}) async {
    await _storage.write(key: _accessKey, value: access);
    await _storage.write(key: _refreshKey, value: refresh);
  }

  Future<void> clear() async {
    await _storage.delete(key: _accessKey);
    await _storage.delete(key: _refreshKey);
  }
}
