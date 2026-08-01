import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/constants/api_constants.dart';
import '../../../../core/network/dio_client.dart';

enum ConversionStatus { idle, converting, success, error }

class ConversionState {
  final ConversionStatus status;
  final double progress;
  final String? jobId;
  final String? downloadUrl;
  final String? error;

  const ConversionState({
    this.status = ConversionStatus.idle,
    this.progress = 0.0,
    this.jobId,
    this.downloadUrl,
    this.error,
  });

  ConversionState copyWith({
    ConversionStatus? status,
    double? progress,
    String? jobId,
    String? downloadUrl,
    String? error,
  }) =>
      ConversionState(
        status: status ?? this.status,
        progress: progress ?? this.progress,
        jobId: jobId ?? this.jobId,
        downloadUrl: downloadUrl ?? this.downloadUrl,
        error: error ?? this.error,
      );
}

final conversionProvider =
    StateNotifierProvider<ConversionNotifier, ConversionState>((ref) {
  return ConversionNotifier(ref.watch(dioClientProvider));
});

class ConversionNotifier extends StateNotifier<ConversionState> {
  final DioClient _client;

  ConversionNotifier(this._client) : super(const ConversionState());

  Future<void> convert({
    required File sourceFile,
    required String sourceFormat,
    required String targetFormat,
  }) async {
    state = const ConversionState(status: ConversionStatus.converting);

    try {
      final formData = FormData.fromMap({
        'file': await MultipartFile.fromFile(sourceFile.path,
            filename: sourceFile.path.split('/').last),
        'source_format': sourceFormat.toLowerCase(),
        'target_format': targetFormat.toLowerCase(),
      });

      // Submit job
      final response = await _client.postFormData(
        ApiConstants.convert,
        formData,
        onSendProgress: (sent, total) {
          if (total > 0) {
            // Upload phase is 0→50%
            state = state.copyWith(progress: (sent / total) * 0.5);
          }
        },
      );

      final jobId = (response.data as Map<String, dynamic>)['job_id'] as String?;
      if (jobId == null) {
        state = state.copyWith(
          status: ConversionStatus.error,
          error: 'لم يتم إرجاع معرف المهمة',
        );
        return;
      }

      // Poll for completion (processing phase is 50→100%)
      await _pollStatus(jobId);
    } catch (e) {
      state = state.copyWith(
        status: ConversionStatus.error,
        error: e.toString(),
      );
    }
  }

  Future<void> _pollStatus(String jobId) async {
    var attempts = 0;
    const maxAttempts = 60; // 2 min max

    while (attempts < maxAttempts) {
      await Future.delayed(const Duration(seconds: 2));
      attempts++;

      try {
        final response =
            await _client.get(ApiConstants.conversionStatus(jobId));
        final data = response.data as Map<String, dynamic>;
        final status = data['status'] as String?;
        final progress = (data['progress'] as num?)?.toDouble() ?? 0.0;

        // 50% (upload done) + 50% × server progress
        state = state.copyWith(progress: 0.5 + progress * 0.5);

        if (status == 'completed') {
          state = state.copyWith(
            status: ConversionStatus.success,
            progress: 1.0,
            downloadUrl: data['download_url'] as String?,
          );
          return;
        }

        if (status == 'failed') {
          state = state.copyWith(
            status: ConversionStatus.error,
            error: (data['error'] as String?) ?? 'فشل التحويل',
          );
          return;
        }
      } catch (_) {
        // Network hiccup — keep polling
      }
    }

    state = state.copyWith(
      status: ConversionStatus.error,
      error: 'انتهت مهلة انتظار التحويل',
    );
  }

  void reset() => state = const ConversionState();
}
