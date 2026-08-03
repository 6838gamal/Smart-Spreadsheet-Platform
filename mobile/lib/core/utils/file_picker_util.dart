import 'dart:developer' as developer;
import 'dart:io';

import 'package:device_info_plus/device_info_plus.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart'; // kIsWeb
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:permission_handler/permission_handler.dart';

// ── Result type ───────────────────────────────────────────────────────────────

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
  final String? errorMessage;
  final bool needsSettings;

  bool get success => errorMessage == null && (path != null || bytes != null);
  bool get cancelled => errorMessage == null && path == null && bytes == null;

  static const FilePickResult _cancelled = FilePickResult._();

  factory FilePickResult.error(String msg, {bool needsSettings = false}) =>
      FilePickResult._(errorMessage: msg, needsSettings: needsSettings);

  factory FilePickResult.ok({String? path, String? name, Uint8List? bytes}) =>
      FilePickResult._(path: path, name: name, bytes: bytes);
}

// ── Permission helpers (Android only) ────────────────────────────────────────

Future<int> _androidSdk() async {
  // Platform.isAndroid throws on web — guard with kIsWeb.
  if (kIsWeb || !Platform.isAndroid) return 0;
  final info = await DeviceInfoPlugin().androidInfo;
  return info.version.sdkInt;
}

Future<PermissionStatus> _requestStoragePermission(int sdk) async {
  if (sdk >= 33) {
    final results = await [
      Permission.photos,
      Permission.videos,
      Permission.audio,
    ].request();
    if (results.values.any((s) => s.isPermanentlyDenied)) {
      return PermissionStatus.permanentlyDenied;
    }
    if (results.values.every((s) => s.isGranted || s.isLimited)) {
      return PermissionStatus.granted;
    }
    return PermissionStatus.denied;
  } else {
    return Permission.storage.request();
  }
}

// ── Public API ────────────────────────────────────────────────────────────────

/// Opens the file picker.
///
/// On **Flutter Web**: skips all permission logic and always returns
/// [FilePickResult.bytes] — `path` is always null on web.
///
/// On **Android**: requests storage permission first.
/// On **iOS**: the system sheet handles permissions automatically.
Future<FilePickResult> pickFile({
  List<String>? allowedExtensions,
  bool withData = false,
}) async {
  try {
    // ── 1. Permission gate — Android only, skip entirely on web ─────────────
    if (!kIsWeb && Platform.isAndroid) {
      final sdk = await _androidSdk();
      final Permission primaryPermission =
          sdk >= 33 ? Permission.photos : Permission.storage;
      final currentStatus = await primaryPermission.status;

      if (currentStatus.isPermanentlyDenied) {
        return FilePickResult.error(
          'تم رفض الإذن نهائياً. يُرجى فتح الإعدادات ومنح صلاحية الوصول للملفات يدوياً.',
          needsSettings: true,
        );
      }

      if (!currentStatus.isGranted && !currentStatus.isLimited) {
        final result = await _requestStoragePermission(sdk);

        if (result.isPermanentlyDenied) {
          return FilePickResult.error(
            'تم رفض الإذن نهائياً. يُرجى فتح الإعدادات ومنح صلاحية الوصول للملفات يدوياً.',
            needsSettings: true,
          );
        }

        if (result.isDenied && sdk < 33) {
          return FilePickResult.error(
            'لا يمكن الوصول للملفات بدون الإذن. يُرجى السماح بالوصول عند الطلب.',
          );
        }
      }
    }

    // ── 2. Open file picker ─────────────────────────────────────────────────
    final FileType type =
        (allowedExtensions != null && allowedExtensions.isNotEmpty)
            ? FileType.custom
            : FileType.any;

    // On web, file_picker always returns bytes regardless of withData.
    final effectiveWithData = kIsWeb ? true : withData;

    final result = await FilePicker.platform.pickFiles(
      allowMultiple: false,
      type: type,
      allowedExtensions: type == FileType.custom ? allowedExtensions : null,
      withData: effectiveWithData,
      withReadStream: false,
    );

    if (result == null || result.files.isEmpty) return FilePickResult._cancelled;

    final file = result.files.first;

    // Web: bytes only. Mobile: prefer bytes if loaded, else path.
    if (file.bytes != null) {
      return FilePickResult.ok(bytes: file.bytes, name: file.name);
    }
    if (file.path != null) {
      return FilePickResult.ok(path: file.path, name: file.name);
    }

    // ── 3. Fallback: retry with withData=true (some SAF URIs on old Android) ─
    developer.log(
      'file.path and file.bytes are both null — retrying with withData=true',
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
          onPressed: () async {
            Navigator.of(ctx).pop();
            if (!kIsWeb) await openAppSettings();
          },
          child: const Text('فتح الإعدادات'),
        ),
      ],
    ),
  );
}
