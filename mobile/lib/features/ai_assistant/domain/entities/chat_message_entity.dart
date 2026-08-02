import 'package:freezed_annotation/freezed_annotation.dart';

part 'chat_message_entity.freezed.dart';

enum MessageRole { user, assistant, system }

@freezed
class ChatMessageEntity with _$ChatMessageEntity {
  const factory ChatMessageEntity({
    required String id,
    required MessageRole role,
    required String content,
    required DateTime timestamp,
    @Default(false) bool isStreaming,
    @Default(false) bool isError,
    int? fileId,
    String? fileName,
    String? modelName,
  }) = _ChatMessageEntity;
}
