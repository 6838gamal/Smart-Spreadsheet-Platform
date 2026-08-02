import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';

import '../../../../core/constants/api_constants.dart';
import '../../../../core/network/dio_client.dart';
import '../../domain/entities/chat_message_entity.dart';

// ── HF Model descriptor ───────────────────────────────────────────────────────

class HfModel {
  final int id;
  final String name;
  final String taskType;
  final List<String> languages;
  final String description;

  const HfModel({
    required this.id,
    required this.name,
    required this.taskType,
    required this.languages,
    required this.description,
  });

  factory HfModel.fromJson(Map<String, dynamic> json) => HfModel(
        id: json['id'] as int,
        name: json['name'] as String? ?? '',
        taskType: json['task_type'] as String? ?? '',
        languages: (json['languages'] as List?)
                ?.map((e) => e.toString())
                .toList() ??
            [],
        description: json['description'] as String? ?? '',
      );
}

// ── State ─────────────────────────────────────────────────────────────────────

class AiChatState {
  final List<ChatMessageEntity> messages;
  final bool isLoading;
  final int? activeFileId;
  final String? activeFileName;
  final String? error;
  final List<HfModel> availableModels;
  final HfModel? selectedModel;
  final bool isListeningVoice;

  const AiChatState({
    this.messages = const [],
    this.isLoading = false,
    this.activeFileId,
    this.activeFileName,
    this.error,
    this.availableModels = const [],
    this.selectedModel,
    this.isListeningVoice = false,
  });

  AiChatState copyWith({
    List<ChatMessageEntity>? messages,
    bool? isLoading,
    int? activeFileId,
    String? activeFileName,
    String? error,
    List<HfModel>? availableModels,
    HfModel? selectedModel,
    bool? isListeningVoice,
    bool clearSelectedModel = false,
  }) =>
      AiChatState(
        messages: messages ?? this.messages,
        isLoading: isLoading ?? this.isLoading,
        activeFileId: activeFileId ?? this.activeFileId,
        activeFileName: activeFileName ?? this.activeFileName,
        error: error,
        availableModels: availableModels ?? this.availableModels,
        selectedModel:
            clearSelectedModel ? null : (selectedModel ?? this.selectedModel),
        isListeningVoice: isListeningVoice ?? this.isListeningVoice,
      );
}

// ── Provider ──────────────────────────────────────────────────────────────────

final aiChatProvider =
    StateNotifierProvider<AiChatNotifier, AiChatState>((ref) {
  final client = ref.read(dioClientProvider);
  return AiChatNotifier(client);
});

// ── Notifier ──────────────────────────────────────────────────────────────────

class AiChatNotifier extends StateNotifier<AiChatState> {
  static const _uuid = Uuid();
  final DioClient _client;

  AiChatNotifier(this._client) : super(const AiChatState()) {
    _loadModels();
  }

  // ── Model loading ────────────────────────────────────────────────────────

  Future<void> _loadModels() async {
    try {
      final response = await _client.get(ApiConstants.hfModels);
      final list = response.data['models'] as List? ?? [];
      final models =
          list.map((e) => HfModel.fromJson(e as Map<String, dynamic>)).toList();
      // Default: pick first qa model, then first summarization
      HfModel? def = models.firstWhere(
        (m) =>
            m.taskType == 'question-answering' ||
            m.taskType == 'text2text-generation',
        orElse: () => models.isNotEmpty ? models.first : const HfModel(
          id: 0, name: '', taskType: '', languages: [], description: ''),
      );
      state = state.copyWith(
        availableModels: models,
        selectedModel: models.isNotEmpty ? def : null,
      );
    } catch (_) {
      // Non-critical — user can still chat without model list
    }
  }

  void selectModel(HfModel model) {
    state = state.copyWith(selectedModel: model);
  }

  // ── File management ──────────────────────────────────────────────────────

