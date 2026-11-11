import Foundation

@MainActor
final class ClassifierReviewQueueStore {
    private let directoryURL: URL
    private let fileManager: FileManager

    init(directoryURL: URL = URL.applicationSupportDirectory.appending(path: "ComfyGallery", directoryHint: .isDirectory), fileManager: FileManager = .default) {
        self.directoryURL = directoryURL
        self.fileManager = fileManager
    }

    private var fileURL: URL { directoryURL.appending(path: "classifier-review-queue.json") }

    func load() throws -> ClassifierReviewQueue? {
        guard fileManager.fileExists(atPath: fileURL.path) else { return nil }
        let data = try Data(contentsOf: fileURL)
        let queue = try JSONDecoder().decode(ClassifierReviewQueue.self, from: data)
        guard !queue.mediaIDs.isEmpty, queue.mediaIDs.count <= 200, queue.currentID != nil else { return nil }
        return queue
    }

    func save(_ queue: ClassifierReviewQueue?) throws {
        guard let queue else {
            if fileManager.fileExists(atPath: fileURL.path) { try fileManager.removeItem(at: fileURL) }
            return
        }
        try fileManager.createDirectory(at: directoryURL, withIntermediateDirectories: true)
        let data = try JSONEncoder().encode(queue)
        try data.write(to: fileURL, options: [.atomic, .completeFileProtection])
    }
}
