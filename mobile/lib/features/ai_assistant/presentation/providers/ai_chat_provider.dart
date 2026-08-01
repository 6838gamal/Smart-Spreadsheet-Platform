import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';

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
  return AiChatNotifier();
});

class AiChatNotifier extends StateNotifier<AiChatState> {
  static const _uuid = Uuid();

  AiChatNotifier() : super(const AiChatState());

  void setActiveFile(int fileId, String fileName) {
    state = state.copyWith(activeFileId: fileId, activeFileName: fileName);
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

    final userMsg = ChatMessageEntity(
      id: _uuid.v4(),
      role: MessageRole.user,
      content: content.trim(),
      timestamp: DateTime.now(),
      fileId: state.activeFileId,
    );
    _addMessage(userMsg);

    state = state.copyWith(isLoading: true, error: null);
    await Future.delayed(const Duration(milliseconds: 400));

    _addMessage(ChatMessageEntity(
      id: _uuid.v4(),
      role: MessageRole.assistant,
      content: 'المساعد الذكي غير متاح في الوضع الحالي.',
      timestamp: DateTime.now(),
    ));

    state = state.copyWith(isLoading: false);
  }

  void _addMessage(ChatMessageEntity msg) {
    state = state.copyWith(messages: [...state.messages, msg]);
  }

  void clearChat() {
    state = const AiChatState();
  }

  void summarizeFile() => sendMessage('قم بتلخيص محتوى هذا الملف');
  void extractTables() => sendMessage('استخرج جميع الجداول الموجودة في هذا الملف');
  void extractData() => sendMessage('استخرج البيانات الرئيسية من هذا الملف');
  void analyzeContract() => sendMessage('حلل هذا العقد وأبرز النقاط المهمة');
  void analyzeInvoice() => sendMessage('حلل هذه الفاتورة واستخرج التفاصيل المالية');
  void suggestFormulas() => sendMessage('اقترح صيغ Excel مفيدة لهذه البيانات');
}
