import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/constants/api_constants.dart';
import '../../../../core/network/dio_client.dart';
import '../../../files/data/models/file_model.dart';
import '../../../files/domain/entities/file_entity.dart';

class SearchState {
  final List<FileEntity> results;
  final bool isLoading;
  final String query;
  final String activeFilter;
  final String? error;

  const SearchState({
    this.results = const [],
    this.isLoading = false,
    this.query = '',
    this.activeFilter = 'all',
    this.error,
  });

  SearchState copyWith({
    List<FileEntity>? results,
    bool? isLoading,
    String? query,
    String? activeFilter,
    String? error,
  }) =>
      SearchState(
        results: results ?? this.results,
        isLoading: isLoading ?? this.isLoading,
        query: query ?? this.query,
        activeFilter: activeFilter ?? this.activeFilter,
        error: error ?? this.error,
      );
}

final searchProvider =
    StateNotifierProvider<SearchNotifier, SearchState>((ref) {
  return SearchNotifier(ref.watch(dioClientProvider));
});

class SearchNotifier extends StateNotifier<SearchState> {
  final DioClient _client;
  Timer? _debounce;

  SearchNotifier(this._client) : super(const SearchState());

  void search(String query) {
    state = state.copyWith(query: query);
    _debounce?.cancel();

    if (query.trim().length < 2) {
      state = state.copyWith(results: [], isLoading: false);
      return;
    }

    _debounce = Timer(const Duration(milliseconds: 400), () => _execute(query));
  }

  Future<void> _execute(String query) async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final response = await _client.get(ApiConstants.search, queryParameters: {
        'q': query,
        if (state.activeFilter != 'all') 'type': state.activeFilter,
      });
      final data = response.data as Map<String, dynamic>;
      final items = (data['items'] as List?) ?? [];
      state = state.copyWith(
        results: items
            .map((e) =>
                FileModel.fromJson(e as Map<String, dynamic>).toEntity())
            .toList(),
        isLoading: false,
      );
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString(), results: []);
    }
  }

  void setFilter(String filter) {
    state = state.copyWith(activeFilter: filter);
    if (state.query.isNotEmpty) _execute(state.query);
  }

  void clear() {
    _debounce?.cancel();
    state = const SearchState();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    super.dispose();
  }
}
