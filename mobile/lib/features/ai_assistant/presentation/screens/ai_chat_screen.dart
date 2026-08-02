import 'dart:io' as dart_io;

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:speech_to_text/speech_to_text.dart';

import '../../../../core/utils/file_picker_util.dart';
import '../../../../shared/widgets/chat_bubble.dart';
import '../providers/ai_chat_provider.dart';
import '../../../files/presentation/providers/files_provider.dart';

class AiChatScreen extends ConsumerStatefulWidget {
  const AiChatScreen({super.key});

  @override
  ConsumerState<AiChatScreen> createState() => _AiChatScreenState();
}

class _AiChatScreenState extends ConsumerState<AiChatScreen>
    with TickerProviderStateMixin {
  final _messageCtrl = TextEditingController();
  final _scrollCtrl = ScrollController();
  final _stt = SpeechToText();

  bool _showActions = true;
  bool _sttAvailable = false;

  @override
  void initState() {
    super.initState();
    _initStt();
  }

  Future<void> _initStt() async {
    final available = await _stt.initialize(
      onError: (_) => _stopListening(),
      onStatus: (status) {
        if (status == 'done' || status == 'notListening') _stopListening();
      },
    );
    if (mounted) setState(() => _sttAvailable = available);
  }

  @override
  void dispose() {
    _messageCtrl.dispose();
    _scrollCtrl.dispose();
    _stt.stop();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollCtrl.hasClients) {
        _scrollCtrl.animateTo(
          _scrollCtrl.position.maxScrollExtent,
          duration: const Duration(milliseconds: 350),
          curve: Curves.easeOutCubic,
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

  Future<void> _startListening() async {
    if (!_sttAvailable) return;
    await _stt.listen(
      onResult: (result) {
        _messageCtrl.text = result.recognizedWords;
        _messageCtrl.selection = TextSelection.fromPosition(
          TextPosition(offset: _messageCtrl.text.length),
        );
      },
      listenOptions: SpeechListenOptions(
        localeId: 'ar_SA',
        listenMode: ListenMode.confirmation,
      ),
    );
    ref.read(aiChatProvider.notifier).setListeningVoice(true);
  }

  void _stopListening() {
    _stt.stop();
    ref.read(aiChatProvider.notifier).setListeningVoice(false);
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(aiChatProvider);
    final cs = Theme.of(context).colorScheme;

    if (state.messages.isNotEmpty) _scrollToBottom();

    return Scaffold(
      backgroundColor: cs.surface,
      appBar: _buildAppBar(context, state, cs),
      body: Column(
        children: [
          // ── Model selector bar ─────────────────────────────────────────
          if (state.availableModels.isNotEmpty)
            _ModelBar(state: state, ref: ref),

          // ── Messages ───────────────────────────────────────────────────
          Expanded(
            child: state.messages.isEmpty
                ? _WelcomeView(onAttach: _attachFile, cs: cs)
                : ListView.builder(
                    controller: _scrollCtrl,
                    padding: const EdgeInsets.fromLTRB(12, 16, 12, 12),
                    itemCount: state.messages.length,
                    itemBuilder: (ctx, i) {
                      return ChatBubble(message: state.messages[i])
                          .animate(delay: 30.ms)
                          .fadeIn(duration: 220.ms)
                          .slideY(
                              begin: 0.06, end: 0, duration: 220.ms);
                    },
                  ),
          ),

          // ── Quick actions ──────────────────────────────────────────────
          if (state.activeFileId != null && _showActions && state.messages.length <= 2)
            _QuickActions(
              state: state,
              onAction: () {
                setState(() => _showActions = false);
                _scrollToBottom();
              },
            ),

          // ── Input bar ──────────────────────────────────────────────────
          _InputBar(
            controller: _messageCtrl,
            state: state,
            sttAvailable: _sttAvailable,
            onSend: _send,
            onStartListening: _startListening,
            onStopListening: _stopListening,
            onAttach: _attachFile,
          ),
        ],
      ),
    );
  }

  PreferredSizeWidget _buildAppBar(
      BuildContext context, AiChatState state, ColorScheme cs) {
    return AppBar(
      elevation: 0,
      title: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [cs.primary, cs.tertiary],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(Icons.auto_awesome_rounded,
                size: 18, color: cs.onPrimary),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('مساعد الذكاء الاصطناعي',
                    style: TextStyle(fontSize: 15)),
                if (state.activeFileName != null)
                  Text(
                    state.activeFileName!,
                    style: TextStyle(
                        fontSize: 11,
                        color: cs.primary,
                        fontWeight: FontWeight.w500),
                    overflow: TextOverflow.ellipsis,
                  )
                else
                  Text(
                    'Hugging Face Models',
                    style: TextStyle(fontSize: 11, color: cs.onSurfaceVariant),
                  ),
              ],
            ),
          ),
        ],
      ),
      actions: [
        if (state.activeFileId != null)
          IconButton(
            icon: const Icon(Icons.close_rounded, size: 20),
            onPressed: () => ref.read(aiChatProvider.notifier).clearFile(),
            tooltip: 'إزالة الملف',
          ),
        IconButton(
          icon: const Icon(Icons.attach_file_rounded, size: 20),
          onPressed: _attachFile,
          tooltip: 'إرفاق ملف',
        ),
        IconButton(
          icon: const Icon(Icons.delete_outline_rounded, size: 20),
          onPressed: () => ref.read(aiChatProvider.notifier).clearChat(),
          tooltip: 'مسح المحادثة',
        ),
      ],
    );
  }

  Future<void> _attachFile() async {
    final picked = await pickFile();

    if (picked.cancelled) return;

    if (!picked.success) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(picked.errorMessage ?? 'حدث خطأ أثناء إرفاق الملف'),
          backgroundColor: Theme.of(context).colorScheme.error,
        ));
      }
      return;
    }

    if (picked.path == null || !mounted) return;

    final notifier = ref.read(filesProvider.notifier);
    final success = await notifier.uploadFile(dart_io.File(picked.path!));
    if (!success || !mounted) return;

    final files = ref.read(filesProvider).files;
    final uploadedId = files.isNotEmpty ? files.first.id : 0;
    ref.read(aiChatProvider.notifier).setActiveFile(uploadedId, picked.name ?? '');
  }
}

