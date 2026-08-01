import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

extension DateTimeX on DateTime {
  String get arabicDate {
    return DateFormat('dd/MM/yyyy', 'ar').format(this);
  }

  String get arabicDateTime {
    return DateFormat('dd/MM/yyyy HH:mm', 'ar').format(this);
  }

  bool get isToday {
    final now = DateTime.now();
    return year == now.year && month == now.month && day == now.day;
  }
}

extension StringX on String {
  bool get isArabic => contains(RegExp(r'[\u0600-\u06FF]'));

  String get capitalize =>
      isNotEmpty ? this[0].toUpperCase() + substring(1) : this;

  /// Truncate to maxLength chars, appending '…'
  String truncate(int maxLength) =>
      length <= maxLength ? this : '${substring(0, maxLength)}…';
}

extension NumX on num {
  /// Format bytes as human-readable size string
  String get bytesToHuman {
    if (this < 1024) return '${toStringAsFixed(0)} B';
    if (this < 1024 * 1024) return '${(this / 1024).toStringAsFixed(1)} KB';
    if (this < 1024 * 1024 * 1024) {
      return '${(this / (1024 * 1024)).toStringAsFixed(1)} MB';
    }
    return '${(this / (1024 * 1024 * 1024)).toStringAsFixed(2)} GB';
  }
}

extension ContextX on BuildContext {
  ColorScheme get colors => Theme.of(this).colorScheme;
  TextTheme get textTheme => Theme.of(this).textTheme;
  Size get screenSize => MediaQuery.sizeOf(this);
  bool get isTablet => screenSize.width >= 600;
  bool get isDesktop => screenSize.width >= 1024;
  EdgeInsets get padding => MediaQuery.paddingOf(this);

  void showSnackBar(String message, {bool isError = false}) {
    ScaffoldMessenger.of(this).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: isError ? colors.error : null,
      ),
    );
  }
}
