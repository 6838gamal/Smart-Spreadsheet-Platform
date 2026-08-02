import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/router/app_router.dart';
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
  String? _filePickError;
  bool _isPickingFile = false;
  bool _showConvertOptions = false; // expand/collapse conversion settings

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
    setState(() {
      _isPickingFile = true;
      _filePickError = null;
    });
    try {
      final result = await FilePicker.platform.pickFiles(
        allowMultiple: false,
        withData: false,
        withReadStream: false,
      );
      if (!mounted) return;
      if (result == null || result.files.isEmpty) {
        // User cancelled — not an error
        setState(() => _isPickingFile = false);
        return;
      }
      final file = result.files.first;
      if (file.path == null) {
        setState(() {
          _isPickingFile = false;
          _filePickError = 'تعذّر الوصول إلى الملف — حاول مجدداً';
        });
        return;
      }
      setState(() {
        _isPickingFile = false;
        _selectedFilePath = file.path;
        _selectedFileName = file.name;
        _filePickError = null;
        // Reset conversion state when new file is picked
        _selectedSourceFormat = null;
        _selectedTargetFormat = null;
        _showConvertOptions = false;
        ref.read(conversionProvider.notifier).reset();
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isPickingFile = false;
        _filePickError = 'حدث خطأ أثناء اختيار الملف: ${e.toString()}';
      });
    }
  }

  Future<void> _startConversion() async {
    if (_selectedFilePath == null ||
        _selectedSourceFormat == null ||
        _selectedTargetFormat == null) return;

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
    final hasFile = _selectedFilePath != null;

    return Scaffold(
      appBar: AppBar(
        title: const Text('تحويل الملفات'),
        actions: [
          if (hasFile)
            IconButton(
              icon: const Icon(Icons.refresh_rounded),
              tooltip: 'مسح الاختيار',
              onPressed: () => setState(() {
                _selectedFilePath = null;
                _selectedFileName = null;
                _selectedSourceFormat = null;
                _selectedTargetFormat = null;
                _filePickError = null;
                _showConvertOptions = false;
                ref.read(conversionProvider.notifier).reset();
              }),
            ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── File picker ───────────────────────────────────────────────
            _FilePicker(
              isLoading: _isPickingFile,
              fileName: _selectedFileName,
              filePath: _selectedFilePath,
              error: _filePickError,
              onTap: _isPickingFile ? null : _pickFile,
            ).animate().fadeIn(duration: 300.ms),

            // ── Action buttons — appear after file is selected ─────────────
            if (hasFile) ...[
              const SizedBox(height: 24),
              Text('الإجراءات',
                  style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 12),
              _ActionGrid(
                filePath: _selectedFilePath!,
                fileName: _selectedFileName!,
                showConvertOptions: _showConvertOptions,
                onView: () => _handleView(context),
                onPreview: () => _handlePreview(context),
                onConvert: () => setState(
                    () => _showConvertOptions = !_showConvertOptions),
                onSearch: () => context.push(AppRoutes.search),
                onAiChat: () => context.push(
                  AppRoutes.aiChat,
                  extra: {
                    'fileName': _selectedFileName,
                    'filePath': _selectedFilePath,
                  },
                ),
              ).animate().fadeIn(duration: 400.ms).slideY(begin: 0.1),
            ],

            // ── Conversion settings (expandable) ──────────────────────────
            if (hasFile && _showConvertOptions) ...[
              const SizedBox(height: 20),
              _ConversionSettings(
                conversions: _conversions,
                formatIcons: _formatIcons,
                selectedSource: _selectedSourceFormat,
                selectedTarget: _selectedTargetFormat,
                onSourceChanged: (fmt) => setState(() {
                  _selectedSourceFormat = fmt;
                  _selectedTargetFormat = null;
                  ref.read(conversionProvider.notifier).reset();
                }),
                onTargetChanged: (fmt) =>
                    setState(() => _selectedTargetFormat = fmt),
              ).animate().fadeIn(duration: 300.ms).slideY(begin: -0.05),

              const SizedBox(height: 20),

              // ── Conversion status ────────────────────────────────────────
              if (convState.status == ConversionStatus.converting) ...[
                LinearProgressIndicator(value: convState.progress),
                const SizedBox(height: 8),
                Center(
                  child: Text(
                    convState.progress > 0
                        ? 'جارٍ التحويل... ${(convState.progress * 100).toStringAsFixed(0)}%'
                        : 'جارٍ التحويل...',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                ),
                const SizedBox(height: 16),
              ],

              if (convState.status == ConversionStatus.success) ...[
                _StatusCard(
                  color: Colors.green,
                  icon: Icons.check_circle_rounded,
                  message: 'تم التحويل بنجاح!',
                  action: convState.downloadUrl != null
                      ? TextButton.icon(
                          onPressed: () {},
                          icon: const Icon(Icons.download_rounded),
                          label: const Text('تنزيل'),
                        )
                      : null,
                ).animate().fadeIn(),
                const SizedBox(height: 16),
              ],

              if (convState.error != null) ...[
                _StatusCard(
                  color: cs.error,
                  icon: Icons.error_outline_rounded,
                  message: convState.error!,
                  action: TextButton(
                    onPressed: () =>
                        ref.read(conversionProvider.notifier).reset(),
                    child: const Text('إعادة المحاولة'),
                  ),
                ).animate().fadeIn(),
                const SizedBox(height: 16),
              ],

              // ── Convert button ───────────────────────────────────────────
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: (_selectedSourceFormat != null &&
                          _selectedTargetFormat != null &&
                          convState.status != ConversionStatus.converting)
                      ? _startConversion
                      : null,
                  icon: convState.status == ConversionStatus.converting
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                              strokeWidth: 2, color: Colors.white),
                        )
                      : const Icon(Icons.transform_rounded),
                  label: Text(
                    convState.status == ConversionStatus.converting
                        ? 'جارٍ التحويل...'
                        : 'بدء التحويل',
                  ),
                ),
              ),
            ],

            const SizedBox(height: 32),
          ],
        ),
      ),
    );
  }

  void _handleView(BuildContext context) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('عرض: $_selectedFileName'),
        behavior: SnackBarBehavior.floating,
        action: SnackBarAction(label: 'إغلاق', onPressed: () {}),
      ),
    );
  }

  void _handlePreview(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => _FilePreviewSheet(
        fileName: _selectedFileName ?? '',
        filePath: _selectedFilePath ?? '',
      ),
    );
  }
}

