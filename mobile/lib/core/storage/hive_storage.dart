import 'package:hive_flutter/hive_flutter.dart';

import '../constants/app_constants.dart';

/// Wrapper around Hive providing a simple typed key-value API.
/// Hive is used for non-sensitive data: settings, file metadata cache,
/// offline upload queue. Sensitive data (tokens, PIN) go to SecureStorage.
class HiveStorage {
  HiveStorage._();

  static late Box<dynamic> _settings;
  static late Box<dynamic> _files;
  static late Box<dynamic> _offlineQueue;

  static Future<void> init() async {
    await Hive.initFlutter();
    _settings = await Hive.openBox<dynamic>(AppConstants.settingsBox);
    _files = await Hive.openBox<dynamic>(AppConstants.filesBox);
    _offlineQueue = await Hive.openBox<dynamic>(AppConstants.offlineQueueBox);
  }

  // ── Settings box ─────────────────────────────────────────────────────────────

  static T? get<T>(String key) => _settings.get(key) as T?;

  static Future<void> set(String key, dynamic value) =>
      _settings.put(key, value);

  static Future<void> delete(String key) => _settings.delete(key);

  // ── Files metadata cache ──────────────────────────────────────────────────────

  static Box<dynamic> get filesBox => _files;

  // ── Offline queue ─────────────────────────────────────────────────────────────

  static Box<dynamic> get offlineQueueBox => _offlineQueue;

  // ── Clear all (logout) ────────────────────────────────────────────────────────

  static Future<void> clearAll() async {
    await _settings.clear();
    await _files.clear();
    await _offlineQueue.clear();
  }
}
