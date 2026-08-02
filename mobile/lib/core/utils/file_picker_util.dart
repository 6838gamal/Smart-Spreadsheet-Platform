import 'dart:developer' as developer;
import 'dart:io';

import 'package:device_info_plus/device_info_plus.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:permission_handler/permission_handler.dart';

// ── Result type ───────────────────────────────────────────────────────────────

/// Result of a file pick operation.
class FilePickResult {
  const FilePickResult._({
    this.path,
    this.name,
    this.bytes,
    this.errorMessage,
    this.needsSettings = false,
  });

  final String? path;
  final String? name;
  final Uint8List? bytes;

  /// Non-null when something went wrong (user-visible Arabic message).
  final String? errorMessage;

  /// True when the user must open Settings to grant the permission manually.
  final bool needsSettings;

  bool get success => errorMessage == null && (path != null || bytes != null);
  bool get cancelled => errorMessage == null && path == null && bytes == null;

  static const FilePickResult _cancelled = FilePickResult._();

  factory FilePickResult.error(String msg, {bool needsSettings = false}) =>
      FilePickResult._(errorMessage: msg, needsSettings: needsSettings);

  factory FilePickResult.ok({String? path, String? name, Uint8List? bytes}) =>
      FilePickResult._(path: path, name: name, bytes: bytes);
}

// ── Permission helpers ────────────────────────────────────────────────────────

/// Returns the Android SDK integer (e.g. 33 for Android 13), or 0 on non-Android.
Future<int> _androidSdk() async {
  if (!Platform.isAndroid) return 0;
  final info = await DeviceInfoPlugin().androidInfo;
  return info.version.sdkInt;
}

/// Requests the correct storage permission based on Android SDK version.
///
/// - SDK ≥ 33 (Android 13+): READ_MEDIA_IMAGES/VIDEO/AUDIO for media files,
///   but documents are accessed via SAF without any runtime permission.
///   We request the media trio so the system dialog appears for completeness.
/// - SDK ≤ 32 (Android ≤ 12): READ_EXTERNAL_STORAGE — classic dialog.
///
/// Returns one of: `granted`, `denied`, `permanentlyDenied`.
Future<PermissionStatus> _requestStoragePermission(int sdk) async {
  if (sdk >= 33) {
    // Android 13+: request media permissions (photos/videos/audio).
    // For picking arbitrary documents via SAF, these aren't strictly required,
    // but requesting them gives the user the expected "allow access" dialog.
    final results = await [
      Permission.photos,
      Permission.videos,
      Permission.audio,
    ].request();

    // If any of the three is permanently denied, bubble that up.
    if (results.values.any((s) => s.isPermanentlyDenied)) {
      return PermissionStatus.permanentlyDenied;
    }
    // If all three are granted, we're good.
    if (results.values.every((s) => s.isGranted || s.isLimited)) {
      return PermissionStatus.granted;
    }
    // Partially denied — SAF can still open for documents.
    return PermissionStatus.denied;
  } else {
    // Android ≤ 12: classic READ_EXTERNAL_STORAGE dialog.
    return Permission.storage.request();
  }
}

// ── Public API ────────────────────────────────────────────────────────────────

