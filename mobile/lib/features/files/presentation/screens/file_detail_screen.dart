import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/router/app_router.dart';
import '../providers/files_provider.dart';
import '../../domain/entities/file_entity.dart';

class FileDetailScreen extends ConsumerWidget {
  const FileDetailScreen({required this.fileId, super.key});
  final int fileId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final files = ref.watch(filesProvider);
    final file = files.files.where((f) => f.id == fileId).firstOrNull;
    final cs = Theme.of(context).colorScheme;

    if (file == null) {
      return Scaffold(
        appBar: AppBar(),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(file.originalName,
            overflow: TextOverflow.ellipsis, maxLines: 1),
        actions: [
          IconButton(
            icon: Icon(
              file.isFavorite == true
                  ? Icons.star_rounded
                  : Icons.star_outline_rounded,
              color: file.isFavorite == true ? Colors.amber : null,
            ),
            onPressed: () =>
                ref.read(filesProvider.notifier).toggleFavorite(file.id),
          ),
          PopupMenuButton<String>(
            onSelected: (v) async {
              if (v == 'delete') {
                final confirm = await showDialog<bool>(
                  context: context,
                  builder: (_) => AlertDialog(
                    title: const Text('حذف الملف'),
                    content: const Text('هل أنت متأكد؟'),
                    actions: [
                      TextButton(
                          onPressed: () => Navigator.pop(context, false),
                          child: const Text('إلغاء')),
                      FilledButton(
                          onPressed: () => Navigator.pop(context, true),
                          child: const Text('حذف')),
                    ],
                  ),
                );
                if (confirm == true) {
                  await ref
                      .read(filesProvider.notifier)
                      .deleteFile(file.id);
                  if (context.mounted) context.pop();
                }
              }
            },
            itemBuilder: (_) => [
              const PopupMenuItem(value: 'delete', child: Text('حذف')),
            ],
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // File icon hero
            Center(
              child: Container(
                width: 100,
                height: 100,
                decoration: BoxDecoration(
                  color: cs.primaryContainer,
                  borderRadius: BorderRadius.circular(24),
                ),
                child: Center(
                  child: Text(file.typeIcon, style: const TextStyle(fontSize: 48)),
                ),
              )
                  .animate()
                  .scale(duration: 400.ms, curve: Curves.elasticOut),
            ),
            const SizedBox(height: 16),
            Center(
              child: Text(file.originalName,
                  style: Theme.of(context).textTheme.titleLarge,
                  textAlign: TextAlign.center),
            ),
            const SizedBox(height: 24),

            // Details card
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    _DetailRow(label: 'الحجم', value: file.sizeFormatted),
                    _DetailRow(label: 'الامتداد', value: file.extension.toUpperCase()),
                    _DetailRow(label: 'الحالة', value: file.status),
                    _DetailRow(
                        label: 'تاريخ الرفع',
                        value: file.uploadedAt.toLocal().toString().substring(0, 16)),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 20),

            // Actions
            FilledButton.icon(
              onPressed: () => context.go(AppRoutes.convert),
              icon: const Icon(Icons.transform_rounded),
              label: const Text('تحويل الملف'),
            ),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: () => context.go(AppRoutes.aiChat),
              icon: const Icon(Icons.smart_toy_rounded),
              label: const Text('تحليل بالذكاء الاصطناعي'),
            ),
          ],
        ),
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  final String label;
  final String value;
  const _DetailRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label,
              style: TextStyle(color: cs.onSurfaceVariant)),
          Text(value,
              style: Theme.of(context)
                  .textTheme
                  .bodyMedium
                  ?.copyWith(fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }
}
