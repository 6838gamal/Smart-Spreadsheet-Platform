import 'dart:developer' as developer;
import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/services.dart';
import 'package:permission_handler/permission_handler.dart';

/// Result of a file pick operation.
class FilePickResult {
  const FilePickResult._({this.path, this.name, this.bytes, this.errorMessage});

  final String? path;
  final String? name;
  final Uint8List? bytes;

  /// Non-null when something went wrong (user-visible, in Arabic).
  final String? errorMessage;

  bool get success => errorMessage == null && (path != null || bytes != null);
  bool get cancelled => errorMessage == null && path == null && bytes == null;

  static const FilePickResult _cancelled = FilePickResult._();

  factory FilePickResult.error(String msg) =>
      FilePickResult._(errorMessage: msg);

  factory FilePickResult.ok({String? path, String? name, Uint8List? bytes}) =>
      FilePickResult._(path: path, name: name, bytes: bytes);
}

/// Requests the appropriate storage permission on Android (SDK ≤ 32).
/// On Android 13+, the system document picker (SAF) works without permissions.
/// On iOS, permissions are handled by the system automatically.
Future<bool> _ensureStoragePermission() async {
  if (!Platform.isAndroid) return true;

  // Android 13+ (API 33+): SAF picker needs no runtime permission for documents.
  // We check READ_EXTERNAL_STORAGE only for older SDKs.
  final status = await Permission.storage.status;
  if (status.isGranted || status.isLimited) return true;
  if (status.isPermanentlyDenied) return false;

  final result = await Permission.storage.request();
  return result.isGranted || result.isLimited;
}

/// Opens the file picker with proper permission handling and error reporting.
///
/// [allowedExtensions] – optional list; pass null to allow any file type.
/// [withData] – set true to load bytes into memory (for small files or web).
Future<FilePickResult> pickFile({
  List<String>? allowedExtensions,
  bool withData = false,
}) async {
  try {
    // On Android ≤ 12, request READ_EXTERNAL_STORAGE before using FilePicker.
    if (Platform.isAndroid) {
      final granted = await _ensureStoragePermission();
      if (!granted) {
        // Even if permission is denied, SAF-based picker may still work on 13+.
        // We continue rather than blocking the user immediately.
        developer.log(
          'Storage permission not granted – proceeding with SAF picker.',
          name: 'FilePickerUtil',
        );
      }
    }

    final FileType type =
        (allowedExtensions != null && allowedExtensions.isNotEmpty)
            ? FileType.custom
            : FileType.any;

    final result = await FilePicker.platform.pickFiles(
      allowMultiple: false,
      type: type,
      allowedExtensions:
          (type == FileType.custom) ? allowedExtensions : null,
      withData: withData,
      withReadStream: false,
    );

    if (result == null || result.files.isEmpty) {
      return FilePickResult._cancelled;
    }

    final file = result.files.first;

    // On mobile, we prefer the file path; on web, only bytes are available.
    if (file.path != null) {
      return FilePickResult.ok(path: file.path, name: file.name);
    }

    if (file.bytes != null) {
      return FilePickResult.ok(bytes: file.bytes, name: file.name);
    }

    // Path is null and no bytes – this can happen with some SAF URIs on older
    // Android. Fall back to withData mode and retry once.
    developer.log(
      'file.path is null, retrying with withData=true',
      name: 'FilePickerUtil',
    );
    final retry = await FilePicker.platform.pickFiles(
      allowMultiple: false,
      type: type,
      allowedExtensions:
          (type == FileType.custom) ? allowedExtensions : null,
      withData: true,
    );

    if (retry == null || retry.files.isEmpty) return FilePickResult._cancelled;
    final retryFile = retry.files.first;

    if (retryFile.bytes != null) {
      return FilePickResult.ok(bytes: retryFile.bytes, name: retryFile.name);
    }

    return FilePickResult.error('تعذّر الوصول إلى الملف، حاول مجدداً');
  } on PlatformException catch (e, st) {
    developer.log(
      'FilePicker PlatformException: ${e.code} – ${e.message}',
      name: 'FilePickerUtil',
      error: e,
      stackTrace: st,
    );
    if (e.code == 'read_external_storage_denied' ||
        e.message?.contains('permission') == true) {
      return FilePickResult.error(
        'لا يملك التطبيق إذن الوصول للملفات. '
        'يرجى منح الإذن من إعدادات الجهاز.',
      );
    }
    return FilePickResult.error('خطأ في اختيار الملف (${e.code})');
  } catch (e, st) {
    developer.log(
      'FilePicker unexpected error: $e',
      name: 'FilePickerUtil',
      error: e,
      stackTrace: st,
    );
    return FilePickResult.error('حدث خطأ غير متوقع أثناء اختيار الملف');
  }
}