/// Opens the file picker after requesting the correct storage permission.
///
/// On Android 13+, shows the media-access dialog (photos/videos/audio).
/// On Android ≤ 12, shows the classic storage-access dialog.
/// On iOS, the system sheet handles permissions automatically.
///
/// [allowedExtensions] – optional whitelist (e.g. `['xlsx','csv']`).
/// [withData] – load file bytes into memory (use for small files only).
Future<FilePickResult> pickFile({
  List<String>? allowedExtensions,
  bool withData = false,
}) async {
  try {
    // ── 1. Permission gate (Android only) ───────────────────────────────────
    if (Platform.isAndroid) {
      final sdk = await _androidSdk();

      // Check current status before requesting.
      final Permission primaryPermission =
          sdk >= 33 ? Permission.photos : Permission.storage;
      final currentStatus = await primaryPermission.status;

      if (currentStatus.isPermanentlyDenied) {
        // User previously denied with "Don't ask again" — direct to settings.
        return FilePickResult.error(
          'تم رفض الإذن نهائياً. يُرجى فتح الإعدادات ومنح صلاحية الوصول للملفات يدوياً.',
          needsSettings: true,
        );
      }

      if (!currentStatus.isGranted && !currentStatus.isLimited) {
        // Permission not yet granted — show the dialog.
        final result = await _requestStoragePermission(sdk);

        if (result.isPermanentlyDenied) {
          return FilePickResult.error(
            'تم رفض الإذن نهائياً. يُرجى فتح الإعدادات ومنح صلاحية الوصول للملفات يدوياً.',
            needsSettings: true,
          );
        }

        if (result.isDenied) {
          // User tapped "Deny" — for documents, SAF still works on Android 13+,
          // so we continue. On Android ≤ 12, file access may fail.
          developer.log(
            'Storage permission denied (SDK $sdk) — continuing with SAF.',
            name: 'FilePickerUtil',
          );
          if (sdk < 33) {
            // On old Android without permission, the picker will likely fail.
            return FilePickResult.error(
              'لا يمكن الوصول للملفات بدون الإذن. يُرجى السماح بالوصول عند الطلب.',
            );
          }
        }
      }
    }

    // ── 2. Open file picker ─────────────────────────────────────────────────
    final FileType type =
        (allowedExtensions != null && allowedExtensions.isNotEmpty)
            ? FileType.custom
            : FileType.any;

    final result = await FilePicker.platform.pickFiles(
      allowMultiple: false,
      type: type,
      allowedExtensions: type == FileType.custom ? allowedExtensions : null,
      withData: withData,
      withReadStream: false,
    );

    if (result == null || result.files.isEmpty) return FilePickResult._cancelled;

    final file = result.files.first;

    if (file.path != null) {
      return FilePickResult.ok(path: file.path, name: file.name);
    }
    if (file.bytes != null) {
      return FilePickResult.ok(bytes: file.bytes, name: file.name);
    }

    // ── 3. Fallback: retry with withData=true ───────────────────────────────
    // Some SAF URIs on older Android don't resolve to a filesystem path.
    developer.log(
      'file.path is null — retrying with withData=true',
      name: 'FilePickerUtil',
    );
    final retry = await FilePicker.platform.pickFiles(
      allowMultiple: false,
      type: type,
      allowedExtensions: type == FileType.custom ? allowedExtensions : null,
      withData: true,
    );

    if (retry == null || retry.files.isEmpty) return FilePickResult._cancelled;
    final retryFile = retry.files.first;

    if (retryFile.bytes != null) {
      return FilePickResult.ok(bytes: retryFile.bytes, name: retryFile.name);
    }

    return FilePickResult.error('تعذّر الوصول إلى الملف، يُرجى المحاولة مجدداً.');
  } on PlatformException catch (e, st) {
    developer.log(
      'FilePicker PlatformException: ${e.code} — ${e.message}',
      name: 'FilePickerUtil',
      error: e,
      stackTrace: st,
    );
    if (e.code.contains('permission') ||
        e.message?.toLowerCase().contains('permission') == true ||
        e.code == 'read_external_storage_denied') {
      return FilePickResult.error(
        'لا يملك التطبيق إذن الوصول للملفات. يُرجى منح الإذن من الإعدادات.',
        needsSettings: true,
      );
    }
    return FilePickResult.error('خطأ أثناء اختيار الملف: ${e.message ?? e.code}');
  } catch (e, st) {
    developer.log(
      'FilePicker unexpected error: $e',
      name: 'FilePickerUtil',
      error: e,
      stackTrace: st,
    );
    return FilePickResult.error('حدث خطأ غير متوقع أثناء اختيار الملف.');
  }
}

// ── Settings helper ───────────────────────────────────────────────────────────

/// Shows a dialog guiding the user to open App Settings when a permission
/// has been permanently denied.
Future<void> showPermissionSettingsDialog(BuildContext context) {
  return showDialog(
    context: context,
    builder: (ctx) => AlertDialog(
      title: const Text('صلاحية الوصول مطلوبة'),
      content: const Text(
        'تم رفض إذن الوصول للملفات نهائياً.\n'
        'يُرجى فتح إعدادات التطبيق ومنح صلاحية التخزين يدوياً.',
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(ctx).pop(),
          child: const Text('إلغاء'),
        ),
        FilledButton(
          onPressed: () {
            Navigator.of(ctx).pop();
            openAppSettings();
          },
          child: const Text('فتح الإعدادات'),
        ),
      ],
    ),
  );
}
