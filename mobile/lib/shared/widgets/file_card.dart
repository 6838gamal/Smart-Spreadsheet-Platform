import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/files/domain/entities/file_entity.dart';
import '../../features/files/presentation/providers/files_provider.dart';

/// Reusable file card widget used in home (compact horizontal) and files screen (grid/list).
class FileCard extends ConsumerWidget {
  const FileCard({
    required this.file,
    this.compact = false,
    this.isList = false,
    super.key,
  });

  final FileEntity file;
  final bool compact;
  final bool isList;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (isList) return _buildList(context, ref);
    if (compact) return _buildCompact(context);
    return _buildGrid(context, ref);
  }

  Widget _buildGrid(BuildContext context, WidgetRef ref) {
    final cs = Theme.of(context).colorScheme;
    return GestureDetector(
      onTap: () => context.push('/files/${file.id}'),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(file.typeIcon, style: const TextStyle(fontSize: 28)),
                  IconButton(
                    icon: Icon(
                      file.isFavorite == true
                          ? Icons.star_rounded
                          : Icons.star_outline_rounded,
                      size: 18,
                      color: file.isFavorite == true ? Colors.amber : cs.outline,
                    ),
                    onPressed: () =>
                        ref.read(filesProvider.notifier).toggleFavorite(file.id),
                    visualDensity: VisualDensity.compact,
                  ),
                ],
              ),
              const Spacer(),
              Text(
                file.originalName,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.w500,
                    ),
              ),
              const SizedBox(height: 4),
              Text(
                file.sizeFormatted,
                style: Theme.of(context)
                    .textTheme
                    .bodySmall
                    ?.copyWith(color: cs.onSurfaceVariant),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildCompact(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return GestureDetector(
      onTap: () => context.push('/files/${file.id}'),
      child: Container(
        width: 120,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: cs.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(file.typeIcon, style: const TextStyle(fontSize: 32)),
            const SizedBox(height: 8),
            Text(
              file.originalName,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    fontWeight: FontWeight.w500,
                  ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildList(BuildContext context, WidgetRef ref) {
    final cs = Theme.of(context).colorScheme;
    return ListTile(
      onTap: () => context.push('/files/${file.id}'),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: cs.outlineVariant, width: 0.5),
      ),
      leading: Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          color: cs.primaryContainer,
          borderRadius: BorderRadius.circular(10),
        ),
        child: Center(
          child: Text(file.typeIcon, style: const TextStyle(fontSize: 22)),
        ),
      ),
      title: Text(file.originalName,
          maxLines: 1, overflow: TextOverflow.ellipsis),
      subtitle: Text(
          '${file.sizeFormatted} • ${file.extension.toUpperCase()}'),
      trailing: IconButton(
        icon: Icon(
          file.isFavorite == true
              ? Icons.star_rounded
              : Icons.star_outline_rounded,
          color: file.isFavorite == true ? Colors.amber : null,
        ),
        onPressed: () =>
            ref.read(filesProvider.notifier).toggleFavorite(file.id),
      ),
    );
  }
}