  void setActiveFile(int fileId, String fileName) {
    state = state.copyWith(activeFileId: fileId, activeFileName: fileName);
    _addMessage(ChatMessageEntity(
      id: _uuid.v4(),
      role: MessageRole.assistant,
      content:
          'تم تحميل **$fileName** ✓\n\nكيف يمكنني مساعدتك في تحليله؟ يمكنني:\n- تلخيص المحتوى\n- الإجابة على أسئلتك\n- استخراج البيانات الرئيسية',
      timestamp: DateTime.now(),
    ));
  }

  void clearFile() {
    state = state.copyWith(
      activeFileId: null,
      activeFileName: null,
      clearSelectedModel: false,
    );
  }

  // ── Messaging ────────────────────────────────────────────────────────────

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

    // Show typing indicator
    final thinkingId = _uuid.v4();
    _addMessage(ChatMessageEntity(
      id: thinkingId,
      role: MessageRole.assistant,
      content: '',
      timestamp: DateTime.now(),
      isStreaming: true,
    ));

    state = state.copyWith(isLoading: true, error: null);

    try {
      final response = await _client.post(
        ApiConstants.hfChat,
        data: {
          'message': content.trim(),
          if (state.activeFileId != null) 'file_id': state.activeFileId,
          if (state.selectedModel != null)
            'model_id': state.selectedModel!.id,
        },
      );

      final data = response.data as Map<String, dynamic>;
      final ok = data['ok'] as bool? ?? false;

      // Remove typing indicator
      state = state.copyWith(
        messages: state.messages.where((m) => m.id != thinkingId).toList(),
        isLoading: false,
      );

      if (ok) {
        final answer = data['answer'] as String? ?? '';
        final modelName = data['model_name'] as String?;
        _addMessage(ChatMessageEntity(
          id: _uuid.v4(),
          role: MessageRole.assistant,
          content: answer.isNotEmpty ? answer : '...لا توجد إجابة من النموذج',
          timestamp: DateTime.now(),
          modelName: modelName,
        ));
      } else {
        final loading = data['loading'] as bool? ?? false;
        final error = data['error'] as String? ?? 'حدث خطأ غير معروف';
        final eta = data['estimated_seconds'] as int?;
        _addMessage(ChatMessageEntity(
          id: _uuid.v4(),
          role: MessageRole.assistant,
          content: loading
              ? '⏳ النموذج يتم تحميله الآن${eta != null ? "، انتظر ~$eta ثانية ثم أعد المحاولة" : "، أعد المحاولة بعد لحظات"}'
              : '⚠️ $error',
          timestamp: DateTime.now(),
          isError: true,
        ));
      }
    } catch (e) {
      state = state.copyWith(
        messages: state.messages.where((m) => m.id != thinkingId).toList(),
        isLoading: false,
      );
      _addMessage(ChatMessageEntity(
        id: _uuid.v4(),
        role: MessageRole.assistant,
        content: '⚠️ تعذّر الاتصال بالخادم: ${e.toString().split('\n').first}',
        timestamp: DateTime.now(),
        isError: true,
      ));
    }
  }

  void _addMessage(ChatMessageEntity msg) {
    state = state.copyWith(messages: [...state.messages, msg]);
  }

  void clearChat() {
    state = state.copyWith(
      messages: [],
      activeFileId: null,
      activeFileName: null,
      error: null,
    );
  }

  void setListeningVoice(bool value) {
    state = state.copyWith(isListeningVoice: value);
  }

  // ── Quick actions ────────────────────────────────────────────────────────
  void summarizeFile() => sendMessage('قم بتلخيص محتوى هذا الملف');
  void extractTables() =>
      sendMessage('استخرج جميع الجداول الموجودة في هذا الملف');
  void extractData() =>
      sendMessage('استخرج البيانات الرئيسية من هذا الملف');
  void analyzeContract() =>
      sendMessage('حلل هذا العقد وأبرز النقاط المهمة والمخاطر');
  void analyzeInvoice() =>
      sendMessage('حلل هذه الفاتورة واستخرج التفاصيل المالية');
  void suggestFormulas() =>
      sendMessage('اقترح صيغ Excel مفيدة لتحليل هذه البيانات');
}
