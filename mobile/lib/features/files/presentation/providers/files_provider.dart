import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:freezed_annotation/freezed_annotation.dart';

import '../../../../core/network/dio_client.dart';
import '../../data/datasources/files_remote_datasource.dart';
import '../../domain/entities/file_entity.dart';
import '../../data/models/file_model.dart';

part 'files_provider.freezed.dart';

// ── Repository provider ────────────────────────────────────────────────────────

final filesDataSourceProvider = Provider<FilesRemoteDataSource>((ref) {
  return FilesRemoteDataSourceImpl(ref.watch(dioClientProvider));
});

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
  return FilesNotifier(ref.watch(filesDataSourceProvider));
});

class FilesNotifier extends StateNotifier<FilesState> {
  final FilesRemoteDataSource _dataSource;
  CancelToken? _uploadCancelToken;

  FilesNotifier(this._dataSource) : super(const FilesState()) {
    loadFiles();
  }

  Future<void> loadFiles({bool refresh = false}) async {
    if (state.isLoading) return;

    final page = refresh ? 1 : state.currentPage;

    state = state.copyWith(
      isLoading: true,
      error: null,
      files: refresh ? [] : state.files,
    );

    try {
      final models = await _dataSource.getFiles(
          page: page, section: state.activeSection == 'all' ? null : state.activeSection);
      final entities = models.map((m) => m.toEntity()).toList();

      state = state.copyWith(
        files: refresh ? entities : [...state.files, ...entities],
        isLoading: false,
        currentPage: page + 1,
        hasMore: entities.length >= 20,
      );
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString());
    }
  }

  Future<void> setSection(String section) async {
    state = state.copyWith(activeSection: section);
    await loadFiles(refresh: true);
  }

  Future<bool> uploadFile(File file) async {
    _uploadCancelToken = CancelToken();
    state = state.copyWith(isUploading: true, uploadProgress: 0, error: null);

    try {
      final model = await _dataSource.uploadFile(
        file,
        onProgress: (sent, total) {
          if (total > 0) {
            state = state.copyWith(uploadProgress: sent / total);
          }
        },
        cancelToken: _uploadCancelToken,
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
    _uploadCancelToken?.cancel('Upload cancelled by user');
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
