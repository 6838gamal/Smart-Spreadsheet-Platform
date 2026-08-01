// coverage:ignore-file
// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'files_provider.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

T _$identity<T>(T value) => value;

final _privateConstructorUsedError = UnsupportedError(
  'It seems like you constructed your class using `MyClass._()`. This constructor is only meant to be used by freezed and you are not supposed to need it nor use it.\nPlease check the documentation here for more information: https://github.com/rrousselGit/freezed#adding-getters-and-methods-to-our-models',
);

/// @nodoc
mixin _$FilesState {
  List<FileEntity> get files => throw _privateConstructorUsedError;
  bool get isLoading => throw _privateConstructorUsedError;
  bool get isUploading => throw _privateConstructorUsedError;
  double get uploadProgress => throw _privateConstructorUsedError;
  String? get error => throw _privateConstructorUsedError;
  bool get hasMore => throw _privateConstructorUsedError;
  int get currentPage => throw _privateConstructorUsedError;
  String get activeSection => throw _privateConstructorUsedError;

  /// Create a copy of FilesState
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  $FilesStateCopyWith<FilesState> get copyWith =>
      throw _privateConstructorUsedError;
}

/// @nodoc
abstract class $FilesStateCopyWith<$Res> {
  factory $FilesStateCopyWith(
    FilesState value,
    $Res Function(FilesState) then,
  ) = _$FilesStateCopyWithImpl<$Res, FilesState>;
  @useResult
  $Res call({
    List<FileEntity> files,
    bool isLoading,
    bool isUploading,
    double uploadProgress,
    String? error,
    bool hasMore,
    int currentPage,
    String activeSection,
  });
}

/// @nodoc
class _$FilesStateCopyWithImpl<$Res, $Val extends FilesState>
    implements $FilesStateCopyWith<$Res> {
  _$FilesStateCopyWithImpl(this._value, this._then);

  // ignore: unused_field
  final $Val _value;
  // ignore: unused_field
  final $Res Function($Val) _then;

  /// Create a copy of FilesState
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? files = null,
    Object? isLoading = null,
    Object? isUploading = null,
    Object? uploadProgress = null,
    Object? error = freezed,
    Object? hasMore = null,
    Object? currentPage = null,
    Object? activeSection = null,
  }) {
    return _then(
      _value.copyWith(
            files: null == files
                ? _value.files
                : files // ignore: cast_nullable_to_non_nullable
                      as List<FileEntity>,
            isLoading: null == isLoading
                ? _value.isLoading
                : isLoading // ignore: cast_nullable_to_non_nullable
                      as bool,
            isUploading: null == isUploading
                ? _value.isUploading
                : isUploading // ignore: cast_nullable_to_non_nullable
                      as bool,
            uploadProgress: null == uploadProgress
                ? _value.uploadProgress
                : uploadProgress // ignore: cast_nullable_to_non_nullable
                      as double,
            error: freezed == error
                ? _value.error
                : error // ignore: cast_nullable_to_non_nullable
                      as String?,
            hasMore: null == hasMore
                ? _value.hasMore
                : hasMore // ignore: cast_nullable_to_non_nullable
                      as bool,
            currentPage: null == currentPage
                ? _value.currentPage
                : currentPage // ignore: cast_nullable_to_non_nullable
                      as int,
            activeSection: null == activeSection
                ? _value.activeSection
                : activeSection // ignore: cast_nullable_to_non_nullable
                      as String,
          )
          as $Val,
    );
  }
}

/// @nodoc
abstract class _$$FilesStateImplCopyWith<$Res>
    implements $FilesStateCopyWith<$Res> {
  factory _$$FilesStateImplCopyWith(
    _$FilesStateImpl value,
    $Res Function(_$FilesStateImpl) then,
  ) = __$$FilesStateImplCopyWithImpl<$Res>;
  @override
  @useResult
  $Res call({
    List<FileEntity> files,
    bool isLoading,
    bool isUploading,
    double uploadProgress,
    String? error,
    bool hasMore,
    int currentPage,
    String activeSection,
  });
}

