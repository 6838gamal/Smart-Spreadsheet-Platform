import 'package:flutter_riverpod/flutter_riverpod.dart';

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
  return ConversionNotifier();
});

class ConversionNotifier extends StateNotifier<ConversionState> {
  ConversionNotifier() : super(const ConversionState());

  Future<void> convert({
    required dynamic sourceFile,
    required String sourceFormat,
    required String targetFormat,
  }) async {
    state = const ConversionState(status: ConversionStatus.converting);
    await Future.delayed(const Duration(milliseconds: 500));
    state = const ConversionState(
      status: ConversionStatus.error,
      error: 'التحويل غير متاح في الوضع المحلي',
    );
  }

  void reset() {
    state = const ConversionState();
  }
}
