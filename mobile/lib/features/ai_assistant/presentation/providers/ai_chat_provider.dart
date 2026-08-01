import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';

import '../../../../core/constants/api_constants.dart';
import '../../../../core/network/dio_client.dart';
import '../../domain/entities/chat_message_entity.dart';

class AiChatState {
  final List<ChatMessageEntity> messages;
  final bool isLoading;
  final int? activeFileId;
  final String? activeFileName;
  final String? error;

  const AiChatState({
    this.messages = const [],
    this.isLoading = false,
    this.activeFileId,
    this.activeFileName,
    this.error,
  });

  AiChatState copyWith({
    List<ChatMessageEntity>? messages,
    bool? isLoading,
    int? activeFileId,
    String? activeFileName,
    String? error,
  }) =>
      AiChatState(
        messages: messages ?? this.messages,
        isLoading: isLoading ?? this.isLoading,
        activeFileId: activeFileId ?? this.activeFileId,
        activeFileName: activeFileName ?? this.activeFileName,
        error: error ?? this.error,
      );
}

final aiChatProvider =
    StateNotifierProvider<AiChatNotifier, AiChatState>((ref) {
  return AiChatNotifier(ref.watch(dioClientProvider));
});

class AiChatNotifier extends StateNotifier<AiChatState> {
  final DioClient _client;
  static const _uuid = Uuid();

  AiChatNotifier(this._client) : super(const AiChatState());

  void setActiveFile(int fileId, String fileName) {
    state = state.copyWith(activeFileId: fileId, activeFileName: fileName);
    // Add system-style context message
    _addMessage(ChatMessageEntity(
      id: _uuid.v4(),
      role: MessageRole.assistant,
      content: 'تم تحميل الملف: **$fileName**\nكيف يمكنني مساعدتك في تحليله؟',
      timestamp: DateTime.now(),
    ));
  }

  void clearFile() {
    state = state.copyWith(activeFileId: null, activeFileName: null);
  }

  Future<void> sendMessage(String content) async {
    if (content.trim().isEmpty) return;

    // Add user message immediately for responsive UX
    final userMsg = ChatMessageEntity(
      id: _uuid.v4(),
      role: MessageRole.user,
      content: content.trim(),
      timestamp: DateTime.now(),
      fileId: state.activeFileId,
    );
    _addMessage(userMsg);

    // Placeholder streaming message
    final assistantId = _uuid.v4();
    final placeholder = ChatMessageEntity(
      id: assistantId,
      role: MessageRole.assistant,
      content: '',
      timestamp: DateTime.now(),
      isStreaming: true,
    );
    _addMessage(placeholder);

    state = state.copyWith(isLoading: true, error: null);

    try {
      // Build conversation history for context
      final history = state.messages
          .where((m) => !m.isStreaming)
          .map((m) => {
                'role': m.role == MessageRole.user ? 'user' : 'assistant',
                'content': m.content,
              })
          .toList();

      final response = await _client.post(ApiConstants.aiChat, data: {
        'messages': history,
        if (state.activeFileId != null) 'file_id': state.activeFileId,
      });

      final reply = (response.data as Map<String, dynamic>)['message'] as String? ??
          (response.data as Map<String, dynamic>)['reply'] as String? ??
          'لم أتمكن من الحصول على رد';

      // Replace placeholder with real response
      _replaceMessage(
          assistantId,
          placeholder.copyWith(
            content: reply,
            isStreaming: false,
          ));
    } catch (e) {
      _replaceMessage(
          assistantId,
          placeholder.copyWith(
            content: 'عذراً، حدث خطأ: ${e.toString()}',
            isStreaming: false,
          ));
      state = state.copyWith(error: e.toString());
    } finally {
      state = state.copyWith(isLoading: false);
    }
  }

  void _addMessage(ChatMessageEntity msg) {
    state = state.copyWith(messages: [...state.messages, msg]);
  }

  void _replaceMessage(String id, ChatMessageEntity updated) {
    state = state.copyWith(
      messages: state.messages.map((m) => m.id == id ? updated : m).toList(),
    );
  }

  void clearChat() {
    state = const AiChatState();
  }

  // Quick-action helpers
  void summarizeFile() => sendMessage('قم بتلخيص محتوى هذا الملف');
  void extractTables() => sendMessage('استخرج جميع الجداول الموجودة في هذا الملف');
  void extractData() => sendMessage('استخرج البيانات الرئيسية من هذا الملف');
  void analyzeContract() => sendMessage('حلل هذا العقد وأبرز النقاط المهمة');
  void analyzeInvoice() => sendMessage('حلل هذه الفاتورة واستخرج التفاصيل المالية');
  void suggestFormulas() => sendMessage('اقترح صيغ Excel مفيدة لهذه البيانات');
}
