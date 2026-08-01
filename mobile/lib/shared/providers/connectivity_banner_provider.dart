import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/network_info.dart';

/// Drives the offline banner shown across all shell screens.
/// True = offline, False = online.
final showOfflineBannerProvider = Provider<bool>((ref) {
  return !ref.watch(isOnlineProvider);
});
