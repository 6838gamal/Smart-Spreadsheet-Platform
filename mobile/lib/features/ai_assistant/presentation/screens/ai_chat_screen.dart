import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../shared/widgets/chat_bubble.dart';
import '../providers/ai_chat_provider.dart';

class AiChatScreen extends ConsumerStatefulWidget {
  const AiChatScreen({super.key});

  @override
  ConsumerState<AiChatScreen> createState() => _AiChatScreenState();
}

class _AiChatScreenState extends ConsumerState<AiChatScreen> {
  final _messageCtrl = TextEditingController();
  final _scrollCtrl = ScrollController();
  bool _showActions = true;

  @override
  void dispose() {
    _messageCtrl.dispose();
    _scrollCtrl.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollCtrl.hasClients) {
        _scrollCtrl.animateTo(
          _scrollCtrl.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _send() async {
    final text = _messageCtrl.text.trim();
    if (text.isEmpty) return;
    _messageCtrl.clear();
    setState(() => _showActions = false);
    await ref.read(aiChatProvider.notifier).sendMessage(text);
    _scrollToBottom();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(aiChatProvider);
    final cs = Theme.of(context).colorScheme;

    // Auto-scroll when new messages arrive
    if (state.messages.isNotEmpty) _scrollToBottom();

    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('AI Assistant'),
            if (state.activeFileName != null)
              Text(
                state.activeFileName!,
                style: Theme.of(context)
                    .textTheme
                    .bodySmall
                    ?.copyWith(color: cs.primary),
                overflow: TextOverflow.ellipsis,
              ),
          ],
        ),
        actions: [
          if (state.activeFileId != null)
            IconButton(
              icon: const Icon(Icons.close_rounded),
              onPressed: () => ref.read(aiChatProvider.notifier).clearFile(),
              tooltip: 'إزالة الملف',
            ),
          IconButton(
            icon: const Icon(Icons.attach_file_rounded),
            onPressed: _attachFile,
            tooltip: 'إرفاق ملف',
          ),
          IconButton(
            icon: const Icon(Icons.delete_outline_rounded),
            onPressed: () => ref.read(aiChatProvider.notifier).clearChat(),
            tooltip: 'مسح المحادثة',
          ),
        ],
      ),
      body: Column(
        children: [
          // Chat messages
          Expanded(
            child: state.messages.isEmpty
                ? _buildWelcome(context, ref)
                : ListView.builder(
                    controller: _scrollCtrl,
                    padding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 16),
                    itemCount: state.messages.length,
                    itemBuilder: (ctx, i) {
                      final msg = state.messages[i];
                      return ChatBubble(message: msg)
                          .animate(delay: 50.ms)
                          .fadeIn(duration: 250.ms)
                          .slideY(begin: 0.1, duration: 250.ms);
                    },
                  ),
          ),

          // Quick action chips (shown when chat is empty / has file)
          if (state.activeFileId != null && _showActions)
            _buildQuickActions(context, ref),

          // Input bar
          _buildInputBar(context, state),
        ],
      ),
    );
  }

  Widget _buildWelcome(BuildContext context, WidgetRef ref) {
    final cs = Theme.of(context).colorScheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: cs.primaryContainer,
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.smart_toy_rounded,
                  size: 48, color: cs.onPrimaryContainer),
            ).animate().scale(duration: 500.ms, curve: Curves.elasticOut),
            const SizedBox(height: 20),
            Text('مساعد الذكاء الاصطناعي',
                style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 8),
            Text(
              'أرفق ملفاً وابدأ المحادثة. يمكنني:\n• تلخيص الملف\n• استخراج الجداول والبيانات\n• الإجابة على أسئلتك\n• تحليل العقود والفواتير',
              textAlign: TextAlign.center,
              style: Theme.of(context)
                  .textTheme
                  .bodyMedium
                  ?.copyWith(color: cs.onSurfaceVariant),
            ),
            const SizedBox(height: 24),
            OutlinedButton.icon(
              onPressed: _attachFile,
              icon: const Icon(Icons.attach_file_rounded),
              label: const Text('إرفاق ملف للبدء'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildQuickActions(BuildContext context, WidgetRef ref) {
    final notifier = ref.read(aiChatProvider.notifier);
    final actions = [
      ('تلخيص', Icons.summarize_rounded, notifier.summarizeFile),
      ('استخراج جداول', Icons.table_chart_rounded, notifier.extractTables),
      ('استخراج بيانات', Icons.data_object_rounded, notifier.extractData),
      ('تحليل عقد', Icons.gavel_rounded, notifier.analyzeContract),
      ('تحليل فاتورة', Icons.receipt_rounded, notifier.analyzeInvoice),
      ('صيغ Excel', Icons.functions_rounded, notifier.suggestFormulas),
    ];

    return Container(
      height: 48,
      margin: const EdgeInsets.only(bottom: 4),
      child: ListView.separated(
        padding: const EdgeInsets.symmetric(horizontal: 12),
        scrollDirection: Axis.horizontal,
        itemCount: actions.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (ctx, i) {
          final (label, icon, onTap) = actions[i];
          return ActionChip(
            avatar: Icon(icon, size: 16),
            label: Text(label),
            onPressed: () {
              onTap();
              setState(() => _showActions = false);
              _scrollToBottom();
            },
          );
        },
      ),
    );
  }

  Widget _buildInputBar(BuildContext context, AiChatState state) {
    final cs = Theme.of(context).colorScheme;
    return SafeArea(
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: cs.surface,
          border: Border(top: BorderSide(color: cs.outlineVariant, width: 0.5)),
        ),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: _messageCtrl,
                onSubmitted: (_) => _send(),
                textInputAction: TextInputAction.send,
                decoration: InputDecoration(
                  hintText: 'اكتب سؤالك هنا...',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(24),
                    borderSide: BorderSide.none,
                  ),
                  filled: true,
                  fillColor: cs.surfaceContainerHighest,
                  contentPadding: const EdgeInsets.symmetric(
                      horizontal: 16, vertical: 10),
                  isDense: true,
                ),
                maxLines: 4,
                minLines: 1,
              ),
            ),
            const SizedBox(width: 8),
            FilledButton(
              onPressed: state.isLoading ? null : _send,
              style: FilledButton.styleFrom(
                shape: const CircleBorder(),
                padding: const EdgeInsets.all(12),
                minimumSize: Size.zero,
              ),
              child: state.isLoading
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                          strokeWidth: 2.5, color: Colors.white))
                  : const Icon(Icons.send_rounded),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _attachFile() async {
    final result = await FilePicker.platform.pickFiles();
    if (result == null || result.files.isEmpty) return;
    final file = result.files.first;
    // In a real impl, upload first then set active file id
    // For now, just set name so the UI updates
    ref.read(aiChatProvider.notifier).setActiveFile(
          0, // placeholder — replace with real uploaded file id
          file.name,
        );
  }
}
