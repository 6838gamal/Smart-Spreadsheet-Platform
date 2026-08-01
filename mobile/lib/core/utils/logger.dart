import 'package:logger/logger.dart';

/// App-wide logger. Use via the [log] singleton.
/// In production builds, level is set to warning to suppress debug noise.
final log = Logger(
  printer: PrettyPrinter(
    methodCount: 2,
    errorMethodCount: 8,
    lineLength: 80,
    colors: true,
    printEmojis: true,
    dateTimeFormat: DateTimeFormat.onlyTimeAndSinceStart,
  ),
  level: const bool.fromEnvironment('dart.vm.product')
      ? Level.warning
      : Level.debug,
);
