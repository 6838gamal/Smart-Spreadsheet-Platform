import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/conversion_provider.dart';

class ConversionScreen extends ConsumerStatefulWidget {
  const ConversionScreen({super.key});

  @override
  ConsumerState<ConversionScreen> createState() => _ConversionScreenState();
}

class _ConversionScreenState extends ConsumerState<ConversionScreen> {
  String? _selectedSourceFormat;
  String? _selectedTargetFormat;
  String? _selectedFilePath;
  String? _selectedFileName;

  // Conversion map: source → list of possible targets
  static const Map<String, List<String>> _conversions = {
    'PDF': ['Excel', 'Word', 'CSV', 'Text'],
    'Image': ['Excel', 'Word', 'PDF', 'Text'],
    'Excel': ['PDF', 'CSV', 'JSON'],
    'Word': ['PDF', 'Text'],
    'CSV': ['Excel', 'PDF'],
    'PowerPoint': ['PDF'],
  };

  static const Map<String, IconData> _formatIcons = {
    'PDF': Icons.picture_as_pdf_rounded,
    'Image': Icons.image_rounded,
    'Excel': Icons.table_chart_rounded,
    'Word': Icons.description_rounded,
    'CSV': Icons.grid_on_rounded,
    'PowerPoint': Icons.slideshow_rounded,
    'Text': Icons.text_fields_rounded,
    'JSON': Icons.data_object_rounded,
  };

  Future<void> _pickFile() async {
    final result = await FilePicker.platform.pickFiles();
    if (result == null || result.files.isEmpty) return;
    setState(() {
      _selectedFilePath = result.files.first.path;
      _selectedFileName = result.files.first.name;
    });
  }

  Future<void> _startConversion() async {
    if (_selectedFilePath == null ||
        _selectedSourceFormat == null ||
        _selectedTargetFormat == null) { return; }

    await ref.read(conversionProvider.notifier).convert(
          sourceFile: File(_selectedFilePath!),
          sourceFormat: _selectedSourceFormat!,
          targetFormat: _selectedTargetFormat!,
        );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final convState = ref.watch(conversionProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('تحويل الملفات')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Source format ─────────────────────────────────────────────
            Text('من: صيغة المصدر',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: _conversions.keys.map((fmt) {
                final isSelected = _selectedSourceFormat == fmt;
                return ChoiceChip(
                  avatar: Icon(_formatIcons[fmt], size: 16),
                  label: Text(fmt),
                  selected: isSelected,
                  onSelected: (_) => setState(() {
                    _selectedSourceFormat = fmt;
                    _selectedTargetFormat = null; // reset target
                  }),
                );
              }).toList(),
            )
                .animate()
                .fadeIn(duration: 300.ms)
                .slideY(begin: 0.1, duration: 300.ms),

            if (_selectedSourceFormat != null) ...[
              const SizedBox(height: 24),

              // ── Target format ──────────────────────────────────────────
              Text('إلى: صيغة الهدف',
                  style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children:
                    (_conversions[_selectedSourceFormat] ?? []).map((fmt) {
                  final isSelected = _selectedTargetFormat == fmt;
                  return ChoiceChip(
                    avatar: Icon(_formatIcons[fmt], size: 16),
                    label: Text(fmt),
                    selected: isSelected,
                    onSelected: (_) =>
                        setState(() => _selectedTargetFormat = fmt),
                  );
                }).toList(),
              ).animate().fadeIn(duration: 300.ms),
            ],

            const SizedBox(height: 24),

            // ── File picker ───────────────────────────────────────────────
            Text('اختر الملف', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            InkWell(
              onTap: _pickFile,
              borderRadius: BorderRadius.circular(16),
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  border: Border.all(
                    color: _selectedFilePath != null
                        ? cs.primary
                        : cs.outlineVariant,
                    width: _selectedFilePath != null ? 2 : 1,
                    style: BorderStyle.solid,
                  ),
                  borderRadius: BorderRadius.circular(16),
                  color: _selectedFilePath != null
                      ? cs.primaryContainer.withValues(alpha: 0.3)
                      : null,
                ),
                child: Column(
                  children: [
                    Icon(
                      _selectedFilePath != null
                          ? Icons.check_circle_rounded
                          : Icons.upload_file_rounded,
                      size: 40,
                      color: _selectedFilePath != null
                          ? cs.primary
                          : cs.onSurfaceVariant,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _selectedFileName ?? 'اضغط لاختيار ملف',
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            color: _selectedFilePath != null
                                ? cs.primary
                                : cs.onSurfaceVariant,
                          ),
                      textAlign: TextAlign.center,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 32),

            // ── Conversion status ─────────────────────────────────────────
            if (convState.status == ConversionStatus.converting) ...[
              LinearProgressIndicator(value: convState.progress),
              const SizedBox(height: 8),
              Center(
                child: Text(
                  'جارٍ التحويل... ${(convState.progress * 100).toStringAsFixed(0)}%',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ),
              const SizedBox(height: 16),
            ],

            if (convState.status == ConversionStatus.success) ...[
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.green.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.green),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.check_circle_rounded, color: Colors.green),
                    const SizedBox(width: 8),
                    const Expanded(child: Text('تم التحويل بنجاح!')),
                    TextButton(
                        onPressed: () {}, child: const Text('تنزيل')),
                  ],
                ),
              ),
              const SizedBox(height: 16),
            ],

            if (convState.error != null) ...[
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: cs.errorContainer,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  children: [
                    Icon(Icons.error_outline, color: cs.onErrorContainer),
                    const SizedBox(width: 8),
                    Expanded(
                        child: Text(convState.error!,
                            style:
                                TextStyle(color: cs.onErrorContainer))),
                  ],
                ),
              ),
              const SizedBox(height: 16),
            ],

            // ── Convert button ────────────────────────────────────────────
            FilledButton.icon(
              onPressed: (_selectedFilePath != null &&
                      _selectedTargetFormat != null &&
                      convState.status != ConversionStatus.converting)
                  ? _startConversion
                  : null,
              icon: const Icon(Icons.transform_rounded),
              label: const Text('بدء التحويل'),
            ),
          ],
        ),
      ),
    );
  }
}