// ── Model selector bar ────────────────────────────────────────────────────────

class _ModelBar extends StatelessWidget {
  const _ModelBar({required this.state, required this.ref});
  final AiChatState state;
  final WidgetRef ref;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      height: 40,
      decoration: BoxDecoration(
        color: cs.surfaceContainerLow,
        border: Border(
            bottom: BorderSide(color: cs.outlineVariant.withAlpha(80))),
      ),
      child: Row(
        children: [
          Padding(
            padding: const EdgeInsets.only(left: 12, right: 6),
            child: Icon(Icons.model_training_outlined,
                size: 14, color: cs.onSurfaceVariant),
          ),
          Expanded(
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 2),
              itemCount: state.availableModels.length,
              separatorBuilder: (_, __) => const SizedBox(width: 6),
              itemBuilder: (ctx, i) {
                final model = state.availableModels[i];
                final isSelected = state.selectedModel?.id == model.id;
                return GestureDetector(
                  onTap: () =>
                      ref.read(aiChatProvider.notifier).selectModel(model),
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 200),
                    padding: const EdgeInsets.symmetric(
                        horizontal: 10, vertical: 0),
                    decoration: BoxDecoration(
                      color: isSelected
                          ? cs.primaryContainer
                          : cs.surfaceContainerHighest,
                      borderRadius: BorderRadius.circular(20),
                      border: isSelected
                          ? Border.all(color: cs.primary, width: 1.5)
                          : null,
                    ),
                    child: Center(
                      child: Text(
                        model.name,
                        style: TextStyle(
                          fontSize: 11,
                          color: isSelected
                              ? cs.onPrimaryContainer
                              : cs.onSurfaceVariant,
                          fontWeight: isSelected
                              ? FontWeight.w600
                              : FontWeight.normal,
                        ),
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

// ── Welcome screen ────────────────────────────────────────────────────────────

class _WelcomeView extends StatelessWidget {
  const _WelcomeView({required this.onAttach, required this.cs});
  final VoidCallback onAttach;
  final ColorScheme cs;

  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    return SingleChildScrollView(
      padding: const EdgeInsets.all(28),
      child: Column(
        children: [
          const SizedBox(height: 20),
          // ── Hero icon ──────────────────────────────────────────────────
          Container(
            width: 88,
            height: 88,
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [cs.primary, cs.tertiary],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(24),
              boxShadow: [
                BoxShadow(
                  color: cs.primary.withAlpha(80),
                  blurRadius: 20,
                  offset: const Offset(0, 8),
                ),
              ],
            ),
            child: Icon(Icons.auto_awesome_rounded,
                size: 44, color: cs.onPrimary),
          )
              .animate()
              .scale(
                  duration: 600.ms,
                  curve: Curves.elasticOut,
                  begin: const Offset(0.5, 0.5))
              .fadeIn(duration: 400.ms),

          const SizedBox(height: 20),
          Text(
            'مساعد ذكي بنماذج HF',
            style: tt.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
            textAlign: TextAlign.center,
          ).animate().fadeIn(delay: 200.ms, duration: 400.ms).slideY(
              begin: 0.2, duration: 400.ms),

          const SizedBox(height: 8),
          Text(
            'يستخدم نماذج Hugging Face لتحليل ملفاتك\nوالإجابة على أسئلتك باللغتين العربية والإنجليزية',
            style: tt.bodyMedium?.copyWith(
                color: cs.onSurfaceVariant, height: 1.6),
            textAlign: TextAlign.center,
          ).animate().fadeIn(delay: 300.ms, duration: 400.ms),

          const SizedBox(height: 28),

          // ── Feature cards ──────────────────────────────────────────────
          ...[
            (Icons.question_answer_outlined, 'سؤال وجواب',
                'اطرح أسئلة عن محتوى ملفك'),
            (Icons.summarize_outlined, 'تلخيص تلقائي',
                'احصل على ملخص فوري لأي وثيقة'),
            (Icons.record_voice_over_outlined, 'إدخال صوتي',
                'تحدث بدلاً من الكتابة'),
            (Icons.volume_up_outlined, 'قراءة صوتية',
                'استمع للإجابات بصوت واضح'),
          ].asMap().entries.map((entry) {
            final (icon, title, desc) = entry.value;
            return _FeatureCard(
              icon: icon,
              title: title,
              desc: desc,
              cs: cs,
              tt: tt,
            )
                .animate(delay: Duration(milliseconds: 350 + entry.key * 80))
                .fadeIn(duration: 350.ms)
                .slideX(begin: 0.1, duration: 350.ms);
          }),

          const SizedBox(height: 28),
          FilledButton.icon(
            onPressed: onAttach,
            icon: const Icon(Icons.attach_file_rounded),
            label: const Text('إرفاق ملف للبدء'),
            style: FilledButton.styleFrom(
              minimumSize: const Size(double.infinity, 48),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14)),
            ),
          ).animate(delay: 700.ms).fadeIn(duration: 350.ms).slideY(
              begin: 0.2, duration: 350.ms),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: () {},
            icon: const Icon(Icons.chat_outlined),
            label: const Text('تحدث مباشرة بدون ملف'),
            style: OutlinedButton.styleFrom(
              minimumSize: const Size(double.infinity, 48),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14)),
            ),
          ).animate(delay: 780.ms).fadeIn(duration: 350.ms),
        ],
      ),
    );
  }
}

