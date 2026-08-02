import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/constants/storage_keys.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/storage/secure_storage.dart';
enum PinMode { verify, set, change }

class PinScreen extends ConsumerStatefulWidget {
  const PinScreen({required this.mode, super.key});
  final PinMode mode;

  @override
  ConsumerState<PinScreen> createState() => _PinScreenState();
}

class _PinScreenState extends ConsumerState<PinScreen> {
  final List<String> _digits = [];
  String? _error;

  void _onDigitTap(String digit) {
    if (_digits.length >= AppConstants.pinLength) return;
    setState(() => _digits.add(digit));
    if (_digits.length == AppConstants.pinLength) _verify();
  }

  void _onBackspace() {
    if (_digits.isEmpty) return;
    setState(() => _digits.removeLast());
  }

  String _hash(String pin) => sha256.convert(utf8.encode(pin)).toString();

  Future<void> _verify() async {
    final pin = _digits.join();

    if (widget.mode == PinMode.verify) {
      final stored = await SecureStorage.read(StorageKeys.pinHash);
      if (stored == null || _hash(pin) != stored) {
        _showError('رمز PIN غير صحيح');
      } else if (mounted) {
        context.go(AppRoutes.home);
      }
    } else {
      await SecureStorage.write(StorageKeys.pinHash, _hash(pin));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('تم حفظ رمز PIN بنجاح')),
        );
        context.pop();
      }
    }
  }

  void _showError(String msg) {
    setState(() {
      _error = msg;
      _digits.clear();
    });
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: Text(
            widget.mode == PinMode.verify ? 'أدخل رمز PIN' : 'تعيين رمز PIN'),
        leading: widget.mode != PinMode.verify ? const BackButton() : null,
      ),
      body: SafeArea(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // PIN dots
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: List.generate(AppConstants.pinLength, (i) {
                final filled = i < _digits.length;
                return AnimatedContainer(
                  duration: 150.ms,
                  margin: const EdgeInsets.symmetric(horizontal: 8),
                  width: 16,
                  height: 16,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: _error != null
                        ? cs.error
                        : filled
                            ? cs.primary
                            : cs.outlineVariant,
                  ),
                );
              }),
            ),

            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(_error!, style: TextStyle(color: cs.error))
                  .animate()
                  .shakeX(duration: 400.ms),
            ],

            const SizedBox(height: 48),

            // Numpad
            for (final row in [
              ['1', '2', '3'],
              ['4', '5', '6'],
              ['7', '8', '9'],
              ['', '0', '⌫'],
            ])
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: row.map((d) {
                  if (d.isEmpty) return const SizedBox(width: 80, height: 72);
                  return SizedBox(
                    width: 80,
                    height: 72,
                    child: TextButton(
                      style:
                          TextButton.styleFrom(shape: const CircleBorder()),
                      onPressed:
                          d == '⌫' ? _onBackspace : () => _onDigitTap(d),
                      child: Text(d,
                          style:
                              Theme.of(context).textTheme.headlineMedium),
                    ),
                  );
                }).toList(),
              ),
          ],
        ),
      ),
    );
  }
}
