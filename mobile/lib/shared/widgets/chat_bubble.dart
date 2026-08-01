import 'package:flutter/material.dart';
import 'package:shimmer/shimmer.dart';

import '../../features/ai_assistant/domain/entities/chat_message_entity.dart';

/// Renders a single chat message bubble.
/// User messages are right-aligned, assistant left-aligned (RTL-aware).
class ChatBubble extends StatelessWidget {
  const ChatBubble({required this.message, super.key});
  final ChatMessageEntity message;

  @override
  Widget build(BuildContext context) {
    final isUser = message.role == MessageRole.user;
    final cs = Theme.of(context).colorScheme;

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        mainAxisAlignment:
            isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          if (!isUser) ...[
            CircleAvatar(
              radius: 16,
              backgroundColor: cs.primaryContainer,
              child: Icon(Icons.smart_toy_rounded,
                  size: 18, color: cs.onPrimaryContainer),
            ),
            const SizedBox(width: 8),
          ],

          Flexible(
            child: Container(
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.78,
              ),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: isUser ? cs.primary : cs.surfaceContainerHighest,
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(18),
                  topRight: const Radius.circular(18),
                  bottomLeft: Radius.circular(isUser ? 18 : 4),
                  bottomRight: Radius.circular(isUser ? 4 : 18),
                ),
              ),
              child: message.isStreaming
                  ? _buildStreamingIndicator(cs)
                  : Text(
                      message.content,
                      style: TextStyle(
                        color: isUser ? cs.onPrimary : cs.onSurface,
                        height: 1.5,
                      ),
                    ),
            ),
          ),

          if (isUser) const SizedBox(width: 8),
        ],
      ),
    );
  }

  Widget _buildStreamingIndicator(ColorScheme cs) {
    return Shimmer.fromColors(
      baseColor: cs.onSurfaceVariant,
      highlightColor: cs.onSurface,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: List.generate(
          3,
          (i) => Container(
            margin: const EdgeInsets.symmetric(horizontal: 3),
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: cs.onSurfaceVariant,
              shape: BoxShape.circle,
            ),
          ),
        ),
      ),
    );
  }
}
