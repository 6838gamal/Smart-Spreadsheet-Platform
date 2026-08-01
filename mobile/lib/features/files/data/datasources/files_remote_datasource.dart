import 'dart:io';

import 'package:dio/dio.dart';

import '../../../../core/constants/api_constants.dart';
import '../../../../core/network/dio_client.dart';
import '../models/file_model.dart';

abstract class FilesRemoteDataSource {
  Future<List<FileModel>> getFiles({int page = 1, String? section});
  Future<FileModel> uploadFile(
    File file, {
    ProgressCallback? onProgress,
    CancelToken? cancelToken,
  });
  Future<void> deleteFile(int id);
  Future<FileModel> toggleFavorite(int id);
}

class FilesRemoteDataSourceImpl implements FilesRemoteDataSource {
  final DioClient _client;

  const FilesRemoteDataSourceImpl(this._client);

  @override
  Future<List<FileModel>> getFiles({int page = 1, String? section}) async {
    final response = await _client.get(
      ApiConstants.files,
      queryParameters: {
        'page': page,
        'per_page': 20,
        if (section != null) 'section': section,
      },
    );

    final data = response.data;
    List<dynamic> items;

    if (data is Map<String, dynamic>) {
      items = data['items'] as List? ??
          data['files'] as List? ??
          data['data'] as List? ??
          [];
    } else if (data is List) {
      items = data;
    } else {
      items = [];
    }

    return items
        .map((e) => FileModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<FileModel> uploadFile(
    File file, {
    ProgressCallback? onProgress,
    CancelToken? cancelToken,
  }) async {
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(
        file.path,
        filename: file.path.split('/').last,
      ),
    });

    final response = await _client.postFormData(
      ApiConstants.fileUpload,
      formData,
      onSendProgress: onProgress,
      cancelToken: cancelToken,
    );

    return FileModel.fromJson(response.data as Map<String, dynamic>);
  }

  @override
  Future<void> deleteFile(int id) async {
    await _client.delete(ApiConstants.fileById(id));
  }

  @override
  Future<FileModel> toggleFavorite(int id) async {
    final response = await _client.post('${ApiConstants.fileById(id)}/favorite');
    return FileModel.fromJson(response.data as Map<String, dynamic>);
  }
}
