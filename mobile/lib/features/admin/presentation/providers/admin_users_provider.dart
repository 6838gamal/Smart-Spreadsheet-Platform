import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/constants/api_constants.dart';
import '../../../../core/network/dio_client.dart';

class AdminUser {
  final int id;
  final String email;
  final String username;
  final String role;
  bool isActive;
  final DateTime createdAt;

  AdminUser({
    required this.id,
    required this.email,
    required this.username,
    required this.role,
    required this.isActive,
    required this.createdAt,
  });

  factory AdminUser.fromJson(Map<String, dynamic> json) => AdminUser(
        id: json['id'] as int,
        email: json['email'] as String,
        username: json['username'] as String,
        role: json['role'] as String? ?? 'USER',
        isActive: json['is_active'] as bool? ?? true,
        createdAt: json['created_at'] != null
            ? DateTime.tryParse(json['created_at'] as String) ?? DateTime.now()
            : DateTime.now(),
      );
}

class AdminUsersState {
  final List<AdminUser> users;
  final bool isLoading;
  final String? error;

  const AdminUsersState({
    this.users = const [],
    this.isLoading = false,
    this.error,
  });

  AdminUsersState copyWith({
    List<AdminUser>? users,
    bool? isLoading,
    String? error,
  }) =>
      AdminUsersState(
        users: users ?? this.users,
        isLoading: isLoading ?? this.isLoading,
        error: error,
      );
}

final adminUsersProvider =
    StateNotifierProvider<AdminUsersNotifier, AdminUsersState>((ref) {
  final client = ref.read(dioClientProvider);
  return AdminUsersNotifier(client);
});

class AdminUsersNotifier extends StateNotifier<AdminUsersState> {
  final DioClient _client;

  AdminUsersNotifier(this._client) : super(const AdminUsersState()) {
    loadUsers();
  }

  Future<void> loadUsers() async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final response = await _client.get(ApiConstants.adminUsers);
      final data = response.data;
      final items = data['items'] as List? ?? (data is List ? data : []);
      state = AdminUsersState(
        users: items
            .map((e) => AdminUser.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString());
    }
  }

  Future<void> toggleActive(int userId) async {
    try {
      final response = await _client.patch(
        ApiConstants.adminToggleUser(userId),
      );
      final isActive = response.data['is_active'] as bool;
      state = state.copyWith(
        users: state.users
            .map((u) => u.id == userId
                ? (AdminUser(
                    id: u.id,
                    email: u.email,
                    username: u.username,
                    role: u.role,
                    isActive: isActive,
                    createdAt: u.createdAt,
                  ))
                : u)
            .toList(),
      );
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }

  Future<bool> deleteUser(int userId) async {
    try {
      await _client.delete(ApiConstants.adminDeleteUser(userId));
      state = state.copyWith(
        users: state.users.where((u) => u.id != userId).toList(),
      );
      return true;
    } catch (e) {
      state = state.copyWith(error: e.toString());
      return false;
    }
  }
}
