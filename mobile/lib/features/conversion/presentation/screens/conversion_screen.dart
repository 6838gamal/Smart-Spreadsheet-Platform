import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../../core/constants/app_constants.dart';
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
  bool _isPickingFile = false;
  String? _filePickError;

  static const Map<String, List<String>> _conversions = {
    'PDF':        ['Excel', 'Word', 'CSV', 'Text'],
    'Image':      ['Excel', 'Word', 'PDF', 'Text'],
    'Excel':      ['PDF', 'CSV', 'JSON'],
    'Word':       ['PDF', 'Text'],
    'CSV':        ['Excel', 'PDF'],
    'PowerPoint': ['PDF'],
  };

  static const Map<String, IconData> _formatIcons = {
    'PDF':        Icons.picture_as_pdf_rounded,
    'Image':      Icons.image_rounded,
    'Excel':      Icons.table_chart_rounded,
    'Word':       Icons.description_rounded,
    'CSV':        Icons.grid_on_rounded,
    'PowerPoint': Icons.slideshow_rounded,
    'Text':       Icons.text_fields_rounded,
    'JSON':       Icons.data_object_rounded,
  };

  static const Map<String, Color> _formatColors = {
    'PDF':        Color(0xFFE53935),
    'Image':      Color(0xFF8E24AA),
    'Excel':      Color(0xFF2E7D32),
    'Word':       Color(0xFF1565C0),
    'CSV':        Color(0xFF00695C),
    'PowerPoint': Color(0xFFBF360C),
    'Text':       Color(0xFF546E7A),
    'JSON':       Color(0xFFF57F17),
  };

  Future<void> _pickFile() async {
    setState(() {
      _isPickingFile = true;
      _filePickError = null;
    });
    try {
      final result = await FilePicker.platform.pickFiles(
        allowMultiple: false,
        withData: false,
      );
      if (!mounted) return;
      if (result == null || result.files.isEmpty) {
        setState(() => _isPickingFile = false);
        return;
      }
      final file = result.files.first;
      if (file.path == null) {
        setState(() {
          _isPickingFile = false;
          _filePickError = 'تعذّر الوصول إلى الملف، حاول مجدداً';
        });
        return;
      }
      setState(() {
        _isPickingFile = false;
        _filePickError = null;
        _selectedFilePath = file.path;
        _selectedFileName = file.name;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isPickingFile = false;
        _filePickError = 'حدث خطأ أثناء اختيار الملف';
      });
    }
  }

  Future<void> _startConversion() async {
    if (_selectedFilePath == null ||
        _selectedSourceFormat == null ||
        _selectedTargetFormat == null) {
      return;
    }
    await ref.read(conversionProvider.notifier).convert(
          sourceFile: File(_selectedFilePath!),
          sourceFormat: _selectedSourceFormat!,
          targetFormat: _selectedTargetFormat!,
        );
  }

  Future<void> _launchDownload(String relativeUrl) async {
    final baseUrl = AppConstants.defaultApiBaseUrl;
    final fullUrl = '$baseUrl$relativeUrl';
    final uri = Uri.parse(fullUrl);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final convState = ref.watch(conversionProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('تحويل الملفات'),
        actions: [
          if (_selectedFilePath != null ||
              _selectedSourceFormat != null ||
              convState.status != ConversionStatus.idle)
            IconButton(
              icon: const Icon(Icons.refresh_rounded),
              tooltip: 'إعادة التعيين',
              onPressed: () => setState(() {
                _selectedFilePath = null;
                _selectedFileName = null;
                _selectedSourceFormat = null;
                _selectedTargetFormat = null;
                _filePickError = null;
                ref.read(conversionProvider.notifier).reset();
              }),
            ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [

            // ── Step 1: Source format ──────────────────────────────────────
            _StepHeader(
              number: '١',
              title: 'صيغة المصدر',
              isDone: _selectedSourceFormat != null,
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: _conversions.keys.map((fmt) {
                final isSelected = _selectedSourceFormat == fmt;
                final color = _formatColors[fmt] ?? cs.primary;
                return _FormatChip(
                  label: fmt,
                  icon: _formatIcons[fmt]!,
                  color: color,
                  isSelected: isSelected,
                  onTap: () => setState(() {
                    _selectedSourceFormat = fmt;
                    _selectedTargetFormat = null;
                    ref.read(conversionProvider.notifier).reset();
                  }),
                );
              }).toList(),
            )
                .animate()
                .fadeIn(duration: 350.ms)
                .slideY(begin: 0.08, duration: 350.ms),

            // ── Step 2: Target format ──────────────────────────────────────
            if (_selectedSourceFormat != null) ...[
              const SizedBox(height: 28),
              _StepHeader(
                number: '٢',
                title: 'صيغة الهدف',
                isDone: _selectedTargetFormat != null,
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: (_conversions[_selectedSourceFormat] ?? [])
                    .map((fmt) {
                  final isSelected = _selectedTargetFormat == fmt;
                  final color = _formatColors[fmt] ?? cs.primary;
                  return _FormatChip(
                    label: fmt,
                    icon: _formatIcons[fmt]!,
                    color: color,
                    isSelected: isSelected,
                    onTap: () => setState(() => _selectedTargetFormat = fmt),
                  );
                }).toList(),
              ).animate().fadeIn(duration: 300.ms).slideY(begin: 0.08),
            ],

            // ── Step 3: File picker ────────────────────────────────────────
            const SizedBox(height: 28),
            _StepHeader(
              number: '٣',
              title: 'اختر الملف',
              isDone: _selectedFilePath != null,
            ),
            const SizedBox(height: 12),
            _FilePicker(
              isLoading: _isPickingFile,
              fileName: _selectedFileName,
              filePath: _selectedFilePath,
              error: _filePickError,
              onTap: _isPickingFile ? null : _pickFile,
            ).animate().fadeIn(duration: 300.ms),

            const SizedBox(height: 32),

            // ── Conversion status ──────────────────────────────────────────
            if (convState.status == ConversionStatus.uploading) ...[
              _ConvertingCard(
                progress: convState.progress,
                label: 'جارٍ رفع الملف...',
              ).animate().fadeIn(duration: 250.ms),
              const SizedBox(height: 16),
            ],

            if (convState.status == ConversionStatus.converting) ...[
              _ConvertingCard(
                progress: convState.progress,
                label: 'جارٍ التحويل...',
              ).animate().fadeIn(duration: 250.ms),
              const SizedBox(height: 16),
            ],

            if (convState.status == ConversionStatus.success) ...[
              _ResultCard(
                isSuccess: true,
                message: 'تم التحويل بنجاح!',
                action: TextButton.icon(
                  onPressed: convState.downloadUrl != null
                      ? () => _launchDownload(convState.downloadUrl!)
                      : null,
                  icon: const Icon(Icons.download_rounded, size: 18),
                  label: const Text('تنزيل الملف'),
                ),
              ).animate().fadeIn(duration: 300.ms).scale(
                    begin: const Offset(0.95, 0.95),
                    duration: 300.ms,
                    curve: Curves.easeOutBack,
                  ),
              const SizedBox(height: 16),
            ],

            if (convState.error != null) ...[
              _ResultCard(
                isSuccess: false,
                message: convState.error!,
                action: TextButton.icon(
                  onPressed: () =>
                      ref.read(conversionProvider.notifier).reset(),
                  icon: const Icon(Icons.refresh_rounded, size: 18),
                  label: const Text('إعادة المحاولة'),
                ),
              ).animate().fadeIn(duration: 300.ms).shake(duration: 400.ms),
              const SizedBox(height: 16),
            ],

            // ── Convert button ─────────────────────────────────────────────
            _ConvertButton(
              isReady: _selectedFilePath != null &&
                  _selectedSourceFormat != null &&
                  _selectedTargetFormat != null,
              isConverting: convState.status == ConversionStatus.uploading ||
                  convState.status == ConversionStatus.converting,
              onPressed: _startConversion,
            ).animate().fadeIn(delay: 100.ms, duration: 300.ms),
          ],
        ),
      ),
    );
  }
}