// ── File picker widget ────────────────────────────────────────────────────────

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

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(16),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            width: double.infinity,
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              border: Border.all(
                color: error != null
                    ? cs.error
                    : hasFile
                        ? cs.primary
                        : cs.outlineVariant,
                width: (hasFile || error != null) ? 2 : 1,
              ),
              borderRadius: BorderRadius.circular(16),
              color: hasFile
                  ? cs.primaryContainer.withOpacity(0.25)
                  : error != null
                      ? cs.errorContainer.withOpacity(0.2)
                      : null,
            ),
            child: Column(
              children: [
                if (isLoading) ...[
                  const SizedBox(height: 4),
                  const CircularProgressIndicator(),
                  const SizedBox(height: 12),
                  Text(
                    'جارٍ فتح منتقي الملفات...',
                    style: Theme.of(context)
                        .textTheme
                        .bodyMedium
                        ?.copyWith(color: cs.onSurfaceVariant),
                  ),
                  const SizedBox(height: 4),
                ] else ...[
                  Icon(
                    error != null
                        ? Icons.error_outline_rounded
                        : hasFile
                            ? Icons.check_circle_rounded
                            : Icons.upload_file_rounded,
                    size: 40,
                    color: error != null
                        ? cs.error
                        : hasFile
                            ? cs.primary
                            : cs.onSurfaceVariant,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    hasFile
                        ? fileName!
                        : error != null
                            ? 'اضغط للمحاولة مجدداً'
                            : 'اضغط لاختيار ملف',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: error != null
                              ? cs.error
                              : hasFile
                                  ? cs.primary
                                  : cs.onSurfaceVariant,
                          fontWeight:
                              hasFile ? FontWeight.w600 : FontWeight.normal,
                        ),
                    textAlign: TextAlign.center,
                    overflow: TextOverflow.ellipsis,
                    maxLines: 2,
                  ),
                  if (!hasFile && error == null)
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Text(
                        'PDF، Excel، Word، CSV، صور، وأكثر',
                        style: Theme.of(context)
                            .textTheme
                            .bodySmall
                            ?.copyWith(color: cs.outline),
                        textAlign: TextAlign.center,
                      ),
                    ),
                ],
              ],
            ),
          ),
        ),

        // Error message below picker
        if (error != null) ...[
          const SizedBox(height: 8),
          Row(
            children: [
              Icon(Icons.info_outline_rounded,
                  size: 14, color: cs.error),
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
        ],
      ],
    );
  }
}

