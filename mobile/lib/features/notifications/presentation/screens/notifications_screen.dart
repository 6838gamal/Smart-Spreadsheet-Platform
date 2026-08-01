import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:timeago/timeago.dart' as timeago;

import '../providers/notifications_provider.dart';

class NotificationsScreen extends ConsumerWidget {
  const NotificationsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(notificationsProvider);
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('الإشعارات'),
        actions: [
          if (state.notifications.isNotEmpty)
            TextButton(
              onPressed: () =>
                  ref.read(notificationsProvider.notifier).markAllRead(),
              child: const Text('تعيين الكل كمقروء'),
            ),
        ],
      ),
      body: state.notifications.isEmpty
          ? Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.notifications_none_rounded,
                      size: 64, color: cs.outlineVariant),
                  const SizedBox(height: 16),
                  Text('لا توجد إشعارات',
                      style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  Text(
                    'ستظهر إشعارات التحويل والتحليل هنا',
                    style: Theme.of(context)
                        .textTheme
                        .bodyMedium
                        ?.copyWith(color: cs.onSurfaceVariant),
                  ),
                ],
              ),
            )
          : ListView.separated(
              padding: const EdgeInsets.all(12),
              itemCount: state.notifications.length,
              separatorBuilder: (_, __) => const SizedBox(height: 8),
              itemBuilder: (ctx, i) {
                final notif = state.notifications[i];
                return _NotificationTile(notification: notif)
                    .animate(delay: (i * 30).ms)
                    .fadeIn(duration: 250.ms)
                    .slideX(begin: 0.05, duration: 250.ms);
              },
            ),
    );
  }
}

class _NotificationTile extends ConsumerWidget {
  const _NotificationTile({required this.notification});
  final NotificationItem notification;

  IconData get _icon => switch (notification.type) {
        NotificationType.conversion => Icons.transform_rounded,
        NotificationType.analysis => Icons.analytics_rounded,
        NotificationType.shared => Icons.share_rounded,
        NotificationType.quota => Icons.warning_amber_rounded,
        NotificationType.update => Icons.system_update_rounded,
      };

  Color _iconColor(ColorScheme cs) => switch (notification.type) {
        NotificationType.conversion => cs.primary,
        NotificationType.analysis => cs.secondary,
        NotificationType.shared => cs.tertiary,
        NotificationType.quota => Colors.orange,
        NotificationType.update => cs.primary,
      };

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cs = Theme.of(context).colorScheme;

    return Dismissible(
      key: Key(notification.id),
      direction: DismissDirection.endToStart,
      background: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 16),
        decoration: BoxDecoration(
          color: cs.errorContainer,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Icon(Icons.delete_rounded, color: cs.onErrorContainer),
      ),
      onDismissed: (_) => ref
          .read(notificationsProvider.notifier)
          .dismiss(notification.id),
      child: ListTile(
        onTap: () =>
            ref.read(notificationsProvider.notifier).markRead(notification.id),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(
            color: notification.isRead
                ? cs.outlineVariant
                : cs.primary.withValues(alpha: 0.3),
            width: notification.isRead ? 0.5 : 1.5,
          ),
        ),
        tileColor: notification.isRead
            ? null
            : cs.primaryContainer.withValues(alpha: 0.2),
        leading: Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            color: _iconColor(cs).withValues(alpha: 0.15),
            shape: BoxShape.circle,
          ),
          child: Icon(_icon, color: _iconColor(cs), size: 22),
        ),
        title: Text(
          notification.title,
          style: TextStyle(
            fontWeight:
                notification.isRead ? FontWeight.normal : FontWeight.w600,
          ),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(notification.body),
            const SizedBox(height: 2),
            Text(
              timeago.format(notification.createdAt, locale: 'ar'),
              style: Theme.of(context)
                  .textTheme
                  .bodySmall
                  ?.copyWith(color: cs.onSurfaceVariant),
            ),
          ],
        ),
        isThreeLine: true,
      ),
    );
  }
}
