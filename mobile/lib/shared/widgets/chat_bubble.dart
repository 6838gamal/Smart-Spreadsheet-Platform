import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:shimmer/shimmer.dart';

import '../../features/ai_assistant/domain/entities/chat_message_entity.dart';

class ChatBubble extends StatefulWidget {
  const ChatBubble({required this.message, super.key});
  final ChatMessageEntity message;

  @override
  State<ChatBubble> createState() => _ChatBubbleState();
}

class _ChatBubbleState extends State<ChatBubble> {
  static final FlutterTts _tts = FlutterTts();
  bool _isSpeaking = false;

  @override
  void dispose() {
    if (_isSpeaking) _tts.stop();
    super.dispose();
  }

  Future<void> _toggleSpeech() async {
    if (_isSpeaking) {
      await _tts.stop();
      if (mounted) setState(() => _isSpeaking = false);
      return;
    }
    await _tts.setLanguage(
      _containsArabic(widget.message.content) ? 'ar-SA' : 'en-US',
    );
    await _tts.setSpeechRate(0.45);
    await _tts.setPitch(1.0);

    _tts.setCompletionHandler(() {
      if (mounted) setState(() => _isSpeaking = false);
    });

    setState(() => _isSpeaking = true);
    await _tts.speak(_stripMarkdown(widget.message.content));
  }

  bool _containsArabic(String text) =>
      RegExp(r'[\u0600-\u06FF]').hasMatch(text);

  String _stripMarkdown(String text) => text
      .replaceAll(RegExp(r'\*\*(.+?)\*\*'), r'$1')
      .replaceAll(RegExp(r'\*(.+?)\*'), r'$1')
      .replaceAll(RegExp(r'`(.+?)`'), r'$1')
      .replaceAll(RegExp(r'^#+\s+', multiLine: true), '')
      .replaceAll(RegExp(r'^[-•]\s+', multiLine: true), '')
      .trim();

  @override
  Widget build(BuildContext context) {
    final isUser = widget.message.role == MessageRole.user;
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(context).textTheme;

    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Column(
        crossAxisAlignment:
            isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment:
                isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              // ── Avatar (assistant only) ────────────────────────────────
              if (!isUser) ...[
                _AssistantAvatar(cs: cs),
                const SizedBox(width: 8),
              ],

              // ── Bubble ─────────────────────────────────────────────────
              Flexible(
                child: Container(
                  constraints: BoxConstraints(
                    maxWidth: MediaQuery.of(context).size.width * 0.80,
                  ),
                  decoration: BoxDecoration(
                    color: isUser
                        ? cs.primary
                        : widget.message.isError
                            ? cs.errorContainer.withAlpha(180)
                            : cs.surfaceContainerHighest,
                    borderRadius: BorderRadius.only(
                      topLeft: const Radius.circular(20),
                      topRight: const Radius.circular(20),
                      bottomLeft: Radius.circular(isUser ? 20 : 4),
                      bottomRight: Radius.circular(isUser ? 4 : 20),
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: cs.shadow.withAlpha(20),
                        blurRadius: 4,
                        offset: const Offset(0, 2),
                      ),
                    ],
                  ),
                  child: widget.message.isStreaming
                      ? _ThinkingIndicator(cs: cs)
                      : _BubbleContent(
                          message: widget.message,
                          isUser: isUser,
                          cs: cs,
                          tt: tt,
                        ),
                ),
              ),

              if (isUser) const SizedBox(width: 8),
            ],
          ),

          // ── Toolbar (assistant only, non-streaming, non-error) ──────────
          if (!isUser &&
              !widget.message.isStreaming &&
              !widget.message.isError &&
              widget.message.content.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(left: 48, top: 4),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // TTS
                  _ToolbarButton(
                    icon: _isSpeaking
                        ? Icons.stop_rounded
                        : Icons.volume_up_outlined,
                    label: _isSpeaking ? 'إيقاف' : 'استماع',
                    color: _isSpeaking ? cs.error : cs.onSurfaceVariant,
                    onTap: _toggleSpeech,
                  ),
                  const SizedBox(width: 4),
                  // Copy
                  _ToolbarButton(
                    icon: Icons.copy_outlined,
                    label: 'نسخ',
                    color: cs.onSurfaceVariant,
                    onTap: () {
                      Clipboard.setData(
                          ClipboardData(text: widget.message.content));
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('تم النسخ'),
                          duration: Duration(seconds: 1),
                          behavior: SnackBarBehavior.floating,
                        ),
                      );
                    },
                  ),
                  // Model badge
                  if (widget.message.modelName != null) ...[
                    const SizedBox(width: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: cs.secondaryContainer,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        widget.message.modelName!,
                        style: tt.labelSmall?.copyWith(
                            color: cs.onSecondaryContainer, fontSize: 9),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ],
              ),
            ),

          // ── Timestamp ──────────────────────────────────────────────────
          if (!widget.message.isStreaming)
            Padding(
              padding: EdgeInsets.only(
                left: isUser ? 0 : 48,
                right: isUser ? 0 : 0,
                top: 2,
              ),
              child: Text(
                _formatTime(widget.message.timestamp),
                style: tt.labelSmall
                    ?.copyWith(color: cs.onSurfaceVariant.withAlpha(140)),
              ),
            ),
        ],
      ),
    );
  }

  String _formatTime(DateTime dt) {
    final h = dt.hour.toString().padLeft(2, '0');
    final m = dt.minute.toString().padLeft(2, '0');
    return '$h:$m';
  }
}

