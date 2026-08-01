import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';

enum NotificationType { conversion, analysis, shared, quota, update }

class NotificationItem {
  final String id;
  final NotificationType type;
  final String title;
  final String body;
  final bool isRead;
  final DateTime createdAt;

  const NotificationItem({
    required this.id,
    required this.type,
    required this.title,
    required this.body,
    required this.isRead,
    required this.createdAt,
  });

  NotificationItem copyWith({bool? isRead}) => NotificationItem(
        id: id,
        type: type,
        title: title,
        body: body,
        isRead: isRead ?? this.isRead,
        createdAt: createdAt,
      );
}

class NotificationsState {
  final List<NotificationItem> notifications;
  const NotificationsState({this.notifications = const []});

  int get unreadCount => notifications.where((n) => !n.isRead).length;

  NotificationsState copyWith({List<NotificationItem>? notifications}) =>
      NotificationsState(notifications: notifications ?? this.notifications);
}

final notificationsProvider =
    StateNotifierProvider<NotificationsNotifier, NotificationsState>((ref) {
  return NotificationsNotifier();
});

class NotificationsNotifier extends StateNotifier<NotificationsState> {
  static const _uuid = Uuid();

  NotificationsNotifier() : super(const NotificationsState()) {
    // Seed with example notifications for development
    _seedDemoNotifications();
  }

  void _seedDemoNotifications() {
    state = NotificationsState(notifications: [
      NotificationItem(
        id: _uuid.v4(),
        type: NotificationType.conversion,
        title: 'تم التحويل بنجاح',
        body: 'تم تحويل "report.pdf" إلى Excel بنجاح',
        isRead: false,
        createdAt: DateTime.now().subtract(const Duration(minutes: 5)),
      ),
      NotificationItem(
        id: _uuid.v4(),
        type: NotificationType.analysis,
        title: 'اكتمل التحليل',
        body: 'تم تحليل "contract.pdf" — 3 عقود مكتشفة',
        isRead: false,
        createdAt: DateTime.now().subtract(const Duration(hours: 1)),
      ),
      NotificationItem(
        id: _uuid.v4(),
        type: NotificationType.quota,
        title: 'تحذير: الحد اليومي',
        body: 'لقد استهلكت 80% من حصتك اليومية من التحويلات',
        isRead: true,
        createdAt: DateTime.now().subtract(const Duration(hours: 3)),
      ),
    ]);
  }

  void add(NotificationItem item) {
    state = state.copyWith(
        notifications: [item, ...state.notifications]);
  }

  void markRead(String id) {
    state = state.copyWith(
      notifications: state.notifications
          .map((n) => n.id == id ? n.copyWith(isRead: true) : n)
          .toList(),
    );
  }

  void markAllRead() {
    state = state.copyWith(
      notifications:
          state.notifications.map((n) => n.copyWith(isRead: true)).toList(),
    );
  }

  void dismiss(String id) {
    state = state.copyWith(
      notifications: state.notifications.where((n) => n.id != id).toList(),
    );
  }
}