/// @nodoc
class __$$FilesStateImplCopyWithImpl<$Res>
    extends _$FilesStateCopyWithImpl<$Res, _$FilesStateImpl>
    implements _$$FilesStateImplCopyWith<$Res> {
  __$$FilesStateImplCopyWithImpl(
    _$FilesStateImpl _value,
    $Res Function(_$FilesStateImpl) _then,
  ) : super(_value, _then);

  /// Create a copy of FilesState
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? files = null,
    Object? isLoading = null,
    Object? isUploading = null,
    Object? uploadProgress = null,
    Object? error = freezed,
    Object? hasMore = null,
    Object? currentPage = null,
    Object? activeSection = null,
  }) {
    return _then(
      _$FilesStateImpl(
        files: null == files
            ? _value._files
            : files // ignore: cast_nullable_to_non_nullable
                  as List<FileEntity>,
        isLoading: null == isLoading
            ? _value.isLoading
            : isLoading // ignore: cast_nullable_to_non_nullable
                  as bool,
        isUploading: null == isUploading
            ? _value.isUploading
            : isUploading // ignore: cast_nullable_to_non_nullable
                  as bool,
        uploadProgress: null == uploadProgress
            ? _value.uploadProgress
            : uploadProgress // ignore: cast_nullable_to_non_nullable
                  as double,
        error: freezed == error
            ? _value.error
            : error // ignore: cast_nullable_to_non_nullable
                  as String?,
        hasMore: null == hasMore
            ? _value.hasMore
            : hasMore // ignore: cast_nullable_to_non_nullable
                  as bool,
        currentPage: null == currentPage
            ? _value.currentPage
            : currentPage // ignore: cast_nullable_to_non_nullable
                  as int,
        activeSection: null == activeSection
            ? _value.activeSection
            : activeSection // ignore: cast_nullable_to_non_nullable
                  as String,
      ),
    );
  }
}

/// @nodoc

class _$FilesStateImpl implements _FilesState {
  const _$FilesStateImpl({
    final List<FileEntity> files = const [],
    this.isLoading = false,
    this.isUploading = false,
    this.uploadProgress = 0.0,
    this.error,
    this.hasMore = false,
    this.currentPage = 1,
    this.activeSection = 'all',
  }) : _files = files;

  final List<FileEntity> _files;
  @override
  @JsonKey()
  List<FileEntity> get files {
    if (_files is EqualUnmodifiableListView) return _files;
    // ignore: implicit_dynamic_type
    return EqualUnmodifiableListView(_files);
  }

  @override
  @JsonKey()
  final bool isLoading;
  @override
  @JsonKey()
  final bool isUploading;
  @override
  @JsonKey()
  final double uploadProgress;
  @override
  final String? error;
  @override
  @JsonKey()
  final bool hasMore;
  @override
  @JsonKey()
  final int currentPage;
  @override
  @JsonKey()
  final String activeSection;

  @override
  String toString() {
    return 'FilesState(files: $files, isLoading: $isLoading, isUploading: $isUploading, uploadProgress: $uploadProgress, error: $error, hasMore: $hasMore, currentPage: $currentPage, activeSection: $activeSection)';
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _$FilesStateImpl &&
            const DeepCollectionEquality().equals(other._files, _files) &&
            (identical(other.isLoading, isLoading) ||
                other.isLoading == isLoading) &&
            (identical(other.isUploading, isUploading) ||
                other.isUploading == isUploading) &&
            (identical(other.uploadProgress, uploadProgress) ||
                other.uploadProgress == uploadProgress) &&
            (identical(other.error, error) || other.error == error) &&
            (identical(other.hasMore, hasMore) || other.hasMore == hasMore) &&
            (identical(other.currentPage, currentPage) ||
                other.currentPage == currentPage) &&
            (identical(other.activeSection, activeSection) ||
                other.activeSection == activeSection));
  }

  @override
  int get hashCode => Object.hash(
    runtimeType,
    const DeepCollectionEquality().hash(_files),
    isLoading,
    isUploading,
    uploadProgress,
    error,
    hasMore,
    currentPage,
    activeSection,
  );

  /// Create a copy of FilesState
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  @pragma('vm:prefer-inline')
  _$$FilesStateImplCopyWith<_$FilesStateImpl> get copyWith =>
      __$$FilesStateImplCopyWithImpl<_$FilesStateImpl>(this, _$identity);
}

abstract class _FilesState implements FilesState {
  const factory _FilesState({
    final List<FileEntity> files,
    final bool isLoading,
    final bool isUploading,
    final double uploadProgress,
    final String? error,
    final bool hasMore,
    final int currentPage,
    final String activeSection,
  }) = _$FilesStateImpl;

  @override
  List<FileEntity> get files;
  @override
  bool get isLoading;
  @override
  bool get isUploading;
  @override
  double get uploadProgress;
  @override
  String? get error;
  @override
  bool get hasMore;
  @override
  int get currentPage;
  @override
  String get activeSection;

  /// Create a copy of FilesState
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  _$$FilesStateImplCopyWith<_$FilesStateImpl> get copyWith =>
      throw _privateConstructorUsedError;
}
