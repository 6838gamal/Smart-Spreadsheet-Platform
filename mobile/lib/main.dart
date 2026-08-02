import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'app.dart';
import 'core/services/remote_config_service.dart';
import 'core/storage/hive_storage.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Lock to portrait + landscape (unlock for tablets later via adaptive layout)
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
    DeviceOrientation.landscapeLeft,
    DeviceOrientation.landscapeRight,
  ]);

  // Status bar style — will be updated per-theme
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
  ));

  // Initialize Hive local database
  await HiveStorage.init();

  // Fetch public config from backend (GOOGLE_CLIENT_ID etc.)
  // Falls back to compile-time --dart-define values on failure.
  await RemoteConfigService.fetch();

  runApp(
    // ProviderScope is the root of the Riverpod dependency graph.
    // All providers are lazily created and cached here.
    const ProviderScope(
      child: SmartSpreadsheetApp(),
    ),
  );
}
