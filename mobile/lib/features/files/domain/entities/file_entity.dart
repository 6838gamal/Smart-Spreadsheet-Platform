import 'package:freezed_annotation/freezed_annotation.dart';

part 'file_entity.freezed.dart';

@freezed
class FileEntity with _$FileEntity {
  const factory FileEntity({
    required int id,
    required String name,
    required String originalName,
    required String extension,
    required int sizeBytes,
    required String status,
    required DateTime uploadedAt,
    DateTime? processedAt,
    bool? isFavorite,
    String? downloadUrl,
    Map<String, dynamic>? metadata,
  }) = _FileEntity;
}

extension FileEntityX on FileEntity {
  String get sizeFormatted {
    if (sizeBytes < 1024) return '$sizeBytes B';
    if (sizeBytes < 1024 * 1024) return '${(sizeBytes / 1024).toStringAsFixed(1)} KB';
    return '${(sizeBytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }

  String get typeIcon {
    return switch (extension.toLowerCase()) {
      'pdf' => '📄',
      'xlsx' || 'xls' || 'xlsb' || 'xlsm' => '📊',
      'docx' || 'doc' => '📝',
      'pptx' || 'ppt' => '📑',
      'csv' => '📋',
      'jpg' || 'jpeg' || 'png' || 'webp' || 'tiff' => '🖼️',
      'txt' => '📃',
      _ => '📁',
    };
  }
}