class _FeatureCard extends StatelessWidget {
  const _FeatureCard({
    required this.icon,
    required this.title,
    required this.desc,
    required this.cs,
    required this.tt,
  });
  final IconData icon;
  final String title;
  final String desc;
  final ColorScheme cs;
  final TextTheme tt;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: cs.surfaceContainerLow,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: cs.outlineVariant.withAlpha(80)),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: cs.primaryContainer,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, size: 20, color: cs.onPrimaryContainer),
          ),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title,
                  style: tt.bodyMedium
                      ?.copyWith(fontWeight: FontWeight.w600)),
              Text(desc,
                  style: tt.bodySmall
                      ?.copyWith(color: cs.onSurfaceVariant)),
            ],
          ),
        ],
      ),
    );
  }
}

// ── Quick actions ─────────────────────────────────────────────────────────────

class _QuickActions extends StatelessWidget {
  const _QuickActions({required this.state, required this.onAction});
  final AiChatState state;
  final VoidCallback onAction;

  @override
  Widget build(BuildContext context) {
    final notifier =
        ProviderScope.containerOf(context).read(aiChatProvider.notifier);
    final actions = [
      ('تلخيص', Icons.summarize_rounded, notifier.summarizeFile),
      ('استخراج جداول', Icons.table_chart_rounded, notifier.extractTables),
      ('استخراج بيانات', Icons.data_object_rounded, notifier.extractData),
      ('تحليل عقد', Icons.gavel_rounded, notifier.analyzeContract),
      ('تحليل فاتورة', Icons.receipt_rounded, notifier.analyzeInvoice),
      ('صيغ Excel', Icons.functions_rounded, notifier.suggestFormulas),
    ];

    return Container(
      height: 50,
      margin: const EdgeInsets.only(bottom: 2),
      child: ListView.separated(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        scrollDirection: Axis.horizontal,
        itemCount: actions.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (ctx, i) {
          final (label, icon, fn) = actions[i];
          return ActionChip(
            avatar: Icon(icon, size: 15),
            label: Text(label, style: const TextStyle(fontSize: 12)),
            onPressed: () {
              fn();
              onAction();
            },
            padding: const EdgeInsets.symmetric(horizontal: 4),
          );
        },
      ),
    );
  }
}

// ── Input bar ─────────────────────────────────────────────────────────────────

class _InputBar extends StatefulWidget {
  const _InputBar({
    required this.controller,
    required this.state,
    required this.sttAvailable,
    required this.onSend,
    required this.onStartListening,
    required this.onStopListening,
    required this.onAttach,
  });
  final TextEditingController controller;
  final AiChatState state;
  final bool sttAvailable;
  final VoidCallback onSend;
  final VoidCallback onStartListening;
  final VoidCallback onStopListening;
  final VoidCallback onAttach;

