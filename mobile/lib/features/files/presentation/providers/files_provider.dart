import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:freezed_annotation/freezed_annotation.dart';

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
  return FilesNotifier();
});

class FilesNotifier extends StateNotifier<FilesState> {
  FilesNotifier() : super(const FilesState());

  Future<void> loadFiles({bool refresh = false}) async {
    // Offline mode — no API calls, return empty list immediately
    state = state.copyWith(isLoading: false, files: [], error: null);
  }

  Future<void> setSection(String section) async {
    state = state.copyWith(activeSection: section);
  }

  Future<bool> uploadFile(File file) async {
    return false;
  }

  void cancelUpload() {
    state = state.copyWith(isUploading: false, uploadProgress: 0);
  }

  Future<void> deleteFile(int id) async {
    state = state.copyWith(
      files: state.files.where((f) => f.id != id).toList(),
    );
  }

  Future<void> toggleFavorite(int id) async {}
}
