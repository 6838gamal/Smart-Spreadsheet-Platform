import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/constants/api_constants.dart';
import '../../../../core/network/dio_client.dart';
import '../../../files/data/datasources/files_remote_datasource.dart';

enum ConversionStatus { idle, uploading, converting, success, error }

class ConversionState {
  final ConversionStatus status;
  final double progress;
  final String? outputFilename;
  final String? downloadUrl;
  final String? error;

  const ConversionState({
    this.status = ConversionStatus.idle,
    this.progress = 0.0,
    this.outputFilename,
    this.downloadUrl,
    this.error,
  });

  ConversionState copyWith({
    ConversionStatus? status,
    double? progress,
    String? outputFilename,
    String? downloadUrl,
    String? error,
  }) =>
      ConversionState(
        status: status ?? this.status,
        progress: progress ?? this.progress,
        outputFilename: outputFilename ?? this.outputFilename,
        downloadUrl: downloadUrl ?? this.downloadUrl,
        error: error ?? this.error,
      );
}

final conversionProvider =
    StateNotifierProvider<ConversionNotifier, ConversionState>((ref) {
  final client = ref.read(dioClientProvider);
  return ConversionNotifier(client);
});

class ConversionNotifier extends StateNotifier<ConversionState> {
  final DioClient _client;

  ConversionNotifier(this._client) : super(const ConversionState());

  Future<void> convert({
    required File sourceFile,
    required String sourceFormat,
    required String targetFormat,
  }) async {
    // Step 1: upload the file
    state = const ConversionState(
        status: ConversionStatus.uploading, progress: 0.0);
    try {
      final dataSource = FilesRemoteDataSourceImpl(_client);
      final uploaded = await dataSource.uploadFile(
        sourceFile,
        onProgress: (sent, total) {
          if (total > 0) {
            state = state.copyWith(progress: (sent / total) * 0.5);
          }
        },
      );

      // Step 2: request conversion
      state = state.copyWith(
          status: ConversionStatus.converting, progress: 0.5);
      final response = await _client.post(
        ApiConstants.convert,
        data: {
          'file_id': uploaded.id,
          'target_format': targetFormat.toLowerCase(),
        },
      );

      final outputFilename =
          response.data['output_filename'] as String?;
      if (outputFilename == null) {
        state = const ConversionState(
          status: ConversionStatus.error,
          error: 'لم يتم استلام اسم الملف من الخادم',
        );
        return;
      }

      final downloadUrl =
          '${ApiConstants.conversionDownloadBase}/$outputFilename';
      state = ConversionState(
        status: ConversionStatus.success,
        progress: 1.0,
        outputFilename: outputFilename,
        downloadUrl: downloadUrl,
      );
    } catch (e) {
      state = ConversionState(
        status: ConversionStatus.error,
        error: e.toString(),
      );
    }
  }

  void reset() {
    state = const ConversionState();
  }
}
