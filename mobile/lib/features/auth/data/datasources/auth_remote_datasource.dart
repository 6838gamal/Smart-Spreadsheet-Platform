import '../../../../core/constants/api_constants.dart';
import '../../../../core/constants/storage_keys.dart';
import '../../../../core/network/dio_client.dart';
import '../../../../core/storage/secure_storage.dart';
import '../models/user_model.dart';

abstract class AuthRemoteDataSource {
  Future<UserModel> login({required String email, required String password});
  Future<UserModel> register({
    required String email,
    required String username,
    required String password,
  });
  Future<UserModel> loginWithGoogleIdToken(String idToken);
  Future<void> logout();
  Future<UserModel> getCurrentUser();
}

class AuthRemoteDataSourceImpl implements AuthRemoteDataSource {
  final DioClient _client;

  const AuthRemoteDataSourceImpl(this._client);

  @override
  Future<UserModel> login({
    required String email,
    required String password,
  }) async {
    final response = await _client.post(
      ApiConstants.login,
      data: {'email': email, 'password': password},
    );
    final data = response.data as Map<String, dynamic>;
    // Store tokens from response
    final token = data['access_token'] as String?;
    if (token != null) {
      await SecureStorage.write(StorageKeys.accessToken, token);
    }
    return UserModel.fromJson(data['user'] as Map<String, dynamic>? ?? data);
  }

  @override
  Future<UserModel> register({
    required String email,
    required String username,
    required String password,
  }) async {
    final response = await _client.post(
      ApiConstants.register,
      data: {
        'email': email,
        'username': username,
        'password': password,
      },
    );
    final data = response.data as Map<String, dynamic>;
    final token = data['access_token'] as String?;
    if (token != null) {
      await SecureStorage.write(StorageKeys.accessToken, token);
    }
    return UserModel.fromJson(data['user'] as Map<String, dynamic>? ?? data);
  }

  @override
  Future<UserModel> loginWithGoogleIdToken(String idToken) async {
    final response = await _client.post(
      ApiConstants.googleLogin,
      data: {'id_token': idToken},
    );
    final data = response.data as Map<String, dynamic>;
    final token = data['access_token'] as String?;
    if (token != null) {
      await SecureStorage.write(StorageKeys.accessToken, token);
    }
    return UserModel.fromJson(data['user'] as Map<String, dynamic>? ?? data);
  }

  @override
  Future<void> logout() async {
    try {
      await _client.post(ApiConstants.logout);
    } finally {
      await SecureStorage.delete(StorageKeys.accessToken);
      await SecureStorage.delete(StorageKeys.refreshToken);
    }
  }

  @override
  Future<UserModel> getCurrentUser() async {
    final response = await _client.get(ApiConstants.me);
    return UserModel.fromJson(response.data as Map<String, dynamic>);
  }
}
