import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'app.dart';
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

  // Google Sign-In init — skipped in local-only mode
  // await GoogleSignIn.instance.initialize();

  runApp(
    // ProviderScope is the root of the Riverpod dependency graph.
    // All providers are lazily created and cached here.
    const ProviderScope(
      child: SmartSpreadsheetApp(),
    ),
  );
}