  @override
  State<_InputBar> createState() => _InputBarState();
}

class _InputBarState extends State<_InputBar> {
  bool _hasText = false;

  @override
  void initState() {
    super.initState();
    widget.controller.addListener(() {
      final hasText = widget.controller.text.trim().isNotEmpty;
      if (hasText != _hasText) setState(() => _hasText = hasText);
    });
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final isListening = widget.state.isListeningVoice;

    return SafeArea(
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
        decoration: BoxDecoration(
          color: cs.surface,
          border: Border(
              top: BorderSide(color: cs.outlineVariant.withAlpha(100))),
          boxShadow: [
            BoxShadow(
                color: cs.shadow.withAlpha(20),
                blurRadius: 8,
                offset: const Offset(0, -2)),
          ],
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            // ── Attach button ──────────────────────────────────────────
            _BarIconButton(
              icon: Icons.attach_file_rounded,
              color: cs.onSurfaceVariant,
              onTap: widget.onAttach,
            ),
            const SizedBox(width: 8),

            // ── Text field ─────────────────────────────────────────────
            Expanded(
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                decoration: BoxDecoration(
                  color: isListening
                      ? cs.errorContainer.withAlpha(80)
                      : cs.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(24),
                  border: isListening
                      ? Border.all(color: cs.error, width: 1.5)
                      : null,
                ),
                child: TextField(
                  controller: widget.controller,
                  onSubmitted: (_) => widget.onSend(),
                  textInputAction: TextInputAction.send,
                  decoration: InputDecoration(
                    hintText: isListening
                        ? '🎤 جارٍ الاستماع...'
                        : 'اكتب سؤالك هنا...',
                    border: InputBorder.none,
                    contentPadding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 10),
                    isDense: true,
                  ),
                  maxLines: 5,
                  minLines: 1,
                ),
              ),
            ),
            const SizedBox(width: 8),

            // ── Voice / Send button ────────────────────────────────────
            AnimatedSwitcher(
              duration: const Duration(milliseconds: 200),
              child: _hasText
                  ? _SendButton(
                      isLoading: widget.state.isLoading,
                      onSend: widget.onSend,
                      cs: cs,
                    )
                  : _VoiceButton(
                      sttAvailable: widget.sttAvailable,
                      isListening: isListening,
                      onStartListening: widget.onStartListening,
                      onStopListening: widget.onStopListening,
                      cs: cs,
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SendButton extends StatelessWidget {
  const _SendButton(
      {required this.isLoading,
      required this.onSend,
      required this.cs});
  final bool isLoading;
  final VoidCallback onSend;
  final ColorScheme cs;

  @override
  Widget build(BuildContext context) {
    return FilledButton(
      onPressed: isLoading ? null : onSend,
      style: FilledButton.styleFrom(
        shape: const CircleBorder(),
        padding: const EdgeInsets.all(12),
        minimumSize: Size.zero,
      ),
      child: isLoading
          ? const SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(
                  strokeWidth: 2.5, color: Colors.white))
          : const Icon(Icons.send_rounded, size: 20),
    );
  }
}

class _VoiceButton extends StatelessWidget {
  const _VoiceButton({
    required this.sttAvailable,
    required this.isListening,
    required this.onStartListening,
    required this.onStopListening,
    required this.cs,
  });
  final bool sttAvailable;
  final bool isListening;
  final VoidCallback onStartListening;
  final VoidCallback onStopListening;
  final ColorScheme cs;

  @override
  Widget build(BuildContext context) {
    if (!sttAvailable) {
      return _BarIconButton(
        icon: Icons.mic_off_rounded,
        color: cs.onSurfaceVariant.withAlpha(100),
        onTap: () {},
      );
    }
    return AnimatedContainer(
      duration: const Duration(milliseconds: 200),
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: isListening ? cs.error : cs.primaryContainer,
        boxShadow: isListening
            ? [
                BoxShadow(
                    color: cs.error.withAlpha(100),
                    blurRadius: 12,
                    spreadRadius: 2)
              ]
            : null,
      ),
      child: IconButton(
        icon: Icon(
          isListening ? Icons.stop_rounded : Icons.mic_rounded,
          color: isListening ? cs.onError : cs.onPrimaryContainer,
          size: 22,
        ),
        onPressed: isListening ? onStopListening : onStartListening,
      ),
    );
  }
}

class _BarIconButton extends StatelessWidget {
  const _BarIconButton(
      {required this.icon, required this.color, required this.onTap});
  final IconData icon;
  final Color color;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(20),
      child: Padding(
        padding: const EdgeInsets.all(8),
        child: Icon(icon, color: color, size: 22),
      ),
    );
  }
}
