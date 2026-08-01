import '../../domain/entities/file_entity.dart';

/// JSON-serialisable counterpart of [FileEntity].
class FileModel {
  final int id;
  final String name;
  final String originalName;
  final String extension;
  final int sizeBytes;
  final String status;
  final DateTime uploadedAt;
  final DateTime? processedAt;
  final bool? isFavorite;
  final String? downloadUrl;
  final Map<String, dynamic>? metadata;

  const FileModel({
    required this.id,
    required this.name,
    required this.originalName,
    required this.extension,
    required this.sizeBytes,
    required this.status,
    required this.uploadedAt,
    this.processedAt,
    this.isFavorite,
    this.downloadUrl,
    this.metadata,
  });

  factory FileModel.fromJson(Map<String, dynamic> json) {
    final rawName = json['original_filename'] as String? ??
        json['original_name'] as String? ??
        json['name'] as String? ??
        '';
    final ext = (json['file_type'] as String? ??
            json['extension'] as String? ??
            (rawName.contains('.') ? rawName.split('.').last : ''))
        .replaceAll('.', '');

    return FileModel(
      id: json['id'] as int? ?? 0,
      name: json['filename'] as String? ?? rawName,
      originalName: rawName,
      extension: ext,
      sizeBytes: json['file_size'] as int? ?? json['size_bytes'] as int? ?? 0,
      status: json['status'] as String? ?? 'uploaded',
      uploadedAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'] as String) ?? DateTime.now()
          : DateTime.now(),
      processedAt: json['processed_at'] != null
          ? DateTime.tryParse(json['processed_at'] as String)
          : null,
      isFavorite: json['is_favorite'] as bool?,
      downloadUrl: json['download_url'] as String?,
      metadata: json['metadata'] as Map<String, dynamic>?,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'filename': name,
        'original_name': originalName,
        'extension': extension,
        'size_bytes': sizeBytes,
        'status': status,
        'created_at': uploadedAt.toIso8601String(),
        if (processedAt != null)
          'processed_at': processedAt!.toIso8601String(),
        if (isFavorite != null) 'is_favorite': isFavorite,
        if (downloadUrl != null) 'download_url': downloadUrl,
        if (metadata != null) 'metadata': metadata,
      };

  FileEntity toEntity() => FileEntity(
        id: id,
        name: name,
        originalName: originalName,
        extension: extension,
        sizeBytes: sizeBytes,
        status: status,
        uploadedAt: uploadedAt,
        processedAt: processedAt,
        isFavorite: isFavorite,
        downloadUrl: downloadUrl,
        metadata: metadata,
      );
}
