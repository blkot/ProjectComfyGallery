import Foundation
import Photos
import UniformTypeIdentifiers

enum SystemPhotoLibrary {
    static func originalExtension(mimeType: String?, filename: String?, kind: MediaKind) -> String {
        let expected: UTType = kind == .image ? .image : .movie
        if let mimeType, let type = UTType(mimeType: mimeType), type.conforms(to: expected),
           let ext = type.preferredFilenameExtension { return ext }
        if let filename {
            let ext = URL(fileURLWithPath: filename).pathExtension.lowercased()
            if let type = UTType(filenameExtension: ext), type.conforms(to: expected) { return ext }
        }
        return kind == .image ? "png" : "mp4"
    }

    static func requestAddPermission() async -> Bool {
        let status = await PHPhotoLibrary.requestAuthorization(for: .addOnly)
        return status == .authorized || status == .limited
    }

    static func addOriginal(fileURL: URL, kind: MediaKind) async throws {
        try await PHPhotoLibrary.shared().performChanges {
            let request = PHAssetCreationRequest.forAsset()
            let options = PHAssetResourceCreationOptions()
            options.shouldMoveFile = false
            request.addResource(with: kind == .image ? .photo : .video, fileURL: fileURL, options: options)
        }
    }
}
