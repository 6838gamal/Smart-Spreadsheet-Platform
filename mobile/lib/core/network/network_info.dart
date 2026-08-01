import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Watches the device's network connectivity state.
/// Features can watch [connectivityProvider] to react to network changes.
final connectivityProvider =
    StreamProvider<List<ConnectivityResult>>((ref) {
  return Connectivity().onConnectivityChanged;
});

/// Simple boolean — true when any non-none connection is available.
final isOnlineProvider = Provider<bool>((ref) {
  final results = ref.watch(connectivityProvider).valueOrNull ?? [];
  return results.any((r) => r != ConnectivityResult.none);
});
