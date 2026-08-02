import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:shimmer/shimmer.dart';

import '../../../../core/router/app_router.dart';
import '../../../../core/utils/file_picker_util.dart';
import '../../../../shared/widgets/file_card.dart';
import '../providers/files_provider.dart';

class FilesScreen extends ConsumerStatefulWidget {
  const FilesScreen({super.key});

  @override
  ConsumerState<FilesScreen> createState() => _FilesScreenState();
}

class _FilesScreenState extends ConsumerState<FilesScreen> {
  bool _isGrid = true;
  final _sections = [
    ('all', 'الكل'),
    ('recent', 'الأخيرة'),
    ('favorites', 'المفضلة'),
    ('shared', 'المشتركة'),
    ('offline', 'غير متصل'),
    ('downloads', 'التنزيلات'),
    ('trash', 'المحذوفة'),
  ];

  Future<void> _pickAndUpload() async {
    final picked = await pickFile();

    if (picked.cancelled) return;

    if (!picked.success) {
      if (mounted) {
        if (picked.needsSettings) {
          await showPermissionSettingsDialog(context);
        } else {
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text(picked.errorMessage ?? 'حدث خطأ أثناء اختيار الملف'),
            backgroundColor: Theme.of(context).colorScheme.error,
          ));
        }
      }
      return;
    }

    if (!mounted) return;

    final path = picked.path;
    if (path == null) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: const Text('تعذّر الوصول إلى مسار الملف'),
        backgroundColor: Theme.of(context).colorScheme.error,
      ));
      return;
    }

    final success =
        await ref.read(filesProvider.notifier).uploadFile(File(path));
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(success ? 'تم رفع الملف بنجاح' : 'فشل رفع الملف'),
        backgroundColor:
            success ? Colors.green : Theme.of(context).colorScheme.error,
      ));
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(filesProvider);
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('ملفاتي'),
        actions: [
          IconButton(
            icon: Icon(_isGrid ? Icons.list_rounded : Icons.grid_view_rounded),
            onPressed: () => setState(() => _isGrid = !_isGrid),
          ),
          IconButton(
            icon: const Icon(Icons.search_rounded),
            onPressed: () => context.push(AppRoutes.search),
          ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(48),
          child: SizedBox(
            height: 48,
            child: ListView.builder(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              scrollDirection: Axis.horizontal,
              itemCount: _sections.length,
              itemBuilder: (ctx, i) {
                final (key, label) = _sections[i];
                final isActive = state.activeSection == key;
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: FilterChip(
                    label: Text(label),
                    selected: isActive,
                    onSelected: (_) =>
                        ref.read(filesProvider.notifier).setSection(key),
                  ),
                );
              },
            ),
          ),
        ),
      ),
      body: Column(
        children: [
          // Upload progress
          if (state.isUploading)
            LinearProgressIndicator(value: state.uploadProgress),

          // File list / grid
          Expanded(
            child: RefreshIndicator(
              onRefresh: () =>
                  ref.read(filesProvider.notifier).loadFiles(refresh: true),
              child: state.isLoading && state.files.isEmpty
                  ? _buildShimmer(isGrid: _isGrid)
                  : state.files.isEmpty
                      ? _buildEmpty()
                      : _isGrid
                          ? _buildGrid(state, cs)
                          : _buildList(state),
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: state.isUploading ? null : _pickAndUpload,
        icon: state.isUploading
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2.5))
            : const Icon(Icons.upload_rounded),
        label: Text(state.isUploading ? 'جارٍ الرفع...' : 'رفع ملف'),
      ),
    );
  }

  Widget _buildGrid(FilesState state, ColorScheme cs) {
    return GridView.builder(
      padding: const EdgeInsets.all(12),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        mainAxisSpacing: 12,
        crossAxisSpacing: 12,
        childAspectRatio: 1.1,
      ),
      itemCount: state.files.length,
      itemBuilder: (ctx, i) {
        return FileCard(file: state.files[i])
            .animate(delay: (i * 30).ms)
            .fadeIn(duration: 250.ms)
            .scale(begin: const Offset(0.95, 0.95), duration: 250.ms);
      },
    );
  }

  Widget _buildList(FilesState state) {
    return ListView.separated(
      padding: const EdgeInsets.all(12),
      itemCount: state.files.length,
      separatorBuilder: (_, __) => const SizedBox(height: 8),
      itemBuilder: (ctx, i) {
        return FileCard(file: state.files[i], compact: false, isList: true)
            .animate(delay: (i * 30).ms)
            .fadeIn(duration: 250.ms)
            .slideX(begin: 0.05, duration: 250.ms);
      },
    );
  }

  Widget _buildShimmer({required bool isGrid}) {
    return Shimmer.fromColors(
      baseColor: Colors.grey.shade300,
      highlightColor: Colors.grey.shade100,
      child: isGrid
          ? GridView.builder(
              padding: const EdgeInsets.all(12),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                mainAxisSpacing: 12,
                crossAxisSpacing: 12,
              ),
              itemCount: 8,
              itemBuilder: (_, __) => Container(
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                ),
              ),
            )
          : ListView.builder(
              padding: const EdgeInsets.all(12),
              itemCount: 6,
              itemBuilder: (_, __) => Container(
                height: 72,
                margin: const EdgeInsets.only(bottom: 8),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
            ),
    );
  }

  Widget _buildEmpty() {
    final cs = Theme.of(context).colorScheme;
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.folder_open_rounded,
              size: 80, color: cs.outlineVariant),
          const SizedBox(height: 16),
          Text('لا توجد ملفات',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          Text(
            'اضغط على "رفع ملف" لإضافة أول ملف',
            style: Theme.of(context)
                .textTheme
                .bodyMedium
                ?.copyWith(color: cs.onSurfaceVariant),
          ),
        ],
      ),
    );
  }
}
