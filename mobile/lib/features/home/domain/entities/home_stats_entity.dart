import 'package:freezed_annotation/freezed_annotation.dart';

part 'home_stats_entity.freezed.dart';

@freezed
class HomeStatsEntity with _$HomeStatsEntity {
  const factory HomeStatsEntity({
    required int totalFiles,
    required double storageUsedMb,
    required double storageLimitMb,
    required int conversionsToday,
    required int conversionsLimit,
    required int analysesToday,
    required String planName,
  }) = _HomeStatsEntity;
}
