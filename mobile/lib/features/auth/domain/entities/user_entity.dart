import 'package:freezed_annotation/freezed_annotation.dart';

part 'user_entity.freezed.dart';

/// Pure domain entity — no JSON annotations, no external dependencies.
/// Changes here never force a data-layer rebuild.
@freezed
class UserEntity with _$UserEntity {
  const factory UserEntity({
    required int id,
    required String email,
    required String username,
    required String role,
    required bool isActive,
    String? avatarUrl,
    required String language,
    required String theme,
    required DateTime createdAt,
  }) = _UserEntity;
}