// ── Step header ───────────────────────────────────────────────────────────────

class _StepHeader extends StatelessWidget {
  const _StepHeader({
    required this.number,
    required this.title,
    required this.isDone,
  });
  final String number;
  final String title;
  final bool isDone;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Row(
      children: [
        AnimatedContainer(
          duration: const Duration(milliseconds: 300),
          width: 28,
          height: 28,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: isDone ? cs.primary : cs.surfaceContainerHighest,
          ),
          child: Center(
            child: isDone
                ? Icon(Icons.check_rounded,
                    size: 16, color: cs.onPrimary)
                : Text(
                    number,
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      color: cs.onSurfaceVariant,
                    ),
                  ),
          ),
        ),
        const SizedBox(width: 10),
        Text(
          title,
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                color: isDone ? cs.primary : null,
                fontWeight: isDone ? FontWeight.w600 : FontWeight.w500,
              ),
        ),
      ],
    );
  }
}

// ── Format chip ───────────────────────────────────────────────────────────────

class _FormatChip extends StatelessWidget {
  const _FormatChip({
    required this.label,
    required this.icon,
    required this.color,
    required this.isSelected,
    required this.onTap,
  });
  final String label;
  final IconData icon;
  final Color color;
  final bool isSelected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 200),
      child: Material(
        color: isSelected ? color.withValues(alpha: 0.15) : Colors.transparent,
        borderRadius: BorderRadius.circular(50),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(50),
          child: Container(
            padding:
                const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(50),
              border: Border.all(
                color:
                    isSelected ? color : Theme.of(context).colorScheme.outlineVariant,
                width: isSelected ? 1.5 : 1,
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(icon,
                    size: 16,
                    color: isSelected
                        ? color
                        : Theme.of(context).colorScheme.onSurfaceVariant),
                const SizedBox(width: 6),
                Text(
                  label,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                    color: isSelected
                        ? color
                        : Theme.of(context).colorScheme.onSurface,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ── File picker ───────────────────────────────────────────────────────────────

class _FilePicker extends StatelessWidget {
  const _FilePicker({
    required this.isLoading,
    required this.fileName,
    required this.filePath,
    required this.error,
    required this.onTap,
  });
  final bool isLoading;
  final String? fileName;
  final String? filePath;
  final String? error;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final hasFile = filePath != null;
    final hasError = error != null;

    final borderColor = hasError
        ? cs.error
        : hasFile
            ? cs.primary
            : cs.outlineVariant;
    final bgColor = hasError
        ? cs.errorContainer.withValues(alpha: 0.15)
        : hasFile
            ? cs.primaryContainer.withValues(alpha: 0.2)
            : cs.surfaceContainerHighest.withValues(alpha: 0.3);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(20),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 250),
            width: double.infinity,
            padding: const EdgeInsets.symmetric(vertical: 28, horizontal: 20),
            decoration: BoxDecoration(
              color: bgColor,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(
                color: borderColor,
                width: (hasFile || hasError) ? 1.8 : 1,
                style: isLoading ? BorderStyle.none : BorderStyle.solid,
              ),
            ),
            child: isLoading
                ? Column(
                    children: [
                      const SizedBox(
                        width: 36,
                        height: 36,
                        child: CircularProgressIndicator(strokeWidth: 3),
                      ),
                      const SizedBox(height: 12),
                      Text(
                        'جارٍ فتح منتقي الملفات...',
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: cs.onSurfaceVariant,
                            ),
                      ),
                    ],
                  )
                : Column(
                    children: [
                      // Icon with animated transition
                      AnimatedSwitcher(
                        duration: const Duration(milliseconds: 300),
                        child: Icon(
                          hasError
                              ? Icons.error_outline_rounded
                              : hasFile
                                  ? Icons.check_circle_outline_rounded
                                  : Icons.cloud_upload_outlined,
                          key: ValueKey(hasFile ? 'done' : hasError ? 'err' : 'empty'),
                          size: 44,
                          color: hasError
                              ? cs.error
                              : hasFile
                                  ? cs.primary
                                  : cs.onSurfaceVariant,
                        ),
                      ),
                      const SizedBox(height: 10),
                      AnimatedSwitcher(
                        duration: const Duration(milliseconds: 250),
                        child: Text(
                          hasFile
                              ? fileName!
                              : hasError
                                  ? 'اضغط للمحاولة مجدداً'
                                  : 'اضغط لاختيار ملف',
                          key: ValueKey(fileName ?? error ?? 'empty'),
                          style: Theme.of(context)
                              .textTheme
                              .bodyMedium
                              ?.copyWith(
                                fontWeight: hasFile
                                    ? FontWeight.w600
                                    : FontWeight.normal,
                                color: hasError
                                    ? cs.error
                                    : hasFile
                                        ? cs.primary
                                        : cs.onSurfaceVariant,
                              ),
                          textAlign: TextAlign.center,
                          overflow: TextOverflow.ellipsis,
                          maxLines: 2,
                        ),
                      ),
                      if (!hasFile && !hasError) ...[
                        const SizedBox(height: 4),
                        Text(
                          'PDF، Excel، Word، CSV، صور، وأكثر',
                          style: Theme.of(context)
                              .textTheme
                              .bodySmall
                              ?.copyWith(color: cs.outline),
                        ),
                      ],
                    ],
                  ),
          ),
        ),

        // Inline error below the picker
        if (hasError) ...[
          const SizedBox(height: 8),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: Row(
              children: [
                Icon(Icons.info_outline_rounded, size: 14, color: cs.error),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    error!,
                    style: Theme.of(context)
                        .textTheme
                        .bodySmall
                        ?.copyWith(color: cs.error),
                  ),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}

// ── Converting card ───────────────────────────────────────────────────────────

class _ConvertingCard extends StatelessWidget {
  const _ConvertingCard({required this.progress, this.label = 'جارٍ التحويل...'});
  final double progress;
  final String label;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: cs.primaryContainer.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: cs.primary.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(
                  strokeWidth: 2.5,
                  color: cs.primary,
                  value: progress > 0 ? progress : null,
                ),
              ),
              const SizedBox(width: 12),
              Text(
                label,
                style: TextStyle(
                    color: cs.primary, fontWeight: FontWeight.w600),
              ),
              const Spacer(),
              if (progress > 0)
                Text(
                  '${(progress * 100).toStringAsFixed(0)}%',
                  style: TextStyle(
                      color: cs.primary, fontWeight: FontWeight.bold),
                ),
            ],
          ),
          if (progress > 0) ...[
            const SizedBox(height: 10),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: progress,
                minHeight: 6,
                backgroundColor: cs.primary.withValues(alpha: 0.15),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

// ── Result card ───────────────────────────────────────────────────────────────

class _ResultCard extends StatelessWidget {
  const _ResultCard({
    required this.isSuccess,
    required this.message,
    this.action,
  });
  final bool isSuccess;
  final String message;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final color = isSuccess ? const Color(0xFF2E7D32) : Theme.of(context).colorScheme.error;
    final icon =
        isSuccess ? Icons.check_circle_rounded : Icons.error_outline_rounded;

    return Container(
      padding: const EdgeInsets.fromLTRB(14, 12, 8, 12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Row(
        children: [
          Icon(icon, color: color, size: 22),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: TextStyle(
                  color: color, fontWeight: FontWeight.w500, fontSize: 14),
            ),
          ),
          if (action != null) action!,
        ],
      ),
    );
  }
}

// ── Convert button ────────────────────────────────────────────────────────────

class _ConvertButton extends StatelessWidget {
  const _ConvertButton({
    required this.isReady,
    required this.isConverting,
    required this.onPressed,
  });
  final bool isReady;
  final bool isConverting;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      height: 52,
      child: FilledButton.icon(
        onPressed: (isReady && !isConverting) ? onPressed : null,
        style: FilledButton.styleFrom(
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        ),
        icon: isConverting
            ? const SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(
                    strokeWidth: 2.5, color: Colors.white),
              )
            : const Icon(Icons.transform_rounded),
        label: Text(
          isConverting ? 'جارٍ التحويل...' : 'بدء التحويل',
          style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
        ),
      ),
    );
  }
}
