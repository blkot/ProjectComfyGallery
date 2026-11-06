import Foundation
import Observation

@MainActor
@Observable
final class PhotoLibrarySaver {
    private(set) var isSaving = false
    private(set) var message: String?
    private(set) var permissionDenied = false
    private let apiClient: APIClient

    init(apiClient: APIClient) { self.apiClient = apiClient }

    func clearMessage() { if !isSaving { message = nil; permissionDenied = false } }

    func save(_ item: MobileMediaSummary) async {
        guard !isSaving else { return }
        isSaving = true
        permissionDenied = false
        message = "正在请求相册权限…"
        defer { isSaving = false }
        guard await SystemPhotoLibrary.requestAddPermission() else {
            permissionDenied = true
            message = "未获准添加到系统相册。请在系统设置中允许添加照片后重试。"
            return
        }
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent("photos-export-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: directory) }
        do {
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            message = "正在下载原始媒体…"
            let download = directory.appendingPathComponent("download")
            let response = try await apiClient.download(.mediaOriginal(id: item.id), to: download)
            try Task.checkCancellation()
            let ext = SystemPhotoLibrary.originalExtension(mimeType: response.mimeType,
                                                          filename: item.originalFilename, kind: item.kind)
            let file = directory.appendingPathComponent("original.\(ext)")
            try FileManager.default.moveItem(at: download, to: file)
            message = "正在保存到系统相册…"
            try await SystemPhotoLibrary.addOriginal(fileURL: file, kind: item.kind)
            message = "已保存到系统相册"
        } catch {
            message = "未能保存到相册：\(error.localizedDescription) 原始格式不受 iOS 支持时不会转存缩略图。"
        }
    }
}
