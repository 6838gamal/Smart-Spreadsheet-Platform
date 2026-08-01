import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../shared/widgets/file_card.dart';
import '../providers/search_provider.dart';

class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key});

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  final _searchCtrl = TextEditingController();
  final _focusNode = FocusNode();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _focusNode.requestFocus());
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(searchProvider);

    return Scaffold(
      appBar: AppBar(
        titleSpacing: 0,
        title: TextField(
          controller: _searchCtrl,
          focusNode: _focusNode,
          onChanged: (q) => ref.read(searchProvider.notifier).search(q),
          decoration: InputDecoration(
            hintText: 'ابحث في الملفات والتحليلات...',
            border: InputBorder.none,
            prefixIcon: const Icon(Icons.search_rounded),
            suffixIcon: _searchCtrl.text.isNotEmpty
                ? IconButton(
                    icon: const Icon(Icons.close_rounded),
                    onPressed: () {
                      _searchCtrl.clear();
                      ref.read(searchProvider.notifier).clear();
                    },
                  )
                : null,
          ),
        ),
      ),
      body: Column(
        children: [
          // Filter chips
          if (_searchCtrl.text.isNotEmpty || state.results.isNotEmpty)
            _FilterBar(),

          // Results
          Expanded(
            child: state.isLoading
                ? const Center(child: CircularProgressIndicator())
                : state.results.isEmpty && _searchCtrl.text.isNotEmpty
                    ? _buildNoResults(context)
                    : state.results.isEmpty
                        ? _buildSuggestions(context)
                        : _buildResults(state),
          ),
        ],
      ),
    );
  }

  Widget _buildResults(SearchState state) {
    return ListView.separated(
      padding: const EdgeInsets.all(12),
      itemCount: state.results.length,
      separatorBuilder: (_, __) => const SizedBox(height: 8),
      itemBuilder: (ctx, i) {
        final file = state.results[i];
        return FileCard(file: file, isList: true)
            .animate(delay: (i * 30).ms)
            .fadeIn(duration: 250.ms)
            .slideX(begin: 0.05, duration: 250.ms);
      },
    );
  }

  Widget _buildNoResults(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.search_off_rounded, size: 64, color: cs.outlineVariant),
          const SizedBox(height: 16),
          Text('لا توجد نتائج',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          Text('جرب كلمات بحث مختلفة',
              style: Theme.of(context)
                  .textTheme
                  .bodyMedium
                  ?.copyWith(color: cs.onSurfaceVariant)),
        ],
      ),
    );
  }

  Widget _buildSuggestions(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('اقتراحات البحث',
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    color: cs.onSurfaceVariant,
                  )),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              'PDF',
              'Excel',
              'صور',
              'عقود',
              'فواتير',
              'تقارير',
            ].map((s) => ActionChip(
                  label: Text(s),
                  onPressed: () {
                    _searchCtrl.text = s;
                    ref.read(searchProvider.notifier).search(s);
                  },
                )).toList(),
          ),
        ],
      ),
    );
  }
}

class _FilterBar extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(searchProvider);
    final filters = [
      ('all', 'الكل'),
      ('pdf', 'PDF'),
      ('excel', 'Excel'),
      ('image', 'صور'),
      ('word', 'Word'),
    ];

    return Container(
      height: 48,
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: ListView.separated(
        padding: const EdgeInsets.symmetric(horizontal: 12),
        scrollDirection: Axis.horizontal,
        itemCount: filters.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (ctx, i) {
          final (key, label) = filters[i];
          return FilterChip(
            label: Text(label),
            selected: state.activeFilter == key,
            onSelected: (_) =>
                ref.read(searchProvider.notifier).setFilter(key),
          );
        },
      ),
    );
  }
}