// ── Action grid ───────────────────────────────────────────────────────────────

class _ActionGrid extends StatelessWidget {
  const _ActionGrid({
    required this.filePath,
    required this.fileName,
    required this.showConvertOptions,
    required this.onView,
    required this.onPreview,
    required this.onConvert,
    required this.onSearch,
    required this.onAiChat,
  });

  final String filePath;
  final String fileName;
  final bool showConvertOptions;
  final VoidCallback onView;
  final VoidCallback onPreview;
  final VoidCallback onConvert;
  final VoidCallback onSearch;
  final VoidCallback onAiChat;

  @override
  Widget build(BuildContext context) {
    final actions = [
      _ActionItem(
        icon: Icons.open_in_new_rounded,
        label: 'عرض',
        color: Colors.blue,
        onTap: onView,
      ),
      _ActionItem(
        icon: Icons.preview_rounded,
        label: 'معاينة',
        color: Colors.purple,
        onTap: onPreview,
      ),
      _ActionItem(
        icon: Icons.transform_rounded,
        label: 'تحويل',
        color: Colors.orange,
        isActive: showConvertOptions,
        onTap: onConvert,
      ),
      _ActionItem(
        icon: Icons.search_rounded,
        label: 'بحث',
        color: Colors.teal,
        onTap: onSearch,
      ),
      _ActionItem(
        icon: Icons.smart_toy_rounded,
        label: 'ذكاء اصطناعي',
        color: Colors.indigo,
        onTap: onAiChat,
      ),
    ];

    return GridView.count(
      crossAxisCount: 3,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisSpacing: 10,
      mainAxisSpacing: 10,
      childAspectRatio: 1.1,
      children: actions
          .asMap()
          .entries
          .map(
            (e) => e.value
                .animate(delay: Duration(milliseconds: 60 * e.key))
                .fadeIn(duration: 250.ms)
                .scale(
                    begin: const Offset(0.85, 0.85),
                    duration: 300.ms,
                    curve: Curves.easeOutBack),
          )
          .toList(),
    );
  }
}

class _ActionItem extends StatelessWidget {
  const _ActionItem({
    required this.icon,
    required this.label,
    required this.color,
    required this.onTap,
    this.isActive = false,
  });

  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;
  final bool isActive;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Material(
      color: isActive
          ? color.withOpacity(0.15)
          : cs.surfaceContainerHighest.withOpacity(0.5),
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: isActive
                ? Border.all(color: color, width: 1.5)
                : null,
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: color.withOpacity(0.15),
                  shape: BoxShape.circle,
                ),
                child: Icon(icon, color: color, size: 22),
              ),
              const SizedBox(height: 6),
              Text(
                label,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      fontWeight: FontWeight.w600,
                      color: isActive ? color : null,
                    ),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Conversion settings ───────────────────────────────────────────────────────

class _ConversionSettings extends StatelessWidget {
  const _ConversionSettings({
    required this.conversions,
    required this.formatIcons,
    required this.selectedSource,
    required this.selectedTarget,
    required this.onSourceChanged,
    required this.onTargetChanged,
  });