// ── Sub-widgets ───────────────────────────────────────────────────────────────

class _AssistantAvatar extends StatelessWidget {
  const _AssistantAvatar({required this.cs});
  final ColorScheme cs;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 32,
      height: 32,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [cs.primary, cs.tertiary],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        shape: BoxShape.circle,
      ),
      child: Icon(Icons.auto_awesome_rounded, size: 16, color: cs.onPrimary),
    );
  }
}

class _BubbleContent extends StatelessWidget {
  const _BubbleContent({
    required this.message,
    required this.isUser,
    required this.cs,
    required this.tt,
  });
  final ChatMessageEntity message;
  final bool isUser;
  final ColorScheme cs;
  final TextTheme tt;

  @override
  Widget build(BuildContext context) {
    final textColor = isUser
        ? cs.onPrimary
        : message.isError
            ? cs.onErrorContainer
            : cs.onSurface;

    if (isUser) {
      // User messages: plain text, right-aligned
      return Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        child: Text(
          message.content,
          style: tt.bodyMedium?.copyWith(color: textColor, height: 1.5),
          textDirection: TextDirection.rtl,
        ),
      );
    }

    // Assistant messages: Markdown rendering
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      child: MarkdownBody(
        data: message.content,
        styleSheet: MarkdownStyleSheet(
          p: tt.bodyMedium?.copyWith(color: textColor, height: 1.6),
          strong: tt.bodyMedium?.copyWith(
              color: textColor, fontWeight: FontWeight.bold),
          em: tt.bodyMedium?.copyWith(
              color: textColor, fontStyle: FontStyle.italic),
          code: tt.bodySmall?.copyWith(
            color: cs.primary,
            backgroundColor: cs.primaryContainer.withAlpha(100),
            fontFamily: 'monospace',
          ),
          codeblockDecoration: BoxDecoration(
            color: cs.primaryContainer.withAlpha(80),
            borderRadius: BorderRadius.circular(8),
          ),
          h1: tt.titleMedium
              ?.copyWith(color: textColor, fontWeight: FontWeight.bold),
          h2: tt.titleSmall
              ?.copyWith(color: textColor, fontWeight: FontWeight.bold),
          h3: tt.bodyLarge
              ?.copyWith(color: textColor, fontWeight: FontWeight.w600),
          listBullet:
              tt.bodyMedium?.copyWith(color: cs.primary),
          blockquoteDecoration: BoxDecoration(
            border: Border(
                left: BorderSide(color: cs.primary, width: 3)),
            color: cs.primaryContainer.withAlpha(40),
          ),
        ),
        selectable: true,
      ),
    );
  }
}

class _ThinkingIndicator extends StatelessWidget {
  const _ThinkingIndicator({required this.cs});
  final ColorScheme cs;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      child: Shimmer.fromColors(
        baseColor: cs.onSurfaceVariant.withAlpha(80),
        highlightColor: cs.primary.withAlpha(200),
        period: const Duration(milliseconds: 1200),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: List.generate(3, (i) {
            return AnimatedContainer(
              duration: Duration(milliseconds: 300 + i * 100),
              margin: const EdgeInsets.symmetric(horizontal: 3),
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                color: cs.onSurfaceVariant,
                shape: BoxShape.circle,
              ),
            );
          }),
        ),
      ),
    );
  }
}

class _ToolbarButton extends StatelessWidget {
  const _ToolbarButton({
    required this.icon,
    required this.label,
    required this.color,
    required this.onTap,
  });
  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 14, color: color),
            const SizedBox(width: 3),
            Text(
              label,
              style: TextStyle(fontSize: 11, color: color),
            ),
          ],
        ),
      ),
    );
  }
}
