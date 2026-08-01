import '../../domain/entities/user_entity.dart';

/// JSON-serialisable counterpart of [UserEntity].
/// Only this layer knows about the raw API shape.
class UserModel {
  final int id;
  final String email;
  final String username;
  final String role;
  final bool isActive;
  final String? avatarUrl;
  final String language;
  final String theme;
  final DateTime createdAt;

  const UserModel({
    required this.id,
    required this.email,
    required this.username,
    required this.role,
    required this.isActive,
    this.avatarUrl,
    required this.language,
    required this.theme,
    required this.createdAt,
  });

  factory UserModel.fromJson(Map<String, dynamic> json) {
    final prefs = json['preferences'] as Map<String, dynamic>? ?? {};
    return UserModel(
      id: json['id'] as int? ?? 0,
      email: json['email'] as String? ?? '',
      username: json['username'] as String? ?? '',
      role: json['role'] as String? ?? 'USER',
      isActive: json['is_active'] as bool? ?? true,
      avatarUrl: json['avatar_url'] as String?,
      language: prefs['language'] as String? ?? 'ar',
      theme: prefs['theme'] as String? ?? 'dark',
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'] as String) ?? DateTime.now()
          : DateTime.now(),
    );
  }

  UserEntity toEntity() => UserEntity(
        id: id,
        email: email,
        username: username,
        role: role,
        isActive: isActive,
        avatarUrl: avatarUrl,
        language: language,
        theme: theme,
        createdAt: createdAt,
      );
}
