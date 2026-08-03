import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:freezed_annotation/freezed_annotation.dart';

import '../../../../core/network/dio_client.dart';
import '../../data/datasources/files_remote_datasource.dart';
import '../../domain/entities/file_entity.dart';

part 'files_provider.freezed.dart';

// ── Files list state ──────────────────────────────────────────────────────────

@freezed
class FilesState with _$FilesState {
  const factory FilesState({
    @Default([]) List<FileEntity> files,
    @Default(false) bool isLoading,
    @Default(false) bool isUploading,
    @Default(0.0) double uploadProgress,
    String? error,
    @Default(false) bool hasMore,
    @Default(1) int currentPage,
    @Default('all') String activeSection,
  }) = _FilesState;
}

final filesProvider =
    StateNotifierProvider<FilesNotifier, FilesState>((ref) {
  final client = ref.read(dioClientProvider);
  final dataSource = FilesRemoteDataSourceImpl(client);
  return FilesNotifier(dataSource);
});

class FilesNotifier extends StateNotifier<FilesState> {
  final FilesRemoteDataSource _dataSource;

  FilesNotifier(this._dataSource) : super(const FilesState()) {
    loadFiles();
  }

  Future<void> loadFiles({bool refresh = false}) async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final page = refresh ? 1 : state.currentPage;
      final section =
          state.activeSection == 'all' ? null : state.activeSection;
      final models = await _dataSource.getFiles(page: page, section: section);
      state = state.copyWith(
        isLoading: false,
        files: models.map((m) => m.toEntity()).toList(),
        currentPage: page,
        error: null,
      );
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString());
    }
  }

  Future<void> setSection(String section) async {
    state = state.copyWith(activeSection: section, currentPage: 1);
    await loadFiles(refresh: true);
  }

  Future<bool> uploadFile(File file) async {
    state = state.copyWith(isUploading: true, uploadProgress: 0);
    try {
      final model = await _dataSource.uploadFile(
        file,
        onProgress: (sent, total) {
          if (total > 0) {
            state = state.copyWith(uploadProgress: sent / total);
          }
        },
      );
      state = state.copyWith(
        isUploading: false,
        uploadProgress: 0,
        files: [model.toEntity(), ...state.files],
      );
      return true;
    } catch (e) {
      state = state.copyWith(
          isUploading: false, uploadProgress: 0, error: e.toString());
      return false;
    }
  }

  /// Upload from raw bytes — used on Flutter Web where dart:io File is unavailable.
  Future<bool> uploadFileBytes(Uint8List bytes, String filename) async {
    state = state.copyWith(isUploading: true, uploadProgress: 0);
    try {
      final model = await _dataSource.uploadFileBytes(
        bytes,
        filename,
        onProgress: (sent, total) {
          if (total > 0) {
            state = state.copyWith(uploadProgress: sent / total);
          }
        },
      );
      state = state.copyWith(
        isUploading: false,
        uploadProgress: 0,
        files: [model.toEntity(), ...state.files],
      );
      return true;
    } catch (e) {
      state = state.copyWith(
          isUploading: false, uploadProgress: 0, error: e.toString());
      return false;
    }
  }

  void cancelUpload() {
    state = state.copyWith(isUploading: false, uploadProgress: 0);
  }

  Future<void> deleteFile(int id) async {
    try {
      await _dataSource.deleteFile(id);
      state = state.copyWith(
        files: state.files.where((f) => f.id != id).toList(),
      );
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }

  Future<void> toggleFavorite(int id) async {
    try {
      final updated = await _dataSource.toggleFavorite(id);
      state = state.copyWith(
        files: state.files
            .map((f) => f.id == id ? updated.toEntity() : f)
            .toList(),
      );
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }
}
