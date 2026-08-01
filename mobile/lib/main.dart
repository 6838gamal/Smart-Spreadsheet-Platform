import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'app.dart';
import 'core/constants/app_constants.dart';
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

  // Initialize Google Sign-In with Client ID from --dart-define
  await GoogleSignIn.instance.initialize(
    clientId: AppConstants.googleClientId.isNotEmpty
        ? AppConstants.googleClientId
        : null,
  );

  runApp(
    // ProviderScope is the root of the Riverpod dependency graph.
    // All providers are lazily created and cached here.
    const ProviderScope(
      child: SmartSpreadsheetApp(),
    ),
  );
}
