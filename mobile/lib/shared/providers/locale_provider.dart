import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/constants/storage_keys.dart';
import '../../core/storage/hive_storage.dart';

/// Persists and exposes the user's chosen locale (AR or EN).
final localeProvider = StateNotifierProvider<LocaleNotifier, Locale>((ref) {
  return LocaleNotifier();
});

class LocaleNotifier extends StateNotifier<Locale> {
  LocaleNotifier() : super(_loadSaved());

  static Locale _loadSaved() {
    final saved = HiveStorage.get<String>(StorageKeys.locale);
    return saved != null ? Locale(saved) : const Locale('ar');
  }

  Future<void> setLocale(Locale locale) async {
    state = locale;
    await HiveStorage.set(StorageKeys.locale, locale.languageCode);
  }

  bool get isArabic => state.languageCode == 'ar';
}