  final Map<String, List<String>> conversions;
  final Map<String, IconData> formatIcons;
  final String? selectedSource;
  final String? selectedTarget;
  final ValueChanged<String> onSourceChanged;
  final ValueChanged<String> onTargetChanged;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: cs.surfaceContainerHighest.withOpacity(0.4),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: cs.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.settings_rounded, size: 18, color: cs.primary),
              const SizedBox(width: 8),
              Text(
                'إعدادات التحويل',
                style: Theme.of(context)
                    .textTheme
                    .titleSmall
                    ?.copyWith(color: cs.primary),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Source format
          Text('من: صيغة المصدر',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  )),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: conversions.keys.map((fmt) {
              final isSelected = selectedSource == fmt;
              return ChoiceChip(
                avatar: Icon(formatIcons[fmt], size: 16),
                label: Text(fmt),
                selected: isSelected,
                onSelected: (_) => onSourceChanged(fmt),
              );
            }).toList(),
          ),

          if (selectedSource != null) ...[
            const SizedBox(height: 16),
            const Divider(height: 1),
            const SizedBox(height: 16),

            // Target format
            Text('إلى: صيغة الهدف',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                    )),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children:
                  (conversions[selectedSource] ?? []).map((fmt) {
                final isSelected = selectedTarget == fmt;
                return ChoiceChip(
                  avatar: Icon(formatIcons[fmt], size: 16),
                  label: Text(fmt),
                  selected: isSelected,
                  onSelected: (_) => onTargetChanged(fmt),
                );
              }).toList(),
            ),
          ],
        ],
      ),
    );
  }
}

// ── Status card ───────────────────────────────────────────────────────────────

class _StatusCard extends StatelessWidget {
  const _StatusCard({
    required this.color,
    required this.icon,
    required this.message,
    this.action,
  });

  final Color color;
  final IconData icon;
  final String message;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.5)),
      ),
      child: Row(
        children: [
          Icon(icon, color: color),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: TextStyle(color: color, fontWeight: FontWeight.w500),
            ),
          ),
          if (action != null) action!,
        ],
      ),
    );
  }
}

// ── File preview bottom sheet ─────────────────────────────────────────────────

class _FilePreviewSheet extends StatelessWidget {
  const _FilePreviewSheet({
    required this.fileName,
    required this.filePath,
  });

  final String fileName;
  final String filePath;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final ext = fileName.split('.').last.toLowerCase();
    final isImage = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'].contains(ext);

    return DraggableScrollableSheet(
      initialChildSize: 0.6,
      minChildSize: 0.4,
      maxChildSize: 0.92,
      expand: false,
      builder: (_, controller) => Column(
        children: [
          // Handle
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: cs.outlineVariant,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),

          // Title
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                const Icon(Icons.preview_rounded),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    fileName,
                    style: Theme.of(context).textTheme.titleMedium,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close_rounded),
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ],
            ),
          ),

          const Divider(height: 1),

          // Preview content
          Expanded(
            child: ListView(
              controller: controller,
              padding: const EdgeInsets.all(16),
              children: [
                if (isImage)
                  ClipRRect(
                    borderRadius: BorderRadius.circular(12),
                    child: Image.file(
                      File(filePath),
                      errorBuilder: (_, __, ___) => _PreviewPlaceholder(
                          ext: ext, fileName: fileName),
                    ),
                  )
                else
                  _PreviewPlaceholder(ext: ext, fileName: fileName),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _PreviewPlaceholder extends StatelessWidget {
  const _PreviewPlaceholder({required this.ext, required this.fileName});
  final String ext;
  final String fileName;

  static const Map<String, IconData> _extIcons = {
    'pdf': Icons.picture_as_pdf_rounded,
    'xlsx': Icons.table_chart_rounded,
    'xls': Icons.table_chart_rounded,
    'csv': Icons.grid_on_rounded,
    'docx': Icons.description_rounded,
    'doc': Icons.description_rounded,
    'pptx': Icons.slideshow_rounded,
    'ppt': Icons.slideshow_rounded,
    'json': Icons.data_object_rounded,
    'txt': Icons.text_fields_rounded,
  };

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final icon = _extIcons[ext] ?? Icons.insert_drive_file_rounded;

    return Container(
      padding: const EdgeInsets.symmetric(vertical: 48),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 72, color: cs.primary.withOpacity(0.6)),
          const SizedBox(height: 16),
          Text(
            fileName,
            style: Theme.of(context).textTheme.titleMedium,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 8),
          Text(
            'المعاينة غير متاحة لهذا النوع من الملفات',
            style: Theme.of(context)
                .textTheme
                .bodySmall
                ?.copyWith(color: cs.outline),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}
